import datetime as dt
import itertools
import functools
import logging
import os
import platform
import re
import sys
import shutil
import threading
import traceback
from urllib.parse import urlparse
from collections import namedtuple
from time import time
from getpass import getuser

import click
import pendulum
from cli_helpers.tabular_output import TabularOutputFormatter
from cli_helpers.tabular_output.preprocessors import align_decimals, format_numbers
from cli_helpers.utils import strip_ansi
from intersystems_iris.dbapi._DBAPI import OperationalError
from prompt_toolkit.completion import DynamicCompleter, ThreadedCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER, EditingMode
from prompt_toolkit.filters import HasFocus, IsDone
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.layout.processors import (
    ConditionalProcessor,
    HighlightMatchingBracketProcessor,
    TabsProcessor,
)
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import CompleteStyle, PromptSession

from irissqlcli.completion_refresher import CompletionRefresher

from .__init__ import __version__
from .clitoolbar import create_toolbar_tokens_func
from .config import config_location, get_config, ensure_dir_exists
from .key_bindings import irissqlcli_bindings
from .lexer import IRISSqlLexer
from .sqlcompleter import SQLCompleter
from .sqlexecute import SQLExecute
from .style import style_factory, style_factory_output
from .packages.encodingutils import utf8tounicode, text_type
from .packages import special
from .packages.prompt_utils import confirm, confirm_destructive_query

COLOR_CODE_REGEX = re.compile(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))")
DEFAULT_MAX_FIELD_WIDTH = 500

# Query tuples are used for maintaining history
MetaQuery = namedtuple(
    "Query",
    [
        "query",  # The entire text of the command
        "successful",  # True If all subqueries were successful
        "total_time",  # Time elapsed executing the query and formatting results
        "execution_time",  # Time elapsed executing the query
        "meta_changed",  # True if any subquery executed create/alter/drop
        "db_changed",  # True if any subquery changed the database
        "path_changed",  # True if any subquery changed the search path
        "mutated",  # True if any subquery executed insert/update/delete
        "is_special",  # True if the query is a special command
    ],
)
MetaQuery.__new__.__defaults__ = ("", False, 0, 0, False, False, False, False)


class IRISSQLCliQuitError(Exception):
    pass


class IRISSqlCli(object):

    default_prompt = "[SQL]\\u@\\h:\\d> "
    max_len_prompt = 45

    def __init__(
        self,
        force_passwd_prompt=False,
        quiet=False,
        sqlexecute=None,
        logfile=None,
        irissqlclirc=None,
        warn=None,
        auto_vertical_output=False,
    ) -> None:
        self.force_passwd_prompt = force_passwd_prompt
        self.quiet = quiet
        self.sqlexecute = sqlexecute
        self.logfile = logfile

        c = self.config = get_config(irissqlclirc)

        self.output_file = None

        self.multi_line = c["main"].as_bool("multi_line")
        c_dest_warning = c["main"].as_bool("destructive_warning")
        self.destructive_warning = c_dest_warning if warn is None else warn

        self.min_num_menu_lines = c["main"].as_int("min_num_menu_lines")

        self.key_bindings = c["main"]["key_bindings"]
        self.table_format = c["main"]["table_format"]
        self.formatter = TabularOutputFormatter(format_name=c["main"]["table_format"])
        self.syntax_style = c["main"]["syntax_style"]
        self.less_chatty = c["main"].as_bool("less_chatty")
        self.show_bottom_toolbar = (
            False
            if isinstance(sys.stdout, ISC_StdoutTypeWrapper)
            else c["main"].as_bool("show_bottom_toolbar")
        )
        self.cli_style = c["colors"]
        self.style_output = style_factory_output(self.syntax_style, self.cli_style)
        self.wider_completion_menu = c["main"].as_bool("wider_completion_menu")
        self.autocompletion = c["main"].as_bool("autocompletion")
        self.login_path_as_host = c["main"].as_bool("login_path_as_host")

        # read from cli argument or user config file
        self.auto_vertical_output = auto_vertical_output or c["main"].as_bool(
            "auto_vertical_output"
        )

        self.logger = logging.getLogger(__name__)
        self.initialize_logging()

        keyword_casing = c["main"].get("keyword_casing", "auto")

        self.now = dt.datetime.today()

        self.completion_refresher = CompletionRefresher()

        self.query_history = []

        # Initialize completer.
        self.completer = SQLCompleter(
            supported_formats=self.formatter.supported_formats,
            keyword_casing=keyword_casing,
        )
        self._completer_lock = threading.Lock()
        self.prompt_format = c["main"].get("prompt", self.default_prompt)

        self.multiline_continuation_char = c["main"]["multiline_continuation_char"]

        self.register_special_commands()

    def quit(self):
        raise IRISSQLCliQuitError

    def register_special_commands(self):
        special.register_special_command(
            self.change_table_format,
            ".mode",
            "\\T",
            "Change the table format used to output results.",
            aliases=("tableformat", "\\T"),
            case_sensitive=True,
        )
        special.register_special_command(
            self.change_prompt_format,
            "prompt",
            "\\R",
            "Change prompt format.",
            aliases=("\\R",),
            case_sensitive=True,
        )

    def change_table_format(self, arg, **_):
        try:
            self.formatter.format_name = arg
            yield (None, None, None, "Changed table format to {}".format(arg))
        except ValueError:
            msg = "Table format {} not recognized. Allowed formats:".format(arg)
            for table_type in self.formatter.supported_formats:
                msg += "\n\t{}".format(table_type)
            yield (None, None, None, msg)

    def change_prompt_format(self, arg, **_):
        """
        Change the prompt format.
        """
        if not arg:
            message = "Missing required argument, format."
            return [(None, None, None, message)]

        self.prompt_format = self.get_prompt(arg)
        return [(None, None, None, "Changed prompt format to %s" % arg)]

    def connect_uri(self, uri):
        hostname, port, namespace, username, password, embedded =  parse_uri(uri)
        self.connect(hostname, port, namespace, username, password, embedded)

    def connect(
        self,
        hostname=None,
        port=None,
        namespace=None,
        username=None,
        password=None,
        embedded=False,
        **kwargs
    ):
        username = username or getuser()
        kwargs.setdefault("application_name", "irissqlcli")

        if not self.force_passwd_prompt and not password:
            password = os.environ.get("IRIS_PASSWORD", "")

        if self.force_passwd_prompt and not password:
            password = click.prompt(
                "Password for %s" % username,
                hide_input=True,
                show_default=False,
                type=str,
            )

        try:
            sqlexecute = SQLExecute(
                hostname, port, namespace, username, password, embedded, **kwargs
            )
        except Exception as e:  # Connecting to a database could fail.
            self.logger.debug("Database connection failed: %r.", e)
            self.logger.error("traceback: %r", traceback.format_exc())
            click.secho(str(e), err=True, fg="red")
            exit(1)

        self.sqlexecute = sqlexecute

    def get_prompt(self, string):
        # should be before replacing \\d
        string = string.replace("\\t", self.now.strftime("%x %X"))
        string = string.replace("\\u", self.sqlexecute.username or "(none)")
        string = string.replace("\\H", self.sqlexecute.hostname or "(none)")
        string = string.replace("\\h", self.sqlexecute.hostname or "(none)")
        string = string.replace("\\d", self.sqlexecute.namespace or "(none)")
        string = string.replace("\\N", self.sqlexecute.namespace or "(none)")
        string = string.replace("\\p", str(self.sqlexecute.port) or "(none)")
        string = string.replace("\\n", "\n")
        return string

    def run_query(self, query, new_line=True):
        """Runs *query*."""
        results = self.sqlexecute.run(query)
        for result in results:
            title, cur, headers, status, sql, success, is_special = result
            self.formatter.query = query
            output = self.format_output(title, cur, headers, "")
            for line in output:
                special.write_tee(line)
                click.echo(line, nl=new_line)

    def _build_cli(self, history):
        key_bindings = irissqlcli_bindings(self)

        def get_message():
            prompt_format = self.prompt_format

            prompt = self.get_prompt(prompt_format)

            if (
                prompt_format == self.default_prompt
                and len(prompt) > self.max_len_prompt
            ):
                prompt = self.get_prompt("\\d> ")

            prompt = prompt.replace("\\x1b", "\x1b")
            return ANSI(prompt)

        def get_continuation(width, line_number, is_soft_wrap):
            continuation = self.multiline_continuation_char * (width - 1) + " "
            return [("class:continuation", continuation)]

        get_toolbar_tokens = create_toolbar_tokens_func(self)

        if self.wider_completion_menu:
            complete_style = CompleteStyle.MULTI_COLUMN
        else:
            complete_style = CompleteStyle.COLUMN

        with self._completer_lock:
            prompt_app = PromptSession(
                lexer=PygmentsLexer(IRISSqlLexer),
                reserve_space_for_menu=self.min_num_menu_lines,
                message=get_message,
                prompt_continuation=get_continuation,
                bottom_toolbar=get_toolbar_tokens if self.show_bottom_toolbar else None,
                complete_style=complete_style,
                input_processors=[
                    # Highlight matching brackets while editing.
                    ConditionalProcessor(
                        processor=HighlightMatchingBracketProcessor(chars="[](){}"),
                        filter=HasFocus(DEFAULT_BUFFER) & ~IsDone(),
                    ),
                    # Render \t as 4 spaces instead of "^I"
                    TabsProcessor(char1=" ", char2=" "),
                ],
                auto_suggest=AutoSuggestFromHistory(),
                tempfile_suffix=".sql",
                history=history,
                completer=ThreadedCompleter(DynamicCompleter(lambda: self.completer)),
                complete_while_typing=True,
                style=style_factory(self.syntax_style, self.cli_style),
                include_default_pygments_style=False,
                key_bindings=key_bindings,
                enable_open_in_editor=True,
                enable_system_prompt=True,
                enable_suspend=True,
                editing_mode=EditingMode.VI
                if self.key_bindings == "vi"
                else EditingMode.EMACS,
                search_ignore_case=True,
            )

            return prompt_app

    def _evaluate_command(self, text):
        """Used to run a command entered by the user during CLI operation
        (Puts the E in REPL)

        returns (results, MetaQuery)
        """
        logger = self.logger
        logger.debug("sql: %r", text)

        # set query to formatter in order to parse table name
        self.formatter.query = text
        all_success = True
        meta_changed = False  # CREATE, ALTER, DROP, etc
        mutated = False  # INSERT, DELETE, etc
        db_changed = False
        path_changed = False
        output = []
        total = 0
        execution = 0

        # Run the query.
        start = time()
        # on_error_resume = self.on_error == "RESUME"
        res = self.sqlexecute.run(
            text,
            # self.special,
            # exception_formatter,
            # on_error_resume,
        )

        is_special = None

        for title, cur, headers, status, sql, success, is_special in res:
            logger.debug("headers: %r", headers)
            logger.debug("rows: %r", cur)
            logger.debug("status: %r", status)

            # if self._should_limit_output(sql, cur):
            #     cur, status = self._limit_output(cur)

            execution = time() - start
            formatted = self.format_output(title, cur, headers, status)

            output.extend(formatted)
            total = time() - start

            # Keep track of whether any of the queries are mutating or changing
            # the database
            if success:
                mutated = mutated or is_mutating(status)
                db_changed = db_changed or has_change_db_cmd(sql)
                meta_changed = meta_changed or has_meta_cmd(sql)
                path_changed = path_changed or has_change_path_cmd(sql)
            else:
                all_success = False

        meta_query = MetaQuery(
            text,
            all_success,
            total,
            execution,
            meta_changed,
            db_changed,
            path_changed,
            mutated,
            is_special,
        )

        return output, meta_query

    def execute_command(self, text, handle_closed_connection=True):
        logger = self.logger

        query = MetaQuery(query=text, successful=False)

        try:
            if self.destructive_warning:
                destroy = confirm_destructive_query(text)
                if destroy is None:
                    pass  # Query was not destructive. Nothing to do here.
                elif destroy is True:
                    self.echo("Your call!")
                else:
                    self.echo("Wise choice!")
                    return

            output, query = self._evaluate_command(text)
        except KeyboardInterrupt:
            logger.debug("cancelled query, sql: %r", text)
            click.secho("cancelled query", err=True, fg="red")
        except NotImplementedError:
            click.secho("Not Yet Implemented.", fg="yellow")
        except OperationalError as e:
            logger.error("sql: %r, error: %r", text, e)
            logger.error("traceback: %r", traceback.format_exc())
            click.secho(str(e), err=True, fg="red")
            if handle_closed_connection:
                self._handle_server_closed_connection(text)
        except (IRISSQLCliQuitError, EOFError) as e:
            raise
        except Exception as e:
            logger.error("sql: %r, error: %r", text, e)
            logger.error("traceback: %r", traceback.format_exc())
            click.secho(str(e), err=True, fg="red")
        else:
            try:
                self.output(output)
            except KeyboardInterrupt:
                pass

            if True or self.special.timing_enabled:
                # Only add humanized time display if > 1 second
                if query.total_time > 1:
                    print(
                        "Time: %0.03fs (%s), executed in: %0.03fs (%s)"
                        % (
                            query.total_time,
                            pendulum.Duration(seconds=query.total_time).in_words(),
                            query.execution_time,
                            pendulum.Duration(seconds=query.execution_time).in_words(),
                        )
                    )
                else:
                    print("Time: %0.03fs" % query.total_time)

            # Check if we need to update completions, in order of most
            # to least drastic changes
            if query.db_changed:
                with self._completer_lock:
                    self.completer.reset_completions()
                self.refresh_completions(persist_priorities="keywords")
            elif query.meta_changed:
                self.refresh_completions(persist_priorities="all")
            elif query.path_changed:
                logger.debug("Refreshing search path")
                with self._completer_lock:
                    self.completer.set_search_path(self.sqlexecute.search_path())
                logger.debug("Search path: %r", self.completer.search_path)
        return query

    def refresh_completions(self, history=None, persist_priorities="all"):
        """Refresh outdated completions

        :param history: A prompt_toolkit.history.FileHistory object. Used to
                        load keyword and identifier preferences

        :param persist_priorities: 'all' or 'keywords'
        """

        callback = functools.partial(
            self._on_completions_refreshed, persist_priorities=persist_priorities
        )
        return self.completion_refresher.refresh(
            self.sqlexecute,
            callback,
            {},
        )

    def _on_completions_refreshed(self, new_completer, persist_priorities):
        with self._completer_lock:
            self.completer = new_completer

        if self.prompt_app:
            # After refreshing, redraw the CLI to clear the statusbar
            # "Refreshing completions..." indicator
            self.prompt_app.app.invalidate()

    def get_completions(self, text, cursor_positition):
        with self._completer_lock:
            return self.completer.get_completions(
                Document(text=text, cursor_position=cursor_positition), None
            )

    def log_output(self, output):
        """Log the output in the audit log, if it's enabled."""
        if self.logfile:
            click.echo(utf8tounicode(output), file=self.logfile)

    def echo(self, s, **kwargs):
        """Print a message to stdout.

        The message will be logged in the audit log, if enabled.

        All keyword arguments are passed to click.echo().

        """
        self.log_output(s)
        click.secho(s, **kwargs)

    def get_output_margin(self, status=None):
        """Get the output margin (number of rows for the prompt, footer and
        timing message."""
        margin = (
            self.get_reserved_space()
            + self.get_prompt(self.prompt_format).count("\n")
            + 2
        )
        if status:
            margin += 1 + status.count("\n")

        return margin

    def initialize_logging(self):

        log_file = self.config["main"]["log_file"]
        if log_file == "default":
            log_file = config_location() + "log"
        ensure_dir_exists(log_file)
        log_level = "DEBUG" or self.config["main"]["log_level"]

        # Disable logging if value is NONE by switching to a no-op handler.
        # Set log level to a high value so it doesn't even waste cycles getting called.
        if log_level.upper() == "NONE":
            handler = logging.NullHandler()
        else:
            handler = logging.FileHandler(os.path.expanduser(log_file))

        level_map = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
            "NONE": logging.CRITICAL,
        }

        log_level = level_map[log_level.upper()]

        formatter = logging.Formatter(
            "%(asctime)s (%(process)d/%(threadName)s) "
            "%(name)s %(levelname)s - %(message)s"
        )

        handler.setFormatter(formatter)

        root_logger = logging.getLogger("irissqlcli")
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)

        root_logger.debug("Initializing irissqlcli logging.")
        root_logger.debug("Log file %r.", log_file)

    def configure_pager(self):
        # Provide sane defaults for less if they are empty.
        if not os.environ.get("LESS"):
            os.environ["LESS"] = "-RXF"

        cnf = self.read_my_cnf_files(["pager", "skip-pager"])
        if cnf["pager"]:
            special.set_pager(cnf["pager"])
            self.explicit_pager = True
        else:
            self.explicit_pager = False

        if cnf["skip-pager"] or not self.config["main"].as_bool("enable_pager"):
            special.disable_pager()

    def read_my_cnf_files(self, keys):
        """
        Reads a list of config files and merges them. The last one will win.
        :param files: list of files to read
        :param keys: list of keys to retrieve
        :returns: tuple, with None for missing keys.
        """
        cnf = self.config

        sections = ["main"]

        def get(key):
            result = None
            for sect in cnf:
                if sect in sections and key in cnf[sect]:
                    result = cnf[sect][key]
            return result

        return {x: get(x) for x in keys}

    def output(self, output, status=None):
        """Output text to stdout or a pager command.

        The status text is not outputted to pager or files.

        The message will be logged in the audit log, if enabled. The
        message will be written to the tee file, if enabled. The
        message will be written to the output file, if enabled.

        """
        if output:
            size = self.prompt_app.output.get_size()

            margin = self.get_output_margin(status)

            fits = True
            buf = []
            output_via_pager = self.explicit_pager and special.is_pager_enabled()
            for i, line in enumerate(output, 1):
                self.log_output(line)
                special.write_tee(line)
                special.write_once(line)

                if fits or output_via_pager:
                    # buffering
                    buf.append(line)
                    if len(line) > size.columns or i > (size.rows - margin):
                        fits = False
                        if not self.explicit_pager and special.is_pager_enabled():
                            # doesn't fit, use pager
                            output_via_pager = True

                        if not output_via_pager:
                            # doesn't fit, flush buffer
                            for line in buf:
                                click.secho(line)
                            buf = []
                else:
                    click.secho(line)

            if buf:
                if output_via_pager:
                    # sadly click.echo_via_pager doesn't accept generators
                    click.echo_via_pager("\n".join(buf))
                else:
                    for line in buf:
                        click.secho(line)

        if status:
            self.log_output(status)
            click.secho(status)

    def run_cli(self):
        logger = self.logger
        self.configure_pager()
        self.refresh_completions()

        history_file = self.config["main"]["history_file"]
        if history_file == "default":
            history_file = config_location() + "history"
        history = FileHistory(os.path.expanduser(history_file))

        self.prompt_app = self._build_cli(history)

        if not self.quiet:
            print("Server: ", self.sqlexecute.server_version)
            print("Version:", __version__)

        try:
            while True:
                try:
                    text = self.prompt_app.prompt()
                except KeyboardInterrupt:
                    continue

                query = self.execute_command(text)

                self.query_history.append(query)

                self.now = dt.datetime.today()

                # with self._completer_lock:
                #     self.completer.extend_query_history(text)

        except (IRISSQLCliQuitError, EOFError):
            if not self.quiet:
                print("Goodbye!")

    def get_reserved_space(self):
        """Get the number of lines to reserve for the completion menu."""
        reserved_space_ratio = 0.45
        max_reserved_space = 8
        _, height = shutil.get_terminal_size()
        return min(int(round(height * reserved_space_ratio)), max_reserved_space)

    def format_output(
        self, title, cur, headers, status, expanded=False, max_width=None
    ):
        output = []
        table_format = self.formatter.format_name

        def format_status(cur, status):
            # redshift does not return rowcount as part of status.
            # See https://github.com/dbcli/irissqlcli/issues/1320
            if cur and hasattr(cur, "rowcount") and cur.rowcount is not None:
                if status and not status.endswith(str(cur.rowcount)):
                    status += " %s" % cur.rowcount
            return status

        output_kwargs = {
            "sep_title": "RECORD {n}",
            "sep_character": "-",
            "sep_length": (1, 25),
            "preprocessors": (format_numbers, align_decimals),
            "disable_numparse": True,
            "preserve_whitespace": True,
            "style": self.style_output,
        }

        if table_format == "csv":
            # The default CSV dialect is "excel" which is not handling newline values correctly
            # Nevertheless, we want to keep on using "excel" on Windows since it uses '\r\n'
            # as the line terminator
            # https://github.com/dbcli/irissqlcli/issues/1102
            dialect = "excel" if platform.system() == "Windows" else "unix"
            output_kwargs["dialect"] = dialect

        if title:  # Only print the title if it's not None.
            output.append(title)

        if cur:
            if max_width is not None:
                cur = list(cur)
            column_types = None
            if hasattr(cur, "description"):
                column_types = [col.type_code for col in cur.description]

            formatted = self.formatter.format_output(
                cur,
                headers,
                format_name="vertical" if expanded else None,
                column_types=column_types,
                **output_kwargs,
            )
            if isinstance(formatted, str):
                formatted = iter(formatted.splitlines())
            first_line = next(formatted)
            formatted = itertools.chain([first_line], formatted)
            if (
                not expanded
                and max_width
                and len(strip_ansi(first_line)) > max_width
                and headers
            ):
                formatted = self.formatter.format_output(
                    cur,
                    headers,
                    format_name="vertical",
                    column_types=column_types,
                    **output_kwargs,
                )
                if isinstance(formatted, str):
                    formatted = iter(formatted.splitlines())

            output = itertools.chain(output, formatted)

        # Only print the status if it's not None
        if status:
            output = itertools.chain(output, [format_status(cur, status)])

        return output


CONTEXT_SETTINGS = {"help_option_names": ["--help"]}


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "-h",
    "--host",
    "hostname",
    default="localhost",
    envvar="IRIS_HOSTNAME",
    help="Host address of the IRIS instance.",
)
@click.option(
    "-p",
    "--port",
    default=1972,
    help="Port number at which the " "IRIS instance is listening.",
    envvar="IRIS_PORT",
    type=click.INT,
)
@click.option(
    "-U",
    "--username",
    "username_opt",
    help="Username to connect to the IRIS instance.",
)
@click.option(
    "-u", "--user", "username_opt", help="Username to connect to the IRIS instance."
)
@click.option(
    "-W",
    "--password",
    "prompt_passwd",
    is_flag=True,
    default=False,
    help="Force password prompt.",
)
@click.option("-v", "--version", is_flag=True, help="Version of irissqlcli.")
@click.option("-n", "--nspace", "namespace_opt", help="namespace name to connect to.")
@click.option(
    "-q",
    "--quiet",
    "quiet",
    is_flag=True,
    default=False,
    help="Quiet mode, skip intro on startup and goodbye on exit.",
)
@click.option(
    "-l",
    "--logfile",
    type=click.File(mode="a", encoding="utf-8"),
    help="Log every query and its results to a file.",
)
@click.option(
    "--irissqlclirc",
    default=config_location() + "config",
    help="Location of irissqlclirc file.",
    type=click.Path(dir_okay=False),
)
@click.option(
    "--auto-vertical-output",
    is_flag=True,
    help="Automatically switch to vertical output mode if the result is wider than the terminal width.",
)
@click.option(
    "--row-limit",
    default=None,
    envvar="IRIS_ROWLIMIT",
    type=click.INT,
    help="Set threshold for row limit prompt. Use 0 to disable prompt.",
)
@click.option(
    "-t", "--table", is_flag=True, help="Display batch output in table format."
)
@click.option("--csv", is_flag=True, help="Display batch output in CSV format.")
@click.option(
    "--warn/--no-warn", default=None, help="Warn before running a destructive query."
)
@click.option("-e", "--execute", type=str, help="Execute command and quit.")
@click.argument("uri", default=lambda: None, envvar="IRIS_URI", nargs=1)
@click.argument("username", default=lambda: None, envvar="IRIS_USERNAME", nargs=1)
def cli(
    uri,
    hostname,
    port,
    username_opt,
    namespace_opt,
    username,
    prompt_passwd,
    version,
    quiet,
    logfile,
    irissqlclirc,
    auto_vertical_output,
    csv,
    table,
    execute,
    warn,
    row_limit,
):
    if version:
        print("Version:", __version__)
        sys.exit(0)

    embedded = False
    namespace = None
    password = None
    if uri:
        hostname, port, namespace, username, password, embedded =  parse_uri(uri, hostname, port, namespace, username)

    namespace = namespace_opt or namespace or "USER"
    username = username_opt or username
    irissqlcli = IRISSqlCli(
        prompt_passwd,
        quiet,
        logfile=logfile,
        irissqlclirc=irissqlclirc,
        auto_vertical_output=auto_vertical_output,
    )

    if not namespace:
        click.secho(
            "NAMESPACE is requred. ",
            err=True,
            fg="red",
        )
    namespace = namespace.upper()

    irissqlcli.connect(hostname, port, namespace, username, password, embedded=embedded)

    irissqlcli.logger.debug(
        "Launch Params: \n" "\tnamespace: %r" "\tuser: %r" "\thost: %r" "\tport: %r",
        namespace,
        username,
        hostname,
        port,
    )

    #  --execute argument
    if execute:
        try:
            if csv:
                irissqlcli.formatter.format_name = "csv"
            elif not table:
                irissqlcli.formatter.format_name = "tsv"

            irissqlcli.run_query(execute)
            exit(0)
        except Exception as e:
            click.secho(str(e), err=True, fg="red")
            exit(1)

    if sys.stdin.isatty():
        irissqlcli.run_cli()
    else:
        stdin = click.get_text_stream("stdin")
        stdin_text = stdin.read()

        try:
            sys.stdin = open("/dev/tty")
        except (FileNotFoundError, OSError):
            irissqlcli.logger.warning("Unable to open TTY as stdin.")

        if (
            irissqlcli.destructive_warning
            and confirm_destructive_query(stdin_text) is False
        ):
            exit(0)
        try:
            new_line = True

            if csv:
                irissqlcli.formatter.format_name = "csv"
            elif not table:
                irissqlcli.formatter.format_name = "tsv"

            irissqlcli.run_query(stdin_text, new_line=new_line)
            exit(0)
        except Exception as e:
            click.secho(str(e), err=True, fg="red")
            exit(1)

def parse_uri(uri, hostname=None, port=None, namespace=None, username=None):
    parsed = urlparse(uri)
    embedded = False
    if str(parsed.scheme).startswith("iris"):
        namespace = parsed.path.split("/")[1] if parsed.path else None or namespace
        username = parsed.username or username
        password = parsed.password or None
        hostname = parsed.hostname or hostname
        port = parsed.port or port
    if parsed.scheme == "iris+emb":
        embedded = True
    return hostname, port, namespace, username, password, embedded

class ISC_StdoutTypeWrapper(object):
    def __init__(self, stdout, fileno) -> None:
        self._stdout = stdout
        self._fileno = fileno

    def fileno(self):
        return self._fileno

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return getattr(self, attr)
        return getattr(self._stdout, attr)


def cli_embedded():
    sys.stdin = ISC_StdoutTypeWrapper(sys.stdout, 0)
    sys.stdout = ISC_StdoutTypeWrapper(sys.stdout, 1)
    sys.stderr = ISC_StdoutTypeWrapper(sys.stdout, 2)
    irissqlcli = IRISSqlCli()
    irissqlcli.connect(embedded=True)
    irissqlcli.run_cli()


def has_change_db_cmd(query):
    """Determines if the statement is a database switch such as 'use' or '\\c'"""
    try:
        first_token = query.split()[0]
        if first_token.lower() in ("use", "\\c", "\\connect"):
            return True
    except Exception:
        return False

    return False


def has_change_path_cmd(sql):
    """Determines if the search_path should be refreshed by checking if the
    sql has 'set search_path'."""
    return "set search_path" in sql.lower()


def is_mutating(status):
    """Determines if the statement is mutating based on the status."""
    if not status:
        return False

    mutating = {"insert", "update", "delete"}
    return status.split(None, 1)[0].lower() in mutating


def has_meta_cmd(query):
    """Determines if the completion needs a refresh by checking if the sql
    statement is an alter, create, drop, commit or rollback."""
    try:
        first_token = query.split()[0]
        if first_token.lower() in ("alter", "create", "drop", "commit", "rollback"):
            return True
    except Exception:
        return False

    return False


def exception_formatter(e):
    return click.style(str(e), fg="red")


if __name__ == "__main__":
    cli()

from .main import IRISSqlCli
import sql.parse
import sql.connection
import logging

_logger = logging.getLogger(__name__)


def load_ipython_extension(ipython):
    """This is called via the ipython command '%load_ext irissqlcli.magic'"""

    # first, load the sql magic if it isn't already loaded
    if not ipython.find_line_magic("sql"):
        ipython.run_line_magic("load_ext", "sql")

    # register our own magic
    ipython.register_magic_function(irissqlcli_line_magic, "line", "irissqlcli")


def irissqlcli_line_magic(line):
    _logger.debug("irissqlcli magic called: %r", line)
    parsed = sql.parse.parse(line, {})
    conn = sql.connection.Connection.set(parsed["connection"], False)

    try:
        # A corresponding irissqlcli object already exists
        irissqlcli = conn._irissqlcli
        _logger.debug("Reusing existing irissqlcli")
    except AttributeError:
        irissqlcli = IRISSqlCli()
        u = conn.session.engine.url
        _logger.debug("New irissqlcli: %r", str(u))

        irissqlcli.connect_uri(str(u._replace(drivername="iris")))
        conn._irissqlcli = irissqlcli

    try:
        irissqlcli.run_cli()
    except SystemExit:
        pass

    if not irissqlcli.query_history:
        return

    q = irissqlcli.query_history[-1]

    if not q.successful:
        _logger.debug("Unsuccessful query - ignoring")
        return

    if q.meta_changed or q.db_changed or q.path_changed:
        _logger.debug("Dangerous query detected -- ignoring")
        return

    ipython = get_ipython()
    return ipython.run_cell_magic("sql", line, q.query)

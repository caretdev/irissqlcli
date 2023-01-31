from __future__ import unicode_literals
import os
import re
import locale
import logging
import subprocess
import shlex
from io import open
from time import sleep

import click
import sqlparse
from configobj import ConfigObj

from . import export
from .main import special_command, NO_QUERY, PARSED_QUERY
from .favoritequeries import FavoriteQueries
from .utils import handle_cd_command
from ..prompt_utils import confirm_destructive_query

use_expanded_output = False
PAGER_ENABLED = True
tee_file = None
once_file = written_to_once_file = None
favoritequeries = FavoriteQueries(ConfigObj())


@export
def set_favorite_queries(config):
    global favoritequeries
    favoritequeries = FavoriteQueries(config)


@export
def set_pager_enabled(val):
    global PAGER_ENABLED
    PAGER_ENABLED = val


@export
def is_pager_enabled():
    return PAGER_ENABLED


@export
@special_command(
    "pager",
    "\\P [command]",
    "Set PAGER. Print the query results via PAGER.",
    arg_type=PARSED_QUERY,
    aliases=("\\P",),
    case_sensitive=True,
)
def set_pager(arg, **_):
    if arg:
        os.environ["PAGER"] = arg
        msg = "PAGER set to %s." % arg
        set_pager_enabled(True)
    else:
        if "PAGER" in os.environ:
            msg = "PAGER set to %s." % os.environ["PAGER"]
        else:
            # This uses click's default per echo_via_pager.
            msg = "Pager enabled."
        set_pager_enabled(True)

    return [(None, None, None, msg)]


@export
@special_command(
    "nopager",
    "\\n",
    "Disable pager, print to stdout.",
    arg_type=NO_QUERY,
    aliases=("\\n",),
    case_sensitive=True,
)
def disable_pager():
    set_pager_enabled(False)
    return [(None, None, None, "Pager disabled.")]


def parseargfile(arg):
    if arg.startswith("-o "):
        mode = "w"
        filename = arg[3:]
    else:
        mode = "a"
        filename = arg

    if not filename:
        raise TypeError("You must provide a filename.")

    return {"file": os.path.expanduser(filename), "mode": mode}


@special_command(
    "tee",
    "tee [-o] filename",
    "Append all results to an output file (overwrite using -o).",
)
def set_tee(arg, **_):
    global tee_file

    try:
        tee_file = open(**parseargfile(arg))
    except (IOError, OSError) as e:
        raise OSError("Cannot write to file '{}': {}".format(e.filename, e.strerror))

    return [(None, None, None, "")]


@export
def close_tee():
    global tee_file
    if tee_file:
        tee_file.close()
        tee_file = None


@special_command("notee", "notee", "Stop writing results to an output file.")
def no_tee(arg, **_):
    close_tee()
    return [(None, None, None, "")]


@export
def write_tee(output):
    global tee_file
    if tee_file:
        click.echo(output, file=tee_file, nl=False)
        click.echo("\n", file=tee_file, nl=False)
        tee_file.flush()


@special_command(
    ".once",
    "\\o [-o] filename",
    "Append next result to an output file (overwrite using -o).",
    aliases=("\\o", "\\once"),
)
def set_once(arg, **_):
    global once_file

    once_file = parseargfile(arg)

    return [(None, None, None, "")]


@export
def write_once(output):
    global once_file, written_to_once_file
    if output and once_file:
        try:
            f = open(**once_file)
        except (IOError, OSError) as e:
            once_file = None
            raise OSError(
                "Cannot write to file '{}': {}".format(e.filename, e.strerror)
            )

        with f:
            click.echo(output, file=f, nl=False)
            click.echo("\n", file=f, nl=False)
        written_to_once_file = True


@export
def unset_once_if_written():
    """Unset the once file, if it has been written to."""
    global once_file, written_to_once_file
    if written_to_once_file:
        once_file = written_to_once_file = None

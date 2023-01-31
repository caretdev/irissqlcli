from __future__ import unicode_literals, print_function
import csv
import logging
import os
import sys
import platform
import shlex
from sqlite3 import ProgrammingError

from irissqlcli import __version__
from . import iocommands
from .utils import format_uptime
from .main import special_command, RAW_QUERY, PARSED_QUERY, ArgumentMissing

log = logging.getLogger(__name__)


@special_command(
    ".schemas",
    "\\ds",
    "List schemas.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\dt",),
)
def list_schemas(cur, arg=None, arg_type=PARSED_QUERY, verbose=False):
    if arg:
        args = ("{0}%".format(arg),)
        query = """
            SELECT name FROM sqlite_master
            WHERE type IN ('table','view') AND name LIKE ? AND name NOT LIKE 'sqlite_%'
            ORDER BY 1
        """
    else:
        args = tuple()
        query = """
            SELECT SCHEMA_NAME 
            FROM INFORMATION_SCHEMA.SCHEMATA
            WHERE 
                NOT SCHEMA_NAME %STARTSWITH '%'
            AND NOT SCHEMA_NAME %STARTSWITH 'Ens'
            AND SCHEMA_NAME <> 'INFORMATION_SCHEMA'
            ORDER BY SCHEMA_NAME
        """

    log.debug(query)
    cur.execute(query, args)
    tables = cur.fetchall()
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "")]

    return [(None, tables, headers, status)]


@special_command(
    ".tables",
    "\\dt [schema]",
    "List tables.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\dt",),
)
def list_tables(cur, arg=None, arg_type=PARSED_QUERY, verbose=False):
    schema = arg
    query = """
        SELECT TABLE_SCHEMA || '.' || TABLE_NAME AS TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES
        WHERE
    """
    if schema:
        args = ("{0}%".format(schema),)
        query += """
                TABLE_SCHEMA LIKE ?
        """
    else:
        args = tuple()
        query += """
                NOT TABLE_SCHEMA %STARTSWITH '%'
            AND NOT TABLE_SCHEMA %STARTSWITH 'Ens'
            AND TABLE_SCHEMA <> 'INFORMATION_SCHEMA'
        """

    log.debug(query)
    cur.execute(query, args)
    tables = cur.fetchall()
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "")]

    return [(None, tables, headers, status)]

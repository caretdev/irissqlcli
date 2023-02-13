from __future__ import unicode_literals, print_function
import logging

from irissqlcli import __version__
from .main import special_command, PARSED_QUERY

log = logging.getLogger(__name__)


@special_command(
    ".schemas",
    "\\ds [schema]",
    "List schemas.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\ds",),
)
def list_schemas(cur, arg=None, arg_type=PARSED_QUERY, verbose=False):
    if arg:
        args = ("{0}%".format(arg),)
        query = """
            SELECT SCHEMA_NAME 
            FROM INFORMATION_SCHEMA.SCHEMATA
            WHERE SCHEMA_NAME LIKE ?
            ORDER BY SCHEMA_NAME
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


@special_command(
    "tstart",
    "\\ts",
    "Start a Database Transaction.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\ts",),
)
def start_db_transaction(cur, arg=None, arg_type=PARSED_QUERY, verbose=False):
    cur.execute("START TRANSACTION")
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "Transaction Started")]

    return [(None, None, headers, status)]


@special_command(
    "tcommit",
    "\\tc",
    "Commit a Database Transaction.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\tc",),
)
def commit_db_transaction(cur, arg=None, arg_type=PARSED_QUERY, verbose=False):
    cur.execute("COMMIT")
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "Transaction Committed")]

    return [(None, None, headers, status)]


@special_command(
    "trollback",
    "\\tr",
    "Rollback a Database Transaction.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\tr",),
)
def rollback_db_transaction(cur, arg=None, arg_type=PARSED_QUERY, verbose=False):
    cur.execute("ROLLBACK")
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "Transaction Rolled Back")]

    return [(None, None, headers, status)]

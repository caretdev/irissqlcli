import logging
import intersystems_iris.dbapi._DBAPI as dbapi
import sqlparse
import traceback

from .packages import special

_logger = logging.getLogger(__name__)


class SQLExecute:

    schemas_query = """
        SELECT 
            SCHEMA_NAME
        FROM INFORMATION_SCHEMA.SCHEMATA
        WHERE 
            NOT SCHEMA_NAME %STARTSWITH '%'
        AND NOT SCHEMA_NAME %STARTSWITH 'Ens'
        AND SCHEMA_NAME <> 'INFORMATION_SCHEMA'
        ORDER BY SCHEMA_NAME
    """

    tables_query = """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE 
            NOT TABLE_SCHEMA %STARTSWITH '%'
        AND NOT TABLE_SCHEMA %STARTSWITH 'Ens'
        AND TABLE_SCHEMA <> 'INFORMATION_SCHEMA'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """

    table_columns_query = """
        SELECT 
            TABLE_SCHEMA, 
            TABLE_NAME,
            COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE 
            NOT TABLE_SCHEMA %STARTSWITH '%'
        AND NOT TABLE_SCHEMA %STARTSWITH 'Ens'
        AND TABLE_SCHEMA <> 'INFORMATION_SCHEMA'
        ORDER BY TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
    """

    def __init__(
        self,
        hostname,
        port,
        namespace,
        username,
        password,
        embedded=False,
        sslcontext=None,
        **kw,
    ) -> None:
        self.hostname = hostname
        self.port = port
        self.namespace = namespace
        self.username = username
        self.password = password
        self.embedded = embedded
        self.sslcontext = sslcontext
        self.extra_params = kw

        self.server_version = None

        self.connect()

    def connect(self):
        conn_params = {
            "hostname": self.hostname,
            "port": self.port,
            "namespace": self.namespace,
            "username": self.username,
            "password": self.password,
            "sslcontext": self.sslcontext,
        }
        conn_params["embedded"] = self.embedded
        conn_params.update(self.extra_params)

        conn = dbapi.connect(**conn_params)
        self.conn = conn
        self.conn.setAutoCommit(True)
        if self.embedded:
            self.server_version = self.conn.iris.system.Version.GetVersion()
            self.username = self.conn.iris.system.Process.UserName()
            self.namespace = self.conn.iris.system.Process.NameSpace()
            self.hostname = self.conn.iris.system.Util.InstallDirectory()
        else:
            self.server_version = self.conn._connection_info._server_version

    def run(
        self,
        statement,
    ):
        statement = statement.strip()
        if not statement:  # Empty string
            yield None, None, None, None, statement, False, False

        sqltemp = []
        sqlarr = []

        if statement.startswith("--"):
            sqltemp = statement.split("\n")
            sqlarr.append(sqltemp[0])
            for i in sqlparse.split(sqltemp[1]):
                sqlarr.append(i)
        elif statement.startswith("/*"):
            sqltemp = statement.split("*/")
            sqltemp[0] = sqltemp[0] + "*/"
            for i in sqlparse.split(sqltemp[1]):
                sqlarr.append(i)
        else:
            sqlarr = sqlparse.split(statement)

        # run each sql query
        for sql in sqlarr:
            # Remove spaces, eol and semi-colons.
            sql = sql.rstrip(";")
            sql = sqlparse.format(sql, strip_comments=False).strip()
            if not sql:
                continue

            try:
                try:
                    cur = self.conn.cursor()
                except dbapi.InterfaceError:
                    cur = None
                try:
                    _logger.debug("Trying a dbspecial command. sql: %r", sql)
                    for result in special.execute(cur, sql):
                        yield result + (sql, True, True)
                except special.CommandNotFound:
                    yield self.execute_normal_sql(sql) + (sql, True, False)

            except dbapi.DatabaseError as e:
                _logger.error("sql: %r, error: %r", sql, e)
                _logger.error("traceback: %r", traceback.format_exc())

                yield None, None, None, e, sql, False, False

    def execute_normal_sql(self, split_sql):
        """Returns tuple (title, rows, headers, status)"""
        _logger.debug("Regular sql statement. sql: %r", split_sql)

        title = headers = None

        cursor = self.conn.cursor()
        cursor.execute(split_sql)

        # cur.description will be None for operations that do not return
        # rows.
        if cursor.description:
            headers = [x[0] for x in cursor.description]
            status = "{0} row{1} in set"
            cursor = list(cursor)
            rowcount = len(cursor)
        else:
            _logger.debug("No rows in result.")
            status = "Query OK, {0} row{1} affected"
            rowcount = 0 if cursor.rowcount == -1 else cursor.rowcount
            cursor = None

        status = status.format(rowcount, "" if rowcount == 1 else "s")

        return (title, cursor, headers, status)

    def schemas(self):
        """Yields schema names"""

        with self.conn.cursor() as cur:
            _logger.debug("Schemas Query. sql: %r", self.schemas_query)
            cur.execute(self.schemas_query)
            for row in cur:
                yield row

    def tables(self):
        """Yields table names"""

        with self.conn.cursor() as cur:
            _logger.debug("Tables Query. sql: %r", self.tables_query)
            cur.execute(self.tables_query)
            for row in cur:
                yield row

    def table_columns(self):
        """Yields column names"""
        with self.conn.cursor() as cur:
            _logger.debug("Columns Query. sql: %r", self.table_columns_query)
            cur.execute(self.table_columns_query)
            for row in cur:
                yield row

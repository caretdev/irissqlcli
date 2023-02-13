from __future__ import print_function
from __future__ import unicode_literals
import logging
from re import compile, escape
from collections import Counter

from prompt_toolkit.completion import Completer, Completion

from .packages.completion_engine import suggest_type
from .packages.parseutils import last_word
from .packages.special.iocommands import favoritequeries
from .packages.filepaths import parse_path, complete_path, suggest_path

_logger = logging.getLogger(__name__)


class SQLCompleter(Completer):
    keywords = [
        "ABORT",
        "ACTION",
        "ADD",
        "AFTER",
        "ALL",
        "ALTER",
        "ANALYZE",
        "AND",
        "AS",
        "ASC",
        "ATTACH",
        "AUTOINCREMENT",
        "BEFORE",
        "BEGIN",
        "BETWEEN",
        "BIGINT",
        "BLOB",
        "BOOLEAN",
        "BY",
        "CASCADE",
        "CASE",
        "CAST",
        "CHARACTER",
        "CHECK",
        "CLOB",
        "COLLATE",
        "COLUMN",
        "COMMIT",
        "CONFLICT",
        "CONSTRAINT",
        "CREATE",
        "CROSS",
        "CURRENT",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "DATABASE",
        "DATE",
        "DATETIME",
        "DECIMAL",
        "DEFAULT",
        "DEFERRABLE",
        "DEFERRED",
        "DELETE",
        "DETACH",
        "DISTINCT",
        "DO",
        "DOUBLE PRECISION",
        "DOUBLE",
        "DROP",
        "EACH",
        "ELSE",
        "END",
        "ESCAPE",
        "EXCEPT",
        "EXCLUSIVE",
        "EXISTS",
        "EXPLAIN",
        "FAIL",
        "FILTER",
        "FLOAT",
        "FOLLOWING",
        "FOR",
        "FOREIGN",
        "FROM",
        "FULL",
        "GLOB",
        "GROUP",
        "HAVING",
        "IF",
        "IGNORE",
        "IMMEDIATE",
        "IN",
        "INDEX",
        "INDEXED",
        "INITIALLY",
        "INNER",
        "INSERT",
        "INSTEAD",
        "INT",
        "INT2",
        "INT8",
        "INTEGER",
        "INTERSECT",
        "INTO",
        "IS",
        "ISNULL",
        "JOIN",
        "KEY",
        "LEFT",
        "LIKE",
        "MATCH",
        "MEDIUMINT",
        "NATIVE CHARACTER",
        "NATURAL",
        "NCHAR",
        "NO",
        "NOT",
        "NOTHING",
        "NULL",
        "NULLS FIRST",
        "NULLS LAST",
        "NUMERIC",
        "NVARCHAR",
        "OF",
        "OFFSET",
        "ON",
        "OR",
        "ORDER BY",
        "OUTER",
        "OVER",
        "PARTITION",
        "PLAN",
        "PRAGMA",
        "PRECEDING",
        "PRIMARY",
        "QUERY",
        "RAISE",
        "RANGE",
        "REAL",
        "RECURSIVE",
        "REFERENCES",
        "REGEXP",
        "REINDEX",
        "RELEASE",
        "RENAME",
        "REPLACE",
        "RESTRICT",
        "RIGHT",
        "ROLLBACK",
        "ROW",
        "ROWS",
        "SAVEPOINT",
        "SELECT",
        "SET",
        "SMALLINT",
        "TABLE",
        "TEMP",
        "TEMPORARY",
        "TEXT",
        "THEN",
        "TINYINT",
        "TO",
        "TRANSACTION",
        "TRIGGER",
        "UNBOUNDED",
        "UNION",
        "UNIQUE",
        "UNSIGNED BIG INT",
        "UPDATE",
        "USING",
        "VACUUM",
        "VALUES",
        "VARCHAR",
        "VARYING CHARACTER",
        "VIEW",
        "VIRTUAL",
        "WHEN",
        "WHERE",
        "WINDOW",
        "WITH",
        "WITHOUT",
    ]

    agg_functions = [
        "AVG",
        "COUNT",
        "%DLIST",
        "LIST",
        "MIN",
        "MAX",
    ]

    functions = [
        "ABS",
        "ACOS",
        "ASCII",
        "ASIN",
        "ATAN",
        "ATAN2",
        "CAST",
        "CEILING",
        "CHAR",
        "CHARACTER_LENGTH",
        "CHARINDEX",
        "CHAR_LENGTH",
        "COALESCE",
        "CONCAT",
        "CONVERT",
        "COS",
        "COT",
        "CURDATE",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "CURTIME",
        "DATABASE",
        "DATALENGTH",
        "DATE",
        "DATEADD",
        "DATEDIFF",
        "DATENAME",
        "DATEPART",
        "DAY",
        "DAYNAME",
        "DAYOFMONTH",
        "DAYOFWEEK",
        "DAYOFYEAR",
        "DECODE",
        "DEGREES",
        "%EXACT",
        "EXP",
        "%EXTERNAL",
        "$EXTRACT",
        "$FIND",
        "FLOOR",
        "GETDATE",
        "GETUTCDATE",
        "GREATEST",
        "HOUR",
        "IFNULL",
        "INSTR",
        "%INTERNAL",
        "ISNULL",
        "ISNUMERIC",
        "JSON_ARRAY",
        "JSON_OBJECT",
        "$JUSTIFY",
        "LAST_DAY",
        "LAST_IDENTITY",
        "LCASE",
        "LEAST",
        "LEFT",
        "LEN",
        "LENGTH",
        "$LENGTH",
        "$LIST",
        "$LISTBUILD",
        "$LISTDATA",
        "$LISTFIND",
        "$LISTFROMSTRING",
        "$LISTGET",
        "$LISTLENGTH",
        "$LISTSAME",
        "$LISTTOSTRING",
        "LOG",
        "LOG10",
        "LOWER",
        "LPAD",
        "LTRIM",
        "%MINUS",
        "MINUTE",
        "MOD",
        "MONTH",
        "MONTHNAME",
        "NOW",
        "NULLIF",
        "NVL",
        "%OBJECT",
        "%ODBCIN",
        "%ODBCOUT",
        "%OID",
        "PI",
        "$PIECE",
        "%PLUS",
        "POSITION",
        "POWER",
        "PREDICT",
        "PROBABILITY",
        "QUARTER",
        "RADIANS",
        "REPEAT",
        "REPLACE",
        "REPLICATE",
        "REVERSE",
        "RIGHT",
        "ROUND",
        "RPAD",
        "RTRIM",
        "SEARCH_INDEX",
        "SECOND",
        "SIGN",
        "SIN",
        "SPACE",
        "%SQLSTRING",
        "%SQLUPPER",
        "SQRT",
        "SQUARE",
        "STR",
        "STRING",
        "STUFF",
        "SUBSTR",
        "SUBSTRING",
        "SYSDATE",
        "TAN",
        "TIMESTAMPADD",
        "TIMESTAMPDIFF",
        "TO_CHAR",
        "TO_DATE",
        "TO_NUMBER",
        "TO_POSIXTIME",
        "TO_TIMESTAMP",
        "$TRANSLATE",
        "TRIM",
        "TRUNCATE",
        "%TRUNCATE",
        "$TSQL_NEWID",
        "UCASE",
        "UNIX_TIMESTAMP",
        "UPPER",
        "USER",
        "WEEK",
        "XMLCONCAT",
        "XMLELEMENT",
        "XMLFOREST",
        "YEAR",
    ]

    variables = [
        "$HOROLOG",
        "$JOB",
        "$NAMESPACE",
        "$TLEVEL",
        "$USERNAME",
        "$ZHOROLOG",
        "$ZJOB",
        "$ZPI",
        "$ZTIMESTAMP",
        "$ZTIMEZONE",
        "$ZVERSION",
    ]

    def __init__(self, supported_formats=(), keyword_casing="auto"):
        super(self.__class__, self).__init__()
        self.reserved_words = set()
        for x in self.keywords:
            self.reserved_words.update(x.split())
        self.name_pattern = compile("^[_a-z][_a-z0-9\$]*$")

        self.special_commands = []
        self.table_formats = supported_formats
        if keyword_casing not in ("upper", "lower", "auto"):
            keyword_casing = "auto"
        self.keyword_casing = keyword_casing
        self.reset_completions()

    def escape_name(self, name):
        if name and (
            (not self.name_pattern.match(name))
            or (name.upper() in self.reserved_words)
            or (name.upper() in self.functions)
        ):
            name = ".".join(['"%s"' % n for n in name.split(".")])

        return name

    def unescape_name(self, name):
        """Unquote a string."""
        if name and name[0] == '"' and name[-1] == '"':
            name = name[1:-1]

        return name

    def escaped_names(self, names):
        return [self.escape_name(name) for name in names]

    def extend_special_commands(self, special_commands):
        # Special commands are not part of all_completions since they can only
        # be at the beginning of a line.
        self.special_commands.extend(special_commands)

    def extend_database_names(self, databases):
        self.databases.extend(databases)

    def extend_keywords(self, additional_keywords):
        self.keywords.extend(additional_keywords)
        self.all_completions.update(additional_keywords)

    def extend_schemas(self, data, kind):
        try:
            data = [self.escaped_names(d) for d in data]
        except Exception as ex:
            logging.exception(ex)
            data = []

        metadata = self.dbmetadata[kind]
        for [
            schema,
        ] in data:
            metadata[schema] = {}
            self.all_completions.add(schema)

    def extend_relations(self, data, kind):
        """Extend metadata for tables or views

        :param data: list of (rel_name, ) tuples
        :param kind: either 'tables' or 'views'
        :return:
        """
        # 'data' is a generator object. It can throw an exception while being
        # consumed. This could happen if the user has launched the app without
        # specifying a database name. This exception must be handled to prevent
        # crashing.
        try:
            data = [self.escaped_names(d) for d in data]
        except Exception as ex:
            logging.exception(ex)
            data = []

        # dbmetadata['tables'][$schema_name][$table_name] should be a list of
        # column names. Default to an asterisk
        metadata = self.dbmetadata[kind]
        for [schema, relname] in data:
            metadata[schema] = metadata[schema] if schema in metadata else {}
            metadata[schema][relname] = ["*"]
            self.all_completions.add(relname)

    def extend_columns(self, column_data, kind):
        """Extend column metadata

        :param column_data: list of (rel_name, column_name) tuples
        :param kind: either 'tables' or 'views'
        :return:
        """
        # 'column_data' is a generator object. It can throw an exception while
        # being consumed. This could happen if the user has launched the app
        # without specifying a database name. This exception must be handled to
        # prevent crashing.
        try:
            column_data = [self.escaped_names(d) for d in column_data]
        except Exception as ex:
            logging.exception(ex)
            column_data = []

        metadata = self.dbmetadata[kind]
        for schema, relname, column in column_data:
            metadata[schema][relname].append(column)
            self.all_completions.add(column)

    def extend_functions(self, func_data):
        # 'func_data' is a generator object. It can throw an exception while
        # being consumed. This could happen if the user has launched the app
        # without specifying a database name. This exception must be handled to
        # prevent crashing.
        try:
            func_data = [self.escaped_names(d) for d in func_data]
        except Exception:
            func_data = []

        # dbmetadata['functions'][$schema_name][$function_name] should return
        # function metadata.
        metadata = self.dbmetadata["functions"]

        for func in func_data:
            metadata[func[0]] = None
            self.all_completions.add(func[0])

    def reset_completions(self):
        self.databases = []
        self.dbmetadata = {"tables": {}, "views": {}, "functions": {}}
        self.all_completions = set(
            self.keywords + self.agg_functions + self.functions + self.variables
        )

    @staticmethod
    def find_matches(
        text,
        collection,
        start_only=False,
        fuzzy=True,
        casing=None,
        punctuations="most_punctuations",
    ):
        """Find completion matches for the given text.

        Given the user's input text and a collection of available
        completions, find completions matching the last word of the
        text.

        If `start_only` is True, the text will match an available
        completion only at the beginning. Otherwise, a completion is
        considered a match if the text appears anywhere within it.

        yields prompt_toolkit Completion instances for any matches found
        in the collection of available completions.
        """
        last = last_word(text, include=punctuations)
        text = last.lower()

        completions = []

        if fuzzy:
            regex = ".*?".join(map(escape, text))
            pat = compile("(%s)" % regex)
            for item in sorted(collection):
                r = pat.search(item.lower())
                if r:
                    completions.append((len(r.group()), r.start(), item))
        else:
            match_end_limit = len(text) if start_only else None
            for item in sorted(collection):
                match_point = item.lower().find(text, 0, match_end_limit)
                if match_point >= 0:
                    completions.append((len(text), match_point, item))

        if casing == "auto":
            casing = "lower" if last and last[-1].islower() else "upper"

        def apply_case(kw):
            if casing == "upper":
                return kw.upper()
            return kw.lower()

        _logger.debug(
            "find_matches: %r; %r - %r/%r",
            fuzzy,
            text,
            len(collection),
            len(completions),
        )
        return (
            Completion(z if casing is None else apply_case(z), -len(text))
            for x, y, z in sorted(completions)
        )

    def get_completions(self, document, complete_event):
        word_before_cursor = document.get_word_before_cursor(WORD=True)
        completions = []
        suggestions = []
        suggestions = suggest_type(document.text, document.text_before_cursor)

        for suggestion in suggestions:

            _logger.debug("Suggestion for: %r", document.text)
            _logger.debug("Suggestion type: %r", suggestion["type"])

            if suggestion["type"] == "column":
                tables = suggestion["tables"]
                _logger.debug("Completion column scope: %r", tables)
                scoped_cols = self.populate_scoped_cols(tables)
                if suggestion.get("drop_unique"):
                    # drop_unique is used for 'tb11 JOIN tbl2 USING (...'
                    # which should suggest only columns that appear in more than
                    # one table
                    scoped_cols = [
                        col
                        for (col, count) in Counter(scoped_cols).items()
                        if count > 1 and col != "*"
                    ]

                cols = self.find_matches(word_before_cursor, scoped_cols)
                completions.extend(cols)

            elif suggestion["type"] == "function":
                # suggest user-defined functions using substring matching
                funcs = self.populate_schema_objects(suggestion["schema"], "functions")
                user_funcs = self.find_matches(word_before_cursor, funcs)
                completions.extend(user_funcs)

                # suggest hardcoded functions using startswith matching only if
                # there is no schema qualifier. If a schema qualifier is
                # present it probably denotes a table.
                # eg: SELECT * FROM users u WHERE u.
                if not suggestion["schema"]:
                    predefined_funcs = self.find_matches(
                        word_before_cursor,
                        self.functions + self.agg_functions + self.variables,
                        start_only=True,
                        fuzzy=False,
                        casing=self.keyword_casing,
                    )
                    completions.extend(predefined_funcs)

            elif suggestion["type"] == "schema":
                schemas = self.populate_schema_objects(None, "schemas")
                schemas = self.find_matches(word_before_cursor, schemas)
                completions.extend(schemas)

            elif suggestion["type"] == "table":
                tables = self.populate_schema_objects(suggestion["schema"], "tables")
                tables = self.find_matches(word_before_cursor, tables)
                completions.extend(tables)

            elif suggestion["type"] == "view":
                views = self.populate_schema_objects(suggestion["schema"], "views")
                views = self.find_matches(word_before_cursor, views)
                completions.extend(views)

            elif suggestion["type"] == "alias":
                aliases = suggestion["aliases"]
                aliases = self.find_matches(word_before_cursor, aliases)
                completions.extend(aliases)

            elif suggestion["type"] == "database":
                dbs = self.find_matches(word_before_cursor, self.databases)
                completions.extend(dbs)

            elif suggestion["type"] == "keyword":
                keywords = self.find_matches(
                    word_before_cursor,
                    self.keywords,
                    start_only=True,
                    fuzzy=False,
                    casing=self.keyword_casing,
                    punctuations="many_punctuations",
                )
                completions.extend(keywords)

            elif suggestion["type"] == "special":
                special = self.find_matches(
                    word_before_cursor,
                    self.special_commands,
                    start_only=True,
                    fuzzy=False,
                    punctuations="many_punctuations",
                )
                completions.extend(special)
            # elif suggestion["type"] == "favoritequery":
            #     queries = self.find_matches(
            #         word_before_cursor,
            #         favoritequeries.list(),
            #         start_only=False,
            #         fuzzy=True,
            #     )
            #     completions.extend(queries)
            elif suggestion["type"] == "table_format":
                formats = self.find_matches(
                    word_before_cursor, self.table_formats, start_only=True, fuzzy=False
                )
                completions.extend(formats)
            elif suggestion["type"] == "file_name":
                file_names = self.find_files(word_before_cursor)
                completions.extend(file_names)

        _logger.debug("Completions: %r", len(completions))
        return completions

    def find_files(self, word):
        """Yield matching directory or file names.

        :param word:
        :return: iterable

        """
        # base_path, last_path, position = parse_path(word)
        # paths = suggest_path(word)
        # for name in sorted(paths):
        #     suggestion = complete_path(name, last_path)
        #     if suggestion:
        #         yield Completion(suggestion, position)

    def populate_scoped_cols(self, scoped_tbls):
        """Find all columns in a set of scoped_tables
        :param scoped_tbls: list of (schema, table, alias) tuples
        :return: list of column names
        """
        columns = []
        meta = self.dbmetadata

        _logger.debug("populate_scoped_cols: %r", scoped_tbls)

        for (schema, relname, _) in scoped_tbls:
            _logger.debug("populate_scoped_cols: %r.%r", schema, relname)
            # A fully qualified schema.relname reference or default_schema
            # DO NOT escape schema names.
            schema = schema if schema is not None else "SQLUser"

            for obj_type in ["tables", "views"]:
                if not obj_type in meta:
                    continue
                for _schema in [schema, self.escape_name(schema)]:
                    if not _schema in meta[obj_type]:
                        continue
                    for _relname in [relname, self.escape_name(relname)]:
                        if not _relname in meta[obj_type][_schema]:
                            continue
                        columns.extend(meta[obj_type][_schema][_relname])
        return list(set(columns))

    def populate_schema_objects(self, schema, obj_type):
        """Returns list of tables or functions for a (optional) schema"""
        objects = []
        if obj_type == "schemas":
            obj_type = "tables"
            schema = "SQLUser"
            schemas = []
            schemas.extend(self.dbmetadata["tables"].keys())
            schemas.extend(self.dbmetadata["views"].keys())
            objects.extend([schema + "." for schema in schemas])
        metadata = self.dbmetadata[obj_type]
        schema = (
            schema if not isinstance(schema, list) else schema[0] if schema else None
        )
        if schema is None:
            return objects
        try:
            if schema is None:
                objects = metadata.keys()
            elif schema in metadata:
                objects.extend(metadata[schema].keys())
            elif self.escape_name(schema) in metadata:
                objects.extend(metadata[self.escape_name(schema)].keys())
        except KeyError:
            _logger.debug("populate_schema_objects error: %r - %r\n", schema, obj_type)
            # schema doesn't exist

        return objects

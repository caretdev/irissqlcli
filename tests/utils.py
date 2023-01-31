# -*- coding: utf-8 -*-
from os import getenv
import time
import signal
import platform
import multiprocessing
import logging
from contextlib import closing

import intersystems_iris.dbapi._DBAPI as dbapi
import pytest

from irissqlcli.main import special

IRIS_HOSTNAME = getenv("IRIS_HOSTNAME", "localhost")
IRIS_PORT = getenv("IRIS_PORT", 1972)
IRIS_NAMESPACE = getenv("IRIS_NAMESPACE", "USER")
IRIS_USERNAME = getenv("IRIS_USERNAME", "_SYSTEM")
IRIS_PASSWORD = getenv("IRIS_PASSWORD", "SYS")


def db_connection(embedded=False):
    if embedded:
        conn = dbapi.connect(embedded=True)
    else:
        conn = dbapi.connect(
            hostname=IRIS_HOSTNAME,
            port=IRIS_PORT,
            namespace=IRIS_NAMESPACE,
            username=IRIS_USERNAME,
            password=IRIS_PASSWORD,
        )
    return conn


try:
    db_connection()
    CAN_CONNECT_TO_DB = True
except Exception as ex:
    CAN_CONNECT_TO_DB = False

dbtest = pytest.mark.skipif(
    not CAN_CONNECT_TO_DB, reason="Error creating IRIS connection"
)


def drop_tables(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME from INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ?",
            ["SQLUser"],
        )
        tables = [row[0] for row in cursor]
        for table in tables:
            cursor.execute(f"DROP TABLE {table}")


def run(executor, sql, rows_as_list=True):
    """Return string output for the sql to be run."""
    result = []

    for title, rows, headers, status, sql, success, is_special in executor.run(sql):
        rows = list(rows) if (rows_as_list and rows) else rows
        result.append(
            {"title": title, "rows": rows, "headers": headers, "status": status}
        )

    return result


def set_expanded_output(is_expanded):
    """Pass-through for the tests."""
    return special.set_expanded_output(is_expanded)


def is_expanded_output():
    """Pass-through for the tests."""
    return special.is_expanded_output()


def send_ctrl_c_to_pid(pid, wait_seconds):
    """Sends a Ctrl-C like signal to the given `pid` after `wait_seconds`
    seconds."""
    time.sleep(wait_seconds)
    system_name = platform.system()
    if system_name == "Windows":
        os.kill(pid, signal.CTRL_C_EVENT)
    else:
        os.kill(pid, signal.SIGINT)


def send_ctrl_c(wait_seconds):
    """Create a process that sends a Ctrl-C like signal to the current process
    after `wait_seconds` seconds.

    Returns the `multiprocessing.Process` created.

    """
    ctrl_c_process = multiprocessing.Process(
        target=send_ctrl_c_to_pid, args=(os.getpid(), wait_seconds)
    )
    ctrl_c_process.start()
    return ctrl_c_process

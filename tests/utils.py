# -*- coding: utf-8 -*-
import os
import time
import signal
import platform
import multiprocessing

import intersystems_iris.dbapi._DBAPI as dbapi
import pytest

from irissqlcli.main import special


def db_connection(embedded=False):
    if embedded:
        conn = dbapi.connect(embedded=True)
    else:
        conn = dbapi.connect(
            hostname=pytest.iris_hostname,
            port=pytest.iris_port,
            namespace=pytest.iris_namespace,
            username=pytest.iris_username,
            password=pytest.iris_password,
        )
    return conn


def check_connection():
    try:
        db_connection()
        return True
    except Exception as ex:  # noqa
        print(ex)
        return False


def dbtest():
    if check_connection():

        def decorator(func):
            return func

        return decorator

    return pytest.mark.skip(reason="Error creating IRIS connection")


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

from __future__ import print_function

import os
import pytest
from utils import (
    IRIS_HOSTNAME,
    IRIS_PORT,
    IRIS_NAMESPACE,
    IRIS_USERNAME,
    IRIS_PASSWORD,
    db_connection,
    drop_tables,
)
import irissqlcli.sqlexecute


@pytest.fixture(scope="function")
def connection():
    connection = db_connection()
    drop_tables(connection)
    yield connection

    drop_tables(connection)
    connection.close()


@pytest.fixture
def cursor(connection):
    with connection.cursor() as cur:
        return cur


@pytest.fixture
def executor(connection):
    return irissqlcli.sqlexecute.SQLExecute(
        hostname=IRIS_HOSTNAME,
        port=IRIS_PORT,
        namespace=IRIS_NAMESPACE,
        username=IRIS_USERNAME,
        password=IRIS_PASSWORD,
    )


@pytest.fixture
def exception_formatter():
    return lambda e: str(e)


@pytest.fixture(scope="session", autouse=True)
def temp_config(tmpdir_factory):
    # this function runs on start of test session.
    # use temporary directory for config home so user config will not be used
    os.environ["XDG_CONFIG_HOME"] = str(tmpdir_factory.mktemp("data"))

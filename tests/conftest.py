from __future__ import print_function

import os
import pytest
from pytest import Config
from testcontainers.iris import IRISContainer
from utils import (
    db_connection,
    drop_tables,
)
from irissqlcli.sqlexecute import SQLExecute
from click.testing import CliRunner


def pytest_addoption(parser):
    group = parser.getgroup("iris")

    group.addoption(
        "--container",
        action="store",
        default=None,
        type=str,
        help="Docker image with IRIS",
    )


def pytest_configure(config: Config):
    global iris
    iris = None
    container = config.getoption("container")
    if not container:
        pytest.iris_hostname = os.getenv("IRIS_HOSTNAME", "localhost")
        pytest.iris_port = int(os.getenv("IRIS_PORT", 1972))
        pytest.iris_username = os.getenv("IRIS_USERNAME", "_SYSTEM")
        pytest.iris_password = os.getenv("IRIS_PASSWORD", "SYS")
        pytest.iris_namespace = os.getenv("IRIS_NAMESPACE", "USER")
        pytest.url
        return

    print("Starting IRIS container:", container)
    iris = IRISContainer(
        container,
        username="irissqlcli",
        password="irissqlcli",
        namespace="TEST",
        license_key=os.path.expanduser("~/iris-community.key"),
    )
    iris.start()
    print("dburi:", iris.get_connection_url())
    pytest.dburi = iris.get_connection_url()
    pytest.iris_hostname = "localhost"
    pytest.iris_port = int(iris.get_exposed_port(1972))
    pytest.iris_username = iris.username
    pytest.iris_password = iris.password
    pytest.iris_namespace = iris.namespace


def pytest_unconfigure(config):
    global iris
    if iris and iris._container:
        print("Stopping IRIS container", iris)
        iris.stop()


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
    return SQLExecute.from_uri(pytest.dburi)


@pytest.fixture
def runner():
    return CliRunner(
        env={
            "IRIS_URI": pytest.dburi,
        }
    )


@pytest.fixture
def exception_formatter():
    return lambda e: str(e)


@pytest.fixture(scope="session", autouse=True)
def temp_config(tmpdir_factory):
    # this function runs on start of test session.
    # use temporary directory for config home so user config will not be used
    os.environ["XDG_CONFIG_HOME"] = str(tmpdir_factory.mktemp("data"))

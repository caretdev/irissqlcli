#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
from io import open
import re
import os
from setuptools import setup, find_packages

_version_re = re.compile(r"__version__\s+=\s+(.*)")

with open("irissqlcli/__init__.py", "rb") as f:
    version = str(
        ast.literal_eval(_version_re.search(f.read().decode("utf-8")).group(1))
    )


def open_file(filename):
    """Open and read the file *filename*."""
    with open(filename) as f:
        return f.read()


readme = open_file("README.md")

install_requirements = [
    "click >= 4.1",
    "Pygments>=2.0",
    "prompt_toolkit>=3.0.3,<4.0.0",
    "sqlparse >=0.3.0,<0.5",
    "configobj >= 5.0.6",
    "pendulum ~= 2.1.0",
    "cli_helpers[styles] >= 2.2.1",
]

setup(
    name="irissqlcli",
    author="CaretDev",
    author_email="irissqlcli@caretdev.com",
    license="MIT",
    version=version,
    url="https://github.com/caretdev/irissqlcli",
    packages=find_packages(),
    package_data={"irissqlcli": ["irissqlclirc", "AUTHORS"]},
    description="CLI for SQL of InterSystems IRIS Databases with "
    "auto-completion and syntax highlighting.",
    long_description=readme,
    long_description_content_type="text/markdown",
    install_requires=install_requirements,
    entry_points={
        "console_scripts": ["irissqlcli = irissqlcli.main:cli"],
        "distutils.commands": ["lint = tasks:lint", "test = tasks:test"],
    },
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Unix",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: SQL",
        "Topic :: Database",
        "Topic :: Database :: Front-Ends",
        "Topic :: Software Development",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)

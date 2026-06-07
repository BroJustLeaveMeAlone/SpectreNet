import pytest
from spectrenet.wrappers.builtin.sqlmap import SqlmapWrapper

INJECTABLE_OUTPUT = """\
[INFO] GET parameter 'id' is vulnerable. Do you want to keep testing the others (if any)? [y/N] N
[INFO] sqlmap identified the following injection point(s) with a total of 42 HTTP(s) requests:
Parameter: id (GET)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
available databases [2]:
[*] information_schema
[*] webapp
"""

NOT_INJECTABLE = "[INFO] all tested parameters do not appear to be injectable"


def test_parse_injectable_true():
    result = SqlmapWrapper().parse(INJECTABLE_OUTPUT)
    assert result["injectable"] is True


def test_parse_detects_payload_type():
    result = SqlmapWrapper().parse(INJECTABLE_OUTPUT)
    assert "boolean-based blind" in result["payloads"]


def test_parse_extracts_databases():
    result = SqlmapWrapper().parse(INJECTABLE_OUTPUT)
    assert "webapp" in result["databases"]
    assert "information_schema" in result["databases"]


def test_parse_not_injectable():
    result = SqlmapWrapper().parse(NOT_INJECTABLE)
    assert result["injectable"] is False
    assert result["databases"] == []


def test_schema_present():
    schema = SqlmapWrapper().schema
    assert "injectable" in schema
    assert "databases" in schema

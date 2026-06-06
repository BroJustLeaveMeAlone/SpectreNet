# tests/conftest.py
import logging
import pytest

@pytest.fixture(autouse=True)
def quiet_logging():
    logging.getLogger("spectrenet").handlers.clear()
    logging.getLogger("spectrenet").addHandler(logging.NullHandler())
    yield

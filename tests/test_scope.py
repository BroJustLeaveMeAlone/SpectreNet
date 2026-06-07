import pytest
from spectrenet.scope import ScopeEnforcer


def test_no_scope_allows_all():
    s = ScopeEnforcer()
    assert s.in_scope("192.168.1.1")
    assert s.in_scope("10.0.0.1")
    assert s.active is False


def test_single_cidr_in_scope():
    s = ScopeEnforcer(["192.168.1.0/24"])
    assert s.in_scope("192.168.1.1")
    assert s.in_scope("192.168.1.254")
    assert not s.in_scope("192.168.2.1")
    assert not s.in_scope("10.0.0.1")


def test_multiple_cidrs():
    s = ScopeEnforcer(["10.0.0.0/24", "172.16.0.0/16"])
    assert s.in_scope("10.0.0.5")
    assert s.in_scope("172.16.50.1")
    assert not s.in_scope("10.0.1.1")
    assert not s.in_scope("192.168.1.1")


def test_add_cidr():
    s = ScopeEnforcer()
    assert s.active is False
    ok = s.add("10.10.10.0/24")
    assert ok is True
    assert s.active is True
    assert s.in_scope("10.10.10.1")


def test_add_invalid_cidr():
    s = ScopeEnforcer()
    ok = s.add("not-a-cidr")
    assert ok is False
    assert s.active is False


def test_hostname_passes_through():
    s = ScopeEnforcer(["10.0.0.0/8"])
    assert s.in_scope("example.com") is True


def test_check_args_all_in_scope():
    s = ScopeEnforcer(["10.0.0.0/24"])
    ok, out = s.check_args(["nmap", "10.0.0.5", "-sV"])
    assert ok is True
    assert out == []


def test_check_args_out_of_scope():
    s = ScopeEnforcer(["10.0.0.0/24"])
    ok, out = s.check_args(["nmap", "192.168.1.1", "-sV"])
    assert ok is False
    assert "192.168.1.1" in out


def test_check_args_no_scope():
    s = ScopeEnforcer()
    ok, out = s.check_args(["nmap", "1.2.3.4", "-sV"])
    assert ok is True
    assert out == []


def test_summary_no_scope():
    s = ScopeEnforcer()
    assert "no scope" in s.summary()


def test_summary_with_scope():
    s = ScopeEnforcer(["10.0.0.0/8"], strict=True)
    summary = s.summary()
    assert "10.0.0.0/8" in summary
    assert "strict" in summary.lower()


def test_summary_warn_mode():
    s = ScopeEnforcer(["10.0.0.0/8"], strict=False)
    summary = s.summary()
    assert "warn" in summary.lower()


def test_invalid_cidr_in_constructor():
    s = ScopeEnforcer(["10.0.0.0/24", "bad-input", "192.168.1.0/24"])
    assert len(s._networks) == 2

# tests/test_approval_gate.py
from spectrenet.tui.approval_gate import (
    ActionCard, ApprovalResult, format_action_card
)
from spectrenet.storage.session import SessionStore

def test_approval_result_enum_values():
    assert ApprovalResult.APPROVED.value == "Y"
    assert ApprovalResult.DENIED.value == "N"
    assert ApprovalResult.SKIPPED.value == "S"

def test_action_card_holds_fields():
    card = ActionCard(
        action="exploit/multi/handler",
        target="192.168.1.45:445",
        module="ms17_010_eternalblue",
        risk="HIGH",
        reason="SMB service detected, patch level < 2017",
    )
    assert card.action == "exploit/multi/handler"
    assert card.risk == "HIGH"

def test_format_action_card_contains_key_fields():
    card = ActionCard(
        action="exploit/multi/handler",
        target="192.168.1.45:445",
        module="ms17_010_eternalblue",
        risk="HIGH",
        reason="EternalBlue candidate",
    )
    rendered = format_action_card(card)
    assert "APPROVAL REQUIRED" in rendered
    assert "exploit/multi/handler" in rendered
    assert "192.168.1.45:445" in rendered
    assert "ms17_010_eternalblue" in rendered
    assert "HIGH" in rendered
    assert "[Y]" in rendered
    assert "[N]" in rendered
    assert "[S]" in rendered

def test_format_action_card_truncates_long_values():
    long_action = "exploit/windows/smb/" + "x" * 60
    card = ActionCard(
        action=long_action,
        target="192.168.1.1:445",
        module="ms17_010",
        risk="HIGH",
        reason="test",
    )
    rendered = format_action_card(card)
    # Every line must have the same length (box border intact)
    lines = rendered.split("\n")
    lengths = [len(line) for line in lines]
    assert len(set(lengths)) == 1, f"Inconsistent line lengths: {lengths}"
    assert "…" in rendered  # truncation marker present

def test_session_store_logs_approval(tmp_path):
    store = SessionStore(tmp_path / "s.db")
    sid = store.create_session("test", "alice")
    store.log_approval(
        session_id=sid,
        operator="alice",
        action="exploit/multi/handler",
        target="192.168.1.45:445",
        risk="HIGH",
        result="Y",
    )
    approvals = store.approvals_for(sid)
    assert len(approvals) == 1
    assert approvals[0]["result"] == "Y"
    assert approvals[0]["action"] == "exploit/multi/handler"

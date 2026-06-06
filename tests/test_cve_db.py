# tests/test_cve_db.py
from spectrenet.knowledge.cve_db import CVEKnowledgeBase

def test_seed_and_query_by_service(tmp_path):
    kb = CVEKnowledgeBase(tmp_path / "cve.db")
    kb.add_cve("CVE-2017-0144", 9.3, "microsoft-ds", "Samba 4.6", "EternalBlue SMB RCE")
    kb.add_cve("CVE-2014-6271", 10.0, "bash", "<4.3", "Shellshock")
    hits = kb.find_by_service("microsoft-ds")
    assert len(hits) == 1
    assert hits[0]["cve_id"] == "CVE-2017-0144"
    assert hits[0]["cvss"] == 9.3

def test_query_unknown_service_returns_empty(tmp_path):
    kb = CVEKnowledgeBase(tmp_path / "cve.db")
    assert kb.find_by_service("nothing") == []

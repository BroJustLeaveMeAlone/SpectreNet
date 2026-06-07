import pytest
from spectrenet.knowledge.vector_store import VectorStore


@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_dir=tmp_path / "vectors")


def test_add_and_count(store):
    store.add("CVE-2021-44228", "Log4Shell JNDI injection RCE Apache Log4j", {"service": "http"})
    store.add("CVE-2017-0144",  "EternalBlue MS17-010 SMBv1 unauth RCE",      {"service": "smb"})
    assert store.count() == 2


def test_search_returns_results(store):
    store.add("CVE-2021-44228", "Log4Shell JNDI injection RCE Apache Log4j",     {"service": "http"})
    store.add("CVE-2017-0144",  "EternalBlue MS17-010 SMBv1 unauth RCE",          {"service": "smb"})
    store.add("CVE-2019-0708",  "BlueKeep pre-auth RCE Windows 7 via RDP",        {"service": "rdp"})
    results = store.search("RCE")
    assert len(results) >= 1
    assert all("id" in r and "text" in r and "score" in r for r in results)


def test_search_most_relevant_first(store):
    store.add("CVE-A", "apache path traversal remote code execution",  {})
    store.add("CVE-B", "mysql authentication bypass credential dump",   {})
    store.add("CVE-C", "apache buffer overflow denial of service",      {})
    results = store.search("apache path traversal")
    # First result should mention apache
    assert results[0]["id"] in ("CVE-A", "CVE-C")


def test_search_empty_store(store):
    results = store.search("anything")
    assert results == []


def test_upsert_replaces_existing(store):
    store.add("CVE-X", "old description", {})
    store.add("CVE-X", "new updated description with more detail", {})
    assert store.count() == 1
    results = store.search("new updated description")
    assert len(results) >= 1


def test_add_exploit(store):
    store.add_exploit("50383", "Apache Path Traversal RCE",
                      "Unauthenticated path traversal on Apache 2.4.49",
                      "exploit/multi/http/apache_path_traversal")
    assert store.count() == 1
    results = store.search("apache traversal")
    assert len(results) >= 1


def test_seed_from_cves(tmp_path):
    from spectrenet.knowledge.cve_db import CVEKnowledgeBase
    db = CVEKnowledgeBase(tmp_path / "cves.db")
    db.add_cve("CVE-2021-44228", 10.0, "http",  "", "Log4Shell JNDI injection")
    db.add_cve("CVE-2017-0144",   9.3, "smb",   "", "EternalBlue SMBv1")
    db.add_cve("CVE-2019-0708",   9.8, "rdp",   "", "BlueKeep pre-auth RCE")
    store = VectorStore(persist_dir=tmp_path / "vecs")
    n = store.seed_from_cves(db)
    assert n == 3
    assert store.count() == 3
    db.close()


def test_backend_property(store):
    assert store.backend in ("chromadb", "fallback")


def test_search_n_limit(store):
    for i in range(10):
        store.add(f"CVE-{i}", f"vulnerability rce remote code execution {i}", {})
    results = store.search("rce remote code execution", n=3)
    assert len(results) <= 3

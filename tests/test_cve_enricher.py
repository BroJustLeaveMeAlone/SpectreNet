import pytest
from pathlib import Path
from spectrenet.knowledge.cve_enricher import CVEEnricher


@pytest.fixture
def enricher(tmp_path):
    e = CVEEnricher(tmp_path / "test_cve.db")
    yield e
    e._db.close()


def test_seed_data_loaded(enricher):
    rows = enricher._db.conn.execute("SELECT COUNT(*) FROM cves").fetchone()[0]
    assert rows > 0


def test_enrich_empty_hosts(enricher):
    alerts = enricher.enrich({})
    assert alerts == []


def test_enrich_ftp_vsftpd(enricher):
    hosts = {"10.0.0.1": [{"port": "21", "proto": "tcp", "service": "ftp", "version": "vsftpd 2.3.4"}]}
    alerts = enricher.enrich(hosts)
    cve_ids = [a["cve_id"] for a in alerts]
    assert "CVE-2011-2523" in cve_ids


def test_enrich_smb_eternalblue(enricher):
    hosts = {"10.0.0.2": [{"port": "445", "proto": "tcp", "service": "smb", "version": ""}]}
    alerts = enricher.enrich(hosts)
    cve_ids = [a["cve_id"] for a in alerts]
    assert "CVE-2017-0144" in cve_ids


def test_enrich_http_apache_path_traversal(enricher):
    hosts = {"10.0.0.3": [{"port": "80", "proto": "tcp", "service": "http", "version": "Apache httpd 2.4.49"}]}
    alerts = enricher.enrich(hosts)
    cve_ids = [a["cve_id"] for a in alerts]
    assert "CVE-2021-41773" in cve_ids


def test_enrich_https_falls_through_to_http(enricher):
    hosts = {"10.0.0.4": [{"port": "443", "proto": "tcp", "service": "https", "version": "Apache httpd 2.4.49"}]}
    alerts = enricher.enrich(hosts)
    cve_ids = [a["cve_id"] for a in alerts]
    assert "CVE-2021-41773" in cve_ids


def test_enrich_rdp_bluekeep(enricher):
    hosts = {"10.0.0.5": [{"port": "3389", "proto": "tcp", "service": "rdp", "version": ""}]}
    alerts = enricher.enrich(hosts)
    cve_ids = [a["cve_id"] for a in alerts]
    assert "CVE-2019-0708" in cve_ids


def test_enrich_alert_fields(enricher):
    hosts = {"10.0.0.1": [{"port": "21", "proto": "tcp", "service": "ftp", "version": "vsftpd 2.3.4"}]}
    alerts = enricher.enrich(hosts)
    assert len(alerts) > 0
    a = alerts[0]
    assert "ip"          in a
    assert "port"        in a
    assert "cve_id"      in a
    assert "cvss"        in a
    assert "description" in a


def test_enrich_sorted_by_cvss(enricher):
    hosts = {"10.0.0.1": [
        {"port": "21",  "proto": "tcp", "service": "ftp", "version": "vsftpd 2.3.4"},
        {"port": "22",  "proto": "tcp", "service": "ssh", "version": ""},
        {"port": "445", "proto": "tcp", "service": "smb", "version": ""},
    ]}
    alerts = enricher.enrich(hosts)
    cvss_scores = [a["cvss"] for a in alerts]
    assert cvss_scores == sorted(cvss_scores, reverse=True)


def test_enrich_no_match_unknown_service(enricher):
    hosts = {"10.0.0.1": [{"port": "9999", "proto": "tcp", "service": "unknownsvc", "version": "1.0"}]}
    alerts = enricher.enrich(hosts)
    assert alerts == []


def test_enrich_deduplication(enricher):
    hosts = {"10.0.0.1": [{"port": "445", "proto": "tcp", "service": "smb", "version": ""}]}
    alerts = enricher.enrich(hosts)
    keys = [(a["ip"], a["port"], a["cve_id"]) for a in alerts]
    assert len(keys) == len(set(keys))


def test_two_instances_both_seeded(tmp_path):
    e1 = CVEEnricher(tmp_path / "db1.db")
    e2 = CVEEnricher(tmp_path / "db2.db")
    count1 = e1._db.conn.execute("SELECT COUNT(*) FROM cves").fetchone()[0]
    count2 = e2._db.conn.execute("SELECT COUNT(*) FROM cves").fetchone()[0]
    assert count1 > 0
    assert count2 > 0
    e1._db.close()
    e2._db.close()

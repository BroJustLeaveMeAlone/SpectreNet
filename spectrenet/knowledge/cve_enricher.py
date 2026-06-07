"""
Automatic CVE enrichment for nmap findings.

After a scan, call enrich(hosts) with the dict returned by parse_nmap_text().
Returns a list of alerts — one per (ip, port, CVE) hit — sorted by CVSS descending.
"""
from __future__ import annotations

from pathlib import Path
from spectrenet.knowledge.cve_db import CVEKnowledgeBase

_DB_PATH = Path(".spectrenet_cve.db")


# ── Built-in CVE seed data ────────────────────────────────────────────────────
# (cve_id, cvss, service, version_match, description)
# version_match: substring expected in nmap's version field ("" = any version)

_SEED_CVES = [
    # FTP
    ("CVE-2011-2523", 10.0, "ftp",   "vsftpd 2.3.4",  "vsftpd 2.3.4 backdoor — connects to port 6200 for root shell. MSF: exploit/unix/ftp/vsftpd_234_backdoor"),
    ("CVE-2015-3306", 10.0, "ftp",   "ProFTPD 1.",     "ProFTPD mod_copy unauthenticated RCE — copy arbitrary files via CPFR/CPTO. MSF: exploit/unix/ftp/proftpd_modcopy_exec"),

    # SSH
    ("CVE-2018-15473", 5.3, "ssh",   "",               "OpenSSH username enumeration (all versions < 7.7) — leaks valid usernames via timing difference"),
    ("CVE-2023-38408", 9.8, "ssh",   "",               "OpenSSH ssh-agent RCE via forwarded agent — exploitable if agent forwarding enabled. Patch: OpenSSH 9.3p2+"),

    # HTTP / Apache
    ("CVE-2021-41773", 9.8, "http",  "2.4.49",         "Apache 2.4.49 path traversal + RCE (if mod_cgi on) — unauthenticated. PoC: curl 'http://target/cgi-bin/.%2e/.%2e/etc/passwd'"),
    ("CVE-2021-42013", 9.8, "http",  "2.4.50",         "Apache 2.4.50 path traversal bypass (CVE-2021-41773 patch bypass). Same exploitation method."),
    ("CVE-2017-7679",  9.8, "http",  "2.2.",           "Apache 2.2.x mod_mime buffer overflow — can lead to RCE. Upgrade immediately."),
    ("CVE-2019-10082", 7.5, "http",  "2.4.3",          "Apache 2.4.17–2.4.38 HTTP/2 read-after-free DoS. Affects most 2.4.3x versions."),
    ("CVE-2021-44228", 10.0,"http",  "",               "Log4Shell — Log4j JNDI injection RCE. Affects any Java app using Log4j 2.0–2.14. Test all HTTP services."),

    # IIS
    ("CVE-2017-7269",  10.0,"http",  "IIS/6.0",        "IIS 6.0 WebDAV buffer overflow — unauthenticated RCE. MSF: exploit/windows/iis/iis_webdav_scstoragepathfromurl"),

    # SMB / Windows
    ("CVE-2017-0144",  9.3, "smb",   "",               "MS17-010 EternalBlue — unauthenticated RCE on SMBv1 (Windows 7/2008/2012/2016 unpatched). MSF: exploit/windows/smb/ms17_010_eternalblue"),
    ("CVE-2020-0796",  10.0,"smb",   "3.1.1",          "SMBGhost — Windows 10 1903/1909 SMBv3 RCE. MSF: exploit/windows/smb/cve_2020_0796_smbghost"),
    ("CVE-2017-7494",  10.0,"smb",   "Samba",          "SambaCry — Samba < 4.6.4 writable share RCE. MSF: exploit/linux/samba/is_known_pipename"),
    ("CVE-2021-44142", 9.9, "smb",   "Samba 4.",       "Samba heap RCE via VFS module — Samba 4.13.x/4.14.x/4.15.x. Patch to 4.13.17+/4.14.12+/4.15.5+"),

    # RDP
    ("CVE-2019-0708",  9.8, "rdp",   "",               "BlueKeep — pre-auth RCE on Windows 7/2008 via RDP. MSF: exploit/windows/rdp/cve_2019_0708_bluekeep_rce"),
    ("CVE-2019-1181",  9.8, "rdp",   "",               "DejaBlue — pre-auth RCE on Windows 8/10/2012/2016/2019 via RDP. Patch: MS19-Aug Security Update"),

    # MySQL
    ("CVE-2012-2122",  5.1, "mysql", "5.1.",           "MySQL 5.1.x authentication bypass — repeated login attempts with wrong password may authenticate. MSF: auxiliary/scanner/mysql/mysql_authbypass_hashdump"),
    ("CVE-2016-6662",  10.0,"mysql", "",               "MySQL < 5.7.15 remote code execution via malicious config. MSF: exploit/multi/mysql/mysql_udf_payload"),

    # FTP misc
    ("CVE-2010-2075",  7.5, "irc",   "3.2.8.1",        "UnrealIRCd 3.2.8.1 backdoor — DEBUG3_DOLOG_SYSTEM command gives remote shell. MSF: exploit/unix/irc/unreal_ircd_3281_backdoor"),

    # Tomcat
    ("CVE-2017-12617", 9.8, "http",  "Tomcat",         "Apache Tomcat PUT method RCE — upload JSP via PUT request if readonly=false. MSF: exploit/multi/http/tomcat_jsp_upload_bypass"),
    ("CVE-2020-1938",  9.8, "ajp",   "",               "Ghostcat — Apache Tomcat AJP connector file read/include. Any Tomcat < 9.0.31/8.5.51/7.0.100. MSF: auxiliary/admin/http/tomcat_ghostcat"),

    # PHP
    ("CVE-2012-1823",  7.5, "http",  "PHP/5.",         "PHP CGI argument injection — passes query string as CLI args. MSF: exploit/multi/http/php_cgi_arg_injection"),

    # Unauthenticated services (version_match="" matches all)
    ("NOAUTH-REDIS",   9.1, "redis", "",               "Redis with no authentication — allows arbitrary file write and potential RCE via config set/slave replication. Run: redis-cli -h target INFO"),
    ("NOAUTH-MONGO",   9.1, "mongodb","",              "MongoDB with no authentication — full DB read/write access without credentials. Run: mongo --host target"),
    ("NOAUTH-ELASTIC", 9.1, "elasticsearch","",        "Elasticsearch with no authentication — full index access. Run: curl http://target:9200/_cat/indices"),
    ("NOAUTH-MEMCACHE",7.5, "memcached","",            "Memcached unauthenticated — cache dump + potential SSRF amplification. Run: echo 'stats' | nc target 11211"),
    ("NOAUTH-COUCH",   9.1, "couchdb","",              "CouchDB with admin party mode — full DB access. Check: curl http://target:5984/_all_dbs"),
]


def get_enricher() -> "CVEEnricher":
    return CVEEnricher(_DB_PATH)


class CVEEnricher:
    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self._db = CVEKnowledgeBase(db_path)
        self._seed()

    def _seed(self) -> None:
        cur = self._db.conn.execute("SELECT COUNT(*) FROM cves").fetchone()[0]
        if cur == 0:
            for row in _SEED_CVES:
                self._db.add_cve(*row)

    def enrich(self, hosts: dict[str, list[dict]]) -> list[dict]:
        """
        Cross-reference parsed nmap hosts against the CVE DB.

        hosts: {ip: [{port, proto, service, version}, ...]}
        Returns list of alert dicts sorted by cvss desc.
        """
        alerts = []
        for ip, ports in hosts.items():
            for entry in ports:
                service = entry.get("service", "").lower()
                version = entry.get("version", "")
                port    = entry.get("port", "")
                if not service:
                    continue
                hits = self._find(service, version)
                for hit in hits:
                    alerts.append({
                        "ip":          ip,
                        "port":        port,
                        "service":     service,
                        "cve_id":      hit["cve_id"],
                        "cvss":        hit["cvss"],
                        "description": hit["description"],
                    })
        alerts.sort(key=lambda a: a["cvss"], reverse=True)
        # Deduplicate same CVE on same ip:port
        seen: set[tuple] = set()
        unique = []
        for a in alerts:
            key = (a["ip"], a["port"], a["cve_id"])
            if key not in seen:
                seen.add(key)
                unique.append(a)
        return unique

    def _find(self, service: str, version: str) -> list[dict]:
        # https also checks http CVEs — same vulnerabilities apply
        services     = [service, "http"] if service == "https" else [service]
        placeholders = ",".join("?" * len(services))
        rows = self._db.conn.execute(
            f"SELECT * FROM cves WHERE service IN ({placeholders}) ORDER BY cvss DESC",
            services,
        ).fetchall()
        version_lower = version.lower()
        return [
            dict(r) for r in rows
            if not r["version_match"] or r["version_match"].lower() in version_lower
        ]

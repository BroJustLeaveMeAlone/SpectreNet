"""
Tool availability checker and install helper.

snet tools          -- show all tool status (same as snet tools status)
snet tools status   -- show all tool status
snet tools install  -- print install commands for every missing tool
"""
from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field


@dataclass
class _Tool:
    name:             str
    description:      str
    binary:           str          # primary binary to check on PATH
    alt_binaries:     list[str]    = field(default_factory=list)  # fallback binaries
    apt:              str          = ""   # apt package name
    brew:             str          = ""   # homebrew formula
    pip:              str          = ""   # pip package (if applicable)
    go_install:       str          = ""   # go install URL
    gem_install:      str          = ""   # gem install package
    notes:            str          = ""
    api_key_required: bool         = False


# ---- Tool definitions -------------------------------------------------------

_TOOLS: list[_Tool] = [
    # Recon
    _Tool("nmap",         "Network/port/service/OS detection",
          "nmap",         apt="nmap",             brew="nmap"),
    _Tool("masscan",      "High-speed port scanning",
          "masscan",      apt="masscan",           brew="masscan"),
    _Tool("subfinder",    "Passive subdomain enumeration",
          "subfinder",    apt="subfinder",         brew="subfinder",
          go_install="github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"),
    _Tool("shodan",       "Shodan host intelligence lookup",
          "shodan",       pip="shodan",
          notes="After install: shodan init <your-api-key>",
          api_key_required=True),

    # Web
    _Tool("nikto",        "Web server vulnerability scanning",
          "nikto",        apt="nikto",             brew="nikto"),
    _Tool("nuclei",       "Template-based CVE and vulnerability scanning",
          "nuclei",       apt="nuclei",            brew="nuclei",
          go_install="github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"),
    _Tool("gobuster",     "Directory and DNS brute-forcing",
          "gobuster",     apt="gobuster",          brew="gobuster"),
    _Tool("sqlmap",       "Automated SQL injection detection",
          "sqlmap",       apt="sqlmap",            brew="sqlmap",     pip="sqlmap"),
    _Tool("whatweb",      "Web technology fingerprinting",
          "whatweb",      apt="whatweb",
          gem_install="whatweb",
          notes="Linux/macOS -- also: gem install whatweb"),

    # SMB / AD
    _Tool("enum4linux",   "SMB/NetBIOS enumeration",
          "enum4linux",   apt="enum4linux",
          notes="Linux/macOS only"),
    _Tool("crackmapexec", "SMB/AD/SSH credential testing and lateral movement",
          "netexec",      alt_binaries=["nxc", "crackmapexec", "cme"],
          apt="crackmapexec",   pip="netexec",
          notes="Accepts netexec (nxc), crackmapexec (cme), or netexec"),

    # Exploitation
    _Tool("hydra",        "Login brute-force (SSH, FTP, HTTP, SMB...)",
          "hydra",        apt="hydra",             brew="hydra"),
    _Tool("searchsploit", "Offline exploit database search",
          "searchsploit", apt="exploitdb",         brew="exploitdb"),
    _Tool("msfvenom",     "Payload generation (part of Metasploit)",
          "msfvenom",     apt="metasploit-framework",
          notes="Included with Metasploit Framework"),

    # Metasploit
    _Tool("metasploit",   "MSF console, exploit modules, session management",
          "msfconsole",   apt="metasploit-framework", brew="metasploit",
          notes="Start RPC before launching SpectreNet: msfrpcd -P msf -S false"),
]


# ---- Helpers ----------------------------------------------------------------

def _os() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    return "linux"


def _is_available(t: _Tool) -> bool:
    if shutil.which(t.binary):
        return True
    return any(shutil.which(b) for b in t.alt_binaries)


def _install_hint(t: _Tool, os_name: str) -> str:
    if os_name == "linux":
        if t.apt:
            return f"sudo apt install {t.apt}"
        if t.pip:
            return f"pip install {t.pip}"
        if t.go_install:
            return f"go install -v {t.go_install}"
        if t.gem_install:
            return f"gem install {t.gem_install}"
    elif os_name == "macos":
        if t.brew:
            return f"brew install {t.brew}"
        if t.pip:
            return f"pip install {t.pip}"
        if t.go_install:
            return f"go install -v {t.go_install}"
        if t.gem_install:
            return f"gem install {t.gem_install}"
    elif os_name == "windows":
        if t.pip:
            return f"pip install {t.pip}"
        return "WSL recommended -- wsl --install, then re-run snet tools install"
    return t.notes or "see project docs"


# ---- Public commands --------------------------------------------------------

def cmd_tools_status() -> None:
    os_name = _os()
    n_ok = sum(1 for t in _TOOLS if _is_available(t))

    print(f"\n  SpectreNet Tool Status  [{os_name}]")
    print("  " + "-" * 58)

    categories = [
        ("Recon",         ["nmap", "masscan", "subfinder", "shodan"]),
        ("Web",           ["nikto", "nuclei", "gobuster", "sqlmap", "whatweb"]),
        ("SMB / AD",      ["enum4linux", "crackmapexec"]),
        ("Exploitation",  ["hydra", "searchsploit", "msfvenom", "metasploit"]),
    ]

    for cat_name, names in categories:
        print(f"\n  {cat_name}")
        for name in names:
            t = next((x for x in _TOOLS if x.name == name), None)
            if t is None:
                continue
            ok   = _is_available(t)
            mark = "OK" if ok else "--"
            api  = "  (API key required)" if t.api_key_required else ""
            flag = "  (run: msfrpcd -P msf -S false)" if name == "metasploit" and ok else ""
            print(f"    [{mark}]  {t.name:<16} {t.description}{api}{flag}")

    print()
    print(f"  {n_ok}/{len(_TOOLS)} tools available", end="")
    if n_ok < len(_TOOLS):
        print("  --  run 'snet tools install' for install commands", end="")
    print("\n")


def cmd_tools_install() -> None:
    os_name  = _os()
    missing  = [t for t in _TOOLS if not _is_available(t)]

    if not missing:
        print("\n  All tools are installed.\n")
        return

    print(f"\n  Install commands for missing tools  [{os_name}]")
    print("  " + "-" * 58)

    if os_name == "linux":
        apt_pkgs = [t.apt for t in missing if t.apt]
        if apt_pkgs:
            print(f"\n  # Install all at once (Kali / Debian / Ubuntu / Parrot):")
            print(f"  sudo apt install -y {' '.join(apt_pkgs)}")

        go_tools = [t for t in missing if t.go_install]
        if go_tools:
            print(f"\n  # Go-based tools  (requires Go -- https://go.dev/dl/):")
            for t in go_tools:
                print(f"  go install -v {t.go_install}")

        pip_tools = [t for t in missing if t.pip and not t.apt]
        if pip_tools:
            print(f"\n  # Python packages:")
            for t in pip_tools:
                print(f"  pip install {t.pip}")

    elif os_name == "macos":
        brew_tools = [t for t in missing if t.brew]
        if brew_tools:
            print(f"\n  # Homebrew:")
            print(f"  brew install {' '.join(t.brew for t in brew_tools)}")

        go_tools = [t for t in missing if t.go_install]
        if go_tools:
            print(f"\n  # Go-based tools  (requires Go -- https://go.dev/dl/):")
            for t in go_tools:
                print(f"  go install -v {t.go_install}")

        pip_tools = [t for t in missing if t.pip and not t.brew]
        if pip_tools:
            print(f"\n  # Python packages:")
            for t in pip_tools:
                print(f"  pip install {t.pip}")

    elif os_name == "windows":
        print()
        print("  Most tools run best under WSL (Windows Subsystem for Linux).")
        print("  Enable WSL:  wsl --install")
        print("  Then open a WSL shell and run:  snet tools install")
        print()
        pip_tools = [t for t in missing if t.pip]
        if pip_tools:
            print("  # Python packages (install natively on Windows):")
            for t in pip_tools:
                print(f"  pip install {t.pip}")

    api_tools = [t for t in missing if t.api_key_required]
    if api_tools:
        print(f"\n  # API key setup (after installing the package):")
        for t in api_tools:
            print(f"  {t.name:<16}  {t.notes}")

    msf_missing = next((t for t in missing if t.name == "metasploit"), None)
    if msf_missing:
        print(f"\n  # After installing Metasploit -- start the RPC daemon:")
        print(f"  msfrpcd -P msf -S false")

    print()

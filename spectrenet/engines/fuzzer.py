"""HTTP fuzzer — wordlist-driven path and parameter fuzzing."""
from __future__ import annotations

import time
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


_DEFAULT_WORDLIST = [
    "admin", "administrator", "login", "dashboard", "api", "v1", "v2",
    "config", "backup", "test", "dev", "staging", "phpinfo.php", ".env",
    "robots.txt", "sitemap.xml", ".git/HEAD", "wp-admin", "wp-login.php",
    "manager", "phpmyadmin", "actuator", "swagger", "api-docs", "graphql",
    "console", "status", "health", "metrics", "debug", "shell.php",
    "upload", "uploads", "files", "images", "static", "assets",
]


@dataclass
class FuzzResult:
    path:    str
    status:  int
    length:  int
    elapsed: float


class HTTPFuzzer:
    """
    Fuzz HTTP paths on a target URL.

    Usage:
        fuzzer = HTTPFuzzer("http://10.0.0.1")
        for result in fuzzer.fuzz():
            print(result)
    """

    def __init__(
        self,
        base_url: str,
        wordlist: list[str] | None = None,
        wordlist_file: str | None = None,
        threads: int = 10,
        timeout: float = 5.0,
        delay: float = 0.0,
        filter_codes: set[int] | None = None,
    ) -> None:
        self._base_url     = base_url.rstrip("/")
        self._wordlist     = self._load_wordlist(wordlist, wordlist_file)
        self._threads      = max(1, threads)
        self._timeout      = timeout
        self._delay        = delay
        self._filter_codes = filter_codes or {404, 400}

    def _load_wordlist(self, words: list[str] | None, path: str | None) -> list[str]:
        if path:
            p = Path(path)
            if p.exists():
                return [line.strip() for line in p.read_text().splitlines() if line.strip()]
        return words or list(_DEFAULT_WORDLIST)

    def fuzz(self, callback=None) -> list[FuzzResult]:
        """Fuzz all paths, returning a list of interesting results."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list[FuzzResult] = []

        def probe(path: str) -> FuzzResult | None:
            url = f"{self._base_url}/{path}"
            try:
                t0  = time.monotonic()
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    body   = resp.read()
                    status = resp.status
                    length = len(body)
            except urllib.error.HTTPError as e:
                status = e.code
                length = 0
                t0 = time.monotonic() - t0
            except Exception:
                return None
            elapsed = time.monotonic() - t0
            if self._delay:
                time.sleep(self._delay)
            if status in self._filter_codes:
                return None
            return FuzzResult(path=path, status=status, length=length, elapsed=elapsed)

        with ThreadPoolExecutor(max_workers=self._threads) as executor:
            futures = {executor.submit(probe, p): p for p in self._wordlist}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
                    if callback:
                        callback(result)

        results.sort(key=lambda r: (r.status, -r.length))
        return results

    def fuzz_params(
        self,
        url: str,
        param: str,
        payloads: list[str] | None = None,
    ) -> list[FuzzResult]:
        """Fuzz a single query parameter with a list of payloads."""
        _payloads = payloads or [
            "'", "\"", "1 OR 1=1", "<script>alert(1)</script>",
            "../../../../etc/passwd", "| id", "; id", "${7*7}",
            "{{7*7}}", "admin'--", "%00", "null", "undefined",
        ]
        results = []
        for payload in _payloads:
            params  = urllib.parse.urlencode({param: payload})
            full    = f"{url}?{params}"
            try:
                t0  = time.monotonic()
                req = urllib.request.Request(full, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    body   = resp.read()
                    status = resp.status
                    length = len(body)
                elapsed = time.monotonic() - t0
                results.append(FuzzResult(path=f"{param}={payload}", status=status, length=length, elapsed=elapsed))
            except urllib.error.HTTPError as e:
                results.append(FuzzResult(path=f"{param}={payload}", status=e.code, length=0, elapsed=0.0))
            except Exception:
                pass
        return results

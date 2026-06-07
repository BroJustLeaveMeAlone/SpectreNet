"""Web crawler — link and form extractor for recon and attack surface mapping."""
from __future__ import annotations

import re
import time
import urllib.request
import urllib.parse
import urllib.error
from collections import deque
from dataclasses import dataclass, field


_LINK_RE = re.compile(r'href=["\']([^"\'#\s]+)["\']', re.IGNORECASE)
_SRC_RE  = re.compile(r'src=["\']([^"\'#\s]+)["\']',  re.IGNORECASE)
_FORM_RE = re.compile(
    r'<form[^>]*action=["\']([^"\']*)["\'][^>]*method=["\']?(\w+)["\']?[^>]*>',
    re.IGNORECASE,
)
_INPUT_RE = re.compile(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)


@dataclass
class CrawlPage:
    url:    str
    status: int
    links:  list[str] = field(default_factory=list)
    forms:  list[dict] = field(default_factory=list)
    depth:  int = 0


class WebCrawler:
    """
    BFS web crawler — stays within the same origin by default.

    Usage:
        crawler = WebCrawler("http://10.0.0.1", max_pages=50)
        pages   = crawler.crawl()
    """

    def __init__(
        self,
        start_url: str,
        max_pages:  int   = 100,
        max_depth:  int   = 3,
        timeout:    float = 5.0,
        delay:      float = 0.1,
        same_origin: bool = True,
    ) -> None:
        self._start      = start_url.rstrip("/")
        self._max_pages  = max_pages
        self._max_depth  = max_depth
        self._timeout    = timeout
        self._delay      = delay
        self._same_origin = same_origin
        parsed           = urllib.parse.urlparse(start_url)
        self._origin     = f"{parsed.scheme}://{parsed.netloc}"

    def crawl(self, callback=None) -> list[CrawlPage]:
        visited: set[str] = set()
        queue   = deque([(self._start, 0)])
        pages   : list[CrawlPage] = []

        while queue and len(pages) < self._max_pages:
            url, depth = queue.popleft()
            if url in visited or depth > self._max_depth:
                continue
            visited.add(url)

            page = self._fetch(url, depth)
            if page is None:
                continue
            pages.append(page)
            if callback:
                callback(page)

            for link in page.links:
                abs_link = self._abs(url, link)
                if abs_link and abs_link not in visited:
                    if not self._same_origin or abs_link.startswith(self._origin):
                        queue.append((abs_link, depth + 1))

            if self._delay:
                time.sleep(self._delay)

        return pages

    def _fetch(self, url: str, depth: int) -> CrawlPage | None:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body   = resp.read().decode("utf-8", errors="ignore")
                status = resp.status
        except urllib.error.HTTPError as e:
            return CrawlPage(url=url, status=e.code, depth=depth)
        except Exception:
            return None

        links = list(dict.fromkeys(
            self._abs(url, m.group(1)) or m.group(1)
            for m in _LINK_RE.finditer(body)
        ))
        links += list(dict.fromkeys(
            self._abs(url, m.group(1)) or m.group(1)
            for m in _SRC_RE.finditer(body)
        ))

        forms = []
        for m in _FORM_RE.finditer(body):
            action  = m.group(1) or url
            method  = m.group(2).upper()
            # Extract input names from what follows the form tag (crude but effective)
            form_block_start = m.start()
            form_block_end   = body.find("</form>", form_block_start)
            form_block       = body[form_block_start: form_block_end + 7] if form_block_end != -1 else ""
            inputs           = _INPUT_RE.findall(form_block)
            forms.append({
                "action": self._abs(url, action) or action,
                "method": method,
                "inputs": inputs,
            })

        return CrawlPage(url=url, status=status, links=links, forms=forms, depth=depth)

    def _abs(self, base: str, href: str) -> str | None:
        if not href:
            return None
        if href.startswith(("http://", "https://")):
            return href.split("?")[0].split("#")[0]
        if href.startswith("//"):
            parsed = urllib.parse.urlparse(base)
            return f"{parsed.scheme}:{href.split('?')[0]}"
        if href.startswith("/"):
            return f"{self._origin}{href.split('?')[0]}"
        base_path = "/".join(base.split("/")[:-1])
        return f"{base_path}/{href.split('?')[0]}"

    def summary(self, pages: list[CrawlPage]) -> str:
        forms  = sum(len(p.forms) for p in pages)
        errors = sum(1 for p in pages if p.status >= 400)
        return (
            f"{len(pages)} pages crawled  "
            f"{forms} forms found  "
            f"{errors} errors"
        )

"""
Semantic vector store over CVE descriptions and exploit write-ups.

Uses ChromaDB when available; falls back to a pure-Python substring search
so the rest of SpectreNet works without the optional dependency.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spectrenet.knowledge.cve_db import CVEKnowledgeBase

_CHROMA_AVAILABLE = False
try:
    import chromadb  # type: ignore
    _CHROMA_AVAILABLE = True
except ImportError:
    pass


class VectorStore:
    """
    Semantic search over CVE descriptions and exploit write-ups.

    Usage:
        store = VectorStore(persist_dir=".spectrenet_vectors")
        store.seed_from_cves(cve_db)
        results = store.search("apache path traversal rce")
    """

    COLLECTION = "spectrenet_cves"

    def __init__(self, persist_dir: str | Path = ".spectrenet_vectors") -> None:
        self._dir      = Path(persist_dir)
        self._docs:    list[dict] = []   # fallback in-memory store
        self._client   = None
        self._coll     = None
        self._use_chroma = False

        if _CHROMA_AVAILABLE:
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(path=str(self._dir))
                self._coll   = self._client.get_or_create_collection(
                    name=self.COLLECTION,
                    metadata={"hnsw:space": "cosine"},
                )
                self._use_chroma = True
            except Exception:
                pass

    # ── Public interface ───────────────────────────────────────────────────────

    def add(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """Add or update a document in the store."""
        meta = metadata or {}
        if self._use_chroma and self._coll is not None:
            self._coll.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[meta],
            )
        else:
            # Replace existing entry if id already present
            self._docs = [d for d in self._docs if d["id"] != doc_id]
            self._docs.append({"id": doc_id, "text": text, **meta})

    def search(self, query: str, n: int = 5) -> list[dict]:
        """
        Return up to n relevant documents for the query.

        Each result: {"id", "text", "score", ...metadata}
        """
        if self._use_chroma and self._coll is not None:
            try:
                res = self._coll.query(query_texts=[query], n_results=min(n, max(1, self._coll.count())))
                results = []
                ids       = res.get("ids",       [[]])[0]
                docs      = res.get("documents",  [[]])[0]
                metas     = res.get("metadatas",  [[]])[0]
                distances = res.get("distances",  [[]])[0]
                for i, doc_id in enumerate(ids):
                    score = 1.0 - (distances[i] if distances else 0.0)
                    entry = {"id": doc_id, "text": docs[i], "score": score}
                    if metas:
                        entry.update(metas[i] or {})
                    results.append(entry)
                return results
            except Exception:
                pass

        # Fallback: keyword overlap score
        query_words = set(re.findall(r'\w+', query.lower()))
        scored = []
        for doc in self._docs:
            doc_words = set(re.findall(r'\w+', doc["text"].lower()))
            overlap   = len(query_words & doc_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                scored.append({**doc, "score": score})
        scored.sort(key=lambda d: d["score"], reverse=True)
        return scored[:n]

    def count(self) -> int:
        if self._use_chroma and self._coll is not None:
            try:
                return self._coll.count()
            except Exception:
                pass
        return len(self._docs)

    def seed_from_cves(self, db: "CVEKnowledgeBase") -> int:
        """Populate the store from all CVEs in the knowledge base. Returns count added."""
        rows = db.conn.execute("SELECT cve_id, service, description FROM cves").fetchall()
        for row in rows:
            text = f"{row['cve_id']} {row['service']} {row['description']}"
            self.add(
                doc_id=row["cve_id"],
                text=text,
                metadata={"cve_id": row["cve_id"], "service": row["service"]},
            )
        return len(rows)

    def add_exploit(self, exploit_id: str, title: str, description: str, msf_module: str = "") -> None:
        """Add an exploit write-up to the semantic index."""
        text = f"{title} {description} {msf_module}"
        self.add(
            doc_id=f"exploit:{exploit_id}",
            text=text,
            metadata={"type": "exploit", "title": title, "msf_module": msf_module},
        )

    @property
    def backend(self) -> str:
        return "chromadb" if self._use_chroma else "fallback"

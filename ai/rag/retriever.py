# RAG retriever - Sentence-BERT embeddings, JSON-persisted index.
# Same EmbeddingVectorizer as scorer (shared vector space).
# bootstrap() seeds static corpus + active jobs at API startup.

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from dataclasses import asdict, dataclass
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional

from ai.embeddings.vectorizer import EmbeddingVectorizer
from ai.rag.corpus import CorpusDocument, default_corpus

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    doc_id: str
    title: str
    text: str
    source: str
    score: float

    def as_context(self) -> str:
        return f"[{self.title}] {self.text}"


class RAGRetriever:
    # embedding-based retriever with on-disk persistence

    DEFAULT_INDEX_FILE = "rag_index.json"

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        vectorizer: Optional[EmbeddingVectorizer] = None,
    ) -> None:
        self._lock = RLock()
        self.vectorizer = vectorizer or EmbeddingVectorizer()
        self.persist_dir = persist_dir or os.environ.get("RAG_INDEX_DIR", "./chroma_db")
        os.makedirs(self.persist_dir, exist_ok=True)
        self._index_path = os.path.join(self.persist_dir, self.DEFAULT_INDEX_FILE)
        self._documents: List[Dict[str, Any]] = []  # each entry: {doc_id, title, text, source, embedding}
        self._loaded = False
        self._load()

    # I/O
    def _load(self) -> None:
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                docs = payload.get("documents", [])
                if docs and len(docs[0].get("embedding", [])) == self.vectorizer.embedding_dim:
                    self._documents = docs
                    logger.info(
                        "RAG retriever loaded %d documents from %s",
                        len(self._documents),
                        self._index_path,
                    )
                else:
                    logger.warning(
                        "RAG index dimensionality mismatch (expected %d). Reindex required.",
                        self.vectorizer.embedding_dim,
                    )
                    self._documents = []
            except Exception as exc:  # pragma: no cover - corrupted index
                logger.exception("Failed to load RAG index, starting fresh: %s", exc)
                self._documents = []
        self._loaded = True

    def _persist(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "embedding_dim": self.vectorizer.embedding_dim,
                    "documents": self._documents,
                },
                fh,
            )

    # mgmt
    def add_documents(
        self,
        documents: Iterable[Dict[str, Any] | CorpusDocument],
        replace: bool = False,
    ) -> int:
        # returns the count of newly indexed entries
        materialised: List[Dict[str, Any]] = []
        for doc in documents:
            if isinstance(doc, CorpusDocument):
                doc = asdict(doc)
            text = (doc.get("text") or "").strip()
            if not text:
                continue
            doc_id = doc.get("doc_id") or hashlib.md5(text.encode("utf-8")).hexdigest()
            materialised.append(
                {
                    "doc_id": doc_id,
                    "title": doc.get("title") or doc_id,
                    "text": text,
                    "source": doc.get("source") or "external",
                }
            )

        if not materialised:
            return 0

        embeddings = self.vectorizer.generate_embeddings_batch(
            [d["text"] for d in materialised]
        )
        for doc, embedding in zip(materialised, embeddings):
            doc["embedding"] = embedding

        with self._lock:
            if replace:
                self._documents = materialised
            else:
                existing_ids = {d["doc_id"] for d in self._documents}
                for doc in materialised:
                    if doc["doc_id"] in existing_ids:
                        # update embedding in place
                        for i, existing in enumerate(self._documents):
                            if existing["doc_id"] == doc["doc_id"]:
                                self._documents[i] = doc
                                break
                    else:
                        self._documents.append(doc)
                        existing_ids.add(doc["doc_id"])
            self._persist()
        return len(materialised)

    def bootstrap(self, extra_documents: Optional[Iterable[Dict[str, Any]]] = None) -> int:
        # seed the index with the static corpus + whatever the caller hands in
        seeded = self.add_documents(default_corpus())
        extra = self.add_documents(extra_documents or [])
        total = seeded + extra
        logger.info("RAG retriever bootstrap complete: %d documents indexed.", total)
        return total

    # query
    def retrieve(self, query: str, k: int = 3) -> List[str]:
        # back-compat: top-k texts only, no scores
        chunks = self.retrieve_chunks(query, k=k)
        return [chunk.as_context() for chunk in chunks]

    def retrieve_chunks(self, query: str, k: int = 3) -> List[RetrievedChunk]:
        # top-k chunks with similarity scores
        if not query or not self._documents:
            return []
        query_embedding = self.vectorizer.generate_embedding(query)
        scored: List[RetrievedChunk] = []
        for doc in self._documents:
            score = _cosine(query_embedding, doc["embedding"])
            scored.append(
                RetrievedChunk(
                    doc_id=doc["doc_id"],
                    title=doc.get("title", doc["doc_id"]),
                    text=doc["text"],
                    source=doc.get("source", "external"),
                    score=score,
                )
            )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[: max(1, k)]

    # info
    @property
    def document_count(self) -> int:
        return len(self._documents)

    def initialize_vectorstore(self, documents: List[Dict[str, Any]]) -> None:
        # back-compat alias for older callers
        self.add_documents(documents, replace=True)


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


_singleton: Optional[RAGRetriever] = None
_singleton_lock = RLock()


def get_retriever() -> RAGRetriever:
    # process-wide singleton retriever
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = RAGRetriever()
        return _singleton


__all__ = ["RAGRetriever", "RetrievedChunk", "get_retriever"]

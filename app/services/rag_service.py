from __future__ import annotations

from collections import Counter
import hashlib
import json
import logging
import math
from pathlib import Path
import re
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.db.sqlite import connect, migrate
from app.models.ollama import OllamaClient

logger = logging.getLogger(__name__)


SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf", ".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml", ".csv", ".log"}
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class RagService:
    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm
        self.collection_name = "agentforge_documents"
        self.embedding_model = settings.fast_model
        migrate()

    def capabilities(self) -> dict[str, object]:
        try:
            with connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return {
                "available": True,
                "mode": "chroma_or_sqlite",
                "message": "Document AI is available. ChromaDB is optional; SQLite fallback is enabled.",
            }
        except Exception as exc:
            logger.warning("RAG storage unavailable: %s", exc)
            return {
                "available": False,
                "mode": "disabled",
                "message": "Document AI is unavailable because local storage could not be opened.",
            }

    async def ingest_uploads(self, files: list[UploadFile]) -> list[str]:
        ingested: list[str] = []
        for file in files:
            raw = await file.read()
            source = file.filename or f"upload-{uuid4()}"
            text = self._extract_text(source, raw)
            count = await self._store_text(source, text)
            ingested.append(f"{source} ({count} chunks)")
        return ingested

    async def ingest_path(self, path: str) -> list[str]:
        root = Path(path)
        if not root.exists():
            return [f"Path not found: {path}"]

        files = [root] if root.is_file() else [item for item in root.rglob("*") if item.is_file()]
        ingested: list[str] = []
        for file_path in files:
            if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            text = self._extract_text(str(file_path), file_path.read_bytes())
            count = await self._store_text(str(file_path), text)
            ingested.append(f"{file_path} ({count} chunks)")
        return ingested

    async def query(self, question: str, model: str, top_k: int = 5) -> dict[str, object]:
        rows = self.search(question, limit=top_k)
        context = "\n\n".join(row["content"] for row in rows)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are AgentForce AI, an offline research assistant. "
                    "Answer only from provided local document context."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Use the following context to answer.\n"
                    "If the answer is not present, say the local knowledge base does not contain enough information.\n\n"
                    f"{context}\n\nQuestion: {question}"
                ),
            },
        ]
        try:
            answer = await self.llm.chat(model, messages)
        except Exception:
            answer = self._fallback_answer(question, rows)
        return {"answer": answer, "sources": [row["source"] for row in rows], "context": rows}

    def search(self, question: str, limit: int = 5) -> list[dict[str, str]]:
        chroma_rows = self._search_chroma(question, limit)
        if chroma_rows:
            return chroma_rows
        return self._search_sqlite(question, limit)

    async def _store_text(self, source: str, text: str) -> int:
        chunks = self._chunk(text)
        if not chunks:
            return 0

        self._store_sqlite(source, chunks)
        self._store_chroma(source, chunks)
        return len(chunks)

    def _store_sqlite(self, source: str, chunks: list[str]) -> None:
        with connect() as conn:
            conn.execute("DELETE FROM rag_documents WHERE source = ?", (source,))
            for index, chunk in enumerate(chunks):
                embedding = self._embed_local(chunk)
                conn.execute(
                    "INSERT INTO rag_documents (source, chunk_index, content, embedding) VALUES (?, ?, ?, ?)",
                    (source, index, chunk, json.dumps(embedding)),
                )

    def _store_chroma(self, source: str, chunks: list[str]) -> None:
        try:
            collection = self._collection()
            existing = collection.get(where={"source": source})
            ids = existing.get("ids", [])
            if ids:
                collection.delete(ids=ids)
            ids = [f"{hashlib.sha256(source.encode()).hexdigest()[:16]}-{index}" for index in range(len(chunks))]
            collection.add(
                ids=ids,
                documents=chunks,
                embeddings=[self._embed_local(chunk) for chunk in chunks],
                metadatas=[{"source": source, "chunk_index": index} for index in range(len(chunks))],
            )
        except Exception:
            logger.info("ChromaDB unavailable; using SQLite vector fallback.")
            return

    def _search_chroma(self, question: str, limit: int) -> list[dict[str, str]]:
        try:
            result = self._collection().query(
                query_embeddings=[self._embed_local(question)],
                n_results=limit,
                include=["documents", "metadatas"],
            )
        except Exception:
            logger.info("ChromaDB search unavailable; using SQLite vector fallback.")
            return []

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        rows: list[dict[str, str]] = []
        for document, metadata in zip(documents, metadatas):
            rows.append({"source": str(metadata.get("source", "unknown")), "content": document})
        return rows

    def _search_sqlite(self, question: str, limit: int) -> list[dict[str, str]]:
        query_embedding = self._embed_local(question)
        scored: list[tuple[float, dict[str, str]]] = []
        with connect() as conn:
            rows = conn.execute("SELECT source, content, embedding FROM rag_documents").fetchall()
        for row in rows:
            embedding = json.loads(row["embedding"])
            score = self._cosine(query_embedding, embedding)
            if score > 0:
                scored.append((score, {"source": row["source"], "content": row["content"]}))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def _collection(self):
        import chromadb

        client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        return client.get_or_create_collection(name=self.collection_name)

    def _extract_text(self, source: str, raw: bytes) -> str:
        if source.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                from io import BytesIO

                reader = PdfReader(BytesIO(raw))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                return raw.decode("utf-8", errors="ignore")
        return raw.decode("utf-8", errors="ignore")

    def _chunk(self, text: str) -> list[str]:
        clean = text.strip()
        if not clean:
            return []
        size = settings.rag_chunk_size
        overlap = min(settings.rag_chunk_overlap, size // 2)
        chunks: list[str] = []
        start = 0
        while start < len(clean):
            chunks.append(clean[start : start + size])
            start += size - overlap
        return chunks

    def _embed_local(self, text: str, dimensions: int = 256) -> list[float]:
        vector = [0.0] * dimensions
        counts = Counter(token.lower() for token in TOKEN_RE.findall(text))
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            vector[index] += float(count)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _cosine(self, left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))

    def _fallback_answer(self, question: str, rows: list[dict[str, str]]) -> str:
        if not rows:
            return "The local knowledge base does not contain enough context to answer this question."
        excerpts = "\n\n".join(row["content"][:500] for row in rows[:3])
        return f"Relevant local excerpts for '{question}':\n\n{excerpts}"

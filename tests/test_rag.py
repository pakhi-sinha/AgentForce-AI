from pathlib import Path

import pytest

from app.models.ollama import OllamaClient
from app.rag.service import RagService


@pytest.mark.asyncio
async def test_rag_ingest_and_query_local_fallback(tmp_path: Path) -> None:
    note = tmp_path / "notes.md"
    note.write_text("AgentForge uses Ollama for offline model serving.", encoding="utf-8")
    rag = RagService(OllamaClient(base_url="http://127.0.0.1:9", timeout=0.01))

    ingested = await rag.ingest_path(str(note))
    result = await rag.query("What serves offline models?", "llama3")

    assert ingested
    assert "Ollama" in result["answer"]

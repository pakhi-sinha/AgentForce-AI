from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.core.orchestrator import Orchestrator
from app.models.ollama import OllamaUnavailable


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class UnavailableLlm:
    async def chat(self, model: str, messages: list[dict[str, str]]) -> str:
        raise OllamaUnavailable("test")

    async def embed(self, model: str, text: str) -> list[float]:
        return []


@pytest.mark.asyncio
async def test_orchestrator_offline_fallback() -> None:
    orchestrator = Orchestrator(UnavailableLlm())
    result = await orchestrator.run("Plan my study schedule")
    assert result["status"] in {"completed", "completed_with_findings"}
    assert result["task_id"]
    assert result["plan"]["steps"]
    assert "Plan my study schedule" in result["goal"]

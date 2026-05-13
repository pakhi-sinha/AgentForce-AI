import httpx
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class OllamaUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
        resolved_url = base_url if base_url is not None else settings.ollama_base_url
        self.base_url = resolved_url.rstrip("/") if resolved_url else ""
        self.timeout = timeout

    def _candidate_urls(self) -> list[str]:
        if not self.base_url:
            return []
        candidates = [self.base_url]
        if "host.docker.internal" in self.base_url:
            local_fallback = self.base_url.replace("host.docker.internal", "127.0.0.1")
            if local_fallback not in candidates:
                candidates.append(local_fallback)
        return candidates

    async def list_models(self) -> dict[str, object]:
        candidates = self._candidate_urls()
        if not candidates:
            return {"models": [], "offline": settings.offline_mode, "error": self._missing_config_message()}
        last_error = ""
        for candidate in candidates:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(f"{candidate}/api/tags")
                    response.raise_for_status()
                    self.base_url = candidate
                    return response.json()
            except httpx.HTTPError as exc:
                last_error = str(exc)
                logger.warning("Ollama model list unavailable at %s: %s", candidate, exc)
        return {
            "models": [],
            "offline": settings.offline_mode,
            "error": f"Ollama unavailable at {', '.join(candidates)}. Set OLLAMA_BASE_URL correctly or enable OPENAI_API_KEY. Details: {last_error}",
        }

    async def chat(self, model: str, messages: list[dict[str, str]], temperature: float = 0.7) -> str:
        payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
        candidates = self._candidate_urls()
        if not candidates:
            if settings.openai_api_key:
                return await self._openai_chat(messages, temperature=temperature)
            raise OllamaUnavailable(self._missing_config_message())
        last_exc: Exception | None = None
        for candidate in candidates:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(f"{candidate}/api/chat", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    self.base_url = candidate
                    return data.get("message", {}).get("content", "")
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("Ollama chat unavailable at %s, attempting fallback when configured: %s", candidate, exc)
        if settings.openai_api_key:
            return await self._openai_chat(messages, temperature=temperature)
        raise OllamaUnavailable(f"Ollama chat endpoint is unavailable at {', '.join(candidates)}: {last_exc}") from last_exc

    async def stream_chat(self, model: str, messages: list[dict[str, str]], temperature: float = 0.7):
        payload = {"model": model, "messages": messages, "stream": True, "options": {"temperature": temperature}}
        candidates = self._candidate_urls()
        if not candidates:
            if settings.openai_api_key:
                async for token in self._openai_stream_chat(messages, temperature=temperature):
                    yield token
                return
            raise OllamaUnavailable(self._missing_config_message())
        last_exc: Exception | None = None
        for candidate in candidates:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("POST", f"{candidate}/api/chat", json=payload) as response:
                        response.raise_for_status()
                        self.base_url = candidate
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if data.get("done"):
                                return
                        return
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                last_exc = exc
                logger.warning("Ollama streaming unavailable at %s, attempting fallback when configured: %s", candidate, exc)
        if settings.openai_api_key:
            async for token in self._openai_stream_chat(messages, temperature=temperature):
                yield token
            return
        raise OllamaUnavailable(f"Ollama streaming endpoint is unavailable at {', '.join(candidates)}: {last_exc}") from last_exc

    def _missing_config_message(self) -> str:
        return (
            "OLLAMA_BASE_URL is not configured. For Docker, use "
            "http://host.docker.internal:11434. Local development can use http://127.0.0.1:11434. "
            "You can also provide OPENAI_API_KEY for fallback."
        )

    async def embed(self, model: str, text: str) -> list[float]:
        payload = {"model": model, "prompt": text}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [])
        except httpx.HTTPError:
            return []

    async def _openai_chat(self, messages: list[dict[str, str]], temperature: float = 0.7) -> str:
        payload = {"model": settings.openai_model, "messages": messages, "stream": False, "temperature": temperature}
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{settings.openai_base_url.rstrip('/')}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def _openai_stream_chat(self, messages: list[dict[str, str]], temperature: float = 0.7):
        payload = {"model": settings.openai_model, "messages": messages, "stream": True, "temperature": temperature}
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload_text = line.removeprefix("data: ").strip()
                    if payload_text == "[DONE]":
                        break
                    data = json.loads(payload_text)
                    token = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if token:
                        yield token

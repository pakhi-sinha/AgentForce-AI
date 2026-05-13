from __future__ import annotations

import time
from collections.abc import AsyncGenerator

from app.core.config import settings
from app.db.usage import approx_tokens, record_usage
from app.models.ollama import OllamaClient
from app.services.memory_service import MemoryService
from app.services.rag_service import RagService


SYSTEM_PROMPTS = {
    "general": (
        "You are AgentForce AI, a private offline AI assistant. Be clear, helpful, "
        "and concise. Format answers with practical steps when useful."
    ),
    "study": (
        "You are AgentForce AI in study mode. Explain concepts for exams with "
        "definitions, key points, examples, and answer-style structure."
    ),
    "teacher": (
        "You are AgentForce AI in teacher mode. Teach step by step with clear "
        "definitions, examples, checks for understanding, and exam-ready structure."
    ),
    "research": (
        "You are AgentForce AI in research mode. Answer with a short overview, key findings, "
        "important caveats, and a crisp conclusion. When document context exists, ground the answer in it."
    ),
    "summarizer": (
        "You are AgentForce AI in summarizer mode. Produce a clean summary with the core idea, "
        "key bullet points, and a short action-oriented takeaway."
    ),
    "coding": (
        "You are AgentForce AI in coding mode. Give precise engineering help, explain "
        "tradeoffs, and include clean, commented code examples when useful."
    ),
    "assistant": (
        "You are AgentForce AI in assistant mode. Be concise, proactive, organized, "
        "and practical. Help the user finish tasks with crisp next steps."
    ),
    "agriculture": (
        "You are AgentForce AI as an agriculture expert. Give locally practical, "
        "safety-aware guidance about crops, soil, irrigation, pests, and farm planning."
    ),
    "agriculture expert": (
        "You are AgentForce AI as an agriculture expert. Give locally practical, "
        "safety-aware guidance about crops, soil, irrigation, pests, and farm planning."
    ),
    "ai/ml": (
        "You are AgentForce AI as an AI and machine learning expert. Explain models, "
        "math, systems, and implementation tradeoffs precisely."
    ),
    "dbms": (
        "You are AgentForce AI as a DBMS expert. Explain databases, SQL, transactions, "
        "normalization, indexing, and system design with exam-ready clarity."
    ),
}


class ChatService:
    def __init__(self, llm: OllamaClient, memory: MemoryService, rag: RagService) -> None:
        self.llm = llm
        self.memory = memory
        self.rag = rag
        self._cache: dict[str, tuple[float, str]] = {}
        self.cache_ttl_seconds = 120

    async def chat(
        self,
        message: str,
        user_id: str = "default",
        mode: str = "general",
        model: str | None = None,
        use_rag: bool = False,
        use_memory: bool = True,
        temperature: float = 0.7,
        top_k: int = 5,
        chat_id: str | None = None,
    ) -> dict[str, object]:
        model_name = model or settings.default_model
        mode_key = mode.lower().strip()
        system_prompt = SYSTEM_PROMPTS.get(mode_key, SYSTEM_PROMPTS["general"])
        title = self._title_from_message(message)
        chat_id = await self.memory.ensure_chat(user_id, chat_id, title, mode_key, model_name)
        history = await self.memory.get_history(user_id, chat_id=chat_id) if use_memory else []
        docs = self.rag.search(message, limit=top_k) if use_rag else []

        messages = self._build_messages(system_prompt, history, docs, message)
        await self.memory.add_message(user_id, "user", message, chat_id=chat_id)
        response = await self._cached_chat(model_name, mode_key, use_rag, temperature, message, messages)
        await self.memory.add_message(user_id, "assistant", response, chat_id=chat_id, model=model_name)
        record_usage(user_id, chat_id, messages=2, tokens=approx_tokens(message) + approx_tokens(response))

        return {
            "chat_id": chat_id,
            "user_id": user_id,
            "mode": mode_key if mode_key in SYSTEM_PROMPTS else "general",
            "model": model_name,
            "message": response,
            "sources": [doc["source"] for doc in docs],
        }

    async def stream_chat(
        self,
        message: str,
        user_id: str = "default",
        mode: str = "general",
        model: str | None = None,
        use_rag: bool = False,
        use_memory: bool = True,
        temperature: float = 0.7,
        top_k: int = 5,
        chat_id: str | None = None,
    ) -> tuple[str, str, list[str], AsyncGenerator[str, None]]:
        model_name = model or settings.default_model
        mode_key = mode.lower().strip()
        system_prompt = SYSTEM_PROMPTS.get(mode_key, SYSTEM_PROMPTS["general"])
        title = self._title_from_message(message)
        chat_id = await self.memory.ensure_chat(user_id, chat_id, title, mode_key, model_name)
        history = await self.memory.get_history(user_id, chat_id=chat_id) if use_memory else []
        docs = self.rag.search(message, limit=top_k) if use_rag else []
        messages = self._build_messages(system_prompt, history, docs, message)
        await self.memory.add_message(user_id, "user", message, chat_id=chat_id)

        async def generator() -> AsyncGenerator[str, None]:
            chunks: list[str] = []
            async for token in self.llm.stream_chat(model_name, messages, temperature=temperature):
                chunks.append(token)
                yield token
            response = "".join(chunks).strip()
            await self.memory.add_message(user_id, "assistant", response, chat_id=chat_id, model=model_name)
            record_usage(user_id, chat_id, messages=2, tokens=approx_tokens(message) + approx_tokens(response))

        return chat_id, model_name, [doc["source"] for doc in docs], generator()

    async def _cached_chat(
        self,
        model: str,
        mode: str,
        use_rag: bool,
        temperature: float,
        message: str,
        messages: list[dict[str, str]],
    ) -> str:
        key = f"{model}:{mode}:{use_rag}:{temperature}:{message.strip().lower()}"
        cached = self._cache.get(key)
        now = time.time()
        if cached and now - cached[0] < self.cache_ttl_seconds:
            return cached[1]
        response = await self.llm.chat(model, messages, temperature=temperature)
        if len(message) < 240 and not use_rag:
            self._cache[key] = (now, response)
        return response

    def _title_from_message(self, message: str) -> str:
        title = " ".join(message.strip().split())
        return title[:58] or "New chat"

    def _build_messages(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        docs: list[dict[str, str]],
        message: str,
    ) -> list[dict[str, str]]:
        context_parts: list[str] = []
        if history:
            memory_context = "\n".join(f"{item['role']}: {item['content']}" for item in history[-10:])
            context_parts.append(f"Conversation memory:\n{memory_context}")
        doc_context = ""
        if docs:
            doc_context = "\n\n".join(f"Source: {doc['source']}\n{doc['content']}" for doc in docs)
            context_parts.append(f"Relevant local documents:\n{doc_context}")

        messages = [{"role": "system", "content": system_prompt}]
        if context_parts:
            messages.append(
                {
                    "role": "system",
                    "content": "\n\n".join(context_parts),
                }
            )
        if doc_context:
            prompt = (
                "Use the following context to answer.\n"
                "If the answer is not in the context, clearly say so.\n\n"
                f"{doc_context}\n\n"
                f"Question: {message}"
            )
            messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": message})
        return messages

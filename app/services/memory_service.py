from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import redis

from app.core.config import settings
from app.db.sqlite import connect, migrate


class MemoryService:
    def __init__(self, max_messages: int = 20) -> None:
        self.max_messages = max_messages
        self._redis: redis.Redis | None = None
        migrate()

    def _client(self) -> redis.Redis | None:
        if self._redis is not None:
            return self._redis
        try:
            client = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
            client.ping()
            self._redis = client
            return client
        except redis.RedisError:
            return None

    def _key(self, user_id: str, chat_id: str | None = None) -> str:
        suffix = chat_id or "default"
        return f"agentforge:chat:{user_id}:{suffix}"

    async def create_chat(
        self,
        user_id: str = "default",
        title: str = "New chat",
        mode: str = "general",
        model: str = "llama3",
    ) -> dict[str, str]:
        chat_id = str(uuid4())
        with connect() as conn:
            conn.execute(
                "INSERT INTO chats (id, user_id, title, mode, model) VALUES (?, ?, ?, ?, ?)",
                (chat_id, user_id, title[:80] or "New chat", mode, model),
            )
        return {"id": chat_id, "user_id": user_id, "title": title[:80] or "New chat", "mode": mode, "model": model}

    async def ensure_chat(
        self,
        user_id: str,
        chat_id: str | None,
        title: str,
        mode: str,
        model: str,
    ) -> str:
        if chat_id:
            with connect() as conn:
                row = conn.execute("SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id)).fetchone()
                if row:
                    conn.execute(
                        "UPDATE chats SET mode = ?, model = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (mode, model, chat_id),
                    )
                    return chat_id
        chat = await self.create_chat(user_id=user_id, title=title, mode=mode, model=model)
        return chat["id"]

    async def list_chats(self, user_id: str = "default") -> list[dict[str, object]]:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    chats.id,
                    chats.user_id,
                    chats.title,
                    chats.mode,
                    chats.model,
                    chats.created_at,
                    chats.updated_at,
                    COUNT(conversation_messages.id) AS message_count
                FROM chats
                LEFT JOIN conversation_messages ON conversation_messages.chat_id = chats.id
                WHERE chats.user_id = ?
                GROUP BY chats.id
                ORDER BY chats.updated_at DESC, chats.created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    async def get_chat_messages(self, chat_id: str, user_id: str = "default") -> list[dict[str, str]]:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, model, created_at
                FROM conversation_messages
                WHERE chat_id = ? AND user_id = ?
                ORDER BY id ASC
                """,
                (chat_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    async def rename_chat(self, chat_id: str, title: str, user_id: str = "default") -> bool:
        with connect() as conn:
            cursor = conn.execute(
                "UPDATE chats SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (title[:80] or "New chat", chat_id, user_id),
            )
        return cursor.rowcount > 0

    async def delete_chat(self, chat_id: str, user_id: str = "default") -> bool:
        client = self._client()
        if client:
            try:
                client.delete(self._key(user_id, chat_id))
            except redis.RedisError:
                self._redis = None
        with connect() as conn:
            conn.execute("DELETE FROM conversation_messages WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            cursor = conn.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
        return cursor.rowcount > 0

    async def delete_all_chats(self, user_id: str = "default") -> int:
        client = self._client()
        if client:
            try:
                for chat in await self.list_chats(user_id):
                    client.delete(self._key(user_id, str(chat["id"])))
            except redis.RedisError:
                self._redis = None
        with connect() as conn:
            conn.execute("DELETE FROM conversation_messages WHERE user_id = ?", (user_id,))
            cursor = conn.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
        return cursor.rowcount

    async def add_message(
        self,
        user_id: str,
        role: str,
        content: str,
        chat_id: str | None = None,
        model: str | None = None,
    ) -> None:
        message = {"role": role, "content": content}
        client = self._client()
        if client:
            try:
                key = self._key(user_id, chat_id)
                client.rpush(key, json.dumps(message))
                client.ltrim(key, -self.max_messages, -1)
            except redis.RedisError:
                self._redis = None

        with connect() as conn:
            conn.execute(
                "INSERT INTO conversation_messages (chat_id, user_id, role, content, model) VALUES (?, ?, ?, ?, ?)",
                (chat_id, user_id, role, content, model),
            )
            if chat_id:
                conn.execute("UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (chat_id,))

    async def get_history(
        self,
        user_id: str,
        limit: int | None = None,
        chat_id: str | None = None,
    ) -> list[dict[str, str]]:
        limit = limit or self.max_messages
        client = self._client()
        if client:
            try:
                raw_messages = client.lrange(self._key(user_id, chat_id), -limit, -1)
                parsed = [self._parse_message(item) for item in raw_messages]
                if parsed:
                    return parsed
            except redis.RedisError:
                self._redis = None

        with connect() as conn:
            if chat_id:
                rows = conn.execute(
                    """
                    SELECT role, content
                    FROM conversation_messages
                    WHERE user_id = ? AND chat_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (user_id, chat_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT role, content
                    FROM conversation_messages
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    async def clear_history(self, user_id: str, chat_id: str | None = None) -> None:
        client = self._client()
        if client:
            try:
                client.delete(self._key(user_id, chat_id))
            except redis.RedisError:
                self._redis = None
        with connect() as conn:
            if chat_id:
                conn.execute("DELETE FROM conversation_messages WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            else:
                conn.execute("DELETE FROM conversation_messages WHERE user_id = ?", (user_id,))

    def _parse_message(self, value: str) -> dict[str, str]:
        try:
            parsed: dict[str, Any] = json.loads(value)
            return {"role": str(parsed.get("role", "user")), "content": str(parsed.get("content", ""))}
        except json.JSONDecodeError:
            return {"role": "user", "content": value}

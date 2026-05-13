from __future__ import annotations

from app.db.sqlite import connect


def approx_tokens(text: str) -> int:
    return max(1, len((text or "").split()))


def record_usage(user_id: str, chat_id: str | None, messages: int, tokens: int) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_events (user_id, chat_id, message_count, token_count)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, chat_id, messages, tokens),
        )
        conn.commit()


def usage_summary(user_id: str) -> dict[str, int]:
    with connect() as conn:
        usage = conn.execute(
            """
            SELECT
                COALESCE(SUM(message_count), 0) AS messages,
                COALESCE(SUM(token_count), 0) AS tokens
            FROM usage_events
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        chats = conn.execute("SELECT COUNT(*) AS chats FROM chats WHERE user_id = ?", (user_id,)).fetchone()
        documents = conn.execute("SELECT COUNT(DISTINCT source) AS documents FROM rag_documents").fetchone()
    return {
        "messages": int(usage["messages"] if usage else 0),
        "tokens": int(usage["tokens"] if usage else 0),
        "chats": int(chats["chats"] if chats else 0),
        "documents": int(documents["documents"] if documents else 0),
    }


def get_settings(user_id: str) -> dict[str, object]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT model, mode, temperature, memory_enabled, voice_enabled, rag_enabled
            FROM user_settings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
            row = conn.execute(
                """
                SELECT model, mode, temperature, memory_enabled, voice_enabled, rag_enabled
                FROM user_settings
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
    return _settings_row(row)


def update_settings(user_id: str, values: dict[str, object]) -> dict[str, object]:
    current = get_settings(user_id)
    merged = {**current, **{key: value for key, value in values.items() if value is not None}}
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_settings (
                user_id, model, mode, temperature, memory_enabled, voice_enabled, rag_enabled, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                model = excluded.model,
                mode = excluded.mode,
                temperature = excluded.temperature,
                memory_enabled = excluded.memory_enabled,
                voice_enabled = excluded.voice_enabled,
                rag_enabled = excluded.rag_enabled,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                str(merged["model"]),
                str(merged["mode"]),
                float(merged["temperature"]),
                1 if merged["memory_enabled"] else 0,
                1 if merged["voice_enabled"] else 0,
                1 if merged["rag_enabled"] else 0,
            ),
        )
    return get_settings(user_id)


def _settings_row(row) -> dict[str, object]:
    return {
        "model": row["model"],
        "mode": row["mode"],
        "temperature": float(row["temperature"]),
        "memory_enabled": bool(row["memory_enabled"]),
        "voice_enabled": bool(row["voice_enabled"]),
        "rag_enabled": bool(row["rag_enabled"]),
    }

from pathlib import Path
import sqlite3

from app.core.config import settings


def connect() -> sqlite3.Connection:
    path = Path(settings.sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'general',
                model TEXT NOT NULL DEFAULT 'llama3',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                plan TEXT NOT NULL,
                execution TEXT NOT NULL,
                evaluation TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                model TEXT NOT NULL DEFAULT 'llama3',
                mode TEXT NOT NULL DEFAULT 'general',
                temperature REAL NOT NULL DEFAULT 0.7,
                memory_enabled INTEGER NOT NULL DEFAULT 1,
                voice_enabled INTEGER NOT NULL DEFAULT 1,
                rag_enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                chat_id TEXT,
                message_count INTEGER NOT NULL DEFAULT 0,
                token_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_column(conn, "conversation_messages", "chat_id", "TEXT")
        _ensure_column(conn, "conversation_messages", "model", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

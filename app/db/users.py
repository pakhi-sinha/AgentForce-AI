from uuid import uuid4
import sqlite3
from app.db.sqlite import connect


def create_user(username: str, email: str, password_hash: str) -> dict:
    user_id = str(uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (id, username, email, password_hash) VALUES (?, ?, ?, ?)",
            (user_id, username, email, password_hash),
        )
        row = conn.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else {}


def get_user_by_username(username: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT id, username, email, password_hash, created_at FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None

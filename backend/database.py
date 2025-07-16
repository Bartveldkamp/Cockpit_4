import sqlite3
import json
from typing import List, Dict, Any

from backend.config import settings

def get_db_connection():
    conn = sqlite3.connect(settings.database_file)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            );
        """)
        conn.commit()

def save_chat_history(session_id: str, history: List[Dict[str, Any]]):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO sessions (session_id) VALUES (?)", (session_id,))
        cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        for entry in history:
            content = entry["content"]
            if not isinstance(content, str):
                content = json.dumps(content)
            cursor.execute(
                "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, entry["role"], content)
            )
        conn.commit()

def load_chat_history(session_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM chat_history WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )
        rows = cursor.fetchall()
        history = []
        for row in rows:
            raw = row["content"]
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
            history.append({"role": row["role"], "content": parsed})
        return history

def clear_session_history(session_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()

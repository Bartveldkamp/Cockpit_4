import pytest
import sqlite3
import json
from unittest.mock import patch, MagicMock
from backend.database import (
    get_db_connection, create_tables, save_chat_history, load_chat_history, clear_session_history
)

@pytest.fixture
def mock_db_connection():
    with patch('backend.database.sqlite3.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        yield mock_conn

def test_get_db_connection(mock_db_connection):
    conn = get_db_connection()
    assert conn is not None
    assert conn.row_factory == sqlite3.Row

def test_create_tables(mock_db_connection):
    create_tables()
    cursor = mock_db_connection.cursor()
    cursor.execute.assert_any_call("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute.assert_any_call("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        );
    """)
    mock_db_connection.commit.assert_called_once()

def test_save_chat_history(mock_db_connection):
    session_id = "test-session"
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": {"response": "Hi"}}
    ]

    save_chat_history(session_id, history)
    cursor = mock_db_connection.cursor()

    cursor.execute.assert_any_call("INSERT OR IGNORE INTO sessions (session_id) VALUES (?)", (session_id,))
    cursor.execute.assert_any_call("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    cursor.execute.assert_any_call(
        "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, "user", "Hello")
    )
    cursor.execute.assert_any_call(
        "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, "assistant", json.dumps({"response": "Hi"}))
    )
    mock_db_connection.commit.assert_called_once()

def test_load_chat_history(mock_db_connection):
    session_id = "test-session"
    mock_cursor = mock_db_connection.cursor()
    mock_cursor.fetchall.return_value = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": json.dumps({"response": "Hi"})}
    ]

    history = load_chat_history(session_id)
    cursor = mock_db_connection.cursor()
    cursor.execute.assert_called_once_with(
        "SELECT role, content FROM chat_history WHERE session_id = ? ORDER BY timestamp",
        (session_id,)
    )
    assert history == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": {"response": "Hi"}}
    ]

def test_clear_session_history(mock_db_connection):
    session_id = "test-session"

    clear_session_history(session_id)
    cursor = mock_db_connection.cursor()
    cursor.execute.assert_any_call("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    cursor.execute.assert_any_call("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    mock_db_connection.commit.assert_called_once()

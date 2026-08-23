import sqlite3
from pathlib import Path


DB_PATH = Path("/tmp/demo_app.db")


def set_db_path(path: Path):
    global DB_PATH
    DB_PATH = path


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()


def create_user(username: str, password_hash: str):
    connection = get_connection()

    connection.execute(
        "INSERT INTO users(username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )

    connection.commit()
    connection.close()


def get_user(username: str):
    connection = get_connection()

    row = connection.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    connection.close()

    return row

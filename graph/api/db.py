import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "graph.db"
ON_VERCEL = os.getenv("VERCEL") == "1"


def get_conn() -> sqlite3.Connection:
    if ON_VERCEL:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if ON_VERCEL:
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id           TEXT PRIMARY KEY,
                name         TEXT,
                avatar       TEXT,
                account_type TEXT,
                status       TEXT,
                repos_count  INTEGER DEFAULT 0,
                location     TEXT,
                company      TEXT
            );

            CREATE TABLE IF NOT EXISTS edges (
                source            TEXT NOT NULL,
                target            TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                shared_repos      INTEGER DEFAULT 0,
                repos             TEXT DEFAULT '',
                PRIMARY KEY (source, target, relationship_type)
            );

            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
        """)

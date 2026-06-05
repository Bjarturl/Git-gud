"""
Sync script: Postgres (main Django DB) → SQLite (graph.db)

Run manually:
    python sync.py

Uses the same env vars as the Django app, with sensible local defaults.
"""
import os
import sqlite3
import psycopg2
import psycopg2.extras
from db import DB_PATH, init_db

PG = dict(
    dbname=os.getenv("DB_NAME", "backend_db"),
    user=os.getenv("DB_USER", "backend_user"),
    password=os.getenv("DB_PASSWORD", "backend_password"),
    host=os.getenv("DB_HOST", "postgres"),
    port=os.getenv("DB_PORT", "5432"),
)

FOLLOWER_TYPES = {"Follower", "Following"}


def sync():
    init_db()

    pg = psycopg2.connect(**PG)
    pg.set_session(readonly=True, autocommit=True)
    cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sq = sqlite3.connect(DB_PATH)

    print("Clearing existing data...")
    sq.execute("DELETE FROM edges")
    sq.execute("DELETE FROM nodes")
    sq.commit()

    print("Syncing nodes...")
    cur.execute("""
        SELECT
            username          AS id,
            name,
            avatar,
            account_type,
            status,
            location,
            company,
            (
                SELECT COUNT(*) FROM git_repo r
                WHERE r.owner_id = u.id AND r.is_fork = FALSE
            ) AS repos_count
        FROM git_user u
        WHERE u.account_type != 'Bot'
    """)
    nodes = cur.fetchall()
    sq.executemany(
        """
        INSERT OR REPLACE INTO nodes
            (id, name, avatar, account_type, status, repos_count, location, company)
        VALUES
            (:id, :name, :avatar, :account_type, :status, :repos_count, :location, :company)
        """,
        nodes,
    )
    print(f"  {len(nodes)} nodes written")

    print("Syncing edges...")
    cur.execute("""
        SELECT
            fu.username             AS source,
            tu.username             AS target,
            r.relationship_type,
            COUNT(DISTINCT r.repo_id) FILTER (WHERE r.repo_id IS NOT NULL) AS shared_repos,
            STRING_AGG(DISTINCT gr.full_name, ',' ORDER BY gr.full_name)
                FILTER (WHERE gr.full_name IS NOT NULL) AS repos
        FROM git_user_relationship r
        JOIN git_user fu ON fu.id = r.from_user_id
        JOIN git_user tu ON tu.id = r.to_user_id
        LEFT JOIN git_repo gr ON gr.id = r.repo_id
        WHERE fu.account_type != 'Bot' AND tu.account_type != 'Bot'
        GROUP BY fu.username, tu.username, r.relationship_type
    """)
    raw_edges = cur.fetchall()

    # Normalise Follower/Following: both mean "source follows target"
    # Deduplicate so we store only one (source, target, "follows") row
    seen_follows: set[tuple] = set()
    edges = []
    for e in raw_edges:
        rtype = e["relationship_type"]
        src, tgt = e["source"], e["target"]
        if rtype in FOLLOWER_TYPES:
            key = (src, tgt)
            if key in seen_follows:
                continue
            seen_follows.add(key)
            edges.append({
                "source": src,
                "target": tgt,
                "relationship_type": "Follows",
                "shared_repos": 0,
                "repos": "",
            })
        else:
            edges.append({
                "source": src,
                "target": tgt,
                "relationship_type": rtype,
                "shared_repos": e["shared_repos"],
                "repos": e["repos"] or "",
            })

    sq.executemany(
        """
        INSERT OR REPLACE INTO edges (source, target, relationship_type, shared_repos, repos)
        VALUES (:source, :target, :relationship_type, :shared_repos, :repos)
        """,
        edges,
    )
    print(f"  {len(edges)} edges written")

    sq.commit()
    sq.close()
    pg.close()
    print("Done.")


if __name__ == "__main__":
    sync()

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse

from db import get_conn, init_db
from shortest_path import find_shortest_path

FRONTEND = Path(__file__).parent / "templates" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Graph API", lifespan=lifespan)


@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(FRONTEND)


@app.get("/autocomplete")
def autocomplete(q: str = Query(default="")):
    q = q.strip()
    with get_conn() as conn:
        if q:
            rows = conn.execute(
                "SELECT id FROM nodes WHERE id LIKE ? COLLATE NOCASE LIMIT 5",
                (f"{q}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id FROM nodes ORDER BY RANDOM() LIMIT 5"
            ).fetchall()
    return {"results": [r["id"] for r in rows]}


@app.get("/shortest-path")
def shortest_path(
    source: str = Query(..., description="Username of the starting user"),
    target: str = Query(..., description="Username of the destination user"),
):
    source = source.strip()
    target = target.strip()

    with get_conn() as conn:
        src_row = conn.execute(
            "SELECT id FROM nodes WHERE id = ? COLLATE NOCASE", (source,)
        ).fetchone()
        tgt_row = conn.execute(
            "SELECT id FROM nodes WHERE id = ? COLLATE NOCASE", (target,)
        ).fetchone()

    if not src_row:
        raise HTTPException(status_code=404, detail=f"User '{source}' not found in graph")
    if not tgt_row:
        raise HTTPException(status_code=404, detail=f"User '{target}' not found in graph")

    source, target = src_row["id"], tgt_row["id"]

    with get_conn() as conn:
        result = find_shortest_path(conn, source, target)

    if result is None:
        with get_conn() as conn:
            src_node = dict(conn.execute("SELECT * FROM nodes WHERE id = ?", (source,)).fetchone())
            tgt_node = dict(conn.execute("SELECT * FROM nodes WHERE id = ?", (target,)).fetchone())
        return {"nodes": [src_node, tgt_node], "edges": [], "no_path": True}

    return result


@app.get("/user/{username}")
def user(username: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM nodes WHERE id = ? COLLATE NOCASE", (username,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found in graph")
        uid = row["id"]
        neighbor_count = conn.execute(
            "SELECT COUNT(DISTINCT CASE WHEN source=? THEN target ELSE source END) FROM edges WHERE source=? OR target=?",
            (uid, uid, uid),
        ).fetchone()[0]
    return {**dict(row), "neighbor_count": neighbor_count}


@app.get("/relationships/{source}/{target}")
def relationships(source: str, target: str):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM edges
               WHERE (source = ? AND target = ?) OR (source = ? AND target = ?)""",
            (source, target, target, source),
        ).fetchall()
    return {"relationships": [dict(r) for r in rows]}


@app.get("/neighbors/{username}")
def neighbors(username: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM nodes WHERE id = ? COLLATE NOCASE", (username,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")
        uid = row["id"]

        edge_rows = conn.execute(
            "SELECT * FROM edges WHERE source = ? OR target = ?", (uid, uid)
        ).fetchall()

        neighbor_ids = []
        seen = set()
        edges_out = []
        for e in edge_rows:
            e = dict(e)
            nbr = e["target"] if e["source"] == uid else e["source"]
            edges_out.append(e)
            if nbr not in seen:
                seen.add(nbr)
                neighbor_ids.append(nbr)

        total = len(neighbor_ids)
        capped = neighbor_ids[:60]

        if not capped:
            return {"nodes": [], "edges": [], "total": 0}

        placeholders = ",".join("?" * len(capped))
        node_rows = conn.execute(
            f"SELECT * FROM nodes WHERE id IN ({placeholders})", capped
        ).fetchall()

        capped_set = set(capped)
        edges_out = [e for e in edges_out if e["source"] in capped_set or e["target"] in capped_set]

    return {"nodes": [dict(r) for r in node_rows], "edges": edges_out, "total": total}

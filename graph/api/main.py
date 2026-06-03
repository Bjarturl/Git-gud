import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

logging.basicConfig(level=logging.INFO, format="%(message)s")

from db import get_conn, init_db
from shortest_path import find_shortest_path

FRONTEND = Path(__file__).parent / "templates" / "index.html"

def real_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

limiter = Limiter(key_func=real_ip, default_limits=["10/second"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ice-git-graph", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def log_and_secure(request: Request, call_next):
    t = time.monotonic()
    response = await call_next(request)
    ms = (time.monotonic() - t) * 1000
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "-").split(",")[0].strip()
    logging.info(f'{ip} {request.method} {request.url.path}{("?" + str(request.query_params)) if request.query_params else ""} {response.status_code} {ms:.0f}ms')
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


_SECURITY_TXT = (
    "Contact: mailto:bbsnskj@gmail.com\n"
    "Expires: 2027-06-01T00:00:00Z\n"
    "Canonical: https://ice-git-graph.vercel.app/.well-known/security.txt\n"
    "Preferred-Languages: en, is\n"
)


@app.get("/.well-known/security.txt", response_class=PlainTextResponse)
@app.get("/security.txt", response_class=PlainTextResponse)
def security_txt():
    return _SECURITY_TXT


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return (
        "User-agent: *\n"
        "Disallow: /autocomplete\n"
        "Disallow: /shortest-path\n"
        "Disallow: /neighbors/\n"
        "Disallow: /relationships/\n"
        "Disallow: /user/\n"
    )


@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(FRONTEND)


@app.get("/autocomplete")
def autocomplete(request: Request, q: str = Query(default="")):
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
    request: Request,
    source: str = Query(...),
    target: str = Query(...),
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
def user(request: Request, username: str):
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
def relationships(request: Request, source: str, target: str):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM edges
               WHERE (source = ? AND target = ?) OR (source = ? AND target = ?)""",
            (source, target, target, source),
        ).fetchall()
    return {"relationships": [dict(r) for r in rows]}


@app.get("/neighbors/{username}")
def neighbors(request: Request, username: str):
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

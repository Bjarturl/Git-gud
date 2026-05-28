from collections import deque
from typing import Optional
import sqlite3


def find_shortest_path(
    conn: sqlite3.Connection, source: str, target: str
) -> Optional[dict]:
    """
    Bidirectional BFS on the edges table.
    Returns {"nodes": [...], "edges": [...]} for the path, or None if unreachable.
    Each node dict comes from the nodes table; each edge dict includes relationship_type.
    """
    if source == target:
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (source,)).fetchone()
        node = dict(row) if row else {"id": source}
        return {"nodes": [node], "edges": []}

    # --- bidirectional BFS setup ---
    # parent[node] = (prev_node, edge_dict) so we can reconstruct the path
    fwd_parent: dict[str, tuple] = {source: None}
    bwd_parent: dict[str, tuple] = {target: None}
    fwd_queue: deque[str] = deque([source])
    bwd_queue: deque[str] = deque([target])

    meeting_node: Optional[str] = None

    def neighbors(node: str) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM edges WHERE source = ? OR target = ?", (node, node)
        ).fetchall()
        result = []
        for r in rows:
            r = dict(r)
            nbr = r["target"] if r["source"] == node else r["source"]
            result.append({"neighbor": nbr, "edge": r})
        return result

    def expand(queue, visited, other_visited, parent):
        nonlocal meeting_node
        if not queue:
            return False
        node = queue.popleft()
        for item in neighbors(node):
            nbr = item["neighbor"]
            edge = item["edge"]
            if nbr not in visited:
                visited[nbr] = None
                parent[nbr] = (node, edge)
                queue.append(nbr)
                if nbr in other_visited:
                    meeting_node = nbr
                    return True
        return False

    while fwd_queue and bwd_queue:
        if expand(fwd_queue, fwd_parent, bwd_parent, fwd_parent):
            break
        if expand(bwd_queue, bwd_parent, fwd_parent, bwd_parent):
            break
    else:
        return None  # no path found

    if meeting_node is None:
        return None

    # --- reconstruct path ---
    # forward: source → meeting_node
    fwd_path = []
    node = meeting_node
    while node is not None:
        entry = fwd_parent[node]
        fwd_path.append((node, entry[1] if entry else None))
        node = entry[0] if entry else None
    fwd_path.reverse()  # now source → meeting_node

    # backward: meeting_node → target
    bwd_path = []
    node = meeting_node
    while True:
        entry = bwd_parent[node]
        if entry is None:
            break
        prev_node, edge = entry
        bwd_path.append((prev_node, edge))
        node = prev_node

    # full ordered node ids
    path_nodes = [n for n, _ in fwd_path] + [n for n, _ in bwd_path]
    path_edges_raw = (
        [e for _, e in fwd_path if e is not None] +
        [e for _, e in bwd_path if e is not None]
    )

    # fetch node details
    placeholders = ",".join("?" * len(path_nodes))
    rows = conn.execute(
        f"SELECT * FROM nodes WHERE id IN ({placeholders})", path_nodes
    ).fetchall()
    nodes_by_id = {r["id"]: dict(r) for r in rows}
    # preserve order and fall back gracefully if a node isn't synced yet
    nodes_out = [nodes_by_id.get(n, {"id": n}) for n in path_nodes]

    # deduplicate edges (bidirectional BFS can produce duplicates)
    seen = set()
    edges_out = []
    for e in path_edges_raw:
        key = (e["source"], e["target"], e["relationship_type"])
        if key not in seen:
            seen.add(key)
            edges_out.append(e)

    return {"nodes": nodes_out, "edges": edges_out}

from collections import deque
from typing import Optional
import sqlite3

EDGE_WEIGHT = {
    "Collaborator": 0,
    "Contributor":  1,
    "OrgMember":    2,
    "Follows":      4,
    "Following":    4,
    "Follower":     4,
}


def find_shortest_path(
    conn: sqlite3.Connection, source: str, target: str
) -> Optional[dict]:
    if source == target:
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (source,)).fetchone()
        node = dict(row) if row else {"id": source}
        return {"nodes": [node], "edges": []}

    def best_neighbors(node: str) -> list[dict]:
        # UNION ALL lets SQLite use idx_edges_source and idx_edges_target separately
        rows = conn.execute(
            """
            SELECT * FROM edges WHERE source = ?
            UNION ALL
            SELECT * FROM edges WHERE target = ? AND source != ?
            """,
            (node, node, node),
        ).fetchall()
        # Keep only the best-weighted edge per neighbor
        best: dict[str, dict] = {}
        for r in rows:
            r = dict(r)
            nbr = r["target"] if r["source"] == node else r["source"]
            w = EDGE_WEIGHT.get(r["relationship_type"], 4)
            if nbr not in best or w < EDGE_WEIGHT.get(best[nbr]["relationship_type"], 4):
                best[nbr] = r
        return [{"neighbor": nbr, "edge": edge} for nbr, edge in best.items()]

    # Bidirectional BFS
    fwd_parent: dict[str, Optional[tuple]] = {source: None}
    bwd_parent: dict[str, Optional[tuple]] = {target: None}
    fwd_queue: deque[str] = deque([source])
    bwd_queue: deque[str] = deque([target])
    meeting_node: Optional[str] = None

    def expand(queue, visited, other_visited, parent):
        nonlocal meeting_node
        if not queue:
            return False
        node = queue.popleft()
        for item in best_neighbors(node):
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
        return None

    if meeting_node is None:
        return None

    # Reconstruct forward: source → meeting_node
    fwd_path = []
    node = meeting_node
    while node is not None:
        entry = fwd_parent[node]
        fwd_path.append((node, entry[1] if entry else None))
        node = entry[0] if entry else None
    fwd_path.reverse()

    # Reconstruct backward: meeting_node → target
    bwd_path = []
    node = meeting_node
    while True:
        entry = bwd_parent[node]
        if entry is None:
            break
        prev_node, edge = entry
        bwd_path.append((prev_node, edge))
        node = prev_node

    path_nodes = [n for n, _ in fwd_path] + [n for n, _ in bwd_path]
    path_edges_raw = (
        [e for _, e in fwd_path if e is not None] +
        [e for _, e in bwd_path if e is not None]
    )

    placeholders = ",".join("?" * len(path_nodes))
    rows = conn.execute(
        f"SELECT * FROM nodes WHERE id IN ({placeholders})", path_nodes
    ).fetchall()
    nodes_by_id = {r["id"]: dict(r) for r in rows}
    nodes_out = [nodes_by_id.get(n, {"id": n}) for n in path_nodes]

    seen: set[tuple] = set()
    edges_out = []
    for e in path_edges_raw:
        key = (e["source"], e["target"], e["relationship_type"])
        if key not in seen:
            seen.add(key)
            edges_out.append(e)

    return {"nodes": nodes_out, "edges": edges_out}

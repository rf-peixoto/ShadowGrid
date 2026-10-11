"""Grid geometry shared by the player movement / reveal logic.

Square grid edges: 0=N 1=E 2=S 3=W.
Flat-top hex grid, odd-q offset coordinates, edges: 0=SE 1=S 2=SW 3=NW 4=N 5=NE.
"""

SQUARE_OFFSETS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
HEX_OFFSETS_EVEN = [(1, 0), (0, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
HEX_OFFSETS_ODD = [(1, 1), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, 0)]


def edge_count(grid_type):
    return 6 if grid_type == "hex" else 4


def neighbor(grid_type, c, r, e):
    if grid_type == "hex":
        dc, dr = (HEX_OFFSETS_ODD if c & 1 else HEX_OFFSETS_EVEN)[e]
    else:
        dc, dr = SQUARE_OFFSETS[e]
    return c + dc, r + dr


def opposite_edge(grid_type, e):
    return (e + 3) % 6 if grid_type == "hex" else (e + 2) % 4


def edge_between(grid_type, a, b):
    """Edge index on cell a that touches cell b, or None if not adjacent."""
    for e in range(edge_count(grid_type)):
        if neighbor(grid_type, a[0], a[1], e) == (b[0], b[1]):
            return e
    return None


def key(c, r):
    return f"{c},{r}"


def in_bounds(m, c, r):
    return 0 <= c < m["width"] and 0 <= r < m["height"]


def is_room(cells, c, r):
    cell = cells.get(key(c, r))
    return bool(cell and cell.get("fill"))


def door_closed(grid_type, cells, a, b):
    """True if a closed door sits on the shared edge of adjacent cells a and b."""
    e = edge_between(grid_type, a, b)
    if e is None:
        return False
    ca = cells.get(key(*a)) or {}
    cb = cells.get(key(*b)) or {}
    da = (ca.get("doors") or {}).get(str(e))
    db = (cb.get("doors") or {}).get(str(opposite_edge(grid_type, e)))
    for d in (da, db):
        if d and not d.get("open"):
            return True
    return False


def is_secret(cells, c, r):
    cell = cells.get(key(c, r))
    return bool(cell and cell.get("secret"))


def passable(grid_type, cells, m, a, b, explored=None):
    """Can a token step from a to b? Adjacent, both rooms, no closed door.
    Secret cells are only walkable once the GM has revealed them to this player."""
    if not in_bounds(m, *b) or not is_room(cells, *b):
        return False
    if is_secret(cells, *b) and not (explored or {}).get(key(*b)):
        return False
    if edge_between(grid_type, a, b) is None:
        return False
    return not door_closed(grid_type, cells, a, b)


def reveal_from(m, cells, start, radius, explored=None):
    """BFS through room cells up to `radius` steps, not crossing closed doors.
    Secret cells are never revealed this way (only the GM can), and are not
    walked through unless already explored. Returns the set of cell keys to mark explored."""
    explored = explored or {}
    grid_type = m["gridType"]
    seen = {tuple(start): 0}
    frontier = [tuple(start)]
    while frontier:
        nxt = []
        for cur in frontier:
            d = seen[cur]
            if d >= radius:
                continue
            for e in range(edge_count(grid_type)):
                nb = neighbor(grid_type, cur[0], cur[1], e)
                if nb in seen:
                    continue
                if not in_bounds(m, *nb) or not is_room(cells, *nb):
                    continue
                if is_secret(cells, *nb) and not explored.get(key(*nb)):
                    continue
                if door_closed(grid_type, cells, cur, nb):
                    continue
                seen[nb] = d + 1
                nxt.append(nb)
        frontier = nxt
    return {key(c, r) for (c, r) in seen}


def find_path(m, cells, start, goal, max_len=120, explored=None):
    """Shortest path of passable steps from start to goal (list of (c,r) excluding start), or None."""
    grid_type = m["gridType"]
    start, goal = tuple(start), tuple(goal)
    if start == goal:
        return []
    if not in_bounds(m, *goal) or not is_room(cells, *goal):
        return None
    prev = {start: None}
    frontier = [start]
    depth = 0
    while frontier and depth < max_len:
        nxt = []
        for cur in frontier:
            for e in range(edge_count(grid_type)):
                nb = neighbor(grid_type, cur[0], cur[1], e)
                if nb in prev or not passable(grid_type, cells, m, cur, nb, explored):
                    continue
                prev[nb] = cur
                if nb == goal:
                    path = []
                    while nb != start:
                        path.append(nb)
                        nb = prev[nb]
                    return path[::-1]
                nxt.append(nb)
        frontier = nxt
        depth += 1
    return None


def door_on_edge(grid_type, cells, c, r, e):
    """The door object sitting on edge e of cell (c,r), whether stored on this cell or the neighbour."""
    own = ((cells.get(key(c, r)) or {}).get("doors") or {}).get(str(e))
    if own:
        return own
    nc, nr = neighbor(grid_type, c, r, e)
    return ((cells.get(key(nc, nr)) or {}).get("doors") or {}).get(str(opposite_edge(grid_type, e)))

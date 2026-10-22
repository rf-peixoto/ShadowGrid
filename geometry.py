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


# ---------------------------------------------------------------- line of sight and cover
SQRT3 = 3 ** 0.5


def cell_center(grid_type, c, r):
    """Center of a cell in a continuous space (square: unit cells; hex: flat-top, size 1)."""
    if grid_type == "hex":
        return c * 1.5, SQRT3 * (r + 0.5 * (c & 1))
    return c + 0.5, r + 0.5


def point_cell(grid_type, x, y):
    """The cell containing point (x, y)."""
    if grid_type != "hex":
        return int(x // 1), int(y // 1)
    q = (2 / 3) * x
    r = (-1 / 3) * x + (SQRT3 / 3) * y
    cx, cz = q, r
    cy = -cx - cz
    rx, ry, rz = round(cx), round(cy), round(cz)
    dx, dy, dz = abs(rx - cx), abs(ry - cy), abs(rz - cz)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    col = int(rx)
    row = int(rz + (col - (col & 1)) / 2)
    return col, row


def _step_ok(m, cells, a, b):
    """Can sight pass from cell a into the next cell b? b must be a room, and no closed door between."""
    gt = m["gridType"]
    if not in_bounds(m, *b) or not is_room(cells, *b):
        return False
    if edge_between(gt, a, b) is None:
        # diagonal corner crossing on a square grid: open if either way around is open
        if gt != "hex" and abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1:
            for mid in ((b[0], a[1]), (a[0], b[1])):
                if is_room(cells, *mid) and not door_closed(gt, cells, a, mid) and not door_closed(gt, cells, mid, b):
                    return True
            return False
        return True
    return not door_closed(gt, cells, a, b)


def ray_clear(m, cells, p, q, start_cell, end_cell):
    """True if a straight line from point p to point q crosses no wall or closed door."""
    gt = m["gridType"]
    dist = ((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5
    steps = max(1, int(dist / 0.08))
    cur = start_cell
    for i in range(1, steps + 1):
        t = i / steps
        nxt = point_cell(gt, p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
        if i == steps:
            nxt = end_cell
        if nxt != cur:
            if not _step_ok(m, cells, cur, nxt):
                return False
            cur = nxt
    return True


def _samples(grid_type, c, r, spread):
    x, y = cell_center(grid_type, c, r)
    s = spread * 0.5      # stays inside the cell on both grids (hex inner radius is 0.87)
    return [(x, y), (x - s, y - s), (x + s, y - s), (x - s, y + s), (x + s, y + s)]


def line_of_sight(m, cells, a, b):
    """Sight between two cells: rays from points around the attacker's cell to points around the target's.
    Returns {"los": bool, "cover": 0-4, "clear": n, "rays": n}. Cover follows the share of blocked rays:
    up to 1/4 blocked = Cover I, 1/2 = II, 3/4 = III, more = IV; all blocked = no line of sight."""
    a, b = tuple(a), tuple(b)
    if a == b:
        return {"los": True, "cover": 0, "clear": 1, "rays": 1}
    gt = m["gridType"]
    src = _samples(gt, a[0], a[1], 0.6)
    dst = _samples(gt, b[0], b[1], 0.7)
    total = clear = 0
    for p in src:
        for q in dst:
            total += 1
            if ray_clear(m, cells, p, q, a, b):
                clear += 1
    if not clear:
        return {"los": False, "cover": 0, "clear": 0, "rays": total}
    blocked = 1 - clear / total
    cover = 0 if blocked == 0 else 1 if blocked <= 0.25 else 2 if blocked <= 0.5 else 3 if blocked <= 0.75 else 4
    return {"los": True, "cover": cover, "clear": clear, "rays": total}


def visible_cells(m, cells, start, radius, explored=None):
    """Room cells within `radius` steps that can be seen from `start` (walls and closed doors block sight).
    A cell counts as seen if any sight line reaches it: the centre-to-centre ray first, then rays from the
    four corners of our own cell. Secret cells stay hidden unless already explored. Returns cell keys."""
    explored = explored or {}
    gt = m["gridType"]
    a = tuple(start)
    out = {key(*a)}
    src = _samples(gt, a[0], a[1], 0.6)
    for c in range(a[0] - radius - 1, a[0] + radius + 2):
        for r in range(a[1] - radius - 1, a[1] + radius + 2):
            b = (c, r)
            if b == a or not in_bounds(m, c, r) or not is_room(cells, c, r):
                continue
            if cell_distance(gt, a, b) > radius:
                continue
            if is_secret(cells, c, r) and not explored.get(key(c, r)):
                continue
            q = cell_center(gt, c, r)
            if any(ray_clear(m, cells, p, q, a, b) for p in src):
                out.add(key(c, r))
    return out


def cell_distance(grid_type, a, b):
    """Steps between two cells (Chebyshev on squares, hex distance on hexes)."""
    if grid_type != "hex":
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    def cube(c, r):
        x = c
        z = r - (c - (c & 1)) // 2
        return x, -x - z, z
    ax, ay, az = cube(*a)
    bx, by, bz = cube(*b)
    return max(abs(ax - bx), abs(ay - by), abs(az - bz))

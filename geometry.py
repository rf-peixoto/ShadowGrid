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


# ---------------------------------------------------------------- line of sight, cover, light and vision
SQRT3 = 3 ** 0.5
LIGHT_LEVELS = ("bright", "dim", "dark")
SMOKE_KINDS = ("smoke", "thermal")
ULTRASOUND_M = 50          # an ultrasound sensor "sees" this far in total darkness (sensor table, p. 277)
FLASHLIGHT_M = 10          # a carried flashlight lights the cells around its holder that it can reach


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


_HEX_CORNERS = [(1.0, 0.0), (0.5, SQRT3 / 2), (-0.5, SQRT3 / 2), (-1.0, 0.0), (-0.5, -SQRT3 / 2), (0.5, -SQRT3 / 2)]


def _samples(grid_type, c, r, spread):
    x, y = cell_center(grid_type, c, r)
    s = spread * 0.5      # stays inside the cell on both grids (hex inner radius is 0.87)
    return [(x, y), (x - s, y - s), (x + s, y - s), (x - s, y + s), (x + s, y + s)]


def _cover_level(clear, total):
    if not clear:
        return 0
    blocked = 1 - clear / total
    return 0 if blocked == 0 else 1 if blocked <= 0.25 else 2 if blocked <= 0.5 else 3 if blocked <= 0.75 else 4


def vision_handles(vision, light, smoke, dist_m=0):
    """Does this set of vision types see through a condition clearly? light: 0 bright, 1 dim, 2 dark;
    smoke: None, "smoke" or "thermal". Low-light: anything but total darkness (p. 73); thermographic:
    darkness and normal smoke, not thermal smoke (p. 263); ultrasound: darkness and smoke, within 50 m."""
    v = vision or ()
    ultra = "Ultrasound" in v and dist_m <= ULTRASOUND_M
    if smoke == "thermal" and not ultra:
        return False
    if smoke == "smoke" and not (ultra or "Thermographic" in v):
        return False
    if light >= 2:
        return ultra or "Thermographic" in v
    if light == 1:
        return ultra or "Thermographic" in v or "Low-light" in v
    return True


class Sight:
    """Walls, doors, light and smoke of one map, for fast sight lines. Rays walk the grid exactly, cell to
    cell (squares: a DDA; hexes: through the edges of each hexagon), so the work grows with the distance in
    cells rather than with tiny sampling steps. The browser (gridcore.js) does the same.

    m: {"gridType", "width", "height", "settings"?}; cells: map cells; sources: [(c, r, radius_cells)] lights."""

    def __init__(self, m, cells, sources=(), ambient=None):
        self.hex = m.get("gridType") == "hex"
        self.gt = "hex" if self.hex else "square"
        self.w, self.h = int(m["width"]), int(m["height"])
        st = m.get("settings") or {}
        amb = ambient if ambient is not None else st.get("ambientLight", "bright")
        self.ambient = LIGHT_LEVELS.index(amb) if amb in LIGHT_LEVELS else 0
        self.rooms, self.secret, self.closed, self.light, self.smoke = set(), set(), set(), {}, {}
        for k, cell in cells.items():
            if not isinstance(cell, dict):
                continue
            try:
                i = k.index(",")
                c, r = int(k[:i]), int(k[i + 1:])
            except ValueError:
                continue
            if cell.get("fill") and 0 <= c < self.w and 0 <= r < self.h:
                self.rooms.add((c, r))
            if cell.get("secret"):
                self.secret.add((c, r))
            if cell.get("light") in LIGHT_LEVELS:
                self.light[(c, r)] = LIGHT_LEVELS.index(cell["light"])
            if cell.get("smoke") in SMOKE_KINDS:
                self.smoke[(c, r)] = cell["smoke"]
            for e, d in (cell.get("doors") or {}).items():
                if isinstance(d, dict) and not d.get("open") and str(e).isdigit():
                    nb = neighbor(self.gt, c, r, int(e))
                    self.closed.add(((c, r), nb))
                    self.closed.add((nb, (c, r)))
        self.lit = set()
        for (sc, sr_, rad) in sources or ():
            self.lit |= self._lit_by((sc, sr_), rad)
        self.sig = hash((self.gt, self.w, self.h, self.ambient, frozenset(self.rooms), frozenset(self.closed),
                         frozenset(self.light.items()), frozenset(self.smoke.items()), frozenset(self.lit)))

    # ---- cells
    def room(self, c, r):
        return (c, r) in self.rooms

    def level(self, c, r):
        """Light at a cell: 0 bright, 1 dim, 2 dark (a light source brightens what it reaches)."""
        if (c, r) in self.lit:
            return 0
        return self.light.get((c, r), self.ambient)

    def adjacent(self, a, b):
        if not self.hex:
            return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        return edge_between("hex", a, b) is not None

    def step_ok(self, a, b):
        """Can sight pass from cell a into the next cell b? b must be a room, and no closed door between."""
        if b not in self.rooms:
            return False
        if (a, b) in self.closed:
            return False
        if not self.hex and abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1:
            # exactly through a corner: open if either way around is open
            for mid in ((b[0], a[1]), (a[0], b[1])):
                if mid in self.rooms and (a, mid) not in self.closed and (mid, b) not in self.closed:
                    return True
            return False
        return True

    # ---- rays
    def walk(self, p, q, a, b):
        """Cells a ray from point p (in cell a) to point q (in cell b) enters, in order: yields (cell, ok).
        Stops at the first step that is blocked (ok False) or at b."""
        cur = a
        if self.hex:
            dx, dy = q[0] - p[0], q[1] - p[1]
            t = 0.0
            for _ in range(4 * (self.w + self.h) + 8):
                if cur == b:
                    return
                cx, cy = cell_center("hex", cur[0], cur[1])
                best, be = 2.0, -1
                for e in range(6):
                    x1, y1 = _HEX_CORNERS[e]
                    x2, y2 = _HEX_CORNERS[(e + 1) % 6]
                    ax, ay = cx + x1, cy + y1
                    ex, ey = x2 - x1, y2 - y1
                    den = dx * ey - dy * ex
                    if abs(den) < 1e-12:
                        continue
                    s = ((ax - p[0]) * ey - (ay - p[1]) * ex) / den
                    u = ((ax - p[0]) * dy - (ay - p[1]) * dx) / den
                    if s > t + 1e-9 and -1e-9 <= u <= 1 + 1e-9 and s < best:
                        best, be = s, e
                if be < 0 or best >= 1.0:
                    # the ray ends in this cell: the sample point sits at the edge of the target cell
                    yield b, self.step_ok(cur, b) if cur != b else True
                    return
                nxt = neighbor("hex", cur[0], cur[1], be)
                ok = self.step_ok(cur, nxt)
                yield nxt, ok
                if not ok:
                    return
                cur, t = nxt, best
            return
        x0, y0 = p
        dx, dy = q[0] - x0, q[1] - y0
        c, r = cur
        sx = 1 if dx > 0 else -1
        sy = 1 if dy > 0 else -1
        tdx = abs(1 / dx) if dx else float("inf")
        tdy = abs(1 / dy) if dy else float("inf")
        tx = ((c + 1 - x0) if dx > 0 else (x0 - c)) * tdx if dx else float("inf")
        ty = ((r + 1 - y0) if dy > 0 else (y0 - r)) * tdy if dy else float("inf")
        for _ in range(2 * (self.w + self.h) + 8):
            if (c, r) == b:
                return
            if abs(tx - ty) < 1e-9:
                t, nc, nr = tx, c + sx, r + sy
                tx += tdx
                ty += tdy
            elif tx < ty:
                t, nc, nr = tx, c + sx, r
                tx += tdx
            else:
                t, nc, nr = ty, c, r + sy
                ty += tdy
            if t >= 1.0:
                yield b, self.step_ok((c, r), b) if (c, r) != b else True
                return
            ok = self.step_ok((c, r), (nc, nr))
            yield (nc, nr), ok
            if not ok:
                return
            c, r = nc, nr

    def ray_clear(self, p, q, a, b):
        for _cell, ok in self.walk(p, q, a, b):
            if not ok:
                return False
        return True

    def cover(self, a, b):
        """Sight between two cells: 5 points around the viewer's cell to 5 around the target's (25 rays).
        Cover follows the share of blocked rays: up to 1/4 = I, 1/2 = II, 3/4 = III, more = IV; all = none."""
        a, b = tuple(a), tuple(b)
        if a == b:
            return {"los": True, "cover": 0, "clear": 1, "rays": 1}
        src = _samples(self.gt, a[0], a[1], 0.6)
        dst = _samples(self.gt, b[0], b[1], 0.7)
        clear = sum(1 for p in src for q in dst if self.ray_clear(p, q, a, b))
        return {"los": bool(clear), "cover": _cover_level(clear, 25), "clear": clear, "rays": 25}

    def can_see(self, a, b):
        """Any sight line from around a to the centre of b (walls and closed doors only)."""
        a, b = tuple(a), tuple(b)
        if a == b:
            return True
        q = cell_center(self.gt, b[0], b[1])
        return any(self.ray_clear(p, q, a, b) for p in _samples(self.gt, a[0], a[1], 0.6))

    def _lit_by(self, src, radius):
        out = {src} if src in self.rooms else set()
        p = cell_center(self.gt, *src)
        for c in range(src[0] - radius - 1, src[0] + radius + 2):
            for r in range(src[1] - radius - 1, src[1] + radius + 2):
                if (c, r) in self.rooms and cell_distance(self.gt, src, (c, r)) <= radius and \
                        self.ray_clear(p, cell_center(self.gt, c, r), src, (c, r)):
                    out.add((c, r))
        return out

    def smoke_between(self, a, b):
        """The thickest smoke a centre-to-centre line passes through (not counting either end)."""
        worst = None
        for cell, ok in self.walk(cell_center(self.gt, *a), cell_center(self.gt, *b), tuple(a), tuple(b)):
            if not ok or cell == tuple(b):
                break
            s = self.smoke.get(cell)
            if s == "thermal" or (s and worst is None):
                worst = s
        return worst

    # ---- what a character sees
    def view(self, a, b, vision=(), cell_m=2.0, blinded=0):
        """How a viewer in cell a with these vision types sees cell b (walls aside):
        {"see": bool, "blind": 0-3 environmental Blinded level, "clear": sees clearly, "dark": too dark}.
        Darkness: only thermographic or ultrasound (50 m). Smoke: Blinded I looking through it, II from
        inside it (p. 263). Dim light costs nothing but a clear view (the bonus Edge rule, p. 118)."""
        a, b = tuple(a), tuple(b)
        if blinded >= 3:
            return {"see": False, "blind": 3, "clear": False, "dark": False}
        dist_m = self.distance_m(a, b, cell_m)
        lv = self.level(*b)
        if lv >= 2 and not vision_handles(vision, 2, None, dist_m):
            return {"see": False, "blind": 3, "clear": False, "dark": True}
        blind = 0
        own = self.smoke.get(a)
        if own and not vision_handles(vision, 0, own, dist_m):
            blind = 2
        else:
            mid = self.smoke.get(b) or self.smoke_between(a, b)
            if mid and not vision_handles(vision, 0, mid, dist_m):
                blind = 1
        clear = blind == 0 and (lv == 0 or vision_handles(vision, lv, None, dist_m))
        return {"see": True, "blind": blind, "clear": clear, "dark": False}

    def distance_m(self, a, b, cell_m=2.0):
        """Straight-line distance between cell centres in meters."""
        ax, ay = cell_center(self.gt, *a)
        bx, by = cell_center(self.gt, *b)
        d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
        return d / SQRT3 * cell_m if self.hex else d * cell_m

    def visible_cells(self, start, radius, explored=None, vision=None, cell_m=2.0, blinded=0):
        """Room cells within `radius` steps the viewer can see: any sight line from around their cell to the
        cell's centre, and (with `vision` given) light enough for their eyes. Secret cells stay hidden unless
        explored. Cached: the same map state, place and eyes give the same answer."""
        explored = explored or {}
        a = tuple(start)
        vkey = None if vision is None else tuple(sorted(vision))
        ck = (self.sig, a, radius, vkey, cell_m, blinded, frozenset(k for k in explored if k in self._secret_keys()))
        hit = _VIS_CACHE.get(ck)
        if hit is not None:
            return set(hit)
        out = {key(*a)}
        if blinded < 3:
            src = _samples(self.gt, a[0], a[1], 0.6)
            for c in range(a[0] - radius - 1, a[0] + radius + 2):
                for r in range(a[1] - radius - 1, a[1] + radius + 2):
                    b = (c, r)
                    if b == a or b not in self.rooms or cell_distance(self.gt, a, b) > radius:
                        continue
                    if b in self.secret and not explored.get(key(c, r)):
                        continue
                    if vision is not None and self.level(c, r) >= 2 and \
                            not vision_handles(vision, 2, None, self.distance_m(a, b, cell_m)):
                        continue
                    q = cell_center(self.gt, c, r)
                    if any(self.ray_clear(p, q, a, b) for p in src):
                        out.add(key(c, r))
        _VIS_CACHE[ck] = frozenset(out)
        while len(_VIS_CACHE) > _VIS_CACHE_MAX:
            _VIS_CACHE.pop(next(iter(_VIS_CACHE)))
        return out

    def _secret_keys(self):
        return {key(*x) for x in self.secret} if self.secret else ()


_VIS_CACHE = {}
_VIS_CACHE_MAX = 512


def line_of_sight(m, cells, a, b):
    """Sight and cover between two cells (walls and closed doors). See Sight.cover."""
    return Sight(m, cells).cover(a, b)


def visible_cells(m, cells, start, radius, explored=None):
    """Room cells within `radius` steps that can be seen from `start` (walls and closed doors block sight)."""
    return Sight(m, cells).visible_cells(start, radius, explored)


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

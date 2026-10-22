"""Sight on a live map: the map's walls, doors, light and smoke (geometry.Sight) plus its light sources
(markers the GM lit, runners' flashlights), and what one runner's eyes make of it."""
import json
import math

import geometry as geo
from core import get_db, load_char
from sr import combat as X
from sr import rules as R

_CACHE = {}
_CACHE_MAX = 64


def cell_meters(m):
    try:
        v = float((m.get("settings") or {}).get("cellMeters") or 2)
    except (TypeError, ValueError):
        v = 2.0
    return max(0.5, min(10.0, v))


def cells_for(meters, m):
    return max(0, int(math.ceil(float(meters) / cell_meters(m) - 1e-9)))


def flashlights(map_id, db=None, me=None):
    """Cells of runners on this map with their flashlight switched on. me: a player dict (row_to_player)
    whose unsaved state replaces what the database has for them."""
    db = db or get_db()
    out = []
    states = {row["id"]: json.loads(row["state"] or "{}") for row in
              db.execute("SELECT id, state FROM players WHERE current_map_id=?", (map_id,)).fetchall()}
    if me is not None:
        states.pop(me["id"], None)
        if me.get("currentMapId") == map_id:
            states[me["id"]] = me.get("state") or {}
    for state in states.values():
        st = (state.get("maps") or {}).get(map_id) or {}
        tok = st.get("token")
        if st.get("flashlight") and isinstance(tok, dict):
            out.append((int(tok["c"]), int(tok["r"])))
    return out


def light_sources(m, db=None, me=None):
    """[(c, r, radius in cells)] for lit markers and flashlights."""
    src = []
    for mk in m["data"].get("markers") or []:
        lr = mk.get("light")
        if lr:
            src.append((int(mk["c"]), int(mk["r"]), cells_for(lr, m)))
    if m.get("id"):
        r = cells_for(geo.FLASHLIGHT_M, m)
        src += [(c, rr, r) for c, rr in flashlights(m["id"], db, me)]
    return tuple(sorted(src))


def map_sight(m, db=None, cached=False, me=None):
    """geometry.Sight for a map dict (with data). cached=True reuses one built for the same saved map
    version and the same light sources (read paths); writes build a fresh one from the data in hand."""
    src = light_sources(m, db, me)
    key = (m.get("id"), m.get("updatedAt"), src) if cached and m.get("updatedAt") is not None else None
    if key is not None and key in _CACHE:
        return _CACHE[key]
    s = geo.Sight(m, m["data"]["cells"], src)
    if key is not None:
        _CACHE[key] = s
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
    return s


def blinded_level(statuses):
    v = (statuses or {}).get("Blinded")
    if not v:
        return 0
    return 1 if v is True else max(0, min(3, int(v) if str(v).isdigit() else 1))


def eyes_of_char(c, d=None):
    """(vision types, extras, Blinded level) of a runner."""
    d = d or R.derive(c)
    return list(d.get("vision") or []), list(d.get("vision_extras") or []), blinded_level(c.get("statuses"))


def eyes_of_marker(mk):
    return X.npc_vision(mk.get("npc"), mk), [], blinded_level(mk.get("statuses"))


def eyes_of_player_row(row):
    return eyes_of_char(load_char(row))


CREATURE_TYPES = ("danger", "boss", "npc")


def is_creature(mk):
    """Markers that move and hide: enemies, bosses, NPCs and anything with a stat block or monitor."""
    return mk.get("type") in CREATURE_TYPES or bool(mk.get("npc")) or bool(mk.get("cm"))

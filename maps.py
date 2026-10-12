"""Maps: fog of war, doors, markers, tokens, snapshots (GM) and the player's map view.

Players are real accounts, tokens and enemy markers carry Shadowrun condition
monitors, and dice live in the Shadowrun roller (game.py).
"""
import json
import re

from flask import Response, abort, jsonify, request

import geometry as geo
from core import (DEFAULT_SETTINGS, app, body, campaign_version, clamp_int, clean_color, display_name,
                  err, fetch_player, get_db, load_char, new_id, now, player_required, roll_rows,
                  row_to_player, save_char, save_player)
import fight
from security import gamemaster_required, rate_limited
from sr import combat as X
from sr import rules as R

MAP_FORMAT = "shadowgrid-map-1"


# ====================================================================== cleaning
def merged_settings(user):
    s = json.loads(json.dumps(DEFAULT_SETTINGS))
    if isinstance(user, dict):
        for k, v in user.items():
            if k == "colors" and isinstance(v, dict):
                for ck, cv in v.items():
                    if ck in s["colors"]:
                        s["colors"][ck] = clean_color(cv, s["colors"][ck])
            elif k == "doorPalette" and isinstance(v, list):
                s[k] = [clean_color(c, "#ffffff") for c in v[:12]]
            elif k in ("legendVisible", "showGrid", "showRoomLabels"):
                s[k] = bool(v)
    return s


def clean_cm(v):
    """Enemy condition monitor: {pm, sm, ov, p, s} (max physical, max stun, overflow, damage).
    Grunts have a single track (``grunt``: true, sm 0) and remember what hit them last."""
    if not isinstance(v, dict):
        return None
    pm = clamp_int(v.get("pm"), 0, 60, 0)
    sm = clamp_int(v.get("sm"), 0, 60, 0)
    if not pm and not sm:
        return None
    ov = clamp_int(v.get("ov"), 0, 40, 0)
    out = {"pm": pm, "sm": sm, "ov": ov,
           "p": clamp_int(v.get("p"), 0, pm + ov, 0), "s": clamp_int(v.get("s"), 0, sm, 0)}
    if v.get("grunt"):
        out["grunt"] = True
        out["sm"] = 0
        out["ov"] = 0
        out["p"] = min(out["p"], pm)
        if v.get("last") in ("P", "S"):
            out["last"] = v["last"]
    return out


def cm_damage(cm, track, amount):
    """Apply +/- boxes to a marker monitor with Stun overflowing into Physical (same rule as characters)."""
    X.marker_damage(cm, track, amount)


RUNTIME_MARKER_KEYS = ("cm", "statuses")


def clean_data(data, grid_type="square"):
    """Validate the map body coming from the editor. Drops junk, keeps shape stable."""
    out = {"cells": {}, "markers": [], "rooms": []}
    if not isinstance(data, dict):
        return out
    for k, cell in (data.get("cells") or {}).items():
        if not isinstance(cell, dict):
            continue
        try:
            c, r = (int(x) for x in k.split(","))
        except ValueError:
            continue
        nc = {}
        if cell.get("fill"):
            nc["fill"] = clean_color(cell["fill"], "#1c4a52")
        if cell.get("border"):
            nc["border"] = clean_color(cell["border"], "#4fd8dc")
        if cell.get("borderOn") is False:
            nc["borderOn"] = False
        if cell.get("secret"):
            nc["secret"] = True
        doors = {}
        for e, d in (cell.get("doors") or {}).items():
            if isinstance(d, dict) and str(e).isdigit() and int(e) < 6:
                nd = {"color": clean_color(d.get("color"), "#2de2e6"), "open": bool(d.get("open")) and not d.get("locked")}
                if d.get("locked"):
                    nd["locked"] = True
                doors[str(int(e))] = nd
        if doors:
            nc["doors"] = doors
        if nc:
            out["cells"][f"{c},{r}"] = nc
    # a door belongs to one edge; if both cells of a shared edge carry one, keep the first and drop the mirror
    seen_edges = set()
    for k in sorted(out["cells"]):
        cell = out["cells"][k]
        if not cell.get("doors"):
            continue
        c, r = (int(x) for x in k.split(","))
        for e in list(cell["doors"]):
            nc, nr = geo.neighbor(grid_type, c, r, int(e))
            sig = frozenset([(c, r, int(e)), (nc, nr, geo.opposite_edge(grid_type, int(e)))])
            if sig in seen_edges:
                del cell["doors"][e]
            else:
                seen_edges.add(sig)
        if not cell["doors"]:
            del cell["doors"]
            if not cell:
                del out["cells"][k]
    for m in (data.get("markers") or [])[:5000]:
        if not isinstance(m, dict):
            continue
        try:
            nm = {"id": str(m.get("id") or new_id(8))[:16], "c": int(m["c"]), "r": int(m["r"]),
                  "type": str(m.get("type") or "poi")[:24], "color": clean_color(m.get("color"), "#ff2f7d"),
                  "label": str(m.get("label") or "")[:80]}
        except (KeyError, TypeError, ValueError):
            continue
        if m.get("hidden"):
            nm["hidden"] = True
        cm = clean_cm(m.get("cm"))
        if cm:
            nm["cm"] = cm
        npc = X.clean_npc(m.get("npc"))
        if npc:
            nm["npc"] = npc
        st = fight.clean_statuses(m.get("statuses"))
        if st:
            nm["statuses"] = st
        t = m.get("target")
        if m.get("linkId") or nm["type"] == "link":
            nm["linkId"] = re.sub(r"[^A-Za-z0-9_-]", "", str(m.get("linkId") or ""))[:24] or new_id(8)
            if isinstance(t, dict):
                try:
                    nm["target"] = {"mapId": str(t.get("mapId") or "")[:16], "c": int(t.get("c", 0)), "r": int(t.get("r", 0))}
                except (TypeError, ValueError):
                    pass
        out["markers"].append(nm)
    for room in (data.get("rooms") or [])[:1000]:
        if not isinstance(room, dict):
            continue
        cells = [str(k)[:16] for k in (room.get("cells") or []) if isinstance(k, str)][:20000]
        out["rooms"].append({"id": str(room.get("id") or new_id(8))[:16], "name": str(room.get("name") or "Room")[:60],
                             "cells": cells})
    return out


def row_to_map(row, include_data=True):
    m = {"id": row["id"], "campaignId": row["campaign_id"], "name": row["name"], "gridType": row["grid_type"],
         "width": row["width"], "height": row["height"], "cellSize": row["cell_size"],
         "settings": merged_settings(json.loads(row["settings"])),
         "createdAt": row["created_at"], "updatedAt": row["updated_at"]}
    if include_data:
        m["data"] = json.loads(row["data"])
        m["data"].setdefault("cells", {})
        m["data"].setdefault("markers", [])
        m["data"].setdefault("rooms", [])
    return m


def fetch_map(map_id):
    row = get_db().execute("SELECT * FROM maps WHERE id=?", (map_id,)).fetchone()
    if not row:
        abort(404)
    return row_to_map(row)


def save_map_data(map_id, data):
    get_db().execute("UPDATE maps SET data=?, updated_at=? WHERE id=?", (json.dumps(data), now(), map_id))


def player_map_state(p, map_id):
    maps = p["state"].setdefault("maps", {})
    return maps.setdefault(map_id, {"explored": {}, "token": None, "mapStation": False})


def place_player(p, m, c, r, path=None):
    """Put a player's token on a map cell and reveal around it (and along `path`). Mutates p."""
    ms = player_map_state(p, m["id"])
    ms["token"] = {"c": c, "r": r}
    p["currentMapId"] = m["id"]
    ms["explored"][f"{c},{r}"] = True
    for step in (path or []) + [(c, r)]:
        for k in geo.reveal_from(m, m["data"]["cells"], step, p["radius"], ms["explored"]):
            ms["explored"][k] = True


def is_link(mk):
    return bool(mk.get("linkId")) or mk.get("type") == "link"


def link_at(m, c, r):
    return next((mk for mk in m["data"]["markers"] if is_link(mk) and mk["c"] == c and mk["r"] == r), None)


def resolve_link(link, from_map):
    """Destination (map row, c, r) for a link marker: explicit target, else a marker sharing its linkId elsewhere."""
    db = get_db()
    t = link.get("target") or {}
    row = db.execute("SELECT * FROM maps WHERE id=?", (t.get("mapId"),)).fetchone() if t.get("mapId") else None
    if row and row["id"] != from_map["id"]:
        return row, int(t.get("c", 0)), int(t.get("r", 0))
    lid = link.get("linkId")
    if lid and from_map["campaignId"]:
        for r2 in db.execute("SELECT * FROM maps WHERE campaign_id=? AND id<>?", (from_map["campaignId"], from_map["id"])).fetchall():
            for mk in json.loads(r2["data"]).get("markers", []):
                if is_link(mk) and mk.get("linkId") == lid:
                    return r2, mk["c"], mk["r"]
    return None, 0, 0


def travel_player(p, m, link):
    row, tc, tr = resolve_link(link, m)
    if not row:
        return False
    target = row_to_map(row)
    if not geo.in_bounds(target, tc, tr):
        tc, tr = 0, 0
    place_player(p, target, tc, tr)
    return True


def locked_player(pid):
    """Start a write transaction and load the player inside it, so concurrent fog/token
    updates (a player moving while the GM reveals) can't overwrite each other."""
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    row = db.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not row:
        db.rollback()
        abort(404)
    return row_to_player(row)


def insert_map(b, default_name, campaign_id=None):
    db = get_db()
    name = (str(b.get("name") or default_name)).strip()[:120]
    grid_type = b.get("gridType") if b.get("gridType") in ("square", "hex") else "square"
    width = clamp_int(b.get("width"), 4, 200, 40)
    height = clamp_int(b.get("height"), 4, 200, 24)
    cell_size = clamp_int(b.get("cellSize"), 8, 128, 32)
    settings = merged_settings(b.get("settings"))
    data = clean_data(b.get("data"), grid_type)
    cid = b.get("campaignId") or campaign_id
    if cid and not db.execute("SELECT 1 FROM campaigns WHERE id=?", (cid,)).fetchone():
        cid = None
    map_id = new_id()
    t = now()
    db.execute("INSERT INTO maps (id,campaign_id,name,grid_type,width,height,cell_size,settings,data,created_at,updated_at)"
               " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (map_id, cid, name, grid_type, width, height, cell_size, json.dumps(settings), json.dumps(data), t, t))
    db.commit()
    return map_id


# ====================================================================== gamemaster api: maps
@app.route("/api/maps", methods=["POST"])
@gamemaster_required
def create_map():
    return jsonify({"id": insert_map(body(), "Untitled map")}), 201


@app.route("/api/maps/<map_id>", methods=["GET"])
@gamemaster_required
def get_map(map_id):
    return jsonify(fetch_map(map_id))


def runner_vehicles(rows):
    """Vehicles and drones the runners own, as NPC template keys for the editor ("pv:<player>:<item>")."""
    out = []
    for r in rows:
        c = load_char(r)
        for it in R.vehicles_of(c):
            out.append({"key": f"pv:{r['id']}:{it['uid']}", "name": f"{it['name']} ({display_name(r, c)})",
                        "kind": "Runners' vehicles", "pr": None})
    return out


def runner_vehicle_npc(key):
    """NPC stat block for a runner's own vehicle, linked to it (damage on the map is written back)."""
    _, pid, uid = key.split(":", 2)
    row = get_db().execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not row:
        raise R.RuleError("That runner is gone.")
    c = load_char(row)
    it = next((x for x in R.vehicles_of(c) if x["uid"] == uid), None)
    if not it:
        raise R.RuleError("That vehicle is gone.")
    npc = X.vehicle_npc(it, f"{it['name']} ({display_name(row, c)})", link={"pid": pid, "uid": uid})
    return npc, R._int(it.get("damage"))


@app.route("/api/maps/<map_id>/context", methods=["GET"])
@gamemaster_required
def map_context(map_id):
    """Everything the editor needs in one call."""
    db = get_db()
    m = fetch_map(map_id)
    version = campaign_version(m["campaignId"], map_id)
    if request.args.get("since") == version:
        return jsonify({"unchanged": True, "version": version})
    ctx = {"map": m, "players": [], "campaignMaps": [], "snapshots": [], "campaign": None, "version": version}
    if m["campaignId"]:
        crow = db.execute("SELECT * FROM campaigns WHERE id=?", (m["campaignId"],)).fetchone()
        ctx["campaign"] = dict(crow) if crow else None
        prow = db.execute("SELECT * FROM players WHERE campaign_id=? ORDER BY created_at", (m["campaignId"],)).fetchall()
        ctx["players"] = [row_to_player(r) for r in prow]
        ctx["vehicles"] = runner_vehicles(prow)
        ctx["campaignMaps"] = [{"id": r["id"], "name": r["name"]} for r in db.execute(
            "SELECT id,name FROM maps WHERE campaign_id=? ORDER BY name", (m["campaignId"],)).fetchall()]
        ctx["snapshots"] = [{"id": r["id"], "name": r["name"], "createdAt": r["created_at"]} for r in db.execute(
            "SELECT id,name,created_at FROM snapshots WHERE campaign_id=? ORDER BY created_at DESC", (m["campaignId"],)).fetchall()]
    ctx["allMaps"] = [{"id": r["id"], "name": r["name"], "campaignId": r["campaign_id"]} for r in db.execute(
        "SELECT id,name,campaign_id FROM maps ORDER BY name").fetchall()]
    ctx["rolls"] = roll_rows(m["campaignId"], gamemaster=True)
    ctx["tracker"] = fight.tracker_view(fight.load_tracker(m["campaignId"]), True) if m["campaignId"] else None
    ctx["now"] = now()
    return jsonify(ctx)


def keep_runtime(old, new, runtime):
    """The editor autosaves the whole map. Doors opened by players and monitors or statuses changed by
    combat happen on the server meanwhile, so keep the server's value unless the editor says it changed it."""
    rt = runtime if isinstance(runtime, dict) else {}
    door_keys = {str(k) for k in (rt.get("doors") or [])}
    marker_ids = {str(k) for k in (rt.get("markers") or [])}
    for k, cell in new.get("cells", {}).items():
        oc = old.get("cells", {}).get(k) or {}
        for e, door in (cell.get("doors") or {}).items():
            od = (oc.get("doors") or {}).get(e)
            if od is not None and f"{k}:{e}" not in door_keys:
                door["open"] = bool(od.get("open"))
                if od.get("locked"):
                    door["locked"] = True
                    door["open"] = False
                else:
                    door.pop("locked", None)
    old_markers = {m["id"]: m for m in old.get("markers", [])}
    for m in new.get("markers", []):
        om = old_markers.get(m["id"])
        if om is None or m["id"] in marker_ids:
            continue
        for key in RUNTIME_MARKER_KEYS:
            if key in om:
                m[key] = om[key]
            else:
                m.pop(key, None)


@app.route("/api/maps/<map_id>", methods=["PUT"])
@gamemaster_required
def update_map(map_id):
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    old = fetch_map(map_id)
    b = body()
    name = str(b.get("name") or old["name"]).strip()[:120]
    width = clamp_int(b.get("width"), 4, 200, old["width"])
    height = clamp_int(b.get("height"), 4, 200, old["height"])
    cell_size = clamp_int(b.get("cellSize"), 8, 128, old["cellSize"])
    settings = merged_settings(b["settings"]) if "settings" in b else old["settings"]
    data = clean_data(b["data"], old["gridType"]) if "data" in b else old["data"]
    if "data" in b:
        keep_runtime(old["data"], data, b.get("runtime"))
    cid = old["campaignId"]
    if "campaignId" in b:
        cid = b["campaignId"] or None
        if cid and not db.execute("SELECT 1 FROM campaigns WHERE id=?", (cid,)).fetchone():
            cid = None
    db.execute("UPDATE maps SET name=?,campaign_id=?,width=?,height=?,cell_size=?,settings=?,data=?,updated_at=? WHERE id=?",
               (name, cid, width, height, cell_size, json.dumps(settings), json.dumps(data), now(), map_id))
    db.commit()
    return jsonify({"ok": True, "updatedAt": now()})


@app.route("/api/maps/<map_id>", methods=["DELETE"])
@gamemaster_required
def delete_map(map_id):
    """Delete a map: runners on it are taken off, and its enemies leave the combat tracker."""
    db = get_db()
    row = db.execute("SELECT campaign_id FROM maps WHERE id=?", (map_id,)).fetchone()
    if not row:
        return err("Map not found.", 404)
    db.execute("DELETE FROM maps WHERE id=?", (map_id,))
    db.execute("UPDATE players SET current_map_id=NULL, updated_at=? WHERE current_map_id=?", (now(), map_id))
    cid = row["campaign_id"]
    if cid:
        t = fight.load_tracker(cid)
        keep = [e for e in t["entries"] if not (e.get("kind") == "marker" and e.get("mapId") == map_id)]
        if len(keep) != len(t["entries"]):
            t["entries"] = keep
            t["turn"] = min(t.get("turn", 0), max(0, len(keep) - 1))
        fight.save_tracker(cid, t)   # also bumps the game's version so open pages refresh
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/maps/<map_id>/duplicate", methods=["POST"])
@gamemaster_required
def duplicate_map(map_id):
    m = fetch_map(map_id)
    m["name"] += " (copy)"
    return jsonify({"id": insert_map(m, m["name"], m["campaignId"])}), 201


@app.route("/api/maps/<map_id>/export", methods=["GET"])
@gamemaster_required
def export_map(map_id):
    m = fetch_map(map_id)
    m.pop("id", None)
    m.pop("campaignId", None)
    m["format"] = MAP_FORMAT
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in m["name"]).strip() or "map"
    return Response(json.dumps(m, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.json"'})


@app.route("/api/maps/import", methods=["POST"])
@gamemaster_required
def import_map():
    b = request.get_json(force=True, silent=True)
    if not isinstance(b, dict) or b.get("format") != MAP_FORMAT or not isinstance(b.get("data"), dict):
        return err("Not a ShadowGrid map file.")
    b = dict(b)
    b.pop("id", None)
    return jsonify({"id": insert_map(b, "Imported map", request.args.get("campaign"))}), 201


def apply_reveal(p, map_id, m, action, cell_keys):
    ms = player_map_state(p, map_id)
    if action == "station_on":
        ms["mapStation"] = True
    elif action == "station_off":
        ms["mapStation"] = False
    else:
        keys = list(m["data"]["cells"].keys()) if cell_keys == "all" else [str(k)[:16] for k in cell_keys]
        if action == "reveal":
            for k in keys:
                if k in m["data"]["cells"]:
                    ms["explored"][k] = True
        elif action == "hide":
            for k in keys:
                ms["explored"].pop(k, None)


@app.route("/api/maps/<map_id>/reveal", methods=["POST"])
@gamemaster_required
def bulk_reveal(map_id):
    """Delta updates to players' fog: {players:'all'|[ids], cells:'all'|[keys], action:reveal|hide|station_on|station_off}."""
    m = fetch_map(map_id)
    b = body()
    action = b.get("action")
    if action not in ("reveal", "hide", "station_on", "station_off"):
        return err("Unknown action.")
    cells = b.get("cells", "all")
    if cells != "all" and not isinstance(cells, list):
        return err("cells must be 'all' or a list.")
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    if b.get("players") == "all":
        rows = db.execute("SELECT * FROM players WHERE campaign_id=?", (m["campaignId"],)).fetchall()
    else:
        ids = [str(i) for i in (b.get("players") or [])][:100]
        rows = [r for i in ids for r in db.execute("SELECT * FROM players WHERE id=? AND campaign_id=?", (i, m["campaignId"])).fetchall()]
    out = []
    for row in rows:
        p = row_to_player(row)
        apply_reveal(p, map_id, m, action, cells)
        save_player(p)
        out.append(p)
    db.commit()
    return jsonify({"players": out, "version": campaign_version(m["campaignId"], map_id)})


@app.route("/api/maps/<map_id>/door", methods=["POST"])
@gamemaster_required
def gamemaster_toggle_door(map_id):
    get_db().execute("BEGIN IMMEDIATE")
    m = fetch_map(map_id)
    b = body()
    c, r, e = clamp_int(b.get("c"), 0, 999, -1), clamp_int(b.get("r"), 0, 999, -1), clamp_int(b.get("edge"), 0, 5, -1)
    door = geo.door_on_edge(m["gridType"], m["data"]["cells"], c, r, e)
    if not door:
        get_db().rollback()
        return err("No door on that edge.", 404)
    if "locked" in b:
        if b["locked"]:
            door["locked"] = True
            door["open"] = False
        else:
            door.pop("locked", None)
    elif "open" in b:
        door["open"] = bool(b["open"])
    else:
        door["open"] = not door.get("open")
    if door.get("locked") and door.get("open"):
        door["open"] = False
    save_map_data(map_id, m["data"])
    get_db().commit()
    return jsonify({"open": door["open"], "locked": bool(door.get("locked")), "version": campaign_version(m["campaignId"], map_id)})


@app.route("/api/maps/<map_id>/marker", methods=["POST"])
@gamemaster_required
def gamemaster_update_marker(map_id):
    """In-place marker update used in Play mode: move it, set label/visibility, condition monitor, damage,
    NPC template or stat block."""
    get_db().execute("BEGIN IMMEDIATE")
    m = fetch_map(map_id)
    b = body()
    mk = next((x for x in m["data"]["markers"] if x["id"] == str(b.get("id"))), None)
    if not mk:
        get_db().rollback()
        return err("Marker not found.", 404)
    if b.get("template"):
        dmg = 0
        try:
            if str(b["template"]).startswith("pv:"):
                npc, dmg = runner_vehicle_npc(str(b["template"]))
            else:
                npc = X.npc_from_key(b["template"], clamp_int(b.get("force"), 1, 12, 3))
        except R.RuleError as e:
            get_db().rollback()
            return err(str(e))
        mk["npc"] = X.clean_npc(npc)
        mk["cm"] = clean_cm(X.npc_cm(npc))
        if dmg:
            mk["cm"]["p"] = min(mk["cm"]["pm"], dmg)
        if not mk.get("label") or b.get("relabel"):
            mk["label"] = (npc.get("template") or "Enemy")[:80]
    if "npc" in b:
        npc = X.clean_npc(b["npc"])
        if npc:
            mk["npc"] = npc
        else:
            mk.pop("npc", None)
    if "c" in b and "r" in b:
        c, r = clamp_int(b["c"], 0, 999, -1), clamp_int(b["r"], 0, 999, -1)
        if not geo.in_bounds(m, c, r):
            return err("Out of bounds.")
        mk["c"], mk["r"] = c, r
    if "label" in b:
        mk["label"] = str(b["label"])[:80]
    if "hidden" in b:
        if b["hidden"]:
            mk["hidden"] = True
        else:
            mk.pop("hidden", None)
    if "cm" in b:
        cm = clean_cm(b["cm"])
        if cm:
            mk["cm"] = cm
        else:
            mk.pop("cm", None)
    if "statuses" in b:
        st = fight.clean_statuses(b["statuses"])
        if st:
            mk["statuses"] = st
        else:
            mk.pop("statuses", None)
    if "damage" in b and mk.get("cm"):
        d = b["damage"] if isinstance(b["damage"], dict) else {}
        if d.get("track") in ("physical", "stun"):
            cm_damage(mk["cm"], d["track"], clamp_int(d.get("amount"), -99, 99, 0))
    if (mk.get("npc") or {}).get("link") and ("damage" in b or "cm" in b):
        cache = {}
        fight.sync_vehicle(get_db(), mk, cache)
        for pid, (_row, c) in cache.items():
            save_char(pid, c)
    save_map_data(map_id, m["data"])
    get_db().commit()
    return jsonify({"marker": mk, "version": campaign_version(m["campaignId"], map_id)})


@app.route("/api/maps/<map_id>/return-link", methods=["POST"])
@gamemaster_required
def create_return_link(map_id):
    target = fetch_map(map_id)
    b = body()
    c, r = clamp_int(b.get("c"), 0, 999, -1), clamp_int(b.get("r"), 0, 999, -1)
    if not geo.in_bounds(target, c, r):
        return err("Arrival cell is outside the destination map.")
    if any(mk["c"] == c and mk["r"] == r for mk in target["data"]["markers"]):
        return err("The arrival cell already has a marker.", 409)
    lid = re.sub(r"[^A-Za-z0-9_-]", "", str(b.get("linkId") or ""))[:24] or new_id(8)
    target["data"]["markers"].append({"id": new_id(8), "c": c, "r": r, "type": str(b.get("type") or "link")[:24], "linkId": lid,
                                      "color": clean_color(b.get("color"), "#ff2f7d"), "label": str(b.get("label") or "")[:80],
                                      "target": {"mapId": str(b.get("fromMapId") or "")[:16], "c": clamp_int(b.get("fromC"), 0, 999, 0),
                                                 "r": clamp_int(b.get("fromR"), 0, 999, 0)}})
    save_map_data(map_id, target["data"])
    get_db().commit()
    return jsonify({"ok": True})


# ====================================================================== gamemaster api: tokens
@app.route("/api/players/<pid>", methods=["PUT"])
@gamemaster_required
def update_player(pid):
    p = locked_player(pid)
    b = body()
    if "color" in b:
        p["color"] = clean_color(b["color"], p["color"])
    if "radius" in b:
        p["radius"] = clamp_int(b["radius"], 0, 20, p["radius"])
    if "currentMapId" in b:
        p["currentMapId"] = b["currentMapId"] or None
    if "state" in b and isinstance(b["state"], dict):
        maps = {}
        for mid, ms in (b["state"].get("maps") or {}).items():
            if not isinstance(ms, dict):
                continue
            tok = ms.get("token")
            maps[str(mid)[:16]] = {
                "explored": {str(k)[:16]: True for k, v in (ms.get("explored") or {}).items() if v},
                "token": {"c": int(tok["c"]), "r": int(tok["r"])} if isinstance(tok, dict) else None,
                "mapStation": bool(ms.get("mapStation")),
            }
        p["state"] = {"maps": maps}
    save_player(p)
    get_db().commit()
    return jsonify(fetch_player(pid))


@app.route("/api/players/<pid>/place", methods=["POST"])
@gamemaster_required
def gamemaster_place_player(pid):
    b = body()
    m = fetch_map(str(b.get("mapId") or ""))
    p = locked_player(pid)
    c, r = clamp_int(b.get("c"), 0, 999, -1), clamp_int(b.get("r"), 0, 999, -1)
    if not geo.in_bounds(m, c, r):
        return err("Out of bounds.")
    place_player(p, m, c, r)
    save_player(p)
    get_db().commit()
    return jsonify(fetch_player(pid))


@app.route("/api/players/<pid>/unplace", methods=["POST"])
@gamemaster_required
def gamemaster_unplace_player(pid):
    """Take a token off its current map (it keeps what it explored)."""
    p = locked_player(pid)
    if p["currentMapId"]:
        player_map_state(p, p["currentMapId"])["token"] = None
    p["currentMapId"] = None
    save_player(p)
    get_db().commit()
    return jsonify(fetch_player(pid))


# ====================================================================== gamemaster api: snapshots
def campaign_state(cid):
    db = get_db()
    players = {r["id"]: {"currentMapId": r["current_map_id"], "state": json.loads(r["state"])}
               for r in db.execute("SELECT * FROM players WHERE campaign_id=?", (cid,)).fetchall()}
    doors = {}
    for r in db.execute("SELECT id, data FROM maps WHERE campaign_id=?", (cid,)).fetchall():
        d = {}
        for k, cell in (json.loads(r["data"]).get("cells") or {}).items():
            for e, door in (cell.get("doors") or {}).items():
                if door.get("open"):
                    d.setdefault(k, []).append(e)
        doors[r["id"]] = d
    return {"players": players, "doors": doors}


@app.route("/api/campaigns/<cid>/snapshots", methods=["POST"])
@gamemaster_required
def create_snapshot(cid):
    b = body()
    sid = new_id()
    get_db().execute("INSERT INTO snapshots (id,campaign_id,name,state,created_at) VALUES (?,?,?,?,?)",
                     (sid, cid, str(b.get("name") or "Snapshot").strip()[:80], json.dumps(campaign_state(cid)), now()))
    get_db().commit()
    return jsonify({"id": sid}), 201


@app.route("/api/snapshots/<sid>/restore", methods=["POST"])
@gamemaster_required
def restore_snapshot(sid):
    db = get_db()
    row = db.execute("SELECT * FROM snapshots WHERE id=?", (sid,)).fetchone()
    if not row:
        abort(404)
    st = json.loads(row["state"])
    for pid, ps in st.get("players", {}).items():
        db.execute("UPDATE players SET current_map_id=?, state=?, updated_at=? WHERE id=? AND campaign_id=?",
                   (ps.get("currentMapId"), json.dumps(ps.get("state") or {"maps": {}}), now(), pid, row["campaign_id"]))
    for mid, open_doors in st.get("doors", {}).items():
        mrow = db.execute("SELECT data FROM maps WHERE id=?", (mid,)).fetchone()
        if not mrow:
            continue
        data = json.loads(mrow["data"])
        for k, cell in (data.get("cells") or {}).items():
            for e, door in (cell.get("doors") or {}).items():
                door["open"] = e in (open_doors.get(k) or [])
        save_map_data(mid, data)
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/snapshots/<sid>", methods=["DELETE"])
@gamemaster_required
def delete_snapshot(sid):
    get_db().execute("DELETE FROM snapshots WHERE id=?", (sid,))
    get_db().commit()
    return jsonify({"ok": True})


@app.route("/api/defaults")
@gamemaster_required
def defaults():
    return jsonify(DEFAULT_SETTINGS)


# ====================================================================== player map view
def player_view(me_row):
    """Filter the player's current map down to what they are allowed to see."""
    p = row_to_player(me_row)
    out = {"map": None, "others": [], "pings": [], "canTravel": None, "doorsHere": [],
           "token": None, "now": now(), "tracker": fight.player_tracker(p["campaignId"]), "statuses": p.get("statuses") or {}}
    if not p["currentMapId"]:
        return out
    row = get_db().execute("SELECT * FROM maps WHERE id=?", (p["currentMapId"],)).fetchone()
    if not row:
        return out
    m = row_to_map(row)
    ms = player_map_state(p, m["id"])
    explored = ms.get("explored") or {}
    station = bool(ms.get("mapStation"))
    cells = {}
    all_cells = m["data"]["cells"]
    for k, cell in all_cells.items():
        if explored.get(k):
            vis = "full"
        elif station and not cell.get("secret"):
            vis = "dim"
        else:
            continue
        cells[k] = {"fill": cell.get("fill"), "border": cell.get("border"), "borderOn": cell.get("borderOn", True),
                    "doors": dict(cell.get("doors") or {}), "vis": vis}
    # doors stored on a hidden neighbour but facing a visible cell: mirror them onto the visible cell
    for k in list(cells.keys()):
        c, r = (int(x) for x in k.split(","))
        for e in range(geo.edge_count(m["gridType"])):
            if str(e) in cells[k]["doors"]:
                continue
            nc, nr = geo.neighbor(m["gridType"], c, r, e)
            nk = f"{nc},{nr}"
            if nk in cells:
                continue
            d = ((all_cells.get(nk) or {}).get("doors") or {}).get(str(geo.opposite_edge(m["gridType"], e)))
            if d:
                cells[k]["doors"][str(e)] = dict(d)
    markers = []
    for mk in m["data"]["markers"]:
        k = f"{mk['c']},{mk['r']}"
        if explored.get(k) and not mk.get("hidden"):
            o = {k2: mk.get(k2) for k2 in ("id", "c", "r", "type", "color", "label", "cm", "statuses")}
            if is_link(mk):
                o["isLink"] = True
                trow, _, _ = resolve_link(mk, m)
                o["targetName"] = trow["name"] if trow else None
            markers.append(o)
    for r2 in get_db().execute("SELECT * FROM players WHERE campaign_id=? AND current_map_id=? AND id<>?",
                              (p["campaignId"], m["id"], p["id"])).fetchall():
        st = json.loads(r2["state"]).get("maps", {}).get(m["id"]) or {}
        tok = st.get("token")
        c2 = load_char(r2)
        if tok and explored.get(f"{tok['c']},{tok['r']}"):
            out["others"].append({"id": r2["id"], "name": display_name(r2, c2), "color": r2["color"], "c": tok["c"], "r": tok["r"],
                                  "cm": R.condition_summary(c2), "statuses": c2.get("statuses") or {}})
        ping = json.loads(r2["ping"]) if r2["ping"] else None
        if ping and ping.get("mapId") == m["id"] and now() - ping.get("t", 0) < 10:
            out["pings"].append({"name": display_name(r2, c2), "color": r2["color"], "c": ping["c"], "r": ping["r"], "t": ping["t"]})
    own = p.get("ping")
    if own and own.get("mapId") == m["id"] and now() - own.get("t", 0) < 10:
        out["pings"].append({"name": p["name"], "color": p["color"], "c": own["c"], "r": own["r"], "t": own["t"]})
    token = ms.get("token")
    if token:
        lk = link_at(m, token["c"], token["r"])
        if lk:
            trow, _, _ = resolve_link(lk, m)
            if trow:
                out["canTravel"] = {"markerId": lk["id"], "mapName": trow["name"]}
        for e in range(geo.edge_count(m["gridType"])):
            d = geo.door_on_edge(m["gridType"], m["data"]["cells"], token["c"], token["r"], e)
            if d:
                out["doorsHere"].append({"edge": e, "open": bool(d.get("open")), "locked": bool(d.get("locked")), "color": d.get("color")})
    out["token"] = token
    out["map"] = {"id": m["id"], "name": m["name"], "gridType": m["gridType"], "width": m["width"],
                  "height": m["height"], "cellSize": m["cellSize"],
                  "settings": {"colors": m["settings"]["colors"], "showGrid": m["settings"]["showGrid"], "legendVisible": m["settings"]["legendVisible"]},
                  "cells": cells, "markers": markers, "mapStation": station}
    return out


def _me_fresh(me):
    return get_db().execute("SELECT * FROM players WHERE id=?", (me["id"],)).fetchone()


@app.route("/api/me/move", methods=["POST"])
@player_required
@rate_limited("player_move", 90)
def player_move(me):
    p = locked_player(me["id"])
    if not p["currentMapId"]:
        return err("The GM has not placed you on a map yet.")
    m = fetch_map(p["currentMapId"])
    ms = player_map_state(p, m["id"])
    if not ms.get("token"):
        return err("The GM has not placed your token yet.")
    b = body()
    c, r = clamp_int(b.get("c"), 0, 999, -1), clamp_int(b.get("r"), 0, 999, -1)
    cur = (ms["token"]["c"], ms["token"]["r"])
    path = geo.find_path(m, m["data"]["cells"], cur, (c, r), explored=ms.get("explored"))
    if path is None:
        return err("There is no open way to get there.")
    place_player(p, m, c, r, path)
    link = link_at(m, c, r)
    if link:
        travel_player(p, m, link)
    save_player(p)
    get_db().commit()
    return jsonify(player_view(_me_fresh(me)))


@app.route("/api/me/door", methods=["POST"])
@player_required
@rate_limited("player_door", 60)
def player_door(me):
    p = locked_player(me["id"])
    if not p["currentMapId"]:
        abort(400)
    m = fetch_map(p["currentMapId"])
    ms = player_map_state(p, m["id"])
    tok = ms.get("token")
    if not tok:
        abort(400)
    e = clamp_int(body().get("edge"), 0, 5, -1)
    door = geo.door_on_edge(m["gridType"], m["data"]["cells"], tok["c"], tok["r"], e)
    if not door:
        return err("No door there.")
    if door.get("locked"):
        return err("That door is locked.")
    door["open"] = not door.get("open")
    save_map_data(m["id"], m["data"])
    if door["open"]:
        place_player(p, m, tok["c"], tok["r"])
        save_player(p)
    get_db().commit()
    return jsonify(player_view(_me_fresh(me)))


@app.route("/api/me/ping", methods=["POST"])
@player_required
@rate_limited("player_ping", 30)
def player_ping(me):
    if not me["current_map_id"]:
        abort(400)
    b = body()
    c, r = clamp_int(b.get("c"), 0, 999, -1), clamp_int(b.get("r"), 0, 999, -1)
    m = fetch_map(me["current_map_id"])
    if not geo.in_bounds(m, c, r):
        abort(400)
    get_db().execute("UPDATE players SET ping=?, updated_at=? WHERE id=?",
                     (json.dumps({"mapId": m["id"], "c": c, "r": r, "t": now()}), now(), me["id"]))
    get_db().commit()
    return jsonify({"ok": True})


@app.route("/api/me/travel", methods=["POST"])
@player_required
@rate_limited("player_travel", 30)
def player_travel(me):
    p = locked_player(me["id"])
    if not p["currentMapId"]:
        abort(400)
    m = fetch_map(p["currentMapId"])
    tok = player_map_state(p, m["id"]).get("token")
    if not tok:
        abort(400)
    link = link_at(m, tok["c"], tok["r"])
    if not link:
        return err("There is no exit here.")
    if not travel_player(p, m, link):
        return err("That exit leads nowhere yet.")
    save_player(p)
    get_db().commit()
    return jsonify(player_view(_me_fresh(me)))

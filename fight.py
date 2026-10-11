"""GM combat tools on the map: initiative tracker, GM-rolled attacks (attack ->
defense -> soak -> monitor), status effects and NPC templates for markers."""
import json
import secrets

from flask import jsonify, request

from core import (GM_COLOR, add_roll, app, body, clamp_int, display_name, err, get_db, load_char, now,
                  roll_rows, save_char)
from security import admin_required
from sr import combat as X
from sr import core6e as K
from sr import gear6e as G
from sr import rules as R

_rng = secrets.SystemRandom()


# ====================================================================== initiative tracker
def load_tracker(cid):
    row = get_db().execute("SELECT combat FROM campaigns WHERE id=?", (cid,)).fetchone()
    try:
        t = json.loads(row["combat"] or "{}") if row else {}
    except ValueError:
        t = {}
    t.setdefault("active", False)
    t.setdefault("visible", False)
    t.setdefault("round", 1)
    t.setdefault("turn", 0)
    t.setdefault("entries", [])
    return t


def save_tracker(cid, t):
    get_db().execute("UPDATE campaigns SET combat=?, updated_at=? WHERE id=?", (json.dumps(t), now(), cid))


def ordered(t):
    def key(e):
        tot = e.get("total")
        return (0 if tot is not None else 1, -(tot or 0), -(e.get("edge") or 0), -(e.get("rea") or 0),
                -(e.get("int") or 0), e.get("tie", 0))
    return sorted(t["entries"], key=key)


def tracker_view(t, gm):
    order = ordered(t)
    turn = max(0, min(len(order) - 1, t.get("turn", 0))) if order else 0
    current = order[turn]["id"] if order else None
    entries = []
    for e in order:
        if not gm and e.get("hidden"):
            continue
        o = {k: e.get(k) for k in ("id", "kind", "ref", "mapId", "name", "total", "dice", "color", "minor", "hidden")}
        o["current"] = e["id"] == current
        entries.append(o)
    shown = {e["id"] for e in entries}
    return {"active": t["active"], "visible": t["visible"], "round": t["round"], "entries": entries,
            "current": current if current in shown else None}


def player_tracker(cid):
    t = load_tracker(cid)
    if not (t["active"] and t["visible"]):
        return None
    return tracker_view(t, False)


def _new_entry(kind, ref, name, color, map_id=None, **kw):
    e = {"id": secrets.token_hex(4), "kind": kind, "ref": ref, "name": name[:60], "color": color, "mapId": map_id,
         "total": None, "dice": [], "hidden": False, "tie": _rng.random()}
    e.update(kw)
    return e


def _player_entry(row):
    c = load_char(row)
    d = R.derive(c)
    return _new_entry("player", row["id"], display_name(row, c), row["color"], row["current_map_id"],
                      score=d["initiative_score"], initDice=d["initiative_dice"], minor=d["minor_actions"],
                      edge=c["current_edge"], rea=d["attributes"]["Reaction"], int=d["attributes"]["Intuition"])


def _marker_entry(map_id, mk):
    npc = mk.get("npc") or {}
    attrs = npc.get("attrs") or {}
    dice = npc.get("init_dice") or 1
    return _new_entry("marker", mk["id"], mk.get("label") or npc.get("template") or "Enemy", mk.get("color") or "#ff2f7d", map_id,
                      score=npc.get("init") or (attrs.get("Reaction", 0) + attrs.get("Intuition", 0)) or 0, initDice=dice,
                      minor=min(R.MAX_MINOR, 1 + dice), edge=npc.get("edge") or 0, rea=attrs.get("Reaction", 0),
                      int=attrs.get("Intuition", 0), hidden=bool(mk.get("hidden")), grunt=bool(npc.get("grunt")))


def _roll_entry(e):
    if e.get("grunt") and e.get("fixed"):
        e["dice"], e["total"] = [], e.get("score", 0)
        return
    dice = [_rng.randint(1, 6) for _ in range(max(1, min(5, e.get("initDice") or 1)))]
    e["dice"] = dice
    e["total"] = (e.get("score") or 0) + sum(dice)


def tracker_set_player(cid, pid, total, d):
    """Called when a player rolls initiative: update (or join) the active tracker."""
    t = load_tracker(cid)
    if not t["active"]:
        return
    e = next((x for x in t["entries"] if x["kind"] == "player" and x["ref"] == pid), None)
    if not e:
        row = get_db().execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
        if not row:
            return
        e = _player_entry(row)
        t["entries"].append(e)
    e["total"] = total
    e["minor"] = d["minor_actions"]
    save_tracker(cid, t)


def _markers(map_id):
    row = get_db().execute("SELECT data FROM maps WHERE id=?", (map_id,)).fetchone()
    return json.loads(row["data"]).get("markers", []) if row else []


@app.route("/api/games/<cid>/combat")
@admin_required
def combat_get(cid):
    return jsonify({"tracker": tracker_view(load_tracker(cid), True)})


@app.route("/api/games/<cid>/combat", methods=["POST"])
@admin_required
def combat_op(cid):
    """Initiative tracker operations (see ``op``)."""
    b = body()
    op = str(b.get("op") or "")
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        t = load_tracker(cid)
        msg = ""
        if op == "start":
            t = {"active": True, "visible": bool(b.get("visible")), "round": 1, "turn": 0, "entries": []}
            op = "add"
        if op == "add":
            for pid in b.get("players") or []:
                row = db.execute("SELECT * FROM players WHERE id=? AND campaign_id=?", (str(pid), cid)).fetchone()
                if row and not any(e["kind"] == "player" and e["ref"] == row["id"] for e in t["entries"]):
                    t["entries"].append(_player_entry(row))
            map_id = str(b.get("mapId") or "")
            if map_id:
                for mk in _markers(map_id):
                    if mk["id"] in (b.get("markers") or []) and not any(e["kind"] == "marker" and e["ref"] == mk["id"] for e in t["entries"]):
                        t["entries"].append(_marker_entry(map_id, mk))
            if isinstance(b.get("custom"), dict):
                cu = b["custom"]
                t["entries"].append(_new_entry("custom", None, str(cu.get("name") or "Combatant"), "#9fb3b0",
                                               score=clamp_int(cu.get("score"), 0, 60, 0), initDice=clamp_int(cu.get("dice"), 1, 5, 1),
                                               minor=min(R.MAX_MINOR, 1 + clamp_int(cu.get("dice"), 1, 5, 1)),
                                               hidden=bool(cu.get("hidden"))))
            t["active"] = True
            if b.get("roll"):
                for e in t["entries"]:
                    if e["kind"] != "player" and e.get("total") is None:
                        _roll_entry(e)
        elif op == "end":
            t["active"] = False
            t["visible"] = False
            msg = "Combat ended."
        elif op in ("show", "hide"):
            t["visible"] = op == "show"
        elif op == "roll":
            for e in t["entries"]:
                if (b.get("id") and e["id"] == b["id"]) or (not b.get("id") and e["kind"] != "player" and (b.get("all") or e.get("total") is None)):
                    if e["kind"] == "player":
                        row = db.execute("SELECT * FROM players WHERE id=?", (e["ref"],)).fetchone()
                        if row:
                            d = R.derive(load_char(row))
                            e["score"], e["initDice"] = d["initiative_score"], d["initiative_dice"]
                    _roll_entry(e)
        elif op == "set":
            e = next((x for x in t["entries"] if x["id"] == b.get("id")), None)
            if not e:
                return _fail(db, "Not in the tracker.")
            if "total" in b:
                e["total"] = None if b["total"] in (None, "") else clamp_int(b["total"], -20, 99, 0)
                e["dice"] = []
            if "hidden" in b:
                e["hidden"] = bool(b["hidden"])
            if "name" in b:
                e["name"] = str(b["name"])[:60] or e["name"]
        elif op == "remove":
            t["entries"] = [x for x in t["entries"] if x["id"] != b.get("id")]
        elif op in ("next", "prev"):
            n = len(t["entries"])
            if n:
                t["turn"] = t.get("turn", 0) + (1 if op == "next" else -1)
                if t["turn"] >= n:
                    t["turn"] = 0
                    t["round"] += 1
                elif t["turn"] < 0:
                    t["turn"] = n - 1
                    t["round"] = max(1, t["round"] - 1)
        elif op == "round":
            t["turn"] = 0
            t["round"] += 1
        elif op == "turn":
            order = ordered(t)
            idx = next((i for i, e in enumerate(order) if e["id"] == b.get("id")), None)
            if idx is not None:
                t["turn"] = idx
        else:
            return _fail(db, "Unknown tracker operation.")
        save_tracker(cid, t)
        if op == "end":
            add_roll(cid, None, "GM", GM_COLOR, "note", {"text": "ended the combat."})
        elif op == "add" and b.get("op") == "start":
            add_roll(cid, None, "GM", GM_COLOR, "note", {"text": "started a combat. Roll initiative!"}, hidden=not t["visible"])
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return jsonify({"tracker": tracker_view(t, True), "message": msg})


def _fail(db, msg):
    db.rollback()
    return err(msg)


# ====================================================================== attacks
def _fighter(db, cid, map_data, ref, cache):
    """-> (Fighter, saver) for {"kind": "player"|"marker", "id": ...}."""
    kind, rid = (ref or {}).get("kind"), str((ref or {}).get("id") or "")
    if kind == "player":
        if rid not in cache:
            row = db.execute("SELECT * FROM players WHERE id=? AND campaign_id=?", (rid, cid)).fetchone()
            if not row:
                raise R.RuleError("That runner isn't in this game.")
            cache[rid] = (row, load_char(row))
        row, c = cache[rid]
        return X.Fighter.from_char(display_name(row, c), c), ("player", rid)
    if kind == "marker":
        mk = next((m for m in map_data.get("markers", []) if m["id"] == rid), None)
        if not mk:
            raise R.RuleError("That marker is gone.")
        if not mk.get("cm"):
            mk["cm"] = {"pm": 10, "sm": 10, "ov": 0, "p": 0, "s": 0}
        return X.Fighter.from_marker(mk), ("marker", mk)
    raise R.RuleError("Pick the attacker and the target.")


@app.route("/api/maps/<map_id>/attack", methods=["POST"])
@admin_required
def gm_attack(map_id):
    """The GM resolves an attack between two combatants on this map, rolling every test."""
    b = body()
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        mrow = db.execute("SELECT * FROM maps WHERE id=?", (map_id,)).fetchone()
        if not mrow:
            return _fail(db, "Map not found.")
        cid = mrow["campaign_id"]
        data = json.loads(mrow["data"])
        cache = {}
        att, att_ref = _fighter(db, cid, data, b.get("attacker"), cache)
        tgt, tgt_ref = _fighter(db, cid, data, b.get("target"), cache)
        if att_ref == tgt_ref:
            return _fail(db, "Pick a different target.")
        mode = b.get("mode") if b.get("mode") in G.FIRING_MODES else None
        rng = b.get("range") if b.get("range") in G.RANGES else "Near"
        notes = []
        if att_ref[0] == "player":
            weapon = X.char_weapon_profile(att, str(b.get("weapon") or ""), mode, rng, clamp_int(b.get("amp"), 0, 10, 0))
            if weapon.get("uid") not in (None, "unarmed") and not weapon.get("spell"):
                note = R.consume_attack(att.char, weapon["uid"], weapon.get("mode"))
                if note:
                    notes.append(note)
        else:
            npc = att.npc or {}
            wl = npc.get("weapons") or []
            i = clamp_int(b.get("weapon"), -1, len(wl) - 1, -1)
            if i < 0:
                ua = att.attrs.get("Strength", 1)
                w = {"name": "Unarmed", "skill": "Close Combat", "dv": (ua + 1) // 2, "type": "S",
                     "ar": [att.attrs.get("Reaction", 1) + ua, None, None, None, None], "modes": []}
            else:
                w = wl[i]
            weapon = X.npc_weapon_profile(att, w, mode)
            if b.get("dice") not in (None, ""):
                weapon["parts"] = [["Dice", clamp_int(b.get("dice"), 0, 60, 0)]]
        opts = {"range": rng, "attack_mod": b.get("attackMod"), "defense_mod": b.get("defenseMod"),
                "soak_mod": b.get("soakMod"), "wild": b.get("wild"), "extra_dv": b.get("extraDv"),
                "unopposed": bool(b.get("unopposed"))}
        res = X.resolve_attack(att, weapon, tgt, opts)
        res["notes"] = notes
        if weapon.get("spell") and att_ref[0] == "player":
            dr = R.resist_drain(att.char, R.derive(att.char), weapon.get("drain", 0), "drain")
            res["drain"] = dr
            notes.append(f"drain {dr['dv']}: {dr['text']}")
        apply = b.get("apply", True)
        if apply and res.get("damage"):
            if tgt_ref[0] == "player":
                c = cache[tgt_ref[1]][1]
                R.take_damage(c, res["track"], res["damage"])
                for name, val in res.get("effects") or []:
                    c.setdefault("statuses", {})[name] = val if val else True
            else:
                mk = tgt_ref[1]
                X.marker_damage(mk["cm"], res["track"], res["damage"])
                for name, val in res.get("effects") or []:
                    mk.setdefault("statuses", {})[name] = val if val else True
                res["targetStatus"] = X.marker_status(mk["cm"], mk.get("npc"))
        res["applied"] = bool(apply)
        for pid, (row, c) in cache.items():
            R.clamp_state(c)
            save_char(pid, c)
        db.execute("UPDATE maps SET data=?, updated_at=? WHERE id=?", (json.dumps(data), now(), map_id))
        if cid:
            add_roll(cid, None, "GM", GM_COLOR, "attack", res, hidden=bool(b.get("hidden")))
        db.commit()
    except R.RuleError as e:
        db.rollback()
        return err(str(e))
    except BaseException:
        db.rollback()
        raise
    return jsonify({"result": res, "rolls": roll_rows(cid, admin=True) if cid else []})


@app.route("/api/maps/<map_id>/attack-options", methods=["POST"])
@admin_required
def gm_attack_options(map_id):
    """What a combatant can attack with (for the GM's attack dialog)."""
    b = body()
    db = get_db()
    mrow = db.execute("SELECT * FROM maps WHERE id=?", (map_id,)).fetchone()
    if not mrow:
        return err("Map not found.", 404)
    data = json.loads(mrow["data"])
    try:
        f, ref = _fighter(db, mrow["campaign_id"], data, b.get("who"), {})
    except R.RuleError as e:
        return err(str(e))
    out = []
    if ref[0] == "player":
        c, d = f.char, f.d
        for it in R.weapon_items(c):
            p = R.weapon_profile(c, d, it, "")
            if p:
                out.append({"key": f"weapon:{it['uid']}", "name": it["name"], "pool": sum(x[1] for x in p["parts"]),
                            "dv": f"{p['dv']}{p['type']}", "ar": p["ar"], "modes": p["modes"], "loaded": p["loaded"], "clip": p["clip"],
                            "qty": R._int(it.get("qty"), 1) if p["consumable"] else None})
        u = R.unarmed_profile(c, d)
        out.append({"key": "weapon:unarmed", "name": "Unarmed", "pool": sum(x[1] for x in u["parts"]), "dv": f"{u['dv']}{u['type']}",
                    "ar": u["ar"], "modes": []})
        if c.get("magic_type") in R.CASTERS:
            for i, sp in enumerate(c.get("spells") or []):
                if sp.get("category") == "Combat":
                    p = R.spell_profile(c, d, sp)
                    if p:
                        out.append({"key": f"spell:{i}", "name": f"{sp['name']} (spell)", "pool": sum(x[1] for x in p["parts"]),
                                    "dv": ("net hits" if p["direct"] else f"{p['dv']}+net") + p["type"], "ar": p["ar"], "modes": [],
                                    "spell": True, "drain": p["drain"]})
    else:
        for i, w in enumerate((f.npc or {}).get("weapons") or []):
            p = X.npc_weapon_profile(f, w)
            out.append({"key": str(i), "name": w["name"], "pool": sum(x[1] for x in p["parts"]), "dv": f"{w['dv']}{w['type']}",
                        "ar": w["ar"], "modes": w.get("modes") or [], "grenade": w.get("grenade")})
        ua = f.attrs.get("Strength", 1)
        out.append({"key": "-1", "name": "Unarmed", "pool": f.attrs.get("Agility", 1) + R._int((f.skills or {}).get("Close Combat")),
                    "dv": f"{(ua + 1) // 2}S", "ar": [f.attrs.get("Reaction", 1) + ua, None, None, None, None], "modes": []})
    return jsonify({"options": out, "dr": f.dr, "name": f.name})


# ====================================================================== statuses
@app.route("/api/maps/<map_id>/status", methods=["POST"])
@admin_required
def gm_status(map_id):
    """Tick or clear a status on a runner or a marker (GM only)."""
    b = body()
    name = b.get("status")
    if name not in K.STATUSES:
        return err("Unknown status.")
    on = bool(b.get("on"))
    meta = K.STATUSES[name]
    val = clamp_int(b.get("value"), 1, 20, 1) if (meta.get("value") or meta.get("levels")) else True
    tgt = b.get("target") or {}
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        if tgt.get("kind") == "player":
            row = db.execute("SELECT * FROM players WHERE id=?", (str(tgt.get("id")),)).fetchone()
            if not row:
                return _fail(db, "Runner not found.")
            c = load_char(row)
            st = c.setdefault("statuses", {})
            if on:
                st[name] = val
            else:
                st.pop(name, None)
            save_char(row["id"], c)
            out = st
        else:
            mrow = db.execute("SELECT * FROM maps WHERE id=?", (map_id,)).fetchone()
            if not mrow:
                return _fail(db, "Map not found.")
            data = json.loads(mrow["data"])
            mk = next((m for m in data.get("markers", []) if m["id"] == str(tgt.get("id"))), None)
            if not mk:
                return _fail(db, "Marker not found.")
            st = mk.setdefault("statuses", {})
            if on:
                st[name] = val
            else:
                st.pop(name, None)
            if not st:
                mk.pop("statuses", None)
            db.execute("UPDATE maps SET data=?, updated_at=? WHERE id=?", (json.dumps(data), now(), map_id))
            out = st
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return jsonify({"statuses": out})


@app.route("/api/npc-templates/<path:key>")
@admin_required
def npc_template(key):
    try:
        npc = X.npc_from_key(key, clamp_int(request.args.get("force"), 1, 12, 3))
    except R.RuleError as e:
        return err(str(e))
    return jsonify({"npc": npc, "cm": X.npc_cm(npc)})


def clean_statuses(v):
    if not isinstance(v, dict):
        return None
    out = {}
    for k, val in v.items():
        if k in K.STATUSES:
            out[k] = True if val is True else clamp_int(val, 1, 20, 1)
    return out or None


__all__ = ["player_tracker", "tracker_set_player", "clean_statuses", "roll_rows"]

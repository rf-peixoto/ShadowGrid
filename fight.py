"""GM combat tools on the map: initiative tracker, GM-rolled attacks (attack ->
defense -> soak -> monitor), status effects and NPC templates for markers."""
import json
import secrets

from flask import jsonify, request

import geometry as geo

from core import (GM_COLOR, add_roll, app, body, clamp_int, display_name, err, get_db, load_char, now,
                  roll_rows, save_char)
from security import gamemaster_required
from sr import actions6e as ACT
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
    for e in t["entries"]:
        e.setdefault("used", {"major": 0, "minor": 0})
        e.setdefault("fd", False)
        e.setdefault("dirt", False)
        e.setdefault("edgeGained", 0)
    return t


# ---------------------------------------------------------------- actions per round
def actions_left(e):
    minor = max(1, min(ACT.MAX_MINOR, e.get("minor") or 1))
    u = e.get("used") or {}
    return 1 - _clamp0(u.get("major")), minor - _clamp0(u.get("minor"))


def _clamp0(v):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def spend_action(e, cost, what, force=False):
    """Use a Major or Minor Action from a tracker entry. Four Minor can stand in for a Major,
    and a spare Major can be used for a Minor. Returns a note, or raises RuleError."""
    if e is None:
        return ""
    u = e.setdefault("used", {"major": 0, "minor": 0})
    major, minor = actions_left(e)
    if cost == "major":
        if major > 0:
            u["major"] = _clamp0(u.get("major")) + 1
            return ""
        if minor >= ACT.MINOR_PER_MAJOR:
            u["minor"] = _clamp0(u.get("minor")) + ACT.MINOR_PER_MAJOR
            return f"{e['name']} trades {ACT.MINOR_PER_MAJOR} Minor Actions for {what}"
    else:
        if minor > 0:
            u["minor"] = _clamp0(u.get("minor")) + 1
            return ""
        if major > 0:
            u["major"] = _clamp0(u.get("major")) + 1
            return f"{e['name']} uses their Major Action for {what}"
    if force:
        u[cost] = _clamp0(u.get(cost)) + 1
        return f"{e['name']} had no {cost.capitalize()} Action left for {what} (GM allowed it)"
    raise R.RuleError(f"{e['name']} has no {cost.capitalize()} Action left this round for {what}.")


def new_round(t):
    t["round"] += 1
    for e in t["entries"]:
        e["used"] = {"major": 0, "minor": 0}
        e["fd"] = False
        e["edgeGained"] = 0


def entry_for(t, kind, ref):
    if not t.get("active"):
        return None
    return next((e for e in t["entries"] if e.get("kind") == kind and e.get("ref") == ref), None)


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
        o = {k: e.get(k) for k in ("id", "kind", "ref", "mapId", "name", "total", "dice", "color", "minor", "hidden", "used", "fd", "dirt", "edgeGained")}
        o["current"] = e["id"] == current
        o["majorLeft"], o["minorLeft"] = actions_left(e)
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


def _roll_entry(e, statuses=None):
    pen = sum(v for _, v in X.status_parts(X.Fighter(e.get("name"), {}, 0, 0, statuses=statuses or {}), "init"))
    if e.get("grunt") and e.get("fixed"):
        e["dice"], e["total"] = [], e.get("score", 0) + pen
        return
    dice = [_rng.randint(1, 6) for _ in range(max(1, min(5, e.get("initDice") or 1)))]
    e["dice"] = dice
    e["total"] = (e.get("score") or 0) + sum(dice) + pen
    e["initPenalty"] = pen


def _entry_statuses(db, e):
    if e.get("kind") == "player":
        row = db.execute("SELECT character FROM players WHERE id=?", (e["ref"],)).fetchone()
        try:
            return (json.loads(row["character"]).get("statuses") or {}) if row else {}
        except ValueError:
            return {}
    if e.get("kind") == "marker" and e.get("mapId"):
        mk = next((m for m in _markers(e["mapId"]) if m["id"] == e["ref"]), None)
        return (mk or {}).get("statuses") or {}
    return {}


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
@gamemaster_required
def combat_get(cid):
    return jsonify({"tracker": tracker_view(load_tracker(cid), True)})


@app.route("/api/games/<cid>/combat", methods=["POST"])
@gamemaster_required
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
                        _roll_entry(e, _entry_statuses(db, e))
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
                    _roll_entry(e, _entry_statuses(db, e))
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
                    new_round(t)
                elif t["turn"] < 0:
                    t["turn"] = n - 1
                    t["round"] = max(1, t["round"] - 1)
                order = ordered(t)
                if op == "next" and order:
                    order[t["turn"]]["dirt"] = False      # Hit the Dirt penalty ends as their turn comes up
        elif op == "round":
            t["turn"] = 0
            new_round(t)
        elif op == "use":
            e = next((x for x in t["entries"] if x["id"] == b.get("id")), None)
            if not e:
                return _fail(db, "Not in the tracker.")
            u = e.setdefault("used", {"major": 0, "minor": 0})
            kind = "major" if b.get("action") == "major" else "minor"
            limit = 1 if kind == "major" else max(1, min(ACT.MAX_MINOR, e.get("minor") or 1))
            u[kind] = max(0, min(limit + ACT.MAX_MINOR, _clamp0(u.get(kind)) + clamp_int(b.get("delta"), -10, 10, 1)))
            if b.get("reset"):
                e["used"] = {"major": 0, "minor": 0}
                e["fd"] = False
        elif op == "ongoing":
            msg = resolve_ongoing(db, cid, t)
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


def _position(db, map_id, ref, map_data):
    """(c, r) of a runner's token or a marker on this map, or None."""
    kind, rid = (ref or {}).get("kind"), str((ref or {}).get("id") or "")
    if kind == "marker":
        mk = next((m for m in map_data.get("markers", []) if m["id"] == rid), None)
        return (int(mk["c"]), int(mk["r"])) if mk else None
    if kind == "player":
        row = db.execute("SELECT state, current_map_id FROM players WHERE id=?", (rid,)).fetchone()
        if not row or row["current_map_id"] != map_id:
            return None
        tok = ((json.loads(row["state"]).get("maps") or {}).get(map_id) or {}).get("token")
        return (int(tok["c"]), int(tok["r"])) if isinstance(tok, dict) else None
    return None


def sight(db, map_row, a_ref, b_ref):
    """Line of sight, cover from the map (walls, closed doors) and distance in cells between two combatants."""
    data = json.loads(map_row["data"])
    m = {"gridType": map_row["grid_type"], "width": map_row["width"], "height": map_row["height"]}
    pa, pb = _position(db, map_row["id"], a_ref, data), _position(db, map_row["id"], b_ref, data)
    if not pa or not pb:
        return None
    out = geo.line_of_sight(m, data.get("cells") or {}, pa, pb)
    out["cells"] = geo.cell_distance(m["gridType"], pa, pb)
    return out


@app.route("/api/maps/<map_id>/sight", methods=["POST"])
@gamemaster_required
def gm_sight(map_id):
    b = body()
    db = get_db()
    mrow = db.execute("SELECT * FROM maps WHERE id=?", (map_id,)).fetchone()
    if not mrow:
        return err("Map not found.", 404)
    res = sight(db, mrow, b.get("a"), b.get("b"))
    return jsonify({"sight": res})


def _ref_key(ref):
    return f"{(ref or {}).get('kind')}:{(ref or {}).get('id')}"


@app.route("/api/maps/<map_id>/attack", methods=["POST"])
@gamemaster_required
def gm_attack(map_id):
    """The GM resolves an attack (one target, or several with Multiple Attacks), rolling every test:
    attack, each target's Defense (with their defensive interrupt, cover, counterspelling), soak.
    Actions are taken from the initiative tracker and Edge for AR vs DR is awarded (2 per round at most)."""
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
        t = load_tracker(cid) if cid else {"active": False, "entries": []}
        att, att_ref = _fighter(db, cid, data, b.get("attacker"), cache)
        att.entry = entry_for(t, att_ref[0], att_ref[1] if att_ref[0] == "player" else att_ref[1]["id"])
        refs = b.get("targets") or ([b["target"]] if b.get("target") else [])
        targets, seen = [], set()
        for ref in refs[:8]:
            k = _ref_key(ref)
            if k in seen:
                continue
            seen.add(k)
            f, tref = _fighter(db, cid, data, ref, cache)
            if tref == att_ref:
                return _fail(db, "Pick a different target.")
            f.entry = entry_for(t, tref[0], tref[1] if tref[0] == "player" else tref[1]["id"])
            targets.append((ref, f, tref))
        if not targets:
            return _fail(db, "Pick a target.")
        mode = b.get("mode") if b.get("mode") in G.FIRING_MODES else None
        rng = b.get("range") if b.get("range") in G.RANGES else "Near"
        force = bool(b.get("ignoreActions"))
        notes = []
        wkey = str(b.get("weapon") or "")
        if att_ref[0] == "player":
            weapon = X.char_weapon_profile(att, wkey, mode, rng, clamp_int(b.get("amp"), 0, 10, 0))
        elif wkey == "astral":
            weapon = X.astral_profile(att)
        else:
            npc = att.npc or {}
            wl = npc.get("weapons") or []
            i = clamp_int(wkey, -1, len(wl) - 1, -1)
            if i < 0:
                ua = att.attrs.get("Strength", 1)
                w = {"name": "Unarmed", "skill": "Close Combat", "dv": (ua + 1) // 2, "type": "S",
                     "ar": [att.attrs.get("Reaction", 1) + ua, None, None, None, None], "modes": []}
            else:
                w = wl[i]
            weapon = X.npc_weapon_profile(att, w, mode)
            if b.get("dice") not in (None, ""):
                weapon["parts"] = [["Dice", clamp_int(b.get("dice"), 0, 60, 0)]]
        n = len(targets)
        called = ACT.CALLED_SHOTS.get(b.get("called") or "")
        if called and called.get("melee") and not weapon.get("melee"):
            return _fail(db, f"{called['name']} is for melee attacks.")
        anticipation = bool(b.get("anticipation")) and n > 1

        # line of sight (not needed in astral combat or when the GM says so)
        sights = {}
        for ref, f, tref in targets:
            sg = sight(db, mrow, b.get("attacker"), ref)
            sights[_ref_key(ref)] = sg
            if sg and not sg["los"] and not weapon.get("astral") and not weapon.get("matrix") and not b.get("ignoreSight"):
                return _fail(db, f"{att.name} has no line of sight to {f.name} (walls or a closed door). Tick “Ignore line of sight” for indirect fire.")

        # actions and Edge
        what = "the Intercept" if b.get("intercept") else "the attack"
        for cost, label in [("major", what)] + ([("minor", "Multiple Attacks")] if n > 1 else []) + ([("minor", "the called shot")] if called else []):
            note = spend_action(att.entry, cost, label, force)
            if note:
                notes.append(note)
        edge_cost = (called["edge"] if called else 0) + (ACT.ANTICIPATION["edge"] if anticipation else 0)
        att.spend_edge(edge_cost, "this attack")
        if edge_cost:
            notes.append(f"{att.name} spends {edge_cost} Edge")

        # ammo: each target takes the firing mode's rounds, full auto is one burst for everyone
        if att_ref[0] == "player" and weapon.get("uid") not in (None, "unarmed") and not weapon.get("spell") and not weapon.get("astral"):
            for k in range(1 if weapon.get("mode") == "FA" else n):
                note = R.consume_attack(att.char, weapon["uid"], weapon.get("mode"))
                if note and k == 0:
                    notes.append(note)

        defenses = b.get("defenses") or {}
        covers = b.get("cover") if isinstance(b.get("cover"), dict) else {}
        results = []
        for ref, tgt, tref in targets:
            k = _ref_key(ref)
            dkey = defenses.get(k) or None
            if dkey:
                ok, why = X.interrupt_ok(dkey, weapon)
                if not ok:
                    return _fail(db, why)
                it = ACT.INTERRUPTS[dkey]
                note = spend_action(tgt.entry, it["cost"], it["name"], force)
                if note:
                    notes.append(note)
            sg = sights.get(k)
            auto_cover = sg["cover"] if sg else 0
            chosen = covers.get(k, "auto")
            cover = auto_cover if chosen in (None, "auto") else clamp_int(chosen, 0, 4, 0)
            cover = max(cover, tgt.status("Cover"))
            cs = None
            if weapon.get("spell") and b.get("counterspell"):
                prot, _ = _fighter(db, cid, data, b["counterspell"], cache)
                cs = [prot.name, prot.rank(ACT.COUNTERSPELL["skill"])]
            opts = {"range": rng, "attack_mod": b.get("attackMod"), "defense_mod": b.get("defenseMod"),
                    "soak_mod": b.get("soakMod"), "wild": b.get("wild"), "extra_dv": b.get("extraDv"),
                    "unopposed": bool(b.get("unopposed")), "defense": dkey, "cover": cover,
                    "full_defense": bool(tgt.entry and tgt.entry.get("fd")), "called": b.get("called") or None,
                    "split": 1 if anticipation else n, "counterspell": cs, "dirt": bool(att.entry and att.entry.get("dirt"))}
            res = X.resolve_attack(att, weapon, tgt, opts)
            res["sight"] = sg
            if dkey == "full_defense" and tgt.entry:
                tgt.entry["fd"] = True
            if dkey == "hit_the_dirt":
                tgt.statuses["Prone"] = True
                if tgt.entry:
                    tgt.entry["dirt"] = True
                res.setdefault("effects", []).append(["Prone", None])
            results.append((res, tgt, tref))

        if weapon.get("illegal") and att_ref[0] == "player":
            os_add = sum(res["defense"]["hits"] for res, _, _ in results)

            class _Log:
                log = []
            if R.add_overwatch(att.char, _Log, os_add, weapon["name"]):
                notes.extend(_Log.log)
        if weapon.get("spell") and att_ref[0] == "player":
            dr = R.resist_drain(att.char, R.derive(att.char), weapon.get("drain", 0), "drain")
            notes.append(f"drain {dr['dv']}: {dr['text']}")
            results[0][0]["drain"] = dr

        apply = b.get("apply", True)
        auto_edge = b.get("autoEdge", True)
        for res, tgt, tref in results:
            if apply and res.get("damage") and res["track"] == "matrix":
                if tref[0] == "player":
                    c = cache[tref[1]][1]
                    note = R.matrix_damage(c, res["damage"])
                    if note:
                        notes.append(f"{tgt.name}: {note}")
                    bio = weapon.get("biofeedback")
                    mode = (c.get("matrix") or {}).get("mode", "AR")
                    if bio and mode.startswith("VR"):
                        hot = "hot" in mode
                        kind = "P" if (bio == "P" and hot) or (bio == "sim" and hot) else "S"
                        res_hits = R.hits_of(R._int(tgt.attrs.get("Willpower"), 1))
                        bdmg = max(0, res["damage"] - res_hits)
                        if bdmg:
                            R.take_damage(c, "physical" if kind == "P" else "stun", bdmg)
                        notes.append(f"{tgt.name}: biofeedback {res['damage']}{kind}, resisted {res_hits} → {bdmg}")
                else:
                    X.marker_damage(tref[1]["cm"], "physical", res["damage"])
                    sync_vehicle(db, tref[1], cache)
                    res["targetStatus"] = X.marker_status(tref[1]["cm"], tref[1].get("npc"))
            elif apply and res.get("damage"):
                if tref[0] == "player":
                    c = cache[tref[1]][1]
                    R.take_damage(c, res["track"], res["damage"])
                    for name, val in res.get("effects") or []:
                        c.setdefault("statuses", {})[name] = val if val else True
                else:
                    mk = tref[1]
                    track, dmg = vehicle_hit(mk, res)
                    if res.get("note_vehicle"):
                        notes.append(res["note_vehicle"])
                        res["damage"] = 0
                    X.marker_damage(mk["cm"], track, dmg)
                    sync_vehicle(db, mk, cache)
                    for name, val in res.get("effects") or []:
                        if (mk.get("npc") or {}).get("kind") in ("Vehicle", "Drone") and name == "Prone":
                            continue
                        mk.setdefault("statuses", {})[name] = val if val else True
                    res["targetStatus"] = X.marker_status(mk["cm"], mk.get("npc"))
            elif res.get("effects"):
                st = cache[tref[1]][1].setdefault("statuses", {}) if tref[0] == "player" else tref[1].setdefault("statuses", {})
                for name, val in res["effects"]:
                    st[name] = val if val else True
            if auto_edge and res.get("edge_hint"):
                who = att if res["edge_hint"] == "attacker" else tgt
                e = who.entry
                if e is None or _clamp0(e.get("edgeGained")) < ACT.EDGE_GAIN_CAP:
                    got = who.gain_edge(1)
                    if got:
                        if e is not None:
                            e["edgeGained"] = _clamp0(e.get("edgeGained")) + got
                        res["edge_awarded"] = who.name
                        notes.append(f"{who.name} gains 1 Edge (AR vs DR)")
            res["applied"] = bool(apply)
        for pid, (row, c) in cache.items():
            R.clamp_state(c)
            save_char(pid, c)
        db.execute("UPDATE maps SET data=?, updated_at=? WHERE id=?", (json.dumps(data), now(), map_id))
        if t.get("active"):
            save_tracker(cid, t)
        out = []
        for i, (res, tgt, tref) in enumerate(results):
            res["notes"] = notes if i == 0 else []
            if n > 1:
                res["multi"] = f"{i + 1}/{n}"
            if cid:
                add_roll(cid, None, "GM", GM_COLOR, "attack", res, hidden=bool(b.get("hidden")))
            out.append(res)
        db.commit()
    except R.RuleError as e:
        db.rollback()
        return err(str(e))
    except BaseException:
        db.rollback()
        raise
    return jsonify({"result": out[0], "results": out, "rolls": roll_rows(cid, gamemaster=True) if cid else []})


def resolve_ongoing(db, cid, t):
    """Start of a round: everyone Burning, Corrosive or Poisoned resists the damage (soak pool), Poisoned drops by 1."""
    lines = []
    for e in t["entries"]:
        if e.get("kind") == "player":
            row = db.execute("SELECT * FROM players WHERE id=?", (e["ref"],)).fetchone()
            if not row:
                continue
            c = load_char(row)
            f = X.Fighter.from_char(e["name"], c)
            st = c.setdefault("statuses", {})
            changed = False
            for name, (elem, drop) in ACT.ONGOING.items():
                v = st.get(name)
                if not v:
                    continue
                dv = 1 if v is True else int(v)
                soak = X._total(f.soak_pool())
                hits = R.hits_of(soak) if soak else 0
                dmg = max(0, dv - hits)
                if dmg:
                    R.take_damage(c, "physical", dmg)
                lines.append(f"{e['name']}: {name} {dv}, soaked {hits} → {dmg} Physical")
                if drop:
                    nv = dv - drop
                    if nv > 0:
                        st[name] = nv
                    else:
                        st.pop(name, None)
                changed = True
            if changed:
                R.clamp_state(c)
                save_char(row["id"], c)
        elif e.get("kind") == "marker" and e.get("mapId"):
            mrow = db.execute("SELECT data FROM maps WHERE id=?", (e["mapId"],)).fetchone()
            if not mrow:
                continue
            data = json.loads(mrow["data"])
            mk = next((m for m in data.get("markers", []) if m["id"] == e["ref"]), None)
            if not mk or not mk.get("statuses"):
                continue
            f = X.Fighter.from_marker(mk)
            changed = False
            for name, (elem, drop) in ACT.ONGOING.items():
                v = mk["statuses"].get(name)
                if not v:
                    continue
                dv = 1 if v is True else int(v)
                soak = X._total(f.soak_pool())
                hits = R.hits_of(soak) if soak else 0
                dmg = max(0, dv - hits)
                if dmg and mk.get("cm"):
                    X.marker_damage(mk["cm"], "physical", dmg)
                lines.append(f"{e['name']}: {name} {dv}, soaked {hits} → {dmg} Physical")
                if drop:
                    nv = dv - drop
                    if nv > 0:
                        mk["statuses"][name] = nv
                    else:
                        mk["statuses"].pop(name, None)
                changed = True
            if changed:
                db.execute("UPDATE maps SET data=?, updated_at=? WHERE id=?", (json.dumps(data), now(), e["mapId"]))
    if lines:
        add_roll(cid, None, "GM", GM_COLOR, "note", {"text": "ongoing damage: " + "; ".join(lines) + "."})
        return "Ongoing damage resolved."
    return "Nobody is burning, corroding or poisoned."


@app.route("/api/maps/<map_id>/attack-options", methods=["POST"])
@gamemaster_required
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
                            "qty": R._int(it.get("qty"), 1) if p["consumable"] else None, "melee": p["skill"] == "Close Combat"})
        for i, w in enumerate(d.get("natural_weapons") or []):
            p = X.char_weapon_profile(f, f"natural:{i}", None, None)
            out.append({"key": f"natural:{i}", "name": f"{w['name']} ({w['source']})", "pool": sum(x[1] for x in p["parts"]),
                        "dv": f"{p['dv']}{p['type']}", "ar": p["ar"], "modes": [], "melee": p.get("melee")})
        u = R.unarmed_profile(c, d)
        out.append({"key": "weapon:unarmed", "name": "Unarmed", "pool": sum(x[1] for x in u["parts"]), "dv": f"{u['dv']}{u['type']}",
                    "ar": u["ar"], "modes": [], "melee": True})
        if c.get("magic_type") in R.CASTERS:
            for i, sp in enumerate(c.get("spells") or []):
                if sp.get("category") == "Combat":
                    p = R.spell_profile(c, d, sp)
                    if p:
                        out.append({"key": f"spell:{i}", "name": f"{sp['name']} (spell)", "pool": sum(x[1] for x in p["parts"]),
                                    "dv": ("net hits" if p["direct"] else f"{p['dv']}+net") + p["type"], "ar": p["ar"], "modes": [],
                                    "spell": True, "drain": p["drain"], "direct": p["direct"]})
        if d["matrix"].get("device"):
            for mk_ in ("data_spike", "tarpit"):
                pool = next((x for x in R.pools(c, d) if x["key"] == f"matrix:{mk_}"), None)
                if pool:
                    dv = (d["matrix"]["attack"] + 1) // 2 if mk_ == "data_spike" else 1
                    out.append({"key": f"matrix:{mk_}", "name": f"{pool['label']} (Matrix)", "pool": pool["value"], "dv": f"{dv}+net Matrix",
                                "ar": [d["matrix"]["ar"]] * 5, "modes": [], "matrix": True})
        if d.get("awakened") and (c.get("skills") or {}).get("Astral"):
            a = X.astral_profile(f)
            out.append({"key": "astral", "name": "Astral combat", "pool": X._total(a["parts"]), "dv": f"{a['dv']}{a['type']}",
                        "ar": [None] * 5, "modes": [], "astral": True, "melee": True})
    else:
        for i, w in enumerate((f.npc or {}).get("weapons") or []):
            p = X.npc_weapon_profile(f, w)
            out.append({"key": str(i), "name": w["name"], "pool": sum(x[1] for x in p["parts"]), "dv": f"{w['dv']}{w['type']}",
                        "ar": w["ar"], "modes": w.get("modes") or [], "grenade": w.get("grenade"), "melee": p["melee"]})
        ua = f.attrs.get("Strength", 1)
        out.append({"key": "-1", "name": "Unarmed", "pool": f.attrs.get("Agility", 1) + R._int((f.skills or {}).get("Close Combat")),
                    "dv": f"{(ua + 1) // 2}S", "ar": [f.attrs.get("Reaction", 1) + ua, None, None, None, None], "modes": [], "melee": True})
        if (f.npc or {}).get("kind") == "Spirit" or f.rank("Astral"):
            a = X.astral_profile(f)
            out.append({"key": "astral", "name": "Astral combat", "pool": X._total(a["parts"]), "dv": f"{a['dv']}{a['type']}",
                        "ar": [None] * 5, "modes": [], "astral": True, "melee": True})
    cid = mrow["campaign_id"]
    e = entry_for(load_tracker(cid), ref[0], ref[1] if ref[0] == "player" else ref[1]["id"]) if cid else None
    major, minor = actions_left(e) if e else (None, None)
    defense = {"block": f.rank("Close Combat"), "dodge": f.rank("Athletics"), "hit_the_dirt": 2,
               "full_defense": R._int(f.attrs.get("Willpower"), 1), "sorcery": f.rank("Sorcery")}
    try:
        mdr = f.matrix_dr()
    except R.RuleError:
        mdr = None
    return jsonify({"options": out, "dr": f.dr, "matrixDr": mdr, "name": f.name, "edge": f.edge(), "defense": defense,
                    "inCombat": e is not None, "majorLeft": major, "minorLeft": minor, "fullDefense": bool(e and e.get("fd")),
                    "dirt": bool(e and e.get("dirt")), "statuses": f.statuses})


# ====================================================================== statuses
@app.route("/api/maps/<map_id>/status", methods=["POST"])
@gamemaster_required
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
@gamemaster_required
def npc_template(key):
    dmg = 0
    try:
        if key.startswith("pv:"):
            import maps
            npc, dmg = maps.runner_vehicle_npc(key)
        else:
            npc = X.npc_from_key(key, clamp_int(request.args.get("force"), 1, 12, 3))
    except R.RuleError as e:
        return err(str(e))
    cm = X.npc_cm(npc)
    cm["p"] = min(cm["pm"], dmg)
    return jsonify({"npc": npc, "cm": cm})


def vehicle_hit(mk, res):
    """Vehicles shrug off Stun up to their Body; stronger Stun becomes Physical."""
    npc = mk.get("npc") or {}
    if npc.get("kind") not in ("Vehicle", "Drone") or res.get("track") != "stun":
        return res["track"], res["damage"]
    body = R._int((npc.get("attrs") or {}).get("Body"), 1)
    if R._int(res.get("dv")) <= body:
        res["note_vehicle"] = f"{mk.get('label') or 'The vehicle'} ignores Stun damage up to its Body ({body})."
        return "physical", 0
    return "physical", res["damage"]


def sync_vehicle(db, mk, cache):
    """A runner's own vehicle on the map: write its damage back to their sheet."""
    link = (mk.get("npc") or {}).get("link")
    if not link or not mk.get("cm"):
        return
    pid = link.get("pid")
    if pid in cache:
        c = cache[pid][1]
    else:
        row = db.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
        if not row:
            return
        cache[pid] = (row, load_char(row))
        c = cache[pid][1]
    it = next((x for x in c["inventory"] if x.get("uid") == link.get("uid")), None)
    if it:
        it["damage"] = R._int(mk["cm"].get("p"))


def clean_statuses(v):
    if not isinstance(v, dict):
        return None
    out = {}
    for k, val in v.items():
        if k in K.STATUSES:
            out[k] = True if val is True else clamp_int(val, 1, 20, 1)
    return out or None


__all__ = ["player_tracker", "tracker_set_player", "clean_statuses", "roll_rows"]

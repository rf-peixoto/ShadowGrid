"""GM combat tools on the map: initiative tracker, GM-rolled attacks (attack ->
defense -> soak -> monitor), status effects and NPC templates for markers."""
import json
import secrets

from flask import jsonify, request

import geometry as geo
import sightmap as SM
import stealth as ST

from core import (GM_COLOR, add_roll, app, body, clamp_int, display_name, err, get_db, load_char, now,
                  roll_rows, save_char)
from security import gamemaster_required
from sr import actions6e as ACT
from sr import catalog as CAT
from sr import combat as X
from sr import core6e as K
from sr import dice as DICE
from sr import gear6e as G
from sr import matrix6e as MX
from sr import rules as R

MX_VM_EXTRA = MX.VIRTUAL_MACHINE["extra_damage"]

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


def _entry_fighter(db, e):
    """Fighter for a tracker entry (runner or marker), with a saver: (fighter, save()) or (None, None)."""
    if e.get("kind") == "player":
        row = db.execute("SELECT * FROM players WHERE id=?", (e["ref"],)).fetchone()
        if not row:
            return None, None
        c = load_char(row)
        return X.Fighter.from_char(e["name"], c), (lambda: save_char(row["id"], c))
    if e.get("kind") == "marker" and e.get("mapId"):
        mrow = db.execute("SELECT data FROM maps WHERE id=?", (e["mapId"],)).fetchone()
        if not mrow:
            return None, None
        data = json.loads(mrow["data"])
        mk = next((m for m in data.get("markers", []) if m["id"] == e["ref"]), None)
        if not mk:
            return None, None
        return X.Fighter.from_marker(mk), (lambda: db.execute("UPDATE maps SET data=?, updated_at=? WHERE id=?", (json.dumps(data), now(), e["mapId"])))
    return None, None


def _test(f, pool, threshold):
    n = sum(R._int(f.attrs.get(a), 1) for a in pool)
    hits = R.hits_of(n)
    return hits, n, hits >= threshold


def _pool_parts(f, names):
    """Dice parts for a list of skill and attribute names."""
    out = []
    for n in names:
        if n in K.PHYSICAL or n in K.MENTAL or n in ("Magic", "Resonance"):
            out.append([n, R._int(f.attrs.get(n), 1)])
        else:
            out.append([n, f.rank(n)])
    return out


def _entry_status(db, e, name, on, value=True):
    """Set or clear a status on a tracker entry's runner or marker (saved at once)."""
    f, save = _entry_fighter(db, e)
    if not f:
        return
    st = (f.char.setdefault("statuses", {}) if f.char is not None else f.marker.setdefault("statuses", {}))
    if on:
        X.add_status(st, name, value)
    else:
        st.pop(name, None)
    save()


def _entry_damage(db, e, track, amount):
    """Damage on a tracker entry's runner or marker; returns a status line for markers."""
    if amount <= 0:
        return
    f, save = _entry_fighter(db, e)
    if not f:
        return
    if f.char is not None:
        R.take_damage(f.char, track, amount)
        R.clamp_state(f.char)
    elif f.marker is not None and f.marker.get("cm"):
        X.marker_damage(f.marker["cm"], track, amount)
    save()


def release_grapple(db, t, e, note=True):
    """End the grapple this entry is in (both sides lose Restrained / Grappling)."""
    g = e.get("grapple")
    if not g:
        return
    other = next((x for x in t["entries"] if x["id"] == g.get("with")), None)
    for x in (e, other):
        if not x:
            continue
        role = (x.get("grapple") or {}).get("role")
        _entry_status(db, x, "Restrained" if role == "held" else "Grappling", False)
        x.pop("grapple", None)


def start_grapple(db, t, att_e, tgt_e):
    """The attacker now holds the target: statuses and the link between both tracker entries."""
    for x in (att_e, tgt_e):
        if x and x.get("grapple"):
            release_grapple(db, t, x)
    if att_e and tgt_e:
        att_e["grapple"] = {"with": tgt_e["id"], "role": "grappler"}
        tgt_e["grapple"] = {"with": att_e["id"], "role": "held"}


def round_start(db, cid, t):
    """Start of a combat round: the surprised can act again from round 2; Nauseated combatants roll
    Body + Willpower (2): failure costs the whole round, success costs a Minor Action."""
    lines = []
    for e in t["entries"]:
        if t["round"] >= 2:
            e.pop("surprised", None)
        if not _entry_statuses(db, e).get("Nauseated"):
            continue
        f, _save = _entry_fighter(db, e)
        if not f:
            continue
        hits, n, ok = _test(f, ACT.NAUSEA_TEST["pool"], ACT.NAUSEA_TEST["threshold"])
        if ok:
            e["used"]["minor"] = _clamp0(e["used"].get("minor")) + 1
            lines.append(f"{e['name']} fights the nausea ({hits} hits on {n} dice) and loses a Minor Action")
        else:
            e["used"] = {"major": 1, "minor": ACT.MAX_MINOR}
            lines.append(f"{e['name']} is too sick to act this round ({hits} hits on {n} dice)")
    if lines:
        add_roll(cid, None, "GM", GM_COLOR, "note", {"text": f"round {t['round']}, Nauseated: " + "; ".join(lines) + "."})


def surprise(db, t, ambushers):
    """Surprise test (Reaction + Intuition (3)) for everyone but the ambushers: failures can't act or spend
    Edge in the first round (they still defend and soak)."""
    lines = []
    for e in t["entries"]:
        if e.get("kind") == "custom" or e.get("ref") in ambushers or e.get("id") in ambushers:
            continue
        f, _save = _entry_fighter(db, e)
        if not f:
            continue
        hits, n, ok = _test(f, ACT.SURPRISE["pool"], ACT.SURPRISE["threshold"])
        if not ok:
            e["surprised"] = True
            e["used"] = {"major": 1, "minor": ACT.MAX_MINOR}
            e["edgeRound"] = t["round"]
        lines.append(f"{e['name']} {'is surprised' if not ok else 'reacts in time'} ({hits} hits)")
    return lines


def trim_bonus_edge(db, t):
    """When the confrontation ends, Edge above each runner's Edge rating goes away (p. 45)."""
    for e in t["entries"]:
        if e.get("kind") != "player":
            continue
        row = db.execute("SELECT * FROM players WHERE id=?", (e["ref"],)).fetchone()
        if not row:
            continue
        c = load_char(row)
        cap = R.derive(c)["edge_max"]
        if c["current_edge"] > cap:
            c["current_edge"] = cap
            save_char(row["id"], c)


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
        o = {k: e.get(k) for k in ("id", "kind", "ref", "mapId", "name", "total", "dice", "color", "minor", "hidden", "used", "fd", "dirt", "edgeGained",
                                   "surprised", "cs", "edgeRound", "aim", "aimRound", "troll", "grapple", "mv")}
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


@app.route("/api/games/<cid>/sustained")
@gamemaster_required
def sustained_spells(cid):
    """Every runner's sustained spells (for dispelling)."""
    out = []
    for row in get_db().execute("SELECT * FROM players WHERE campaign_id=?", (cid,)).fetchall():
        c = load_char(row)
        for i, rec in enumerate(c.get("sustained") or []):
            out.append({"pid": row["id"], "who": display_name(row, c), "index": i, "name": rec.get("name"),
                        "hits": R._int(rec.get("hits")), "dv": R.sustained_dv(c, rec)})
    return jsonify({"spells": out})


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
            if b.get("op") == "start" and b.get("surprise"):
                lines = surprise(db, t, set(str(x) for x in b.get("ambushers") or []))
                if lines:
                    add_roll(cid, None, "GM", GM_COLOR, "note", {"text": "Surprise (Reaction + Intuition, 3): " + "; ".join(lines) + "."},
                             hidden=not t["visible"])
        elif op == "end":
            for x in t["entries"]:
                release_grapple(db, t, x)
            trim_bonus_edge(db, t)
            t["active"] = False
            t["visible"] = False
            msg = "Combat ended. Edge above each runner's rating is gone."
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
            gone = next((x for x in t["entries"] if x["id"] == b.get("id")), None)
            if gone:
                release_grapple(db, t, gone)
            t["entries"] = [x for x in t["entries"] if x["id"] != b.get("id")]
        elif op in ("next", "prev"):
            n = len(t["entries"])
            if n and op == "next":
                cur = ordered(t)[min(t.get("turn", 0), n - 1)]
                if cur.get("aim") and cur.get("aimTouch") != t["round"]:
                    cur["aim"] = 0                       # a turn without Take Aim or an attack: the aim is lost
            if n:
                t["turn"] = t.get("turn", 0) + (1 if op == "next" else -1)
                if t["turn"] >= n:
                    t["turn"] = 0
                    new_round(t)
                    round_start(db, cid, t)
                elif t["turn"] < 0:
                    t["turn"] = n - 1
                    t["round"] = max(1, t["round"] - 1)
                order = ordered(t)
                if op == "next" and order:
                    order[t["turn"]]["dirt"] = False      # Hit the Dirt penalty ends as their turn comes up
        elif op == "round":
            t["turn"] = 0
            new_round(t)
            round_start(db, cid, t)
        elif op == "counterspell":
            caster = next((x for x in t["entries"] if x["id"] == b.get("id")), None)
            if not caster:
                return _fail(db, "Not in the tracker.")
            f, _save = _entry_fighter(db, caster)
            if not f:
                return _fail(db, "That combatant can't counterspell.")
            sk, attr = ACT.COUNTERSPELL["pool"]
            magic, rank = R._int(f.attrs.get(attr)), f.rank(sk)
            if not magic or not rank:
                return _fail(db, f"{caster['name']} needs Sorcery and Magic to counterspell.")
            note = spend_action(caster, "major", "counterspelling", bool(b.get("force")))
            roll = DICE.new_roll(magic + rank)
            protect = [x for x in t["entries"] if x["id"] in (b.get("protect") or [])] or [caster]
            for x in protect:
                x["cs"] = {"by": caster["name"], "hits": roll["hits"], "until": t["round"] + magic - 1}
            msg = (f"{caster['name']} counterspells: {roll['hits']} hits on {magic + rank} dice, added to "
                   f"{', '.join(x['name'] for x in protect)}'s Defense against spells for {magic} rounds." + (f" {note}." if note else ""))
            add_roll(cid, None, "GM", GM_COLOR, "note", {"text": msg})
        elif op == "aim":
            e = next((x for x in t["entries"] if x["id"] == b.get("id")), None)
            if not e:
                return _fail(db, "Not in the tracker.")
            f, _save = _entry_fighter(db, e)
            if not f:
                return _fail(db, "That combatant can't take aim.")
            if e.get("aimRound") == t["round"] and not b.get("force"):
                return _fail(db, f"{e['name']} already took aim this round (once per round).")
            note = spend_action(e, ACT.TAKE_AIM["cost"], "Take Aim", bool(b.get("force")))
            cap = R._int(f.attrs.get(ACT.TAKE_AIM["max"]), 1)
            e["aim"] = min(cap, _clamp0(e.get("aim")) + ACT.TAKE_AIM["dice"])
            e["aimRound"] = e["aimTouch"] = t["round"]
            msg = f"{e['name']} takes aim: +{e['aim']} dice on the next ranged attack (at most {cap})." + (f" {note}." if note else "")
            add_roll(cid, None, "GM", GM_COLOR, "note", {"text": msg})
        elif op == "dispel":
            caster = next((x for x in t["entries"] if x["id"] == b.get("id")), None)
            if not caster:
                return _fail(db, "Not in the tracker.")
            f, _save = _entry_fighter(db, caster)
            sk, attr = ACT.DISPEL["pool"]
            if not f or not R._int(f.attrs.get(attr)) or not f.rank(sk):
                return _fail(db, f"{caster['name']} needs Sorcery and Magic to dispel.")
            tg = b.get("target") or {}
            row = c = rec = None
            if tg.get("pid"):
                row = db.execute("SELECT * FROM players WHERE id=? AND campaign_id=?", (str(tg["pid"]), cid)).fetchone()
                if not row:
                    return _fail(db, "That runner isn't in this game.")
                c = load_char(row)
                lst = c.get("sustained") or []
                i = clamp_int(tg.get("index"), -1, len(lst) - 1, -1)
                if i < 0:
                    return _fail(db, "That spell isn't sustained any more.")
                rec = lst[i]
                name, hits, dv = rec["name"], R._int(rec.get("hits")), R.sustained_dv(c, rec)
            else:
                name = str(tg.get("name") or "the spell")[:60]
                hits, dv = clamp_int(tg.get("hits"), 0, 30, 0), clamp_int(tg.get("dv"), 1, 30, 3)
            note = spend_action(caster, ACT.DISPEL["action"], "dispelling", bool(b.get("force")))
            pool = R._int(f.attrs.get(attr)) + f.rank(sk)
            roll, resist = DICE.new_roll(pool), DICE.new_roll(max(1, dv * 2))
            net = max(0, roll["hits"] - resist["hits"])
            left = max(0, hits - net)
            if rec is not None:
                if left:
                    rec["hits"] = left
                else:
                    c["sustained"].remove(rec)
                save_char(row["id"], c)
            msg = (f"{caster['name']} dispels {name}: {roll['hits']} hits on {pool} dice vs {resist['hits']} on {dv * 2} (Drain Value × 2), "
                   f"{net} net → " + (f"{name} is dispelled." if not left else f"{name} keeps {left} of its {hits} hits.") + (f" {note}." if note else ""))
            add_roll(cid, None, "GM", GM_COLOR, "note", {"text": msg})
        elif op == "grapple":
            e = next((x for x in t["entries"] if x["id"] == b.get("id")), None)
            act_ = ACT.GRAPPLE["actions"].get(b.get("action") or "")
            if not e or not act_:
                return _fail(db, "Pick a grapple action.")
            g = e.get("grapple") or {}
            if not g or (g.get("role") == "held") != bool(act_.get("held")):
                return _fail(db, f"{e['name']} isn't " + ("held" if act_.get("held") else "holding anyone") + ".")
            other = next((x for x in t["entries"] if x["id"] == g.get("with")), None)
            fa, _sa = _entry_fighter(db, e)
            fo, _so = _entry_fighter(db, other) if other else (None, None)
            if not fa or not fo:
                release_grapple(db, t, e)
                return _fail(db, "The other side of the grapple is gone; it's over.")
            note = spend_action(e, "major", act_["name"], bool(b.get("force")))
            a_parts = _pool_parts(fa, act_["attack"]) + ([["Wound modifier", fa.wound]] if fa.wound else [])
            d_parts = _pool_parts(fo, act_["defense"]) + ([["Wound modifier", fo.wound]] if fo.wound else [])
            if act_.get("penalty"):
                d_parts.append(["Restrained", ACT.GRAPPLE["restrained_defense"]])
            ar, dr_ = DICE.new_roll(max(1, X._total(a_parts))), DICE.new_roll(max(1, X._total(d_parts)))
            net = ar["hits"] - dr_["hits"]
            ok = ar["hits"] > 0 and net >= 0
            line = f"{e['name']}: {act_['name']} ({ar['hits']} vs {dr_['hits']} hits)"
            key = b.get("action")
            if key == "restrain":
                if not ok:
                    release_grapple(db, t, e)
                line += " → " + ("still holding " + other["name"] if ok else f"{other['name']} breaks loose")
            elif key == "break":
                if ok:
                    release_grapple(db, t, e)
                line += " → " + ("free" if ok else "still held")
            elif key == "damage" and ok:
                dv = (R._int(fa.attrs.get("Strength"), 1) + 1) // 2 + max(0, net)
                soak = R.hits_of(X._total(fo.soak_pool()))
                dmg = max(0, dv - soak)
                _entry_damage(db, other, "stun", dmg)
                line += f" → DV {dv}S, soaked {soak} → {dmg} Stun to {other['name']}"
            elif key == "tackle" and ok:
                dv = R._int(fa.attrs.get("Body"), 1) + max(0, net)
                soak = R.hits_of(R._int(fo.attrs.get("Body"), 1))
                dmg = max(0, dv - soak)
                _entry_damage(db, other, "stun", dmg)
                _entry_status(db, other, "Prone", True)
                line += f" → {other['name']} goes Prone, DV {dv}S, resisted {soak} → {dmg} Stun"
            else:
                line += " → no effect"
            add_roll(cid, None, "GM", GM_COLOR, "note", {"text": line + "." + (f" {note}." if note else "")})
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


RANGE_LIMITS = (("Close", 3), ("Near", 50), ("Medium", 250), ("Far", 500))


def range_band(meters):
    """Range category for a distance in meters (p. 108): Close 0-3, Near 4-50, Medium 51-250, Far 251-500."""
    for name, top in RANGE_LIMITS:
        if meters <= top + 1e-6:
            return name
    return "Extreme"


def _map_dict(map_row, data):
    return {"id": map_row["id"], "gridType": map_row["grid_type"], "width": map_row["width"], "height": map_row["height"],
            "settings": json.loads(map_row["settings"] or "{}"), "data": data, "updatedAt": map_row["updated_at"]}


def _eyes(db, ref, data):
    kind, rid = (ref or {}).get("kind"), str((ref or {}).get("id") or "")
    if kind == "marker":
        mk = next((m for m in data.get("markers", []) if m["id"] == rid), None)
        return SM.eyes_of_marker(mk) if mk else ([], [], 0)
    if kind == "player":
        row = db.execute("SELECT character FROM players WHERE id=?", (rid,)).fetchone()
        return SM.eyes_of_player_row(row) if row else ([], [], 0)
    return [], [], 0


def sight(db, map_row, a_ref, b_ref, data=None, sm=None):
    """Line of sight, cover (walls, closed doors), distance and range band between two combatants, and how
    each sees the other in the map's light and smoke with their own eyes."""
    data = data if data is not None else json.loads(map_row["data"])
    m = _map_dict(map_row, data)
    pa, pb = _position(db, map_row["id"], a_ref, data), _position(db, map_row["id"], b_ref, data)
    if not pa or not pb:
        return None
    sm = sm or SM.map_sight(m, db)
    out = sm.cover(pa, pb)
    out["cells"] = geo.cell_distance(m["gridType"], pa, pb)
    cell_m = SM.cell_meters(m)
    out["meters"] = round(sm.distance_m(pa, pb, cell_m), 1)
    out["band"] = range_band(out["meters"])
    ea, eb = _eyes(db, a_ref, data), _eyes(db, b_ref, data)
    out["view"] = sm.view(pa, pb, ea[0], cell_m, ea[2])
    out["back"] = sm.view(pb, pa, eb[0], cell_m, eb[2])
    out["light"] = geo.LIGHT_LEVELS[sm.level(*pb)]
    out["magnification"] = "Magnification" in ea[1]
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


def _owner_char(db, cid, att, att_ref, cache):
    """(pid, character) owning an attacker's mounted weapons: the runner, or the owner of a linked vehicle marker."""
    if att_ref[0] == "player":
        return att_ref[1], cache[att_ref[1]][1]
    link = (att.npc or {}).get("link") or {}
    pid = link.get("pid")
    if not pid:
        return None, None
    if pid not in cache:
        row = db.execute("SELECT * FROM players WHERE id=? AND campaign_id=?", (pid, cid)).fetchone()
        if not row:
            return None, None
        cache[pid] = (row, load_char(row))
    return pid, cache[pid][1]


def _linked_vehicle_item(db, cid, f, cache):
    """A runner's own vehicle behind a vehicle marker (its speed and mounts live on their sheet)."""
    link = (f.npc or {}).get("link") or {}
    if not link.get("pid"):
        return None
    pid, c = _owner_char(db, cid, f, ("marker", None), cache)
    if not c:
        return None
    return next((x for x in c["inventory"] if x.get("uid") == link.get("uid")), None)


def _mounted_options(c, only_vehicle=None):
    """[(weapon, vehicle)] for every weapon in a mount (on one vehicle, or on all of them)."""
    out = []
    for w in c["inventory"]:
        if w.get("mounted"):
            _m, v = R.mount_vehicle(c, w)
            if v and (only_vehicle is None or v.get("uid") == only_vehicle):
                out.append((w, v))
    return out


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
        auto_range = b.get("range") in (None, "", "auto")
        rng = b.get("range") if b.get("range") in G.RANGES else "Near"
        if auto_range:
            sg0 = sight(db, mrow, b.get("attacker"), targets[0][0], data)
            rng = sg0["band"] if sg0 else "Near"
        force = bool(b.get("ignoreActions"))
        notes = []
        wkey = str(b.get("weapon") or "")
        if wkey.startswith("mount:"):
            owner_pid, owner_c = _owner_char(db, cid, att, att_ref, cache)
            if not owner_c:
                return _fail(db, "That weapon mount belongs to nobody in this game.")
            weapon = X.mount_profile(owner_c, wkey[6:], mode, rng, gunner=att_ref[0] == "player",
                                     gunner_c=att.char if att_ref[0] == "player" else None)
            weapon["owner"] = owner_pid
        elif att_ref[0] == "player":
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
            if (att.npc or {}).get("kind") in ("Vehicle", "Drone"):
                pen = X.marker_speed_penalty(att.npc, _linked_vehicle_item(db, cid, att, cache))
                if pen:
                    weapon["parts"].append(["Speed Intervals", pen])
                    if w.get("category") == "Ram":
                        weapon["dv"] -= pen                # +1 DV per current Speed Interval
                        notes.append(f"ram at speed: +{-pen} DV")
        n = len(targets)
        called = ACT.CALLED_SHOTS.get(b.get("called") or "")
        if called and called.get("melee") and not weapon.get("melee"):
            return _fail(db, f"{called['name']} is for melee attacks.")
        eact_key = b.get("edgeAction") if b.get("edgeAction") in ACT.EDGE_ACTIONS else None
        eact = ACT.EDGE_ACTIONS.get(eact_key or "")
        att_cover = att.status("Cover") if not weapon.get("astral") and not weapon.get("matrix") else 0
        if eact and eact.get("melee") and not weapon.get("melee"):
            return _fail(db, f"{eact['name']} is for melee attacks.")
        if eact and eact.get("ranged") and weapon.get("melee"):
            return _fail(db, f"{eact['name']} is for ranged attacks.")
        if eact and eact.get("cover") and att_cover < eact["cover"]:
            return _fail(db, f"{eact['name']} needs the attacker in Cover IV.")
        trip = bool(b.get("trip"))
        if trip and not weapon.get("melee"):
            return _fail(db, "Trip is a melee attack.")
        grapple = bool(b.get("grapple"))
        if grapple and (not weapon.get("melee") or "unarmed" not in (str(weapon.get("uid") or "") + weapon["name"].lower())):
            return _fail(db, "Grappling is an unarmed melee attack.")
        if grapple and n > 1:
            return _fail(db, "Grapple one opponent at a time.")
        physical_ranged = not weapon.get("melee") and not weapon.get("spell") and not weapon.get("astral") and not weapon.get("matrix")
        aim_now = bool(b.get("aimNow"))
        if aim_now and not physical_ranged:
            return _fail(db, "Take Aim is for firearms, bows and other ranged weapons.")
        anticipation = bool(b.get("anticipation")) and n > 1
        if anticipation and weapon.get("melee"):
            return _fail(db, "Anticipation is for ranged Multiple Attacks.")
        if b.get("intercept") and not weapon.get("melee"):
            return _fail(db, "Intercept is a melee attack.")

        # line of sight, light and smoke (not needed in astral combat or when the GM says so)
        sights = {}
        sm_ = SM.map_sight(_map_dict(mrow, data), db)
        physical_sight = not weapon.get("astral") and not weapon.get("matrix")
        for ref, f, tref in targets:
            sg = sight(db, mrow, b.get("attacker"), ref, data, sm_)
            sights[_ref_key(ref)] = sg
            if sg and not sg["los"] and physical_sight and not b.get("ignoreSight"):
                return _fail(db, f"{att.name} has no line of sight to {f.name} (walls or a closed door). Tick “Ignore line of sight” for indirect fire.")
            if sg and not sg["view"]["see"] and physical_sight and not b.get("ignoreSight"):
                why = "it's too dark for their eyes" if sg["view"].get("dark") else "they are blinded"
                return _fail(db, f"{att.name} can't see {f.name}: {why} (a visibility test fails outright, p. 51). "
                                 "Tick “Ignore line of sight” to attack anyway.")

        # actions (Intercept: Minor + the Attack Major; full auto splits without Multiple Attacks; attacking
        # from Cover needs an extra Minor) and Edge (one expenditure per combat round)
        costs = [("major", "the attack")]
        if b.get("intercept"):
            costs.append(("minor", "Intercept"))
        fork = bool(weapon.get("matrix") and weapon.get("fork") and n == 2)    # Fork: two targets, no split
        if n > 1 and weapon.get("mode") != "FA" and not fork:
            costs.append(("minor", "Multiple Attacks"))
        if called and called.get("minor"):
            costs.append(("minor", "the called shot"))
        if att_cover:
            costs.append(("minor", "getting clear of cover"))
        if trip:
            costs.append(("minor", "Trip"))
        if aim_now:
            costs.append(("minor", "Take Aim"))
        for cost, label in costs:
            note = spend_action(att.entry, cost, label, force)
            if note:
                notes.append(note)
        edge_cost = (called["edge"] if called else 0) + (ACT.ANTICIPATION["edge"] if anticipation else 0) + (eact["edge"] if eact else 0)
        if edge_cost:
            edge_once(t, att.entry, att.name, force)
        att.spend_edge(edge_cost, "this attack")
        if edge_cost:
            notes.append(f"{att.name} spends {edge_cost} Edge")

        # Take Aim: the bonus built up in the tracker (+1 now with "Take Aim first"); used up by this attack
        aim_dice = 0
        rnd = t.get("round") if t.get("active") else None
        if att.entry is not None and t.get("active"):
            if aim_now:
                if att.entry.get("aimRound") == rnd and not force:
                    return _fail(db, f"{att.name} already took aim this round (once per round).")
                att.entry["aim"] = min(R._int(att.attrs.get(ACT.TAKE_AIM["max"]), 1), _clamp0(att.entry.get("aim")) + 1)
                att.entry["aimRound"] = rnd
            if physical_ranged:
                aim_dice = _clamp0(att.entry.get("aim"))
                att.entry["aim"] = 0
            att.entry["aimTouch"] = rnd
        elif aim_now:
            aim_dice = 1
        if aim_dice:
            notes.append(f"Take Aim +{aim_dice}")
        tactical_att = bool(att.entry and att.entry.get("troll") == rnd and rnd is not None)

        wrests = b.get("wrest") if isinstance(b.get("wrest"), dict) else {}
        rolls_ = b.get("tactical") if isinstance(b.get("tactical"), dict) else {}
        for ref, tgt, tref in targets:
            k = _ref_key(ref)
            dk = (b.get("defenses") or {}).get(k)
            if wrests.get(k) and (dk != "block" or not weapon.get("melee")):
                return _fail(db, "Wrest goes with a Block against a melee attack.")
            if wrests.get(k) and tgt.edge() < ACT.DEFENSE_EDGE_ACTIONS["wrest"]["edge"]:
                return _fail(db, f"{tgt.name} needs {ACT.DEFENSE_EDGE_ACTIONS['wrest']['edge']} Edge to Wrest (has {tgt.edge()}).")
            if rolls_.get(k):
                if dk != "hit_the_dirt":
                    return _fail(db, "Tactical Roll goes with Hit the Dirt.")
                edge_once(t, tgt.entry, tgt.name, force)
                tgt.spend_edge(ACT.DEFENSE_EDGE_ACTIONS["tactical_roll"]["edge"], "Tactical Roll")
                if tgt.entry is not None:
                    tgt.entry["troll"] = rnd
                notes.append(f"{tgt.name} spends 1 Edge on a Tactical Roll")

        # ammo: each target takes the firing mode's rounds, full auto is one burst for everyone
        ammo_c = cache[weapon["owner"]][1] if weapon.get("owner") else (att.char if att_ref[0] == "player" else None)
        if ammo_c is not None and weapon.get("uid") not in (None, "unarmed") and not weapon.get("spell") and not weapon.get("astral"):
            for k in range(1 if weapon.get("mode") == "FA" else n):
                note = R.consume_attack(ammo_c, weapon["uid"], weapon.get("mode"))
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
            cs = counterspell_on(t, tgt.entry) if weapon.get("spell") else None
            rng_t = rng
            if auto_range and sg and physical_sight:
                rng_t = sg["band"]
            env_blind = sg["view"]["blind"] if sg and physical_sight and sg["view"]["see"] else 0
            opts = {"range": rng_t, "attack_mod": b.get("attackMod"), "env_blind": env_blind,
                    "magnification": bool(sg and sg.get("magnification")), "defense_mod": b.get("defenseMod"),
                    "soak_mod": b.get("soakMod"), "wild": b.get("wild"), "extra_dv": b.get("extraDv"),
                    "unopposed": bool(b.get("unopposed")), "defense": dkey, "cover": cover,
                    "full_defense": bool(tgt.entry and tgt.entry.get("fd")), "called": b.get("called") or None,
                    "split": 1 if anticipation or fork else n, "counterspell": cs, "dirt": bool(att.entry and att.entry.get("dirt")),
                    "att_cover": att_cover, "edge_action": eact_key, "astral_type": b.get("astralType"),
                    "aim": aim_dice, "trip": trip, "grapple": grapple, "tactical_att": tactical_att,
                    "tactical_def": bool(tgt.entry and rnd is not None and tgt.entry.get("troll") is not None and rnd <= tgt.entry["troll"] + 1)}
            restrained = bool(tgt.status("Restrained"))
            stray_item = None
            res = X.resolve_attack(att, weapon, tgt, opts)
            res["sight"] = sg
            if restrained:
                res["restrained"] = True
            # Wrest: after a successful Block, Close Combat + Agility with the attacker's Strength as threshold
            if wrests.get(k) and not res.get("hit"):
                wa = ACT.DEFENSE_EDGE_ACTIONS["wrest"]
                edge_once(t, tgt.entry, tgt.name, force)
                tgt.spend_edge(wa["edge"], "Wrest")
                w_parts = _pool_parts(tgt, wa["test"])
                w_roll = DICE.new_roll(max(1, X._total(w_parts)))
                thr = R._int(att.attrs.get(wa["threshold"]), 1)
                got = "takes it" if w_roll["hits"] > thr else "knocks it to the ground" if w_roll["hits"] == thr else "can't get hold of it"
                res["wrest"] = {"parts": w_parts, "dice": w_roll["dice"], "hits": w_roll["hits"], "threshold": thr, "outcome": got}
                notes.append(f"{tgt.name} wrests at {att.name}'s {weapon['name']} ({w_roll['hits']} hits vs Strength {thr}): {got}")
            # a missed attack on a restrained character may hit the one holding them
            if restrained and not res.get("hit") and tgt.entry and (tgt.entry.get("grapple") or {}).get("with") != (att.entry or {}).get("id"):
                ge = next((x for x in t["entries"] if x["id"] == (tgt.entry.get("grapple") or {}).get("with")), None)
                if ge and (ge.get("kind") == "player" or ge.get("mapId") == map_id):
                    gref = {"kind": ge["kind"], "id": ge["ref"]}
                    gf, gtref = _fighter(db, cid, data, gref, cache)
                    gf.entry = ge
                    stray = X.resolve_attack(att, weapon, gf, dict(opts, defense=None, cover=0, attack_roll={
                        "dice": res["attack"]["dice"], "hits": res["attack"]["hits"], "glitch": res["attack"]["glitch"], "critical": res["attack"]["critical"]}))
                    stray["stray"] = f"missed {tgt.name} and went at {gf.name}, who holds them"
                    stray_item = (stray, gf, gtref)
            if dkey == "full_defense" and tgt.entry:
                tgt.entry["fd"] = True
            if dkey == "hit_the_dirt":
                tgt.statuses["Prone"] = True
                if tgt.entry:
                    tgt.entry["dirt"] = True
                res.setdefault("effects", []).append(["Prone", None])
            if res.get("grapple", {}).get("held"):
                start_grapple(db, t, att.entry, tgt.entry)
                ast = att.char.setdefault("statuses", {}) if att.char is not None else (att.marker.setdefault("statuses", {}) if att.marker is not None else {})
                X.add_status(ast, "Grappling")
            results.append((res, tgt, tref))
            if stray_item:
                results.append(stray_item)

        if len(results) > 1 and results[0][0].get("ar") is not None:
            top = max(range(len(results)), key=lambda i: results[i][0]["dr"])
            diff = results[0][0]["ar"] - results[top][0]["dr"]
            for i, (res, _, _) in enumerate(results):
                res["edge_hint"] = None
            if diff >= ACT.EDGE_HINT_MARGIN and not att_cover:
                results[0][0]["edge_hint"] = "attacker"
            elif diff <= -ACT.EDGE_HINT_MARGIN:
                results[top][0]["edge_hint"] = "defender"

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
            icr = res.get("ic") or {}
            if apply and res.get("hit") and icr.get("reduce") and tref[0] == "player":
                c = cache[tref[1]][1]
                mods = c.setdefault("matrix_state", {}).setdefault("ic_mods", {})
                mods[icr["reduce"]] = R._int(mods.get(icr["reduce"])) - icr["by"]
                notes.append(f"{tgt.name}: {icr['reduce'].replace('_', ' ').title()} −{icr['by']} until they leave the host")
            if res.get("hit") and icr.get("linklock"):
                notes.append(f"{tgt.name} is link-locked")
            if res.get("damage") and res.get("track") == "matrix" and weapon.get("lockdown"):
                notes.append(f"{tgt.name} is link-locked (Lockdown)")
            if apply and res.get("damage") and res.get("track") == "matrix" and tref[0] == "player" \
                    and R.program_running(tgt.d, "Virtual Machine"):
                res["damage"] += MX_VM_EXTRA
                notes.append(f"{tgt.name}: +1 box from running a Virtual Machine")
            if apply and res.get("damage") and res["track"] == "matrix":
                if tref[0] == "player":
                    c = cache[tref[1]][1]
                    if icr.get("damage") != "bio":
                        note = R.matrix_damage(c, res["damage"])
                        if note:
                            notes.append(f"{tgt.name}: {note}")
                    bio = weapon.get("biofeedback")
                    mode = (c.get("matrix") or {}).get("mode", "AR")
                    # IC biofeedback hits whoever it reaches; the Biofeedback program needs a VR target
                    if bio and (mode.startswith("VR") or icr):
                        hot = "hot" in mode
                        kind = "P" if (bio in ("P", "sim") and hot) else "S"
                        res_hits = R.hits_of(R._int(tgt.attrs.get("Willpower"), 1))
                        bdmg = max(0, res["damage"] - res_hits)
                        if bdmg:
                            R.take_damage(c, "physical" if kind == "P" else "stun", bdmg)
                        notes.append(f"{tgt.name}: biofeedback {res['damage']}{kind}, resisted {res_hits} (Willpower) → {bdmg}")
                else:
                    X.marker_damage(tref[1]["cm"], "physical", res["damage"])
                    sync_vehicle(db, tref[1], cache)
                    res["targetStatus"] = X.marker_status(tref[1]["cm"], tref[1].get("npc"))
            elif apply and res.get("damage"):
                if tref[0] == "player":
                    c = cache[tref[1]][1]
                    R.take_damage(c, res["track"], res["damage"])
                    if res.get("knockout"):
                        c["stun_damage"] = R.derive(c)["stun_boxes"]
                    for name, val in res.get("effects") or []:
                        X.add_status(c.setdefault("statuses", {}), name, val)
                else:
                    mk = tref[1]
                    track, dmg = vehicle_hit(mk, res)
                    if res.get("note_vehicle"):
                        notes.append(res["note_vehicle"])
                        res["damage"] = 0
                    X.marker_damage(mk["cm"], track, dmg)
                    if res.get("knockout") and mk.get("cm"):
                        if mk["cm"].get("grunt"):
                            mk["cm"]["p"] = max(mk["cm"]["p"], mk["cm"]["pm"])
                        else:
                            mk["cm"]["s"] = mk["cm"].get("sm", 0)
                    sync_vehicle(db, mk, cache)
                    for name, val in res.get("effects") or []:
                        if (mk.get("npc") or {}).get("kind") in ("Vehicle", "Drone") and name == "Prone":
                            continue
                        X.add_status(mk.setdefault("statuses", {}), name, val)
                    res["targetStatus"] = X.marker_status(mk["cm"], mk.get("npc"))
            elif res.get("effects"):
                st = cache[tref[1]][1].setdefault("statuses", {}) if tref[0] == "player" else tref[1].setdefault("statuses", {})
                for name, val in res["effects"]:
                    X.add_status(st, name, val)
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
            sgv = (res.get("sight") or {})
            if auto_edge and physical_sight and sgv.get("view") and not res.get("stray"):
                # vision advantage (p. 118): whoever sees the other clearly while they can't gains 1 Edge
                a_clear, d_clear = sgv["view"].get("clear"), sgv["back"].get("clear")
                who = att if a_clear and not d_clear else tgt if d_clear and not a_clear and sgv["back"].get("see") else None
                e = who.entry if who else None
                if who and (e is None or _clamp0(e.get("edgeGained")) < ACT.EDGE_GAIN_CAP):
                    got = who.gain_edge(1)
                    if got:
                        if e is not None:
                            e["edgeGained"] = _clamp0(e.get("edgeGained")) + got
                        res["vision_edge"] = who.name
                        notes.append(f"{who.name} gains 1 Edge (sees better in the {sgv.get('light', 'light')}"
                                     f"{' and smoke' if sgv['view'].get('blind') or sgv['back'].get('blind') else ''})")
            if res.get("restrained") and not res.get("stray"):
                e = att.entry
                if e is None or _clamp0(e.get("edgeGained")) < ACT.EDGE_GAIN_CAP:
                    got = att.gain_edge(ACT.GRAPPLE["edge_on_restrained"])
                    if got:
                        if e is not None:
                            e["edgeGained"] = _clamp0(e.get("edgeGained")) + got
                        notes.append(f"{att.name} gains 1 Edge against a restrained target")
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
        if b.get("apply", True):
            # attacking, or being attacked, ends stealth
            if att_ref[0] == "player":
                ST.stop_pid(db, att_ref[1], "attacked")
            for _ref, _f, tref in targets:
                if tref[0] == "player":
                    ST.stop_pid(db, tref[1], "came under attack")
        db.commit()
    except R.RuleError as e:
        db.rollback()
        return err(str(e))
    except BaseException:
        db.rollback()
        raise
    return jsonify({"result": out[0], "results": out, "rolls": roll_rows(cid, gamemaster=True) if cid else []})


def edge_once(t, entry, name, force=False):
    """One Edge expenditure per combat round (core p. 45)."""
    if not t.get("active") or entry is None:
        return
    if entry.get("edgeRound") == t.get("round") and not force:
        raise R.RuleError(f"{name} already spent Edge this combat round (one expenditure per round).")
    entry["edgeRound"] = t.get("round")


def player_edge_round(cid, pid):
    """A runner in an active combat makes at most one Edge expenditure per combat round."""
    t = load_tracker(cid)
    e = entry_for(t, "player", pid)
    if not e:
        return
    edge_once(t, e, e["name"])
    save_tracker(cid, t)


def counterspell_on(t, entry):
    """[caster, hits] when this combatant is under a counterspelling boost that still lasts."""
    cs = (entry or {}).get("cs")
    if cs and t.get("active") and _clamp0(t.get("round")) <= _clamp0(cs.get("until")):
        return [cs.get("by") or "counterspell", _clamp0(cs.get("hits"))]
    return None


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
                    dv = (d["matrix"]["ar"] + 1) // 2 if mk_ == "data_spike" else 1
                    out.append({"key": f"matrix:{mk_}", "name": f"{pool['label']} (Matrix)", "pool": pool["value"], "dv": f"{dv}+net Matrix",
                                "ar": [d["matrix"]["ar"]] * 5, "modes": [], "matrix": True})
        if d.get("awakened") and (c.get("skills") or {}).get("Astral"):
            a = X.astral_profile(f)
            out.append({"key": "astral", "name": "Astral combat", "pool": X._total(a["parts"]), "dv": f"{a['dv']} (P or S)",
                        "ar": a["ar"], "modes": [], "astral": True, "melee": True})
        for w, v in _mounted_options(c):
            try:
                p = X.mount_profile(c, w["uid"], None, None, gunner=True)
            except R.RuleError:
                continue
            out.append({"key": f"mount:{w['uid']}", "name": f"{w['name']} on the {v['name']} (gunner)", "pool": X._total(p["parts"]),
                        "dv": f"{p['dv']}{p['type']}", "ar": p["ar"], "modes": CAT.modes_list(w.get("modes")),
                        "loaded": w.get("loaded"), "clip": w.get("clip"), "mounted": True})
    else:
        for i, w in enumerate((f.npc or {}).get("weapons") or []):
            p = X.npc_weapon_profile(f, w)
            out.append({"key": str(i), "name": w["name"], "pool": sum(x[1] for x in p["parts"]), "dv": f"{w['dv']}{w['type']}",
                        "ar": w["ar"], "modes": w.get("modes") or [], "grenade": w.get("grenade"), "melee": p["melee"]})
        ua = f.attrs.get("Strength", 1)
        out.append({"key": "-1", "name": "Unarmed", "pool": f.attrs.get("Agility", 1) + R._int((f.skills or {}).get("Close Combat")),
                    "dv": f"{(ua + 1) // 2}S", "ar": [f.attrs.get("Reaction", 1) + ua, None, None, None, None], "modes": [], "melee": True})
        link = (f.npc or {}).get("link") or {}
        if link.get("pid"):
            cache = {}
            pid, oc = _owner_char(db, mrow["campaign_id"], f, ref, cache)
            for w, v in (_mounted_options(oc, link.get("uid")) if oc else []):
                try:
                    p = X.mount_profile(oc, w["uid"], None, None, gunner=False)
                except R.RuleError:
                    continue
                out.append({"key": f"mount:{w['uid']}", "name": f"{w['name']} (the drone fires)", "pool": X._total(p["parts"]),
                            "dv": f"{p['dv']}{p['type']}", "ar": p["ar"], "modes": CAT.modes_list(w.get("modes")),
                            "loaded": w.get("loaded"), "clip": w.get("clip"), "mounted": True})
        if (f.npc or {}).get("kind") == "Spirit" or f.rank("Astral"):
            a = X.astral_profile(f)
            out.append({"key": "astral", "name": "Astral combat", "pool": X._total(a["parts"]), "dv": f"{a['dv']} (P or S)",
                        "ar": a["ar"], "modes": [], "astral": True, "melee": True})
    cid = mrow["campaign_id"]
    e = entry_for(load_tracker(cid), ref[0], ref[1] if ref[0] == "player" else ref[1]["id"]) if cid else None
    major, minor = actions_left(e) if e else (None, None)
    defense = {"block": f.rank("Close Combat"), "dodge": f.rank("Athletics"), "hit_the_dirt": 2,
               "full_defense": R._int(f.attrs.get("Willpower"), 1), "sorcery": f.rank("Sorcery")}
    try:
        mdr = f.matrix_dr()
    except R.RuleError:
        mdr = None
    t = load_tracker(cid) if cid else {"active": False}
    return jsonify({"options": out, "dr": f.dr, "matrixDr": mdr, "astralDr": f.astral_dr(), "name": f.name, "edge": f.edge(), "defense": defense,
                    "inCombat": e is not None, "majorLeft": major, "minorLeft": minor, "fullDefense": bool(e and e.get("fd")),
                    "dirt": bool(e and e.get("dirt")), "statuses": f.statuses, "cover": f.status("Cover"),
                    "counterspell": counterspell_on(t, e), "edgeSpent": bool(e and e.get("edgeRound") == t.get("round")),
                    "canCounterspell": bool(R._int(f.attrs.get("Magic")) and f.rank("Sorcery")),
                    "aim": _clamp0((e or {}).get("aim")), "aimedThisRound": bool(e and t.get("active") and e.get("aimRound") == t.get("round")),
                    "aimMax": R._int(f.attrs.get(ACT.TAKE_AIM["max"]), 1),
                    "tacticalRoll": bool(e and t.get("active") and e.get("troll") is not None and t.get("round", 0) <= e["troll"] + 1),
                    "restrained": bool(f.status("Restrained")), "grapple": (e or {}).get("grapple"),
                    "wrestAgility": f.rank("Close Combat") + R._int(f.attrs.get("Agility"), 1), "strength": R._int(f.attrs.get("Strength"), 1)})


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
                X.add_status(st, name, val)
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
                X.add_status(st, name, val)
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

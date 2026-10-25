"""Stealth (core book p. 97): "a Stealth + Agility test is made at the start of such an effort, with the net
hits being used as a threshold for others to notice". A runner ticks Stealth: their test is rolled at once
and its hits become the threshold. Every enemy that could see them (a sight line, and light and smoke their
eyes can handle) rolls Perception + Intuition against it, once per stealth attempt, as the runner comes into
their view. Those who reach the threshold notice the runner (the GM sees who). The rules add no movement
penalty for sneaking. Stealth ends when the runner unticks it, when the GM ends it, or when the runner attacks
or is attacked. Unnoticed sneaking runners are offered as ambushers when the GM starts combat.

Stored on the player's state: state["stealth"] = {"on", "mapId", "hits", "pool", "checked": [marker ids],
"spotted": [marker ids], "at"}."""
import json

import sightmap as SM
from core import GM_COLOR, add_roll, game_settings, get_db, load_char, now
from sr import combat as X
from sr import dice as DICE
from sr import rules as R

OUT_COLD = ("Unconscious", "Dying", "Dead", "Destroyed", "Disabled")
BLIND_DICE = 3                     # Blinded: -3 per level to visual tests (p. 52)


def state_of(p):
    """The stealth state of a player dict (row_to_player), or None when not sneaking."""
    st = (p.get("state") or {}).get("stealth")
    return st if isinstance(st, dict) and st.get("on") else None


def rolls_hidden(cid):
    """The GM decides whether players see stealth and perception rolls."""
    return not game_settings(cid).get("stealthRolls")


def stealth_parts(c, d=None):
    """Stealth + Agility, with the Sneaking specialization or expertise, wounds, statuses and drugs."""
    d = d or R.derive(c)
    pools = {p["key"]: p for p in R.pools(c, d)}
    for key in ("exp:Stealth:Sneaking", "spec:Stealth:Sneaking", "skill:Stealth"):
        if key in pools:
            return [list(x) for x in pools[key]["parts"]]
    return [["Agility", d["attributes"].get("Agility", 1)], ["Stealth (untrained)", -1]]


def perception_parts(mk, blind):
    """Perception + Intuition for an NPC marker, minus wounds and Blinded (its own and the smoke's)."""
    f = X.Fighter.from_marker(mk)
    parts = [["Intuition", R._int(f.attrs.get("Intuition"), 1)]]
    rank = f.rank("Perception")
    parts.append(["Perception", rank] if rank else ["Perception (untrained)", -1])
    if f.wound:
        parts.append(["Wound modifier", f.wound])
    lv = min(3, blind + SM.blinded_level(mk.get("statuses")))
    if lv:
        parts.append([f"Blinded {lv}", -BLIND_DICE * lv])
    return parts


def _roll(parts, label):
    pool = sum(p[1] for p in parts)
    res = DICE.new_roll(pool) if pool > 0 else {"dice": [], "hits": 0, "pool": 0, "glitch": False, "critical": False}
    res["label"], res["parts"] = label, parts
    return res


def _awake(mk):
    if (mk.get("statuses") or {}).get("Unconscious"):
        return False
    try:
        return X.marker_status(mk.get("cm"), mk.get("npc")) not in OUT_COLD
    except Exception:          # a marker without a usable monitor still has eyes
        return True


def is_observer(mk):
    """Who looks out for intruders: enemies and bosses, and any marker with a stat block. A plain NPC or
    contact marker without stats doesn't roll."""
    return mk.get("type") in ("danger", "boss") or bool(mk.get("npc"))


def watchers(m, tok, sight=None):
    """[(marker, view)] for the creature markers (shown or hidden from players) that can see this cell now."""
    if not tok:
        return []
    sight = sight or SM.map_sight(m, cached=True)
    cell_m = SM.cell_meters(m)
    b = (int(tok["c"]), int(tok["r"]))
    out = []
    for mk in m["data"].get("markers") or []:
        if not is_observer(mk) or not _awake(mk):
            continue
        a = (int(mk["c"]), int(mk["r"]))
        if a == b or not sight.can_see(a, b):
            continue
        vision, _x, blinded = SM.eyes_of_marker(mk)
        v = sight.view(a, b, vision, cell_m, blinded)
        if v["see"]:
            out.append((mk, v))
    return out


def check(p, m, c=None, recheck=False, sight=None):
    """Roll Perception for every enemy that can see the sneaking runner and hasn't rolled yet this attempt.
    Mutates p's stealth state and logs the rolls. Returns the names of those who noticed the runner."""
    st = state_of(p)
    tok = (((p.get("state") or {}).get("maps") or {}).get(m["id"]) or {}).get("token")
    if not st or not tok:
        return []
    if st.get("mapId") != m["id"]:
        st["mapId"], st["checked"], st["spotted"] = m["id"], [], []
    elif recheck:                      # a fresh look: whoever noticed before must notice again
        st["checked"], st["spotted"] = [], []
    checked, spotted = set(st.get("checked") or []), list(st.get("spotted") or [])
    threshold = max(1, int(st.get("hits") or 0))
    lines, found = [], []
    for mk, v in watchers(m, tok, sight):
        if mk["id"] in checked:
            continue
        checked.add(mk["id"])
        res = _roll(perception_parts(mk, v.get("blind") or 0), f"Perception + Intuition ({threshold}) to spot {p['name']}")
        noticed = res["hits"] >= threshold
        name = mk.get("label") or "An enemy"
        if noticed:
            found.append(name)
            if mk["id"] not in spotted:
                spotted.append(mk["id"])
        lines.append(f"{name}: {res['hits']} hit{'s' if res['hits'] != 1 else ''} on {res['pool']} dice, "
                     + ("notices them" if noticed else "doesn't notice"))
    st["checked"], st["spotted"] = sorted(checked), spotted
    if lines:
        add_roll(p["campaignId"], None, "GM", GM_COLOR, "note",
                 {"text": f"Stealth: {p['name']} sneaks past (threshold {threshold}). " + "; ".join(lines) + "."},
                 hidden=rolls_hidden(p["campaignId"]))
    return found


def start(p, m, c):
    """Tick Stealth: roll Stealth + Agility and check everyone already looking. Mutates p."""
    parts = stealth_parts(c)
    res = _roll(parts, "Stealth + Agility (sneaking)")
    p["state"]["stealth"] = {"on": True, "mapId": m["id"] if m else None, "hits": res["hits"], "pool": res["pool"],
                             "checked": [], "spotted": [], "at": now(), "glitch": bool(res.get("glitch"))}
    add_roll(p["campaignId"], p["id"], p["name"], p["color"], "sr", res, hidden=rolls_hidden(p["campaignId"]))
    return check(p, m, c) if m else []


def stop(p, why):
    """End stealth on a player dict. Returns True when they were sneaking."""
    if not state_of(p):
        return False
    p["state"].pop("stealth", None)
    add_roll(p["campaignId"], p["id"], p["name"], p["color"], "note", {"text": f"is no longer sneaking ({why})."})
    return True


def stop_pid(db, pid, why):
    """End a runner's stealth straight in the database (an attack inside another transaction)."""
    row = db.execute("SELECT id, campaign_id, color, state, character, username FROM players WHERE id=?", (pid,)).fetchone()
    if not row:
        return False
    state = json.loads(row["state"] or "{}")
    if not (state.get("stealth") or {}).get("on"):
        return False
    state.pop("stealth", None)
    db.execute("UPDATE players SET state=?, updated_at=? WHERE id=?", (json.dumps(state), now(), pid))
    name = (load_char(row).get("name") or "").strip() or row["username"]
    add_roll(row["campaign_id"], pid, name, row["color"], "note", {"text": f"is no longer sneaking ({why})."})
    return True


def player_info(p, m, visible_ids):
    """What the runner sees of their own stealth: whether they're sneaking, their hits (when the GM shows
    stealth rolls) and which enemies they can see have eyes on them right now."""
    st = state_of(p)
    if not st:
        return {"on": False}
    out = {"on": True}
    if not rolls_hidden(p["campaignId"]):
        out["hits"] = st.get("hits")
    tok = (((p.get("state") or {}).get("maps") or {}).get(m["id"]) or {}).get("token") if m else None
    out["watchers"] = [mk["id"] for mk, _v in watchers(m, tok) if mk["id"] in visible_ids] if tok else []
    return out


def gm_info(p):
    """The GM's view of a runner's stealth."""
    st = state_of(p)
    if not st:
        return None
    return {"hits": st.get("hits"), "pool": st.get("pool"), "mapId": st.get("mapId"),
            "checked": st.get("checked") or [], "spotted": st.get("spotted") or [], "at": st.get("at")}

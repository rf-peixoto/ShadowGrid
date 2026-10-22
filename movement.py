"""Movement in combat (core book p. 44-45 and the statuses, p. 51-54).

Move (Minor Action): 10 meters (the metatype's walking rate), one per turn.
Sprint (Major Action): 15 meters plus 1 per hit on Athletics + Agility (metatypes vary), one per turn, and
not in the same turn as a Move. Statuses: Immobilized, Restrained or out cold: no movement; Prone: 2 m and
no Sprint; Hobbled: halved (round up); Fatigued III: 5 m walking, 10 m sprinting; Zapped: no Sprint.
Surprised characters can't act in the first round.

During combat a runner's own moves are checked on the server: it must be their turn, the first move
spends their Move (a Minor Action), going past walking range turns it into a Sprint (a Major Action and the
Athletics + Agility test), and a move past their reach stops where their meters run out. The GM's moves
are never limited."""
import math

from sr import dice as DICE
from sr import rules as R

PRONE_M = 2
FATIGUED_III = (5, 10)


def _lv(statuses, name):
    v = (statuses or {}).get(name)
    if not v:
        return 0
    if v is True:
        return 1
    try:
        return int(v)
    except (TypeError, ValueError):
        return 1


def allowance(move, statuses, condition="OK", surprised=False):
    """Meters a character can cover this turn: {"walk", "sprint", "perHit", "canMove", "canSprint", "why"}.
    move: [walk, sprint base, meters per sprint hit] (from the sheet, or an NPC's "10/15/+1")."""
    walk, sprint, per_hit = (list(move) + [10, 15, 1])[:3] if move else (10, 15, 1)
    walk, sprint, per_hit = max(0, int(walk)), max(0, int(sprint)), max(0, int(per_hit))
    why = []
    can_sprint = True
    if condition in ("Unconscious", "Dying", "Dead"):
        return {"walk": 0, "sprint": 0, "perHit": 0, "canMove": False, "canSprint": False, "why": [condition.lower()]}
    for name in ("Immobilized", "Restrained", "Petrified", "Stilled"):
        if _lv(statuses, name):
            return {"walk": 0, "sprint": 0, "perHit": 0, "canMove": False, "canSprint": False, "why": [name]}
    if surprised:
        return {"walk": 0, "sprint": 0, "perHit": 0, "canMove": False, "canSprint": False, "why": ["surprised"]}
    if _lv(statuses, "Fatigued") >= 3:
        walk, sprint = min(walk, FATIGUED_III[0]), min(sprint, FATIGUED_III[1])
        why.append("Fatigued III")
    if _lv(statuses, "Prone"):
        walk, can_sprint = min(walk, PRONE_M), False
        why.append("Prone")
    if _lv(statuses, "Zapped"):
        can_sprint = False
        why.append("Zapped")
    if _lv(statuses, "Hobbled"):
        walk = math.ceil(walk / 2)                 # sprints are halved at the end (sprint_cap)
        why.append("Hobbled (halved)")
    return {"walk": walk, "sprint": sprint if can_sprint else 0, "perHit": per_hit if can_sprint else 0,
            "canMove": walk > 0, "canSprint": can_sprint and sprint > 0, "why": why, "hobbled": bool(_lv(statuses, "Hobbled"))}


def sprint_cap(a, hits):
    """Meters a Sprint covers with this many hits (Hobbled halves the whole distance, rounding up)."""
    m = a["sprint"] + hits * a["perHit"]
    return math.ceil(m / 2) if a.get("hobbled") else m


def parse_npc_move(txt):
    """"10/15/+1" -> [10, 15, 1]."""
    try:
        parts = [int(str(x).strip().lstrip("+")) for x in str(txt or "").split("/")[:3]]
        if len(parts) == 3:
            return parts
    except ValueError:
        pass
    return [10, 15, 1]


def sprint_parts(c, d):
    """Athletics + Agility (+ the Sprinting specialization), wound and status penalties."""
    parts = R._skill_parts(c, d, "Athletics", "Agility", focus="Sprinting")
    if d.get("wound_modifier"):
        parts.append(["Wound modifier", d["wound_modifier"]])
    fat = _lv(c.get("statuses"), "Fatigued")
    if fat:
        parts.append([f"Fatigued {fat}", -2 * fat])
    return parts


def state(e, rnd):
    """This round's movement on a tracker entry: {"m": meters moved, "mode": None|"move"|"sprint", "cap": m}."""
    mv = e.get("mv") or {}
    if mv.get("round") != rnd:
        return {"m": 0.0, "mode": None, "cap": 0}
    return {"m": float(mv.get("m") or 0), "mode": mv.get("mode"), "cap": float(mv.get("cap") or 0)}


def overlay(t, e, c, d, cell_m, is_turn):
    """What the player's movement overlay needs: meters left walking and sprinting this turn."""
    import fight
    a = allowance(R.move_list(d), c.get("statuses"), d.get("status"), bool(e.get("surprised")) and t.get("round") == 1)
    st = state(e, t.get("round"))
    major, minor = fight.actions_left(e)
    can_minor = minor > 0 or major > 0
    can_major = major > 0 or minor >= 4
    out = {"active": True, "yourTurn": is_turn, "cellM": cell_m, "moved": st["m"], "mode": st["mode"],
           "walk": 0, "sprint": 0, "sprintMax": 0, "why": list(a["why"]), "rolled": e.get("total") is not None}
    if not a["canMove"]:
        return out
    if st["mode"] == "move":
        out["walk"] = max(0.0, st["cap"] - st["m"])
    elif st["mode"] == "sprint":
        out["sprint"] = out["sprintMax"] = max(0.0, st["cap"] - st["m"])
    else:
        if can_minor:
            out["walk"] = a["walk"]
        elif not can_major:
            out["why"].append("no actions left")
        if a["canSprint"] and can_major:
            pool = max(0, sum(p[1] for p in sprint_parts(c, d)))
            out["sprint"] = sprint_cap(a, 0)
            out["sprintMax"] = sprint_cap(a, pool)
    return out


def combat_move(t, e, c, d, steps, cell_m, who):
    """Check (and record) a runner's move of `steps` cells on their turn. Returns (steps allowed, notes,
    rolls) or raises R.RuleError. Spends the Move or Sprint action on the tracker entry."""
    import fight
    rnd = t.get("round")
    a = allowance(R.move_list(d), c.get("statuses"), d.get("status"), bool(e.get("surprised")) and rnd == 1)
    if not a["canMove"]:
        raise R.RuleError(f"{who} can't move right now ({', '.join(a['why'])}).")
    st = state(e, rnd)
    dist = steps * cell_m
    total = st["m"] + dist
    notes, rolls = [], []
    if st["mode"] == "move":
        if total > st["cap"] + 1e-6:
            left = max(0.0, st["cap"] - st["m"])
            raise R.RuleError(f"Your Move covers {st['cap']:g} m and you have {left:g} m left this turn"
                              " (a Sprint can't follow a Move).")
    elif st["mode"] == "sprint":
        if total > st["cap"] + 1e-6:
            steps = int(max(0.0, st["cap"] - st["m"]) // cell_m)
            if steps <= 0:
                raise R.RuleError(f"You've used your Sprint ({st['cap']:g} m) this turn.")
            notes.append(f"stops after {steps * cell_m:g} m (end of the Sprint)")
    elif total <= a["walk"] + 1e-6:
        fight.spend_action(e, "minor", "Move")
        st = {"m": st["m"], "mode": "move", "cap": float(a["walk"])}
        notes.append(f"Move ({a['walk']:g} m)")
    else:
        if not a["canSprint"]:
            raise R.RuleError(f"That's {dist:g} m: walking takes you {a['walk']:g} m"
                              + (f" ({', '.join(a['why'])})" if a["why"] else "") + " and you can't Sprint.")
        fight.spend_action(e, "major", "Sprint")
        parts = sprint_parts(c, d)
        pool = sum(p[1] for p in parts)
        res = DICE.new_roll(pool) if pool > 0 else {"dice": [], "hits": 0, "pool": 0, "glitch": False, "critical": False}
        cap = sprint_cap(a, res["hits"])
        res["label"] = "Sprint (Athletics + Agility)"
        res["parts"] = parts
        rolls.append(res)
        st = {"m": st["m"], "mode": "sprint", "cap": float(cap)}
        notes.append(f"Sprint: {res['hits']} hits, {cap:g} m")
        if total > cap + 1e-6:
            steps = int(max(0.0, cap - st["m"]) // cell_m)
            notes.append(f"stops after {steps * cell_m:g} m")
    st["m"] = st["m"] + steps * cell_m
    e["mv"] = {"round": rnd, "m": st["m"], "mode": st["mode"], "cap": st["cap"]}
    return steps, notes, rolls

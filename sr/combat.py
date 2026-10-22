"""Combat for the GM's map: NPC stat blocks (core-book templates), attack
resolution (attack -> defense -> soak -> condition monitor), and helpers for
the initiative tracker.

Combatants are either player characters (sheet dicts, handled through
sr.rules) or map markers carrying an ``npc`` stat block and a ``cm`` monitor.
"""
import math
import re

from . import actions6e as ACT
from . import catalog as CAT
from . import core6e as K
from . import dice as DICE
from . import gear6e as G
from . import magic6e as M
from . import matrix6e as MX
from . import rigging6e as RIG
from . import npc6e as N
from . import rules as R

ATTR_KEYS = {"B": "Body", "A": "Agility", "R": "Reaction", "S": "Strength", "W": "Willpower",
             "L": "Logic", "I": "Intuition", "C": "Charisma", "M": "Magic", "RES": "Resonance"}
ELEMENT_STATUS = {"Electricity": ("Zapped", None), "Fire": ("Burning", 3), "Cold": ("Chilled", None),
                  "Chemical": ("Corrosive", 3)}


def _int(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def _lead_int(s, d=0):
    """'5(7)' -> 7 (augmented value), '14(18)' -> 18, '4 (Armor: 1)' -> 4."""
    s = str(s or "")
    m = re.match(r"^\s*(\d+)\s*\((\d+)\)", s)
    if m:
        return int(m.group(2))
    m = re.match(r"^\s*(\d+)", s)
    return int(m.group(1)) if m else d


def _split_top(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def parse_skills(s):
    """'Firearms 8 (Automatic Rifles +2), Perception 7' -> {skill: rank}, {skill: [(spec, bonus)]}."""
    ranks, specs = {}, {}
    for part in _split_top(str(s or "")):
        m = re.match(r"^([A-Za-z][A-Za-z ']*?)\s+(\d+)(.*)$", part)
        if not m:
            continue
        name = m.group(1).strip()
        ranks[name] = int(m.group(2))
        for sm in re.finditer(r"\(([^()]+?)\s*\+(\d)\)", m.group(3)):
            specs.setdefault(name, []).append([sm.group(1).strip(), int(sm.group(2))])
    return ranks, specs


WEAPON_SKILL_WORDS = [
    (("launcher", "missile", "rocket"), "Exotic Weapons"),
    (("pistol", "hold-out", "holdout", "smg", "submachine", "rifle", "shotgun", "machine gun", "taser", "carbine"), "Firearms"),
    (("thrown", "throwing", "grenade", "bow"), "Athletics"),
]


def weapon_skill(category, name=""):
    t = f"{category} {name}".lower()
    for words, skill in WEAPON_SKILL_WORDS:
        if any(w in t for w in words):
            return skill
    return "Close Combat"


def parse_weapon(s):
    """One weapon line of a stat block -> attack profile."""
    s = str(s or "").strip()
    count = 1
    m = re.match(r"^(\d+)\s*x\s+(.*)$", s)
    if m:
        count, s = int(m.group(1)), m.group(2)
    name = re.split(r"\s*[\[(:]", s, maxsplit=1)[0].strip() or "Attack"
    cat = ""
    m = re.search(r"\[([^,\]]+)", s)
    if m:
        cat = m.group(1).strip()
    g = re.search(r"DV:?\s*(\d+)\s*([PS])\s*,\s*(\d+)\s*([PS])\s*,\s*(\d+)\s*([PS]).*?Blast:?\s*(\d+)\s*m", s)
    if g:
        return {"name": name, "skill": "Athletics", "dv": int(g.group(1)), "type": g.group(2), "element": "",
                "ar": [8, 8, 4, None, None], "modes": [], "grenade": [g.group(1) + g.group(2), g.group(3) + g.group(4), g.group(5) + g.group(6)],
                "blast": g.group(7) + "m", "count": count, "category": "Grenade"}
    m = re.search(r"DV:?\s*(\d+)\s*([PS])\s*(\(?[ef]\)?)?", s)
    dv, dtype, flag = (int(m.group(1)), m.group(2), (m.group(3) or "").strip("()")) if m else (0, "P", "")
    m = re.search(r"((?:\d+\*?|—)\s*/\s*(?:\d+\*?|—)\s*/\s*(?:\d+\*?|—)\s*/\s*(?:\d+\*?|—)\s*/\s*(?:\d+\*?|—))", s)
    ar = CAT.parse_ar(m.group(1).replace(" ", "")) if m else [None] * 5
    modes = []
    m = re.search(r"\b((?:SS|SA|BF|FA)(?:/(?:SS|SA|BF|FA))*)\b", s)
    if m:
        modes = m.group(1).split("/")
    return {"name": name, "skill": weapon_skill(cat, name), "dv": dv, "type": dtype,
            "element": "Electricity" if flag == "e" else "", "ar": ar, "modes": modes, "count": count, "category": cat}


def parse_template(t):
    """A core-book stat block (sr.npc6e) -> numeric NPC sheet used by markers."""
    attrs = {}
    for k, v in (t.get("attrs") or {}).items():
        if k == "Essence":
            continue
        attrs[k] = _lead_int(v, 0) if str(v).strip() not in ("*", "") else 0
    for a in K.PHYSICAL + K.MENTAL:
        attrs.setdefault(a, 1)
    kind = t.get("kind") or "Grunt"
    ranks, specs = parse_skills(t.get("skills"))
    cm_txt = str(t.get("cm") or "")
    grunt = kind == "Grunt"
    if "/" in cm_txt:
        pm, sm = (_lead_int(x) for x in cm_txt.split("/")[:2])
    elif cm_txt:
        pm, sm = _lead_int(cm_txt), 0
    else:
        pm, sm = 8 + (attrs["Body"] + 1) // 2, 8 + (attrs["Willpower"] + 1) // 2
    if not grunt and not sm and kind != "Grunt":
        sm = 8 + (attrs["Willpower"] + 1) // 2
    init = str(t.get("init") or "")
    m = re.match(r"^\s*(\d+)\s*/\s*(\d+)", init)
    init_score, init_dice = (int(m.group(1)), int(m.group(2))) if m else (attrs["Reaction"] + attrs["Intuition"], 1)
    dr_txt = t.get("dr") or t.get("defense_rating") or ""
    dr = _lead_int(dr_txt, attrs["Body"])
    notes = []
    for k in ("augmentations", "gear", "powers", "spells", "complex_forms", "metamagics", "weaknesses", "knowledge_skills", "notes", "note", "initiate"):
        if t.get(k):
            notes.append(f"{k.replace('_', ' ').capitalize()}: {t[k]}")
    return {
        "template": t.get("name"), "kind": kind, "pr": t.get("pr"), "attrs": attrs,
        "dr": dr, "init": init_score, "init_dice": max(1, min(5, init_dice)),
        "grunt": grunt, "edge": t.get("pr") if grunt else min(7, attrs.get("Edge", 2) or 2),
        "skills": ranks, "specs": specs, "move": t.get("move") or "10/15/+1",
        "weapons": [parse_weapon(w) for w in t.get("weapons") or []],
        "notes": "\n".join(notes)[:4000], "pm": pm, "sm": sm,
    }


def spirit_npc(kind, force):
    s = R.spirit_stats(kind, force)
    attrs = {k: v for k, v in s["attrs"].items() if k != "Essence"}
    weapons = []
    for a in s["attacks"]:
        dvp = CAT.parse_dv(a["dv"]) or (0, "P", "")
        weapons.append({"name": a["name"], "skill": "Close Combat" if "Elemental" not in a["name"] else "Exotic Weapons",
                        "dv": dvp[0], "type": dvp[1], "element": "Fire" if "Fire" in a["name"] else "",
                        "ar": CAT.parse_ar(a["ar"]), "modes": [], "count": 1, "category": "Spirit"})
    return {"template": f"{kind} spirit (Force {s['force']})", "kind": "Spirit", "pr": None, "attrs": attrs,
            "dr": s["dr"], "init": s["init"], "init_dice": s["init_dice"], "grunt": False, "edge": 0,
            "skills": s["skills"], "specs": {}, "move": s["move"], "weapons": weapons,
            "notes": "Powers: " + ", ".join(s["powers"]) + (f"\nOptional powers ({s['optional_count']}): " + ", ".join(s["optional"]) if s["optional_count"] else ""),
            "pm": s["cm"], "sm": s["cm"], "force": s["force"]}


def ic_npc(kind, rating):
    """IC for a host of this rating (p. 186): Host Rating x 2 for its attack rolls, Attack Rating and Condition
    Monitor; (Data Processing x 2) + 3D6 Initiative. Its Defense Rating is the host's (rating x 2)."""
    r = max(1, min(12, _int(rating, 3)))
    t = MX.IC_TYPES[kind]
    attrs = {a: r for a in K.PHYSICAL + K.MENTAL}
    weapons = [{"name": f"{kind} attack", "skill": "Cracking", "dv": r if t["damage"] else 0, "type": "M", "element": "",
                "ar": [r * 2] * 5, "modes": [], "count": 1, "category": "IC", "matrix": True, "ic": kind,
                "biofeedback": "sim" if t["damage"] in ("both", "bio") else None,
                "pool": r * 2, "pool_label": "Host rating × 2"}]
    pm = r * MX.IC_CM_PER_RATING
    dfn = " + ".join(t["defense"]) if t["defense"] else "no test"
    return {"template": f"{kind} (host rating {r})", "kind": "IC", "pr": None, "attrs": attrs, "dr": r * 2, "init": r * 2,
            "init_dice": MX.IC_INIT_DICE, "grunt": False, "edge": 0, "skills": {"Cracking": r, "Electronics": r}, "specs": {}, "move": "—",
            "weapons": weapons, "notes": f"{kind}: {t['effect']}\nThe target defends with {dfn}.\nInitiative: (Data Processing x 2) + 3D6.",
            "pm": pm, "sm": 0, "force": r, "matrix": {"rating": r}}


VEHICLES = [e for e in CAT.ITEMS if e.get("cat") in ("Vehicles", "Drones") and e.get("handling")]
VEHICLE_BY_ID = {e["id"]: e for e in VEHICLES}


def vehicle_npc(v, name=None, link=None):
    """A vehicle or drone on the map: one Condition Monitor of (Body / 2) + 8, Defense Rating Pilot + Armor,
    soaks with Body, rams for its Body in DV. ``link`` ties it to a runner's own vehicle (damage is shared)."""
    body, armor, pilot = _int(v.get("body"), 1), _int(v.get("armor")), _int(v.get("pilot"))
    drone = v.get("cat") == "Drones"
    attrs = {a: max(1, pilot) for a in K.PHYSICAL + K.MENTAL}
    attrs["Body"] = max(1, body)
    attrs["Strength"] = max(1, body)
    sensor = _int(v.get("sensor"))
    ram = {"name": RIG.RAM["name"], "skill": "Piloting", "dv": (body + 1) // 2, "type": "P", "element": "",
           "ar": [pilot + sensor, None, None, None, None], "modes": [], "count": 1, "category": "Ram",
           "pool": pilot * 2, "pool_label": "Pilot + Maneuvering (set the dice for a driver's Piloting + Reaction)"}
    return {"template": name or v.get("name"), "kind": "Drone" if drone else "Vehicle", "pr": None, "attrs": attrs,
            "dr": pilot + armor, "init": pilot * 2, "init_dice": RIG.DRONE_INIT_DICE if drone else 1, "grunt": False, "edge": 0,
            "skills": {"Piloting": pilot, "Perception": _int(v.get("sensor"))}, "specs": {},
            "move": f"Speed {v.get('speed_interval')}/{v.get('top_speed')} · Accel {v.get('accel')}",
            "weapons": [ram],
            "notes": (f"{v.get('sub', '')}. Handling {v.get('handling')}, Sensor {v.get('sensor')}, Seats {v.get('seats', '—')}.\n"
                      "Stun damage with a DV up to its Body does nothing; above that it counts as Physical. "
                      "Damage raises its Handling by 1 per 3 boxes. Ram: add +1 DV per current Speed Interval (Extra DV). "
                      "A driver uses their own Piloting for Defense Rating (Piloting + Armor) and ramming (Piloting + Sensor)."),
            "pm": RIG.MONITOR_BASE + (body + 1) // 2, "sm": 0, "force": None,
            "matrix": {"rating": max(1, pilot)},
            "vehicle": {k: str(v.get(k, "")) for k in ("handling", "accel", "speed_interval", "top_speed", "body", "armor", "pilot", "sensor", "seats")},
            "link": link}


def templates():
    """Template list for the GM's picker."""
    out = [{"key": f"t:{i}", "name": t["name"], "kind": t.get("kind"), "pr": t.get("pr")}
           for i, t in enumerate(N.NPC_TEMPLATES)]
    out += [{"key": f"s:{k}", "name": f"{k} spirit", "kind": "Spirit", "pr": None, "force": True} for k in M.SPIRITS]
    out += [{"key": f"ic:{k}", "name": f"{k} IC", "kind": "IC", "pr": None, "force": True, "forceLabel": "Host rating"} for k in MX.IC]
    out += [{"key": f"v:{e['id']}", "name": f"{e['name']} ({e.get('sub')})", "kind": "Drone" if e["cat"] == "Drones" else "Vehicle", "pr": None}
            for e in VEHICLES]
    return out


def npc_from_key(key, force=None):
    key = str(key or "")
    if key.startswith("t:"):
        i = _int(key[2:], -1)
        if 0 <= i < len(N.NPC_TEMPLATES):
            return parse_template(N.NPC_TEMPLATES[i])
    if key.startswith("s:") and key[2:] in M.SPIRITS:
        return spirit_npc(key[2:], force or 3)
    if key.startswith("ic:") and key[3:] in MX.IC:
        return ic_npc(key[3:], force or 3)
    if key.startswith("v:") and key[2:] in VEHICLE_BY_ID:
        return vehicle_npc(VEHICLE_BY_ID[key[2:]])
    raise R.RuleError("Unknown template.")


VISION_TYPES = ("Low-light", "Thermographic", "Ultrasound")
_VISION_WORDS = (("low-light", "Low-light"), ("lowlight", "Low-light"), ("thermographic", "Thermographic"),
                 ("thermo vision", "Thermographic"), ("ultrasound", "Ultrasound"))


def npc_vision(npc, marker=None):
    """An NPC's vision: what the GM set, else read from the stat block (metatype words in its name, label or
    notes: orks and elves see in low light, dwarfs and trolls in thermographic; and any vision gear,
    cyberware or critter powers mentioned)."""
    npc = npc or {}
    if isinstance((marker or {}).get("vision"), list):
        return [v for v in VISION_TYPES if v in marker["vision"]]
    if isinstance(npc.get("vision"), list):
        return [v for v in VISION_TYPES if v in npc["vision"]]
    text = " ".join(str(x) for x in (npc.get("template"), npc.get("notes"), (marker or {}).get("label")) if x).lower()
    out = {v for w, v in _VISION_WORDS if w in text}
    if re.search(r"\b(orks?|elf|elves|elven)\b", text):
        out.add("Low-light")
    if re.search(r"\b(trolls?|dwarfs?|dwarves)\b", text):
        out.add("Thermographic")
    return [v for v in VISION_TYPES if v in out]


def clean_npc(v):
    """Sanitize an NPC stat block coming from the editor."""
    if not isinstance(v, dict):
        return None
    raw = v.get("attrs") or {}
    attrs = {a: max(0, min(30, _int(raw.get(a), 1))) for a in K.PHYSICAL + K.MENTAL}
    for a in ("Magic", "Resonance", "Edge"):
        if _int(raw.get(a)):
            attrs[a] = max(0, min(30, _int(raw.get(a))))
    weapons = []
    for w in (v.get("weapons") or [])[:20]:
        if not isinstance(w, dict):
            continue
        ar = [None if x in (None, "", "—") else max(0, min(40, _int(x))) for x in (w.get("ar") or [None] * 5)[:5]]
        while len(ar) < 5:
            ar.append(None)
        weapons.append({"name": str(w.get("name") or "Attack")[:60], "skill": w.get("skill") if w.get("skill") in K.SKILLS else "Close Combat",
                        "dv": max(0, min(40, _int(w.get("dv")))), "type": "S" if w.get("type") == "S" else "P",
                        "element": w.get("element") if w.get("element") in ELEMENT_STATUS else "",
                        "ar": ar, "modes": [m for m in (w.get("modes") or []) if m in G.FIRING_MODES][:4],
                        "grenade": [str(x)[:6] for x in (w.get("grenade") or [])][:3] or None,
                        "blast": str(w.get("blast") or "")[:8], "count": max(0, min(99, _int(w.get("count"), 1))),
                        "category": str(w.get("category") or "")[:30],
                        "matrix": bool(w.get("matrix")), "biofeedback": w.get("biofeedback") if w.get("biofeedback") in ("S", "P", "sim") else None,
                        "pool": max(0, min(60, _int(w.get("pool")))) or None, "pool_label": str(w.get("pool_label") or "")[:40] or None,
                        "mount": w.get("mount") if w.get("mount") in ("standard", "heavy") else None})
    skills = {}
    for k, r in (v.get("skills") or {}).items():
        if isinstance(k, str) and len(k) <= 40:
            skills[k] = max(0, min(20, _int(r)))
    specs = {}
    for k, lst in (v.get("specs") or {}).items():
        if isinstance(k, str) and isinstance(lst, list):
            specs[k[:40]] = [[str(x[0])[:40], max(0, min(3, _int(x[1])))] for x in lst[:4] if isinstance(x, list) and len(x) == 2]
    return {"template": str(v.get("template") or "")[:80], "kind": str(v.get("kind") or "Grunt")[:20],
            "pr": None if v.get("pr") is None else max(0, min(10, _int(v.get("pr")))), "attrs": attrs,
            "dr": max(0, min(60, _int(v.get("dr")))), "init": max(0, min(60, _int(v.get("init")))),
            "init_dice": max(1, min(5, _int(v.get("init_dice"), 1))), "grunt": bool(v.get("grunt")),
            "edge": max(0, min(10, _int(v.get("edge")))), "skills": skills, "specs": specs,
            "move": str(v.get("move") or "")[:48], "weapons": weapons, "notes": str(v.get("notes") or "")[:4000],
            "vision": [x for x in VISION_TYPES if x in v["vision"]] if isinstance(v.get("vision"), list) else None,
            "force": _int(v.get("force")) or None,
            "matrix": {"rating": max(0, min(12, _int((v.get("matrix") or {}).get("rating"))))} if isinstance(v.get("matrix"), dict) else None,
            "vehicle": _clean_vehicle(v.get("vehicle")),
            "link": {"pid": str(v["link"].get("pid"))[:40], "uid": str(v["link"].get("uid"))[:20]} if isinstance(v.get("link"), dict) else None}


def _clean_vehicle(v):
    if not isinstance(v, dict):
        return None
    keys = ("handling", "accel", "speed_interval", "top_speed", "body", "armor", "pilot", "sensor", "seats", "speed")
    return {k: str(v.get(k) or "")[:12] for k in keys}


# ---- vehicles in combat: speed and mounted weapons
def marker_speed_penalty(npc, owner_item=None):
    """Speed Interval dice penalty of a vehicle marker (a runner's own vehicle: from their sheet)."""
    if owner_item is not None:
        return R.speed_penalty(owner_item)
    v = (npc or {}).get("vehicle") or {}
    return R.speed_penalty({"speed": _int(v.get("speed")), "speed_interval": _int(v.get("speed_interval"))})


def catalog_mount_weapon(e, sensor, autosoft_rating):
    """A store weapon mounted on an NPC vehicle or drone: it fires with Sensor + Targeting autosoft
    (Sensor − 1 without the autosoft), the weapon's own DV, Attack Rating and firing modes."""
    dvs = str(e.get("dv") or "0P")
    m = re.match(r"^(\d+)\s*([PS])?", dvs)
    dv, typ = (int(m.group(1)), m.group(2) or "P") if m else (0, "P")
    rating = max(0, _int(autosoft_rating))
    pool = max(0, _int(sensor) + rating) if rating else max(0, _int(sensor) - 1)
    label = f"Sensor + Targeting {rating}" if rating else "Sensor − 1 (no Targeting autosoft)"
    return {"name": e["name"], "skill": e.get("skill") or "Firearms", "dv": dv, "type": typ,
            "element": "Electricity" if "(e)" in dvs else "", "ar": CAT.parse_ar(e.get("ar")),
            "modes": CAT.modes_list(e.get("modes")), "count": 1, "category": "Mounted " + (e.get("sub") or ""),
            "pool": pool, "pool_label": label, "mount": "heavy" if e.get("sub") in RIG.HEAVY_MOUNT_WEAPONS else "standard"}


def mount_profile(owner_c, wuid, mode, rng, gunner, gunner_c=None):
    """A runner's weapon in a mount on their vehicle or drone. gunner=True: fired by a person (a jumped-in
    rigger or someone at the controls): Engineering + Logic. Otherwise the drone fires it on its own:
    [Weapon] Targeting autosoft + Sensor (Sensor − 1 without the autosoft). Speed Interval penalties apply."""
    w = R.find_item(owner_c, wuid)
    mnt, v = R.mount_vehicle(owner_c, w)
    if not v:
        raise R.RuleError(f"The {w['name']} isn't in a weapon mount.")
    d = R.derive(owner_c)
    p = R.weapon_profile(owner_c, d, dict(w, equipped=True), mode, rng)
    if not p:
        raise R.RuleError(f"The {w['name']} can't be fired from the mount.")
    if gunner:
        gc = gunner_c if gunner_c is not None else owner_c
        sk, attr = RIG.GUNNERY["manual"]
        parts = R._skill_parts(gc, R.derive(gc), sk, attr=attr) or [[attr, R.derive(gc)["attributes"][attr]], [f"{sk} (untrained)", -1]]
        who = "gunner"
    else:
        rating, sensor = R.autosoft(owner_c, "Targeting"), _int(v.get("sensor"))
        parts = [["Sensor", sensor], ["Targeting autosoft", rating]] if rating else [["Sensor", sensor], ["No Targeting autosoft", -1]]
        who = "drone"
    parts = [list(x) for x in parts]
    pen = R.speed_penalty(v)
    if pen:
        parts.append([f"Speed {_int(v.get('speed'))} m/round", pen])
    return {"name": f"{w['name']} ({v['name']} mount)", "parts": parts, "ar": p["ar"], "dv": p["dv"], "type": p["type"],
            "element": p["element"], "mode": p["mode"], "uid": w["uid"], "melee": False, "mounted": who,
            **_shot_kind(w["name"], p["skill"])}


def npc_cm(npc):
    """Fresh marker monitor for an NPC: grunts have one track (pm), others Physical + Stun."""
    if npc.get("grunt"):
        return {"pm": npc["pm"], "sm": 0, "ov": 0, "p": 0, "s": 0, "grunt": True}
    return {"pm": npc["pm"], "sm": npc["sm"], "ov": 0 if npc.get("kind") in ("Spirit", "IC", "Vehicle", "Drone") else npc["attrs"].get("Body", 1) * 2,
            "p": 0, "s": 0}


# --------------------------------------------------------------------------- marker monitors
def marker_wound(cm):
    if not cm:
        return 0
    if cm.get("grunt"):
        return -(min(cm["p"], cm["pm"]) // 2)
    return -(min(cm.get("p", 0), cm.get("pm", 0)) // 3 + min(cm.get("s", 0), cm.get("sm", 0)) // 3)


def marker_status(cm, npc=None):
    if not cm:
        return "OK"
    if cm.get("grunt"):
        if cm["p"] >= cm["pm"]:
            return "Dying" if cm.get("last") == "P" else "Unconscious"
        if npc and npc.get("pr") is not None and cm["p"] > npc["pr"]:
            return "Shaken"
        return "Wounded" if cm["p"] else "OK"
    if cm["p"] >= cm["pm"] + cm.get("ov", 0) and cm["pm"]:
        return "Dead"
    if cm["p"] >= cm["pm"] and cm["pm"]:
        return "Dying"
    if cm.get("sm") and cm["s"] >= cm["sm"]:
        return "Unconscious"
    return "Wounded" if marker_wound(cm) else "OK"


def marker_damage(cm, track, amount):
    """Apply +/- boxes to a marker monitor (grunts: one track; others: Stun overflows into Physical)."""
    amount = _int(amount)
    if cm.get("grunt"):
        cm["p"] = max(0, min(cm["pm"], cm["p"] + amount))
        if amount > 0:
            cm["last"] = "S" if track == "stun" else "P"
        return
    cap = cm["pm"] + cm.get("ov", 0)
    if track == "stun" and cm.get("sm"):
        v = max(0, cm["s"] + amount)
        if v > cm["sm"]:
            cm["p"] = min(cap, cm["p"] + (v - cm["sm"]))
            v = cm["sm"]
        cm["s"] = v
    else:
        cm["p"] = max(0, min(cap, cm["p"] + amount))


# --------------------------------------------------------------------------- combatants
class Fighter:
    """Uniform view over a player character or an NPC marker for combat math."""

    def __init__(self, name, attrs, dr, wound, skills=None, specs=None, char=None, derived=None, npc=None, cm=None, statuses=None, marker=None):
        self.name, self.attrs, self.dr, self.wound = name, attrs, dr, wound
        self.skills, self.specs = skills or {}, specs or {}
        self.char, self.d, self.npc, self.cm = char, derived, npc, cm
        self.statuses = statuses or {}
        self.marker = marker
        self.entry = None            # initiative tracker entry, when in combat

    @classmethod
    def from_char(cls, name, c):
        d = R.derive(c)
        skills = {k: v for k, v in (c.get("skills") or {}).items() if v}
        return cls(name, d["attributes"], d["defense_rating"], d["wound_modifier"], skills=skills, char=c, derived=d,
                   statuses=c.get("statuses") or {})

    @classmethod
    def from_marker(cls, mk):
        npc = mk.get("npc") or {"attrs": {}, "dr": 0, "skills": {}, "specs": {}}
        attrs = {a: _int((npc.get("attrs") or {}).get(a), 1) for a in K.PHYSICAL + K.MENTAL + ["Magic", "Resonance"]}
        return cls(mk.get("label") or "Enemy", attrs, _int(npc.get("dr")), marker_wound(mk.get("cm")),
                   skills=npc.get("skills"), specs=npc.get("specs"), npc=npc, cm=mk.get("cm"), statuses=mk.get("statuses") or {}, marker=mk)

    @property
    def vision(self):
        """Vision types (Low-light, Thermographic, Ultrasound) and extras (Magnification, Flare compensation)."""
        if self.char is not None:
            return list(self.d.get("vision") or []), list(self.d.get("vision_extras") or [])
        return npc_vision(self.npc, self.marker), []

    def rank(self, skill):
        r = _int((self.skills or {}).get(skill))
        if not r and self.npc and self.npc.get("kind") == "Spirit" and skill in ("Close Combat", "Astral", "Exotic Weapons", "Perception"):
            r = _int(self.npc.get("force"))
        return r

    def status(self, name):
        """0 when absent, the level or number when it has one, 1 otherwise."""
        v = (self.statuses or {}).get(name)
        if not v:
            return 0
        return 1 if v is True else _int(v, 1)

    # Edge: runners use their sheet; NPC markers keep a running pool (grunt groups start at their PR)
    def edge(self):
        if self.char is not None:
            return _int(self.char.get("current_edge"))
        if self.marker is not None:
            return _int(self.marker.get("edge_cur"), _int((self.npc or {}).get("edge")))
        return 0

    def spend_edge(self, n, why):
        if n <= 0:
            return
        if self.status("Dazed"):
            raise R.RuleError(f"{self.name} is Dazed and can't spend Edge.")
        if self.edge() < n:
            raise R.RuleError(f"{self.name} needs {n} Edge for {why} (has {self.edge()}).")
        if self.char is not None:
            self.char["current_edge"] = self.edge() - n
        elif self.marker is not None:
            self.marker["edge_cur"] = self.edge() - n

    def gain_edge(self, n=1):
        """Gain Edge up to the cap; returns what was actually gained."""
        if self.status("Dazed"):
            return 0
        if self.char is not None:
            cap = min(R.EDGE_CAP, self.d["edge_max"]) if self.d else R.EDGE_CAP
            new = min(cap, self.edge() + n)
            got = new - self.edge()
            self.char["current_edge"] = new
            return got
        if self.marker is not None:
            new = min(R.EDGE_CAP, self.edge() + n)
            got = new - self.edge()
            self.marker["edge_cur"] = new
            return got
        return 0

    # ---- Matrix
    def matrix_rating(self):
        return _int(((self.npc or {}).get("matrix") or {}).get("rating"))

    def matrix_defense(self):
        if self.char is not None:
            mx = self.d["matrix"]
            if not mx.get("device"):
                raise R.RuleError(f"{self.name} isn't on the Matrix (no active device).")
            parts = [["Data Processing", mx["data_processing"]], ["Firewall", mx["firewall"]]]
            if mx.get("penalty"):
                parts.append(["Matrix damage on the device", mx["penalty"]])
            return parts
        r = self.matrix_rating()
        if not r:
            raise R.RuleError(f"{self.name} has no Matrix presence (give it an IC or device template).")
        return [["Rating × 2", r * 2]]

    def matrix_pool(self, names):
        """Defense pool named by attributes, e.g. ["Intuition", "Firewall"] (IC defenses)."""
        keys = {"Attack": "attack", "Sleaze": "sleaze", "Data Processing": "data_processing", "Firewall": "firewall",
                "Device Rating": "device_rating"}
        parts = []
        for n in names:
            if n in keys:
                if self.char is not None:
                    mx = self.d["matrix"]
                    if not mx.get("device"):
                        raise R.RuleError(f"{self.name} isn't on the Matrix (no active device).")
                    parts.append([n, _int(mx.get(keys[n]))])
                else:
                    parts.append([n, self.matrix_rating()])
            else:
                parts.append([n, _int(self.attrs.get(n), 1)])
        return parts

    def matrix_dr(self):
        if self.char is not None:
            return self.d["matrix"].get("dr", 0)
        return self.matrix_rating() * 2

    def astral_dr(self):
        """Astral Defense Rating: Intuition (+ a spirit's Force as innate armor)."""
        dr = _int(self.attrs.get(ACT.ASTRAL["dr"]), 1)
        if self.npc and self.npc.get("kind") == "Spirit":
            dr += _int(self.npc.get("force"))
        return dr

    def matrix_firewall(self):
        if self.char is not None:
            return self.d["matrix"].get("firewall", 0)
        return self.matrix_rating()

    def matrix_soak(self):
        """Matrix damage isn't resisted (core p. 179) unless the Biofeedback Filter program runs:
        then roll Device Rating or Body, whichever is higher."""
        if self.char is not None and R.program_running(self.d, "Biofeedback Filter"):
            mx = self.d["matrix"]
            body = _int(self.attrs.get("Body"), 1)
            dr = _int(mx.get("device_rating"))
            return [["Biofeedback Filter: Body", body]] if body >= dr else [["Biofeedback Filter: Device Rating", dr]]
        return []

    def defense_pool(self):
        parts = [["Reaction", self.attrs.get("Reaction", 1)], ["Intuition", self.attrs.get("Intuition", 1)]]
        if self.char is not None:
            cs = R.power_level(self.char, "Combat Sense") if self.char.get("magic_type") in ("Adept", "Mystic Adept") else 0
            if cs:
                parts.append(["Combat Sense", cs])
        return parts

    def soak_pool(self):
        parts = [["Body", self.attrs.get("Body", 1)]]
        if self.char is not None:
            parts += [[it["name"], _int(it.get("soak"))] for it in R.implants(self.char) if _int(it.get("soak"))]
        return parts

    def npc_attack_parts(self, w):
        skill = w.get("skill") or "Close Combat"
        rank = _int(self.skills.get(skill))
        if self.npc and self.npc.get("kind") == "Spirit" and not rank:
            rank = _int(self.npc.get("force"))
        parts = [["Agility", self.attrs.get("Agility", 1)]]
        parts.append([skill, rank] if rank else [f"{skill} (untrained)", -1])
        cat = (w.get("category") or w.get("name") or "").lower()
        for spec, bonus in self.specs.get(skill, []):
            words = [x for x in re.split(r"\W+", spec.lower()) if len(x) > 3]
            if any(x.rstrip("s") in cat for x in words):
                parts.append([f"Specialization ({spec})", bonus])
                break
        return parts


def _total(parts):
    return max(0, sum(p[1] for p in parts))


def _status_value(spec, level):
    """"+#" -> +level, "-2#" -> -2 x level, ints as they are."""
    if isinstance(spec, str):
        sign = -1 if spec.startswith("-") else 1
        mult = spec.strip("+-#") or "1"
        return sign * int(mult) * level
    return spec


def status_parts(f, key, ranged=False):
    """Dice (or DR / AR / initiative) modifiers from a combatant's statuses for one kind of test."""
    out = []
    for name, mod in ACT.STATUS_MODS.items():
        lv = f.status(name)
        if not lv or key not in mod or name == "Cover":
            continue
        if mod.get("ranged_only") and not ranged:
            continue
        v = _status_value(mod[key], lv)
        if v:
            out.append([name + (f" {lv}" if isinstance(f.statuses.get(name), int) and not isinstance(f.statuses.get(name), bool) else ""), v])
    return out


def sustain_parts(f, physical=False):
    """Sustained spells and drugs in effect (runners only)."""
    if f.char is None:
        return []
    n = R.sustain_count(f.char)
    out = [[f"Sustaining {n} spell{'s' if n > 1 else ''}", n * R.sustain_step(f.char)]] if n else []
    return out + R.substance_parts(f.char, physical=physical)


def interrupt_ok(key, weapon):
    """Can this defensive interrupt be used against this attack? -> (ok, reason)."""
    it = ACT.INTERRUPTS.get(key)
    if not it:
        return False, "Unknown defense action."
    if weapon.get("matrix") and key != "full_defense":
        return False, f"{it['name']} doesn't help in the Matrix (Full Matrix Defense does)."
    if weapon.get("spell") and weapon.get("direct") and key != "full_defense":
        return False, f"{it['name']} doesn't help against a direct spell."
    melee = bool(weapon.get("melee"))
    if it["vs"] == "melee" and not melee:
        return False, f"{it['name']} only works against melee attacks."
    if it["vs"] == "ranged" and melee:
        return False, f"{it['name']} only works against ranged attacks."
    return True, ""


def _interrupt_dice(f, key):
    add = ACT.INTERRUPTS[key]["add"]
    if isinstance(add, int):
        return add
    kind, name = add.split(":", 1)
    return f.rank(name) if kind == "skill" else _int(f.attrs.get(name), 1)


def resolve_attack(att, weapon, target, opts):
    """Roll an attack, the defense and the soak. Returns a result dict (no state is changed here).

    ``weapon``: {"name", "parts", "ar" (list), "dv", "type", "element", "mode", "direct", "spell", "melee", "astral"}
    ``opts``: range, attack_mod, defense_mod, soak_mod, wild, extra_dv, unopposed,
              defense (interrupt key), full_defense (bool, already active), cover (0-4), called (key),
              split (number of targets sharing the pool), counterspell ([name, hits] protecting the target),
              dirt (attacker penalty), att_cover (attacker's Cover level), edge_action (key of ACT.EDGE_ACTIONS),
              astral_type ("P"/"S", the attacker's choice in astral combat), aim (Take Aim dice), trip (bool),
              grapple (bool: hold instead of damage), tactical_att / tactical_def (Tactical Roll on the attacker /
              the target), attack_roll (reuse this attack roll: a missed attack on a restrained target hitting the grappler)
    """
    rng = opts.get("range") if opts.get("range") in G.RANGES else "Near"
    ri = G.RANGES.index(rng)
    ar_list = weapon.get("ar") or [None] * 5
    ar = ar_list[ri] if ri < len(ar_list) else None
    if ar is None and not weapon.get("spell") and not weapon.get("astral"):
        raise R.RuleError(f"The {weapon['name']} can't attack at {rng} range.")
    melee = bool(weapon.get("melee"))
    ranged = not melee and not weapon.get("astral")
    called = ACT.CALLED_SHOTS.get(opts.get("called") or "")
    eact = ACT.EDGE_ACTIONS.get(opts.get("edge_action") or "")
    astral = bool(weapon.get("astral"))

    # ---- attack pool
    a_parts = [list(p) for p in weapon["parts"]]
    if att.wound:
        a_parts.append(["Wound modifier", att.wound])
    a_parts += sustain_parts(att, physical=any(p[0] in K.PHYSICAL for p in a_parts)) + status_parts(att, "attack", ranged)
    if opts.get("dirt"):
        a_parts.append(["Hit the Dirt", ACT.HIT_THE_DIRT_PENALTY])
    physical_attack = not astral and not weapon.get("matrix") and not weapon.get("spell")
    if att.status("Prone") and physical_attack and (melee or weapon.get("bow")) and not (melee and opts.get("tactical_att")):
        a_parts.append(["Prone (melee or bow)", ACT.PRONE["melee_or_bow"]])
    aim = _int(opts.get("aim"))
    if aim and ranged and physical_attack:
        a_parts.append(["Take Aim", aim])
    att_cover = max(0, min(4, _int(opts.get("att_cover"))))
    if att_cover == 4 and not (eact and opts.get("edge_action") == "fire_from_cover") and not astral and not weapon.get("matrix"):
        a_parts.append(["Attacking from Cover IV", ACT.COVER_ATTACK["full_cover_dice"]])
    if called:
        a_parts.append([called["name"], called["dice"]])
    env = max(0, min(3, _int(opts.get("env_blind"))) - att.status("Blinded"))
    if env and not melee and not astral and not weapon.get("matrix"):
        a_parts.append([f"Smoke (Blinded {'I' * env})", -3 * env])       # p. 263: through it I, from inside II
    if _int(opts.get("attack_mod")):
        a_parts.append(["Modifier", _int(opts["attack_mod"])])
    split = max(1, _int(opts.get("split"), 1))
    if split > 1:
        whole = _total(a_parts)
        a_parts.append([f"Split among {split} targets", (whole // split) - whole])
    a_roll = opts.get("attack_roll") or DICE.new_roll(max(1, _total(a_parts)), wild=bool(opts.get("wild")) or bool(weapon.get("wild")))
    if ar is not None:
        for name, v in status_parts(att, "ar", ranged):
            ar = max(0, ar + v)
        if opts.get("magnification") and ri >= 2 and ranged and not weapon.get("spell"):
            ar += 2                                 # vision magnification: +2 AR at Medium, Far, Extreme (p. 275)
        if att.status("Prone") and physical_attack and weapon.get("firearm") and not weapon.get("bow"):
            ar += ACT.PRONE["firearm_ar"]

    # ---- Defense Rating (cover, statuses; the Matrix has neither)
    matrix = bool(weapon.get("matrix"))
    cover = 0 if matrix else max(0, min(4, _int(opts.get("cover"))))
    if matrix:
        dr = target.matrix_dr() + (MX.EXPLOIT_DR if weapon.get("exploit") else 0)   # Exploit: −2 to the target's DR
    elif astral:
        dr = target.astral_dr()
    else:
        dr = target.dr + cover + sum(v for _, v in status_parts(target, "dr"))
    out = {"attacker": att.name, "target": target.name, "weapon": weapon["name"], "range": rng,
           "mode": weapon.get("mode"), "ar": ar, "dr": dr, "cover": cover, "melee": melee,
           "called": called["name"] if called else None, "split": split,
           "attack": {"parts": a_parts, "dice": a_roll["dice"], "hits": a_roll["hits"], "glitch": a_roll["glitch"],
                      "critical": a_roll["critical"]}}
    if ar is not None:
        diff = ar - _int(opts.get("edge_dr"), dr)      # several targets: compare with the highest Defense Rating
        out["edge_hint"] = ("attacker" if diff >= ACT.EDGE_HINT_MARGIN else "defender" if diff <= -ACT.EDGE_HINT_MARGIN else None)
        if out["edge_hint"] == "attacker" and att_cover:
            out["edge_hint"] = None                     # no Edge for attacking from Cover

    # ---- defense pool
    A = target.attrs
    ic = MX.IC_TYPES.get(weapon.get("ic") or "")
    if matrix and ic:
        d_parts = target.matrix_pool(ic["defense"]) if ic["defense"] else []
    elif matrix:
        d_parts = target.matrix_defense()
    elif weapon.get("astral"):
        d_parts = [[x, _int(A.get(x), 1)] for x in ACT.ASTRAL["defense"]]
    elif weapon.get("spell") and weapon.get("direct"):
        d_parts = [["Willpower", A.get("Willpower", 1)], ["Intuition", A.get("Intuition", 1)]]
    elif weapon.get("spell"):
        d_parts = [["Reaction", A.get("Reaction", 1)], ["Willpower", A.get("Willpower", 1)]]
    else:
        d_parts = target.defense_pool()
        if target.status("Immobilized"):
            d_parts = [p for p in d_parts if p[0] != "Reaction"] + [["Immobilized: no Reaction", 0]]
    if target.wound:
        d_parts.append(["Wound modifier", target.wound])
    d_parts += sustain_parts(target, physical=any(p[0] in K.PHYSICAL for p in d_parts)) + status_parts(target, "defense", ranged)
    if target.status("Prone") and not matrix and not weapon.get("astral") and not (weapon.get("spell") and weapon.get("direct")):
        far = ranged and rng in ACT.PRONE["far_ranges"]
        if far:
            d_parts.append(["Prone", ACT.PRONE["defense_far"]])
        elif not opts.get("tactical_def"):
            d_parts.append(["Prone", ACT.PRONE["defense_near"]])
    if cover:
        d_parts.append([f"Cover {'I II III IV'.split()[cover - 1]}", cover])
    fd_label, fd_dice = ("Full Matrix Defense (Firewall)", target.matrix_firewall()) if matrix else ("Full Defense (Willpower)", _int(A.get("Willpower"), 1))
    if opts.get("full_defense"):
        d_parts.append([fd_label, fd_dice])
    dkey = opts.get("defense")
    if dkey and dkey != "full_defense":
        d_parts.append([ACT.INTERRUPTS[dkey]["name"], _interrupt_dice(target, dkey)])
    elif dkey == "full_defense" and not opts.get("full_defense"):
        d_parts.append([fd_label, fd_dice])
    if opts.get("counterspell") and weapon.get("spell"):
        name, dice = opts["counterspell"]
        d_parts.append([f"Counterspell ({name})", _int(dice)])
    if _int(opts.get("defense_mod")):
        d_parts.append(["Modifier", _int(opts["defense_mod"])])
    unopposed = bool(opts.get("unopposed"))
    if target.status("Stilled"):
        unopposed = True                                # Stilled: no Defense tests at all
        d_parts = [["Stilled: can't defend", 0]]
    d_hits, d_roll = 0, None
    if not unopposed:
        d_roll = DICE.new_roll(max(1, _total(d_parts))) if _total(d_parts) > 0 else {"hits": 0, "dice": [], "glitch": False, "critical": False}
        d_hits = d_roll["hits"]
    out["defense"] = {"parts": d_parts, "dice": (d_roll or {}).get("dice", []), "hits": d_hits, "unopposed": unopposed,
                      "glitch": (d_roll or {}).get("glitch", False), "action": ACT.INTERRUPTS[dkey]["name"] if dkey else None}
    net = a_roll["hits"] - d_hits
    out["net"] = net
    hit = net > 0 or (net == 0 and a_roll["hits"] > 0 and not weapon.get("spell"))
    out["hit"] = hit
    if not hit:
        out["damage"] = 0
        out["effects"] = []
        out["summary"] = f"{att.name} misses {target.name} ({a_roll['hits']} vs {d_hits} hits)."
        return out

    if ic and not ic["damage"]:
        out["damage"] = 0
        out["effects"] = []
        out["ic"] = {"kind": weapon["ic"], "reduce": ic.get("reduce"), "by": max(1, net), "linklock": bool(ic.get("linklock"))}
        what = (f"{ic['reduce'].replace('_', ' ').title()} −{max(1, net)}" if ic.get("reduce") else ic["effect"])
        out["summary"] = f"{weapon['ic']} hits {target.name}: {what}"
        return out

    # ---- grapple: Strength + net hits vs the target's Strength instead of damage
    if opts.get("grapple"):
        g_att = [["Strength", _int(att.attrs.get("Strength"), 1)], ["Net hits", max(0, net)]]
        g_def = [["Strength", _int(target.attrs.get("Strength"), 1)]]
        ga, gd = DICE.new_roll(max(1, _total(g_att))), DICE.new_roll(max(1, _total(g_def)))
        held = ga["hits"] > gd["hits"]
        out.update({"damage": 0, "effects": [["Restrained", None]] if held else [],
                    "grapple": {"held": held, "attack": {"parts": g_att, "dice": ga["dice"], "hits": ga["hits"]},
                                "defense": {"parts": g_def, "dice": gd["dice"], "hits": gd["hits"]}},
                    "summary": f"{att.name} grabs {target.name}: Strength {ga['hits']} vs {gd['hits']} hits → "
                               + (f"{target.name} is restrained." if held else f"{target.name} slips free.")})
        return out

    # ---- damage and soak
    dtype = weapon.get("type") or "P"
    if astral and opts.get("astral_type") in ("P", "S"):
        dtype = opts["astral_type"]
    extra = _int(opts.get("extra_dv")) + (called["dv"] if called else 0)
    if opts.get("trip"):
        extra += max(ACT.TRIP["dv"], -_int(weapon.get("dv")))     # −2 to the base DV, not below 0
    soak_parts = []
    if weapon.get("spell") and weapon.get("direct"):
        dv = max(0, net) + _int(weapon.get("dv")) + extra
        s_hits = 0
    else:
        dv = _int(weapon.get("dv")) + max(0, net) + extra
        if matrix:
            soak_parts = target.matrix_soak()
        elif weapon.get("astral"):
            soak_parts = [[x, _int(A.get(x), 1)] for x in ACT.ASTRAL["soak"]]
        else:
            soak_parts = target.soak_pool()
            if target.status("Wet") and weapon.get("element") in ("Cold", "Electricity"):
                soak_parts.append(["Wet", ACT.WET_SOAK])
        if _int(opts.get("soak_mod")):
            soak_parts.append(["Modifier", _int(opts["soak_mod"])])
        s_roll = DICE.new_roll(max(1, _total(soak_parts))) if _total(soak_parts) > 0 else {"hits": 0, "dice": []}
        s_hits = s_roll["hits"]
        out["soak"] = {"parts": soak_parts, "dice": s_roll["dice"], "hits": s_hits}
    dmg = max(0, dv - s_hits)
    if called and called.get("no_damage"):
        dmg = 0                                         # Disarm: the weapon goes flying, nobody is hurt
    out["dv"] = dv
    out["type"] = dtype
    out["damage"] = dmg
    out["track"] = "matrix" if matrix else "stun" if dtype == "S" else "physical"
    if ic:
        out["ic"] = {"kind": weapon["ic"], "damage": ic["damage"], "linklock": bool(ic.get("linklock"))}
    effects = []
    if dmg and weapon.get("element") in ELEMENT_STATUS:
        effects.append(ELEMENT_STATUS[weapon["element"]])
    if dmg > target.attrs.get("Body", 1) and not astral and not matrix:
        effects.append(("Prone", None))
    elif eact and opts.get("edge_action") == "tumble" and dv > target.attrs.get("Body", 1):
        effects.append(("Prone", None))
    if eact and opts.get("edge_action") == "knockout" and dmg > _int(target.attrs.get("Willpower"), 1):
        out["knockout"] = True
    if opts.get("trip") and not any(e[0] == "Prone" for e in effects):
        sk, attr = ACT.TRIP["test"]
        t_parts = [[sk, target.rank(sk)], [attr, _int(target.attrs.get(attr), 1)]]
        t_roll = DICE.new_roll(max(1, _total(t_parts)))
        stays = t_roll["hits"] >= dv
        out["trip"] = {"parts": t_parts, "dice": t_roll["dice"], "hits": t_roll["hits"], "threshold": dv, "prone": not stays}
        if not stays:
            effects.append(("Prone", None))
    out["effects"] = [[e[0], e[1]] for e in effects]
    out["disarmed"] = bool(called and called.get("disarm"))
    word = "Matrix damage" if matrix else "Physical" if dtype == "P" else "Stun"
    out["summary"] = (f"{att.name} hits {target.name} with {weapon['name']}: DV {dv}{dtype}"
                      + (f", soaked {s_hits}" if soak_parts else "") + f" → {dmg} {word}"
                      + (f" ({', '.join(e[0] for e in effects)})" if effects else "")
                      + ("; knocked out" if out.get("knockout") else "")
                      + (f"; {target.name} drops their weapon" if out["disarmed"] else "")
                      + (f"; trip: {out['trip']['hits']} hits vs {dv} → " + ("Prone" if out["trip"]["prone"] else "keeps their feet") if out.get("trip") else "") + ".")
    return out


def tradition_attr(f):
    """Logic for hermetic magicians, Charisma for shamans (and NPCs, spirits)."""
    if f.char is not None:
        return M.TRADITIONS.get(f.char.get("tradition") or "") or "Charisma"
    return "Charisma"


def astral_profile(f):
    """Astral combat for a runner or an NPC (dual-natured critters, spirits, projecting magicians):
    Astral + Willpower, Attack Rating Magic + tradition attribute, DV tradition attribute / 2."""
    skill, attr = ACT.ASTRAL["attack"]
    rank = f.rank(skill)
    parts = [[attr, _int(f.attrs.get(attr), 1)], [skill, rank] if rank else [f"{skill} (untrained)", -1]]
    trad = tradition_attr(f)
    magic = _int(f.attrs.get("Magic"))
    if f.npc and f.npc.get("kind") == "Spirit":
        magic = _int(f.npc.get("force"), magic)
    dv_base = _int(f.attrs.get(trad), 1)
    if f.npc and f.npc.get("kind") == "Spirit":
        dv_base = max(dv_base, _int(f.npc.get("force"), dv_base))
    dv = (dv_base + 1) // 2 if ACT.ASTRAL["dv_half"] else dv_base
    ar = magic + _int(f.attrs.get(trad), 1)
    return {"name": "Astral combat", "parts": parts, "ar": [ar] * 5, "dv": dv, "type": ACT.ASTRAL["type"],
            "element": "", "mode": None, "astral": True, "melee": True, "tradition": trad}


def npc_weapon_profile(f, w, mode=None):
    modes = w.get("modes") or []
    mode = mode if mode in modes else (modes[0] if modes else None)
    ar = list(w.get("ar") or [None] * 5)
    dv = _int(w.get("dv"))
    if mode:
        fm = G.FIRING_MODES[mode]
        ar = [None if a is None else max(0, a + fm["ar"]) for a in ar]
        dv += fm["dv"]
    parts = [[w.get("pool_label") or "Dice", _int(w["pool"])]] if w.get("pool") else f.npc_attack_parts(w)
    return {"name": w.get("name") or "Attack", "parts": parts, "ar": ar, "dv": dv,
            "type": w.get("type") or "P", "element": w.get("element") or "", "mode": mode,
            "matrix": bool(w.get("matrix")), "biofeedback": w.get("biofeedback"),
            "melee": (w.get("skill") or "Close Combat") == "Close Combat", **_shot_kind(w.get("name"), w.get("skill"))}


def char_weapon_profile(f, key, mode, rng, amp=0):
    """Attack profile for a player character: weapon:<uid>, weapon:unarmed or spell:<i>."""
    c, d = f.char, f.d
    if key == "weapon:unarmed":
        p = R.unarmed_profile(c, d)
        return {"name": "Unarmed strike", "parts": p["parts"], "ar": p["ar"], "dv": p["dv"], "type": p["type"],
                "element": "", "mode": None, "uid": "unarmed", "melee": True}
    if key == "astral":
        return astral_profile(f)
    if key.startswith("matrix:"):
        act = key[7:]
        if act not in ("data_spike", "tarpit"):
            raise R.RuleError("Pick a Matrix attack.")
        mx = d["matrix"]
        if not mx.get("device"):
            raise R.RuleError(f"{f.name} has no active Matrix device.")
        pool = R.pool_by_key(c, key, d)
        dv = (mx["ar"] + 1) // 2 if act == "data_spike" else 1          # Data Spike: Attack Rating / 2, rounded up
        bio = "sim" if R.program_running(d, "Biofeedback") else ("S" if R.program_running(d, "Blackout") else None)
        return {"name": MX.MATRIX_ACTIONS[act]["name"], "parts": [list(p) for p in pool["parts"]], "ar": [mx["ar"]] * 5, "dv": dv,
                "type": "M", "element": "", "mode": None, "matrix": True, "illegal": True, "tarpit": act == "tarpit",
                "biofeedback": bio, "wild": R.program_running(d, "Overclock"), "exploit": R.program_running(d, "Exploit"),
                "fork": R.program_running(d, "Fork"), "lockdown": R.program_running(d, "Lockdown")}
    if key.startswith("weapon:"):
        it = R.find_item(c, key[7:])
        p = R.weapon_profile(c, d, it, mode, rng)
        if not p:
            raise R.RuleError(f"{f.name} can't use the {it['name']} (untrained exotic weapon).")
        return {"name": it["name"], "parts": p["parts"], "ar": p["ar"], "dv": p["dv"], "type": p["type"],
                "element": p["element"], "mode": p["mode"], "uid": it["uid"], "melee": p["skill"] == "Close Combat",
                **_shot_kind(it["name"], p["skill"])}
    if key.startswith("natural:"):
        nws = d.get("natural_weapons") or []
        i = _int(key[8:], -1)
        if not 0 <= i < len(nws):
            raise R.RuleError("Pick a weapon.")
        w = nws[i]
        p = R.weapon_profile(c, d, {"name": w["name"], "skill": w["skill"], "spec": "Unarmed Combat" if w["skill"] == "Close Combat" else None,
                                    "dv": w["dv"], "ar": w["ar"], "cat": "Melee"}, None, rng)
        if not p:
            raise R.RuleError(f"{f.name} can't use that natural weapon.")
        return {"name": w["name"], "parts": p["parts"], "ar": p["ar"], "dv": p["dv"], "type": p["type"],
                "element": "", "mode": None, "uid": "unarmed", "melee": w["skill"] == "Close Combat"}
    if key.startswith("spell:"):
        sp = (c.get("spells") or [])[_int(key[6:], -1)] if 0 <= _int(key[6:], -1) < len(c.get("spells") or []) else None
        if not sp or sp.get("category") != "Combat":
            raise R.RuleError("Pick a combat spell.")
        p = R.spell_profile(c, d, sp, amp)
        if not p:
            raise R.RuleError(f"{f.name} can't cast spells.")
        return {"name": sp["name"], "parts": p["parts"], "ar": p["ar"], "dv": p["dv"], "type": p["type"],
                "element": p["element"], "mode": None, "spell": sp, "direct": p["direct"], "drain": p["drain"]}
    raise R.RuleError("Pick a weapon.")


def add_status(st, name, val=True):
    """Set a status, applying cancellations: Wet or Chilled put out Burning, Burning dries Wet and Chilled."""
    for other in ACT.STATUS_CANCELS.get(name, ()):
        st.pop(other, None)
    st[name] = val if val else True
    return st


def _shot_kind(name, skill):
    """Bows and firearms matter for Prone attackers (bows −4, firearms +2 Attack Rating)."""
    n = (name or "").lower()
    bow = "bow" in n and "crossbow" not in n
    return {"bow": bow, "firearm": not bow and skill in ("Firearms", "Exotic Weapons")}


def initiative_roll(score, dice):
    return DICE.initiative(score, dice)


def area_note(weapon):
    if weapon.get("grenade"):
        return f"Blast {weapon.get('blast')}: {', '.join(weapon['grenade'])} (ground zero / close / near)"
    return ""


def wound_text(n):
    return f"{n}" if n else "—"


def ceil_half(n):
    return int(math.ceil(n / 2))

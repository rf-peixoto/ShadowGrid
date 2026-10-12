"""Combat for the GM's map: NPC stat blocks (core-book templates), attack
resolution (attack -> defense -> soak -> condition monitor), and helpers for
the initiative tracker.

Combatants are either player characters (sheet dicts, handled through
sr.rules) or map markers carrying an ``npc`` stat block and a ``cm`` monitor.
"""
import math
import re

from . import catalog as CAT
from . import core6e as K
from . import dice as DICE
from . import gear6e as G
from . import magic6e as M
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


def templates():
    """Template list for the GM's picker."""
    out = [{"key": f"t:{i}", "name": t["name"], "kind": t.get("kind"), "pr": t.get("pr")}
           for i, t in enumerate(N.NPC_TEMPLATES)]
    out += [{"key": f"s:{k}", "name": f"{k} spirit", "kind": "Spirit", "pr": None, "force": True} for k in M.SPIRITS]
    return out


def npc_from_key(key, force=None):
    key = str(key or "")
    if key.startswith("t:"):
        i = _int(key[2:], -1)
        if 0 <= i < len(N.NPC_TEMPLATES):
            return parse_template(N.NPC_TEMPLATES[i])
    if key.startswith("s:") and key[2:] in M.SPIRITS:
        return spirit_npc(key[2:], force or 3)
    raise R.RuleError("Unknown template.")


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
                        "category": str(w.get("category") or "")[:30]})
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
            "move": str(v.get("move") or "")[:20], "weapons": weapons, "notes": str(v.get("notes") or "")[:4000],
            "force": _int(v.get("force")) or None}


def npc_cm(npc):
    """Fresh marker monitor for an NPC: grunts have one track (pm), others Physical + Stun."""
    if npc.get("grunt"):
        return {"pm": npc["pm"], "sm": 0, "ov": 0, "p": 0, "s": 0, "grunt": True}
    return {"pm": npc["pm"], "sm": npc["sm"], "ov": 0 if npc.get("kind") in ("Spirit",) else npc["attrs"].get("Body", 1) * 2,
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

    def __init__(self, name, attrs, dr, wound, skills=None, specs=None, char=None, derived=None, npc=None, cm=None):
        self.name, self.attrs, self.dr, self.wound = name, attrs, dr, wound
        self.skills, self.specs = skills or {}, specs or {}
        self.char, self.d, self.npc, self.cm = char, derived, npc, cm

    @classmethod
    def from_char(cls, name, c):
        d = R.derive(c)
        return cls(name, d["attributes"], d["defense_rating"], d["wound_modifier"], char=c, derived=d)

    @classmethod
    def from_marker(cls, mk):
        npc = mk.get("npc") or {"attrs": {}, "dr": 0, "skills": {}, "specs": {}}
        attrs = {a: _int((npc.get("attrs") or {}).get(a), 1) for a in K.PHYSICAL + K.MENTAL + ["Magic"]}
        return cls(mk.get("label") or "Enemy", attrs, _int(npc.get("dr")), marker_wound(mk.get("cm")),
                   skills=npc.get("skills"), specs=npc.get("specs"), npc=npc, cm=mk.get("cm"))

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


def resolve_attack(att, weapon, target, opts):
    """Roll an attack, the defense and the soak. Returns a result dict (no state is changed here,
    except for the attacker's sheet ammo, which the caller handles).

    ``weapon``: {"name", "parts", "ar" (list), "dv", "type", "element", "mode", "direct", "mana", "spell"}
    ``opts``: range, attack_mod, defense_mod, soak_mod, wild, extra_dv
    """
    rng = opts.get("range") if opts.get("range") in G.RANGES else "Near"
    ri = G.RANGES.index(rng)
    ar_list = weapon.get("ar") or [None] * 5
    ar = ar_list[ri] if ri < len(ar_list) else None
    if ar is None and not weapon.get("spell"):
        raise R.RuleError(f"The {weapon['name']} can't attack at {rng} range.")
    a_parts = [list(p) for p in weapon["parts"]]
    if att.wound:
        a_parts.append(["Wound modifier", att.wound])
    if _int(opts.get("attack_mod")):
        a_parts.append(["Modifier", _int(opts["attack_mod"])])
    a_roll = DICE.new_roll(max(1, _total(a_parts)), wild=bool(opts.get("wild")))
    out = {"attacker": att.name, "target": target.name, "weapon": weapon["name"], "range": rng,
           "mode": weapon.get("mode"), "ar": ar, "dr": target.dr,
           "attack": {"parts": a_parts, "dice": a_roll["dice"], "hits": a_roll["hits"], "glitch": a_roll["glitch"],
                      "critical": a_roll["critical"]}}
    if ar is not None:
        diff = ar - target.dr
        out["edge_hint"] = ("attacker" if diff >= 4 else "defender" if diff <= -4 else None)
    # defense
    if weapon.get("spell") and weapon.get("direct"):
        d_parts = [["Willpower", target.attrs.get("Willpower", 1)], ["Intuition", target.attrs.get("Intuition", 1)]]
    elif weapon.get("spell"):
        d_parts = [["Reaction", target.attrs.get("Reaction", 1)], ["Willpower", target.attrs.get("Willpower", 1)]]
    else:
        d_parts = target.defense_pool()
    if target.wound:
        d_parts.append(["Wound modifier", target.wound])
    if _int(opts.get("defense_mod")):
        d_parts.append(["Modifier", _int(opts["defense_mod"])])
    grunt_unopposed = bool(opts.get("unopposed"))
    d_hits = 0
    d_roll = None
    if not grunt_unopposed:
        d_roll = DICE.new_roll(max(1, _total(d_parts))) if _total(d_parts) > 0 else {"hits": 0, "dice": [], "glitch": False, "critical": False}
        d_hits = d_roll["hits"]
    out["defense"] = {"parts": d_parts, "dice": (d_roll or {}).get("dice", []), "hits": d_hits, "unopposed": grunt_unopposed,
                      "glitch": (d_roll or {}).get("glitch", False)}
    net = a_roll["hits"] - d_hits
    out["net"] = net
    hit = net > 0 or (net == 0 and a_roll["hits"] > 0 and not weapon.get("spell"))
    out["hit"] = hit
    if not hit:
        out["damage"] = 0
        out["summary"] = f"{att.name} misses {target.name} ({a_roll['hits']} vs {d_hits} hits)."
        return out
    dtype = weapon.get("type") or "P"
    if weapon.get("spell") and weapon.get("direct"):
        dv = max(0, net) + _int(weapon.get("dv"))
        soak_parts, s_hits = [], 0
    else:
        dv = _int(weapon.get("dv")) + max(0, net) + _int(opts.get("extra_dv"))
        soak_parts = target.soak_pool()
        if _int(opts.get("soak_mod")):
            soak_parts.append(["Modifier", _int(opts["soak_mod"])])
        s_roll = DICE.new_roll(max(1, _total(soak_parts))) if _total(soak_parts) > 0 else {"hits": 0, "dice": []}
        s_hits = s_roll["hits"]
        out["soak"] = {"parts": soak_parts, "dice": s_roll["dice"], "hits": s_hits}
    dmg = max(0, dv - s_hits)
    out["dv"] = dv
    out["type"] = dtype
    out["damage"] = dmg
    out["track"] = "stun" if dtype == "S" else "physical"
    effects = []
    if dmg and weapon.get("element") in ELEMENT_STATUS:
        effects.append(ELEMENT_STATUS[weapon["element"]])
    if dmg > target.attrs.get("Body", 1):
        effects.append(("Prone", None))
    out["effects"] = [[e[0], e[1]] for e in effects]
    word = "Physical" if dtype == "P" else "Stun"
    out["summary"] = (f"{att.name} hits {target.name} with {weapon['name']}: DV {dv}{dtype}"
                      + (f", soaked {s_hits}" if soak_parts else "") + f" → {dmg} {word}"
                      + (f" ({', '.join(e[0] for e in effects)})" if effects else "") + ".")
    return out


def npc_weapon_profile(f, w, mode=None):
    modes = w.get("modes") or []
    mode = mode if mode in modes else (modes[0] if modes else None)
    ar = list(w.get("ar") or [None] * 5)
    dv = _int(w.get("dv"))
    if mode:
        fm = G.FIRING_MODES[mode]
        ar = [None if a is None else max(0, a + fm["ar"]) for a in ar]
        dv += fm["dv"]
    return {"name": w.get("name") or "Attack", "parts": f.npc_attack_parts(w), "ar": ar, "dv": dv,
            "type": w.get("type") or "P", "element": w.get("element") or "", "mode": mode}


def char_weapon_profile(f, key, mode, rng, amp=0):
    """Attack profile for a player character: weapon:<uid>, weapon:unarmed or spell:<i>."""
    c, d = f.char, f.d
    if key == "weapon:unarmed":
        p = R.unarmed_profile(c, d)
        return {"name": "Unarmed strike", "parts": p["parts"], "ar": p["ar"], "dv": p["dv"], "type": p["type"],
                "element": "", "mode": None, "uid": "unarmed"}
    if key.startswith("weapon:"):
        it = R.find_item(c, key[7:])
        p = R.weapon_profile(c, d, it, mode, rng)
        if not p:
            raise R.RuleError(f"{f.name} can't use the {it['name']} (untrained exotic weapon).")
        return {"name": it["name"], "parts": p["parts"], "ar": p["ar"], "dv": p["dv"], "type": p["type"],
                "element": p["element"], "mode": p["mode"], "uid": it["uid"]}
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
                "element": "", "mode": None, "uid": "unarmed"}
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

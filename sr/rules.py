"""Shadowrun 6E character model and every rule that changes a character.

A character is a plain dict (stored as JSON). ``derive()`` recomputes every
derived number (ported from the original ``ShadowrunCharacter.recalculate``)
and ``apply_action()`` is the single entry point for changes, so the server
is the only place Karma and Nuyen ever move.

Economy (agreed with the GM):
- Until a sheet is approved the player may edit freely and every purchase is
  refunded in full when removed.
- After approval spending is final; attributes and skills only go up by
  spending Karma (new rating x 5), specializations cost 5 Karma, new spells
  cost 5 Karma, players can't take/remove qualities, and Karma/Nuyen only
  change through in-app actions, run rewards and GM grants.
- The GM (admin) can do anything, and never pays.
"""
import copy
import re

from . import data as D

EDGE_CAP = 7
ATTR_MIN, ATTR_MAX = 1, 10
SKILL_MAX = 12
KARMA_PER_RATING = 5
KARMA_SPECIALIZATION = 5
KARMA_SPELL = 5
NUYEN_PER_KARMA = 2000
MAX_LIST = 300
PORTRAIT_MAX_CHARS = 450_000

LOCKED_INFO = ("metatype", "role", "magic_type", "initiation_grade")
FREE_INFO = ("name", "tradition", "mentor_spirit", "lifestyle", "age", "reputation", "background", "notes")


# Metatype minimums (from the original recalculate()); Trolls also cap Logic at 5.
METATYPE_MIN = {
    "Dwarf": {"Body": 3, "Willpower": 3},
    "Elf": {"Agility": 2, "Charisma": 3},
    "Ork": {"Body": 3, "Strength": 3},
    "Troll": {"Body": 5, "Strength": 5},
}


def effective_base(c, attr):
    """Base rating counting metatype minimums (what raising an attribute starts from)."""
    return max(_int(c["base_attributes"].get(attr)), METATYPE_MIN.get(c.get("metatype"), {}).get(attr, 0))


class RuleError(ValueError):
    """A rule was broken; the message is shown to the user as-is."""


# --------------------------------------------------------------------------- helpers
def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _yes(v, default=False):
    if v is None:
        return default
    return str(v).strip().lower() in ("yes", "true", "1")


def _clip(s, n):
    return str(s if s is not None else "")[:n]


def fmt_money(n):
    return f"{int(n):,}¥"


def new_character():
    attrs = {a: 1 for a in D.ATTRIBUTES}
    attrs["Magic"] = 0
    attrs["Resonance"] = 0
    attrs["Essence"] = 6.0
    return {
        "name": "", "metatype": "Human", "role": "", "background": "", "notes": "",
        "lifestyle": "Low", "karma": 50, "nuyen": 5000,
        "magic_type": "Mundane", "tradition": "", "mentor_spirit": "", "initiation_grade": 0,
        "age": 25, "reputation": 0, "portrait": None,
        "base_attributes": attrs,
        "skills": {s: 0 for s in D.SKILLS}, "specializations": {},
        "qualities": [],
        "gear": {c: [] for c in D.GEAR_CATEGORIES},
        "contacts": [], "spells": [], "powers": [], "complex_forms": [], "foci": [],
        "physical_damage": 0, "stun_damage": 0, "current_edge": 1,
    }


def normalize(c):
    """Fill missing keys (forward compatible) and coerce types."""
    base = new_character()
    for k, v in base.items():
        if k not in c:
            c[k] = copy.deepcopy(v)
    for a in D.ATTRIBUTES:
        c["base_attributes"].setdefault(a, base["base_attributes"][a])
    for s in D.SKILLS:
        c["skills"].setdefault(s, 0)
    for cat in D.GEAR_CATEGORIES:
        c["gear"].setdefault(cat, [])
    c["karma"] = _int(c["karma"])
    c["nuyen"] = _int(c["nuyen"])
    return c


# --------------------------------------------------------------------------- derived stats
def derive(c):
    """Every derived value, from base attributes + metatype + role + qualities + gear.

    Ported from the original single-pass ``recalculate()`` so gear bonuses
    always stick (the original two-pass version silently dropped them).
    """
    attributes = dict(c["base_attributes"])
    for a in D.ATTRIBUTES:
        attributes.setdefault(a, 0)

    for attr, lo in METATYPE_MIN.get(c.get("metatype"), {}).items():
        attributes[attr] = max(lo, attributes[attr])
    if c.get("metatype") == "Troll":
        attributes["Logic"] = max(1, min(attributes["Logic"], 5))

    bonuses = {a: [] for a in D.ATTRIBUTES}   # where each bonus came from, for the UI

    def bump(attr, amount, source):
        attributes[attr] = attributes[attr] + amount
        bonuses[attr].append([source, amount])

    role = D.ROLES.get(c.get("role") or "")
    if role:
        for attr, bonus in role.items():
            before = attributes[attr]
            attributes[attr] = max(1, attributes[attr] + bonus)
            bonuses[attr].append([f"Role: {c['role']}", attributes[attr] - before])

    q_phys = q_stun = 0
    for q in c["qualities"]:
        for key, bonus in (D.QUALITY_EFFECTS.get(q) or {}).items():
            if key == "karma":
                continue
            if key == "Physical Boxes":
                q_phys += bonus
            elif key == "Stun Boxes":
                q_stun += bonus
            elif key in attributes:
                before = attributes[key]
                attributes[key] = max(1, attributes[key] + bonus)
                bonuses[key].append([q, attributes[key] - before])

    essence_cost = sum(_num(i.get("Essence Cost")) for i in c["gear"]["Cyberware"] + c["gear"]["Bioware"])
    attributes["Essence"] = round(max(0.0, _num(c["base_attributes"].get("Essence", 6.0), 6.0) - essence_cost), 2)

    init_dice_bonus = 0.0
    for item in c["gear"]["Cyberware"] + c["gear"]["Bioware"] + c["powers"]:
        for attr in D.ATTRIBUTES:
            if attr == "Essence" or attr not in item:
                continue
            v = _num(item.get(attr), None)
            if v is not None:
                bump(attr, v, item.get("name", "?"))
        if "Initiative Dice" in item:
            init_dice_bonus += _num(item.get("Initiative Dice"))
    for attr in D.ATTRIBUTES:
        if attr != "Essence":
            attributes[attr] = int(round(attributes[attr]))

    armor = 0
    for item in c["gear"]["Armor"]:
        if _yes(item.get("Equipped"), True):
            armor += _int(item.get("Rating"))
    for p in c["powers"]:
        if "Armor" in p:
            armor += _int(p.get("Armor"))

    accuracy = 0
    for item in c["gear"]["Weapons"]:
        if _yes(item.get("Equipped"), True):
            accuracy = max(accuracy, _int(item.get("Accuracy")))

    if c.get("magic_type") not in ("Mundane", "Technomancer"):
        ess, magic = attributes["Essence"], attributes["Magic"]
        for i in range(1, 7):
            if ess < i:
                magic = min(magic, 6 - i)
        if magic != attributes["Magic"]:
            bonuses["Magic"].append(["Essence loss", magic - attributes["Magic"]])
        attributes["Magic"] = magic

    for f in c["foci"]:
        if _yes(f.get("Bonded")) and (f.get("Type") or f.get("type")) == "Power":
            force = _int(f.get("Force", f.get("force")))
            bump("Magic", force, f.get("name", "Power Focus"))

    body, wil = attributes["Body"], attributes["Willpower"]
    p_boxes = (body + 1) // 2 + 8 + q_phys
    s_boxes = (wil + 1) // 2 + 8 + q_stun
    overflow = max(1, body)

    pd = max(0, _int(c.get("physical_damage")))
    sd = max(0, _int(c.get("stun_damage")))
    wound = -(min(pd, p_boxes) // 3 + min(sd, s_boxes) // 3)
    if pd > p_boxes + overflow:
        status = "Dead"
    elif pd >= p_boxes:
        status = "Dying"
    elif sd >= s_boxes:
        status = "Unconscious"
    elif wound:
        status = "Wounded"
    else:
        status = "OK"

    pp_avail = attributes["Magic"] if c.get("magic_type") in ("Adept", "Mystic Adept") else 0
    pp_used = 0.0
    for p in c["powers"]:
        pp_used += _num(p.get("Cost", p.get("cost", 1)) or 1, 1.0)

    gear_value = 0.0
    for cat in D.GEAR_CATEGORIES:
        for item in c["gear"][cat]:
            gear_value += _num(item.get("Price"))

    return {
        "attributes": attributes,
        "bonuses": {a: b for a, b in bonuses.items() if b},
        "physical_boxes": p_boxes, "stun_boxes": s_boxes, "overflow_boxes": overflow,
        "physical_damage": pd, "stun_damage": sd,
        "wound_modifier": wound, "status": status,
        "initiative_score": attributes["Reaction"] + attributes["Intuition"],
        "initiative_dice": 1 + int(init_dice_bonus),
        "armor_rating": armor, "weapon_accuracy": accuracy,
        "defense_rating": attributes["Body"] + armor,
        "edge_max": attributes["Edge"], "current_edge": _int(c.get("current_edge")),
        "power_points_available": pp_avail, "power_points_used": round(pp_used, 2),
        "gear_value": int(gear_value),
        "lifestyle_cost": D.LIFESTYLE_NUYEN.get(c.get("lifestyle"), 0),
    }


def condition_summary(c, d=None):
    d = d or derive(c)
    return {"p": d["physical_damage"], "pm": d["physical_boxes"], "s": d["stun_damage"], "sm": d["stun_boxes"],
            "ov": d["overflow_boxes"], "status": d["status"], "wound": d["wound_modifier"]}


# --------------------------------------------------------------------------- dice pools
def pools(c, d=None):
    """Every pool a player can pick in the dice roller, computed from the sheet."""
    d = d or derive(c)
    A = d["attributes"]
    out = []

    def add(key, group, label, parts):
        out.append({"key": key, "group": group, "label": label, "parts": parts,
                    "value": max(0, sum(p[1] for p in parts))})

    def skill_parts(skill, attr=None, spec=False):
        attr = attr or D.SKILL_ATTRIBUTE.get(skill, "Agility")
        rank = c["skills"].get(skill, 0)
        parts = [[attr, A.get(attr, 0)]]
        if rank > 0:
            parts.append([skill, rank])
            if spec:
                parts.append([f"Specialization ({c['specializations'].get(skill)})", 2])
        else:
            parts.append([f"{skill} (untrained)", -1])
        return parts

    for skill in D.SKILLS:
        add(f"skill:{skill}", "Skills", skill, skill_parts(skill))
        spec = c["specializations"].get(skill)
        if spec and c["skills"].get(skill, 0) > 0:
            add(f"spec:{skill}", "Skills", f"{skill} [{spec}]", skill_parts(skill, spec=True))

    for i, w in enumerate(c["gear"]["Weapons"]):
        if not _yes(w.get("Equipped"), True):
            continue
        skill = D.WEAPON_SKILL.get(w.get("Type"), "Firearms")
        spec = c["specializations"].get(skill) == w.get("Type")
        add(f"weapon:{i}", "Weapons", f"{w.get('name', 'Weapon')} ({skill})", skill_parts(skill, spec=spec))

    if c.get("magic_type") not in ("Mundane", "Technomancer"):
        for i, s in enumerate(c["spells"]):
            stype = s.get("Type") or s.get("type") or ""
            spec = c["specializations"].get("Sorcery") == f"{stype} Spells"
            add(f"spell:{i}", "Spells", f"Cast {s.get('name', 'spell')}", skill_parts("Sorcery", spec=spec))
        trad_attr = D.TRADITION_DRAIN.get(c.get("tradition") or "", "Willpower")
        add("drain", "Magic", "Drain resistance", [["Willpower", A["Willpower"]], [trad_attr, A.get(trad_attr, 0)]])

    add("defense", "Combat", "Defense test", [["Reaction", A["Reaction"]], ["Intuition", A["Intuition"]]])
    add("soak", "Combat", "Damage resistance", [["Body", A["Body"]]])
    add("composure", "Attribute tests", "Composure", [["Willpower", A["Willpower"]], ["Charisma", A["Charisma"]]])
    add("judge", "Attribute tests", "Judge intentions", [["Willpower", A["Willpower"]], ["Intuition", A["Intuition"]]])
    add("memory", "Attribute tests", "Memory", [["Logic", A["Logic"]], ["Intuition", A["Intuition"]]])
    add("lift", "Attribute tests", "Lift / carry", [["Body", A["Body"]], ["Willpower", A["Willpower"]]])
    for a in D.ATTRIBUTES:
        if a in ("Essence",):
            continue
        add(f"attr:{a}", "Single attribute", a, [[a, A.get(a, 0)]])
    return out


def pool_by_key(c, key):
    for p in pools(c):
        if p["key"] == key:
            return p
    raise RuleError("That dice pool no longer exists on your sheet.")


# --------------------------------------------------------------------------- item cleaning
SAFE_KEY = re.compile(r"^[A-Za-z0-9 _()./+-]{1,40}$")


def clean_item(raw, kind):
    """Shape a gear/spell/power/focus dict coming from the browser."""
    if not isinstance(raw, dict):
        raise RuleError("Bad item.")
    name = _clip(raw.get("name"), 80).strip()
    if not name:
        raise RuleError("A name is required.")
    item = {"name": name, "description": _clip(raw.get("description"), 1000).strip()}
    for k, v in list(raw.items())[:40]:
        if k in ("name", "description") or not isinstance(k, str) or k.startswith("_"):
            continue
        if not SAFE_KEY.match(k):
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            item[k] = v
        elif v is not None and str(v).strip() != "":
            item[k] = _clip(v, 200).strip()
    if kind in D.EQUIPPABLE_CATEGORIES:
        item["Equipped"] = "Yes" if _yes(raw.get("Equipped"), True) else "No"
    if kind == "Focus":
        item["Bonded"] = "Yes" if _yes(raw.get("Bonded")) else "No"
    if "Price" in item:
        p = _num(item["Price"], -1)
        if p < 0:
            raise RuleError("Price must be a number of nuyen.")
        item["Price"] = int(p)
    return item


def predefined(kind, index):
    src = {"Spell": D.PREDEFINED_SPELLS, "Power": D.PREDEFINED_POWERS, "Focus": D.PREDEFINED_FOCI}.get(kind) \
        or D.PREDEFINED_GEAR.get(kind)
    if src is None:
        raise RuleError("Unknown category.")
    i = _int(index, -1)
    if not 0 <= i < len(src):
        raise RuleError("Unknown item.")
    raw = dict(src[i])
    # predefined spells/powers/foci use lowercase keys; the editor uses capitalized ones
    for lower, cap in (("type", "Type"), ("drain", "Drain"), ("force", "Force"), ("activation", "Activation"),
                       ("effect", "Effect"), ("cost", "Cost")):
        if lower in raw and cap not in raw:
            raw[cap] = raw.pop(lower)
    return raw


def focus_bond_cost(f):
    ftype = f.get("Type", f.get("type", ""))
    return _int(f.get("Force", f.get("force"))) * D.FOCUS_BOND_MULTIPLIER.get(ftype, 1)


# --------------------------------------------------------------------------- actions
class Ctx:
    def __init__(self, approved, admin):
        self.approved = approved      # sheet approved by the GM
        self.admin = admin            # GM is the one acting
        self.ledger = []              # [(kind, delta, reason)]
        self.log = []                 # table-log notes (shown in the roll log)

    @property
    def locked(self):
        return self.approved and not self.admin

    @property
    def refunds(self):
        return not self.approved


def spend(c, ctx, kind, amount, reason):
    """Charge karma/nuyen (players only; the GM never pays)."""
    if amount == 0 or ctx.admin:
        return
    if amount > 0 and c[kind] < amount:
        unit = "Karma" if kind == "karma" else "nuyen"
        have = c[kind] if kind == "karma" else fmt_money(c[kind])
        need = amount if kind == "karma" else fmt_money(amount)
        raise RuleError(f"Not enough {unit}: this costs {need} and you have {have}.")
    c[kind] -= amount
    ctx.ledger.append((kind, -amount, reason))


def gain(c, ctx, kind, amount, reason):
    if amount == 0:
        return
    c[kind] += amount
    ctx.ledger.append((kind, amount, reason))


def _need_unlocked(ctx, what):
    if ctx.locked:
        raise RuleError(f"Your sheet is approved, so {what} can only be changed by the GM.")


def _list_index(lst, idx):
    i = _int(idx, -1)
    if not 0 <= i < len(lst):
        raise RuleError("That entry no longer exists. Reload the page.")
    return i


def apply_action(c, action, p, ctx):
    """Mutate character ``c`` according to ``action``; returns a short message."""
    normalize(c)
    fn = ACTIONS.get(action)
    if not fn:
        raise RuleError("Unknown action.")
    edge_max_before = derive(c)["edge_max"]
    msg = fn(c, p or {}, ctx)
    d = derive(c)
    # keep damage inside what the monitors can hold
    c["stun_damage"] = min(max(0, c["stun_damage"]), d["stun_boxes"])
    c["physical_damage"] = min(max(0, c["physical_damage"]), d["physical_boxes"] + d["overflow_boxes"] + 1)
    if not ctx.approved and d["edge_max"] != edge_max_before:
        c["current_edge"] = d["edge_max"]           # during creation Edge follows the Edge attribute
    c["current_edge"] = max(0, min(EDGE_CAP, c["current_edge"]))
    return msg or "Saved."


# ---- info
def a_set_info(c, p, ctx):
    for k in FREE_INFO + LOCKED_INFO:
        if k not in p:
            continue
        if k in LOCKED_INFO and ctx.locked and p[k] != c.get(k):
            raise RuleError(f"Your sheet is approved; ask the GM to change {k.replace('_', ' ')}.")
        v = p[k]
        if k == "metatype" and v not in D.METATYPES:
            raise RuleError("Unknown metatype.")
        if k == "role" and v not in ("", *D.ROLES):
            raise RuleError("Unknown role.")
        if k == "magic_type" and v not in D.MAGIC_TYPES:
            raise RuleError("Unknown magic type.")
        if k == "tradition" and v not in ("", *D.TRADITIONS):
            raise RuleError("Unknown tradition.")
        if k == "lifestyle" and v not in D.LIFESTYLES:
            raise RuleError("Unknown lifestyle.")
        if k in ("age", "reputation", "initiation_grade"):
            v = max(0, min(999 if k == "age" else 99, _int(v)))
        elif k in ("background", "notes"):
            v = _clip(v, 20000)
        else:
            v = _clip(v, 80)
        c[k] = v
    return "Saved."


def a_set_portrait(c, p, ctx):
    img = p.get("data")
    if img is None:
        c["portrait"] = None
        return "Portrait removed."
    if not isinstance(img, str) or not re.match(r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$", img):
        raise RuleError("Portrait must be a JPEG, PNG or WebP image.")
    if len(img) > PORTRAIT_MAX_CHARS:
        raise RuleError("Portrait is too large.")
    c["portrait"] = img
    return "Portrait updated."


def a_pay_lifestyle(c, p, ctx):
    cost = D.LIFESTYLE_NUYEN.get(c["lifestyle"], 0)
    spend(c, ctx, "nuyen", cost, f"{c['lifestyle']} lifestyle, 1 month")
    return f"Paid {fmt_money(cost)} for a month of {c['lifestyle']} lifestyle."


def a_trade_karma(c, p, ctx):
    n = _int(p.get("amount"))
    if n <= 0:
        raise RuleError("Enter how much Karma to trade.")
    if c["karma"] < n:
        raise RuleError(f"You only have {c['karma']} Karma.")
    c["karma"] -= n
    ctx.ledger.append(("karma", -n, "Traded for nuyen"))
    gain(c, ctx, "nuyen", n * NUYEN_PER_KARMA, f"Traded {n} Karma")
    return f"Traded {n} Karma for {fmt_money(n * NUYEN_PER_KARMA)}."


# ---- attributes
def a_set_attribute(c, p, ctx):
    _need_unlocked(ctx, "base attributes")
    attr = p.get("attr")
    if attr not in D.ATTRIBUTES or attr == "Essence":
        raise RuleError("Unknown attribute.")
    lo = 0 if attr in ("Magic", "Resonance") else ATTR_MIN
    c["base_attributes"][attr] = max(lo, min(ATTR_MAX, _int(p.get("value"), lo)))
    return "Saved."


def a_raise_attribute(c, p, ctx):
    attr = p.get("attr")
    if attr not in D.ATTRIBUTES or attr == "Essence":
        raise RuleError("Unknown attribute.")
    cur = effective_base(c, attr)
    if c.get("metatype") == "Troll" and attr == "Logic" and cur >= 5:
        raise RuleError("Trolls can't raise Logic above 5.")
    if cur >= ATTR_MAX:
        raise RuleError(f"{attr} is already at the maximum ({ATTR_MAX}).")
    cost = (cur + 1) * KARMA_PER_RATING
    spend(c, ctx, "karma", cost, f"{attr} {cur} → {cur + 1}")
    c["base_attributes"][attr] = cur + 1
    return f"{attr} raised to {cur + 1}" + ("" if ctx.admin else f" for {cost} Karma.")


def a_autoroll(c, p, ctx):
    _need_unlocked(ctx, "base attributes")
    import secrets
    r = secrets.SystemRandom()
    for attr in D.ATTRIBUTES:
        if attr in ("Essence", "Magic", "Resonance"):
            continue
        c["base_attributes"][attr] = r.randint(1, 6)
    return "Attributes rolled (metatype minimums apply automatically)."


# ---- skills
def a_set_skill(c, p, ctx):
    skill = p.get("skill")
    if skill not in D.SKILLS:
        raise RuleError("Unknown skill.")
    cur = c["skills"].get(skill, 0)
    rank = max(0, min(SKILL_MAX, _int(p.get("rank"), cur))) if "rank" in p else cur
    spec = p.get("spec", c["specializations"].get(skill) or "")
    spec = spec if spec in (D.SKILL_SPECIALIZATIONS.get(skill) or []) else ""
    cur_spec = c["specializations"].get(skill) or ""
    if ctx.locked:
        if rank < cur:
            raise RuleError("Approved sheets can't lower skills.")
        cost = sum(r * KARMA_PER_RATING for r in range(cur + 1, rank + 1))
        if spec and spec != cur_spec:
            if rank == 0:
                raise RuleError("Learn the skill before choosing a specialization.")
            cost += KARMA_SPECIALIZATION
        if cost:
            spend(c, ctx, "karma", cost, f"{skill}" + (f" {cur} → {rank}" if rank != cur else "") +
                  (f", specialization {spec}" if spec and spec != cur_spec else ""))
    c["skills"][skill] = rank
    if spec and rank > 0:
        c["specializations"][skill] = spec
    else:
        c["specializations"].pop(skill, None)
    return "Saved."


# ---- qualities
def _quality_side(q):
    if q in D.QUALITIES["Positive"]:
        return "Positive"
    if q in D.QUALITIES["Negative"]:
        return "Negative"
    raise RuleError("Unknown quality.")


def a_add_quality(c, p, ctx):
    q = p.get("quality")
    side = _quality_side(q)
    if q in c["qualities"]:
        raise RuleError("You already have that quality.")
    if ctx.locked:
        raise RuleError("Qualities can only be changed by the GM once your sheet is approved.")
    karma = (D.QUALITY_EFFECTS.get(q) or {}).get("karma", 0)
    if side == "Positive":
        spend(c, ctx, "karma", karma, f"Quality: {q}")
    elif not ctx.admin:
        gain(c, ctx, "karma", -karma, f"Quality: {q}")
    c["qualities"].append(q)
    return f"{q} added."


def a_remove_quality(c, p, ctx):
    q = p.get("quality")
    side = _quality_side(q)
    if q not in c["qualities"]:
        raise RuleError("You don't have that quality.")
    if ctx.locked:
        raise RuleError("Qualities can only be changed by the GM once your sheet is approved.")
    karma = (D.QUALITY_EFFECTS.get(q) or {}).get("karma", 0)
    if not ctx.admin:
        if side == "Positive":
            gain(c, ctx, "karma", karma, f"Refund: {q}")
        else:
            spend(c, ctx, "karma", -karma, f"Removed negative quality: {q}")
    c["qualities"].remove(q)
    return f"{q} removed."


# ---- gear / store
def a_buy(c, p, ctx):
    cat = p.get("category")
    if cat not in D.GEAR_CATEGORIES:
        raise RuleError("Unknown store category.")
    if len(c["gear"][cat]) >= MAX_LIST:
        raise RuleError("Inventory is full.")
    if p.get("index") is not None:
        raw = predefined(cat, p["index"])
        custom = False
    else:
        raw = p.get("item") or {}
        custom = True
    item = clean_item(raw, cat)
    if custom:
        item["_custom"] = True
    free = ctx.admin and bool(p.get("free", True))
    price = _int(item.get("Price"))
    if not free:
        spend(c, ctx, "nuyen", price, f"Bought {item['name']}")
    c["gear"][cat].append(item)
    if free and ctx.admin:
        return f"{item['name']} added to the inventory."
    return f"Bought {item['name']} for {fmt_money(price)}."


def a_edit_item(c, p, ctx):
    cat = p.get("category")
    if cat not in D.GEAR_CATEGORIES:
        raise RuleError("Unknown category.")
    i = _list_index(c["gear"][cat], p.get("index"))
    old = c["gear"][cat][i]
    new = clean_item(p.get("item") or {}, cat)
    cosmetic = ("name", "description", "Equipped", "Price", "_custom")
    if old.get("_custom") or (not ctx.admin and {k: v for k, v in new.items() if k not in cosmetic} != {k: v for k, v in old.items() if k not in cosmetic}):
        new["_custom"] = True        # a player changed the item's stats: flag it for the GM
    if ctx.locked:
        # after approval only cosmetic fields and the equipped flag can change
        keep = dict(old)
        keep["name"] = new["name"]
        keep["description"] = new["description"]
        if cat in D.EQUIPPABLE_CATEGORIES:
            keep["Equipped"] = new["Equipped"]
        new = keep
    elif not ctx.admin:
        delta = _int(new.get("Price")) - _int(old.get("Price"))
        if delta > 0:
            spend(c, ctx, "nuyen", delta, f"Price change: {new['name']}")
        elif delta < 0:
            gain(c, ctx, "nuyen", -delta, f"Price change: {new['name']}")
    c["gear"][cat][i] = new
    return "Item updated."


def a_toggle_equipped(c, p, ctx):
    cat = p.get("category")
    if cat not in D.EQUIPPABLE_CATEGORIES:
        raise RuleError("Only weapons and armor can be equipped.")
    i = _list_index(c["gear"][cat], p.get("index"))
    it = c["gear"][cat][i]
    it["Equipped"] = "No" if _yes(it.get("Equipped"), True) else "Yes"
    return f"{it['name']} {'equipped' if it['Equipped'] == 'Yes' else 'stored'}."


def a_remove_item(c, p, ctx):
    cat = p.get("category")
    if cat not in D.GEAR_CATEGORIES:
        raise RuleError("Unknown category.")
    i = _list_index(c["gear"][cat], p.get("index"))
    item = c["gear"][cat].pop(i)
    price = _int(item.get("Price"))
    if ctx.refunds and not ctx.admin and price:
        gain(c, ctx, "nuyen", price, f"Refund: {item['name']}")
        return f"{item['name']} returned for {fmt_money(price)}."
    return f"{item['name']} discarded."


def a_use_medkit(c, p, ctx):
    kits = c["gear"]["Medkits"]
    if not kits:
        raise RuleError("You have no medkit.")
    i = _list_index(kits, p.get("index", 0))
    kit = kits[i]
    rating = 1
    rs = str(kit.get("Rating", "1"))
    try:
        rating = int(rs.split()[-1]) if " " in rs else int(float(rs))
    except (ValueError, IndexError):
        pass
    c["physical_damage"] = max(0, c["physical_damage"] - rating * 2)
    c["stun_damage"] = max(0, c["stun_damage"] - rating)
    qty = _int(kit.get("Quantity", 1), 1) - 1
    name = kit.get("name", "Medkit")
    if qty <= 0:
        kits.pop(i)
        tail = " It's used up."
    else:
        kit["Quantity"] = str(qty)
        tail = f" {qty} use{'s' if qty != 1 else ''} left."
    ctx.log.append(f"used {name}: healed up to {rating * 2} Physical and {rating} Stun.")
    return f"{name} applied.{tail}"


def a_rest(c, p, ctx):
    c["stun_damage"] = max(0, c["stun_damage"] - 1)
    return "Rested: 1 box of Stun healed."


# ---- condition monitors
def a_set_damage(c, p, ctx):
    track = p.get("track")
    if track not in ("physical", "stun"):
        raise RuleError("Unknown track.")
    d = derive(c)
    v = max(0, _int(p.get("value")))
    if track == "stun":
        if v > d["stun_boxes"]:
            over = v - d["stun_boxes"]
            c["stun_damage"] = d["stun_boxes"]
            c["physical_damage"] = c["physical_damage"] + over
        else:
            c["stun_damage"] = v
    else:
        c["physical_damage"] = min(v, d["physical_boxes"] + d["overflow_boxes"] + 1)
    return "Condition updated."


def a_damage(c, p, ctx):
    """Add (positive) or heal (negative) boxes on a track, with Stun overflowing into Physical."""
    track = p.get("track")
    n = _int(p.get("amount"))
    if track not in ("physical", "stun") or n == 0:
        raise RuleError("Bad damage.")
    key = f"{track}_damage"
    a_set_damage(c, {"track": track, "value": max(0, c[key] + n)}, ctx)
    word = "healed" if n < 0 else "taken"
    return f"{abs(n)} {track.capitalize()} {word}."


# ---- contacts
def a_save_contact(c, p, ctx):
    raw = p.get("contact") or {}
    name = _clip(raw.get("name"), 80).strip()
    if not name:
        raise RuleError("A contact needs a name.")
    contact = {"name": name, "type": _clip(raw.get("type"), 40), "loyalty": _clip(raw.get("loyalty"), 40),
               "connection": _clip(raw.get("connection"), 40), "notes": _clip(raw.get("notes"), 4000)}
    if p.get("index") is None:
        if len(c["contacts"]) >= MAX_LIST:
            raise RuleError("Too many contacts.")
        c["contacts"].append(contact)
        return f"{name} added."
    i = _list_index(c["contacts"], p["index"])
    c["contacts"][i] = contact
    return "Contact updated."


def a_remove_contact(c, p, ctx):
    i = _list_index(c["contacts"], p.get("index"))
    return f"{c['contacts'].pop(i)['name']} removed."


# ---- magic: spells, powers, foci
def _add_magic(c, p, ctx, kind, key):
    if len(c[key]) >= MAX_LIST:
        raise RuleError("List is full.")
    raw = predefined(kind, p["index"]) if p.get("index") is not None else (p.get("item") or {})
    item = clean_item(raw, kind)
    if p.get("index") is None:
        item["_custom"] = True
    return item


def a_save_spell(c, p, ctx):
    if p.get("edit") is not None:
        i = _list_index(c["spells"], p["edit"])
        if ctx.locked:
            raise RuleError("Learned spells can only be edited by the GM after approval.")
        c["spells"][i] = clean_item(p.get("item") or {}, "Spell")
        return "Spell updated."
    item = _add_magic(c, p, ctx, "Spell", "spells")
    if ctx.approved:
        spend(c, ctx, "karma", KARMA_SPELL, f"Learned spell: {item['name']}")
    c["spells"].append(item)
    return f"Learned {item['name']}" + (f" for {KARMA_SPELL} Karma." if ctx.approved and not ctx.admin else ".")


def a_remove_spell(c, p, ctx):
    _need_unlocked(ctx, "spells")
    i = _list_index(c["spells"], p.get("index"))
    return f"{c['spells'].pop(i)['name']} forgotten."


def a_save_power(c, p, ctx):
    if p.get("edit") is not None:
        i = _list_index(c["powers"], p["edit"])
        _need_unlocked(ctx, "adept powers")
        c["powers"][i] = clean_item(p.get("item") or {}, "Power")
        msg = "Power updated."
    else:
        item = _add_magic(c, p, ctx, "Power", "powers")
        c["powers"].append(item)
        msg = f"{item['name']} added."
    d = derive(c)
    if ctx.locked and d["power_points_used"] > d["power_points_available"]:
        raise RuleError(f"That needs {d['power_points_used']:g} Power Points; you have {d['power_points_available']}.")
    return msg


def a_remove_power(c, p, ctx):
    _need_unlocked(ctx, "adept powers")
    i = _list_index(c["powers"], p.get("index"))
    return f"{c['powers'].pop(i)['name']} removed."


def a_save_focus(c, p, ctx):
    if p.get("edit") is not None:
        _need_unlocked(ctx, "foci")
        i = _list_index(c["foci"], p["edit"])
        old = c["foci"][i]
        new = clean_item(p.get("item") or {}, "Focus")
        new["Bonded"] = old.get("Bonded", "No")
        if not ctx.admin:
            delta = _int(new.get("Price")) - _int(old.get("Price"))
            if delta > 0:
                spend(c, ctx, "nuyen", delta, f"Price change: {new['name']}")
            elif delta < 0:
                gain(c, ctx, "nuyen", -delta, f"Price change: {new['name']}")
        c["foci"][i] = new
        return "Focus updated."
    item = _add_magic(c, p, ctx, "Focus", "foci")
    item["Bonded"] = "No"
    spend(c, ctx, "nuyen", _int(item.get("Price")), f"Bought focus: {item['name']}")
    c["foci"].append(item)
    return f"{item['name']} added. Bond it to use it."


def a_bond_focus(c, p, ctx):
    i = _list_index(c["foci"], p.get("index"))
    f = c["foci"][i]
    cost = focus_bond_cost(f)
    if _yes(f.get("Bonded")):
        if ctx.locked:
            raise RuleError("Unbonding after approval is a GM call.")
        f["Bonded"] = "No"
        if not ctx.admin:
            gain(c, ctx, "karma", cost, f"Unbonded {f['name']}")
        return f"{f['name']} unbonded."
    spend(c, ctx, "karma", cost, f"Bonded {f['name']}")
    f["Bonded"] = "Yes"
    return f"{f['name']} bonded" + ("." if ctx.admin else f" for {cost} Karma.")


def a_remove_focus(c, p, ctx):
    i = _list_index(c["foci"], p.get("index"))
    f = c["foci"][i]
    if ctx.locked:
        raise RuleError("Foci can only be removed by the GM after approval.")
    if not ctx.admin:
        if _yes(f.get("Bonded")):
            gain(c, ctx, "karma", focus_bond_cost(f), f"Bond refund: {f['name']}")
        if _int(f.get("Price")):
            gain(c, ctx, "nuyen", _int(f.get("Price")), f"Refund: {f['name']}")
    c["foci"].pop(i)
    return f"{f['name']} removed."


# ---- GM-only
def a_admin_set(c, p, ctx):
    """GM override for karma / nuyen / current edge (absolute values)."""
    if not ctx.admin:
        raise RuleError("Only the GM can do that.")
    for k in ("karma", "nuyen"):
        if k in p:
            v = _int(p[k], c[k])
            if v != c[k]:
                ctx.ledger.append((k, v - c[k], "GM adjustment"))
                c[k] = v
    if "current_edge" in p:
        c["current_edge"] = max(0, min(EDGE_CAP, _int(p["current_edge"])))
    return "Saved."


ACTIONS = {
    "set_info": a_set_info, "set_portrait": a_set_portrait, "pay_lifestyle": a_pay_lifestyle,
    "trade_karma": a_trade_karma,
    "set_attribute": a_set_attribute, "raise_attribute": a_raise_attribute, "autoroll": a_autoroll,
    "set_skill": a_set_skill,
    "add_quality": a_add_quality, "remove_quality": a_remove_quality,
    "buy": a_buy, "edit_item": a_edit_item, "toggle_equipped": a_toggle_equipped, "remove_item": a_remove_item,
    "use_medkit": a_use_medkit, "rest": a_rest, "set_damage": a_set_damage, "damage": a_damage,
    "save_contact": a_save_contact, "remove_contact": a_remove_contact,
    "save_spell": a_save_spell, "remove_spell": a_remove_spell,
    "save_power": a_save_power, "remove_power": a_remove_power,
    "save_focus": a_save_focus, "bond_focus": a_bond_focus, "remove_focus": a_remove_focus,
    "admin_set": a_admin_set,
}


# --------------------------------------------------------------------------- edge outside rolls
EDGE_SPEND = {
    # key: (cost, label, effect)
    "heal_stun": (3, "Heal 1 box of Stun", "heal_stun"),
    "heal_physical": (4, "Heal 1 box of Physical", "heal_physical"),
    "give": (2, "Give an ally 1 Edge", "give"),
    "negate": (2, "Negate 1 Edge of an opponent", None),
    "glitch2": (5, "Count 2s as glitches on a target's test", None),
    "special": (5, "Create a special effect (with the GM)", None),
}


def spend_edge(c, cost):
    if c["current_edge"] < cost:
        raise RuleError(f"That needs {cost} Edge; you have {c['current_edge']}.")
    c["current_edge"] -= cost

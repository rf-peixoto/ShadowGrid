"""Store catalog built from the core-book gear tables (sr.gear6e).

Responsibilities:
- give every catalog entry a stable id;
- evaluate rated stats ("R*250", "(R/3)(L)") for a chosen rating;
- parse Availability into a number and a legality flag (L = license, I = illegal);
- apply implant grades (Essence, cost and Availability multipliers);
- decide whether a character can buy (or sell) an item through their contacts;
- turn a catalog entry into an inventory item.
"""
import ast
import functools
import math
import re

from . import gear6e as G

CREATION_MAX_AVAIL = 6
ALWAYS_AVAIL = 2          # legal items up to this Availability are on every shelf


class CatalogError(ValueError):
    pass


# --------------------------------------------------------------------------- safe rating expressions
_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.IfExp, ast.Compare,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.USub, ast.UAdd,
            ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.BoolOp, ast.And, ast.Or)


@functools.lru_cache(maxsize=8192)
def _code(expr):
    """Parse, check and compile a rating expression once (the catalog has a few hundred)."""
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise CatalogError(f"Bad expression: {expr}")
        if isinstance(node, ast.Name) and node.id != "R":
            raise CatalogError(f"Bad expression: {expr}")
    return compile(tree, "<catalog>", "eval")


def _eval(expr, rating):
    return eval(_code(str(expr)), {"__builtins__": {}}, {"R": rating})  # noqa: S307 (whitelisted AST)


def num(expr, rating=1, round_up=True):
    """Evaluate a number or an R-expression. Fractions round up (the book's default)."""
    if expr is None or expr == "":
        return 0
    if isinstance(expr, (int, float)):
        return expr
    s = str(expr).strip()
    try:
        v = _eval(s, rating)
    except (CatalogError, SyntaxError, ZeroDivisionError, TypeError):
        return 0
    if isinstance(v, float) and round_up and "." not in s:
        return int(math.ceil(v - 1e-9))
    return v


def ess(expr, rating=1):
    v = num(expr, rating, round_up=False)
    return round(float(v), 2)


def text_with_rating(s, rating):
    """'(R/2)P' -> '2P', '(R/2)/(R)/(R/4)/—/—' -> '2/4/1/—/—'."""
    if not isinstance(s, str) or "R" not in s:
        return s
    return re.sub(r"\(([^()]*R[^()]*)\)|\bR\b", lambda m: str(num(m.group(1) or "R", rating)), s)


def parse_avail(avail, rating=1):
    """-> (number, legality) with legality '' (legal), 'L' (license) or 'I' (illegal)."""
    s = str(avail if avail is not None else "").strip()
    legal = ""
    if s.endswith(("(L)", "(I)")):
        legal, s = s[-2], s[:-3]
    elif len(s) > 1 and s[-1] in "LI" and (s[-2] == ")" or s[-2].isdigit()):
        legal, s = s[-1], s[:-1]
    s = s.strip().lstrip("+").strip()
    n = num(s, rating) if s else 0
    return max(0, int(n)), legal


def avail_text(n, legal):
    return f"{n}" + (f"({legal})" if legal else "")


def parse_dv(dv):
    """'3P' -> (3, 'P', ''), '5S(e)' -> (5, 'S', 'e'), '4P(f)' -> (4, 'P', 'f'). None if not a plain DV."""
    m = re.fullmatch(r"\s*(\d+)\s*([PS])\s*(?:\(?([a-z]+)\)?)?\s*", str(dv or ""))
    if not m:
        return None
    return int(m.group(1)), m.group(2), (m.group(3) or "")


def parse_ar(ar):
    """'10/9/6/—/—' -> [10, 9, 6, None, None] (Close, Near, Medium, Far, Extreme)."""
    parts = str(ar or "").replace(" ", "").split("/")
    out = []
    for p in parts[:5]:
        m = re.match(r"^(\d+)", p)
        out.append(int(m.group(1)) if m else None)
    while len(out) < 5:
        out.append(None)
    return out


def parse_ammo(ammo):
    """'15(c)' -> (15, 'c'); '' -> (0, '')."""
    m = re.match(r"^\s*(\d+)\s*(?:\(([a-z]+)\))?", str(ammo or ""))
    return (int(m.group(1)), m.group(2) or "") if m else (0, "")


def modes_list(modes):
    return [m for m in str(modes or "").split("/") if m in G.FIRING_MODES]


# --------------------------------------------------------------------------- catalog index
def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _build():
    items, seen = [], {}
    for e in G.GEAR_CATALOG:
        if e.get("store") is False:
            continue
        base = _slug(f"{e['cat']}-{e['name']}")
        n = seen.get(base, 0)
        seen[base] = n + 1
        e = dict(e)
        e["id"] = base if not n else f"{base}-{n + 1}"
        e["supply"] = G.CATEGORY_SUPPLY.get(e["cat"], "General")
        items.append(e)
    return items


ITEMS = _build()
BY_ID = {e["id"]: e for e in ITEMS}


def _by_rating():
    """For rated items: [rating, cost, availability, legality, essence] for every rating (used by the store UI)."""
    for e in ITEMS:
        rr = e.get("rating")
        if not rr:
            o = offer(e)
            e["availN"], e["legalN"], e["costN"] = o["avail"], o["legal"], o["cost"]
            if is_implant(e):
                e["essenceN"] = o["essence"]
            continue
        rows = []
        for r in range(int(rr[0]), int(rr[1]) + 1):
            o = offer(e, r)
            rows.append([r, o["cost"], o["avail"], o["legal"], o["essence"]])
        e["byRating"] = rows
        e["availN"], e["legalN"], e["costN"] = rows[0][2], rows[0][3], rows[0][1]


def entry(item_id):
    e = BY_ID.get(str(item_id or ""))
    if not e:
        raise CatalogError("That item is not in the store.")
    return e


def rating_range(e):
    r = e.get("rating")
    return (int(r[0]), int(r[1])) if r else None


def clamp_rating(e, rating):
    rr = rating_range(e)
    if not rr:
        return None
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = rr[0]
    return max(rr[0], min(rr[1], rating))


def is_implant(e):
    return bool(e.get("implant"))


def offer(e, rating=None, grade="Standard", metatype=""):
    """Price, Availability and Essence of a catalog entry with options applied."""
    r = clamp_rating(e, rating) if rating_range(e) else 1
    cost = num(e.get("cost"), r, round_up=False)
    a, legal = parse_avail(e.get("avail"), r)
    essence = ess(e.get("essence"), r) if is_implant(e) else 0.0
    if is_implant(e):
        g = G.IMPLANT_GRADES.get(grade) or G.IMPLANT_GRADES["Standard"]
        cost *= g["cost"]
        essence = round(essence * g["essence"], 2)
        a = max(0, a + g["avail"])
    if isinstance(metatype, (tuple, list)):          # (all gear %, fitted gear %) from rules.price_markup
        all_pct, fitted_pct = metatype
    else:
        size = G_SIZE.get(metatype)
        all_pct = size[1] if size and size[0] == "all" else 0
        fitted_pct = size[1] if size and size[0] == "fitted" else 0
    cost *= 1 + all_pct + (fitted_pct if e["cat"] == "Armor" else 0)
    return {"rating": r if rating_range(e) else None, "cost": int(math.ceil(cost - 1e-9)),
            "avail": a, "legal": legal, "essence": essence}


@functools.lru_cache(maxsize=16384)
def base_offer(eid, markup=(0, 0)):
    """offer() at the base rating and Standard grade, cached per price markup (the store tab's prices)."""
    return offer(BY_ID[eid], None, "Standard", tuple(markup))


G_SIZE = {"Dwarf": ("fitted", 0.10), "Troll": ("all", 0.10)}
_by_rating()


# --------------------------------------------------------------------------- availability through contacts
def contact_supply(ct):
    """What a contact can source: their type's defaults plus the ticked boxes."""
    return set(G.CONTACT_TYPE_SUPPLY.get(ct.get("type") or "", [])) | set(ct.get("supply") or [])


def prepare_contacts(c):
    """[(supply set, connection, verified, name)] for many access() checks in a row."""
    return [(contact_supply(ct), int(ct.get("connection") or 0), ct.get("verified", True), ct.get("name") or "")
            for ct in c.get("contacts") or []]


def access(c, avail, legal, supply, approved, prepared=None):
    """Can this character source an item? -> (ok, reason)."""
    if avail is None:
        return True, ""
    if not approved:
        if avail <= CREATION_MAX_AVAIL:
            return True, ""
        return False, f"Availability {avail}: above the creation limit of {CREATION_MAX_AVAIL}."
    if avail <= ALWAYS_AVAIL and legal != "I":
        return True, ""
    pending = None
    for sup, conn, verified, name in (prepared if prepared is not None else prepare_contacts(c)):
        if (supply in sup or "Fixer" in sup) and conn > avail:
            if verified:
                return True, name
            pending = pending or name or "A contact"
    if pending:
        return False, f"{pending} can get this once the GM confirms them."
    return False, f"Needs a contact for {supply} with Connection {avail + 1} or more."


# --------------------------------------------------------------------------- inventory items
STAT_KEYS = ("dv", "ar", "modes", "ammo", "ammo_class", "fixed_ammo", "skill", "spec", "dr", "capacity",
             "capacity_cost", "device_rating", "data_processing", "firewall", "attack", "sleaze", "program_slots",
             "matrix_init", "dv_gz", "dv_close", "dv_near", "blast", "ammo_for", "ammo_type", "rounds", "mount",
             "handling", "accel", "speed_interval", "top_speed", "body", "armor", "pilot", "sensor", "seats",
             "focus", "medkit", "consumable", "control_rig", "smartlink", "vision", "weapon", "limb_mod", "mod",
             "init_dice", "minor", "phys_boxes", "soak", "unarmed_dv", "unarmed_ar", "heal_bonus", "ignore_boxes",
             "memory_bonus", "lifestyle_mult",
             "Body", "Agility", "Reaction", "Strength", "Willpower", "Logic", "Intuition", "Charisma")


TEXT_KEYS = ("dv", "ar", "dv_gz", "dv_close", "dv_near", "unarmed_dv")
NUM_KEYS = ("dr", "capacity", "capacity_cost", "device_rating", "soak", "phys_boxes", "init_dice", "minor",
            "heal_bonus", "ignore_boxes", "memory_bonus", "unarmed_ar",
            "Body", "Agility", "Reaction", "Strength", "Willpower", "Logic", "Intuition", "Charisma")


def make_item(e, rating=None, grade="Standard", metatype="", uid=""):
    """Inventory item for a catalog entry (stats resolved for the rating)."""
    o = offer(e, rating, grade, metatype)
    r = o["rating"] or 1
    it = {"uid": uid, "ref": e["id"], "name": e["name"], "cat": e["cat"], "sub": e.get("sub", ""),
          "desc": e.get("desc", ""), "cost": o["cost"], "avail": o["avail"], "legal": o["legal"], "qty": 1}
    if o["rating"] is not None:
        it["rating"] = o["rating"]
        it["name"] = f"{e['name']} {o['rating']}" if not re.search(r"\d$", e["name"]) else e["name"]
    if is_implant(e):
        it["implant"] = True
        it["grade"] = grade if grade in G.IMPLANT_GRADES else "Standard"
        it["essence"] = o["essence"]
        if it["grade"] != "Standard":
            it["name"] += f" ({it['grade']})"
    for k in STAT_KEYS:
        if k not in e:
            continue
        v = e[k]
        if isinstance(v, str) and re.search(r"\bR\b", v):
            if k in TEXT_KEYS:
                v = text_with_rating(v, r)
            elif k in NUM_KEYS:
                v = num(v, r, round_up=False)
        it[k] = v
    if e.get("modes") or e.get("ammo"):
        cap, kind = parse_ammo(e.get("ammo"))
        if cap:
            it["clip"] = cap
            it["clip_kind"] = kind
            it["loaded"] = {"rounds": 0, "type": e.get("fixed_ammo") or "Regular"}
    if e["cat"] in ("Melee", "Ranged", "Armor") and not e.get("mod"):
        it["equipped"] = True
    if e["cat"] == "Ammo & Explosives" and e.get("sub") == "Ammunition":
        it["qty"] = int(e.get("rounds") or 1)
        it["unit"] = "rounds" if e.get("ammo_for") not in ("Arrow", "Bolt") else e["ammo_for"].lower() + "s"
    if e.get("focus"):
        it["bonded"] = False
        it["force"] = r
    if e["cat"] in ("Vehicles", "Drones") and not e.get("mod"):
        it["damage"] = 0
    return it


def box_size(e):
    """How many units one purchase gives (ammo comes in boxes of 10)."""
    return int(e.get("rounds") or 1) if e.get("sub") == "Ammunition" else 1


def sell_price(it, pct):
    unit = int(it.get("cost") or 0)
    if it.get("unit") == "rounds":
        unit = unit / 10.0
    q = max(1, int(it.get("qty") or 1))
    return int(math.floor(unit * q * max(0, min(100, pct)) / 100.0))


def store_view(c, approved):
    """Catalog entries with the character's access to each (for the store tab)."""
    out = []
    for e in ITEMS:
        o = offer(e, None, "Standard", c.get("metatype", ""))
        ok, why = access(c, o["avail"], o["legal"], e["supply"], approved)
        row = {k: v for k, v in e.items() if k not in ("rating",)}
        row.update({"price": o["cost"], "availN": o["avail"], "legal": o["legal"], "essenceN": o["essence"],
                    "ok": ok, "why": why if not ok else "", "via": why if ok else ""})
        if e.get("rating"):
            row["rating"] = list(rating_range(e))
        out.append(row)
    return out

"""Shadowrun Sixth World character model and every rule that changes a character.

A character is a plain dict stored as JSON (format version 3). ``derive()``
recomputes every derived number and ``apply_action()`` is the single entry
point for changes, so the server is the only place Karma, nuyen, ammo and
damage ever move.

Economy:
- While a sheet is a draft the player edits freely; purchases are refunded in
  full when removed. Store items are limited to Availability 6.
- After GM approval: attributes and skills cost 5 x new rating, a
  specialization or expertise 5, a knowledge skill 3, a spell or complex form
  5, a positive quality 2 x its cost (removing a negative one 2 x its bonus),
  initiation/submersion 10 + new grade. Store items need a contact whose
  Connection beats the item's Availability (legal items up to 2 are always
  available) and items sell back at the game's sell percentage.
- The GM can do anything and never pays.
"""
import copy
import math
import re
import secrets

from . import actions6e as ACT
from . import catalog as CAT
from . import companion6e as SWC
from . import core6e as K
from . import dice as DICE
from . import gear6e as G
from . import magic6e as M
from . import matrix6e as MX
from . import rigging6e as RIG
from . import toxins6e as TOX

FORMAT = 3
EDGE_CAP = 7
MAX_LIST = 300
PORTRAIT_MAX_CHARS = 450_000
ATTRS = K.BASE_ATTRS + ["Magic", "Resonance"]
CORE_ATTRS = K.PHYSICAL + K.MENTAL
MAGIC_TYPES = ["Mundane", "Magician", "Aspected Magician", "Adept", "Mystic Adept", "Technomancer"]
AWAKENED = ("Magician", "Aspected Magician", "Adept", "Mystic Adept")
CASTERS = ("Magician", "Aspected Magician", "Mystic Adept")
ASPECTS = ["Sorcery", "Conjuring", "Enchanting"]
LIFESTYLES = K.LIFESTYLES
CONTACT_TYPES = sorted({"Fixer", "Fence", "Arms Dealer", "Street Doc", "Talismonger", "Decker", "Mechanic", "Smuggler",
                        "Mr. Johnson", "Corporate", "Police", "Gang", "Media", "Bartender", "Beat Cop", "Mafia Consigliere"}
                       | {ct["name"] for ct in SWC.CONTACTS}) + ["Other"]
SUPPLY = G.CONTACT_SUPPLY + ["Fixer"]
LOCKED_INFO = ("metatype", "magic_type", "tradition", "aspect")
ROLES = ["Adept", "Combat Mage", "Covert Ops Specialist", "Decker", "Face", "Rigger", "Street Samurai",
         "Street Shaman", "Technomancer", "Weapons Specialist"]
FREE_INFO = ("name", "role", "mentor_spirit", "lifestyle", "age", "reputation", "heat", "background", "notes")
WOUND_STEP = 3
MAX_INIT_DICE = 5
MAX_MINOR = 5
STATUS_NAMES = list(K.STATUSES)
HEAL_METHODS = ("first_aid", "medkit", "magic", "natural_stun", "natural_physical")


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


def _clip(s, n):
    return str(s if s is not None else "")[:n]


def _half_up(n):
    return (int(n) + 1) // 2


def fmt_money(n):
    return f"{int(n):,}¥"


def roll(n):
    return DICE.new_roll(max(1, n)) if n > 0 else {"hits": 0, "dice": [], "pool": 0, "glitch": False, "critical": False}


def hits_of(n):
    return roll(n)["hits"] if n > 0 else 0


# --------------------------------------------------------------------------- the character
def new_character():
    attrs = {a: 1 for a in K.BASE_ATTRS}
    attrs.update({"Magic": 0, "Resonance": 0})
    return {
        "v": FORMAT, "name": "", "role": "", "metatype": "Human", "magic_type": "Mundane", "tradition": "", "aspect": "",
        "mentor_spirit": "", "lifestyle": "Low", "age": 25, "reputation": 0, "heat": 0,
        "background": "", "notes": "", "portrait": None, "karma": 50, "nuyen": 5000,
        "attributes": attrs,
        "skills": {s: 0 for s in K.SKILLS}, "specs": {}, "expertise": {},
        "knowledge": [], "languages": [], "qualities": [], "inventory": [], "contacts": [],
        "spells": [], "powers": [], "power_points_bought": 0, "complex_forms": [], "spirits": [], "sprites": [],
        "initiation_grade": 0, "metamagics": [], "submersion_grade": 0, "echoes": [],
        "matrix": {"mode": "AR", "device": ""},
        "physical_damage": 0, "stun_damage": 0, "drain_stun": 0, "drain_phys": 0, "heal_used": {},
        "current_edge": 1, "statuses": {}, "uid_seq": 0,
        "infected": "", "infected_powers": [], "infected_essence": None,
        "sustained": [], "toxins": [], "matrix_state": {"os": 0, "os_known": None},
    }


def _uid(c):
    c["uid_seq"] = _int(c.get("uid_seq")) + 1
    return f"i{c['uid_seq']}"


def normalize(c):
    """Fill missing keys and coerce types. Sheets from other formats start over."""
    if not isinstance(c, dict) or c.get("v") != FORMAT:
        c = new_character()
    base = new_character()
    for k, v in base.items():
        if k not in c:
            c[k] = copy.deepcopy(v)
    for a in ATTRS:
        c["attributes"].setdefault(a, base["attributes"][a])
    for s in K.SKILLS:
        c["skills"].setdefault(s, 0)
    c["karma"] = _int(c["karma"])
    c["nuyen"] = _int(c["nuyen"])
    return c


def import_character(raw):
    """A character from a file: same format only, every list capped, strings clipped, and it must derive cleanly."""
    if not isinstance(raw, dict) or raw.get("v") != FORMAT:
        raise RuleError("That character file comes from another version of ShadowGrid.")
    c = copy.deepcopy(raw)
    base = new_character()
    for k, v in list(c.items()):
        if k not in base and k not in ("imported_at", "sustained", "actions", "toxins", "matrix_state", "vehicle_state", "edge_round"):
            c.pop(k)
        elif k in base and type(base[k]) in (list, dict) and not isinstance(v, type(base[k])):
            c[k] = copy.deepcopy(base[k])
        elif isinstance(v, list):
            c[k] = v[:MAX_LIST]
        elif isinstance(v, str):
            c[k] = v[:PORTRAIT_MAX_CHARS if k == "portrait" else 20000]
    c = normalize(c)
    if c.get("portrait") and not str(c["portrait"]).startswith("data:image/"):
        c["portrait"] = None
    try:
        d = derive(c)
        pools(c, d)
        clamp_state(c)
    except Exception:   # noqa: BLE001 - any broken field means the file can't be used
        raise RuleError("That character file is damaged and can't be read.")
    return c


# --------------------------------------------------------------------------- lookups
SPELLS = {s["name"]: s for s in M.SPELLS}
RITUALS = {r["name"]: r for r in M.RITUALS}
POWERS = {p["name"]: p for p in M.ADEPT_POWERS}
FORMS = {f["name"]: f for f in M.COMPLEX_FORMS}
METAMAGICS = {m["name"]: m for m in M.METAMAGICS}
ECHOES = {e["name"]: e for e in M.ECHOES}


def _spell_entry(s):
    return {k: s[k] for k in ("name", "category", "kind", "range", "type", "duration", "drain", "damage",
                              "element", "area", "desc") if k in s}


def meta_of(c):
    return K.METATYPES.get(c.get("metatype")) or K.METATYPES["Human"]


def base_metatype(c):
    """Human/Elf/Dwarf/Ork/Troll for metavariants; the metasapient's own name otherwise."""
    m = meta_of(c)
    return c.get("metatype") if m.get("base") in (None, "Metasapient") else m["base"]


def infected_info(c):
    """The character's HMHVV expression with the attribute maximums for their base metatype, or None."""
    name = c.get("infected") or ""
    inf = SWC.INFECTED.get(name)
    if not inf:
        return None
    base = base_metatype(c)
    if base in inf["bases"]:
        mx = dict(inf["bases"][base])
    elif inf.get("any_base_mods"):
        meta = meta_of(c)
        mx = {a: meta["max"].get(a, K.DEFAULT_MAX) + inf["any_base_mods"].get(a, 0) for a in K.BASE_ATTRS}
    else:
        mx = None
    return dict(inf, name=name, max=mx, base_ok=mx is not None)


def infected_karma(c, name=None):
    name = name if name is not None else c.get("infected")
    inf = SWC.INFECTED.get(name or "")
    if not inf:
        return 0
    k = inf["karma"]
    if inf.get("non_human_extra") and base_metatype(c) != "Human":
        k += inf["non_human_extra"]
    if inf.get("awakened_discount") and c.get("magic_type") in AWAKENED:
        k -= inf["awakened_discount"]
    return k


def qualities_of(c):
    """Chosen qualities plus the metatype's racial ones (free, can't be removed)."""
    meta = meta_of(c)
    out = [dict(q) for q in c.get("qualities") or [] if q.get("name") in K.QUALITIES]
    for q in meta.get("qualities", []):
        out.append({"name": q, "level": meta.get("quality_levels", {}).get(q, 1),
                    "choice": meta.get("quality_choices", {}).get(q, ""), "racial": True})
    return out


def _qeffect(qs, key, choice=None):
    """Sum a quality effect; 'L' expressions scale with the level."""
    total = 0
    for q in qs:
        eff = (K.QUALITIES[q["name"]].get("effects") or {}).get(key)
        if eff is None:
            continue
        if choice is not None and q.get("choice") != choice:
            continue
        lvl = max(1, _int(q.get("level"), 1))
        if isinstance(eff, str):
            total += {"L": lvl, "-L": -lvl, "2*L": 2 * lvl}.get(eff, 0)
        elif isinstance(eff, bool):
            total += 1 if eff else 0
        else:
            total += eff
    return total


def _has_q(qs, name):
    return any(q["name"] == name for q in qs)


def _qlevel(qs, key):
    """Total levels of qualities carrying an effect key (for per-level effects like essence_hole)."""
    return sum(max(1, _int(q.get("level"), 1)) for q in qs if (K.QUALITIES[q["name"]].get("effects") or {}).get(key))


def _qfixed(qs, attr):
    """attr_max_fixed effects ({"Body": "L"} for Shiva Arms, -1 for Neoteny)."""
    total = 0
    for q in qs:
        eff = (K.QUALITIES[q["name"]].get("effects") or {}).get("attr_max_fixed") or {}
        v = eff.get(attr)
        if v is None:
            continue
        lvl = max(1, _int(q.get("level"), 1))
        total += lvl if v == "L" else -lvl if v == "-L" else _int(v)
    return total


def price_markup(c, qs=None):
    """(all gear %, fitted gear %) for size: troll-sized metatypes, dwarfs, and qualities like Bark or Shiva Arms."""
    qs = qs if qs is not None else qualities_of(c)
    meta = meta_of(c)
    size = meta.get("size") or CAT.G_SIZE.get(meta.get("base") or c.get("metatype"))
    all_pct = size[1] if size and size[0] == "all" else 0.0
    fitted = size[1] if size and size[0] == "fitted" else 0.0
    for q in qs:
        f = (K.QUALITIES[q["name"]].get("effects") or {}).get("fitted_markup")
        if f:
            fitted += f * max(1, _int(q.get("level"), 1))
    return (round(all_pct, 3), round(fitted, 3))


def infected_essence_base(c, inf=None):
    inf = inf if inf is not None else infected_info(c)
    if not inf:
        return 6.0
    if inf["strain"] in ("II", "III"):
        return 5.0
    v = c.get("infected_essence")
    return float(_num(v, 6.0)) if v is not None else 6.0


def natural_max(c, attr, qs=None, inf=None):
    qs = qs if qs is not None else qualities_of(c)
    inf = inf if inf is not None else infected_info(c)
    meta = meta_of(c)
    if attr == "Magic":
        if inf:
            base = 5 if inf["strain"] in ("II", "III") else max(1, int(math.floor(infected_essence_base(c, inf) + 1e-9)))
            return base + _int(c.get("initiation_grade"))
        return 6 + _int(c.get("initiation_grade"))
    if attr == "Resonance":
        return 6 + _int(c.get("submersion_grade"))
    mx = meta["max"].get(attr, K.DEFAULT_MAX)
    if inf and inf.get("max") and attr in inf["max"]:
        mx = inf["max"][attr]
    mx += _qeffect(qs, "attr_max", attr) + _qfixed(qs, attr)
    return max(1, min(13, mx))


def implants(c):
    return [it for it in c["inventory"] if it.get("implant")]


def items(c, *cats):
    return [it for it in c["inventory"] if not cats or it.get("cat") in cats]


def find_item(c, uid):
    for it in c["inventory"]:
        if it.get("uid") == uid:
            return it
    raise RuleError("That item is no longer in the inventory. Reload the page.")


def power_level(c, name, choice=None):
    return sum(max(1, _int(p.get("level"), 1)) for p in c.get("powers") or []
               if p.get("name") == name and (choice is None or p.get("choice") == choice))


def skill_attr(skill):
    return K.SKILLS[skill]["attr"] if skill in K.SKILLS else "Agility"


# --------------------------------------------------------------------------- derived stats
def derive(c):
    """Every derived value of a character."""
    qs = qualities_of(c)
    inf = infected_info(c)
    meta = meta_of(c)
    base = c["attributes"]
    mtype = c.get("magic_type")
    awakened = mtype in AWAKENED or bool(inf)
    A, bonuses, maxes = {}, {}, {}
    for a in ATTRS:
        mx = natural_max(c, a, qs, inf)
        lo = 0 if a in ("Magic", "Resonance") else 1
        maxes[a] = mx
        A[a] = max(lo, min(mx, _int(base.get(a), lo)))
    if not awakened:
        A["Magic"] = 0
    elif inf and A["Magic"] < 1:
        A["Magic"] = 1
    if mtype != "Technomancer" or inf:
        A["Resonance"] = 0

    def bump(attr, amount, source):
        if amount:
            bonuses.setdefault(attr, []).append([source, amount])

    # Essence and its loss
    mult = 2 if _has_q(qs, "Sensitive System") else 1
    hole = round(0.1 * _qlevel(qs, "essence_hole"), 2)               # Augmentation Acclimation / Cyborg
    implant_ess = sum(_num(it.get("essence")) * mult for it in implants(c))
    essence_base = infected_essence_base(c, inf)
    essence = round(max(0.0, essence_base - max(0.0, implant_ess - hole)), 2)
    loss = 0 if essence >= 6 or inf else 6 - math.floor(essence + 1e-9)
    for a in ("Magic", "Resonance"):
        if A[a] and loss:
            bump(a, -min(loss, A[a]), "Essence loss")
    if inf:
        for a, n in (inf.get("minus") or {}).items():
            bump(a, -n, c["infected"])

    # augmentations
    init_dice = 1
    for it in implants(c):
        for a in CORE_ATTRS:
            if it.get(a):
                bump(a, _int(it[a]), it["name"])
        init_dice += _int(it.get("init_dice"))
    if mtype in ("Adept", "Mystic Adept"):
        for p in c.get("powers") or []:
            lvl = max(1, _int(p.get("level"), 1))
            if p.get("name") == "Improved Physical Attribute" and p.get("choice") in K.PHYSICAL:
                bump(p["choice"], lvl, "Improved Physical Attribute")
            elif p.get("name") == "Improved Reflexes":
                bump("Reaction", lvl, "Improved Reflexes")
                init_dice += lvl
    for t in c.get("toxins") or []:                 # drugs in effect
        for a, n in (t.get("attrs") or {}).items():
            if a in CORE_ATTRS:
                bump(a, _int(n), t.get("name") or "Drug")
        init_dice += _int(t.get("init_dice"))
    aug = {}
    for a in ATTRS:
        total = sum(b[1] for b in bonuses.get(a, []))
        if a in CORE_ATTRS:
            total = min(total, K.AUGMENTED_BONUS_MAX)
        aug[a] = max(0, A[a] + total)
    for t in c.get("toxins") or []:                 # a crash can drop attributes to 0 (Novacoke)
        for a in t.get("zero") or []:
            if a in aug:
                aug[a] = 0
    if inf:
        init_dice += _int(inf.get("init_dice"))
    init_dice = max(1, min(MAX_INIT_DICE, init_dice))

    # armor and Defense Rating: best body armor + helmets/shields + implants + qualities + powers
    worn = [it for it in items(c, "Armor") if it.get("equipped") and not it.get("mod")]
    body_armor = max([_int(it.get("dr")) for it in worn if it.get("sub") != "Helmets & Shields"] or [0])
    extra = sum(_int(it.get("dr")) for it in worn if it.get("sub") == "Helmets & Shields")
    impl_dr = sum(_int(it.get("dr")) for it in implants(c) if not it.get("limb_mod"))
    q_dr = _qeffect(qs, "dr")
    p_dr = power_level(c, "Mystic Armor") if mtype in ("Adept", "Mystic Adept") else 0
    n_dr = _int(meta.get("dr")) + (_int(inf.get("dr")) + sum(1 for x in c.get("infected_powers") or [] if x.startswith("Armor"))
                                   if inf else 0)
    armor = body_armor + extra + impl_dr + q_dr + p_dr + n_dr
    armor_parts = [p for p in (["Body armor", body_armor], ["Helmet/shield", extra], ["Implants", impl_dr],
                               ["Qualities", q_dr], ["Mystic Armor", p_dr], ["Natural armor", n_dr]) if p[1]]

    # condition monitors
    limbs = sum(_int(it.get("phys_boxes")) for it in implants(c))
    base_boxes = 6 + aug["Body"] // 2 if _qeffect(qs, "neoteny") else 8 + _half_up(aug["Body"])
    p_boxes = base_boxes + _qeffect(qs, "phys_boxes") + limbs + (_int(inf.get("phys_boxes")) if inf else 0)
    s_boxes = max(2, 8 + _half_up(aug["Willpower"]) + _qeffect(qs, "stun_boxes"))
    overflow = 2 * aug["Body"] + _qeffect(qs, "overflow")
    pd = max(0, _int(c.get("physical_damage")))
    sd = max(0, _int(c.get("stun_damage")))
    ignore = sum(_int(it.get("ignore_boxes")) for it in implants(c))
    ignore += power_level(c, "Pain Resistance") if mtype in ("Adept", "Mystic Adept") else 0
    wp = max(0, min(pd, p_boxes) - ignore) // WOUND_STEP
    ws = max(0, min(sd, s_boxes) - ignore) // WOUND_STEP
    wound = wp + ws
    if wound and _has_q(qs, "High Pain Tolerance"):
        wound = max(0, wound - 1)
    drug_hpt = max([_int(t.get("hpt")) for t in c.get("toxins") or []] or [0])
    if wound and drug_hpt:
        wound = max(0, wound - drug_hpt)
    if _has_q(qs, "Low Pain Tolerance"):
        wound *= 2
    wound = -wound
    if pd >= p_boxes + overflow:
        status = "Dead"
    elif pd >= p_boxes:
        status = "Dying"
    elif sd >= s_boxes:
        status = "Unconscious"
    elif wound:
        status = "Wounded"
    else:
        status = "OK"

    # magic
    trad_attr = M.TRADITIONS.get(c.get("tradition") or "", "Logic")
    pp_avail = 0.0
    if mtype == "Adept":
        pp_avail = float(aug["Magic"])
    elif mtype == "Mystic Adept":
        pp_avail = float(min(_int(c.get("power_points_bought")), aug["Magic"]))
    pp_avail += sum(1 for m in c.get("metamagics") or [] if m == "Power Point")
    pp_used = 0.0
    for p in c.get("powers") or []:
        meta = POWERS.get(p.get("name")) or {}
        cost = meta.get("cost", 1)
        if p.get("name") == "Improved Ability" and p.get("choice") in ("Close Combat", "Firearms", "Exotic Weapons", "Athletics"):
            cost = meta.get("combat_cost", cost)
        pp_used += cost * (max(1, _int(p.get("level"), 1)) if meta.get("levels") else 1)
    bonded = [it for it in c["inventory"] if it.get("focus") and it.get("bonded")]
    power_focus = max([_int(it.get("force")) for it in bonded if it.get("focus") == "Power"] or [0])

    # matrix
    mx = matrix_stats(c, aug)

    # unarmed
    unarmed_dv = _half_up(aug["Strength"])
    phys_unarmed = bool(_qeffect(qs, "unarmed_physical")) or power_level(c, "Killing Hands") > 0
    for it in implants(c):
        if it.get("unarmed_dv"):
            dvp = CAT.parse_dv(it["unarmed_dv"])
            if dvp:
                unarmed_dv = max(unarmed_dv, dvp[0])
                phys_unarmed = True
    unarmed_dv += _qeffect(qs, "unarmed_dv_bonus") + (power_level(c, "Critical Strike") if mtype in ("Adept", "Mystic Adept") else 0)
    unarmed_ar = aug["Reaction"] + aug["Strength"] + max([_int(it.get("unarmed_ar")) for it in implants(c)] or [0])

    lifestyle_mult = SWC.INFECTED_LIFESTYLE_MULT if inf else 1.0
    for q in qs:
        lifestyle_mult *= (K.QUALITIES[q["name"]].get("effects") or {}).get("lifestyle_mult", 1)
    for it in implants(c):
        if it.get("lifestyle_mult"):
            lifestyle_mult *= _num(it["lifestyle_mult"], 1)

    knowledge_free = aug["Logic"]
    # movement: metatype base, Celerity/Satyr Legs, +2 for most Infected
    move = list(meta.get("move") or [10, 15, 1])
    for q in qs:
        mv = (K.QUALITIES[q["name"]].get("effects") or {}).get("move")
        if mv:
            move = [move[i] + mv[i] for i in range(3)]
    if inf and inf.get("move"):
        move = [move[0] + inf["move"], move[1] + inf["move"], move[2]]
    minor = min(MAX_MINOR + _qeffect(qs, "minor_actions"), 1 + init_dice + _qeffect(qs, "minor_actions"))
    if _qeffect(qs, "cyber_psychosis") and _int(c.get("current_edge")) <= 0:
        minor = max(1, minor - _qeffect(qs, "cyber_psychosis"))
    visions = {(K.QUALITIES[q["name"]].get("effects") or {}).get("vision") for q in qs
               if (K.QUALITIES[q["name"]].get("effects") or {}).get("vision")} | {it["vision"] for it in implants(c) if it.get("vision")}
    if inf:
        visions |= {v for v in (inf.get("vision"), inf.get("vision2")) if v}
    composure = aug["Willpower"] + aug["Charisma"] - (init_dice if _qeffect(qs, "twitchy") else 0)
    return {
        "attributes": aug, "base": A, "max": maxes, "bonuses": bonuses, "essence": essence,
        "qualities": qs, "vision": sorted(visions),
        "physical_boxes": p_boxes, "stun_boxes": s_boxes, "overflow_boxes": overflow,
        "physical_damage": pd, "stun_damage": sd, "wound_modifier": wound, "status": status,
        "initiative_score": aug["Reaction"] + aug["Intuition"], "initiative_dice": init_dice,
        "major_actions": 1, "minor_actions": minor,
        "astral_initiative": {"score": aug["Logic"] + aug["Intuition"], "dice": 2} if awakened else None,
        "matrix": mx,
        "armor": armor, "armor_parts": armor_parts, "defense_rating": aug["Body"] + armor,
        "unarmed": {"dv": unarmed_dv, "type": "P" if phys_unarmed else "S", "ar": unarmed_ar},
        "composure": composure, "judge_intentions": aug["Willpower"] + aug["Intuition"],
        "memory": aug["Logic"] + aug["Intuition"], "lift_carry": aug["Body"] + aug["Willpower"],
        "lift_kg": aug["Strength"] ** 2 * 10, "overhead_kg": aug["Strength"] ** 2 * 5,
        "movement": {"walk": move[0], "sprint": move[1], "per_hit": move[2], "note": meta.get("move_note", "")},
        "natural_weapons": natural_weapons(c, qs, inf, aug), "price_markup": price_markup(c, qs),
        "infected": {"name": inf["name"], "strain": inf["strain"], "base_ok": inf["base_ok"], "powers": inf["powers"],
                     "weaknesses": inf["weaknesses"], "optional": inf.get("optional", []), "chosen": c.get("infected_powers") or [],
                     "free_optional": inf.get("free_optional", ""), "notes": inf.get("notes", ""),
                     "strain_text": SWC.STRAINS[inf["strain"]], "essence_base": essence_base} if inf else None,
        "essence_hole": hole, "awakened": awakened,
        "sustained": len(c.get("sustained") or []), "sustain_penalty": sustain_count(c) * sustain_step(c),
        "edge_max": min(EDGE_CAP, aug["Edge"]), "current_edge": _int(c.get("current_edge")),
        "tradition_attr": trad_attr, "spell_ar": aug["Magic"] + aug.get(trad_attr, 0),
        "drain_pool": aug["Willpower"] + (aug.get(trad_attr, 0) if mtype in CASTERS else aug["Body"]),
        "power_focus": power_focus,
        "fading_pool": aug["Willpower"] + aug["Logic"],
        "form_ar": c["skills"].get("Electronics", 0) + aug["Resonance"],
        "power_points_available": round(pp_avail, 2), "power_points_used": round(pp_used, 2),
        "knowledge_free": knowledge_free, "knowledge_used": len(c.get("knowledge") or []) + len(c.get("languages") or []),
        "spirit_force_limit": aug["Magic"] * 3, "sprite_limit": aug["Resonance"],
        "gear_value": int(sum(_int(it.get("cost")) * (1 if it.get("unit") else max(1, _int(it.get("qty"), 1)))
                              for it in c["inventory"])),
        "lifestyle_cost": lifestyle_cost(c, lifestyle_mult), "lifestyle_mult": round(lifestyle_mult, 3),
        "vehicles": [{"uid": it["uid"], "boxes": 8 + _half_up(_int(it.get("body"))), "damage": _int(it.get("damage"))}
                     for it in items(c, "Vehicles", "Drones") if not it.get("mod")],
        "statuses": c.get("statuses") or {},
    }


def natural_weapons(c, qs, inf, aug):
    """Claws, fangs, horns and kicks from the metatype, metagenic qualities and HMHVV."""
    out = []
    for w in meta_of(c).get("weapons") or []:
        out.append(dict(w, source=c.get("metatype")))
    for q in qs:
        nw = (K.QUALITIES[q["name"]].get("effects") or {}).get("natural_weapon")
        if nw:
            w = dict(nw, source=q["name"])
            if q["name"] == "Corrosive Spit":
                w["dv"] = f"{2 * min(4, max(1, _int(q.get('level'), 1)))}P"
            out.append(w)
    if inf:
        sharp = "Sharpened Natural Weapon" in (c.get("infected_powers") or [])
        for name, dv, ar in inf.get("weapons") or []:
            m = re.match(r"(\d+)(\w)", dv)
            dvn, t = int(m.group(1)), m.group(2)
            if sharp and name == (inf.get("weapons") or [[""]])[0][0]:
                dvn, ar = dvn + 1, ar + 2
            out.append({"name": name, "skill": "Close Combat", "dv": f"{dvn}{t}", "ar": f"{ar}/—/—/—/—", "source": c["infected"]})
    for w in out:
        if w["name"] == "Horns" and aug.get("Strength", 0) >= 6:
            a = CAT.parse_ar(w["ar"])
            w["ar"] = "/".join("—" if x is None else str(x + 2) for x in a)
    return out


def lifestyle_cost(c, mult=1.0):
    return int(round(LIFESTYLES.get(c.get("lifestyle"), 0) * mult))


def matrix_stats(c, aug):
    """Matrix attributes of the active device (cyberdeck, commlink or living persona)."""
    m = c.get("matrix") or {}
    mode = m.get("mode") if m.get("mode") in M.MATRIX_INIT else "AR"
    jacks = [it for it in implants(c) if it.get("data_processing")]
    links = [it for it in c["inventory"] if it.get("sub") in ("Commlinks", "RCCs") or it.get("ref", "") == "cyberware-commlink-headware"]
    decks = [it for it in c["inventory"] if it.get("sub") == "Cyberdecks"]
    dev = None
    if m.get("device") == "persona" and c.get("magic_type") == "Technomancer":
        dev = "persona"
    else:
        dev = next((it for it in decks + links if it.get("uid") == m.get("device")), None) or (decks[0] if decks else (links[0] if links else None))
    ms = c.get("matrix_state") or {}
    out = {"mode": mode, "device": None, "attack": 0, "sleaze": 0, "data_processing": 0, "firewall": 0,
           "device_rating": 0, "slots": 0, "programs": [], "boxes": 0, "damage": 0, "penalty": 0,
           "os": _int(ms.get("os")), "os_known": ms.get("os_known")}
    if dev == "persona":
        out.update({"device": "persona", "name": "Living persona", "attack": aug["Charisma"], "sleaze": aug["Intuition"],
                    "data_processing": aug["Logic"], "firewall": aug["Willpower"], "device_rating": aug["Resonance"],
                    "slots": 0, "damage": _int(m.get("persona_damage"))})
    elif dev:
        jack = max(jacks, key=lambda it: _int(it.get("data_processing")), default=None)
        link_best = max(links, key=lambda it: _int(it.get("data_processing")), default=None)
        dp_src = jack or link_best
        dp, fw = _int((dp_src or dev).get("data_processing")), _int((dp_src or dev).get("firewall"))
        if jack and dp_src is jack and _has_q(qualities_of(c), "Cyberjack Maximization"):
            if dp <= fw:
                dp += 1
            else:
                fw += 1
        out.update({"device": dev["uid"], "name": dev["name"],
                    "attack": _int(dev.get("attack")), "sleaze": _int(dev.get("sleaze")),
                    "data_processing": dp,
                    "firewall": fw,
                    "device_rating": _int(dev.get("device_rating")),
                    "slots": _int(dev.get("program_slots")), "damage": _int(dev.get("matrix_damage"))})
    else:
        return out
    out["boxes"] = 8 + _half_up(out["device_rating"])
    if dev == "persona":                       # errata: the living persona uses the Stun Condition Monitor
        out["boxes"] = 8 + _half_up(aug["Willpower"])
        out["damage"] = _int(c.get("stun_damage"))
        out["stun"] = True
    out["penalty"] = -(min(out["damage"], out["boxes"]) // MX.DEVICE_PENALTY_STEP)
    out["ar"] = out["attack"] + out["sleaze"]
    out["dr"] = out["data_processing"] + out["firewall"]
    attr, dice = M.MATRIX_INIT[mode]
    out["init_score"] = aug["Intuition"] + (aug["Reaction"] if attr == "Reaction" else out["data_processing"])
    out["init_dice"] = dice
    out["programs"] = [{"uid": it["uid"], "name": it.get("choice") or it["name"], "running": bool(it.get("running"))}
                       for it in c["inventory"] if it.get("sub") == "Software" and it.get("ref", "").startswith("cyberdecks-software-cyberprogram")]
    return out


def condition_summary(c, d=None):
    d = d or derive(c)
    return {"p": d["physical_damage"], "pm": d["physical_boxes"], "s": d["stun_damage"], "sm": d["stun_boxes"],
            "ov": d["overflow_boxes"], "status": d["status"], "wound": d["wound_modifier"]}


# --------------------------------------------------------------------------- dice pools
def _skill_parts(c, d, skill, attr=None, focus=None, extra_attr=None):
    """Skill + attribute (+2 specialization / +3 expertise when ``focus`` matches)."""
    A = d["attributes"]
    attr = attr or skill_attr(skill)
    rank = c["skills"].get(skill, 0)
    parts = [[attr, A.get(attr, 0)]]
    if rank > 0:
        parts.append([skill, rank])
        if focus and c["expertise"].get(skill) == focus:
            parts.append([f"Expertise ({focus})", K.EXPERTISE_BONUS])
        elif focus and c["specs"].get(skill) == focus:
            parts.append([f"Specialization ({focus})", K.SPEC_BONUS])
    elif K.SKILLS.get(skill, {}).get("untrained", True):
        parts.append([f"{skill} (untrained)", -1])
    else:
        return None
    for p in c.get("powers") or []:
        if p.get("name") == "Improved Ability" and p.get("choice") == skill and c.get("magic_type") in ("Adept", "Mystic Adept"):
            parts.append(["Improved Ability", min(max(1, _int(p.get("level"), 1)), math.ceil(rank * 1.5))])
    return parts


def _pool(key, group, label, parts, **meta):
    o = {"key": key, "group": group, "label": label, "parts": parts, "value": max(0, sum(p[1] for p in parts))}
    o.update(meta)
    return o


def weapon_items(c):
    """Items that can be used to attack (weapons, implant weapons, throwables)."""
    out = []
    for it in c["inventory"]:
        if it.get("cat") in ("Melee", "Ranged") and it.get("equipped", True) and it.get("dv"):
            out.append(it)
        elif it.get("implant") and isinstance(it.get("weapon"), dict):
            out.append(it)
        elif it.get("cat") == "Ammo & Explosives" and it.get("dv_gz") and it.get("sub") == "Grenades":
            out.append(it)
    return out


def weapon_profile(c, d, it, mode=None, rng=None, ammo_type=None):
    """Attack pool, Attack Rating, DV and ammo use of one weapon."""
    w = it.get("weapon") if isinstance(it.get("weapon"), dict) else it
    skill = w.get("skill") or "Close Combat"
    focus = w.get("spec")
    parts = _skill_parts(c, d, skill, focus=focus)
    if parts is None:
        return None
    grenade = bool(it.get("dv_gz"))
    if grenade:
        dv_text = it.get("dv_gz")
        ar = CAT.parse_ar(it.get("ar") or "8/8/4/—/—")
    else:
        dv_text = w.get("dv")
        ar = CAT.parse_ar(w.get("ar"))
    dvp = CAT.parse_dv(dv_text)
    dv, dtype, flag = dvp if dvp else (0, "P", "")
    modes = CAT.modes_list(it.get("modes"))
    if mode == "":            # stats without a firing mode applied (the roller adds the chosen mode)
        mode = None
    else:
        mode = mode if mode in modes else (modes[0] if modes else None)
    loaded = it.get("loaded") or {}
    atype = loaded.get("type") or "Regular"
    ammo = G.AMMO_TYPES.get(atype) or G.AMMO_TYPES["Regular"]
    ar_mod = 0
    dv_mod = 0
    notes = []
    if mode:
        fm = G.FIRING_MODES[mode]
        ar_mod += fm["ar"]
        dv_mod += fm["dv"]
    if it.get("clip"):
        ar_mod += ammo["ar"]
        dv_mod += ammo["dv"]
        if ammo.get("stun"):
            dtype = "S"
        if ammo.get("elec"):
            flag = "e"
        if atype != "Regular":
            notes.append(f"{atype} ammo")
    if power_level(c, "Enhanced Accuracy") and c.get("magic_type") in ("Adept", "Mystic Adept"):
        ar_mod += 2
        notes.append("Enhanced Accuracy +2 AR")
    fav = next((q for q in c.get("qualities") or [] if q.get("name") == "Favored Weapon: An Extension of Yourself"), None)
    if fav and fav.get("choice") and fav["choice"].lower() in (it.get("name") or "").lower():
        ar_mod += 2
        parts = parts + [["Favored weapon", 1]]
        notes.append("Favored weapon +1 die, +2 AR")
    if it.get("cat") == "Melee" or (it.get("implant") and it.get("weapon")):
        crit = power_level(c, "Critical Strike") if c.get("magic_type") in ("Adept", "Mystic Adept") else 0
        if crit:
            dv_mod += crit
            notes.append(f"Critical Strike +{crit} DV")
    ars = [None if a is None else max(0, a + ar_mod) for a in ar]
    elem = {"e": "Electricity", "f": "", "c": "Cold"}.get(flag, "")
    return {"skill": skill, "parts": parts, "ar": ars, "ar_at": (ars[G.RANGES.index(rng)] if rng in G.RANGES else ars[0]),
            "dv": dv + dv_mod, "type": dtype, "element": elem, "mode": mode, "modes": modes,
            "rounds": G.FIRING_MODES[mode]["rounds"] if mode and it.get("clip") else 0,
            "loaded": loaded.get("rounds") if it.get("clip") else None, "clip": it.get("clip"),
            "consumable": bool(it.get("consumable") or grenade), "blast": it.get("blast"),
            "grenade": [it.get("dv_gz"), it.get("dv_close"), it.get("dv_near")] if grenade else None,
            "notes": notes}


def unarmed_profile(c, d):
    parts = _skill_parts(c, d, "Close Combat", focus="Unarmed Combat")
    u = d["unarmed"]
    return {"skill": "Close Combat", "parts": parts, "ar": [u["ar"], None, None, None, None], "ar_at": u["ar"],
            "dv": u["dv"], "type": u["type"], "element": "", "mode": None, "modes": [], "rounds": 0,
            "loaded": None, "clip": None, "consumable": False, "notes": []}


def spell_profile(c, d, sp, amp=0):
    """Casting pool, Attack Rating, base DV and drain of a spell."""
    parts = _skill_parts(c, d, "Sorcery", attr="Magic", focus="Spellcasting")
    if parts is None:
        return None
    if d["power_focus"]:
        parts.append(["Power focus", d["power_focus"]])
    combat = sp.get("category") == "Combat"
    amp = max(0, _int(amp)) if combat else 0
    base_dv = 0
    if combat and sp.get("kind") == "Indirect":
        base_dv = _half_up(d["attributes"]["Magic"]) + amp
    elif combat:
        base_dv = amp
    elem = sp.get("element") or ""
    return {"skill": "Sorcery", "parts": parts, "ar_at": d["spell_ar"], "ar": [d["spell_ar"]] * 5,
            "dv": base_dv, "type": sp.get("damage") or "P", "element": elem, "direct": sp.get("kind") == "Direct",
            "mana": sp.get("type") == "M", "drain": _int(sp.get("drain")) + amp * M.AMP_UP_DRAIN, "combat": combat}


def pools(c, d=None):
    """Every pool a player can pick in the dice roller, computed from the sheet."""
    d = d or derive(c)
    A = d["attributes"]
    out = []
    for skill in K.SKILLS:
        parts = _skill_parts(c, d, skill)
        if parts is not None:
            out.append(_pool(f"skill:{skill}", "Skills", skill, parts))
        for focus, kind in ((c["specs"].get(skill), "spec"), (c["expertise"].get(skill), "exp")):
            if focus and c["skills"].get(skill, 0) > 0:
                out.append(_pool(f"{kind}:{skill}:{focus}", "Skills", f"{skill} ({focus})", _skill_parts(c, d, skill, focus=focus)))
    for it in weapon_items(c):
        prof = weapon_profile(c, d, it, "")
        if prof:
            out.append(_pool(f"weapon:{it['uid']}", "Weapons", it["name"], prof["parts"], weapon=True, modes=prof["modes"],
                             ar=prof["ar"], dv=f"{prof['dv']}{prof['type']}", loaded=prof["loaded"], clip=prof["clip"],
                             consumable=prof["consumable"], qty=_int(it.get("qty"), 1), element=prof["element"]))
    for i, w in enumerate(d.get("natural_weapons") or []):
        prof = weapon_profile(c, d, {"name": w["name"], "skill": w["skill"], "spec": "Unarmed Combat" if w["skill"] == "Close Combat" else None,
                                     "dv": w["dv"], "ar": w["ar"], "cat": "Melee"}, "")
        if prof:
            out.append(_pool(f"natural:{i}", "Weapons", f"{w['name']} ({w['source']})", prof["parts"], weapon=True, modes=[],
                             ar=prof["ar"], dv=f"{prof['dv']}{prof['type']}", natural=True))
    up = unarmed_profile(c, d)
    out.append(_pool("weapon:unarmed", "Weapons", "Unarmed strike", up["parts"], weapon=True, modes=[], ar=up["ar"],
                     dv=f"{up['dv']}{up['type']}"))
    if c.get("magic_type") in CASTERS:
        for i, sp in enumerate(c.get("spells") or []):
            prof = spell_profile(c, d, sp)
            if prof:
                out.append(_pool(f"spell:{i}", "Magic", f"Cast {sp['name']}", prof["parts"], spell=True,
                                 drain=prof["drain"], combat=prof["combat"]))
        out.append(_pool("drain", "Magic", "Drain resistance", [["Willpower", A["Willpower"]], [d["tradition_attr"], A[d["tradition_attr"]]]]))
    if c.get("magic_type") in ("Magician", "Mystic Adept") or (c.get("magic_type") == "Aspected Magician" and c.get("aspect") == "Conjuring"):
        parts = _skill_parts(c, d, "Conjuring", attr="Magic", focus="Summoning")
        if parts:
            out.append(_pool("summon", "Magic", "Summon spirit", parts))
        parts = _skill_parts(c, d, "Conjuring", attr="Magic", focus="Banishing")
        if parts:
            out.append(_pool("banish", "Magic", "Banish spirit", parts))
    if c.get("magic_type") in AWAKENED or c.get("infected"):
        out.append(_pool("astral_defense", "Magic", "Astral defense", [["Intuition", A["Intuition"]], ["Logic", A["Logic"]]]))
    if c.get("magic_type") == "Technomancer":
        for i, f in enumerate(c.get("complex_forms") or []):
            sk = "Cracking" if f.get("name") == "Resonance Spike" else "Electronics"
            parts = _skill_parts(c, d, sk, attr="Resonance")
            if parts:
                meta = FORMS.get(f.get("name")) or {}
                out.append(_pool(f"form:{i}", "Resonance", f"Thread {f['name']}", parts, form=True, fade=meta.get("fade", 0)))
        out.append(_pool("fading", "Resonance", "Fading resistance", [["Willpower", A["Willpower"]], ["Logic", A["Logic"]]]))
        parts = _skill_parts(c, d, "Tasking", attr="Resonance", focus="Compiling")
        if parts:
            out.append(_pool("compile", "Resonance", "Compile sprite", parts))
    mx = d["matrix"]
    if mx.get("device"):
        out.append(_pool("matrix_defense", "Matrix", "Matrix defense", [["Intuition", A["Intuition"]], ["Firewall", mx["firewall"]]]))
    defense = [["Reaction", A["Reaction"]], ["Intuition", A["Intuition"]]]
    cs = power_level(c, "Combat Sense") if c.get("magic_type") in ("Adept", "Mystic Adept") else 0
    if cs:
        defense.append(["Combat Sense", cs])
    out.append(_pool("defense", "Combat", "Defense test", defense))
    soak = [["Body", A["Body"]]] + [[it["name"], _int(it.get("soak"))] for it in implants(c) if _int(it.get("soak"))]
    out.append(_pool("soak", "Combat", "Damage resistance", soak))
    out.append(_pool("toxin", "Combat", "Toxin resistance", [["Body", A["Body"]], ["Willpower", A["Willpower"]]]))
    out.extend(heal_pools(c, d))
    out.append(_pool("composure", "Attribute tests", "Composure", [["Willpower", A["Willpower"]], ["Charisma", A["Charisma"]]]))
    out.append(_pool("judge", "Attribute tests", "Judge intentions", [["Willpower", A["Willpower"]], ["Intuition", A["Intuition"]]]))
    mem = [["Logic", A["Logic"]], ["Intuition", A["Intuition"]]]
    for it in implants(c):
        if _int(it.get("memory_bonus")):
            mem.append([it["name"], _int(it["memory_bonus"])])
    out.append(_pool("memory", "Attribute tests", "Memory", mem))
    out.append(_pool("lift", "Attribute tests", "Lift / carry", [["Body", A["Body"]], ["Willpower", A["Willpower"]]]))
    out.append(_pool("surprise", "Attribute tests", "Surprise", [["Reaction", A["Reaction"]], ["Intuition", A["Intuition"]]]))
    for a in ATTRS:
        if a in ("Magic", "Resonance") and not A[a]:
            continue
        out.append(_pool(f"attr:{a}", "Single attribute", a, [[a, A.get(a, 0)]]))
    mx = d["matrix"]
    if mx.get("device"):
        for key, a in MX.MATRIX_ACTIONS.items():
            if not a.get("pool"):
                continue
            skill, attr = a["pool"]
            parts = _skill_parts(c, d, skill, attr=attr)
            if parts is None:
                continue
            if mx.get("penalty"):
                parts = parts + [["Matrix damage on the device", mx["penalty"]]]
            out.append(_pool(f"matrix:{key}", "Matrix", a["name"], parts, matrix=True, legal=a["legal"],
                             defense=a["defense"], uses=a.get("uses")))
    for p in vehicle_pools(c, d):
        out.append(p)
    return _apply_conditions(c, d, out)


HEAL_SPELLS = ("Heal", "Cleansing Heal", "Cooling Heal", "Warming Heal")


def medkits(c):
    return [it for it in c.get("inventory") or [] if it.get("medkit")]


def medkit_supplies(c):
    return sum(_int(it.get("qty"), 1) for it in c.get("inventory") or [] if it.get("ref") == "medical-medkit-supplies")


def heal_pools(c, d):
    """Healing tests for the dice roller (book p. 119-121). ``heal`` names the method the roll applies."""
    A = d["attributes"]
    base = _skill_parts(c, d, "Biotech", focus="First Aid") or [["Logic", A["Logic"]], ["Biotech (untrained)", -1]]
    kits = medkits(c)
    out = []
    if kits:
        out.append(_pool("first_aid", "Healing", "First aid", base, heal="first_aid"))
        sup = medkit_supplies(c)
        out.append(_pool("medkit", "Healing", f"Medkit · {sup} supplies", base + [["Wireless medkit", 1]],
                         heal="medkit", supplies=sup))
    else:
        out.append(_pool("first_aid", "Healing", "First aid (no medkit)", base + [["No medkit", -2]], heal="first_aid", noEdge=True))
    if c.get("magic_type") in CASTERS:
        for sp in c.get("spells") or []:
            if sp.get("name") in HEAL_SPELLS:
                prof = spell_profile(c, d, sp)
                if prof:
                    out.append(_pool("magic", "Healing", f"{sp['name']} spell", prof["parts"], heal="magic", drain=prof["drain"]))
                break
    out.append(_pool("natural_stun", "Healing", "Rest 1 hour (Stun)", natural_pool(c, "natural_stun"), heal="natural_stun"))
    out.append(_pool("natural_physical", "Healing", "Rest 1 day (Physical)", natural_pool(c, "natural_physical"), heal="natural_physical"))
    return out


def pool_by_key(c, key, d=None):
    for p in pools(c, d):
        if p["key"] == key:
            return p
    raise RuleError("That dice pool no longer exists on your sheet.")


# --------------------------------------------------------------------------- context, money, karma
class Ctx:
    def __init__(self, approved, gamemaster, sell_pct=50, out_of_stock=()):
        self.approved = approved      # sheet approved by the GM
        self.gamemaster = gamemaster            # GM is the one acting
        self.sell_pct = sell_pct      # % of the price the store pays for sold items
        self.out_of_stock = frozenset(out_of_stock)   # store item / PACK ids the GM marked out of stock
        self.ledger = []              # [(kind, delta, reason)]
        self.log = []                 # table-log notes
        self.rolls = []               # extra roll records [(kind, data)] for the table log

    @property
    def locked(self):
        return self.approved and not self.gamemaster


def spend(c, ctx, kind, amount, reason, allow_negative=False):
    """Charge karma/nuyen (players only; the GM never pays)."""
    if amount == 0 or ctx.gamemaster:
        return
    if amount > 0 and c[kind] < amount and not allow_negative:
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


def karma_cost(ctx, amount):
    """Advancement costs Karma only once the sheet is approved."""
    return amount if ctx.approved and not ctx.gamemaster else 0


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
    fn = ACTIONS.get(action)
    if not fn:
        raise RuleError("Unknown action.")
    if action in GAMEMASTER_ONLY and not ctx.gamemaster:
        raise RuleError("Only the GM can do that.")
    edge_before = derive(c)["edge_max"]
    msg = fn(c, p or {}, ctx)
    clamp_state(c, ctx, edge_before)
    return msg or "Saved."


def clamp_state(c, ctx=None, edge_before=None):
    d = derive(c)
    c["stun_damage"] = min(max(0, _int(c["stun_damage"])), d["stun_boxes"])
    c["physical_damage"] = min(max(0, _int(c["physical_damage"])), d["physical_boxes"] + d["overflow_boxes"])
    c["drain_stun"] = min(max(0, _int(c.get("drain_stun"))), c["stun_damage"])
    c["drain_phys"] = min(max(0, _int(c.get("drain_phys"))), c["physical_damage"])
    if ctx is not None and not ctx.approved and edge_before is not None and d["edge_max"] != edge_before:
        c["current_edge"] = d["edge_max"]           # during creation Edge follows the Edge attribute
    c["current_edge"] = max(0, min(EDGE_CAP, _int(c["current_edge"])))


# ---- info
def a_set_info(c, p, ctx):
    if "metatype" in p and p["metatype"] in K.METATYPES and p["metatype"] != c.get("metatype"):
        if ctx.locked:
            raise RuleError("Your sheet is approved; ask the GM to change metatype.")
        if not ctx.gamemaster:
            old_k, new_k = _int(meta_of(c).get("karma")), _int(K.METATYPES[p["metatype"]].get("karma"))
            if new_k > old_k:
                spend(c, ctx, "karma", new_k - old_k, f"Metatype: {p['metatype']}")
            elif old_k > new_k:
                gain(c, ctx, "karma", old_k - new_k, f"Metatype: {p['metatype']}")
    if p.get("magic_type") == "Technomancer" and c.get("infected"):
        raise RuleError("HMHVV is incompatible with Resonance: Infected can't be technomancers.")
    for k in FREE_INFO + LOCKED_INFO:
        if k not in p:
            continue
        v = p[k]
        if k in LOCKED_INFO and ctx.locked and v != c.get(k):
            raise RuleError(f"Your sheet is approved; ask the GM to change {k.replace('_', ' ')}.")
        if k in ("reputation", "heat") and not ctx.gamemaster and _int(v) != _int(c.get(k)):
            raise RuleError(f"Only the GM changes your {k.capitalize()}.")
        if k in ("reputation", "heat") and _int(v) != _int(c.get(k)):
            ctx.log.append(f"{k.capitalize()} {_int(c.get(k))} → {_int(v)}.")
        if k == "metatype" and v not in K.METATYPES:
            raise RuleError("Unknown metatype.")
        if k == "magic_type" and v not in MAGIC_TYPES:
            raise RuleError("Unknown magic type.")
        if k == "tradition" and v not in ("", *M.TRADITIONS):
            raise RuleError("Unknown tradition.")
        if k == "aspect" and v not in ("", *ASPECTS):
            raise RuleError("Unknown aspect.")
        if k == "mentor_spirit" and v not in ("", *M.MENTOR_SPIRITS):
            raise RuleError("Unknown mentor spirit.")
        if k == "role" and v not in ("", *ROLES):
            raise RuleError("Unknown role.")
        if k == "lifestyle" and v not in LIFESTYLES:
            raise RuleError("Unknown lifestyle.")
        if k in ("age", "reputation", "heat"):
            v = max(-99 if k == "reputation" else 0, min(999 if k == "age" else 99, _int(v)))
        elif k in ("background", "notes"):
            v = _clip(v, 20000)
        else:
            v = _clip(v, 80)
        c[k] = v
    if c["magic_type"] not in AWAKENED and not c.get("infected"):
        c["attributes"]["Magic"] = 0
    elif c["attributes"]["Magic"] < 1:
        c["attributes"]["Magic"] = 1
    if c["magic_type"] != "Technomancer":
        c["attributes"]["Resonance"] = 0
    elif c["attributes"]["Resonance"] < 1:
        c["attributes"]["Resonance"] = 1
    if c.get("infected") and not infected_info(c)["base_ok"]:
        raise RuleError(f"A {c['metatype']} can't be a {c['infected']}; remove the infection first.")
    return "Saved."


# ---- HMHVV Infected (Sixth World Companion)
def a_set_infected(c, p, ctx):
    """Become (or stop being) Infected. Costs the quality's Karma at creation; after approval only the GM can do it."""
    name = p.get("infected") or ""
    if name and name not in SWC.INFECTED:
        raise RuleError("Unknown Infected type.")
    if ctx.locked:
        raise RuleError("Only the GM can infect an approved character.")
    if name == c.get("infected"):
        return "No change."
    if name:
        if c.get("magic_type") == "Technomancer":
            raise RuleError("HMHVV is incompatible with Resonance: technomancers can't be Infected.")
        if any(q["name"] == "Magic Resistance" for q in qualities_of(c)):
            raise RuleError("Infected can't have Magic Resistance. Remove that quality first.")
        test = dict(c, infected=name)
        if not infected_info(test)["base_ok"]:
            bases = ", ".join(SWC.INFECTED[name]["bases"])
            raise RuleError(f"A {name} must be a {bases} (your metatype is {c['metatype']}).")
    if not ctx.gamemaster:
        old = infected_karma(c) + sum(SWC.INFECTED_OPTIONAL_POWERS.get(x, 0) for x in c.get("infected_powers") or [] if not x.endswith("(free)"))
        new = infected_karma(c, name)
        if old:
            gain(c, ctx, "karma", old, f"Removed: {c['infected']}")
        if new:
            spend(c, ctx, "karma", new, f"Infected: {name}")
    c["infected"] = name
    c["infected_powers"] = []
    c["infected_essence"] = 6 if name and SWC.INFECTED[name]["strain"] in ("I", "Ia") else None
    if name:
        awaken = SWC.INFECTED[name].get("awaken")
        if awaken == "Adept" and c["magic_type"] == "Mundane":
            c["magic_type"] = "Adept"
        elif awaken == "Adept" and c["magic_type"] == "Magician":
            c["magic_type"] = "Mystic Adept"
        elif awaken == "Magician" and c["magic_type"] == "Mundane":
            c["magic_type"] = "Magician"
        elif awaken == "Magician" and c["magic_type"] == "Adept":
            c["magic_type"] = "Mystic Adept"
        if c["attributes"].get("Magic", 0) < 1:
            c["attributes"]["Magic"] = 1
        d = derive(c)
        for a in K.BASE_ATTRS:                       # new, lower maximums cut base attributes (no refund)
            c["attributes"][a] = min(_int(c["attributes"].get(a), 1), d["max"][a])
        return f"You are now a {name}. Assign 2 free points to physical and 2 to mental attributes (your GM can set them)."
    if c["magic_type"] == "Mundane":
        c["attributes"]["Magic"] = 0
    return "Infection removed."


def a_infected_power(c, p, ctx):
    """Add or remove an Infected optional power (one may be free at creation, per the quality)."""
    inf = infected_info(c)
    if not inf:
        raise RuleError("Only Infected characters have Infected powers.")
    name = p.get("power") or ""
    lst = c.setdefault("infected_powers", [])
    if p.get("remove"):
        i = _list_index(lst, p.get("index"))
        if ctx.locked:
            raise RuleError("Ask the GM to remove an Infected power.")
        old = lst.pop(i)
        if not old.endswith("(free)") and not ctx.gamemaster:
            gain(c, ctx, "karma", SWC.INFECTED_OPTIONAL_POWERS.get(old, 0), f"Removed: {old}")
        return f"{old} removed."
    if name not in (inf.get("optional") or []):
        raise RuleError(f"A {inf['name']} can't take {name or 'that power'}.")
    if name in lst and not name.startswith("Armor"):
        raise RuleError("You already have that power.")
    free = bool(p.get("free")) and inf.get("free_optional") and not any(x.endswith("(free)") for x in lst) and not ctx.locked
    if free:
        lst.append(f"{name} (free)")
        return f"{name} taken as your free optional power."
    spend(c, ctx, "karma", SWC.INFECTED_OPTIONAL_POWERS.get(name, 8), f"Infected power: {name}")
    lst.append(name)
    return f"{name} added." + (" Optional powers can be bought one every two months of game time." if ctx.locked else "")


def a_set_infected_essence(c, p, ctx):
    """Strain I/Ia Essence goes up with Essence Drain and down with Essence Loss (the GM tracks it)."""
    inf = infected_info(c)
    if not inf or inf["strain"] not in ("I", "Ia"):
        raise RuleError("Only Strain I Infected track their Essence this way.")
    if not ctx.gamemaster:
        raise RuleError("Your GM tracks Essence Drain and Essence Loss.")
    cap = 18 if inf["strain"] == "Ia" else 12
    c["infected_essence"] = max(0.0, min(cap, round(_num(p.get("essence"), 6), 2)))
    return f"Essence base set to {c['infected_essence']}."


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


def a_trade_karma(c, p, ctx):
    n = _int(p.get("amount"))
    if n <= 0:
        raise RuleError("Enter how much Karma to trade.")
    if c["karma"] < n:
        raise RuleError(f"You only have {c['karma']} Karma.")
    rate = K.KARMA["nuyen_per_karma_in_debt"] if _has_q(qualities_of(c), "In Debt") else K.KARMA["nuyen_per_karma"]
    c["karma"] -= n
    ctx.ledger.append(("karma", -n, "Traded for nuyen"))
    gain(c, ctx, "nuyen", n * rate, f"Traded {n} Karma")
    return f"Traded {n} Karma for {fmt_money(n * rate)}."


# ---- attributes
def _attr_ok(c, attr):
    if attr not in ATTRS:
        raise RuleError("Unknown attribute.")
    if attr == "Magic" and c.get("magic_type") not in AWAKENED and not c.get("infected"):
        raise RuleError("Only Awakened characters have Magic.")
    if attr == "Resonance" and c.get("magic_type") != "Technomancer":
        raise RuleError("Only technomancers have Resonance.")


def a_set_attribute(c, p, ctx):
    _need_unlocked(ctx, "base attributes")
    attr = p.get("attr")
    _attr_ok(c, attr)
    lo = 1
    c["attributes"][attr] = max(lo, min(natural_max(c, attr), _int(p.get("value"), lo)))
    return "Saved."


def a_raise_attribute(c, p, ctx):
    attr = p.get("attr")
    _attr_ok(c, attr)
    cur = max(1, _int(c["attributes"].get(attr)))
    mx = natural_max(c, attr)
    if cur >= mx:
        raise RuleError(f"{attr} is already at its maximum ({mx}) for a {c['metatype']}.")
    cost = (cur + 1) * K.KARMA["attribute"]
    spend(c, ctx, "karma", karma_cost(ctx, cost), f"{attr} {cur} → {cur + 1}")
    c["attributes"][attr] = cur + 1
    return f"{attr} raised to {cur + 1}" + (f" for {cost} Karma." if karma_cost(ctx, cost) else ".")


def a_autoroll(c, p, ctx):
    _need_unlocked(ctx, "base attributes")
    r = secrets.SystemRandom()
    for attr in K.BASE_ATTRS:
        c["attributes"][attr] = r.randint(1, natural_max(c, attr))
    return "Attributes rolled within your metatype's limits."


# ---- skills
def skill_max(c, skill, ctx):
    aptitude = any(q["name"] == "Aptitude" and q.get("choice") == skill for q in qualities_of(c))
    if not ctx.approved:
        return K.SKILL_MAX_CREATION + (1 if aptitude else 0)
    return K.SKILL_MAX + (1 if aptitude else 0)


def a_set_skill(c, p, ctx):
    skill = p.get("skill")
    if skill not in K.SKILLS:
        raise RuleError("Unknown skill.")
    if any(q["name"] == "Incompetent" and q.get("choice") == skill for q in qualities_of(c)):
        raise RuleError(f"You are Incompetent in {skill}.")
    cur = c["skills"].get(skill, 0)
    rank = max(0, min(skill_max(c, skill, ctx) if not ctx.gamemaster else 12, _int(p.get("rank"), cur)))
    if ctx.locked:
        if rank < cur:
            raise RuleError("Approved sheets can't lower skills.")
        cost = sum(r * K.KARMA["skill"] for r in range(cur + 1, rank + 1))
        if cost:
            spend(c, ctx, "karma", cost, f"{skill} {cur} → {rank}")
    c["skills"][skill] = rank
    if rank == 0:
        c["specs"].pop(skill, None)
        c["expertise"].pop(skill, None)
    elif rank < K.EXPERTISE_MIN_RANK and skill in c["expertise"] and not ctx.approved:
        c["expertise"].pop(skill, None)
    return "Saved."


def _valid_focus(skill, name):
    name = _clip(name, 40).strip()
    if not name:
        return ""
    if name in K.SKILLS[skill]["specs"]:
        return name
    if skill == "Exotic Weapons":
        return name
    raise RuleError("Pick one of the listed specializations.")


def a_set_spec(c, p, ctx):
    """Choose (or clear) a skill's specialization."""
    skill = p.get("skill")
    if skill not in K.SKILLS:
        raise RuleError("Unknown skill.")
    spec = _valid_focus(skill, p.get("spec"))
    cur = c["specs"].get(skill, "")
    if spec == cur:
        return "Saved."
    if c["skills"].get(skill, 0) <= 0 and spec:
        raise RuleError("Learn the skill before choosing a specialization.")
    if spec and spec == c["expertise"].get(skill):
        raise RuleError("You already have expertise in that.")
    if ctx.locked:
        if cur and not spec:
            raise RuleError("Approved sheets can't drop a specialization.")
        if cur:
            raise RuleError("You already have a specialization here. Turn it into expertise first.")
        spend(c, ctx, "karma", K.KARMA["specialization"], f"{skill} specialization: {spec}")
    if spec:
        c["specs"][skill] = spec
    else:
        c["specs"].pop(skill, None)
    return f"Specialization: {spec}." if spec else "Specialization removed."


def a_set_expertise(c, p, ctx):
    """Turn the current specialization into expertise (+3), or clear it (draft/GM)."""
    skill = p.get("skill")
    if skill not in K.SKILLS:
        raise RuleError("Unknown skill.")
    if K.SKILLS[skill].get("exotic"):
        raise RuleError("Exotic Weapons can't have expertise; take several specializations instead.")
    if p.get("clear"):
        _need_unlocked(ctx, "expertise")
        c["expertise"].pop(skill, None)
        return "Expertise removed."
    spec = c["specs"].get(skill)
    if not spec:
        raise RuleError("Expertise grows out of a specialization: pick one first.")
    if c["expertise"].get(skill):
        raise RuleError("A skill can have only one expertise.")
    if c["skills"].get(skill, 0) < K.EXPERTISE_MIN_RANK:
        raise RuleError(f"Expertise needs {skill} at rank {K.EXPERTISE_MIN_RANK} or higher.")
    spend(c, ctx, "karma", karma_cost(ctx, K.KARMA["expertise"]), f"{skill} expertise: {spec}")
    c["expertise"][skill] = spec
    c["specs"].pop(skill, None)
    return f"{spec} is now expertise (+3). You may pick a new specialization."


def a_add_knowledge(c, p, ctx):
    name = _clip(p.get("name"), 60).strip()
    if not name:
        raise RuleError("Name the knowledge skill.")
    if name.lower() in (k.lower() for k in c["knowledge"]):
        raise RuleError("You already know that.")
    if len(c["knowledge"]) >= 60:
        raise RuleError("Too many knowledge skills.")
    spend(c, ctx, "karma", karma_cost(ctx, K.KARMA["knowledge"]), f"Knowledge skill: {name}")
    c["knowledge"].append(name)
    return f"Learned {name}."


def a_remove_knowledge(c, p, ctx):
    _need_unlocked(ctx, "knowledge skills")
    i = _list_index(c["knowledge"], p.get("index"))
    return f"{c['knowledge'].pop(i)} removed."


def a_set_language(c, p, ctx):
    """Add a language or raise its level (Basic → Specialist → Expert; Native only at creation)."""
    name = _clip(p.get("name"), 40).strip()
    level = p.get("level") if p.get("level") in K.LANGUAGE_LEVELS else "Basic"
    if not name:
        raise RuleError("Name the language.")
    cur = next((x for x in c["languages"] if x["name"].lower() == name.lower()), None)
    if level == "Native" and ctx.locked:
        raise RuleError("Native languages are chosen at character creation.")
    if level == "Native" and not ctx.gamemaster and sum(1 for x in c["languages"] if x["level"] == "Native" and x is not cur) >= 1:
        raise RuleError("Only one native language at creation (qualities can add more; ask the GM).")
    order = K.LANGUAGE_LEVELS
    if cur:
        if ctx.locked:
            if order.index(level) <= order.index(cur["level"]):
                raise RuleError("Approved sheets can only raise a language.")
            if cur["level"] == "Native":
                raise RuleError("It's already your native language.")
            steps = order.index(level) - order.index(cur["level"])
            per = 1 if _qeffect(qualities_of(c), "polyglot") else K.KARMA["language_level"]
            spend(c, ctx, "karma", steps * per, f"{name} → {level}")
        cur["level"] = level
        return f"{name}: {level}."
    if len(c["languages"]) >= 30:
        raise RuleError("Too many languages.")
    poly = _qeffect(qualities_of(c), "polyglot")
    cost = (2 if poly else K.KARMA["knowledge"]) + (order.index(level) * (1 if poly else K.KARMA["language_level"]) if level != "Native" else 0)
    spend(c, ctx, "karma", karma_cost(ctx, cost), f"Language: {name} ({level})")
    c["languages"].append({"name": name, "level": level})
    return f"Learned {name} ({level})."


def a_remove_language(c, p, ctx):
    _need_unlocked(ctx, "languages")
    i = _list_index(c["languages"], p.get("index"))
    return f"{c['languages'].pop(i)['name']} removed."


# ---- qualities
def quality_karma(name, level=1):
    q = K.QUALITIES[name]
    return q["karma"] * (max(1, _int(level, 1)) if q.get("levels") else 1)


def a_add_quality(c, p, ctx):
    name = p.get("quality")
    if name not in K.QUALITIES:
        raise RuleError("Unknown quality.")
    q = K.QUALITIES[name]
    if q.get("racial_only"):
        raise RuleError(f"{name} only comes with a metatype; it can't be taken as a quality.")
    level = max(1, min(q.get("levels", 1), _int(p.get("level"), 1)))
    choice = _clip(p.get("choice"), 60).strip()
    if q.get("choice") and not choice:
        raise RuleError(f"{name} needs a choice ({q['choice']}).")
    if any(x["name"] == name and x.get("choice", "") == choice for x in qualities_of(c)):
        raise RuleError("You already have that quality. Change its level instead.")
    karma = quality_karma(name, level)
    if ctx.locked:
        if karma < 0:
            # taken in play: no Karma for it, and the table (the GM) is told
            label = f"{name} {level}" if q.get("levels") else name
            ctx.log.append(f"took the negative quality {label}{f' ({choice})' if choice else ''}. No Karma is given for it after approval.")
        else:
            spend(c, ctx, "karma", karma * K.KARMA["quality_mult"], f"Quality: {name}")
    elif not ctx.gamemaster:
        if karma > 0:
            spend(c, ctx, "karma", karma, f"Quality: {name}")
        elif karma < 0:
            gain(c, ctx, "karma", -karma, f"Quality: {name}")
    c["qualities"].append({"name": name, "level": level, "choice": choice})
    return f"{name} added."


def a_remove_quality(c, p, ctx):
    i = _list_index(c["qualities"], p.get("index"))
    q = c["qualities"][i]
    karma = quality_karma(q["name"], q.get("level"))
    if ctx.locked:
        if karma > 0:
            raise RuleError("Positive qualities can't be dropped after approval.")
        spend(c, ctx, "karma", -karma * K.KARMA["quality_mult"], f"Bought off: {q['name']}")
    elif not ctx.gamemaster:
        if karma > 0:
            gain(c, ctx, "karma", karma, f"Refund: {q['name']}")
        elif karma < 0:
            spend(c, ctx, "karma", -karma, f"Removed: {q['name']}")
    c["qualities"].pop(i)
    return f"{q['name']} removed."


def a_set_quality_level(c, p, ctx):
    i = _list_index(c["qualities"], p.get("index"))
    q = c["qualities"][i]
    meta = K.QUALITIES[q["name"]]
    if not meta.get("levels"):
        raise RuleError("That quality has no levels.")
    new = max(1, min(meta["levels"], _int(p.get("level"), 1)))
    old = max(1, _int(q.get("level"), 1))
    if new == old:
        return "Saved."
    delta = quality_karma(q["name"], new) - quality_karma(q["name"], old)
    if ctx.locked:
        if meta["karma"] > 0 and new < old:
            raise RuleError("Approved sheets can't lower a positive quality.")
        if meta["karma"] < 0 and new > old:
            raise RuleError("Approved sheets can't worsen a negative quality.")
        spend(c, ctx, "karma", abs(delta) * K.KARMA["quality_mult"], f"{q['name']} level {old} → {new}")
    elif not ctx.gamemaster:
        if delta > 0:
            spend(c, ctx, "karma", delta, f"{q['name']} level {old} → {new}")
        else:
            gain(c, ctx, "karma", -delta, f"{q['name']} level {old} → {new}")
    q["level"] = new
    return "Saved."


# ---- inventory and store
def _merge_stack(c, it):
    """Ammo and consumables bought again stack onto the same entry."""
    if not (it.get("unit") or it.get("consumable")) or not it.get("ref"):
        return None
    for x in c["inventory"]:
        if x.get("ref") == it["ref"] and x.get("rating") == it.get("rating") and x is not it:
            x["qty"] = _int(x.get("qty"), 0) + _int(it.get("qty"), 1)
            return x
    return None


OUT_OF_STOCK = "out of stock right now. The GM will say when it's back."


def _store_access(c, ctx, it):
    ok, why = CAT.access(c, it.get("avail"), it.get("legal", ""), G.CATEGORY_SUPPLY.get(it.get("cat"), "General"), ctx.approved)
    return ok, why


def a_buy(c, p, ctx):
    try:
        e = CAT.entry(p.get("ref"))
    except CAT.CatalogError as ex:
        raise RuleError(str(ex))
    qty = max(1, min(100, _int(p.get("qty"), 1)))
    grade = p.get("grade") if p.get("grade") in G.IMPLANT_GRADES else "Standard"
    if grade == "Used" and not CAT.is_implant(e):
        grade = "Standard"
    it = CAT.make_item(e, p.get("rating"), grade, price_markup(c), uid=_uid(c))
    if not ctx.gamemaster:
        if e["id"] in ctx.out_of_stock:
            raise RuleError(f"{e['name']}: {OUT_OF_STOCK}")
        ok, why = _store_access(c, ctx, it)
        if not ok:
            raise RuleError(why)
    if len(c["inventory"]) >= MAX_LIST:
        raise RuleError("Inventory is full.")
    if CAT.is_implant(e) and qty > 1:
        qty = 1
    price = it["cost"] * qty
    free = ctx.gamemaster and p.get("free", True)
    if not free:
        spend(c, ctx, "nuyen", price, f"Bought {it['name']}" + (f" ×{qty}" if qty > 1 else ""))
    if it.get("unit"):
        it["qty"] = CAT.box_size(e) * qty
    else:
        it["qty"] = qty
    if CAT.is_implant(e):
        d = derive(c)
        if d["essence"] - it.get("essence", 0) < 0 and not ctx.gamemaster:
            raise RuleError(f"Not enough Essence: {it['name']} costs {it['essence']} and you have {d['essence']}.")
    if not _merge_stack(c, it):
        if qty > 1 and not (it.get("unit") or it.get("consumable")):
            for _ in range(qty - 1):
                extra = copy.deepcopy(it)
                extra["uid"] = _uid(c)
                extra["qty"] = 1
                c["inventory"].append(extra)
            it["qty"] = 1
        c["inventory"].append(it)
    if CAT.is_implant(e) and ctx.approved and not ctx.gamemaster:
        boxes = max(1, int(round(it.get("essence", 0) * 3)))
        ctx.log.append(f"had {it['name']} implanted (surgery: {boxes} boxes on each monitor).")
        _surgery(c, boxes)
    if free:
        return f"{it['name']} added to the inventory."
    return f"Bought {it['name']} for {fmt_money(price)}."


def a_buy_pack(c, p, ctx):
    """Buy a Sixth World Companion PACK: every item at once, for the PACK's price (grade price for augmentation PACKs)."""
    from . import packs as PK
    hit = PK.PACK_BY_ID.get(p.get("ref") or "")
    if not hit:
        raise RuleError("Unknown PACK.")
    entry, pack = hit
    if not ctx.gamemaster and entry["id"] in ctx.out_of_stock:
        raise RuleError(f"{pack['name']}: {OUT_OF_STOCK}")
    grade = p.get("grade") if p.get("grade") in G.IMPLANT_GRADES else "Standard"
    price = pack["cost"]
    if grade != "Standard":
        if not pack.get("grades") or grade not in pack["grades"]:
            raise RuleError(f"{pack['name']} doesn't come in {grade} grade.")
        price = pack["grades"][grade][0]
    markup = price_markup(c)
    res = PK.resolve_pack(pack)
    made = []
    for x in res["items"]:
        if x.get("ref"):
            e = CAT.BY_ID[x["ref"]]
            g = x.get("grade") or (grade if CAT.is_implant(e) else "Standard")
            it = CAT.make_item(e, x.get("rating"), g, markup, uid="")
            if not ctx.gamemaster:
                if x["ref"] in ctx.out_of_stock:
                    raise RuleError(f"{it['name']}: {OUT_OF_STOCK}")
                ok, why = _store_access(c, ctx, it)
                if not ok:
                    raise RuleError(f"{it['name']}: {why}")
            if x.get("rounds") and it.get("unit"):
                it["qty"] = max(1, _int(x.get("qty"), 1))
            else:
                it["qty"] = max(1, _int(x.get("qty"), 1))
        else:
            it = {"name": x["name"], "cat": "Survival", "sub": "From a PACK", "cost": 0, "qty": max(1, _int(x.get("qty"), 1)),
                  "desc": "", "_custom": True}
        if x.get("note"):
            it["notes"] = x["note"]
        it["pack"] = pack["name"]
        made.append(it)
    # spread the PACK price over its items so selling them back is fair
    def value(it):
        return _int(it.get("cost")) * (_int(it.get("qty"), 1) / 10.0 if it.get("unit") == "rounds" else _int(it.get("qty"), 1))
    total = sum(value(it) for it in made) or 1
    factor = price * (1 + markup[0]) / total
    for it in made:
        it["cost"] = int(round(_int(it.get("cost")) * factor))
    price = int(round(price * (1 + markup[0])))
    if len(c["inventory"]) + len(made) > MAX_LIST:
        raise RuleError("Inventory is full.")
    ess = round(sum(_num(it.get("essence")) for it in made if it.get("implant")), 2)
    if ess and derive(c)["essence"] - ess < 0 and not ctx.gamemaster:
        raise RuleError(f"Not enough Essence: this PACK costs {ess} Essence.")
    free = ctx.gamemaster and p.get("free", True)
    if not free:
        spend(c, ctx, "nuyen", price, f"Bought {pack['name']}" + (f" ({grade})" if grade != "Standard" else ""))
    for it in made:
        it["uid"] = _uid(c)
        if not _merge_stack(c, it):
            c["inventory"].append(it)
    if pack.get("cash"):
        gain(c, ctx, "nuyen", pack["cash"], f"{pack['name']}: cash")
    if ess and ctx.approved and not ctx.gamemaster:
        boxes = max(1, int(round(ess * 3)))
        ctx.log.append(f"had the {pack['name']} implanted (surgery: {boxes} boxes on each monitor).")
        _surgery(c, boxes)
    return f"{pack['name']}: {len(made)} items added" + (f" for {fmt_money(price)}." if not free else ".")


def _surgery(c, boxes):
    """Implant surgery fills boxes on both monitors (no overflow)."""
    d = derive(c)
    c["stun_damage"] = min(d["stun_boxes"] - 1, _int(c["stun_damage"]) + boxes) if d["stun_boxes"] > 1 else c["stun_damage"]
    c["physical_damage"] = min(d["physical_boxes"] - 1, _int(c["physical_damage"]) + boxes) if d["physical_boxes"] > 1 else c["physical_damage"]


CUSTOM_TEXT = ("sub", "desc", "dv", "ar", "modes", "ammo", "ammo_class", "skill", "spec", "focus", "dv_gz", "dv_close",
               "dv_near", "blast", "choice")
CUSTOM_NUM = ("dr", "capacity", "device_rating", "data_processing", "firewall", "attack", "sleaze", "program_slots",
              "handling", "accel", "speed_interval", "top_speed", "body", "armor", "pilot", "sensor",
              "init_dice", "soak", "Body", "Agility", "Reaction", "Strength", "Willpower", "Logic", "Intuition", "Charisma")


def clean_custom(raw):
    """Shape a custom item from the browser (GM gifts, draft homebrew)."""
    if not isinstance(raw, dict):
        raise RuleError("Bad item.")
    name = _clip(raw.get("name"), 80).strip()
    if not name:
        raise RuleError("A name is required.")
    cat = raw.get("cat") if raw.get("cat") in G.STORE_CATEGORIES else "Survival"
    it = {"uid": "", "ref": None, "name": name, "cat": cat, "qty": max(1, min(9999, _int(raw.get("qty"), 1))),
          "cost": max(0, _int(raw.get("cost"))), "_custom": True}
    a, legal = CAT.parse_avail(raw.get("avail", "")) if str(raw.get("avail", "")).strip() else (0, "")
    it["avail"], it["legal"] = a, legal
    for k in CUSTOM_TEXT:
        if raw.get(k) not in (None, ""):
            it[k] = _clip(raw[k], 300 if k == "desc" else 60).strip()
    for k in CUSTOM_NUM:
        if raw.get(k) not in (None, ""):
            it[k] = _int(raw[k])
    if raw.get("essence") not in (None, "", 0, "0"):
        it["essence"] = round(max(0.0, min(6.0, _num(raw["essence"]))), 2)
        it["implant"] = True
    if raw.get("consumable"):
        it["consumable"] = True
    if cat in ("Melee", "Ranged", "Armor"):
        it["equipped"] = True
    if it.get("ammo"):
        cap, kind = CAT.parse_ammo(it["ammo"])
        if cap:
            it["clip"], it["clip_kind"] = cap, kind
            it["loaded"] = {"rounds": 0, "type": "Regular"}
    if cat in ("Vehicles", "Drones"):
        it["damage"] = 0
    if it.get("focus"):
        it["bonded"] = False
        it["force"] = max(1, _int(raw.get("force"), 1))
    return it


def a_buy_custom(c, p, ctx):
    if ctx.approved and not ctx.gamemaster:
        raise RuleError("Custom items are only available during character creation. Ask the GM.")
    it = clean_custom(p.get("item"))
    it["uid"] = _uid(c)
    if not ctx.gamemaster or not p.get("free", True):
        spend(c, ctx, "nuyen", it["cost"] * (1 if it.get("unit") else it["qty"]), f"Bought {it['name']}")
    c["inventory"].append(it)
    return f"{it['name']} added."


def a_give(c, p, ctx):
    """GM only: give a store item (with rating/grade/qty) or a custom item, free."""
    if p.get("ref"):
        q = dict(p)
        q["free"] = True
        return a_buy(c, q, ctx)
    q = {"item": p.get("item"), "free": True}
    return a_buy_custom(c, q, ctx)


def a_edit_item(c, p, ctx):
    it = find_item(c, p.get("uid"))
    raw = p.get("item") or {}
    name = _clip(raw.get("name"), 80).strip() or it["name"]
    desc = _clip(raw.get("desc"), 1000)
    if ctx.gamemaster or (not ctx.approved and it.get("_custom")):
        new = clean_custom({**it, **raw, "name": name})
        for k in ("uid", "ref", "loaded", "bonded", "running", "damage", "matrix_damage", "grade", "rating", "unit", "choice"):
            if k in it and k not in new:
                new[k] = it[k]
        if not ctx.gamemaster and new["cost"] != it.get("cost"):
            delta = new["cost"] * new["qty"] - _int(it.get("cost")) * _int(it.get("qty"), 1)
            if delta > 0:
                spend(c, ctx, "nuyen", delta, f"Price change: {name}")
            elif delta < 0:
                gain(c, ctx, "nuyen", -delta, f"Price change: {name}")
        if not ctx.gamemaster:
            new["_custom"] = True
        it.clear()
        it.update(new)
    else:
        it["name"] = name
        it["desc"] = desc
    if "choice" in raw:
        it["choice"] = _clip(raw.get("choice"), 60).strip()
    return "Item updated."


def a_toggle_equipped(c, p, ctx):
    it = find_item(c, p.get("uid"))
    if it.get("cat") not in ("Melee", "Ranged", "Armor"):
        raise RuleError("Only weapons and armor can be equipped.")
    it["equipped"] = not it.get("equipped", True)
    return f"{it['name']} {'equipped' if it['equipped'] else 'stored'}."


def _refund_value(it):
    unit = _int(it.get("cost"))
    if it.get("unit") == "rounds":
        return int(unit * _int(it.get("qty")) / 10)
    return unit * max(1, _int(it.get("qty"), 1))


def a_remove_item(c, p, ctx):
    it = find_item(c, p.get("uid"))
    c["inventory"].remove(it)
    if not ctx.approved and not ctx.gamemaster:
        val = _refund_value(it)
        if val:
            gain(c, ctx, "nuyen", val, f"Refund: {it['name']}")
            return f"{it['name']} returned for {fmt_money(val)}."
    return f"{it['name']} discarded."


def a_sell_item(c, p, ctx):
    """Sell an item to the store for the game's sell percentage (needs a contact who could handle it)."""
    it = find_item(c, p.get("uid"))
    if not ctx.approved:
        return a_remove_item(c, p, ctx)
    ok, why = _store_access(c, ctx, it)
    if not ok and not ctx.gamemaster:
        raise RuleError("No contact will fence that. " + why)
    qty = _int(p.get("qty"), 0)
    if it.get("unit") or it.get("consumable"):
        qty = max(1, min(_int(it.get("qty"), 1), qty or _int(it.get("qty"), 1)))
    else:
        qty = max(1, _int(it.get("qty"), 1))
    part = dict(it)
    part["qty"] = qty
    price = CAT.sell_price(part, ctx.sell_pct)
    if it.get("implant") and not ctx.gamemaster:
        ctx.log.append(f"had {it['name']} removed and sold it.")
    if it.get("bonded"):
        it["bonded"] = False
    if (it.get("unit") or it.get("consumable")) and qty < _int(it.get("qty"), 1):
        it["qty"] = _int(it["qty"]) - qty
    else:
        c["inventory"].remove(it)
    gain(c, ctx, "nuyen", price, f"Sold {it['name']}" + (f" ×{qty}" if qty > 1 else "") + f" ({ctx.sell_pct}%)")
    return f"Sold {it['name']} for {fmt_money(price)}."


def a_reload(c, p, ctx):
    """Fill a weapon from a compatible ammo stack (unloading other ammo types first)."""
    w = find_item(c, p.get("uid"))
    if not w.get("clip"):
        raise RuleError("That weapon doesn't take ammunition.")
    cls = w.get("ammo_class")
    stacks = [x for x in c["inventory"] if x.get("ammo_for") and x.get("ammo_for") == cls and _int(x.get("qty")) > 0]
    if p.get("ammo"):
        stacks = [x for x in stacks if x.get("uid") == p.get("ammo")]
    if w.get("fixed_ammo"):
        stacks = [x for x in stacks if x.get("ammo_type") in (w["fixed_ammo"], None)] or stacks
    if not stacks:
        raise RuleError(f"You have no ammunition for the {w['name']}" + (f" ({cls})." if cls else "."))
    src = stacks[0]
    loaded = w.setdefault("loaded", {"rounds": 0, "type": "Regular"})
    atype = src.get("ammo_type") or ("Regular" if not src.get("dv_gz") else src["name"])
    if loaded.get("rounds") and loaded.get("type") != atype:
        _unload(c, w)
    room = w["clip"] - _int(loaded.get("rounds"))
    if room <= 0:
        raise RuleError("It's already full.")
    n = min(room, _int(src.get("qty")))
    src["qty"] = _int(src["qty"]) - n
    loaded["rounds"] = _int(loaded.get("rounds")) + n
    loaded["type"] = atype
    loaded["src"] = src.get("ref")
    if src["qty"] <= 0:
        c["inventory"].remove(src)
    return f"Loaded {n} {atype if not src.get('dv_gz') else ''} {'round' if n == 1 else 'rounds'} into the {w['name']}.".replace("  ", " ")


def _unload(c, w):
    loaded = w.get("loaded") or {}
    n = _int(loaded.get("rounds"))
    if n <= 0:
        return 0
    ref = loaded.get("src")
    back = next((x for x in c["inventory"] if ref and x.get("ref") == ref), None)
    if back:
        back["qty"] = _int(back.get("qty")) + n
    elif ref and ref in CAT.BY_ID:
        it = CAT.make_item(CAT.BY_ID[ref], uid=_uid(c))
        it["qty"] = n
        c["inventory"].append(it)
    loaded["rounds"] = 0
    return n


def a_unload(c, p, ctx):
    w = find_item(c, p.get("uid"))
    n = _unload(c, w)
    return f"Unloaded {n} rounds." if n else "It was empty."


def consume_attack(c, uid, mode):
    """Spend the rounds (or the throwable) an attack uses. Returns a short note for the log."""
    if uid in (None, "", "unarmed"):
        return ""
    it = find_item(c, uid)
    if it.get("clip"):
        modes = CAT.modes_list(it.get("modes"))
        mode = mode if mode in modes else (modes[0] if modes else None)
        need = G.FIRING_MODES[mode]["rounds"] if mode else 1
        have = _int((it.get("loaded") or {}).get("rounds"))
        if have <= 0:
            raise RuleError(f"The {it['name']} is empty. Reload it first.")
        if have < need and not (mode == "BF" and have >= 2):
            raise RuleError(f"{G.FIRING_MODES[mode]['name']} needs {need} rounds; only {have} loaded.")
        used = min(need, have)
        it["loaded"]["rounds"] = have - used
        return f"{used} {'round' if used == 1 else 'rounds'} fired, {have - used} left"
    if it.get("consumable") or it.get("dv_gz"):
        q = _int(it.get("qty"), 1) - 1
        if q <= 0:
            c["inventory"].remove(it)
            return f"{it['name']} used up"
        it["qty"] = q
        return f"{q} {it['name']} left"
    return ""


def a_bond_focus(c, p, ctx):
    it = find_item(c, p.get("uid"))
    if not it.get("focus"):
        raise RuleError("That isn't a focus.")
    if c.get("magic_type") not in AWAKENED:
        raise RuleError("Only Awakened characters can bond foci.")
    cost = _int(it.get("force"), 1) * G.FOCUS_BOND_KARMA.get(it["focus"], 2)
    if it.get("bonded"):
        if ctx.locked:
            raise RuleError("Unbonding after approval is a GM call.")
        it["bonded"] = False
        if not ctx.gamemaster:
            gain(c, ctx, "karma", cost, f"Unbonded {it['name']}")
        return f"{it['name']} unbonded."
    limit = derive(c)["attributes"]["Magic"]
    if sum(1 for x in c["inventory"] if x.get("bonded")) >= limit and not ctx.gamemaster:
        raise RuleError(f"You can bond at most {limit} foci (your Magic).")
    spend(c, ctx, "karma", cost, f"Bonded {it['name']}")
    it["bonded"] = True
    return f"{it['name']} bonded" + ("." if ctx.gamemaster else f" for {cost} Karma.")


def a_set_vehicle_damage(c, p, ctx):
    it = find_item(c, p.get("uid"))
    if it.get("cat") not in ("Vehicles", "Drones"):
        raise RuleError("Not a vehicle.")
    it["damage"] = max(0, min(8 + _half_up(_int(it.get("body"))), _int(p.get("value"))))
    return "Vehicle condition updated."


def a_set_program(c, p, ctx):
    it = find_item(c, p.get("uid"))
    if it.get("sub") != "Software":
        raise RuleError("Not a program.")
    if "choice" in p:
        ch = p.get("choice") or ""
        if it.get("ref") == "cyberdecks-software-autosoft":
            allowed = list(RIG.AUTOSOFTS)
        else:
            allowed = list(M.PROGRAMS["Basic"]) + (list(M.PROGRAMS["Hacking"]) if "hacking" in (it.get("ref") or "") else [])
        if ch and ch not in allowed:
            raise RuleError("Pick a program from the list.")
        it["choice"] = ch
    if "running" in p:
        want = bool(p.get("running"))
        if want:
            d = derive(c)
            running = sum(1 for x in c["inventory"] if x.get("running") and x is not it)
            if running >= d["matrix"]["slots"]:
                raise RuleError(f"Your device runs {d['matrix']['slots']} programs at once.")
        it["running"] = want
    return "Saved."


def a_set_matrix(c, p, ctx):
    m = c.setdefault("matrix", {"mode": "AR", "device": ""})
    if p.get("mode") in M.MATRIX_INIT:
        m["mode"] = p["mode"]
    if "device" in p:
        dev = str(p.get("device") or "")
        if dev and dev != "persona":
            find_item(c, dev)
        m["device"] = dev
    if "damage" in p:
        d = derive(c)["matrix"]
        v = max(0, min(d.get("boxes", 0), _int(p.get("damage"))))
        if d.get("device") == "persona":
            c["stun_damage"] = v
        elif d.get("device"):
            find_item(c, d["device"])["matrix_damage"] = v
    return "Saved."


# ---- contacts
def a_save_contact(c, p, ctx):
    raw = p.get("contact") or {}
    name = _clip(raw.get("name"), 80).strip()
    if not name:
        raise RuleError("A contact needs a name.")
    supply = [s for s in (raw.get("supply") or []) if s in SUPPLY][:20]
    cap = min([_int((K.QUALITIES[q["name"]].get("effects") or {}).get("loyalty_cap"), 12) for q in qualities_of(c)
               if (K.QUALITIES[q["name"]].get("effects") or {}).get("loyalty_cap")] or [12])
    if _int(raw.get("loyalty"), 1) > cap and not ctx.gamemaster:
        raise RuleError(f"Your qualities cap contacts' Loyalty at {cap}.")
    contact = {"name": name, "type": _clip(raw.get("type"), 40),
               "connection": max(1, min(12, _int(raw.get("connection"), 1))),
               "loyalty": max(1, min(12, _int(raw.get("loyalty"), 1))),
               "supply": supply, "notes": _clip(raw.get("notes"), 4000), "verified": True}
    if p.get("index") is None:
        if len(c["contacts"]) >= MAX_LIST:
            raise RuleError("Too many contacts.")
        if ctx.locked:
            contact["verified"] = False
        c["contacts"].append(contact)
        return f"{name} added." + (" The GM must confirm the new contact before it can source gear." if ctx.locked else "")
    i = _list_index(c["contacts"], p["index"])
    old = c["contacts"][i]
    if ctx.locked:
        changed = any(old.get(k) != contact[k] for k in ("type", "connection", "loyalty", "supply"))
        contact["verified"] = old.get("verified", True) and not changed
    elif ctx.gamemaster and "verified" in raw:
        contact["verified"] = bool(raw["verified"])
    c["contacts"][i] = contact
    return "Contact updated." + (" Waiting for the GM to confirm the changes." if not contact["verified"] and not ctx.gamemaster else "")


def a_verify_contact(c, p, ctx):
    i = _list_index(c["contacts"], p.get("index"))
    c["contacts"][i]["verified"] = bool(p.get("verified", True))
    return "Contact confirmed." if c["contacts"][i]["verified"] else "Contact marked as unconfirmed."


def a_remove_contact(c, p, ctx):
    i = _list_index(c["contacts"], p.get("index"))
    return f"{c['contacts'].pop(i)['name']} removed."


# ---- magic: spells, rituals, powers, initiation
def _caster(c):
    if c.get("magic_type") not in CASTERS:
        raise RuleError("Only magicians and mystic adepts cast spells.")
    if c.get("magic_type") == "Aspected Magician" and c.get("aspect") != "Sorcery":
        raise RuleError("Your aspect isn't Sorcery.")


def a_learn_spell(c, p, ctx):
    _caster(c)
    name = p.get("name")
    if name in SPELLS:
        sp = _spell_entry(SPELLS[name])
    elif name in RITUALS:
        r = RITUALS[name]
        sp = {"name": name, "category": "Ritual", "keywords": r["keywords"], "threshold": r["threshold"], "desc": r["desc"]}
    elif p.get("custom") and (ctx.gamemaster or not ctx.approved):
        raw = p.get("custom") or {}
        nm = _clip(raw.get("name"), 80).strip()
        if not nm:
            raise RuleError("Name the spell.")
        sp = {"name": nm, "category": raw.get("category") if raw.get("category") in ("Combat", "Detection", "Health", "Illusion", "Manipulation") else "Manipulation",
              "kind": raw.get("kind") if raw.get("kind") in ("Direct", "Indirect") else "", "drain": max(0, min(12, _int(raw.get("drain"), 3))),
              "damage": raw.get("damage") if raw.get("damage") in ("P", "S") else "", "type": "M" if raw.get("type") == "M" else "P",
              "range": _clip(raw.get("range"), 20), "duration": _clip(raw.get("duration"), 4), "desc": _clip(raw.get("desc"), 300), "_custom": True}
    else:
        raise RuleError("Unknown spell.")
    if any(s["name"] == sp["name"] for s in c["spells"]):
        raise RuleError("You already know that.")
    if len(c["spells"]) >= MAX_LIST:
        raise RuleError("Too many spells.")
    spend(c, ctx, "karma", karma_cost(ctx, K.KARMA["spell"]), f"Learned {sp['name']}")
    c["spells"].append(sp)
    return f"Learned {sp['name']}" + (f" for {K.KARMA['spell']} Karma." if karma_cost(ctx, 5) else ".")


def a_forget_spell(c, p, ctx):
    _need_unlocked(ctx, "spells")
    i = _list_index(c["spells"], p.get("index"))
    return f"{c['spells'].pop(i)['name']} forgotten."


def a_set_power(c, p, ctx):
    """Add an adept power or change its level (index given)."""
    if c.get("magic_type") not in ("Adept", "Mystic Adept"):
        raise RuleError("Only adepts and mystic adepts have adept powers.")
    if p.get("index") is not None:
        i = _list_index(c["powers"], p["index"])
        pw = c["powers"][i]
        meta = POWERS.get(pw["name"]) or {}
        new = max(1, min(meta.get("max", 99), _int(p.get("level"), 1)))
        if ctx.locked and new < _int(pw.get("level"), 1):
            raise RuleError("Approved sheets can't lower a power.")
        pw["level"] = new if meta.get("levels") else 1
        if "choice" in p and not ctx.locked:
            pw["choice"] = _clip(p.get("choice"), 40)
    else:
        name = p.get("name")
        meta = POWERS.get(name)
        if not meta:
            raise RuleError("Unknown power.")
        choice = _clip(p.get("choice"), 40).strip()
        if meta.get("choice") and not choice:
            raise RuleError(f"{name} needs a choice ({meta['choice']}).")
        if meta.get("choice") == "Physical attribute" and choice not in K.PHYSICAL:
            raise RuleError("Pick a Physical attribute.")
        if meta.get("choice") == "Skill" and choice not in K.SKILLS:
            raise RuleError("Pick a skill.")
        if any(x["name"] == name and x.get("choice", "") == choice for x in c["powers"]):
            raise RuleError("You already have that power.")
        lvl = max(1, min(meta.get("max", 99), _int(p.get("level"), 1))) if meta.get("levels") else 1
        c["powers"].append({"name": name, "level": lvl, "choice": choice})
    d = derive(c)
    if d["power_points_used"] > d["power_points_available"] + 1e-9 and not ctx.gamemaster and ctx.approved:
        raise RuleError(f"That needs {d['power_points_used']:g} Power Points; you have {d['power_points_available']:g}.")
    return "Saved."


def a_remove_power(c, p, ctx):
    _need_unlocked(ctx, "adept powers")
    i = _list_index(c["powers"], p.get("index"))
    return f"{c['powers'].pop(i)['name']} removed."


def a_buy_power_point(c, p, ctx):
    if c.get("magic_type") != "Mystic Adept":
        raise RuleError("Only mystic adepts buy power points.")
    d = derive(c)
    if _int(c.get("power_points_bought")) >= d["attributes"]["Magic"]:
        raise RuleError("Mystic adepts can have at most Magic power points.")
    spend(c, ctx, "karma", karma_cost(ctx, M.MYSTIC_PP_KARMA), "Power point")
    c["power_points_bought"] = _int(c.get("power_points_bought")) + 1
    return "Power point added."


def a_initiate(c, p, ctx):
    """Initiation (Awakened) or submersion (technomancers): 10 + new grade Karma, plus a metamagic/echo."""
    tm = c.get("magic_type") == "Technomancer"
    if not tm and c.get("magic_type") not in AWAKENED:
        raise RuleError("Only Awakened characters and technomancers can initiate.")
    key = "submersion_grade" if tm else "initiation_grade"
    table = ECHOES if tm else METAMAGICS
    lst = c["echoes"] if tm else c["metamagics"]
    pick = p.get("pick")
    if pick not in table:
        raise RuleError("Pick a metamagic." if not tm else "Pick an echo.")
    meta = table[pick]
    if meta.get("adept_only") and c.get("magic_type") not in ("Adept", "Mystic Adept"):
        raise RuleError(f"{pick} is for adepts.")
    if pick in lst and not meta.get("repeatable"):
        raise RuleError("You already have that.")
    grade = _int(c.get(key)) + 1
    cost = K.KARMA["submersion_base" if tm else "initiation_base"] + grade
    spend(c, ctx, "karma", karma_cost(ctx, cost), f"{'Submersion' if tm else 'Initiation'} grade {grade}: {pick}")
    c[key] = grade
    lst.append(pick)
    return f"{'Submerged' if tm else 'Initiated'} to grade {grade} ({pick})."


# ---- resonance
def a_learn_form(c, p, ctx):
    if c.get("magic_type") != "Technomancer":
        raise RuleError("Only technomancers thread complex forms.")
    name = p.get("name")
    if name not in FORMS:
        raise RuleError("Unknown complex form.")
    if any(f["name"] == name for f in c["complex_forms"]):
        raise RuleError("You already know that.")
    spend(c, ctx, "karma", karma_cost(ctx, K.KARMA["complex_form"]), f"Complex form: {name}")
    c["complex_forms"].append({"name": name, "choice": _clip(p.get("choice"), 40)})
    return f"Learned {name}."


def a_forget_form(c, p, ctx):
    _need_unlocked(ctx, "complex forms")
    i = _list_index(c["complex_forms"], p.get("index"))
    return f"{c['complex_forms'].pop(i)['name']} forgotten."


# ---- spirits and sprites
def spirit_stats(kind, force):
    """Stat block of a spirit of the given Force."""
    s = M.SPIRITS[kind]
    F = max(1, min(12, _int(force, 1)))
    attrs = {a: max(1, F + off) for a, off in s["attrs"].items() if a not in ("Magic", "Essence")}
    attrs["Magic"] = F
    attrs["Essence"] = F
    env = {"F": F}

    def ev(expr):
        try:
            return int(eval(str(expr).replace("ceil", "_ceil"), {"__builtins__": {}, "_ceil": math.ceil}, env))  # noqa: S307 (data from our own table)
        except Exception:
            return 0

    def ev_ar(expr):
        vals = [ev(x) if x != "—" else 0 for x in str(expr).split("/")]
        return "/".join(str(v) if v > 0 else "—" for v in vals)

    return {"type": kind, "force": F, "attrs": attrs, "init": ev(s["init"]) + 0, "init_dice": s.get("init_dice", 2),
            "dr": ev(s["dr"]), "cm": 8 + _half_up(F), "move": s.get("move"), "skills": {k: F for k in s["skills"]},
            "powers": s["powers"], "optional": s.get("optional", []), "optional_count": F // 3,
            "attacks": [{"name": a["name"], "dv": f"{ev(a['dv'])}{a['type']}", "ar": ev_ar(a["ar"]), "note": a.get("note", "")}
                        for a in s.get("attacks", [])]}


def a_summon(c, p, ctx):
    """Summon a spirit: Conjuring + Magic vs Force x 2; services = net hits; drain = the spirit's hits."""
    if c.get("magic_type") not in ("Magician", "Mystic Adept") and not (c.get("magic_type") == "Aspected Magician" and c.get("aspect") == "Conjuring"):
        raise RuleError("You can't summon spirits.")
    kind = p.get("type")
    if kind not in M.SPIRITS:
        raise RuleError("Unknown spirit type.")
    d = derive(c)
    force = max(1, min(d["attributes"]["Magic"] * 2, _int(p.get("force"), 1)))
    active = sum(_int(s.get("force")) for s in c["spirits"])
    if active + force > d["spirit_force_limit"] and not ctx.gamemaster:
        raise RuleError(f"Your spirits' total Force would exceed {d['spirit_force_limit']} (Magic x 3).")
    pool = pool_by_key(c, "summon", d)
    parts = pool["parts"] + ([["Wound modifier", d["wound_modifier"]]] if d["wound_modifier"] else [])
    me = DICE.new_roll(max(1, sum(x[1] for x in parts)))
    spirit = DICE.new_roll(force * 2)
    net = me["hits"] - spirit["hits"]
    drain_dv = spirit["hits"]
    drain = resist_drain(c, d, drain_dv, "drain")
    text = (f"summoned a Force {force} {kind} spirit: {me['hits']} vs {spirit['hits']} hits. "
            + (f"{net} service{'s' if net != 1 else ''}." if net > 0 else "It refused to come.")
            + f" Drain {drain_dv}: {drain['text']}.")
    ctx.log.append(text)
    me["label"] = f"Summon {kind} (Force {force})"
    me["parts"] = parts
    ctx.rolls.append(("sr", me))
    if net > 0:
        c["spirits"].append({"type": kind, "force": force, "services": net, "bound": False, "notes": ""})
        return f"The {kind} spirit answers with {net} service{'s' if net != 1 else ''}. Drain: {drain['text']}."
    return f"The summoning failed. Drain: {drain['text']}."


def a_set_spirit(c, p, ctx):
    i = _list_index(c["spirits"], p.get("index"))
    s = c["spirits"][i]
    if "services" in p:
        s["services"] = max(0, min(30, _int(p["services"])))
    if "bound" in p:
        s["bound"] = bool(p["bound"])
    if "notes" in p:
        s["notes"] = _clip(p["notes"], 300)
    if s["services"] <= 0 and p.get("release_when_done", True) and "services" in p:
        c["spirits"].pop(i)
        return "Services used up: the spirit departs."
    return "Saved."


def a_release_spirit(c, p, ctx):
    i = _list_index(c["spirits"], p.get("index"))
    return f"The {c['spirits'].pop(i)['type']} spirit is released."


def a_compile(c, p, ctx):
    """Compile a sprite: Tasking + Resonance vs Level x 2; tasks = net hits; fading = the sprite's hits."""
    if c.get("magic_type") != "Technomancer":
        raise RuleError("Only technomancers compile sprites.")
    kind = p.get("type")
    if kind not in M.SPRITES:
        raise RuleError("Unknown sprite type.")
    d = derive(c)
    level = max(1, min(d["attributes"]["Resonance"] * 2, _int(p.get("level"), 1)))
    if sum(1 for s in c["sprites"] if not s.get("registered")) >= 1 and not ctx.gamemaster:
        raise RuleError("You can have only one unregistered sprite at a time.")
    pool = pool_by_key(c, "compile", d)
    parts = pool["parts"] + ([["Wound modifier", d["wound_modifier"]]] if d["wound_modifier"] else [])
    me = DICE.new_roll(max(1, sum(x[1] for x in parts)))
    sprite = DICE.new_roll(level * 2)
    net = me["hits"] - sprite["hits"]
    fading = resist_drain(c, d, sprite["hits"], "fading")
    ctx.log.append(f"compiled a level {level} {kind} sprite: {me['hits']} vs {sprite['hits']} hits. "
                   + (f"{net} task{'s' if net != 1 else ''}." if net > 0 else "Compilation failed.")
                   + f" Fading {sprite['hits']}: {fading['text']}.")
    me["label"] = f"Compile {kind} sprite (level {level})"
    me["parts"] = parts
    ctx.rolls.append(("sr", me))
    if net > 0:
        c["sprites"].append({"type": kind, "level": level, "tasks": net, "registered": False})
        return f"The {kind} sprite owes {net} task{'s' if net != 1 else ''}. Fading: {fading['text']}."
    return f"Compilation failed. Fading: {fading['text']}."


def a_set_sprite(c, p, ctx):
    i = _list_index(c["sprites"], p.get("index"))
    s = c["sprites"][i]
    if "tasks" in p:
        s["tasks"] = max(0, min(30, _int(p["tasks"])))
    if "registered" in p:
        want = bool(p["registered"])
        if want and not s.get("registered"):
            d = derive(c)
            if sum(1 for x in c["sprites"] if x.get("registered")) >= d["sprite_limit"] and not ctx.gamemaster:
                raise RuleError(f"You can register at most {d['sprite_limit']} sprites (your Resonance).")
        s["registered"] = want
    if s["tasks"] <= 0 and "tasks" in p:
        c["sprites"].pop(i)
        return "Tasks used up: the sprite decompiles."
    return "Saved."


def a_release_sprite(c, p, ctx):
    i = _list_index(c["sprites"], p.get("index"))
    return f"The {c['sprites'].pop(i)['type']} sprite is released."


# ---- drain / fading
def resist_drain(c, d, dv, kind="drain"):
    """Roll drain (or fading) resistance and apply it: Stun, or Physical when it exceeds Magic/Resonance."""
    dv = max(0, _int(dv))
    if dv <= 0:
        return {"dv": 0, "hits": 0, "damage": 0, "track": None, "text": "no drain" if kind == "drain" else "no fading"}
    if kind == "fading":
        pool = d["fading_pool"]
        cap = d["attributes"]["Resonance"]
    else:
        pool = d["drain_pool"]
        cap = d["attributes"]["Magic"]
    hits = hits_of(pool + (d["wound_modifier"] if d["wound_modifier"] else 0))
    dmg = max(0, dv - hits)
    track = "physical" if dv > cap else "stun"
    if dmg:
        take_damage(c, track, dmg, drain=True)
    word = "Physical" if track == "physical" else "Stun"
    return {"dv": dv, "hits": hits, "damage": dmg, "track": track,
            "text": f"{hits} hits against {dv}" + (f", took {dmg} {word}" if dmg else ", no damage")}


# ---- toxins, drugs and diseases
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}


def effect_status(e):
    """An effect word -> (status, value) or None: "Nausea" -> Nauseated, "Blinded I" -> (Blinded, 1)."""
    e = str(e or "").strip()
    if e in TOX.EFFECT_STATUSES:
        return TOX.EFFECT_STATUSES[e], True
    name, _, lvl = e.partition(" ")
    if name in K.STATUSES:
        return name, _ROMAN.get(lvl.strip(), True) if lvl else True
    return None


def _clean_effect_fields(raw):
    """The lasting parts of a substance or of its crash."""
    out = {"attrs": {a: max(-6, min(6, _int(v))) for a, v in (raw.get("attrs") or {}).items() if a in CORE_ATTRS and _int(v)}}
    for k, lo, hi in (("pool", -6, 6), ("pool_physical", -6, 6), ("hpt", 0, 3), ("sustain", -2, 0)):
        if _int(raw.get(k)):
            out[k] = max(lo, min(hi, _int(raw.get(k))))
    sk = {k: max(-6, min(6, _int(v))) for k, v in (raw.get("skills") or {}).items() if k in K.SKILLS and _int(v)}
    if sk:
        out["skills"] = sk
    zero = [a for a in (raw.get("zero") or []) if a in CORE_ATTRS][:4]
    if zero:
        out["zero"] = zero
    return out


LASTING = ("attrs", "init_dice", "pool", "pool_physical", "hpt", "sustain", "skills", "zero")


def clean_substance(raw):
    """A substance from the GM's library editor -> safe dict (or None)."""
    if not isinstance(raw, dict) or not str(raw.get("name") or "").strip():
        return None
    crash = raw.get("crash") if isinstance(raw.get("crash"), dict) else None
    if crash:
        crash = dict(_clean_effect_fields(crash), dv=max(0, min(30, _int(crash.get("dv")))),
                     damage=crash.get("damage") if crash.get("damage") in ("S", "P") else "S",
                     effects=[_clip(e, 30) for e in (crash.get("effects") or [])][:4], duration=_clip(crash.get("duration"), 40))
    out = {"id": re.sub(r"[^a-z0-9-]", "", str(raw.get("id") or "").lower())[:40] or None,
           "name": _clip(raw.get("name"), 60).strip(), "kind": raw.get("kind") if raw.get("kind") in ("toxin", "drug", "disease") else "toxin",
           "source": _clip(raw.get("source") or "Custom", 40), "vectors": [v for v in (raw.get("vectors") or []) if v in TOX.VECTORS][:4],
           "speed": _clip(raw.get("speed"), 30), "power": max(0, min(30, _int(raw.get("power")))), "duration": _clip(raw.get("duration"), 40),
           "damage": raw.get("damage") if raw.get("damage") in ("S", "P") else "",
           "effects": [_clip(e, 30) for e in (raw.get("effects") or [])][:6],
           "init_dice": max(0, min(4, _int(raw.get("init_dice")))), "addiction": max(0, min(10, _int(raw.get("addiction")))),
           "crash": crash, "desc": _clip(raw.get("desc"), 600)}
    out.update(_clean_effect_fields(raw))
    return out


def _apply_statuses(c, effects, left=None):
    """Set the statuses an effect list calls for; returns the names set."""
    st, names = c.setdefault("statuses", {}), []
    for e in effects or []:
        hit = effect_status(e)
        if not hit:
            continue
        status, value = hit
        st[status] = (left or 1) if status == "Poisoned" else value
        names.append(status)
    return names


def _lasting(src):
    return {k: src[k] for k in LASTING if src.get(k)}


def expose(c, sub, ctx, resist=True, label="Exposed to"):
    """Toxin Resistance (Body + Willpower): hits lower the Power; what's left applies."""
    d = derive(c)
    power = _int(sub.get("power"))
    parts = [["Body", d["attributes"]["Body"]], ["Willpower", d["attributes"]["Willpower"]]]
    res = roll(sum(p[1] for p in parts)) if resist else {"hits": 0, "dice": [], "pool": 0, "glitch": False, "critical": False}
    left = max(0, power - res["hits"])
    lines = [f"{label} {sub['name']} (Power {power})" + (f": resisted {res['hits']} → Power {left}" if resist else " without resisting")]
    if resist:
        res["label"] = f"Toxin resistance: {sub['name']}"
        res["parts"] = parts
        ctx.rolls.append(("sr", res))
    if left:
        if sub.get("damage") in ("S", "P"):
            take_damage(c, "physical" if sub["damage"] == "P" else "stun", left)
            lines.append(f"{left} {'Physical' if sub['damage'] == 'P' else 'Stun'}")
        applied = _apply_statuses(c, sub.get("effects"), left)
        lines += applied
        lasting = _lasting(sub)
        if lasting or applied or sub.get("crash"):
            lst = c.setdefault("toxins", [])
            if sub.get("id"):
                lst[:] = [t for t in lst if t.get("id") != sub.get("id")]
            lst.append(dict(lasting, id=sub.get("id"), name=sub["name"], kind=sub.get("kind"), duration=sub.get("duration") or "",
                            crash=sub.get("crash"), statuses=applied, since=round(__import__("time").time())))
            if lasting:
                lines.append("in effect" + (f" for {sub['duration']}" if sub.get("duration") else ""))
        if sub.get("addiction"):
            ad = roll(sum(p[1] for p in parts))
            ad["label"] = f"Addiction resistance ({sub['addiction']}): {sub['name']}"
            ad["parts"] = parts
            ad["threshold"] = sub["addiction"]
            ad["success"] = ad["hits"] >= sub["addiction"]
            ctx.rolls.append(("sr", ad))
            if not ad["success"]:
                lines.append(addict(c, sub["name"]))
    else:
        lines.append("no effect")
    ctx.log.append("; ".join(lines) + ".")
    return "; ".join(lines) + "."


def addict(c, substance):
    q = next((x for x in c["qualities"] if x.get("name") == "Addiction" and (x.get("choice") or "").lower() == substance.lower()), None)
    if q:
        q["level"] = min(K.QUALITIES["Addiction"].get("levels", 6), max(1, _int(q.get("level"), 1)) + 1)
        return f"Addiction ({substance}) rises to level {q['level']}"
    c["qualities"].append({"name": "Addiction", "level": 1, "choice": substance})
    return f"gains Addiction ({substance}) 1"


def a_end_substance(c, p, ctx):
    """An effect wears off: its bonuses and the statuses it caused end, then its crash applies
    (unresisted damage, statuses, and penalties that last on their own)."""
    lst = c.get("toxins") or []
    i = _list_index(lst, p.get("index"))
    t = lst.pop(i)
    st = c.setdefault("statuses", {})
    still = {s2 for o in lst for s2 in o.get("statuses") or []}
    for name in t.get("statuses") or []:
        if name not in still:
            st.pop(name, None)
    crash = t.get("crash") or {}
    lines = [f"{t['name']} wears off"]
    if _int(crash.get("dv")):
        take_damage(c, "physical" if crash.get("damage") == "P" else "stun", crash["dv"])
        lines.append(f"crash: {crash['dv']} {'Physical' if crash.get('damage') == 'P' else 'Stun'}")
    applied = _apply_statuses(c, crash.get("effects"))
    lines += applied
    lasting = _lasting(crash)
    if lasting or applied:
        lst.append(dict(lasting, id=None, name=f"{t['name']} crash", kind="crash", duration=crash.get("duration") or "",
                        crash=None, statuses=applied, since=round(__import__("time").time())))
        if lasting:
            lines.append("crash in effect" + (f" for {crash['duration']}" if crash.get("duration") else ""))
    ctx.log.append("; ".join(lines) + ".")
    return "; ".join(lines) + "."


# ---- rigging
def control_rig(c):
    return max([_int(it.get("rating"), 1) for it in implants(c) if it.get("control_rig")] or [0])


def autosoft(c, kind):
    return max([_int(it.get("rating"), 1) for it in c["inventory"] if it.get("ref") == "cyberdecks-software-autosoft" and it.get("choice") == kind] or [0])


def vehicles_of(c):
    return [it for it in c["inventory"] if it.get("cat") in ("Vehicles", "Drones") and it.get("handling")]


def vehicle_pools(c, d):
    """Piloting pools for each vehicle or drone the character owns, in each control mode they can use."""
    out = []
    vs = vehicles_of(c)
    if not vs:
        return out
    rig = control_rig(c)
    can_remote = bool(d["matrix"].get("device")) or any(it.get("sub") == "RCCs" for it in c["inventory"])
    for it in vs:
        boxes = monitor_boxes(it)
        dmg_pen = -(min(_int(it.get("damage")), boxes) // WOUND_STEP)
        hint = f"Handling {it.get('handling')}"
        for mode, m in RIG.CONTROL.items():
            if mode == "jumped" and not rig:
                continue
            if mode == "remote" and not can_remote:
                continue
            skill, attr = m["pool"]
            parts = _skill_parts(c, d, skill, attr=attr)
            if parts is None:
                continue
            if mode == "jumped":
                parts = parts + [[f"Control rig {rig}", rig]]
            if dmg_pen:
                parts = parts + [["Vehicle damage", dmg_pen]]
            out.append(_pool(f"vehicle:{it['uid']}:{mode}", "Vehicles", f"{it['name']}: {m['name'].lower()}", parts,
                             vehicle=it["uid"], hint=hint + (f" · thresholds −{rig}" if mode == "jumped" else "")))
        pilot = _int(it.get("pilot"))
        if pilot and it.get("cat") == "Drones":
            for kind in ("Maneuvering", "Clearsight", "Evasion", "Stealth"):
                r = autosoft(c, kind)
                if r:
                    out.append(_pool(f"drone:{it['uid']}:{kind}", "Vehicles", f"{it['name']} on its own: {kind}",
                                     [["Pilot", pilot], [f"{kind} autosoft", r]] + ([["Vehicle damage", dmg_pen]] if dmg_pen else []), vehicle=it["uid"], hint=hint))
    return out


def monitor_boxes(it):
    return RIG.MONITOR_BASE + _half_up(_int(it.get("body")))


# ---- Overwatch Score and convergence
def add_overwatch(c, ctx, amount, why):
    """Raise the Overwatch Score; at 40, convergence."""
    amount = max(0, _int(amount))
    ms = c.setdefault("matrix_state", {"os": 0, "os_known": None})
    if not amount:
        return ""
    ms["os"] = _int(ms.get("os")) + amount
    if ms["os"] >= MX.OS_LIMIT:
        return converge(c, ctx)
    return ""


def converge(c, ctx):
    """GOD converges: the device used is bricked, the user is dumped (dumpshock in VR), location reported."""
    d = derive(c)
    mx = d["matrix"]
    ms = c.setdefault("matrix_state", {"os": 0, "os_known": None})
    ms["os"], ms["os_known"] = 0, None
    lines = ["CONVERGENCE: the demiGODs found you. Your physical location is reported"]
    if mx.get("device") and mx["device"] != "persona":
        find_item(c, mx["device"])["matrix_damage"] = mx["boxes"]
        lines.append(f"{mx.get('name')} is bricked")
    mode = (c.get("matrix") or {}).get("mode", "AR")
    if mode.startswith("VR"):
        dv, kind = MX.DUMPSHOCK["hot" if "hot" in mode else "cold"]
        res = hits_of(d["attributes"]["Willpower"])
        dmg = max(0, dv - res)
        if dmg:
            take_damage(c, "physical" if kind == "P" else "stun", dmg)
        lines.append(f"dumpshock {dv}{kind}, resisted {res} → {dmg} {'Physical' if kind == 'P' else 'Stun'}")
        c["matrix"]["mode"] = "AR"
    ctx.log.append("; ".join(lines) + ".")
    return "Convergence!"


def a_set_os(c, p, ctx):
    """GM: set or adjust a runner's Overwatch Score, or make the GOD converge."""
    ms = c.setdefault("matrix_state", {"os": 0, "os_known": None})
    if p.get("converge"):
        return converge(c, ctx)
    if "delta" in p:
        delta = _int(p["delta"])
        if delta > 0:
            if add_overwatch(c, ctx, delta, "GM"):
                return "Convergence!"
        else:
            ms["os"] = max(0, _int(ms.get("os")) + delta)
        return f"Overwatch Score {ms['os']}."
    ms["os"] = max(0, min(MX.OS_LIMIT, _int(p.get("os"))))
    if ms["os"] >= MX.OS_LIMIT:
        return converge(c, ctx)
    return f"Overwatch Score {ms['os']}."


def matrix_action_roll(c, d, key, res, target_rating, ctx):
    """After a Matrix action from the roller: roll the target's Defense (Device/Host Rating x 2), apply Overwatch."""
    a = MX.MATRIX_ACTIONS[key]
    notes = []
    defense = a.get("defense")
    def_dice = 0
    if isinstance(defense, int):
        def_dice = defense
    elif defense and target_rating:
        def_dice = target_rating * 2
    if def_dice:
        dres = roll(def_dice)
        net = res["hits"] - dres["hits"]
        res["defense"] = {"dice": dres["dice"], "hits": dres["hits"], "pool": def_dice}
        res["net"] = net
        notes.append(f"defense {def_dice} dice: {dres['hits']} hits → {'success' if net > 0 else 'failure'} ({net:+d} net)")
        if key == "check_os" and net > 0:
            c.setdefault("matrix_state", {})["os_known"] = _int((c.get("matrix_state") or {}).get("os"))
            notes.append(f"Overwatch Score {c['matrix_state']['os_known']}")
        if not a["legal"]:
            os_add = dres["hits"] * MX.OS_PER_ILLEGAL_HIT
            if any(p.get("running") and "hacking" in (find_item(c, p["uid"]).get("ref") or "") for p in d["matrix"].get("programs") or []):
                os_add += MX.OS_PER_HACKING_PROGRAM
            if add_overwatch(c, ctx, os_add, a["name"]):
                notes.append("CONVERGENCE")
    elif not a["legal"] and defense:
        notes.append("no target rating given: the GM rolls the defense")
    return notes


def matrix_damage(c, amount):
    """Matrix damage to the active device (the living persona takes it on the Stun track).
    A full monitor bricks the device and dumps the user: dumpshock in VR. Returns a note."""
    amount = max(0, _int(amount))
    d = derive(c)
    mx = d["matrix"]
    if not amount or not mx.get("device"):
        return ""
    if mx["device"] == "persona":
        take_damage(c, "stun", amount)
        return f"{amount} Matrix damage on the living persona (Stun)"
    it = find_item(c, mx["device"])
    it["matrix_damage"] = min(mx["boxes"], _int(it.get("matrix_damage")) + amount)
    if it["matrix_damage"] < mx["boxes"]:
        return f"{amount} Matrix damage on the {it['name']}"
    note = f"the {it['name']} is bricked"
    mode = (c.get("matrix") or {}).get("mode", "AR")
    if mode.startswith("VR"):
        dv, kind = MX.DUMPSHOCK["hot" if "hot" in mode else "cold"]
        res = hits_of(d["attributes"]["Willpower"])
        dmg = max(0, dv - res)
        if dmg:
            take_damage(c, "physical" if kind == "P" else "stun", dmg)
        c["matrix"]["mode"] = "AR"
        note += f"; dumpshock {dv}{kind} → {dmg}"
    return note


# ---- sustained spells
def sustain_count(c):
    """Spells that cost the caster dice: every sustained spell, minus Focused Concentration's free ones."""
    n = len(c.get("sustained") or [])
    if not n:
        return 0
    free = _qlevel(qualities_of(c), "free_sustain")
    return max(0, n - free)


def start_sustaining(c, sp, ctx, hits=0):
    lst = c.setdefault("sustained", [])
    if len(lst) >= 20:
        raise RuleError("That's a lot of spells to hold at once. Drop one first.")
    lst.append({"name": sp["name"], "hits": max(0, _int(hits)), "since": round(__import__("time").time())})
    pen = sustain_count(c)
    ctx.log.append(f"is sustaining {sp['name']}" + (f" (−{-pen * sustain_step(c)} dice on other tests)." if pen else "."))


def a_drop_sustained(c, p, ctx):
    lst = c.get("sustained") or []
    i = _list_index(lst, p.get("index"))
    sp = lst.pop(i)
    return f"Stopped sustaining {sp['name']}."


def a_sustain(c, p, ctx):
    """Sustain a known spell by hand (cast earlier, or by the GM)."""
    name = p.get("name")
    sp = next((x for x in c.get("spells") or [] if x.get("name") == name), None)
    if not sp:
        raise RuleError("Pick one of your spells.")
    start_sustaining(c, sp, ctx, p.get("hits"))
    return f"Sustaining {name}."


def condition_parts(c, d, kind="action", ranged=False):
    """Dice modifiers every test of this kind gets from the character's situation:
    sustained spells and statuses (Zapped, Fatigued, Confused...). Not applied to resistance tests."""
    out = []
    n = sustain_count(c)
    if n:
        out.append([f"Sustaining {n} spell{'s' if n > 1 else ''}", n * sustain_step(c)])
    out += substance_parts(c)
    key = "defense" if kind == "defense" else "attack"
    st = c.get("statuses") or {}
    for name, mod in ACT.STATUS_MODS.items():
        v = st.get(name)
        if not v or key not in mod or name == "Cover" or (mod.get("ranged_only") and not ranged):
            continue
        lv = 1 if v is True else _int(v, 1)
        spec = mod[key]
        if isinstance(spec, str):
            sign = -1 if spec.startswith("-") else 1
            spec = sign * int(spec.strip("+-#") or "1") * lv
        if spec:
            out.append([name, spec])
    return out


def sustain_step(c):
    """Dice lost per sustained spell: −2, or less while a drug such as Psyche is in effect."""
    step = ACT.SUSTAIN_PENALTY
    for t in c.get("toxins") or []:
        if _int(t.get("sustain")):
            step = max(step, _int(t["sustain"]))
    return step


def substance_parts(c, physical=False, only_physical=False):
    """Dice modifiers from drugs and crashes in effect: on every test, and on tests with a Physical attribute."""
    out = []
    for t in c.get("toxins") or []:
        if not only_physical and _int(t.get("pool")):
            out.append([t.get("name") or "Drug", _int(t["pool"])])
        if physical and _int(t.get("pool_physical")):
            out.append([t.get("name") or "Drug", _int(t["pool_physical"])])
    return out


def substance_skills(c):
    """{skill: [[drug, ±n], ...]} from drugs in effect (Nitro: +2 Perception)."""
    out = {}
    for t in c.get("toxins") or []:
        for sk, n in (t.get("skills") or {}).items():
            if _int(n):
                out.setdefault(sk, []).append([t.get("name") or "Drug", _int(n)])
    return out


RESIST_POOLS = {"drain", "fading", "soak", "toxin", "natural_stun", "natural_physical"}


def _apply_conditions(c, d, out):
    act, dfn = condition_parts(c, d, "action"), condition_parts(c, d, "defense")
    rng = condition_parts(c, d, "action", ranged=True)
    phys, skill_bonus = substance_parts(c, physical=True, only_physical=True), substance_skills(c)
    for p in out:
        if p["key"] in RESIST_POOLS:
            continue
        extra = dfn if p["key"] in ("defense", "astral_defense") else (rng if p.get("weapon") and p.get("modes") is not None and p["key"] not in ("weapon:unarmed",) and not p.get("natural") and p.get("ar") and any(a is not None for a in (p.get("ar") or [])[1:]) else act)
        if phys and any(x[0] in K.PHYSICAL for x in p["parts"]):
            extra = list(extra) + phys
        for sk, parts in skill_bonus.items():
            if p["key"] == f"skill:{sk}" or p["key"].startswith(f"skill:{sk}:"):
                extra = list(extra) + parts
        if extra:
            p["parts"] = p["parts"] + [list(x) for x in extra]
            p["value"] = max(0, sum(x[1] for x in p["parts"]))
    return out


def after_cast(c, sp, ctx, extra_drain=0):
    """Drain after casting a spell from the roller."""
    d = derive(c)
    dv = _int(sp.get("drain")) + max(0, _int(extra_drain))
    res = resist_drain(c, d, dv, "drain")
    ctx.log.append(f"drain from {sp['name']} ({dv}): {res['text']}.")
    return res


def after_form(c, f, ctx):
    d = derive(c)
    meta = FORMS.get(f.get("name")) or {}
    res = resist_drain(c, d, meta.get("fade", 0), "fading")
    ctx.log.append(f"fading from {f['name']} ({meta.get('fade', 0)}): {res['text']}.")
    return res


# ---- damage and healing
def take_damage(c, track, amount, drain=False):
    """Add boxes of damage, Stun overflowing into Physical. Resets the 'once per injuries' healing flags."""
    amount = max(0, _int(amount))
    if not amount:
        return
    if not drain and _qeffect(qualities_of(c), "injury_prone"):
        amount += 1                               # Injury Prone: one extra box of the same type
    d = derive(c)
    if track == "stun":
        sd = _int(c["stun_damage"]) + amount
        if sd > d["stun_boxes"]:
            over = sd - d["stun_boxes"]
            sd = d["stun_boxes"]
            c["physical_damage"] = min(d["physical_boxes"] + d["overflow_boxes"], _int(c["physical_damage"]) + over)
            if drain:
                c["drain_phys"] = _int(c.get("drain_phys")) + over
        if drain:
            c["drain_stun"] = _int(c.get("drain_stun")) + (sd - _int(c["stun_damage"]))
        c["stun_damage"] = sd
    else:
        c["physical_damage"] = min(d["physical_boxes"] + d["overflow_boxes"], _int(c["physical_damage"]) + amount)
        if drain:
            c["drain_phys"] = _int(c.get("drain_phys")) + amount
    if not drain:
        c["heal_used"] = {}


def heal_boxes(c, track, n, allow_drain=True):
    """Heal boxes on a track. Overflow (Physical beyond the monitor) heals first."""
    n = max(0, _int(n))
    if track == "stun":
        healable = _int(c["stun_damage"]) - (0 if allow_drain else _int(c.get("drain_stun")))
        h = min(n, max(0, healable))
        c["stun_damage"] = _int(c["stun_damage"]) - h
        if allow_drain:
            c["drain_stun"] = max(0, min(_int(c.get("drain_stun")) - h, c["stun_damage"]))
    else:
        healable = _int(c["physical_damage"]) - (0 if allow_drain else _int(c.get("drain_phys")))
        h = min(n, max(0, healable))
        c["physical_damage"] = _int(c["physical_damage"]) - h
        if allow_drain:
            c["drain_phys"] = max(0, min(_int(c.get("drain_phys")) - h, c["physical_damage"]))
    return h


def a_set_damage(c, p, ctx):
    track = p.get("track")
    if track not in ("physical", "stun"):
        raise RuleError("Unknown track.")
    d = derive(c)
    v = max(0, _int(p.get("value")))
    key = f"{track}_damage"
    cur = _int(c[key])
    if v > cur:
        if track == "stun" and v > d["stun_boxes"]:
            take_damage(c, "stun", v - cur)
        else:
            take_damage(c, track, v - cur)
    else:
        heal_boxes(c, track, cur - v)
    return "Condition updated."


def a_damage(c, p, ctx):
    track = p.get("track")
    n = _int(p.get("amount"))
    if track not in ("physical", "stun") or n == 0:
        raise RuleError("Bad damage.")
    if n > 0:
        take_damage(c, track, n)
    else:
        heal_boxes(c, track, -n)
    return f"{abs(n)} {track.capitalize()} {'healed' if n < 0 else 'taken'}."


def heal_threshold(patient_d):
    return max(0, int(math.ceil(5 - patient_d["essence"] - 1e-9)))


def apply_heal(c, method, hits, ctx):
    """Apply a healing test's hits to a patient (after the healer rolled). Returns a description."""
    d = derive(c)
    used = c.setdefault("heal_used", {})
    if method in ("first_aid", "medkit", "magic"):
        if used.get(method):
            raise RuleError(f"This set of injuries already received {method.replace('_', ' ')}.")
        thr = heal_threshold(d)
        net = hits - thr
        used[method] = True
        if net <= 0:
            return f"{hits} hits vs threshold {thr}: no healing."
        healed = []
        over = max(0, _int(c["physical_damage"]) - d["physical_boxes"])
        if method == "first_aid":
            # 1 Stun per hit (not drain), or 1 Physical/Overflow per 2 hits; Overflow first, then Physical, then Stun
            pts = net
            hp = 0
            while pts >= 2 and _int(c["physical_damage"]) - _int(c.get("drain_phys")) > 0:
                hp += heal_boxes(c, "physical", 1, allow_drain=False)
                pts -= 2
            hs = heal_boxes(c, "stun", pts, allow_drain=False)
            healed = [f"{hp} Physical" if hp else "", f"{hs} Stun" if hs else ""]
        else:
            pts = net
            hp = heal_boxes(c, "physical", min(pts, over), allow_drain=False) if over else 0
            pts -= hp
            hp2 = heal_boxes(c, "physical", pts, allow_drain=False)
            pts -= hp2
            hs = heal_boxes(c, "stun", pts, allow_drain=False)
            healed = [f"{hp} Overflow" if hp else "", f"{hp2} Physical" if hp2 else "", f"{hs} Stun" if hs else ""]
        txt = ", ".join(x for x in healed if x) or "nothing left to heal"
        return f"{hits} hits vs threshold {thr}: healed {txt}."
    if method == "natural_stun":
        h = heal_boxes(c, "stun", hits)
        return f"an hour of rest: {hits} hits, healed {h} Stun."
    if method == "natural_physical":
        h = heal_boxes(c, "physical", hits)
        return f"a day of rest: {hits} hits, healed {h} Physical."
    raise RuleError("Unknown healing method.")


def natural_pool(c, method, assisted=False):
    d = derive(c)
    A = d["attributes"]
    if method == "natural_stun":
        parts = [["Body", A["Body"]], ["Willpower", A["Willpower"]]]
    else:
        parts = [["Body", A["Body"]], ["Body", A["Body"]]]
        over = max(0, d["physical_damage"] - d["physical_boxes"])
        if over and d["wound_modifier"]:
            parts.append(["Wound modifier", d["wound_modifier"]])
    if assisted:
        parts.append(["Medical attention", 2])
    for it in implants(c):
        if _int(it.get("heal_bonus")):
            parts.append([it["name"], _int(it["heal_bonus"])])
    return parts


# ---- statuses (GM)
def a_set_status(c, p, ctx):
    name = p.get("status")
    if name not in K.STATUSES:
        raise RuleError("Unknown status.")
    st = c.setdefault("statuses", {})
    if p.get("on"):
        meta = K.STATUSES[name]
        val = _int(p.get("value"), 1) if (meta.get("value") or meta.get("levels")) else True
        st[name] = val
    else:
        st.pop(name, None)
    return f"{name} {'on' if p.get('on') else 'off'}."


# ---- GM-only
def a_gamemaster_set(c, p, ctx):
    for k in ("karma", "nuyen"):
        if k in p:
            v = _int(p[k], c[k])
            if v != c[k]:
                ctx.ledger.append((k, v - c[k], "GM adjustment"))
                c[k] = v
    if "current_edge" in p:
        c["current_edge"] = max(0, min(EDGE_CAP, _int(p["current_edge"])))
    for k in ("initiation_grade", "submersion_grade"):
        if k in p:
            c[k] = max(0, min(20, _int(p[k])))
    return "Saved."


def a_set_ammo(c, p, ctx):
    """GM: set a weapon's loaded rounds directly."""
    it = find_item(c, p.get("uid"))
    if not it.get("clip"):
        raise RuleError("That weapon doesn't take ammunition.")
    it.setdefault("loaded", {"rounds": 0, "type": "Regular"})["rounds"] = max(0, min(it["clip"], _int(p.get("rounds"))))
    return "Ammo updated."


ACTIONS = {
    "set_info": a_set_info, "set_portrait": a_set_portrait, "trade_karma": a_trade_karma,
    "set_attribute": a_set_attribute, "raise_attribute": a_raise_attribute, "autoroll": a_autoroll,
    "set_skill": a_set_skill, "set_spec": a_set_spec, "set_expertise": a_set_expertise,
    "add_knowledge": a_add_knowledge, "remove_knowledge": a_remove_knowledge,
    "set_language": a_set_language, "remove_language": a_remove_language,
    "add_quality": a_add_quality, "remove_quality": a_remove_quality, "set_quality_level": a_set_quality_level,
    "buy": a_buy, "buy_pack": a_buy_pack, "set_infected": a_set_infected, "infected_power": a_infected_power,
    "set_infected_essence": a_set_infected_essence, "buy_custom": a_buy_custom, "give": a_give, "edit_item": a_edit_item,
    "toggle_equipped": a_toggle_equipped, "remove_item": a_remove_item, "sell_item": a_sell_item,
    "reload": a_reload, "unload": a_unload, "bond_focus": a_bond_focus, "set_vehicle_damage": a_set_vehicle_damage,
    "set_program": a_set_program, "set_matrix": a_set_matrix,
    "save_contact": a_save_contact, "remove_contact": a_remove_contact, "verify_contact": a_verify_contact,
    "learn_spell": a_learn_spell, "forget_spell": a_forget_spell,
    "set_power": a_set_power, "remove_power": a_remove_power, "buy_power_point": a_buy_power_point,
    "initiate": a_initiate, "learn_form": a_learn_form, "forget_form": a_forget_form,
    "summon": a_summon, "set_spirit": a_set_spirit, "release_spirit": a_release_spirit,
    "compile": a_compile, "set_sprite": a_set_sprite, "release_sprite": a_release_sprite,
    "set_damage": a_set_damage, "damage": a_damage,
    "set_status": a_set_status, "gamemaster_set": a_gamemaster_set, "set_ammo": a_set_ammo,
    "drop_sustained": a_drop_sustained, "sustain": a_sustain, "set_os": a_set_os, "end_substance": a_end_substance,
}
GAMEMASTER_ONLY = {"give", "verify_contact", "set_status", "gamemaster_set", "set_ammo", "set_os"}


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

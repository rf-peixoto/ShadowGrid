"""Turn Sixth World Companion PACK contents into store items.

Each PACK line ("4 spare clips", "Ares Predator VI (w/ quickdraw holster, silencer)",
"100 gel rounds (Ares Predator VI)", "cyberjack (rating 6, Used)") is matched to a
catalog entry with a quantity, rating, grade and note. Accessories after "w/"
become their own items. Anything the store doesn't sell becomes a custom item.
"""
import re

from . import catalog as CAT
from . import companion6e as C
from . import gear6e as G

WORD_N = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
GRADES = ("Used", "Alpha", "Beta", "Delta")
GRADE_NAMES = {"Used": "Used", "Alpha": "Alphaware", "Beta": "Betaware", "Delta": "Deltaware"}   # book wording -> store grades
for _p in C.PACKS:
    if _p.get("grades"):
        _p["grades"] = {GRADE_NAMES.get(g, g): v for g, v in _p["grades"].items()}


def _n(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


_BY_NAME = {}


def _index():
    if not _BY_NAME:
        for e in CAT.ITEMS:
            _BY_NAME.setdefault(_n(e["name"]), e)
    return _BY_NAME


# free-text names -> store names
ALIASES = {
    "fake sin": "Fake SIN", "fake license": "Fake License", "stealth tags": "Security/Stealth Tags (10)",
    "stealth tag": "Security/Stealth Tags (10)", "sensor tag": "Sensor Tags (10)", "area jammer": "Jammer, Area",
    "directional jammer": "Jammer, Directional", "plastic restraints": "Plastic Straps (10)", "plastic straps": "Plastic Straps (10)",
    "miniwelder fuel canister": "Miniwelder Fuel Canister", "standard rope": "Standard Rope (100 m)", "stealth rope": "Stealth Rope (100 m)",
    "myomeric rope": "Myomeric Rope (10 m)", "stim patch": "Stim Patch", "trauma patch": "Trauma Patch", "spare clip": "Spare Clip",
    "speed loader": "Speed Loader", "taser dart": "Taser rounds", "injection bolt": "Injection Bolt", "bolt": "Bolt",
    "stun grenade": "Stun Grenade", "fragmentation grenade": "Fragmentation Grenade", "high explosive grenade": "High-Explosive Grenade",
    "smoke grenade": "Smoke/Thermal Smoke Grenade", "thermal smoke grenade": "Smoke/Thermal Smoke Grenade", "gas grenade": "Gas Grenade",
    "flash pak": "Flash-Pak", "fragmentation rocket": "Fragmentation Rocket", "high explosive rocket": "High-Explosive Rocket",
    "anti vehicle rocket": "Anti-Vehicle Rocket", "assault cannon round": "Assault Cannon rounds", "throwing knife": "Throwing Knife", "throwing knives": "Throwing Knife",
    "throwing star": "Throwing Star", "combat knife": "Combat/Survival Knife", "reagent": "Reagents (dram)", "binoculars": "Binoculars, Optical",
    "periscope": "Periscope (handheld)", "mage sight goggles": "Mage Sight Goggles", "magical lodge materials": "Magical Lodge Materials",
    "weapon focus": "Weapon Focus", "electronics kit": "Tool Kit", "automotive kit": "Tool Kit", "aircraft kit": "Tool Kit",
    "armorer kit": "Tool Kit", "demolitions kit": "Tool Kit", "automotive shop": "Tool Shop", "aircraft shop": "Tool Shop",
    "armorer shop": "Tool Shop", "standard certified credstick": "Credstick, Standard", "silver certified credstick": "Credstick, Silver",
    "gold certified credstick": "Credstick, Gold", "commercial explosives": "Explosive Package", "plastic explosives": "Explosive Package",
    "foam explosives": "Explosive Package", "omnidirectional microphone": "Omni-Directional Microphone", "micro camera": "Micro-Camera",
    "sensor handheld": "Handheld Sensor Housing", "single sensor": "Single Sensor", "cyberjack": "Cyberjack", "wired reflexes": "Wired Reflexes",
    "cybereyes": "Cybereyes", "cyberears": "Cyberears", "bone lacing aluminum": "Bone Lacing (Aluminum)", "shock hand": "Shock Limb",
    "retractable spur": "Retractable Spurs", "reflex recorder": "Reflex Recorder", "hydraulic jacks": "Hydraulic Jacks",
    "steel lynx": "Steel Lynx Combat Drone", "ymc delfin": "YNT Delfin", "aztechnology nightrunner": "Aztechnology Sunrunner/Nightrunner",
    "ares red dog": "Ares Red Dog Series", "ares super squirt": "Ares S-III Super Squirt", "fn har": "FN-HAR", "mct hornet": "MCT Hornet",
    "monofilament whip": "Monofilament Whip", "full body armor helmet": "Full Body Armor Helmet", "armante dress": "Armante Dress",
    "agent": "Agent", "activesoft": "Activesoft", "cyberprogram basic": "Cyberprogram, Basic", "cyberprogram hacking": "Cyberprogram, Hacking",
    "mapsoft": "Mapsoft", "flashlight": "Flashlight", "gecko tape gloves": "Gecko Tape Gloves", "survival kit": "Survival Kit",
    "climbing gear": "Climbing Gear", "gas mask": "Gas Mask", "respirator": "Respirator", "trid projector": "Trid Projector",
    "biomonitor": "Biomonitor", "bug scanner": "Bug Scanner", "tag eraser": "Tag Eraser", "micro transceiver": "Micro-Transceiver",
    "miniwelder": "Miniwelder", "grapple gun": "Grapple Gun", "data tap": "Data Tap", "white noise generator": "White Noise Generator",
    "medkit": "Medkit", "rigger interface": "Rigger Interface", "heavy weapon mount": "Heavy Weapon Mount",
    "standard weapon mount": "Standard Weapon Mount", "glue sprayer": "Glue Sprayer", "glue solvent": "Glue Solvent",
    "lockpick set": "Lockpick Set", "sequencer": "Sequencer", "keycard copier": "Keycard Copier", "cellular glove molder": "Cellular Glove Molder",
    "laser microphone": "Laser Microphone", "directional microphone": "Directional Microphone", "earbuds": "Earbuds",
    "glasses": "Glasses", "goggles": "Goggles", "contacts": "Contacts", "camera": "Camera", "helmet": "Helmet",
}
# "w/" add-ons by kind of base item
ADDONS = {
    "weapon": {"internal smartgun system": "Smartgun System, Internal", "external smartgun system": "Smartgun System, External",
               "smartgun system": "Smartgun System, External", "laser sight": "Laser Sight", "quickdraw holster": "Quick-Draw Holster",
               "concealable holster": "Concealable Holster", "concealed holster": "Concealable Holster", "hidden arm slide": "Hidden Arm Slide",
               "gas vent system": "Gas-Vent System", "shock pad": "Shock Pad", "silencer": "Silencer/Suppressor",
               "suppressor": "Silencer/Suppressor", "airburst link": "Airburst Link", "external clip port": "External Clip Port"},
    "armor": {"chemical protection": "Chemical Protection", "chemical resistance": "Chemical Protection", "cold resistance": "Cold Resistance",
              "electricity resistance": "Electricity Resistance", "fire resistance": "Fire Resistance", "chemical seal": "Chemical Seal",
              "electrochromic": "Electrochromic Feature", "electrochromic feature": "Electrochromic Feature"},
    "vision": {"flare compensation": "Flare Compensation", "image link": "Image Link", "low light vision": "Low-Light Vision",
               "thermographic vision": "Thermographic Vision", "smartlink": "Smartlink", "vision enhancement": "Vision Enhancement",
               "visual enhancement": "Vision Enhancement", "vision magnification": "Vision Magnification", "ultrasound": "Ultrasound Link",
               "ultrasound link": "Ultrasound Link", "audio enhancement": "Audio Enhancement", "select sound filter": "Select Sound Filter",
               "spatial recognizer": "Spatial Recognizer"},
    "eye": {"flare compensation": "Flare Compensation (eye)", "image link": "Image Link (eye)", "low light vision": "Low-Light Vision (eye)",
            "thermographic vision": "Thermographic Vision (eye)", "smartlink": "Smartlink (eye)", "vision enhancement": "Vision Enhancement (eye)",
            "vision magnification": "Vision Magnification (eye)"},
    "ear": {"audio enhancement": "Audio Enhancement (ear)", "balance augmenter": "Balance Augmenter", "damper": "Damper",
            "select sound filter": "Select Sound Filter (ear)", "spatial recognizer": "Spatial Recognizer (ear)"},
}
AMMO_TYPES = {"regular": "Regular", "explosive": "Explosive", "gel": "Gel", "apds": "APDS", "flechette": "Flechette",
              "stick n shock": "Stick-n-Shock", "caseless": "Caseless"}
PACKS_BY_NAME = {p["name"]: p for p in C.PACKS}


def _entry(name):
    idx = _index()
    k = _n(name)
    if k in idx:
        return idx[k]
    if k in ALIASES:
        return idx.get(_n(ALIASES[k]))
    for cut in ("es", "s"):
        if k.endswith(cut) and k[:-len(cut)] in ALIASES:
            return idx.get(_n(ALIASES[k[:-len(cut)]]))
        if k.endswith(cut) and k[:-len(cut)] in idx:
            return idx[k[:-len(cut)]]
    return None


def _kind(e):
    if e is None:
        return ""
    if e["name"] in ("Helmet", "Full Body Armor Helmet"):
        return "vision"
    if e["cat"] in ("Ranged", "Melee"):
        return "weapon"
    if e["cat"] == "Armor":
        return "armor"
    if e["name"].startswith("Cybereyes"):
        return "eye"
    if e["name"].startswith("Cyberears"):
        return "ear"
    if e["cat"] == "Tools & Sensors" or e["name"] in ("Helmet", "Full Body Armor Helmet"):
        return "vision"
    return ""


def _ammo(count, kind, weapon_name):
    w = _entry(weapon_name)
    cls = (w or {}).get("ammo_class") or ("Light" if (w or {}).get("sub") == "Hold-outs" else None)
    if not cls or cls not in G.AMMO_CLASSES:
        return None
    label = G.AMMO_CLASSES[cls][0]
    if cls in ("Taser", "Dart", "Cannon"):
        return _entry(f"{label} rounds")
    return _entry(f"{kind} rounds ({label})")


def resolve_line(line):
    """-> list of {ref, name, rating, grade, qty, note, custom} for one PACK line (may expand to several)."""
    text = line.strip()
    count = 1
    m = re.match(r"^(\d+)\s+m\s+(.*)$", text)                         # "30 m myomeric rope"
    if m:
        e = _entry(m.group(2))
        if e:
            per = int(re.search(r"\((\d+) m\)", e["name"]).group(1)) if re.search(r"\((\d+) m\)", e["name"]) else 1
            return [{"ref": e["id"], "qty": max(1, int(m.group(1)) // per), "rating": None, "grade": None, "note": ""}]
    m = re.match(r"^(\d+|two|three|four|five|six)\s+(.*)$", text, re.I)
    if m and not re.match(r"^\d+\s*(?:cf|m)\b", m.group(2)):
        count = int(m.group(1)) if m.group(1).isdigit() else WORD_N[m.group(1).lower()]
        text = m.group(2)
    if text in PACKS_BY_NAME:
        out = []
        for _ in range(count):
            out += resolve_pack(PACKS_BY_NAME[text])["items"]
        return out
    # ammunition for a named weapon
    m = re.match(r"^(regular|explosive|gel|apds|flechette|stick-n-shock|caseless)\s+rounds\s*\((.+)\)$", text, re.I)
    if m:
        e = _ammo(count, AMMO_TYPES[_n(m.group(1))], m.group(2))
        if e:
            return [{"ref": e["id"], "qty": count, "rating": None, "grade": None, "note": f"for the {m.group(2)}", "rounds": True}]
    m = re.match(r"^(.*?) autosoft \(rating (\d+)\)$", text, re.I)
    if m:
        e = _entry("Autosoft")
        return [{"ref": e["id"], "qty": 1, "rating": int(m.group(2)), "grade": None, "note": m.group(1).capitalize()} for _ in range(count)]
    whole = _entry(text)
    base, inner = text, ""
    if not whole and "(" in text:
        base = text[:text.index("(")].strip()
        inner = text[text.index("(") + 1:text.rindex(")")] if ")" in text else text[text.index("(") + 1:]
    rating = grade = None
    notes, addons = [], []
    if inner:
        pre, _, post = inner.partition("w/")
        for tok in [t.strip() for t in pre.split(",") if t.strip()]:
            if re.match(r"^(rating|force)\s+\d+", tok, re.I):
                rating = int(re.findall(r"\d+", tok)[0])
                rest = re.sub(r"^(rating|force)\s+\d+\s*", "", tok, flags=re.I).strip()
                if rest:
                    notes.append(rest)
            elif tok in GRADES:
                grade = GRADE_NAMES[tok]
            elif tok.lower() in ("obvious", "synthetic"):
                base = f"{base} ({tok.lower()})"
            elif _n(tok) in AMMO_TYPES and _n(base).startswith("bone lacing"):
                base = f"{base} ({tok})"
            else:
                notes.append(tok)
        addons = [a.strip() for a in post.split(",") if a.strip()]
    e = whole or _entry(base)
    if e is None and rating:
        k = _n(base)
        name = ALIASES.get(k) or ALIASES.get(k.rstrip("s")) or base
        e = _entry(f"{name} {rating}")
    if e is None:
        return [{"ref": None, "name": text[:80], "qty": count, "rating": None, "grade": None, "note": "", "custom": True}]
    # rated families stored as separate entries ("Cyberjack 6", "Wired Reflexes 2", "Cybereyes 4")
    if rating and not CAT.rating_range(e):
        rated = _entry(f"{e['name']} {rating}")
        if rated:
            e = rated
    m10 = re.search(r"\((\d+)\)$", e["name"])            # sold in tens: "Plastic Straps (10)"
    if m10 and count >= int(m10.group(1)):
        count = max(1, count // int(m10.group(1)))
    out = []
    many = e["cat"] in ("Ranged", "Melee", "Vehicles", "Drones", "Armor", "Cyberware", "Bioware") and not e.get("consumable")
    unit = e.get("sub") == "Ammunition"
    if many and count > 1:
        for _ in range(count):
            out.append({"ref": e["id"], "qty": 1, "rating": rating, "grade": grade, "note": ", ".join(notes)})
    else:
        out.append({"ref": e["id"], "qty": count, "rating": rating, "grade": grade, "note": ", ".join(notes), "rounds": unit})
    kind = _kind(e)
    table = ADDONS.get(kind, {})
    for a in addons:
        am = re.match(r"^(.*?)\s*(\d+)?$", a)
        key, arating = _n(am.group(1)), (int(am.group(2)) if am.group(2) else None)
        target = table.get(key)
        ae = _entry(target) if target else None
        if ae:
            out.append({"ref": ae["id"], "qty": 1, "rating": arating, "grade": grade if ae.get("implant") or CAT.is_implant(ae) else None,
                        "note": f"on the {e['name']}"})
        else:
            out[0]["note"] = ", ".join(x for x in (out[0]["note"], a) if x)
    return out


def resolve_pack(p):
    """-> {"items": [...], "missing": [names not in the store]}"""
    items = []
    if p.get("includes"):
        items += resolve_pack(PACKS_BY_NAME[p["includes"]])["items"]
    for line in p["lines"]:
        items += resolve_line(line)
    if p.get("lifestyle"):
        items.append({"ref": None, "name": f"One month {p['lifestyle']} lifestyle (prepaid)", "qty": 1, "rating": None,
                      "grade": None, "note": "Tell your GM when you use it.", "custom": True})
    return {"items": items, "missing": [i["name"] for i in items if i.get("custom")]}


def pack_entry(p, i):
    """Store entry for a PACK (shown in the PACKs category)."""
    res = resolve_pack(p)
    entries = [CAT.BY_ID[x["ref"]] for x in res["items"] if x.get("ref")]
    offers = [CAT.offer(CAT.BY_ID[x["ref"]], x.get("rating"), x.get("grade") or "Standard", "") for x in res["items"] if x.get("ref")]
    avail = max([o["avail"] for o in offers if o["avail"] is not None] or [0])
    legal = "I" if any(o["legal"] == "I" for o in offers) else ("L" if any(o["legal"] == "L" for o in offers) else "")
    supplies = sorted({G.CATEGORY_SUPPLY.get(x["cat"], "General") for x in entries})
    contents = []
    for x in res["items"]:
        nm = x.get("name") or CAT.BY_ID[x["ref"]]["name"]
        r = f" {x['rating']}" if x.get("rating") and not re.search(r"\d$", nm) else ""
        q = f"{x['qty']} × " if x.get("qty", 1) > 1 and not x.get("rounds") else (f"{x['qty']} " if x.get("rounds") else "")
        g = f" ({x['grade']})" if x.get("grade") else ""
        contents.append(f"{q}{nm}{r}{g}" + (f" [{x['note']}]" if x.get("note") else ""))
    checks = sorted({(o["avail"], o["legal"], G.CATEGORY_SUPPLY.get(x["cat"], "General")) for o, x in zip(offers, entries)
                     if o["avail"] is not None}, key=lambda t: -t[0])
    e = {"id": "pack-" + re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-"), "name": p["name"], "cat": "PACKs",
         "sub": p["group"], "pack": True, "desc": p["desc"], "cost": p["cost"], "costN": p["cost"], "avail": str(avail) + (f"({legal})" if legal else ""),
         "availN": avail, "legalN": legal, "supplies": supplies, "supply": supplies[0] if len(supplies) == 1 else "Fixer",
         "contents": contents, "source": C.SOURCE, "checks": checks}
    if p.get("essence"):
        e["essenceN"] = p["essence"]
    if p.get("grades"):
        e["packGrades"] = {g: {"cost": v[0], "essence": v[1]} for g, v in p["grades"].items()}
    for k in ("skills", "licenses", "includes", "cash"):
        if p.get(k):
            e[k] = p[k]
    return e


PACK_ENTRIES = [pack_entry(p, i) for i, p in enumerate(C.PACKS)]
PACK_BY_ID = {e["id"]: (e, C.PACKS[i]) for i, e in enumerate(PACK_ENTRIES)}


def access(c, e, approved):
    """A PACK is on sale only if every item in it is (same contact rule as single items)."""
    for avail, legal, supply in e["checks"]:
        ok, why = CAT.access(c, avail, legal, supply, approved)
        if not ok:
            return False, why
    return True, ""

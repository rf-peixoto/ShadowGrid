"""Shadowrun Sixth World core rulebook gear tables (stats only).

Every item keeps the book's Availability (the number) and legality ("L" needs
a license, "I" is illegal), its cost and its game stats. Descriptions are
short summaries written for this app, not the book's text.

Rated items use expressions in ``R`` (the rating), e.g. ``cost="R*250"``;
``rating=(1, 6)`` gives the range. ``sr.rules`` evaluates them.
"""

# Store categories, in display order. "supply" is the contact category that
# can source the item (see CONTACT_SUPPLY).
STORE_CATEGORIES = [
    "Melee", "Ranged", "Ammo & Explosives", "Weapon Accessories", "Armor",
    "Electronics", "Cyberdecks & Software", "ID & Credit", "Tools & Sensors",
    "Security & B&E", "Survival", "Medical", "Cyberware", "Bioware", "Magic",
    "Vehicles", "Drones",
]

# What a contact can be asked to source. A contact unlocks an item when it
# covers the item's supply category and its Connection is higher than the
# item's Availability (book p. 244: "contacts can find goods whose
# Availability is less than their Connection rating").
CONTACT_SUPPLY = [
    "Weapons", "Ammo & Explosives", "Armor", "Electronics", "Matrix",
    "Identity", "Tools", "Security", "Medical", "Cyberware", "Bioware",
    "Magic", "Vehicles", "Drones", "General",
]
CATEGORY_SUPPLY = {
    "Melee": "Weapons", "Ranged": "Weapons", "Weapon Accessories": "Weapons",
    "Ammo & Explosives": "Ammo & Explosives", "Armor": "Armor",
    "Electronics": "Electronics", "Cyberdecks & Software": "Matrix",
    "ID & Credit": "Identity", "Tools & Sensors": "Tools",
    "Security & B&E": "Security", "Survival": "General", "Medical": "Medical",
    "Cyberware": "Cyberware", "Bioware": "Bioware", "Magic": "Magic",
    "Vehicles": "Vehicles", "Drones": "Drones",
}

# Firing modes: rounds used and the effect on the attack (SR6 p. 108-109).
FIRING_MODES = {
    "SS": {"name": "Single Shot", "rounds": 1, "ar": 0, "dv": 0},
    "SA": {"name": "Semi-Automatic", "rounds": 2, "ar": -2, "dv": 1},
    "BF": {"name": "Burst Fire", "rounds": 4, "ar": -4, "dv": 2},
    "FA": {"name": "Full Auto", "rounds": 10, "ar": -6, "dv": 0},
}

RANGES = ["Close", "Near", "Medium", "Far", "Extreme"]
RANGE_METERS = {"Close": "0-3 m", "Near": "4-50 m", "Medium": "51-250 m",
                "Far": "251-500 m", "Extreme": "500+ m"}

# Ammo: (class, availability, cost per 10 rounds). Book p. 262.
AMMO_CLASSES = {
    "Light": ("Hold-out / Light Pistol / Machine Pistol", "1", 5),
    "Heavy": ("Heavy Pistol / SMG", "1", 10),
    "Rifle": ("Rifles", "2(L)", 20),
    "Taser": ("Taser", "1", 10),
    "Dart": ("Injection Dart", "2", 5),
    "Cannon": ("Assault Cannon", "4(I)", 50),
}
# Ammo types: AR modifier, DV modifier, cost multiplier.
AMMO_TYPES = {
    "Regular": {"ar": 0, "dv": 0, "mult": 1.0, "note": "Standard rounds."},
    "APDS": {"ar": 2, "dv": -1, "mult": 3.0, "note": "Armor-piercing discarding sabot."},
    "Explosive": {"ar": 0, "dv": 1, "mult": 2.0, "note": "Explodes on impact."},
    "Flechette": {"ar": 1, "dv": -1, "mult": 1.5, "note": "A spread of tiny slivers."},
    "Gel": {"ar": 0, "dv": 0, "mult": 1.5, "stun": True,
            "note": "Stun damage; target makes Agility (2) or Body (4) or falls Prone."},
    "Stick-n-Shock": {"ar": 1, "dv": -1, "mult": 2.0, "stun": True, "elec": True,
                      "note": "Electrical Stun damage and the Zapped status."},
    "Caseless": {"ar": 0, "dv": 0, "mult": 2.0, "note": "Leaves no shell casings."},
}

# Weapon subcategory -> (skill, specialization, ammo class)
WEAPON_GROUPS = {
    "Blades": ("Close Combat", "Blades", None),
    "Clubs": ("Close Combat", "Clubs", None),
    "Other Melee": ("Close Combat", "Unarmed Combat", None),
    "Throwing & Bows": ("Athletics", "Throwing", None),
    "Tasers": ("Firearms", "Pistols", "Taser"),
    "Hold-outs": ("Firearms", "Pistols", "Light"),
    "Light Pistols": ("Firearms", "Pistols", "Light"),
    "Machine Pistols": ("Firearms", "Pistols", "Light"),
    "Heavy Pistols": ("Firearms", "Pistols", "Heavy"),
    "Submachine Guns": ("Firearms", "Automatics", "Heavy"),
    "Shotguns": ("Firearms", "Shotguns", "Rifle"),
    "Assault Rifles": ("Firearms", "Rifles", "Rifle"),
    "Sniper Rifles": ("Firearms", "Longarms", "Rifle"),
    "Machine Guns": ("Firearms", "Automatics", "Rifle"),
    "Special Weapons": ("Exotic Weapons", None, "Dart"),
    "Launchers": ("Exotic Weapons", "Launchers", None),
    "Implant Weapons": ("Close Combat", "Unarmed Combat", None),
}


def _w(name, sub, dv, ar, avail, cost, modes="", ammo="", desc="", **kw):
    skill, spec, ammo_class = WEAPON_GROUPS[sub]
    d = {"name": name, "cat": "Ranged" if modes or sub in ("Throwing & Bows",) else "Melee",
         "sub": sub, "dv": dv, "ar": ar, "avail": avail, "cost": cost,
         "skill": skill, "spec": spec}
    if sub in ("Blades", "Clubs", "Other Melee"):
        d["cat"] = "Melee"
    if modes:
        d["modes"] = modes
    if ammo:
        d["ammo"] = ammo
        if ammo_class:
            d["ammo_class"] = ammo_class
    if desc:
        d["desc"] = desc
    d.update(kw)
    return d


WEAPONS = [
    # --- Blades (p. 249) ---
    _w("Combat Axe", "Blades", "5P", "9/—/—/—/—", "4", 500, desc="Two-handed axe with a thrusting spike."),
    _w("Combat/Survival Knife", "Blades", "3P", "8/2/—/—/—", "2", 220, desc="Chisel-point fighting knife; can be thrown (max 20 m)."),
    _w("Forearm Snap Blades", "Blades", "3P", "6/—/—/—/—", "3", 185, desc="Three blades that pop out of a forearm sheath."),
    _w("Knife", "Blades", "2P", "6/1/—/—/—", "1", 20, desc="Any ordinary fighting blade; can be thrown (max 20 m)."),
    _w("Katana", "Blades", "4P", "10/—/—/—/—", "3", 350, desc="Two-handed samurai sword."),
    _w("Polearm", "Blades", "4P", "8/—/—/—/—", "2", 210, desc="Blade on a long haft; extra reach."),
    _w("Survival Knife", "Blades", "4P", "8/2/—/—/—", "2", 250, desc="Heavy knife with a saw back; can be thrown (max 20 m)."),
    _w("Sword", "Blades", "3P", "9/—/—/—/—", "3", 320),
    # --- Clubs ---
    _w("Club", "Clubs", "3S", "6/—/—/—/—", "1", 65),
    _w("Extendable Baton", "Clubs", "2S", "5/—/—/—/—", "2", 52),
    _w("Sap", "Clubs", "2S", "6/—/—/—/—", "1", 75),
    _w("Staff", "Clubs", "4S", "8/—/—/—/—", "1", 150),
    _w("Stun Baton", "Clubs", "5S(e)", "6/—/—/—/—", "2", 600, desc="Electrical riot prod with ten charges."),
    _w("Telescoping Staff", "Clubs", "4S", "8/—/—/—/—", "2", 250, desc="Collapses to baton size; extending takes a Minor Action."),
    # --- Other melee ---
    _w("Bike Chain", "Other Melee", "2S", "5/—/—/—/—", "1", 15),
    _w("Bullwhip", "Other Melee", "1P", "6/—/—/—/—", "4", 255, skill="Exotic Weapons", spec="Bullwhip"),
    _w("Knucks", "Other Melee", "3P", "6/—/—/—/—", "1", 100),
    _w("Shock Gloves", "Other Melee", "4S(e)", "5/—/—/—/—", "4", 790, desc="Electrified gloves; inflict Zapped. Ten charges."),
    _w("Monofilament Whip", "Other Melee", "6P", "14/—/—/—/—", "6(I)", 1300,
       skill="Exotic Weapons", spec="Monofilament Whip", desc="Two meters of monofilament line; a critical glitch hits the wielder."),
    _w("Ballistic Shield (bash)", "Other Melee", "2S", "4/—/—/—/—", "4", 0, skill="Exotic Weapons", spec="Shields",
       desc="Attack profile of the ballistic shield; buy the shield under Armor.", store=False),
    _w("Riot Shield (bash)", "Other Melee", "4S(e)", "4/—/—/—/—", "4", 0, skill="Exotic Weapons", spec="Shields",
       desc="Attack profile of the riot shield; buy the shield under Armor.", store=False),
    # --- Throwing weapons / projectiles (p. 250) ---
    _w("Bow", "Throwing & Bows", "(R/2)P", "(R/2)/(R)/(R/4)/—/—", "(R/3)(L)", "100+R*10", rating=(1, 14),
       ammo="1", ammo_class="Arrow", desc="Rating is the minimum Strength to use it and sets damage. Arrows must match its rating."),
    _w("Crossbow, Light", "Throwing & Bows", "2P", "6/8/2/—/—", "3", 150, ammo="4(m)", ammo_class="Bolt"),
    _w("Crossbow, Standard", "Throwing & Bows", "3P", "2/10/4/2/—", "3(L)", 290, ammo="4(m)", ammo_class="Bolt"),
    _w("Crossbow, Heavy", "Throwing & Bows", "4P", "2/8/6/4/—", "4(L)", 425, ammo="4(m)", ammo_class="Bolt"),
    _w("Throwing Knife", "Throwing & Bows", "2P", "10/9/3/—/—", "2", 155, consumable=True, desc="Consumed when thrown."),
    _w("Throwing Star", "Throwing & Bows", "2P", "9/11/5/—/—", "2", 160, consumable=True, desc="Consumed when thrown."),
    # --- Tasers ---
    _w("Defiance Super Shock", "Tasers", "6S(e)", "10/6/—/—/—", "1", 340, modes="SS", ammo="4(m)", desc="Heavy taser; max range 20 m."),
    _w("Yamaha Pulsar I", "Tasers", "4S(e)", "9/9/—/—/—", "1", 325, modes="SS", ammo="4(m)", desc="Max range 50 m."),
    _w("Yamaha Pulsar II", "Tasers", "4S(e)", "9/9/—/—/—", "1", 350, modes="SS", ammo="4(m)", desc="Max range 50 m."),
    # --- Hold-outs (p. 253) ---
    _w("Fichetti Tiffani Needler", "Hold-outs", "3P", "10/6/2/—/—", "2", 435, modes="SS", ammo="4(c)", ammo_class=None,
       desc="Fires flechette needles only.", fixed_ammo="Flechette"),
    _w("Streetline Special", "Hold-outs", "2P", "8/8/—/—/—", "2", 200, modes="SS", ammo="6(c)", desc="Plastic hold-out that fools scanners."),
    _w("Walther Palm Pistol", "Hold-outs", "2P", "12/7/—/—/—", "2", 345, modes="SS/BF", ammo="6(b)", desc="Double-barrel derringer."),
    # --- Light pistols ---
    _w("Ares Light Fire 70", "Light Pistols", "2P", "10/7/6/—/—", "3(L)", 350, modes="SA", ammo="16(c)", desc="Integral silencer and laser sight."),
    _w("Ares Light Fire 75", "Light Pistols", "2P", "10/7/6/—/—", "3(L)", 400, modes="SA", ammo="16(c)", desc="Integral silencer, laser sight and smartgun system."),
    _w("Beretta 101T", "Light Pistols", "2P", "9/8/6/—/—", "2(L)", 260, modes="SA", ammo="21(c)"),
    _w("Beretta 201T", "Light Pistols", "2P", "9/8/6/—/—", "3(L)", 460, modes="SA/FA", ammo="21(c)", desc="Detachable shoulder stock."),
    _w("Colt America L36", "Light Pistols", "2P", "8/8/6/—/—", "2(L)", 230, modes="SA", ammo="11(c)"),
    _w("Fichetti Security 600", "Light Pistols", "2P", "10/9/6/—/—", "3(L)", 390, modes="SA", ammo="30(c)", desc="Folding stock and laser sight."),
    _w("Ruger Redhawk", "Light Pistols", "3P", "7/10/7/—/—", "2(L)", 250, modes="SA/BF", ammo="8(cy)", desc="Revolver."),
    # --- Machine pistols ---
    _w("Ares Crusader II", "Machine Pistols", "2P", "9/9/7/—/—", "4(L)", 520, modes="SA/BF", ammo="40(c)", desc="Gas-vent system and smartgun system."),
    _w("Ceska Black Scorpion", "Machine Pistols", "2P", "10/9/8/—/—", "3(L)", 510, modes="SA/BF", ammo="35(c)", desc="Folding stock."),
    _w("Steyr TMP", "Machine Pistols", "2P", "8/8/6/—/—", "3(L)", 690, modes="SA/FA", ammo="30(c)", desc="Laser sight."),
    # --- Heavy pistols (p. 255) ---
    _w("Ares Predator VI", "Heavy Pistols", "3P", "10/10/8/—/—", "2(L)", 750, modes="SA/BF", ammo="15(c)", desc="Smartgun system; variable ammo magazine."),
    _w("Ares Viper Slivergun", "Heavy Pistols", "4P(f)", "12/8/6/—/—", "4(L)", 610, modes="SA/BF", ammo="30(c)", desc="Fires flechette slivers; integral silencer.", fixed_ammo="Flechette"),
    _w("Browning Ultra-Power", "Heavy Pistols", "3P", "10/9/6/—/—", "2(L)", 315, modes="SA", ammo="10(c)", desc="Laser sight."),
    _w("Colt Government 2076", "Heavy Pistols", "3P", "10/8/6/—/—", "3(L)", 275, modes="SA", ammo="14(c)"),
    _w("Colt Manhunter", "Heavy Pistols", "3P", "10/8/6/—/—", "3(L)", 500, modes="SA", ammo="14(c)", desc="Government 2076 with a smartgun system."),
    _w("Ruger Super Warhawk", "Heavy Pistols", "4P", "8/11/8/—/—", "3(L)", 400, modes="SA", ammo="6(cy)", desc="Big revolver."),
    # --- SMGs ---
    _w("Colt Cobra TZ-100", "Submachine Guns", "3P", "9/9/6/—/—", "2(L)", 730, modes="SA/BF", ammo="32(c)"),
    _w("Colt Cobra TZ-110", "Submachine Guns", "3P", "10/10/7/—/—", "2(L)", 785, modes="SA/BF", ammo="32(c)"),
    _w("Colt Cobra TZ-120", "Submachine Guns", "3P", "10/11/8/—/—", "3(L)", 840, modes="SA/BF", ammo="32(c)"),
    _w("FN P93 Praetor", "Submachine Guns", "4P", "9/12/7/—/—", "4(L)", 925, modes="SA/BF/FA", ammo="50(c)"),
    _w("HK-227", "Submachine Guns", "3P", "10/11/8/—/—", "3(L)", 825, modes="SA/BF", ammo="28(c)", desc="Smartgun system, retractable stock."),
    _w("Ingram Smartgun XI", "Submachine Guns", "3P", "11/9/6/—/—", "3(L)", 750, modes="SA/BF", ammo="32(c)", desc="Smartgun system and gas vent."),
    _w("SCK Model 100", "Submachine Guns", "3P", "10/10/7/—/—", "3(L)", 725, modes="SA/BF", ammo="30(c)", desc="Internal smartgun system."),
    _w("Uzi IV", "Submachine Guns", "3P", "8/8/7/—/—", "2(L)", 455, modes="SA/BF/FA", ammo="24(c)", desc="Laser sight."),
    # --- Shotguns (p. 256) ---
    _w("Defiance T-250", "Shotguns", "4P", "7/10/6/—/—", "2(L)", 330, modes="SS/SA", ammo="5(m)"),
    _w("Mossberg CMDT", "Shotguns", "4P", "4/11/7/—/—", "4(L)", 700, modes="SA/BF", ammo="10(c)"),
    _w("PJSS Model 55", "Shotguns", "4P", "3/12/8/—/—", "5(L)", 325, modes="SA/BF", ammo="2(b)", desc="Double barrel; Burst Fire fires both barrels."),
    _w("Remington Roomsweeper", "Shotguns", "5P", "9/8/4/—/—", "2(L)", 325, modes="SA", ammo="8(m)", desc="Short-barrel shotgun."),
    # --- Rifles (p. 258) ---
    _w("AK-97", "Assault Rifles", "5P", "4/11/9/7/1", "2(L)", 2100, modes="SA/BF/FA", ammo="38(c)"),
    _w("Ares Alpha", "Assault Rifles", "4P", "4/10/9/7/2", "5(L)", 3400, modes="SA/BF/FA", ammo="42(c)",
       desc="Smartgun system; underbarrel grenade launcher (AR 4/10/6/2/—, 6(c), fires minigrenades)."),
    _w("Colt M23", "Assault Rifles", "4P", "5/8/8/8/4", "2(L)", 5100, modes="SA/BF/FA", ammo="40(c)"),
    _w("FN-HAR", "Assault Rifles", "5P", "3/11/10/6/1", "3(L)", 2100, modes="SA/BF/FA", ammo="35(c)"),
    _w("Yamaha Raiden", "Assault Rifles", "4P", "4/11/10/7/2", "5(L)", 3200, modes="SA/BF/FA", ammo="60(c)",
       desc="Smartgun system; underbarrel grenade launcher (AR 4/11/7/1/—, 4(c)) and underbarrel shotgun (4P, SS/SA, AR 7/9/8/—/—, 2(b))."),
    _w("Ares Desert Strike", "Sniper Rifles", "5P", "3/10/10/10/10", "4(I)", 11000, modes="SA/BF/FA", ammo="14(c)"),
    _w("Cavalier Arms Crockett EBR", "Sniper Rifles", "5P", "3/8/11/8/8", "5(I)", 9050, modes="SA/BF", ammo="20(c)"),
    _w("Ranger Arms SM-5", "Sniper Rifles", "5P", "3/6/9/11/12", "5(I)", 13200, modes="SA", ammo="15(c)"),
    _w("Remington 900", "Sniper Rifles", "5P", "2/7/10/12/11", "3(L)", 12000, modes="SA", ammo="5(m)"),
    _w("Ruger 101", "Sniper Rifles", "5P", "2/6/10/12/11", "2(L)", 11100, modes="SA", ammo="8(m)"),
    _w("Barret Model 122", "Sniper Rifles", "6P", "1/8/11/16/14", "6(I)", 15200, modes="SA", ammo="10(c)"),
    # --- Machine guns ---
    _w("Ingram Valiant", "Machine Guns", "4P", "2/11/12/7/3", "4(L)", 4175, modes="SA/BF/FA", ammo="50(c)", desc="Or 100-round belt."),
    _w("Stoner-Ares M202", "Machine Guns", "5P", "1/10/11/7/6", "4(L)", 6900, modes="SA/BF/FA", ammo="50(c)", desc="Or 100-round belt."),
    _w("RPK HMG", "Machine Guns", "6P", "1/10/12/8/7", "5(L)", 8000, modes="SA/BF/FA", ammo="50(c)", desc="Or 100-round belt."),
    _w("Panther XXL", "Machine Guns", "7P", "1/9/12/8/6", "6(I)", 10000, modes="SA", ammo="15(c)", ammo_class="Cannon",
       desc="Assault cannon; uses assault cannon rounds only.", skill="Exotic Weapons", spec="Assault Cannon"),
    # --- Special weapons (Exotic) ---
    _w("Ares S-III Super Squirt", "Special Weapons", "Special", "8/12/9/—/—", "3(L)", 560, modes="SS", ammo="20(c)",
       spec="Super Squirt", desc="DMSO gel packs deliver a Contact-vector toxin; no damage of its own."),
    _w("Parashield DART Pistol", "Special Weapons", "1P", "9/10/8/—/—", "2", 510, modes="SS", ammo="5(c)",
       spec="Dart Guns", desc="Injection darts; deliver a toxin or drug on a hit."),
    _w("Parashield DART Rifle", "Special Weapons", "1P", "5/8/11/3/—", "3", 710, modes="SS", ammo="6(m)",
       spec="Dart Guns", desc="Injection darts; imaging scope."),
    # --- Launchers (p. 259) ---
    _w("Ares Antioch II", "Launchers", "Grenade", "—/6/8/6/5", "3(I)", 5900, modes="SS", ammo="8(m)", ammo_class="Grenade",
       desc="Grenade launcher with smartgun system."),
    _w("ArmTech MGL-6", "Launchers", "Grenade", "—/8/8/3/—", "4(I)", 1800, modes="SA", ammo="6(c)", ammo_class="Grenade"),
    _w("ArmTech MGL-12", "Launchers", "Grenade", "—/8/9/6/2", "4(I)", 5000, modes="SA", ammo="12(c)", ammo_class="Grenade"),
    _w("Aztechnology Striker", "Launchers", "Missile", "—/4/10/9/6", "5(I)", 7000, modes="SS", ammo="1(ml)", ammo_class="Rocket"),
    _w("Onotari Interceptor", "Launchers", "Missile", "—/5/9/10/8", "5(I)", 9000, modes="SS", ammo="2(ml)", ammo_class="Rocket"),
]

# Ammunition sold per 10 rounds (or per item for bow/crossbow ammo).
AMMO = []
for _cls, (_label, _av, _cost) in AMMO_CLASSES.items():
    for _t, _m in AMMO_TYPES.items():
        if _cls in ("Taser", "Dart", "Cannon") and _t != "Regular":
            continue
        AMMO.append({
            "name": f"{_t} rounds ({_label})" if _cls not in ("Taser", "Dart", "Cannon") else f"{_label} rounds",
            "cat": "Ammo & Explosives", "sub": "Ammunition", "ammo_for": _cls,
            "ammo_type": _t, "rounds": 10, "avail": _av,
            "cost": round(_cost * _m["mult"]),
            "desc": (_m["note"] + " Box of 10.") if _cls not in ("Dart",) else "Box of 10 darts; the toxin is bought separately.",
        })
AMMO += [
    {"name": "Arrow", "cat": "Ammo & Explosives", "sub": "Ammunition", "ammo_for": "Arrow", "ammo_type": "Regular",
     "rounds": 1, "rating": (1, 14), "avail": "(R/3)", "cost": "R*2", "desc": "Rating must match the bow."},
    {"name": "Injection Arrow", "cat": "Ammo & Explosives", "sub": "Ammunition", "ammo_for": "Arrow", "ammo_type": "Injection",
     "rounds": 1, "rating": (1, 14), "avail": "4", "cost": "R*20", "desc": "Delivers a dose of toxin or drug."},
    {"name": "Bolt", "cat": "Ammo & Explosives", "sub": "Ammunition", "ammo_for": "Bolt", "ammo_type": "Regular",
     "rounds": 1, "avail": "2", "cost": 5},
    {"name": "Injection Bolt", "cat": "Ammo & Explosives", "sub": "Ammunition", "ammo_for": "Bolt", "ammo_type": "Injection",
     "rounds": 1, "avail": "4", "cost": 50, "desc": "Delivers a dose of toxin or drug."},
]


def _ex(name, sub, gz, close, near, blast, avail, cost, **kw):
    d = {"name": name, "cat": "Ammo & Explosives", "sub": sub, "dv_gz": gz, "dv_close": close,
         "dv_near": near, "blast": blast, "avail": avail, "cost": cost, "consumable": True,
         "skill": "Athletics", "spec": "Throwing", "ar": "8/8/4/—/—"}
    d.update(kw)
    return d


# Grenades are thrown with Athletics (or fired as minigrenades from a
# launcher); rockets and missiles need a launcher.
EXPLOSIVES = [
    _ex("Stun Grenade", "Grenades", "10S", "8S", "6S", "15m", "4(L)", 100, ammo_for="Grenade"),
    _ex("Fragmentation Grenade", "Grenades", "16P", "12P", "8P", "20m", "4(I)", 150, ammo_for="Grenade"),
    _ex("High-Explosive Grenade", "Grenades", "16P", "10P", "4P", "15m", "4(I)", 150, ammo_for="Grenade"),
    _ex("Gas Grenade", "Grenades", "—", "—", "—", "—", "4(I)", 50, ammo_for="Grenade",
        desc="50¥ plus 20 doses of the chosen gas; see Gas Attacks."),
    _ex("Smoke/Thermal Smoke Grenade", "Grenades", "—", "—", "—", "—", "4(I)", 50, ammo_for="Grenade",
        desc="Blocks normal (or thermographic) vision in the cloud."),
    _ex("Flash-Pak", "Grenades", "Blinded III", "Blinded II", "Blinded I", "10m", "4(L)", 125, ammo_for="Grenade",
        desc="Inflicts the Blinded status instead of damage."),
    _ex("Anti-Vehicle Rocket", "Rockets & Missiles", "12P", "8P", "4P", "10m", "5(I)", 2800, ammo_for="Rocket",
        skill="Exotic Weapons", spec="Launchers", ar=""),
    _ex("Fragmentation Rocket", "Rockets & Missiles", "16P", "12P", "8P", "30m", "5(I)", 2000, ammo_for="Rocket",
        skill="Exotic Weapons", spec="Launchers", ar=""),
    _ex("High-Explosive Rocket", "Rockets & Missiles", "16P", "10P", "4P", "20m", "5(I)", 2100, ammo_for="Rocket",
        skill="Exotic Weapons", spec="Launchers", ar=""),
    _ex("Gas Rocket", "Rockets & Missiles", "—", "—", "—", "—", "4(I)", 750, ammo_for="Rocket",
        skill="Exotic Weapons", spec="Launchers", ar="", desc="750¥ plus 100 doses of payload."),
    _ex("Smoke/Thermal Smoke Rocket", "Rockets & Missiles", "—", "—", "—", "—", "4(I)", 1200, ammo_for="Rocket",
        skill="Exotic Weapons", spec="Launchers", ar=""),
    {"name": "Explosive Package", "cat": "Ammo & Explosives", "sub": "Conventional Explosives", "rating": (1, 20),
     "avail": "4(I)", "cost": "R*(10 if R<=3 else 50 if R<=6 else 100 if R<=9 else 250 if R<=12 else 500 if R<=15 else 1000 if R<=18 else 5000)",
     "consumable": True, "desc": "Plastic or foam explosive, used with Engineering (Demolitions). The core book lists no Availability for packages; grenade Availability is used."},

]

WEAPON_ACCESSORIES = [
    {"name": n, "cat": "Weapon Accessories", "sub": "Accessories", "mount": m, "avail": a, "cost": c, "desc": d}
    for n, m, a, c, d in [
        ("Airburst Link", "—", "3", 600, "Air-bursts grenades over the target; reduces scatter."),
        ("Bipod", "Under", "1", 200, "Steadies the weapon when deployed."),
        ("Concealable Holster", "—", "1", 150, "Raises the pistol's concealability."),
        ("Gas-Vent System", "Barrel", "3", 500, "Recoil compensation."),
        ("Gyro Mount", "Under", "3", 1400, "Harness-mounted stabiliser for heavy weapons."),
        ("Hidden Arm Slide", "—", "2", 350, "Slides a hold-out or light pistol into your hand."),
        ("Imaging Scope", "Top", "1", 350, "Scope with vision enhancements."),
        ("Laser Sight", "Top or Under", "1", 125, "+1 Attack Rating at Close and Near."),
        ("Periscope", "Top", "2", 70, "Shoot around corners."),
        ("Quick-Draw Holster", "—", "2", 175, "Faster drawing."),
        ("Shock Pad", "—", "2", 50, "Recoil pad for rifles and shotguns."),
        ("Silencer/Suppressor", "Barrel", "4", 500, "Muffles shots."),
        ("Smart Firing Platform", "Under", "5", 2500, "Drone-like platform that fires the weapon."),
        ("Smartgun System, Internal", "—", "1(L)", 500, "Integrated smartgun; +500¥ added to the weapon."),
        ("Smartgun System, External", "Top or Under", "2(L)", 200, "Smartgun adapter."),
        ("Spare Clip", "—", "2", 5, "Extra empty clip."),
        ("Speed Loader", "—", "1", 25, "Reloads a revolver quickly."),
        ("Tripod", "Under", "2", 500, "Stable firing platform."),
    ]
]

ARMOR = [
    {"name": n, "cat": "Armor", "sub": s, "dr": dr, "capacity": cap, "avail": a, "cost": c, "desc": d}
    for n, s, dr, cap, a, c, d in [
        ("Synthleather Jacket", "Armor", 1, 3, "1", 300, ""),
        ("Actioneer Business Clothes", "Armor", 2, 6, "2", 1500, "Armored business suit."),
        ("Armor Clothing", "Armor", 2, 4, "2", 500, "Everyday clothes with armor weave."),
        ("Armor Jacket", "Armor", 4, 8, "2", 1000, ""),
        ("Armor Vest", "Armor", 3, 6, "2", 750, ""),
        ("Chameleon Suit", "Armor", 2, 4, "4(I)", 2000, "Ruthenium polymer suit that blends with its surroundings."),
        ("Full Body Armor", "Armor", 5, 10, "4(L)", 2000, "Military-grade armor."),
        ("Full Body Armor Helmet", "Helmets & Shields", 2, 6, "4(L)", 500, "Helmet for full body armor."),
        ("Lined Coat", "Armor", 3, 7, "2", 900, ""),
        ("Urban Explorer Jumpsuit", "Armor", 3, 6, "2", 800, ""),
        ("Helmet", "Helmets & Shields", 1, 4, "1", 200, ""),
        ("Ballistic Shield", "Helmets & Shields", 2, 2, "4", 900, "Bash attack: Exotic Weapons, 2S, AR 4."),
        ("Riot Shield", "Helmets & Shields", 2, 2, "4", 1200, "Electrified bash: Exotic Weapons, 4S(e), AR 4."),
    ]
] + [
    {"name": "Clothing", "cat": "Armor", "sub": "Clothing", "dr": 0, "avail": "1", "cost": 50,
     "desc": "From 10¥ to 10,000¥ depending on style; edit the price."},
    {"name": "Electrochromic Feature", "cat": "Armor", "sub": "Clothing", "avail": "1", "cost": 75, "mod": True},
    {"name": "Feedback Feature", "cat": "Armor", "sub": "Clothing", "avail": "2", "cost": 150, "mod": True},
    {"name": "Chemical Protection", "cat": "Armor", "sub": "Armor Mods", "capacity_cost": "R", "rating": (1, 6), "avail": "3", "cost": "R*250", "mod": True},
    {"name": "Chemical Seal", "cat": "Armor", "sub": "Armor Mods", "capacity_cost": 6, "avail": "5", "cost": 3000, "mod": True},
    {"name": "Cold Resistance", "cat": "Armor", "sub": "Armor Mods", "capacity_cost": "R", "rating": (1, 6), "avail": "3", "cost": "R*250", "mod": True},
    {"name": "Fire Resistance", "cat": "Armor", "sub": "Armor Mods", "capacity_cost": "R", "rating": (1, 6), "avail": "3", "cost": "R*250", "mod": True},
    {"name": "Electricity Resistance", "cat": "Armor", "sub": "Armor Mods", "capacity_cost": "R", "rating": (1, 6), "avail": "3", "cost": "R*250", "mod": True},
]

COMMLINKS = [
    {"name": n, "cat": "Electronics", "sub": "Commlinks", "device_rating": dr, "data_processing": dp, "firewall": fw,
     "program_slots": slots, "avail": a, "cost": c}
    for n, dr, dp, fw, slots, a, c in [
        ("Meta Link", 1, 1, 0, 0, "2", 100), ("Sony Emperor", 2, 1, 1, 1, "2", 700),
        ("Renraku Sensei", 3, 2, 0, 1, "2", 1000), ("Erika Elite", 4, 2, 1, 2, "2", 2500),
        ("Hermes Ikon", 5, 3, 0, 2, "3", 5000), ("Transys Avalon", 6, 3, 1, 3, "3", 8000),
    ]
]
CYBERDECKS = [
    {"name": n, "cat": "Cyberdecks & Software", "sub": "Cyberdecks", "device_rating": dr, "attack": at, "sleaze": sl,
     "program_slots": slots, "avail": a, "cost": c,
     "desc": "Attack/Sleaze from the deck; Data Processing/Firewall come from your cyberjack or commlink."}
    for n, dr, at, sl, slots, a, c in [
        ("Erika MCD-6", 1, 4, 3, 2, "3(I)", 24750), ("Spinrad Falcon", 2, 5, 4, 4, "3(I)", 61500),
        ("MCT 360", 3, 6, 5, 6, "3(I)", 107000), ("Renraku Kitsune", 4, 7, 6, 8, "4(I)", 95000),
        ("Shiawase Cyber-6", 5, 8, 7, 10, "5(I)", 172500), ("Fairlight Excalibur", 6, 9, 8, 12, "8(I)", 410600),
    ]
]


def _g(name, cat, sub, avail, cost, desc="", **kw):
    d = {"name": name, "cat": cat, "sub": sub, "avail": avail, "cost": cost}
    if desc:
        d["desc"] = desc
    d.update(kw)
    return d


ELECTRONICS = [
    _g("AR Gloves", "Electronics", "Accessories", "1", 150, device_rating=3),
    _g("Biometric Reader", "Electronics", "Accessories", "2", 200, device_rating=3),
    _g("Electronic Paper", "Electronics", "Accessories", "1", 5, device_rating=1),
    _g("Printer", "Electronics", "Accessories", "1", 25, device_rating=3),
    _g("Satellite Link", "Electronics", "Accessories", "3", 500, device_rating=4),
    _g("Simrig", "Electronics", "Accessories", "4", 1000, device_rating=3),
    _g("Subvocal Mic", "Electronics", "Accessories", "2", 50, device_rating=3),
    _g("Trid Projector", "Electronics", "Accessories", "1", 200, device_rating=3),
    _g("Trodes", "Electronics", "Accessories", "1", 70, device_rating=3, desc="Electrode net for DNI without implants."),
    _g("Standard RFID Tags (10)", "Electronics", "RFID Tags", "1", 1, device_rating=1),
    _g("Datachip (10)", "Electronics", "RFID Tags", "1", 5, device_rating=1),
    _g("Security/Stealth Tags (10)", "Electronics", "RFID Tags", "2", 10, device_rating=3),
    _g("Sensor Tags (10)", "Electronics", "RFID Tags", "2", 40, device_rating=2),
    _g("Bug Scanner", "Electronics", "Countermeasures", "3", 200),
    _g("Data Tap", "Electronics", "Countermeasures", "2", 300),
    _g("Headjammer", "Electronics", "Countermeasures", "5(I)", "R*150", rating=(1, 6)),
    _g("Jammer, Area", "Electronics", "Countermeasures", "4(L)", "R*200", rating=(1, 6), desc="Noise equal to its rating in a sphere."),
    _g("Jammer, Directional", "Electronics", "Countermeasures", "4(L)", "R*200", rating=(1, 6), desc="Noise equal to its rating in a cone."),
    _g("Micro-Transceiver", "Electronics", "Countermeasures", "1", 100, device_rating=2),
    _g("Tag Eraser", "Electronics", "Countermeasures", "3", 450, desc="Burns out RFID tags and unshielded electronics."),
    _g("White Noise Generator", "Electronics", "Countermeasures", "3", "R*50", rating=(1, 6)),
    # Software
    _g("Agent", "Cyberdecks & Software", "Software", "R", "R*1500", rating=(1, 6)),
    _g("Autosoft", "Cyberdecks & Software", "Software", "R", "R*500", rating=(1, 6), desc="Drone skill program."),
    _g("Cyberprogram, Basic", "Cyberdecks & Software", "Software", "1", 60),
    _g("Cyberprogram, Hacking", "Cyberdecks & Software", "Software", "4", 250),
    _g("Datasoft", "Cyberdecks & Software", "Software", "2", 120),
    _g("Mapsoft", "Cyberdecks & Software", "Software", "2", 100),
    _g("Shopsoft", "Cyberdecks & Software", "Software", "2", 150),
    _g("Activesoft", "Cyberdecks & Software", "Skillsofts", "4", "R*5000", rating=(1, 6), desc="Needs skillwires."),
    _g("Knowsoft", "Cyberdecks & Software", "Skillsofts", "2", 2500, desc="Needs a skilljack."),
    _g("Linguasoft", "Cyberdecks & Software", "Skillsofts", "1", "R*1500", rating=(1, 4), desc="Needs a skilljack."),
    _g("Tutorsoft", "Cyberdecks & Software", "Skillsofts", "(R/3)", "R*400", rating=(1, 6)),
    # ID & credit
    _g("Credstick, Standard", "ID & Credit", "Credsticks", "1", 5, desc="Holds up to 5,000¥."),
    _g("Credstick, Silver", "ID & Credit", "Credsticks", "1", 20, desc="Holds up to 20,000¥."),
    _g("Credstick, Gold", "ID & Credit", "Credsticks", "2", 100, desc="Holds up to 100,000¥."),
    _g("Credstick, Platinum", "ID & Credit", "Credsticks", "3", 500, desc="Holds up to 500,000¥."),
    _g("Credstick, Ebony", "ID & Credit", "Credsticks", "5", 1000, desc="Holds up to 1,000,000¥."),
    _g("Fake SIN", "ID & Credit", "Identification", "4(I)", "R*2500", rating=(1, 6)),
    _g("Fake License", "ID & Credit", "Identification", "4(I)", "R*200", rating=(1, 6), desc="Attach to a SIN; name what it licenses."),
    # Tools
    _g("Tool Kit", "Tools & Sensors", "Tools", "1", 500, desc="Portable kit for one skill."),
    _g("Tool Shop", "Tools & Sensors", "Tools", "4", 5000),
    _g("Tool Facility", "Tools & Sensors", "Tools", "7", 50000),
    # Optical and imaging
    _g("Binoculars", "Tools & Sensors", "Optical & Imaging", "1", "R*50", rating=(1, 3), capacity="R"),
    _g("Binoculars, Optical", "Tools & Sensors", "Optical & Imaging", "1", 50),
    _g("Camera", "Tools & Sensors", "Optical & Imaging", "1", "R*100", rating=(1, 6), capacity="R"),
    _g("Micro-Camera", "Tools & Sensors", "Optical & Imaging", "1", 100, capacity=1),
    _g("Contacts", "Tools & Sensors", "Optical & Imaging", "2", "R*200", rating=(1, 3), capacity="R"),
    _g("Endoscope", "Tools & Sensors", "Optical & Imaging", "3", 250),
    _g("Glasses", "Tools & Sensors", "Optical & Imaging", "1", "R*100", rating=(1, 4), capacity="R"),
    _g("Goggles", "Tools & Sensors", "Optical & Imaging", "1", "R*50", rating=(1, 6), capacity="R"),
    _g("Imaging Scope (device)", "Tools & Sensors", "Optical & Imaging", "1", 300, capacity=3),
    _g("Monocle", "Tools & Sensors", "Optical & Imaging", "1", "R*120", rating=(1, 4), capacity="R"),
    _g("Mage Sight Goggles", "Tools & Sensors", "Optical & Imaging", "5", 3000, desc="Lets a spellcaster see (and cast) around corners."),
    _g("Periscope (handheld)", "Tools & Sensors", "Optical & Imaging", "2", 50),
    _g("Flare Compensation", "Tools & Sensors", "Vision Enhancements", "1", 250, capacity_cost=1, mod=True),
    _g("Image Link", "Tools & Sensors", "Vision Enhancements", "1", 25, capacity_cost=1, mod=True),
    _g("Low-Light Vision", "Tools & Sensors", "Vision Enhancements", "2", 500, capacity_cost=1, mod=True),
    _g("Smartlink", "Tools & Sensors", "Vision Enhancements", "2", 2000, capacity_cost=2, mod=True,
       desc="Links to a smartgun system."),
    _g("Thermographic Vision", "Tools & Sensors", "Vision Enhancements", "2", 500, capacity_cost=1, mod=True),
    _g("Ultrasound Link", "Tools & Sensors", "Vision Enhancements", "1", 300, capacity_cost=1, mod=True),
    _g("Vision Enhancement", "Tools & Sensors", "Vision Enhancements", "1", 500, capacity_cost=2, mod=True),
    _g("Vision Magnification", "Tools & Sensors", "Vision Enhancements", "1", 250, capacity_cost=1, mod=True),
    # Audio
    _g("Directional Microphone", "Tools & Sensors", "Auditory Devices", "2", "R*50", rating=(1, 6), capacity="R"),
    _g("Earbuds", "Tools & Sensors", "Auditory Devices", "1", "R*50", rating=(1, 3), capacity="R"),
    _g("Headphones", "Tools & Sensors", "Auditory Devices", "1", "R*50", rating=(1, 6), capacity="R"),
    _g("Laser Microphone", "Tools & Sensors", "Auditory Devices", "2", "R*100", rating=(1, 6), capacity="R"),
    _g("Omni-Directional Microphone", "Tools & Sensors", "Auditory Devices", "1", "R*50", rating=(1, 6), capacity="R"),
    _g("Audio Enhancement", "Tools & Sensors", "Audio Enhancements", "1", 500, capacity_cost=1, mod=True,
       desc="+1 die on aural Perception tests."),
    _g("Select Sound Filter", "Tools & Sensors", "Audio Enhancements", "3", "R*250", rating=(1, 3), capacity_cost="R", mod=True),
    _g("Spatial Recognizer", "Tools & Sensors", "Audio Enhancements", "2", 1000, capacity_cost=2, mod=True),
    # Sensors
    _g("Handheld Sensor Housing", "Tools & Sensors", "Sensors", "1", "R*100", rating=(1, 3), capacity="R"),
    _g("Wall-Mounted Sensor Housing", "Tools & Sensors", "Sensors", "1", "R*250", rating=(1, 6), capacity="R"),
    _g("Sensor Array", "Tools & Sensors", "Sensors", "3", "R*1000", rating=(2, 8)),
    _g("Single Sensor", "Tools & Sensors", "Sensors", "2", "R*100", rating=(1, 8), capacity_cost=1),
    # Security and breaking & entering
    _g("Lock", "Security & B&E", "Security Devices", "2", "R*10", rating=(1, 6)),
    _g("Maglock", "Security & B&E", "Security Devices", "3", "R*100", rating=(1, 6)),
    _g("Keypad", "Security & B&E", "Security Devices", "1", 50),
    _g("Card Reader", "Security & B&E", "Security Devices", "1", 50),
    _g("Biometric Lock Reader", "Security & B&E", "Security Devices", "2", 200),
    _g("Metal Restraints", "Security & B&E", "Restraints", "1", 20),
    _g("Plasteel Restraints", "Security & B&E", "Restraints", "2", 50),
    _g("Plastic Straps (10)", "Security & B&E", "Restraints", "1", 5),
    _g("Containment Manacles", "Security & B&E", "Restraints", "3", 250),
    _g("Autopicker", "Security & B&E", "Breaking & Entering", "4", "R*500", rating=(1, 6)),
    _g("Cellular Glove Molder", "Security & B&E", "Breaking & Entering", "6(I)", "R*500", rating=(1, 4)),
    _g("Chisel/Wrecking Bar", "Security & B&E", "Breaking & Entering", "1", 20),
    _g("Keycard Copier", "Security & B&E", "Breaking & Entering", "4(I)", "R*600", rating=(1, 6)),
    _g("Lockpick Set", "Security & B&E", "Breaking & Entering", "2", 250),
    _g("Maglock Passkey", "Security & B&E", "Breaking & Entering", "3(I)", "R*2000", rating=(1, 4)),
    _g("Miniwelder", "Security & B&E", "Breaking & Entering", "1", 250),
    _g("Miniwelder Fuel Canister", "Security & B&E", "Breaking & Entering", "1", 80),
    _g("Monofilament Chainsaw", "Security & B&E", "Breaking & Entering", "3", 500),
    _g("Sequencer", "Security & B&E", "Breaking & Entering", "4(I)", "R*250", rating=(1, 6)),
    _g("Glue Solvent", "Security & B&E", "Industrial Chemicals", "1", 90),
    _g("Glue Sprayer", "Security & B&E", "Industrial Chemicals", "1", 150),
    _g("Thermite Burning Bar", "Security & B&E", "Industrial Chemicals", "5(L)", 500),
    # Survival
    _g("Chemsuit", "Survival", "Survival Gear", "4", "R*150", rating=(1, 6)),
    _g("Climbing Gear", "Survival", "Survival Gear", "1", 200, desc="Gain 1 Edge when starting a climb."),
    _g("Diving Gear", "Survival", "Survival Gear", "3", 2000),
    _g("Flashlight", "Survival", "Survival Gear", "1", 25),
    _g("Gas Mask", "Survival", "Survival Gear", "1", 200),
    _g("Gecko Tape Gloves", "Survival", "Survival Gear", "3", 250),
    _g("Hazmat Suit", "Survival", "Survival Gear", "3", 3000),
    _g("Light Stick", "Survival", "Survival Gear", "1", 25),
    _g("Magnesium Torch/Flare", "Survival", "Survival Gear", "1", 5, consumable=True),
    _g("Microflare Launcher", "Survival", "Survival Gear", "1", 175),
    _g("Microflares", "Survival", "Survival Gear", "1", 25),
    _g("Rappelling Gloves", "Survival", "Survival Gear", "1", 50),
    _g("Respirator", "Survival", "Survival Gear", "1", "R*50", rating=(1, 6)),
    _g("Survival Kit", "Survival", "Survival Gear", "2", 200),
    _g("Grapple Gun", "Survival", "Grapple Gun", "3", 500),
    _g("Microwire (100 m)", "Survival", "Grapple Gun", "2", 50),
    _g("Myomeric Rope (10 m)", "Survival", "Grapple Gun", "4", 200),
    _g("Standard Rope (100 m)", "Survival", "Grapple Gun", "1", 50),
    _g("Stealth Rope (100 m)", "Survival", "Grapple Gun", "3(I)", 85),
    _g("Catalyst Stick", "Survival", "Grapple Gun", "3(I)", 120),
    # Medical / biotech
    _g("Biomonitor", "Medical", "Biotech", "2", 300),
    _g("DocWagon Contract, Basic", "Medical", "DocWagon", "1", 5000, desc="Yearly price (500¥/month)."),
    _g("DocWagon Contract, Gold", "Medical", "DocWagon", "1", 25000, desc="Yearly price (2,500¥/month)."),
    _g("DocWagon Contract, Platinum", "Medical", "DocWagon", "1", 50000, desc="Yearly price (5,000¥/month)."),
    _g("DocWagon Contract, Super-Platinum", "Medical", "DocWagon", "1", 100000),
    _g("Disposable Syringe", "Medical", "Biotech", "2", 10),
    _g("Medkit", "Medical", "Biotech", "3", "R*250", rating=(1, 6), medkit=True,
       desc="Counts as a Biotech kit. Adds its rating to First Aid tests; needs supplies after use."),
    _g("Medkit Supplies", "Medical", "Biotech", "1", 100, consumable=True, desc="Refills a medkit."),
    _g("Antidote Patch", "Medical", "Slap Patches", "3", 150, consumable=True, desc="Removes the Poisoned status."),
    _g("Chem Patch", "Medical", "Slap Patches", "3", 200, consumable=True),
    _g("Stim Patch", "Medical", "Slap Patches", "3", "R*25", rating=(1, 6), consumable=True,
       desc="Removes Stun boxes equal to its rating and the Dazed status; the Stun returns (+1) later."),
    _g("Tranq Patch", "Medical", "Slap Patches", "3", "R*R*10", rating=(1, 12), consumable=True,
       desc="Inflicts Stun damage equal to its rating, resisted by Body."),
    _g("Trauma Patch", "Medical", "Slap Patches", "3", 500, consumable=True,
       desc="Stabilises a patient with overflow damage."),
]

# --- Cyberware -------------------------------------------------------------
# effects: attribute bonuses (Body, Agility...), "dr" (Defense Rating),
# "init_dice", "minor" (extra Minor Actions), "phys_boxes", "soak" (extra
# Body for damage resistance), "unarmed_dv"/"unarmed_ar".


def _c(name, sub, ess, avail, cost, capacity=None, desc="", **kw):
    d = {"name": name, "cat": "Cyberware", "sub": sub, "essence": ess, "avail": avail, "cost": cost,
         "implant": True}
    if capacity is not None:
        d["capacity_cost" if str(capacity).startswith("[") else "capacity"] = str(capacity).strip("[]")
    if desc:
        d["desc"] = desc
    d.update(kw)
    return d


CYBERWARE = [
    # Cyberjacks (p. 284)
    *[_c(f"Cyberjack {r}", "Headware", e, a, c, data_processing=dp, firewall=fw, matrix_init=mi,
         desc="Provides Data Processing and Firewall for a cyberdeck, works as a datajack.")
      for r, dp, fw, mi, a, e, c in [
          (1, 4, 3, 1, "3(L)", 1, 45000), (2, 5, 4, 1, "3(L)", 1.5, 65000), (3, 6, 5, 2, "3(L)", 2, 80000),
          (4, 7, 6, 2, "4(L)", 2.3, 95000), (5, 8, 7, 3, "5(L)", 2.6, 140000), (6, 9, 8, 3, "6(L)", 3, 210000)]],
    # Headware
    _c("Commlink (headware)", "Headware", 0.2, "2", 2000, "[2]", desc="Implanted commlink; add the commlink's price."),
    _c("Control Rig", "Headware", "R", "4(L)", "R*R*30000", rating=(1, 3), control_rig=True,
       desc="When jumped in: rating as dice bonus on vehicle tests and +1 Edge."),
    _c("Cortex Bomb, Kink", "Headware", 0, "6(I)", 10000, "[1]"),
    _c("Cortex Bomb, Microbomb", "Headware", 0, "6(I)", 25000, "[2]"),
    _c("Cortex Bomb, Area", "Headware", 0, "6(I)", 40000, "[3]"),
    _c("Cyberdeck (headware)", "Headware", 0.4, "4(L)", 5000, "[4]", desc="Implanted deck; add the deck's price."),
    _c("Datajack", "Headware", 0.1, "2", 1000, desc="Direct neural interface port."),
    _c("Datalock", "Headware", 0.1, "4", "R*1000", rating=(1, 12)),
    _c("Olfactory Booster", "Headware", 0.2, "3", "R*4000", rating=(1, 3)),
    _c("Simrig (headware)", "Headware", 0.2, "4(L)", 4000),
    _c("Skilljack", "Headware", "R*0.1", "4", "R*20000", rating=(1, 6), desc="Runs knowsofts and linguasofts."),
    _c("Taste Booster", "Headware", 0.2, "3", "R*3000", rating=(1, 3)),
    _c("Tooth Compartment", "Headware", 0, "4", 800),
    _c("Ultrasound Sensor", "Headware", 0.3, "4", 36000, "[2]"),
    _c("Voice Modulator", "Headware", 0.2, "4(L)", "R*5000", rating=(1, 3)),
    # Eyeware (p. 285)
    *[_c(f"Cybereyes {r}", "Eyeware", e, a, c, cap, desc="Basic cybereyes with image link and camera.")
      for r, e, cap, a, c in [(1, 0.1, 1, "2", 1000), (2, 0.2, 4, "2", 4000), (3, 0.3, 8, "3", 6000),
                               (4, 0.4, 12, "3", 10000), (5, 0.5, 16, "3", 16000)]],
    _c("Flare Compensation (eye)", "Eyeware", 0.1, "2", 1000, "[1]"),
    _c("Image Link (eye)", "Eyeware", 0.1, "2", 800),
    _c("Low-Light Vision (eye)", "Eyeware", 0.1, "2", 1500, "[2]", vision="Low-light"),
    _c("Ocular Drone", "Eyeware", 0.3, "3", 6000, "[6]"),
    _c("Retinal Duplication", "Eyeware", 0.1, "5(I)", "R*20000", "[1]", rating=(1, 6)),
    _c("Smartlink (eye)", "Eyeware", 0.2, "3(L)", 4000, "[3]", smartlink=True),
    _c("Thermographic Vision (eye)", "Eyeware", 0.1, "2", 2000, "[2]", vision="Thermographic"),
    _c("Vision Enhancement (eye)", "Eyeware", 0.1, "3", 4000, "[2]"),
    _c("Vision Magnification (eye)", "Eyeware", 0.1, "3", 2000, "[2]"),
    # Earware (p. 286)
    *[_c(f"Cyberears {r}", "Earware", e, a, c, cap)
      for r, e, cap, a, c in [(1, 0.1, 1, "2", 1000), (2, 0.2, 4, "2", 3000), (3, 0.3, 8, "3", 4500),
                               (4, 0.4, 12, "3", 7500), (5, 0.5, 16, "3", 11000)]],
    _c("Audio Enhancement (ear)", "Earware", 0.1, "2", 4000, "[1]"),
    _c("Balance Augmenter", "Earware", 0.1, "3", 8000, "[4]", desc="+1 die on balance tests."),
    _c("Damper", "Earware", 0.1, "2", 2250, "[1]"),
    _c("Select Sound Filter (ear)", "Earware", 0.1, "4", "R*3500", "[R]", rating=(1, 6)),
    _c("Sound Link", "Earware", 0.1, "2", 1000),
    _c("Spatial Recognizer (ear)", "Earware", 0.1, "3", 4000, "[2]"),
    # Bodyware (p. 288)
    _c("Bone Lacing (Plastic)", "Bodyware", 0.5, "3(L)", 8000, soak=1, dr=1, unarmed_dv="3P", unarmed_ar=1),
    _c("Bone Lacing (Aluminum)", "Bodyware", 1, "4(L)", 18000, soak=2, dr=1, unarmed_dv="4P", unarmed_ar=2),
    _c("Bone Lacing (Titanium)", "Bodyware", 1.5, "6(L)", 30000, soak=2, dr=2, unarmed_dv="4P", unarmed_ar=3),
    _c("Dermal Plating", "Bodyware", "R*0.3", "4(L)", "R*4000", rating=(1, 4), dr="R"),
    _c("Fingertip Compartment", "Bodyware", 0.1, "2", 3000, "[1]"),
    _c("Grapple Gun (implant)", "Bodyware", 0.5, "3", 5000, "[4]"),
    _c("Internal Air Tank", "Bodyware", 0.25, "2", "R*4500", "[R]", rating=(1, 4)),
    _c("Muscle Replacement", "Bodyware", "R*0.7", "3(L)", "R*30000", rating=(1, 4), Strength="R", Agility="R"),
    _c("Reaction Enhancers", "Bodyware", "R*0.3", "4(L)", "R*15000", rating=(1, 4), Reaction="R"),
    _c("Skillwires", "Bodyware", "R*0.1", "4", "R*20000", rating=(1, 6)),
    _c("Smuggling Compartment", "Bodyware", 0.2, "3", 7500, "[2]"),
    _c("Wired Reflexes 1", "Bodyware", 1, "3(L)", 40000, Reaction=1, init_dice=1, minor=1),
    _c("Wired Reflexes 2", "Bodyware", 2, "3(L)", 150000, Reaction=2, init_dice=2, minor=2),
    _c("Wired Reflexes 3", "Bodyware", 3, "4(I)", 250000, Reaction=3, init_dice=3, minor=3),
    _c("Wired Reflexes 4", "Bodyware", 4, "6(I)", 400000, Reaction=4, init_dice=4, minor=4),
    # Cyberlimbs (p. 289) -- each adds 1 Physical box; basic attributes 2.
    *[_c(f"Cyber{n} ({kind})", "Cyberlimbs", e, a, c, cap, phys_boxes=1,
         desc="Basic cyberlimb (Physical attributes 2). Add attribute increases as accessories.")
      for n, e, a, (sc, scap), (oc, ocap) in [
          ("skull", 0.75, "5", (15000, 2), (10000, 4)), ("torso", 1.5, "4", (25000, 5), (20000, 10)),
          ("arm", 1, "4", (20000, 8), (15000, 15)), ("forearm", 0.45, "3", (12000, 5), (10000, 10)),
          ("hand", 0.25, "3", (6000, 2), (5000, 4)), ("leg", 1, "4", (20000, 10), (15000, 20)),
          ("lower leg", 0.45, "4", (12000, 6), (10000, 12)), ("foot", 0.25, "4", (6000, 2), (5000, 4))]
      for kind, c, cap in (("synthetic", sc, scap), ("obvious", oc, ocap))],
    _c("Cyberlimb Agility Increase", "Cyberlimb Accessories", 0, "R", "R*5000", "[R]", rating=(1, 4), limb_mod=True),
    _c("Cyberlimb Strength Increase", "Cyberlimb Accessories", 0, "R", "R*5000", "[R]", rating=(1, 4), limb_mod=True),
    _c("Cyberlimb Armor Increase", "Cyberlimb Accessories", 0, "R", "R*5000", "[R]", rating=(1, 4), limb_mod=True, dr="R"),
    _c("Cyberlimb Gyromount", "Cyberlimb Accessories", 0, "5(I)", 6000, "[8]", limb_mod=True),
    _c("Cyberlimb Slide", "Cyberlimb Accessories", 0, "5(L)", 3000, "[3]", limb_mod=True),
    _c("Cyberlimb Holster", "Cyberlimb Accessories", 0, "4", 2000, "[5]", limb_mod=True),
    _c("Hydraulic Jacks", "Cyberlimb Accessories", 0, "4", "R*2500", "[R]", rating=(1, 6), limb_mod=True),
    _c("Cyberlimb Smuggling Compartment", "Cyberlimb Accessories", 0, "2", 6000, "[5]", limb_mod=True),
    # Cyber implant weapons (p. 290)
    _c("Cyberjaw", "Implant Weapons", 0.1, "2", 1500, "[1]", weapon={"dv": "5P", "ar": "2/—/—/—/—", "skill": "Close Combat", "spec": "Unarmed Combat"}),
    _c("Hardening", "Implant Weapons", 0.1, "2", 2500, "[1]", weapon={"dv": "3P", "ar": "6/—/—/—/—", "skill": "Close Combat", "spec": "Unarmed Combat"}),
    _c("Shock Limb", "Implant Weapons", 0.25, "3", 5000, "[1]", weapon={"dv": "4S(e)", "ar": "5/—/—/—/—", "skill": "Close Combat", "spec": "Unarmed Combat"}),
    _c("Handblade", "Implant Weapons", 0.15, "4(I)", 2000, "[1]", weapon={"dv": "3P", "ar": "6/—/—/—/—", "skill": "Close Combat", "spec": "Blades"}),
    _c("Retractable Handblade", "Implant Weapons", 0.25, "4(I)", 2500, "[2]", weapon={"dv": "3P", "ar": "6/—/—/—/—", "skill": "Close Combat", "spec": "Blades"}),
    _c("Hand Razors", "Implant Weapons", 0.15, "3(I)", 1000, "[1]", weapon={"dv": "2P", "ar": "6/—/—/—/—", "skill": "Close Combat", "spec": "Blades"}),
    _c("Retractable Hand Razors", "Implant Weapons", 0.25, "3(I)", 1250, "[2]", weapon={"dv": "2P", "ar": "6/—/—/—/—", "skill": "Close Combat", "spec": "Blades"}),
    _c("Spurs", "Implant Weapons", 0.15, "4(I)", 3000, "[1]", weapon={"dv": "3P", "ar": "7/—/—/—/—", "skill": "Close Combat", "spec": "Blades"}),
    _c("Retractable Spurs", "Implant Weapons", 0.25, "4(I)", 5000, "[3]", weapon={"dv": "3P", "ar": "7/—/—/—/—", "skill": "Close Combat", "spec": "Blades"}),
    _c("Implant Hold-out Pistol Mount", "Implant Weapons", 0.1, "3(L)", 2000, "[2]", desc="Space for a hold-out; buy the gun separately."),
    _c("Implant Light Pistol Mount", "Implant Weapons", 0.25, "3(L)", 3000, "[4]"),
    _c("Implant Machine Pistol Mount", "Implant Weapons", 0.5, "4(L)", 3500, "[6]"),
    _c("Implant Heavy Pistol Mount", "Implant Weapons", 0.5, "4(L)", 4300, "[6]"),
    _c("Implant SMG Mount", "Implant Weapons", 1, "5(L)", 4800, "[8]"),
    _c("Implant Shotgun Mount", "Implant Weapons", 1.25, "5(L)", 8500, "[10]"),
    _c("Implant Grenade Launcher Mount", "Implant Weapons", 1.5, "6(I)", 24000, "[15]"),
    _c("External Clip Port", "Implant Weapons", 0.1, "1", 1000, "[1]"),
    _c("Implant Laser Sight", "Implant Weapons", 0.1, "1", 1000, "[1]"),
    _c("Implant Silencer/Suppressor", "Implant Weapons", 0.1, "4(I)", 1000, "[2]"),
]


def _b(name, ess, avail, cost, desc="", sub="Bioware", **kw):
    d = {"name": name, "cat": "Bioware", "sub": sub, "essence": ess, "avail": avail, "cost": cost, "implant": True}
    if desc:
        d["desc"] = desc
    d.update(kw)
    return d


BIOWARE = [
    _b("Adrenaline Pump", "R*0.75", "5(I)", "R*55000", rating=(1, 3),
       desc="When triggered: +rating to STR, AGI, REA, WIL and ignore wound modifiers for rating x 1D6 rounds."),
    _b("Bone Density Augmentation", "R*0.3", "4(L)", "R*5000", rating=(1, 4), soak="R",
       unarmed_dv="(3 if R<=2 else 4)P", unarmed_ar="R if R<2 else 2 if R<=3 else 3"),
    _b("Cat's Eyes", 0.1, "3", 4000, vision="Low-light"),
    _b("Enhanced Articulation", 0.2, "4", 30000, Agility=1),
    _b("Muscle Augmentation", "R*0.2", "4(L)", "R*31000", rating=(1, 4), Strength="R"),
    _b("Muscle Toner", "R*0.2", "4(L)", "R*32000", rating=(1, 4), Agility="R"),
    _b("Orthoskin", "R*0.25", "4(L)", "R*6000", rating=(1, 4), dr="R"),
    _b("Platelet Factories", 0.2, "4", 17000, desc="Reduce Physical damage of 2+ boxes by 1."),
    _b("Skin Pocket", 0.1, "4", 12000),
    _b("Suprathyroid Gland", 0.7, "5(L)", 140000, Agility=1, Body=1, Reaction=1, Strength=1,
       desc="+1 AGI, BOD, REA, STR; Lifestyle costs +25%.", lifestyle_mult=1.25),
    _b("Symbiotes", "R*0.2", "4", "R*3500", rating=(1, 4), heal_bonus="R",
       desc="+rating dice on healing tests; costs rating x 200¥/month in food below High lifestyle."),
    _b("Synthacardium", "R*0.1", "3", "R*30000", rating=(1, 3), desc="+rating dice on running, swimming and climbing."),
    _b("Tailored Pheromones", "R*0.2", "4(L)", "R*31000", rating=(1, 4), desc="+rating Charisma for Con and Influence in person."),
    _b("Toxin Extractor", "R*0.2", "4", "R*4800", rating=(1, 6)),
    _b("Tracheal Filter", "R*0.1", "4", "R*4500", rating=(1, 6)),
    _b("Cerebral Booster", "R*0.2", "5", "R*31500", sub="Cultured Bioware", rating=(1, 3), Logic="R"),
    _b("Damage Compensator", "R*0.1", "5(L)", "R*2000", sub="Cultured Bioware", rating=(1, 12), ignore_boxes="R",
       desc="Ignore this many damage boxes when working out wound modifiers."),
    _b("Mnemonic Enhancer", "R*0.1", "5", "R*9000", sub="Cultured Bioware", rating=(1, 3), memory_bonus="R"),
    _b("Pain Editor", 0.3, "5(I)", 48000, sub="Cultured Bioware",
       desc="While active: ignore wound modifiers, +1 WIL, -1 INT."),
    _b("Reflex Recorder", 0.1, "5", 14000, sub="Cultured Bioware", desc="+1 to one skill linked to a Physical attribute."),
    _b("Sleep Regulator", 0.1, "5", 12000, sub="Cultured Bioware"),
    _b("Synaptic Booster", "R*0.5", "5(L)", "R*95000", sub="Cultured Bioware", rating=(1, 3),
       Reaction="R", init_dice="R", minor="R"),
]

IMPLANT_GRADES = {
    "Standard": {"essence": 1.0, "cost": 1.0, "avail": 0},
    "Used": {"essence": 1.1, "cost": 0.5, "avail": -1},
    "Alphaware": {"essence": 0.8, "cost": 1.2, "avail": 1},
    "Betaware": {"essence": 0.7, "cost": 1.5, "avail": 2},
    "Deltaware": {"essence": 0.5, "cost": 2.5, "avail": 3},
}

MAGIC_GEAR = [
    _g("Enchanting Focus", "Magic", "Foci", "(R)L", "R*5000", rating=(1, 6), focus="Enchanting"),
    _g("Metamagic Focus", "Magic", "Foci", "(R)L", "R*9000", rating=(1, 6), focus="Metamagic"),
    _g("Power Focus", "Magic", "Foci", "(R+3)L", "R*18000", rating=(1, 6), focus="Power"),
    _g("Qi Focus", "Magic", "Foci", "(R)L", "R*3000", rating=(1, 6), focus="Qi"),
    _g("Spell Focus", "Magic", "Foci", "(R)L", "R*4000", rating=(1, 6), focus="Spell"),
    _g("Spirit Focus", "Magic", "Foci", "(R)L", "R*4000", rating=(1, 6), focus="Spirit"),
    _g("Weapon Focus", "Magic", "Foci", "(R+3)L", "R*7000", rating=(1, 6), focus="Weapon"),
    _g("Combat Spell Formula", "Magic", "Formulae", "3(L)", 2000),
    _g("Detection Spell Formula", "Magic", "Formulae", "2(L)", 500),
    _g("Health Spell Formula", "Magic", "Formulae", "2(L)", 500),
    _g("Illusion Spell Formula", "Magic", "Formulae", "3(L)", 1000),
    _g("Manipulation Spell Formula", "Magic", "Formulae", "3(L)", 1500),
    _g("Magical Lodge Materials", "Magic", "Supplies", "(R)L", "R*500", rating=(1, 6)),
    _g("Reagents (dram)", "Magic", "Supplies", "2", 50, consumable=True),
]

FOCUS_BOND_KARMA = {"Enchanting": 3, "Metamagic": 3, "Power": 6, "Qi": 2, "Spell": 2, "Spirit": 2, "Weapon": 3}


def _v(name, sub, hand, accel, interval, top, body, armor, pilot, sensor, seat, avail, cost, cat="Vehicles", desc=""):
    d = {"name": name, "cat": cat, "sub": sub, "handling": hand, "accel": accel, "speed_interval": interval,
         "top_speed": top, "body": body, "armor": armor, "pilot": pilot, "sensor": sensor, "seats": seat,
         "avail": avail, "cost": cost}
    if desc:
        d["desc"] = desc
    return d


VEHICLES = [
    _v("Dodge Scoot", "Bikes", "5/7", 4, 10, 80, 2, 0, 1, 0, "2", "2", 3000),
    _v("Harley-Davidson Scorpion", "Bikes", "3/5", 16, 30, 200, 7, 6, 1, 1, "2", "2", 14000),
    _v("Yamaha Growler", "Bikes", "3/3", 15, 20, 180, 6, 4, 1, 1, "2", "2", 8000),
    _v("Suzuki Mirage", "Bikes", "2/6", 29, 30, 260, 4, 2, 1, 1, "1", "2", 12000),
    _v("Chrysler-Nissan Jackrabbit", "Cars", "3/5", 20, 15, 160, 8, 4, 2, 1, "3", "2", 11000),
    _v("Honda Spirit", "Cars", "4/5", 15, 20, 150, 10, 3, 1, 1, "4", "2", 13000),
    _v("Eurocar Westwind X80", "Cars", "2/6", 24, 30, 250, 6, 1, 4, 3, "2", "3", 115000),
    _v("Hyundai Shin-hyung", "Cars", "3/5", 12, 25, 200, 7, 1, 1, 1, "3", "2", 20000),
    _v("Ford Americar", "Cars", "4/5", 9, 20, 160, 11, 4, 1, 2, "4", "2", 16000),
    _v("Saeder-Krupp-Bentley Concordat", "Cars", "3/5", 18, 30, 180, 14, 8, 3, 3, "4", "3", 65000),
    _v("Mitsubishi Nightsky", "Cars", "4/6", 10, 10, 160, 18, 10, 3, 4, "8", "3", 259000),
    _v("Toyota Gopher", "Trucks & Vans", "4/4", 15, 15, 150, 12, 6, 1, 1, "4", "2", 25000),
    _v("GMC Bulldog", "Trucks & Vans", "5/7", 10, 10, 140, 16, 12, 2, 3, "2/10", "2", 35000),
    _v("Range Rover Model 2080", "Trucks & Vans", "4/5", 12, 20, 160, 16, 10, 4, 4, "7", "3", 73000),
    _v("Ares Roadmaster", "Trucks & Vans", "5/7", 8, 10, 120, 18, 16, 2, 2, "2/12", "2", 68000),
    _v("Samuvani Criscraft Otter", "Boats", "4", 10, 15, 90, 6, 4, 2, 2, "6", "2", 25000),
    _v("Aztechnology Sunrunner/Nightrunner", "Boats", "3", 20, 20, 120, 10, 8, 3, 3, "5", "3", 39000),
    _v("GMC Riverine", "Boats", "4", 15, 15, 100, 14, 12, 4, 4, "8", "4", 113000),
    _v("Proteus Lamprey/Sea Snake", "Submarines", "3", 13, 10, 60, 2, 1, 2, 1, "4", "2", 15000),
    _v("YNT Delfin", "Submarines", "5", 18, 10, 70, 6, 12, 3, 3, "3", "3", 110000),
    _v("Artemis Industries Nightwing", "Fixed-Wing Aircraft", "4", 15, 25, 150, 2, 0, 1, 1, "1", "2", 20000),
    _v("Cessna C750", "Fixed-Wing Aircraft", "5", 20, 25, 250, 8, 2, 2, 1, "4", "2", 150000),
    _v("MCT-Sikorsky-Bell Seahawk", "Fixed-Wing Aircraft", "5", 30, 50, 500, 12, 4, 2, 2, "8", "2", 300000),
    _v("Ares Dragon", "Rotorcraft", "4", 10, 30, 260, 12, 10, 2, 3, "2/16", "2", 360000),
    _v("MCT-Sikorsky-Bell Wolfhound", "Rotorcraft", "3", 20, 40, 320, 12, 14, 4, 4, "8", "4", 423000),
    _v("Northrup Wasp", "Rotorcraft", "3", 25, 30, 330, 10, 8, 3, 3, "2", "3", 93000),
    _v("Ares Venture", "VTOL/VSTOL", "4", 40, 60, 680, 16, 12, 2, 2, "2/8", "3", 400000),
    _v("GMC Banshee", "VTOL/VSTOL", "3", 60, 90, 900, 18, 18, 4, 4, "2/12", "4", 1300000),
    _v("Federated Boeing Commuter", "VTOL/VSTOL", "3", 35, 60, 420, 16, 10, 2, 2, "2/10", "2", 350000),
    _v("Federated Boeing Osprey X", "VTOL/VSTOL", "3", 35, 80, 420, 16, 16, 4, 4, "2/10", "4", 800000),
    # Drones
    _v("GMC Micromachine", "Microdrones", "3/6", 5, 5, 25, 0, 0, 1, 1, "—", "2", 450, cat="Drones"),
    _v("Shiawase Kanmushi", "Microdrones", "2/3", 4, 5, 15, 0, 0, 3, 2, "—", "2", 900, cat="Drones"),
    _v("Sikorsky-Bell Microskimmer XXS", "Microdrones", "2", 6, 10, 35, 0, 0, 2, 1, "—", "2", 850, cat="Drones"),
    _v("MCT Gnat", "Microdrones", "3", 4, 10, 30, 0, 0, 2, 1, "—", "2", 800, cat="Drones"),
    _v("GM-Nissan Flip-Flop", "Minidrones", "2/4", 8, 15, 50, 1, 0, 2, 1, "—", "2", 1000, cat="Drones"),
    _v("Shiawase Inu", "Minidrones", "2/3", 6, 8, 24, 1, 0, 2, 2, "—", "2", 1100, cat="Drones"),
    _v("Horizon Flying Eye", "Minidrones", "3", 15, 15, 40, 1, 0, 2, 2, "—", "2", 2000, cat="Drones"),
    _v("MCT Hornet", "Minidrones", "3", 20, 15, 35, 1, 0, 2, 2, "—", "2", 2100, cat="Drones"),
    _v("Chrysler-Nissan Pursuit V", "Small Drones", "3/6", 30, 50, 280, 4, 2, 4, 3, "—", "3", 11000, cat="Drones"),
    _v("Aztechnology Crawler", "Small Drones", "3/4", 8, 10, 30, 6, 2, 2, 2, "—", "2", 4500, cat="Drones"),
    _v("Cyberspace Designs Quadrotor", "Small Drones", "2", 15, 20, 120, 3, 1, 3, 2, "—", "2", 5000, cat="Drones"),
    _v("Lockheed Optic-X2", "Small Drones", "4", 15, 30, 140, 2, 4, 4, 4, "—", "3", 18000, cat="Drones"),
    _v("GM-Nissan Doberman", "Medium Drones", "3/5", 10, 15, 100, 4, 6, 2, 3, "—", "2", 6500, cat="Drones"),
    _v("Nissan Samurai", "Medium Drones", "3/4", 10, 10, 30, 6, 6, 3, 2, "—", "2", 4500, cat="Drones"),
    _v("Nissan Oni", "Medium Drones", "3/4", 10, 8, 30, 9, 10, 3, 2, "—", "2", 6700, cat="Drones"),
    _v("MCT-Nissan Roto-Drone", "Medium Drones", "3", 20, 30, 160, 5, 6, 3, 2, "—", "2", 5000, cat="Drones"),
    _v("Federated Boeing Blackhawk", "Medium Drones", "3", 35, 40, 200, 8, 6, 3, 3, "—", "3", 8000, cat="Drones"),
    _v("Steel Lynx Combat Drone", "Large Drones", "3/5", 15, 15, 80, 12, 16, 4, 4, "—", "4", 25000, cat="Drones"),
    _v("Ares Packmule", "Large Drones", "3/4", 6, 5, 30, 8, 6, 2, 1, "—", "3", 10000, cat="Drones"),
    _v("Cyberspace Designs Dalmatian", "Large Drones", "3", 13, 20, 130, 6, 4, 3, 3, "—", "3", 10000, cat="Drones"),
    _v("Ares Black Sky", "Large Drones", "2", 25, 50, 300, 8, 10, 4, 4, "—", "5", 43000, cat="Drones"),
]

VEHICLE_MODS = [
    _g("Rigger Interface", "Vehicles", "Modifications", "2", 1000, mod=True, desc="Lets a rigger jump in (drones have one already)."),
    _g("Standard Weapon Mount", "Vehicles", "Modifications", "4(I)", 2500, mod=True,
       desc="Holds an assault rifle or smaller and 250 rounds."),
    _g("Heavy Weapon Mount", "Vehicles", "Modifications", "5(I)", 5000, mod=True,
       desc="Counts as two mounts; holds any weapon and 500 belt rounds or Body rockets."),
    _g("Manual Operation (mount)", "Vehicles", "Modifications", "+1", 500, mod=True, desc="Vehicles only; adds 1 to the mount's Availability."),
]

GEAR_CATALOG = (WEAPONS + AMMO + EXPLOSIVES + WEAPON_ACCESSORIES + ARMOR + COMMLINKS + CYBERDECKS
                + ELECTRONICS + CYBERWARE + BIOWARE + MAGIC_GEAR + VEHICLES + VEHICLE_MODS)

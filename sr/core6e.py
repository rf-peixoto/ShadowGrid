"""Shadowrun Sixth World core rules data: metatypes, skills, qualities,
lifestyles and statuses (stats only; descriptions are short summaries)."""

PHYSICAL = ["Body", "Agility", "Reaction", "Strength"]
MENTAL = ["Willpower", "Logic", "Intuition", "Charisma"]
BASE_ATTRS = PHYSICAL + MENTAL + ["Edge"]

# Metatype attribute maximums (p. 64); every minimum is 1. Racial qualities
# are granted for free.
METATYPES = {
    "Human": {"max": {"Edge": 7}, "qualities": [],
              "desc": "Adaptable baseline metahuman; Edge up to 7."},
    "Dwarf": {"max": {"Body": 7, "Reaction": 5, "Strength": 8, "Willpower": 7},
              "qualities": ["Toxin Resistance", "Thermographic Vision"],
              "desc": "Short and sturdy; resistant to toxins, sees heat."},
    "Elf": {"max": {"Agility": 7, "Charisma": 8}, "qualities": ["Low-Light Vision"],
            "desc": "Graceful and charismatic; low-light vision."},
    "Ork": {"max": {"Body": 8, "Strength": 8, "Charisma": 5},
            "qualities": ["Low-Light Vision", "Built Tough"], "quality_levels": {"Built Tough": 1},
            "desc": "Big and tough; low-light vision, +1 Physical box."},
    "Troll": {"max": {"Body": 9, "Agility": 5, "Strength": 9, "Charisma": 5},
              "qualities": ["Dermal Deposits", "Thermographic Vision", "Built Tough"],
              "quality_levels": {"Built Tough": 2},
              "desc": "Huge; dermal armor, thermographic vision, +2 Physical boxes."},
}
DEFAULT_MAX = 6
AUGMENTED_BONUS_MAX = 4
# Size cost adjustment (p. 246): dwarfs +10% on fitted gear (armor, clothes),
# trolls +10% on everything.
SIZE_MARKUP = {"Dwarf": ("fitted", 0.10), "Troll": ("all", 0.10)}

SKILLS = {
    "Astral": {"attr": "Intuition", "untrained": False,
               "specs": ["Astral Combat", "Astral Signatures", "Emotional States", "Spirit Types"]},
    "Athletics": {"attr": "Agility", "untrained": True,
                  "specs": ["Climbing", "Flying", "Gymnastics", "Sprinting", "Swimming", "Throwing"]},
    "Biotech": {"attr": "Logic", "untrained": False,
                "specs": ["Biotechnology", "Cybertechnology", "First Aid", "Medicine"]},
    "Close Combat": {"attr": "Agility", "untrained": True, "specs": ["Blades", "Clubs", "Unarmed Combat"]},
    "Con": {"attr": "Charisma", "untrained": True, "specs": ["Acting", "Disguise", "Impersonation", "Performance"]},
    "Conjuring": {"attr": "Magic", "untrained": False, "specs": ["Banishing", "Binding", "Summoning"]},
    "Cracking": {"attr": "Logic", "untrained": False, "specs": ["Cybercombat", "Electronic Warfare", "Hacking"]},
    "Electronics": {"attr": "Logic", "untrained": True, "specs": ["Computer", "Hardware", "Software"]},
    "Enchanting": {"attr": "Magic", "untrained": False, "specs": ["Alchemy", "Artificing", "Disenchanting"]},
    "Engineering": {"attr": "Logic", "untrained": True,
                    "specs": ["Aeronautics Mechanic", "Automotive Mechanic", "Demolitions", "Gunnery",
                              "Industrial Mechanic", "Lockpicking", "Nautical Mechanic"]},
    "Exotic Weapons": {"attr": "Agility", "untrained": False, "exotic": True,
                       "specs": ["Launchers", "Monofilament Whip", "Bullwhip", "Shields", "Dart Guns", "Super Squirt",
                                 "Assault Cannon", "Flamethrower"]},
    "Firearms": {"attr": "Agility", "untrained": True, "specs": ["Automatics", "Longarms", "Pistols", "Rifles", "Shotguns"]},
    "Influence": {"attr": "Charisma", "untrained": True,
                  "specs": ["Etiquette", "Instruction", "Intimidation", "Leadership", "Negotiation"]},
    "Outdoors": {"attr": "Intuition", "untrained": True, "specs": ["Navigation", "Survival", "Tracking", "Urban", "Woods", "Desert"]},
    "Perception": {"attr": "Intuition", "untrained": True, "specs": ["Visual", "Aural", "Tactile", "Urban", "Woods", "Desert"]},
    "Piloting": {"attr": "Reaction", "untrained": True, "specs": ["Ground Craft", "Aircraft", "Watercraft"]},
    "Sorcery": {"attr": "Magic", "untrained": False, "specs": ["Counterspelling", "Ritual Spellcasting", "Spellcasting"]},
    "Stealth": {"attr": "Agility", "untrained": True, "specs": ["Disguise", "Palming", "Sneaking"]},
    "Tasking": {"attr": "Resonance", "untrained": False, "specs": ["Compiling", "Decompiling", "Registering"]},
}
SKILL_MAX = 9
SKILL_MAX_CREATION = 6
SPEC_BONUS = 2
EXPERTISE_BONUS = 3
EXPERTISE_MIN_RANK = 5

KNOWLEDGE_EXAMPLES = [
    "Aerospace Technology", "Arcana", "Automobile Models", "Combat Biker", "Corporate Personalities",
    "Espionage Techniques", "Hacker Groups", "Law Enforcement Corps", "Magical Societies", "Magical Traditions",
    "Metaplanes", "Ork Cuisine", "Orkxploitation Music", "Security Systems", "Seattle Gangs", "Seattle Streets",
    "Sixth World History", "Spirit Types", "Tech Companies", "Trideo Series", "Troll Thrash Rock", "Urban Brawl",
    "Virtual Nightclubs", "Weapons Manufacturers",
]
LANGUAGE_LEVELS = ["Basic", "Specialist", "Expert", "Native"]
LANGUAGE_BONUS = {"Basic": 0, "Specialist": 2, "Expert": 3, "Native": 0}
LANGUAGE_EXAMPLES = ["English", "Spanish", "Japanese", "Mandarin", "Cantonese", "Korean", "German", "French", "Russian",
                     "Portuguese", "Arabic", "Lakota", "Salish", "Sperethiel", "Or'zet", "Cityspeak"]

# Advancement costs (p. 68).
KARMA = {
    "skill": 5,          # x new rank
    "attribute": 5,      # x new rank
    "specialization": 5, "expertise": 5, "knowledge": 3, "language_level": 3,
    "spell": 5, "complex_form": 5, "ritual": 5,
    "initiation_base": 10, "submersion_base": 10,
    "quality_mult": 2,   # buy positive / remove negative after creation
    "nuyen_per_karma": 2000, "nuyen_per_karma_in_debt": 5000,
    "power_point": 5,    # mystic adepts
}
CREATION = {"karma": 50, "max_qualities": 6, "max_negative_karma": 20, "max_avail": 6,
            "contact_points_per_cha": 6, "max_starting_nuyen": 5000}

# Qualities (p. 70-79). karma > 0: cost; karma < 0: bonus. "levels": max level.
# "effects" are applied by sr.rules.derive.
QUALITIES = {
    # --- Positive ---
    "Ambidextrous": {"karma": 4, "desc": "No penalty for off-hand weapon use."},
    "Analytical Mind": {"karma": 3, "desc": "Bonus Edge on any Logic-based test."},
    "Aptitude": {"karma": 12, "choice": "skill", "desc": "Skill max 10 (7 at creation) for the chosen skill."},
    "Astral Chameleon": {"karma": 9, "desc": "-2 dice to recognise your aura; your signature fades twice as fast."},
    "Blandness": {"karma": 8, "desc": "-2 on Memory tests to recall you; +1 threshold to notice you tailing."},
    "Built Tough": {"karma": 4, "levels": 4, "effects": {"phys_boxes": "L"}, "desc": "+1 Physical box per level."},
    "Catlike": {"karma": 12, "desc": "Bonus Edge on balance, falling and landing tests."},
    "Dermal Deposits": {"karma": 7, "effects": {"dr": 1, "unarmed_dv_bonus": 1, "unarmed_physical": True},
                        "desc": "+1 natural armor; unarmed DV (STR/2)+1 Physical."},
    "Double-Jointed": {"karma": 12, "desc": "Bonus Edge on grappling, escaping bonds and squeezing through."},
    "Elemental Resistance": {"karma": 12, "choice": "element", "desc": "Gain Edge before defending against the chosen element."},
    "Exceptional Attribute": {"karma": 12, "choice": "attribute", "effects": {"attr_max": 1},
                              "desc": "+1 to the chosen attribute's maximum (max 10)."},
    "First Impression": {"karma": 12, "desc": "2 Edge on social tests at a first meeting."},
    "Focused Concentration": {"karma": 12, "levels": 3, "effects": {"free_sustain": "L"},
                              "desc": "Sustain one extra spell or form per level without penalty (drain under 7)."},
    "Gearhead": {"karma": 10, "desc": "Edge on vehicle repair tests."},
    "Guts": {"karma": 12, "desc": "Edge to resist Intimidation and fear."},
    "Hardening": {"karma": 10, "desc": "Bonus Edge on Matrix damage resistance; convert 2 boxes to Stun."},
    "High Pain Tolerance": {"karma": 7, "effects": {"wound_reduce": 1}, "desc": "Wound modifiers reduced by 1."},
    "Home Ground": {"karma": 10, "choice": "place", "desc": "Edge on Outdoors and Perception in your home area."},
    "Human-Looking": {"karma": 8, "desc": "Pass as human; +2 on disguise tests."},
    "Indomitable": {"karma": 12, "desc": "Edge Boosts cost 1 less on Willpower tests."},
    "Juryrigger": {"karma": 12, "desc": "Edge on juryrigging tests."},
    "Long Reach": {"karma": 12, "desc": "Melee Close range extends to 5 m."},
    "Low-Light Vision": {"karma": 6, "effects": {"vision": "Low-light"}, "desc": "See in any light except total darkness."},
    "Magic Resistance": {"karma": 8, "desc": "Edge on Magic Resistance tests; Health spells treat your Essence as 2 lower."},
    "Mentor Spirit": {"karma": 10, "choice": "mentor", "desc": "Gain your mentor spirit's advantages and disadvantage."},
    "Photographic Memory": {"karma": 12, "desc": "Bonus Edge on Memory tests."},
    "Quick Healer": {"karma": 8, "effects": {"quick_heal": True}, "desc": "Natural healing intervals are halved."},
    "Resistance to Pathogens": {"karma": 12, "desc": "Bonus Edge on pathogen resistance tests."},
    "Spirit/Sprite Affinity": {"karma": 14, "choice": "spirit/sprite type", "desc": "Bonus Edge on Conjuring or Tasking with that type."},
    "Thermographic Vision": {"karma": 8, "effects": {"vision": "Thermographic"}, "desc": "See heat in total darkness."},
    "Toughness": {"karma": 12, "desc": "Bonus Edge on damage resistance tests."},
    "Toxin Resistance": {"karma": 12, "desc": "Bonus Edge on toxin resistance tests."},
    "Will to Live": {"karma": 8, "levels": 3, "effects": {"overflow": "2*L"}, "desc": "+2 overflow boxes per level."},
    # --- Negative ---
    "Addiction": {"karma": -2, "levels": 6, "choice": "substance", "desc": "No Edge while in withdrawal; -2 dice, growing."},
    "Allergy": {"karma": -2, "max_karma": -20, "choice": "allergen and severity",
                "desc": "Bonus 2-20 by commonness and severity; penalties while exposed."},
    "AR Vertigo": {"karma": -10, "desc": "No Edge while using AR; Nauseated during and after."},
    "Astral Beacon": {"karma": -10, "desc": "Untrained for astral Stealth; others gain Edge assensing you."},
    "Bad Luck": {"karma": -10, "desc": "1s and 2s count toward glitches."},
    "Bad Rep": {"karma": -8, "desc": "No Edge on Social tests."},
    "Combat Paralysis": {"karma": -8, "desc": "Initiative halved and no Move/Sprint in the first round."},
    "Dependents": {"karma": -4, "levels": 3, "desc": "5/10/25% of every score goes to dependents."},
    "Distinctive Style": {"karma": -6, "desc": "No Edge when out of style; others +2 to remember you."},
    "Elf Poser": {"karma": -6, "desc": "Real elves, orks and trolls gain Edge on Etiquette against you."},
    "Glass Jaw": {"karma": -4, "levels": 3, "effects": {"stun_boxes": "-L"}, "desc": "-1 Stun box per level (min 2)."},
    "Gremlins": {"karma": -6, "desc": "Devices you use may malfunction (2D6 with a 1)."},
    "Honorbound": {"karma": -10, "choice": "code", "desc": "Breaking your code locks Edge for 24 hours."},
    "Impaired": {"karma": -8, "levels": 5, "choice": "attribute", "effects": {"attr_max": "-L"},
                 "desc": "-1 to the attribute's maximum per level (min 2)."},
    "Incompetent": {"karma": -10, "choice": "skill", "desc": "Can never gain ranks in the chosen skill."},
    "In Debt": {"karma": 0, "desc": "Karma buys 5,000¥ instead of 2,000¥, all owed to dangerous people."},
    "Insomnia": {"karma": -4, "desc": "Daily Body + Willpower (3) or Edge limits."},
    "Loss of Confidence": {"karma": -6, "desc": "Willpower (2) each encounter or no Edge."},
    "Low Pain Tolerance": {"karma": -10, "effects": {"wound_double": True}, "desc": "All wound modifiers doubled."},
    "Ork Poser": {"karma": -6, "desc": "Real elves, orks and trolls gain Edge on Etiquette against you."},
    "Prejudiced": {"karma": -8, "choice": "group", "desc": "No Edge while that group is present (unless attacking)."},
    "Scorched": {"karma": -6, "desc": "Cannot spend Edge while accessing the Matrix."},
    "Sensitive System": {"karma": -8, "effects": {"essence_mult": 2}, "desc": "Cyberware and bioware Essence doubled; mundane only."},
    "Simsense Vertigo": {"karma": -6, "desc": "No Edge in VR; Nauseated after."},
    "SINner": {"karma": -8, "effects": {"lifestyle_mult": 1.1}, "desc": "Legal SIN: +10% lifestyle cost; easier to trace."},
    "Social Stress": {"karma": -8, "choice": "stressor", "desc": "Charisma (2) test or no Edge."},
    "Spirit/Sprite Bane": {"karma": -12, "choice": "spirit/sprite type", "desc": "That type gains Edge against you and hunts you."},
    "Uncouth": {"karma": -6, "desc": "Cannot spend Edge on Charisma tests."},
    "Uneducated": {"karma": -6, "desc": "Cannot spend Edge on Logic tests."},
    "Unsteady Hands": {"karma": -4, "desc": "Cannot spend Edge on hand-based Agility tests."},
    "Weak Immune System": {"karma": -8, "desc": "No Edge against infection; +1 threshold; -1 while ill."},
}

LIFESTYLES = {"Street": 0, "Squatter": 500, "Low": 2000, "Middle": 5000, "High": 10000, "Luxury": 100000}

# Statuses (p. 51-53) with the icon shown on map tokens.
STATUSES = {
    "Blinded": {"icon": "👁", "levels": 3, "desc": "-3 per level to visual tests; III auto-fails."},
    "Burning": {"icon": "🔥", "value": True, "desc": "Resist # Physical each round."},
    "Chilled": {"icon": "❄", "desc": "-4 Initiative, -1 to pools except resistance."},
    "Confused": {"icon": "❓", "value": True, "desc": "-# to all actions."},
    "Corrosive": {"icon": "🧪", "value": True, "desc": "Resist # Physical each round."},
    "Cover": {"icon": "🛡", "levels": 4, "desc": "+1 DR and defense dice per level."},
    "Dazed": {"icon": "💫", "desc": "-4 Initiative; can't gain or spend Edge."},
    "Deafened": {"icon": "🔇", "levels": 3, "desc": "-3 per level to hearing tests."},
    "Fatigued": {"icon": "😩", "levels": 3, "desc": "-2 per level to pools; slower movement."},
    "Frightened": {"icon": "😱", "desc": "-4 against the source of fear."},
    "Hazed": {"icon": "🌫", "desc": "Can't cross between astral and physical."},
    "Hobbled": {"icon": "🦶", "desc": "Movement halved."},
    "Immobilized": {"icon": "⛓", "desc": "Can't move; -3 AR and attack dice; no Reaction on defense."},
    "Invisible": {"icon": "👻", "value": True, "desc": "Perception threshold #."},
    "Nauseated": {"icon": "🤢", "desc": "Body + Willpower (2) each round or lose actions."},
    "Panicked": {"icon": "🏃", "desc": "Can only flee the cause."},
    "Petrified": {"icon": "🗿", "desc": "No actions, +10 armor."},
    "Poisoned": {"icon": "☠", "value": True, "desc": "Resist the damage each round; drops by 1."},
    "Prone": {"icon": "⬇", "desc": "+2 defense vs Medium+ range, -2 vs Close/Near, -4 melee."},
    "Silent": {"icon": "🤫", "value": True, "desc": "Hearing threshold #."},
    "Stilled": {"icon": "⏸", "desc": "Can't move or act; -10 DR."},
    "Wet": {"icon": "💧", "desc": "-6 to resist cold and electricity."},
    "Zapped": {"icon": "⚡", "desc": "-2 Initiative, no Sprint, -1 to all actions."},
}


# --------------------------------------------------------------------------- Sixth World Companion
# Metavariants, metasapients and the new qualities join the core tables. Base metatypes
# carry "base" = their own name so variants can be grouped and inherit size pricing.
def _merge_companion():
    from . import companion6e as C
    for name, m in METATYPES.items():
        m.setdefault("base", name)
        m.setdefault("karma", 0)
    for name, v in list(C.METAVARIANTS.items()) + list(C.METASAPIENTS.items()):
        METATYPES[name] = {
            "base": v["base"], "karma": v["karma"], "max": dict(v["max"]), "qualities": list(v["qualities"]),
            "quality_levels": dict(v.get("levels", {})), "quality_choices": dict(v.get("choices", {})),
            "weapons": v.get("weapons", []), "move": v.get("move"), "move_note": v.get("move_note", ""),
            "dr": v.get("dr", 0), "size": v.get("size"), "desc": v["desc"], "source": C.SOURCE,
            "metasapient": v["base"] == "Metasapient",
        }
    for table in (C.QUALITIES, C.METAGENIC_POSITIVE, C.METAGENIC_NEGATIVE):
        for name, q in table.items():
            QUALITIES.setdefault(name, q)
    for name, desc in C.RACIAL_ONLY.items():
        QUALITIES.setdefault(name, {"karma": 0, "desc": desc, "racial_only": True, "source": C.SOURCE})
    for alias, real in C.QUALITY_ALIASES.items():
        if alias not in QUALITIES and real in QUALITIES:
            QUALITIES[alias] = dict(QUALITIES[real], alias_of=real, racial_only=True)


_merge_companion()
BASE_METATYPES = ["Human", "Elf", "Dwarf", "Ork", "Troll"]

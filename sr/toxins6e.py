"""Toxins, drugs and diseases (core rulebook rules, Sixth World Companion substances).

Exposure: the target rolls Body + Willpower (Toxin Resistance); each hit lowers the substance's Power
by 1. Whatever Power is left is applied: damage (Stun or Physical), statuses (Nauseated, Dazed for
disorientation, Immobilized for paralysis, Poisoned for ongoing damage) and, for drugs, their bonuses
for the duration. When a drug wears off its crash applies. Some substances call for an addiction
test (Body + Willpower against a threshold); failing it gives or raises the Addiction quality.

Each game keeps a library of substances: the built-in ones below plus anything the GM adds (the core
book's toxins and drugs can be entered with their book values).
"""

VECTORS = ["Contact", "Ingestion", "Inhalation", "Injection"]
EFFECT_STATUSES = {"Nausea": "Nauseated", "Disorientation": "Dazed", "Paralysis": "Immobilized", "Ongoing": "Poisoned"}
DAMAGE_TYPES = {"": "No damage", "S": "Stun", "P": "Physical"}

BUILTIN = [
    {"id": "renfield", "name": "Renfield", "kind": "drug", "source": "Sixth World Companion",
     "vectors": ["Ingestion", "Injection"], "speed": "1 combat round", "power": 8, "duration": "7 days",
     "damage": "", "effects": ["Euphoria"], "attrs": {"Agility": 1, "Intuition": 1, "Strength": 1}, "init_dice": 1,
     "addiction": 3, "crash": None,
     "desc": "Vampire blood drug used to make pawns. Each dose gives a pawn 1D6 Essence. Failing to reduce its Power to 0 calls for an Addiction (3) test."},
    {"id": "hmhvv-1", "name": "HMHVV Strain I", "kind": "disease", "source": "Sixth World Companion",
     "vectors": ["Infection power"], "speed": "1 minute", "power": 13, "duration": "",
     "damage": "", "effects": ["Coma", "Transformation"], "attrs": {}, "init_dice": 0, "addiction": 0, "crash": None,
     "desc": "Vampiric strain, spread only by the Infection power. Power 6 or lower gives a chance to escape the disease."},
    {"id": "hmhvv-2", "name": "HMHVV Strain II", "kind": "disease", "source": "Sixth World Companion",
     "vectors": ["Injection"], "speed": "1 hour", "power": 10, "duration": "",
     "damage": "", "effects": ["Nausea", "Essence loss", "Transformation"], "attrs": {}, "init_dice": 0, "addiction": 0, "crash": None,
     "desc": "Defeated by reducing its Power to 0 with Disease Resistance tests."},
    {"id": "hmhvv-3", "name": "HMHVV Strain III (Krieger)", "kind": "disease", "source": "Sixth World Companion",
     "vectors": ["Injection"], "speed": "12 hours", "power": 6, "duration": "",
     "damage": "", "effects": ["Nausea", "Essence loss", "Transformation"], "attrs": {}, "init_dice": 0, "addiction": 0, "crash": None,
     "desc": "The ghoul strain. Defeated by reducing its Power to 0 with Disease Resistance tests."},
]

MAX_LIBRARY = 200

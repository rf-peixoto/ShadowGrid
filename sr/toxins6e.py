"""Toxins, drugs and diseases (Sixth World core rulebook, with the 2019 errata prices; Sixth World Companion).

Exposure: the target rolls Body + Willpower (Toxin Resistance); each hit lowers the substance's Power
by 1. Whatever Power is left is applied: damage equal to the Power left (Stun or Physical), statuses
for the duration, and, for drugs, their bonuses while they last. When an effect wears off, the statuses
it caused end and its crash applies (damage, statuses, or penalties that last on their own). Some
substances call for an addiction test (Body + Willpower against a threshold); failing it gives or
raises the Addiction quality.

Fields: power, damage ("S"/"P"/""), effects (statuses such as "Dazed", "Blinded I", "Fatigued II",
or the words Nausea / Disorientation / Paralysis / Ongoing, or plain text), attrs {attribute: ±n},
init_dice, hpt (High Pain Tolerance: wound modifiers −n), pool (dice on every test), pool_physical
(dice on tests with a Physical attribute), skills {skill: ±n}, sustain (penalty per sustained spell
instead of −2), zero [attributes that drop to 0], crash {the same fields, plus dv/damage for the
crash's unresisted damage}, addiction (threshold, 0 = none).

Each game keeps a library: these built-in substances plus anything the GM adds. Core-book values are
from the rulebook tables as published (Availability and cost from the errata).
"""

VECTORS = ["Contact", "Ingestion", "Inhalation", "Injection"]
EFFECT_STATUSES = {"Nausea": "Nauseated", "Disorientation": "Dazed", "Paralysis": "Immobilized", "Ongoing": "Poisoned"}
DAMAGE_TYPES = {"": "No damage", "S": "Stun", "P": "Physical"}

CORE = "SR6 core rulebook"


def _t(sid, name, vectors, speed, power, duration, damage, effects, avail, cost, desc, **kw):
    out = {"id": sid, "name": name, "kind": "toxin", "source": CORE, "vectors": vectors, "speed": speed, "power": power,
           "duration": duration, "damage": damage, "effects": effects, "attrs": {}, "init_dice": 0, "addiction": 0, "crash": None,
           "avail": avail, "cost": cost, "desc": desc}
    out.update(kw)
    return out


def _d(sid, name, vectors, speed, power, duration, attrs, avail, cost, desc, **kw):
    out = {"id": sid, "name": name, "kind": "drug", "source": CORE, "vectors": vectors, "speed": speed, "power": power,
           "duration": duration, "damage": "", "effects": [], "attrs": attrs, "init_dice": 0, "addiction": 0, "crash": None,
           "avail": avail, "cost": cost, "desc": desc}
    out.update(kw)
    return out


CORE_TOXINS = [
    _t("cs-tear-gas", "CS/Tear Gas", ["Contact", "Inhalation"], "1 combat round", 8, "(6 − Body) × 5 minutes, min 5", "S",
       ["Dazed", "Nauseated"], "2(L)", 20, "Riot-control irritant: burning eyes, nose and lungs, and panic. Inert after two minutes in the air."),
    _t("gamma-scopolamine", "Gamma-Scopolamine", ["Injection"], "Immediate", 12, "(6 − Body) × 30 minutes, min 30", "",
       ["Dazed", "Immobilized"], "7(I)", 200,
       "Paralytic interrogation drug. When the full effect ends, the residue works as a truth serum for about an hour: Willpower −3 (minimum 1).",
       crash={"dv": 0, "damage": "S", "effects": [], "attrs": {"Willpower": -3}, "duration": "about 1 hour"}),
    _t("narcoject", "Narcoject", ["Injection"], "Immediate", 15, "(6 − Body) hours, min 1", "S",
       [], "4(L)", 50, "Common tranquilizer for dart guns and injection rounds. No side effects."),
    _t("nausea-gas", "Nausea Gas", ["Inhalation"], "3 combat rounds", 9, "(6 − Body) minutes, min 1", "",
       ["Dazed", "Nauseated"], "3(L)", 25, "Riot-control agent. Inert after two minutes in the air."),
    _t("neuro-stun-viii", "Neuro-Stun VIII", ["Contact", "Inhalation"], "1 combat round", 9, "(6 − Body) × 10 minutes, min 10", "S",
       ["Dazed"], "5(L)", 60, "Colorless, odorless knockout gas, the standard for emergency containment. Inert after ten minutes in the air."),
    _t("neuro-stun-ix", "Neuro-Stun IX", ["Contact", "Inhalation"], "1 combat round", 12, "(6 − Body) × 10 minutes, min 10", "S",
       ["Dazed"], "6(L)", 60, "A stronger Neuro-Stun. Inert after ten minutes in the air."),
    _t("neuro-stun-x", "Neuro-Stun X", ["Contact", "Inhalation"], "1 combat round", 15, "(6 − Body) × 10 minutes, min 10", "S",
       ["Dazed"], "7(L)", 100, "The strongest Neuro-Stun. Inert after one minute in the air."),
    _t("pepper-punch", "Pepper Punch", ["Contact", "Inhalation"], "1 combat round", 11, "(8 − Body) × 20 minutes, min 20", "S",
       ["Blinded I", "Dazed", "Nauseated"], "1", 5, "CS and capsaicin self-defense spray, often tagged with RFID or dye to identify the victim later."),
    _t("seven-7", "Seven-7", ["Contact", "Inhalation"], "1 combat round", 12, "(6 − Body) × 10 minutes, min 10", "P",
       ["Blinded I", "Dazed", "Nauseated"], "10(I)", 1000, "Military gas that gets past chemical protection: cramps, nausea, double vision. Inert after ten minutes in the air."),
]

CORE_DRUGS = [
    _d("alcohol", "Alcohol", ["Ingestion"], "1 minute", 6, "(8 − Body) hours, min 1", {"Reaction": -1, "Logic": -1}, "1", 5,
       "From a cheap soykaf-beer (5¥) to the good stuff (500¥).", hpt=1),
    _d("bliss", "Bliss", ["Inhalation", "Injection"], "1 combat round", 8, "(6 − Body) hours, min 1", {"Reaction": -1, "Willpower": -1}, "2(I)", 15,
       "Tranquilizing narcotic: dreamy, detached and pain-free.", hpt=1),
    _d("cram", "Cram", ["Ingestion", "Inhalation"], "10 minutes", 8, "(12 − Body) hours, min 1", {"Reaction": 1}, "2(L)", 10,
       "Stimulant: hyper-alert, almost to the point of paranoia. Crash: 6 Stun, unresisted.", init_dice=1,
       crash={"dv": 6, "damage": "S", "effects": []}),
    _d("deepweed", "Deepweed", ["Ingestion", "Inhalation"], "Immediate", 7, "(6 − Body) hours, min 1", {"Willpower": 1}, "4(I)", 400,
       "Forces Awakened users into astral perception. Crash: −1 die on all tests for as long as the effect lasted.",
       crash={"dv": 0, "damage": "S", "effects": [], "pool": -1, "duration": "as long as the effect lasted"}),
    _d("jazz", "Jazz", ["Inhalation"], "Immediate", 9, "10 × 1D6 minutes", {"Reaction": 1}, "2(L)", 75,
       "Combat stimulant. Crash: Dazed and despondent for as long as the effect lasted.", init_dice=2,
       crash={"dv": 0, "damage": "S", "effects": ["Dazed"], "duration": "as long as the effect lasted"}),
    _d("kamikaze", "Kamikaze", ["Inhalation"], "Immediate", 10, "10 × 1D6 minutes", {"Body": 1, "Agility": 1, "Strength": 2, "Willpower": 1}, "3(L)", 100,
       "Combat drug. Crash: 6 Stun unresisted, then Reaction −1, Willpower −1 and Fatigued II for twice as long as the effect lasted.",
       init_dice=2, hpt=1,
       crash={"dv": 6, "damage": "S", "effects": ["Fatigued II"], "attrs": {"Reaction": -1, "Willpower": -1}, "duration": "twice as long as the effect lasted"}),
    _d("long-haul", "Long Haul", ["Injection"], "10 minutes", 11, "4 days", {}, "1", 50,
       "No need to sleep while it lasts. More doses stretch it with growing fatigue; a fourth extra dose deals 12 Stun, unresisted. "
       "Crash: the user passes out at once for 8D6 hours.",
       crash={"dv": 0, "damage": "S", "effects": [], "duration": "8D6 hours asleep"}),
    _d("nitro", "Nitro", ["Inhalation"], "1 combat round", 12, "10 × 1D6 minutes", {"Strength": 2, "Willpower": 2}, "2(L)", 50,
       "Heavy-duty stimulant: +2 Perception. Crash: 9 Stun unresisted and −2 dice on all tests for as long as the effect lasted.",
       init_dice=1, hpt=1, skills={"Perception": 2},
       crash={"dv": 9, "damage": "S", "effects": [], "pool": -2, "duration": "as long as the effect lasted"}),
    _d("novacoke", "Novacoke", ["Inhalation", "Injection"], "1 combat round", 12, "(10 − Body) hours, min 1", {"Reaction": 1, "Charisma": 1}, "2(L)", 10,
       "Highly addictive social stimulant: +1 Perception. Crash: Charisma and Willpower drop to 0 for as long as the effect lasted.",
       hpt=1, skills={"Perception": 1},
       crash={"dv": 0, "damage": "S", "effects": [], "zero": ["Charisma", "Willpower"], "duration": "as long as the effect lasted"}),
    _d("psyche", "Psyche", ["Ingestion"], "10 minutes", 8, "(12 − Body) hours, min 1", {"Intuition": 1, "Logic": 1}, "1", 200,
       "Concentration drug: Awakened and Emerged users take only −1 per sustained spell or complex form instead of −2.", sustain=-1),
    _d("zen", "Zen", ["Inhalation"], "5 minutes", 7, "10 × 1D6 minutes", {"Reaction": -2, "Willpower": 1}, "3(L)", 5,
       "Relaxing hallucinogen favored by meditating magicians: −1 die on tests with a Physical attribute.", pool_physical=-1),
]

BUILTIN = CORE_TOXINS + CORE_DRUGS + [
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

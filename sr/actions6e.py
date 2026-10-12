"""Shadowrun Sixth World combat actions and situational modifiers (core rulebook, Combat chapter).

Every number the combat code uses lives in this file, so a table can be checked against the book
(and changed) in one place.

Actions: each combat round a combatant has 1 Major Action and 1 Minor Action + 1 per Initiative Die
(at most 5 Minor). Four Minor Actions can be traded for one Major. Interrupt actions are taken out of
turn and use up actions of the current round.
"""

MAX_MINOR = 5
MINOR_PER_MAJOR = 4          # four Minor Actions buy one Major Action
EDGE_GAIN_CAP = 2            # Edge a character can gain per combat round

# ---------------------------------------------------------------- defensive interrupts
# add: dice added to the Defense test. "skill:X" = rank in skill X, "attr:X" = attribute X, int = flat.
# vs: which attacks it works against ("melee", "ranged", "any"). lasts: "attack" (this one) or "round".
INTERRUPTS = {
    "block": {"name": "Block", "cost": "minor", "vs": "melee", "add": "skill:Close Combat",
              "desc": "Add Close Combat to the Defense test against a melee attack."},
    "dodge": {"name": "Dodge", "cost": "minor", "vs": "any", "add": "skill:Athletics",
              "desc": "Add Athletics to the Defense test."},
    "hit_the_dirt": {"name": "Hit the Dirt", "cost": "minor", "vs": "ranged", "add": 2, "status": "Prone",
                     "desc": "+2 dice on the Defense test and drop Prone; −2 on active tests until the end of your next turn unless you Stand Up."},
    "full_defense": {"name": "Full Defense", "cost": "major", "vs": "any", "add": "attr:Willpower", "lasts": "round",
                     "desc": "Add Willpower to every Defense test until the end of the combat round."},
}
HIT_THE_DIRT_PENALTY = -2

# Intercept: Major interrupt, a melee attack against someone moving through your reach. It is rolled
# as a normal attack out of turn (the GM picks "Intercept" in the attack dialog).
INTERCEPT = {"name": "Intercept", "cost": "major",
             "desc": "Out of turn: a melee attack on an enemy who moves within your reach. Counts as your Attack Major Action."}

# ---------------------------------------------------------------- attack options
# Called shots are a Minor Action combined with the Attack. edge: Edge the attacker spends.
CALLED_SHOTS = {
    "damage": {"name": "Called shot: +2 DV", "dice": -4, "dv": 2, "edge": 0,
               "desc": "−4 dice, +2 DV."},
    "shank": {"name": "Shank (melee)", "dice": -2, "dv": 2, "edge": 1, "melee": True,
              "desc": "Called shot in melee with only −2 dice (1 Edge)."},
    "vitals": {"name": "Vitals", "dice": -4, "dv": 3, "edge": 5,
               "desc": "−4 dice, +3 DV (5 Edge)."},
    "disarm": {"name": "Disarm", "dice": -4, "dv": 0, "edge": 5, "disarm": True,
               "desc": "−4 dice; on a hit the target drops their weapon (5 Edge)."},
}
MULTIPLE_ATTACKS = {"cost": "minor", "desc": "Split the dice pool evenly among the targets (Minor Action)."}
ANTICIPATION = {"edge": 4, "desc": "With multiple attacks, roll the full dice pool against every target (4 Edge)."}
EDGE_HINT_MARGIN = 4         # AR beats DR (or the reverse) by this much: that side may gain 1 Edge

# ---------------------------------------------------------------- statuses (core book list, applied in combat)
# attack: dice on attacks; defense: dice on Defense tests; dr: Defense Rating; init: initiative score.
# "#" values use the status level (Cover I-IV, Fatigued I-III...) or its number (Confused 2...).
STATUS_MODS = {
    "Blinded":     {"attack": "-3#", "ranged_only": True},
    "Chilled":     {"attack": -1, "defense": -1, "init": -4},
    "Confused":    {"attack": "-#", "defense": "-#"},
    "Cover":       {"defense": "+#", "dr": "+#"},
    "Dazed":       {"init": -4, "no_edge": True},
    "Fatigued":    {"attack": "-2#", "defense": "-2#"},
    "Immobilized": {"attack": -3, "ar": -3, "no_reaction": True},
    "Petrified":   {"dr": 10},
    "Stilled":     {"dr": -10},
    "Zapped":      {"attack": -1, "defense": -1, "init": -2},
}
PRONE = {"defense_far": 2, "defense_near": -2, "far_ranges": ("Medium", "Far", "Extreme")}
WET_SOAK = -6                # Wet: resisting cold and electricity

# Ongoing damage at the start of each round: (status, element, value drops by)
ONGOING = {"Burning": ("Fire", 0), "Corrosive": ("Chemical", 0), "Poisoned": ("Toxin", 1)}

# ---------------------------------------------------------------- magic in combat
SUSTAIN_PENALTY = -2         # per spell a character sustains themselves
COUNTERSPELL = {"skill": "Sorcery", "desc": "A magician protecting the target adds their Sorcery dice to the Defense test against a spell."}

# Astral combat: attacker rolls skill + attribute against the defender's pool; DV from an attribute.
ASTRAL = {"attack": ("Astral", "Willpower"), "defense": ("Intuition", "Logic"), "soak": ("Willpower",),
          "dv_attr": "Charisma", "dv_half": True,
          "type": "S", "weapon_focus": "A bonded weapon focus adds its DV and uses Close Combat's specialization."}

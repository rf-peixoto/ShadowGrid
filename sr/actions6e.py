"""Shadowrun Sixth World combat actions and situational modifiers (core rulebook, Combat chapter).

Every number the combat code uses lives in this file, so a table can be checked against the book
(and changed) in one place.

Actions: each combat round a combatant has 1 Major Action and 1 Minor Action + 1 per Initiative Die
(at most 5 Minor). Four Minor Actions can be traded for one Major. Interrupt actions are taken out of
turn and use up actions of the current round. Checked against the core rulebook (pp. 40-54, 104-118).

Edge: a character makes one Edge expenditure per combat round (the same boost may be multiplied);
Edge gained above the Edge rating goes away when the confrontation ends.
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
    "hit_the_dirt": {"name": "Hit the Dirt", "cost": "minor", "vs": "any", "add": 2, "status": "Prone",
                     "desc": "+2 dice on the Defense test and drop Prone; −2 on tests with active skills until you Stand Up."},
    "full_defense": {"name": "Full Defense", "cost": "major", "vs": "any", "add": "attr:Willpower", "lasts": "round",
                     "desc": "Add Willpower to every Defense test until the end of the combat round."},
}
HIT_THE_DIRT_PENALTY = -2

# Intercept (Minor, Anytime): a melee attack out of turn on an enemy coming within Close range. It needs a
# Minor and a Major Action left; the attack counts as the Attack Major Action. Not with ranged weapons.
INTERCEPT = {"name": "Intercept", "cost": "minor", "also": "major", "melee_only": True,
             "desc": "Out of turn: a melee attack on an enemy who comes within Close range. Uses a Minor Action and your Attack Major Action."}

# ---------------------------------------------------------------- attack options
# Called shots are a Minor Action combined with the Attack. edge: Edge the attacker spends.
# Call a Shot is a Minor Action; the Edge versions (Shank, Vitals, Disarm) are Edge Actions.
CALLED_SHOTS = {
    "damage": {"name": "Called shot: +2 DV", "dice": -4, "dv": 2, "edge": 0, "minor": True,
               "desc": "−4 dice, +2 DV (Minor Action)."},
    "shank": {"name": "Shank (blade)", "dice": -2, "dv": 2, "edge": 1, "melee": True, "minor": True,
              "desc": "Called shot with a blade at only −2 dice (1 Edge)."},
    "vitals": {"name": "Called shot: Vitals", "dice": 0, "dv": 3, "edge": 5,
               "desc": "+3 DV, no dice penalty (5 Edge)."},
    "disarm": {"name": "Called shot: Disarm", "dice": 0, "dv": 0, "edge": 5, "disarm": True, "no_damage": True,
               "desc": "A hit does no damage, but the target's weapon is knocked from their hands (5 Edge)."},
}
# Other Edge Actions on an attack (they cost Edge, not actions).
EDGE_ACTIONS = {
    "knockout": {"name": "Knockout Blow", "edge": 2, "melee": True,
                 "desc": "Melee: if the damage is greater than the target's Willpower, their Stun track fills (unconscious); nothing overflows."},
    "tumble": {"name": "Tumble", "edge": 1, "melee": True,
               "desc": "Melee: if the damage is greater than the target's Body, they go Prone."},
    "fire_from_cover": {"name": "Fire from Cover", "edge": 2, "ranged": True, "cover": 4,
                        "desc": "Attack from Cover IV without the −2 dice penalty."},
}
# Defensive Edge Actions, taken with an interrupt (they cost Edge, not actions).
DEFENSE_EDGE_ACTIONS = {
    "wrest": {"name": "Wrest", "edge": 2, "with": "block",
              "test": ("Close Combat", "Agility"), "threshold": "Strength",
              "desc": "With a successful Block: Close Combat + Agility, threshold the attacker's Strength. Equal: their weapon "
                      "falls to the ground; more hits: you take it from them (2 Edge)."},
    "tactical_roll": {"name": "Tactical Roll", "edge": 1, "with": "hit_the_dirt",
                      "desc": "With Hit the Dirt: no Prone penalty on your melee attacks this round, and no −2 from Prone "
                              "against Close or Near attacks until the end of the next round (1 Edge)."},
}
# Take Aim (Minor, p. 42): +1 die per action, once per round, up to Willpower; the bonus carries over to the
# next rounds, and is lost on a turn with neither Take Aim nor an attack. Firearms, bows, exotic ranged weapons.
TAKE_AIM = {"cost": "minor", "dice": 1, "max": "Willpower",
            "desc": "+1 die on your next ranged attack (once per round, up to your Willpower; it builds up over rounds)."}
# Trip (Minor, p. 42): melee only, with the Attack. −2 to the base DV; on a hit the target rolls
# Athletics + Agility with the attack's DV as threshold, or goes Prone.
TRIP = {"cost": "minor", "dv": -2, "test": ("Athletics", "Agility"),
        "desc": "Melee, with the attack (Minor Action): −2 DV; on a hit the target rolls Athletics + Agility against the DV or goes Prone."}
# Grapple (p. 111): an unarmed Close Combat + Agility attack; on a hit, Strength + net hits vs the target's
# Strength instead of damage. A restrained character can only try to break free (spells and complex forms
# still work), has −4 on Defense tests, and every attacker gains Edge on them; an attack that misses them may
# hit the grappler (who defends against the same roll). The follow-ups are Major Actions with the unarmed AR.
GRAPPLE = {
    "hold": {"attack": ("Strength",), "net": True, "defense": ("Strength",)},
    "restrained_defense": -4,
    "edge_on_restrained": 1,
    "actions": {
        "restrain": {"name": "Restrain", "attack": ("Close Combat", "Strength"), "defense": ("Close Combat", "Strength"), "penalty": True,
                     "desc": "Keep holding them: Close Combat + Strength vs Close Combat + Strength (−4 for them). If you fail, they're free."},
        "damage": {"name": "Squeeze", "attack": ("Close Combat", "Strength"), "defense": ("Strength", "Reaction"), "penalty": True,
                   "desc": "Hurt them: Close Combat + Strength vs Strength + Reaction (−4 for them); unarmed DV (Strength / 2) + net hits, Stun."},
        "tackle": {"name": "Tackle", "attack": ("Close Combat", "Strength"), "defense": ("Body", "Strength"), "penalty": False,
                   "desc": "Bring them down: Close Combat + Strength vs Body + Strength. They go Prone and take Stun equal to your Body + net hits, resisted with Body."},
        "break": {"name": "Break free", "attack": ("Close Combat", "Strength"), "defense": ("Close Combat", "Strength"), "penalty": False, "held": True,
                  "desc": "Close Combat + Strength vs the grappler's Close Combat + Strength (no −4). Success: free, no damage."},
    },
}
MULTIPLE_ATTACKS = {"cost": "minor", "desc": "Split the dice pool evenly among the targets (Minor Action). Full auto splits without it."}
ANTICIPATION = {"edge": 4, "ranged": True, "desc": "Ranged Multiple Attacks: roll the full dice pool against every target (4 Edge)."}
# Attacking from Cover: an extra Minor Action to get clear, no Edge for the attacker; from Cover IV −2 dice.
COVER_ATTACK = {"minor": True, "no_edge": True, "full_cover_dice": -2}
# Surprise (p. 108): Reaction + Intuition (3); failures can't act or spend Edge in the first round.
SURPRISE = {"pool": ("Reaction", "Intuition"), "threshold": 3}
# Nauseated: Body + Willpower (2) at the start of each round; fail = no actions, success = lose a Minor.
NAUSEA_TEST = {"pool": ("Body", "Willpower"), "threshold": 2}
# Statuses that cancel each other (p. 52-54): Wet or Chilled puts out Burning, Burning dries Wet and Chilled.
STATUS_CANCELS = {"Burning": ("Wet", "Chilled"), "Wet": ("Burning",), "Chilled": ("Burning",)}
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
    "Restrained":  {"defense": -4},
    "Stilled":     {"dr": -10},
    "Zapped":      {"attack": -1, "defense": -1, "init": -2},
}
# Prone: +2 Defense against ranged attacks from Medium or farther, −2 against Close/Near; the prone
# attacker has −4 with melee and bows, and +2 Attack Rating with firearms and other projectile weapons.
PRONE = {"defense_far": 2, "defense_near": -2, "far_ranges": ("Medium", "Far", "Extreme"),
         "melee_or_bow": -4, "firearm_ar": 2}
WET_SOAK = -6                # Wet: resisting cold and electricity

# Ongoing damage at the start of each round: (status, element, value drops by)
ONGOING = {"Burning": ("Fire", 0), "Corrosive": ("Chemical", 0), "Poisoned": ("Toxin", 1)}

# ---------------------------------------------------------------- magic in combat
SUSTAIN_PENALTY = -2         # per spell a character sustains themselves
# Counterspelling, boosted defense (p. 143): a Major Action, Sorcery + Magic; the hits are added to the
# Defense tests of everyone in the area against spells for Magic combat rounds.
COUNTERSPELL = {"action": "major", "pool": ("Sorcery", "Magic"),
                "desc": "Major Action: roll Sorcery + Magic; the hits add to everyone protected's Defense tests against spells for Magic rounds."}

# Dispelling (p. 143): a Counterspell Major Action against a sustained spell: Sorcery + Magic vs Drain Value x 2.
# Net hits cancel the spell's net hits one for one; at zero it is dispelled.
DISPEL = {"action": "major", "pool": ("Sorcery", "Magic"), "resist": "drain_x2",
          "desc": "Major Action against a sustained spell: Sorcery + Magic vs its Drain Value × 2; each net hit cancels one of the spell's hits."}

# Astral combat (p. 161): Attack Rating Magic + tradition attribute, Defense Rating Intuition (+ innate armor);
# unarmed Astral + Willpower vs Intuition + Logic, DV tradition attribute / 2 (round up) + net hits, resisted
# with Willpower; the attacker chooses Physical or Stun.
ASTRAL = {"attack": ("Astral", "Willpower"), "defense": ("Intuition", "Logic"), "soak": ("Willpower",),
          "dr": "Intuition", "dv_half": True, "type": "S",
          "weapon_focus": "Weapon foci: Close Combat + Willpower, the weapon's DV."}

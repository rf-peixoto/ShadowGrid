"""Shadowrun Sixth World core rulebook magic and resonance data (stats only).

Descriptions are short summaries written for this app.
Spell fields: category, kind (Direct/Indirect for combat; Single/Multi-Sense
for illusions), range (LOS, LOS (A), Touch), type (P physical / M mana),
duration (I instant, S sustained, P permanent, L limited), dv (drain value),
damage (S/P for combat spells), area (bool).
"""


def _s(name, category, rng, typ, dur, dv, desc, kind="", damage="", element=""):
    return {"name": name, "category": category, "kind": kind, "range": rng, "type": typ,
            "duration": dur, "drain": dv, "damage": damage, "element": element,
            "area": "(A)" in rng.replace(" ", "").replace("LOS(A)", "(A)") or rng.endswith("(A)"),
            "desc": desc}


SPELLS = [
    # --- Combat (p. 132-134) ---
    _s("Acid Stream", "Combat", "LOS", "P", "I", 5, "Acid damage plus the Corroded status (net hits).", "Indirect", "P", "Chemical"),
    _s("Toxic Wave", "Combat", "LOS (A)", "P", "I", 6, "Area acid attack; Corroded status (net hits).", "Indirect", "P", "Chemical"),
    _s("Clout", "Combat", "LOS", "P", "I", 3, "Shaped air strikes one target.", "Indirect", "S"),
    _s("Blast", "Combat", "LOS (A)", "P", "I", 4, "Area version of Clout.", "Indirect", "S"),
    _s("Flamestrike", "Combat", "LOS", "P", "I", 5, "Fire damage plus Burning (net hits).", "Indirect", "P", "Fire"),
    _s("Fireball", "Combat", "LOS (A)", "P", "I", 6, "Area fire damage plus Burning (net hits).", "Indirect", "P", "Fire"),
    _s("Ice Spear", "Combat", "LOS", "P", "I", 5, "Cold damage plus Chilled for net hits rounds.", "Indirect", "P", "Cold"),
    _s("Ice Storm", "Combat", "LOS (A)", "P", "I", 6, "Area cold damage plus Chilled.", "Indirect", "P", "Cold"),
    _s("Lightning Bolt", "Combat", "LOS", "P", "I", 5, "Electrical damage plus Zapped for net hits turns.", "Indirect", "P", "Electricity"),
    _s("Lightning Ball", "Combat", "LOS (A)", "P", "I", 6, "Area electrical damage plus Zapped.", "Indirect", "P", "Electricity"),
    _s("Manabolt", "Combat", "LOS", "M", "I", 4, "Raw mana damage to one living target.", "Direct", "P"),
    _s("Manaball", "Combat", "LOS (A)", "M", "I", 5, "Area version of Manabolt.", "Direct", "P"),
    _s("Powerbolt", "Combat", "LOS", "P", "I", 4, "Physical damage to one target (also affects objects).", "Direct", "P"),
    _s("Powerball", "Combat", "LOS (A)", "P", "I", 5, "Area version of Powerbolt.", "Direct", "P"),
    _s("Stunbolt", "Combat", "LOS", "M", "I", 3, "Mana Stun damage to one target.", "Direct", "S"),
    _s("Stunball", "Combat", "LOS (A)", "M", "I", 4, "Area version of Stunbolt.", "Direct", "S"),
    # --- Detection (p. 134-135) ---
    _s("Analyze Device", "Detection", "Touch", "P", "S", 2, "Learn a device's function; Edge on its first use while sustained."),
    _s("Analyze Magic", "Detection", "Touch", "P", "S", 3, "Read a magical effect as if assensing."),
    _s("Analyze Truth", "Detection", "Touch", "M", "S", 3, "Sense whether a heard statement is true."),
    _s("Clairaudience", "Detection", "Touch", "M", "S", 3, "Hear sounds at a distant spot."),
    _s("Clairvoyance", "Detection", "Touch", "M", "S", 3, "See sights at a distant spot."),
    _s("Combat Sense", "Detection", "Touch", "M", "S", 3, "Net hits add to Defense Rating and Surprise tests."),
    _s("Detect Enemies", "Detection", "Touch", "M", "S", 3, "Sense people with hostile intent toward the subject."),
    _s("Detect Life", "Detection", "Touch", "M", "S", 3, "Locate sentient beings in range."),
    _s("Detect Magic", "Detection", "Touch", "M", "S", 4, "Sense active magic: foci, spells, spirits, wards."),
    _s("Mindlink", "Detection", "Touch", "M", "S", 3, "Mental communication between caster and subject."),
    _s("Mind Probe", "Detection", "Touch", "P", "S", 5, "Read thoughts and memories (vs Willpower + Logic)."),
    # --- Health (p. 135-137) ---
    _s("Antidote", "Health", "Touch", "P", "P", 5, "Extended test; each net hit reduces a toxin's power by 1."),
    _s("Cleansing Heal", "Health", "Touch", "P", "P", 5, "Heal (threshold 5 - Essence) and remove Corroded."),
    _s("Cooling Heal", "Health", "Touch", "P", "P", 5, "Heal (threshold 5 - Essence) and remove Burning."),
    _s("Decrease Attribute", "Health", "Touch", "P", "S", 3, "Lower one attribute by net hits (+1 drain per extra point)."),
    _s("Heal", "Health", "Touch", "P", "P", 3, "Threshold 5 - Essence; heal 1 box of Stun, Physical or Overflow per net hit."),
    _s("Increase Attribute", "Health", "Touch", "P", "S", 3, "Raise one attribute by net hits (max +4; +1 drain per extra point)."),
    _s("Increase Reflexes", "Health", "Touch", "P", "S", 5, "+1 Reaction and +1 Initiative Die per net hit (+1 drain per extra)."),
    _s("Resist Pain", "Health", "Touch", "M", "S", 3, "Each net hit ignores 1 point of wound modifiers."),
    _s("Stabilize", "Health", "Touch", "M", "P", 3, "Threshold = Overflow boxes; success removes all Overflow."),
    _s("Warming Heal", "Health", "Touch", "P", "P", 5, "Heal (threshold 5 - Essence) and remove Chilled."),
    # --- Illusion (p. 137-138) ---
    _s("Agony", "Illusion", "LOS", "M", "S", 3, "Each net hit counts as a damage box for wound modifiers.", "Single-Sense"),
    _s("Confusion", "Illusion", "LOS", "M", "S", 3, "Confused status equal to net hits.", "Multi-Sense"),
    _s("Chaos", "Illusion", "LOS", "P", "S", 4, "Confusion that also affects technology.", "Multi-Sense"),
    _s("Hush", "Illusion", "Touch", "M", "S", 3, "Silent status equal to net hits.", "Single-Sense"),
    _s("Silence", "Illusion", "Touch", "P", "S", 4, "Silent (Improved) status; fools microphones too.", "Single-Sense"),
    _s("Invisibility", "Illusion", "Touch", "M", "S", 3, "Invisible status equal to net hits.", "Single-Sense"),
    _s("Improved Invisibility", "Illusion", "Touch", "P", "S", 4, "Invisible (Improved); fools cameras too.", "Single-Sense"),
    _s("Mask", "Illusion", "Touch", "M", "S", 3, "Change the subject's appearance, voice and scent.", "Multi-Sense"),
    _s("Physical Mask", "Illusion", "Touch", "P", "S", 4, "Mask that also fools technology.", "Multi-Sense"),
    _s("Phantasm", "Illusion", "LOS (A)", "M", "S", 3, "Project a convincing illusion to living viewers.", "Multi-Sense"),
    _s("Trid Phantasm", "Illusion", "LOS (A)", "P", "S", 4, "Phantasm that also fools cameras and sensors.", "Multi-Sense"),
    _s("Sensor Sneak", "Illusion", "Touch", "P", "S", 2, "Invisible (Improved) to technology only.", "Multi-Sense"),
    # --- Manipulation (p. 139-142) ---
    _s("Animate Metal", "Manipulation", "LOS", "P", "L", 6, "Animate metal (vs Object Resistance); can strike for 4P."),
    _s("Animate Plastic", "Manipulation", "LOS", "P", "L", 3, "Animate plastic; can strike for 1S."),
    _s("Animate Stone", "Manipulation", "LOS", "P", "L", 5, "Animate stone; can strike for 3P."),
    _s("Animate Wood", "Manipulation", "LOS", "P", "L", 4, "Animate wood; can strike for 2S."),
    _s("Armor", "Manipulation", "Touch", "P", "S", 4, "Net hits add to the target's Defense Rating."),
    _s("Control Actions", "Manipulation", "LOS", "M", "L", 4, "Puppet a target (vs Willpower + Logic) for net hits minutes."),
    _s("Control Thoughts", "Manipulation", "LOS", "M", "L", 4, "Plant thoughts in a target (vs Willpower + Logic)."),
    _s("Darkness", "Manipulation", "LOS (A)", "P", "S", 3, "Lower the light level by net hits."),
    _s("Light", "Manipulation", "LOS (A)", "P", "S", 3, "Raise the light level by net hits."),
    _s("Elemental Armor", "Manipulation", "Touch", "M", "S", 5, "Armor plus immunity to one elemental status (fire, electricity, chemical or cold)."),
    _s("Fling", "Manipulation", "LOS", "P", "I", 5, "Hurl half a kilo per net hit; AR Magic/Magic+2/Magic+1/Magic-2/—, Stun = kg."),
    _s("Focus Burst", "Manipulation", "Touch", "M", "L", 7, "Raise a focus's rating by 1 for net hits minutes (vs Force x 2)."),
    _s("Levitate", "Manipulation", "LOS", "P", "S", 6, "Lift 50 kg per net hit; move it Magic meters per turn."),
    _s("Mana Barrier", "Manipulation", "LOS (A)", "M", "S", 5, "Astral wall, Structure = net hits + Magic."),
    _s("Mystic Armor", "Manipulation", "Touch", "P", "S", 3, "Net hits add to Defense Rating in astral combat and against mana spells."),
    _s("Overclock", "Manipulation", "LOS", "P", "S", 4, "Raise a device's Matrix attribute by net hits; it takes Matrix damage after."),
    _s("Physical Barrier", "Manipulation", "LOS (A)", "P", "S", 6, "Wall with Structure = Magic + hits."),
    _s("Shape Metal", "Manipulation", "LOS", "P", "S", 5, "Reshape 1 cubic meter of metal per net hit."),
    _s("Shape Plastic", "Manipulation", "LOS", "P", "S", 2, "Reshape plastic."),
    _s("Shape Stone", "Manipulation", "LOS", "P", "S", 4, "Reshape stone."),
    _s("Shape Wood", "Manipulation", "LOS", "P", "S", 3, "Reshape wood."),
    _s("Strengthen Wall", "Manipulation", "LOS (A)", "P", "S", 4, "Net hits add to a wall's Structure."),
    _s("Thunder", "Manipulation", "LOS (A)", "P", "S", 3, "Loud din; net hits are a penalty to hearing tests."),
    _s("Vehicle Armor", "Manipulation", "Touch", "M", "S", 6, "Net hits add to a vehicle's Armor."),
]

# Drain resistance: Willpower + tradition attribute (p. 128).
TRADITIONS = {"Hermetic": "Logic", "Shamanic": "Charisma"}

# Spell adjustments (p. 131): Amp Up +2 drain per +1 base damage (combat only);
# Increase Area +1 drain per +2 m radius.
AMP_UP_DRAIN = 2
INCREASE_AREA_DRAIN = 1
SUSTAIN_PENALTY = 2

RITUALS = [
    {"name": "Circle of Healing", "keywords": "Anchored, Spell", "threshold": 7, "time": "5 hours",
     "desc": "Cast a Health spell on everyone in a sphere (radius = leader's Magic); lasts net hits days."},
    {"name": "Circle of Protection", "keywords": "Anchored", "threshold": 6, "time": "4 hours",
     "desc": "Dual-natured barrier sphere, Structure = Magic + net hits; lasts net hits hours."},
    {"name": "Curse", "keywords": "Material Link, Spell", "threshold": 5, "time": "3 hours",
     "desc": "Cast an Illusion spell through a material link."},
    {"name": "Prodigal Spell", "keywords": "Spell, Spotter", "threshold": 6, "time": "4 hours",
     "desc": "Cast a Combat spell at a target out of line of sight."},
    {"name": "Remote Sensing", "keywords": "Spell, Spotter", "threshold": 5, "time": "3 hours",
     "desc": "Detection spell with range (Magic + hits) x 100 m."},
    {"name": "Renascence", "keywords": "Anchored, Spell", "threshold": 6, "time": "4 hours",
     "desc": "Maintain an area Manipulation spell; 1 hour doubled per net hit."},
    {"name": "Ward", "keywords": "Anchored", "threshold": 6, "time": "",
     "desc": "Creates a mana barrier around an area."},
    {"name": "Watcher", "keywords": "Minion", "threshold": 4, "time": "1 hour",
     "desc": "Creates a watcher bound to the leader for net hits x 3 hours; skills 2."},
]

# Spirits (p. 147-149). Attributes are offsets from Force; skills are at Force.
SPIRITS = {
    "Air": {
        "attrs": {"Body": -2, "Agility": 3, "Reaction": 4, "Strength": -3, "Willpower": 0, "Logic": 0,
                  "Intuition": 0, "Charisma": 0, "Magic": 0, "Essence": 0},
        "init": "F*2+4", "init_dice": 2, "astral_init": "F*2", "astral_dice": 3, "dr": "F-2", "move": "5/10/+5",
        "skills": ["Astral", "Athletics", "Close Combat", "Exotic Weapons", "Perception"],
        "powers": ["Accident", "Astral Form", "Concealment", "Confusion", "Engulf (Air)", "Materialization",
                   "Movement", "Sapience", "Search"],
        "optional": ["Elemental Attack (Cold)", "Elemental Attack (Electricity)", "Energy Aura", "Fear", "Guard",
                     "Noxious Breath", "Psychokinesis"],
        "attacks": [{"name": "Elemental Attack", "dv": "F", "type": "P", "ar": "F*2/F*2-2/F*2-8/F*2-10/—"},
                    {"name": "Engulf", "dv": "F+2", "type": "S", "ar": "F*2+1/—/—/—/—", "note": "+ Fatigued I"}],
    },
    "Beasts": {
        "attrs": {"Body": 2, "Agility": 1, "Reaction": 0, "Strength": 2, "Willpower": 0, "Logic": 0,
                  "Intuition": 0, "Charisma": 0, "Magic": 0, "Essence": 0},
        "init": "F*2", "init_dice": 2, "dr": "F", "move": "5/10/+3",
        "skills": ["Astral", "Close Combat", "Perception"],
        "powers": ["Animal Control", "Astral Form", "Enhanced Senses (hearing, low-light vision, smell)", "Fear",
                   "Materialization", "Movement", "Sapience"],
        "optional": ["Concealment", "Confusion", "Guard", "Natural Weapon (claws/bite)", "Noxious Breath", "Search", "Venom"],
        "attacks": [{"name": "Claw/bite", "dv": "ceil(F/2)", "type": "P", "ar": "F*2/—/—/—/—"}],
    },
    "Earth": {
        "attrs": {"Body": 4, "Agility": -2, "Reaction": -1, "Strength": 4, "Willpower": 0, "Logic": -1,
                  "Intuition": 0, "Charisma": 0, "Magic": 0, "Essence": 0},
        "init": "F*2-1", "init_dice": 2, "dr": "F+4", "move": "5/10/+1",
        "skills": ["Astral", "Close Combat", "Exotic Weapons", "Perception"],
        "powers": ["Astral Form", "Binding", "Guard", "Materialization", "Movement", "Sapience", "Search"],
        "optional": ["Concealment", "Confusion", "Elemental Attack (Chemical)", "Engulf (Earth)", "Fear"],
        "attacks": [{"name": "Elemental Attack", "dv": "F", "type": "P", "ar": "F*2/F*2-2/F*2-8/F*2-10/—"}],
    },
    "Fire": {
        "attrs": {"Body": 1, "Agility": 2, "Reaction": 3, "Strength": -2, "Willpower": 0, "Logic": 0,
                  "Intuition": 1, "Charisma": 0, "Magic": 0, "Essence": 0},
        "init": "F*2+4", "init_dice": 2, "dr": "F+1", "move": "5/10/+5",
        "skills": ["Astral", "Athletics", "Close Combat", "Exotic Weapons", "Perception"],
        "powers": ["Accident", "Astral Form", "Confusion", "Elemental Attack (Fire)", "Energy Aura (Fire)",
                   "Engulf (Fire)", "Materialization", "Sapience"],
        "optional": ["Fear", "Guard", "Noxious Breath", "Search"],
        "attacks": [{"name": "Elemental Attack (Fire)", "dv": "F", "type": "P", "ar": "F*2/F*2-2/F*2-8/F*2-10/—"},
                    {"name": "Engulf", "dv": "F+2", "type": "S", "ar": "F*2+1/—/—/—/—", "note": "+ Fatigued I"}],
    },
    "Kin": {
        "attrs": {"Body": 1, "Agility": 0, "Reaction": 2, "Strength": -2, "Willpower": 0, "Logic": 0,
                  "Intuition": 1, "Charisma": 0, "Magic": 0, "Essence": 0},
        "init": "F*2+3", "init_dice": 2, "dr": "F+1", "move": "5/10/+1",
        "skills": ["Astral", "Close Combat", "Perception", "Sorcery"],
        "powers": ["Accident", "Astral Form", "Concealment", "Confusion",
                   "Enhanced Senses (low-light, thermographic)", "Guard", "Influence", "Materialization",
                   "Sapience", "Search"],
        "optional": ["Fear", "Innate Spell (one spell the summoner knows)", "Movement", "Psychokinesis"],
        "attacks": [{"name": "Fists", "dv": "ceil(F/2)", "type": "S", "ar": "F*2/—/—/—/—"}],
    },
    "Water": {
        "attrs": {"Body": 0, "Agility": 1, "Reaction": 2, "Strength": 0, "Willpower": 0, "Logic": 0,
                  "Intuition": 0, "Charisma": 0, "Magic": 0, "Essence": 0},
        "init": "F*2+2", "init_dice": 2, "dr": "F", "move": "5/10/+2",
        "skills": ["Astral", "Athletics", "Close Combat", "Exotic Weapons", "Perception"],
        "powers": ["Astral Form", "Concealment", "Confusion", "Engulf (Water)", "Materialization", "Movement",
                   "Sapience", "Search"],
        "optional": ["Accident", "Binding", "Elemental Attack (Cold)", "Energy Aura (Cold)", "Guard", "Weather Control"],
        "weakness": "Allergy (fire, severe)",
        "attacks": [{"name": "Elemental Attack", "dv": "F", "type": "P", "ar": "F*2/F*2-2/F*2-8/F*2-10/—"},
                    {"name": "Engulf", "dv": "F+2", "type": "S", "ar": "F*2+1/—/—/—/—", "note": "+ Fatigued I"}],
    },
}
# Summoning (p. 146): Conjuring + Magic vs Force x 2; services = net hits;
# drain = spirit's hits (Physical if above Magic). Total active Force <= Magic x 3.
# One optional power per 3 full points of Force. Condition monitor (F/2)+8.

ADEPT_POWERS = [
    {"name": "Adrenaline Boost", "cost": 0.25, "levels": True, "activation": "Minor",
     "desc": "+2 Initiative score per level for Magic rounds, then drain equal to level."},
    {"name": "Astral Perception", "cost": 1.0, "activation": "Minor", "desc": "Perceive astrally (dual-natured)."},
    {"name": "Attribute Boost", "cost": 0.25, "levels": True, "activation": "Major", "choice": "Physical attribute",
     "desc": "Roll Magic + level; hits boost the attribute for dice pools for net hits rounds, then drain."},
    {"name": "Combat Sense", "cost": 0.5, "levels": True, "activation": "Passive",
     "desc": "+1 die per level on defense tests; always a Perception test against surprise.", "effect": "defense_dice"},
    {"name": "Critical Strike", "cost": 1.0, "levels": True, "activation": "Passive",
     "desc": "+1 DV per level to melee attacks.", "effect": "melee_dv"},
    {"name": "Danger Sense", "cost": 0.5, "activation": "Passive", "desc": "Gain an Edge before Surprise tests."},
    {"name": "Direction Sense", "cost": 0.25, "activation": "Passive", "desc": "Edge on direction-related Outdoors tests."},
    {"name": "Enhanced Accuracy", "cost": 0.5, "activation": "Passive", "desc": "+2 Attack Rating with any weapon.",
     "effect": "weapon_ar"},
    {"name": "Enhanced Perception", "cost": 0.5, "activation": "Passive", "desc": "Edge on Observe in Detail and searching Perception tests."},
    {"name": "Improved Ability", "cost": 0.5, "combat_cost": 1.0, "levels": True, "activation": "Passive", "choice": "Skill",
     "desc": "+level to one skill (max 1.5 x rank). Combat skills cost 1 PP per level.", "effect": "skill"},
    {"name": "Improved Physical Attribute", "cost": 1.0, "levels": True, "activation": "Passive", "choice": "Physical attribute",
     "desc": "+level to one Physical attribute.", "effect": "attribute"},
    {"name": "Improved Reflexes", "cost": 1.0, "levels": True, "max": 4, "activation": "Passive",
     "desc": "+1 Reaction and +1 Initiative Die per level; not with other boosts.", "effect": "reflexes"},
    {"name": "Improved Sense", "cost": 0.25, "activation": "Passive", "choice": "Sense",
     "desc": "Bonus Edge on tests using the chosen sense."},
    {"name": "Killing Hands", "cost": 0.5, "activation": "Minor", "desc": "Unarmed attacks may do Physical damage and are magical."},
    {"name": "Kinesics", "cost": 0.25, "activation": "Passive", "desc": "Edge when resisting social tests and reads of your emotions."},
    {"name": "Mystic Armor", "cost": 0.25, "levels": True, "activation": "Passive",
     "desc": "+1 Armor (Defense Rating) per level, also astral.", "effect": "dr"},
    {"name": "Pain Resistance", "cost": 0.25, "levels": True, "activation": "Passive",
     "desc": "Wound modifiers start one box later per level.", "effect": "pain"},
    {"name": "Rapid Healing", "cost": 0.5, "levels": True, "activation": "Passive", "desc": "+1 hit per level on healing tests.",
     "effect": "heal_hits"},
    {"name": "Spell Resistance", "cost": 0.5, "levels": True, "activation": "Passive", "desc": "Gain Edge when targeted by spells."},
    {"name": "Traceless Walk", "cost": 0.5, "activation": "Passive", "desc": "Leave no tracks; trackers can't use Edge."},
    {"name": "Vocal Control", "cost": 0.5, "activation": "Passive", "desc": "Edge on voice-based Con or Influence tests."},
    {"name": "Wall Running", "cost": 0.5, "activation": "Minor", "desc": "Sprint up vertical surfaces."},
]
# Mystic adepts buy power points for 5 Karma each after creation (max = Magic).
MYSTIC_PP_KARMA = 5

METAMAGICS = [
    {"name": "Adept Centering", "adept_only": True, "desc": "Foes can't gain Edge from environment or illusions against you."},
    {"name": "Centering", "desc": "Add Initiate Grade dice to drain resistance (Minor Action to center)."},
    {"name": "Fixation", "desc": "Spend Karma to slow a preparation's Potency decay."},
    {"name": "Flexible Signature", "desc": "Disguise, forge or shorten your astral signature."},
    {"name": "Masking", "desc": "Disguise your aura and up to Grade bonded foci."},
    {"name": "Power Point", "adept_only": True, "repeatable": True, "desc": "Gain a power point instead of a metamagic."},
    {"name": "Quickening", "desc": "Spend Karma to make a sustained spell permanent."},
    {"name": "Shielding", "desc": "Add Initiate Grade dice to Boosted Defense counterspelling."},
    {"name": "Spell Shaping", "desc": "Trade spellcasting dice to reshape an area spell without extra drain."},
]
# Initiation (p. 167): Karma 10 + new grade; grade <= Magic; max Magic = 6 + grade.

MENTOR_SPIRITS = {
    "Bear": "All: Edge Boosts cost 1 less to resist damage (not drain). Magician: Health spells. Adept: 1 free level of Rapid Healing. Disadvantage: may go berserk when wounded.",
    "Cat": "All: Edge Boosts cost 1 less for Athletics or Stealth. Magician: Illusion spells. Adept: free Traceless Walk. Disadvantage: toys with prey.",
    "Coyote": "All: Edge Boosts cost 1 less for Con. Magician: Manipulation spells. Adept: free Vocal Control. Disadvantage: can't resist a trick.",
    "Dog": "All: Edge Boosts cost 1 less for Outdoors. Magician: Detection spells. Adept: 2 free Improved Sense powers. Disadvantage: stubbornly loyal.",
    "Dragonslayer": "All: Edge Boosts cost 1 less for Influence. Magician: Combat spells. Adept: free Danger Sense. Disadvantage: -1 to all actions after breaking a promise.",
    "Eagle": "All: Edge Boosts cost 1 less for Perception. Magician: summoning air spirits. Adept: 1 free level of Combat Sense. Disadvantage: Allergy (pollutants, mild).",
    "Fire-Bringer": "All: Edge Boosts cost 1 less for Engineering or Enchanting. Magician: Manipulation spells. Adept: 1 free level of Improved Ability (non-combat). Disadvantage: can't refuse a sincere request for help.",
    "Mountain": "All: Edge Boosts cost 1 less for Outdoors. Magician: counterspelling and anchored rituals. Adept: 2 free levels of Mystic Armor. Disadvantage: sticks to the plan.",
    "Rat": "All: Edge Boosts cost 1 less for Stealth. Magician: Enchanting when harvesting reagents. Adept: 1 free level of Pain Resistance. Disadvantage: flees combat.",
    "Sea": "All: Edge Boosts cost 1 less for swimming; +1 m swim rate. Magician: summoning water spirits. Adept: 1 free level of Improved Ability (Athletics). Disadvantage: greedy.",
    "Seducer": "All: Edge Boosts cost 1 less for Con. Magician: Illusion spells. Adept: 1 free level of Improved Ability (Con or Influence). Disadvantage: pursues vices.",
    "Shark": "All: Edge Boosts cost 1 less for Close Combat with blades or unarmed. Magician: Combat spells. Adept: free Killing Hands. Disadvantage: may go berserk.",
    "Snake": "All: 2 free magic Knowledge skills. Magician: Detection spells. Adept: free Kinesics. Disadvantage: chases secrets.",
    "Thunderbird": "All: Edge Boosts cost 1 less for Influence. Magician: summoning air spirits. Adept: 1 free level of Critical Strike. Disadvantage: answers insults in kind.",
    "Wise Warrior": "All: Edge Boosts cost 1 less for Influence. Magician: Combat spells. Adept: 1 free level of Improved Ability (combat). Disadvantage: -1 to all actions after acting dishonorably.",
    "Wolf": "All: Edge Boosts cost 1 less for Counterspelling. Magician: Combat spells. Adept: 2 free levels of Attribute Boost (Agility). Disadvantage: won't retreat.",
}

# ---------------------------------------------------------------------------
# Matrix and resonance (p. 170-195)
PROGRAMS = {
    "Basic": {
        "Baby Monitor": "Always know your Overwatch Score.",
        "Browse": "1 Edge on Matrix Search (spend immediately).",
        "Configurator": "Store an alternate attribute setup and switch to it at once.",
        "Edit": "1 Edge on Edit File (spend immediately).",
        "Encryption": "+2 dice on Encrypt File.",
        "Signal Scrubber": "Reduce noise by 2.",
        "Toolbox": "+1 Data Processing.",
        "Virtual Machine": "2 more program slots; you take 1 extra box of Matrix damage when attacked.",
    },
    "Hacking": {
        "Armor": "+2 Defense Rating.",
        "Biofeedback": "Matrix attacks also do Stun (cold-sim) or Physical (hot-sim) damage.",
        "Biofeedback Filter": "Soak Matrix damage with Device Rating or Body.",
        "Blackout": "Matrix attacks also do Stun damage.",
        "Decryption": "+2 dice on Crack File.",
        "Defuse": "Soak data bomb damage with Device Rating or Body.",
        "Exploit": "-2 Defense Rating for your hacking target.",
        "Fork": "Hit two targets with one Matrix action.",
        "Lockdown": "Link-lock the target when you do Matrix damage.",
        "Overclock": "+2 dice on a Matrix action; one must be the Wild Die.",
        "Stealth": "1 Edge on Hide actions.",
        "Trace": "1 Edge on Trace Icon actions.",
    },
}
# Matrix initiative (p. 179): AR = REA + INT + 1D6; cold-sim VR = INT + Data
# Processing + 2D6; hot-sim VR = INT + Data Processing + 3D6 (max 5D6).
MATRIX_INIT = {"AR": ("Reaction", 1), "VR (cold sim)": ("Data Processing", 2), "VR (hot sim)": ("Data Processing", 3)}
# Matrix Attack Rating = Attack + Sleaze; Defense Rating = Data Processing + Firewall.
# Device Matrix Condition Monitor = ceil(Device Rating / 2) + 8.

# Living persona (p. 189): Attack = CHA, Sleaze = INT, Data Processing = LOG,
# Firewall = WIL, plus Resonance bonus points (each attribute +50% max, +4 max).
LIVING_PERSONA = {"attack": "Charisma", "sleaze": "Intuition", "data_processing": "Logic", "firewall": "Willpower"}

# Complex forms (p. 189-191): fading resisted with Willpower + Logic;
# Physical if above Resonance. AR = Electronics + Resonance. -2 per sustained form.
COMPLEX_FORMS = [
    {"name": "Cleaner", "fade": 2, "duration": "P", "desc": "Each hit reduces your Overwatch Score by 1."},
    {"name": "Diffusion", "fade": 4, "duration": "S", "choice": "Matrix attribute",
     "desc": "Electronics + Resonance vs Willpower + Firewall; net hits lower the target's attribute (min 1)."},
    {"name": "Editor", "fade": 3, "duration": "P", "desc": "Edit File without the proper access level."},
    {"name": "Emulate", "fade": 0, "duration": "S", "choice": "Program",
     "desc": "Run one program (or autosoft at Data Processing rating)."},
    {"name": "Infusion", "fade": 4, "duration": "S", "choice": "Matrix attribute",
     "desc": "Electronics + Resonance (4); net hits raise the attribute (up to double)."},
    {"name": "Mirrored Persona", "fade": 3, "duration": "I", "desc": "Create a proxy persona; hits are its rating."},
    {"name": "Pulse Storm", "fade": 3, "duration": "I", "desc": "vs Logic + Data Processing; net hits raise the target's noise."},
    {"name": "Puppeteer", "fade": 5, "duration": "S", "desc": "Control Device without the proper access level."},
    {"name": "Resonance Channel", "fade": 2, "duration": "S", "desc": "Each hit reduces your noise by 1."},
    {"name": "Resonance Spike", "fade": 4, "duration": "I", "desc": "Cracking + Resonance vs Willpower + Firewall; net hits = Matrix damage."},
    {"name": "Resonance Veil", "fade": 4, "duration": "S", "desc": "Matrix illusion; net hits are the Matrix Perception threshold."},
    {"name": "Static Bomb", "fade": 6, "duration": "I", "desc": "vs Intuition + Data Processing; those without net hits lose track of you."},
    {"name": "Static Veil", "fade": 3, "duration": "S", "desc": "Target accumulates no Overwatch Score from holding host access."},
    {"name": "Stitches", "fade": 4, "duration": "P", "desc": "Each net hit repairs 1 box of Matrix damage."},
    {"name": "Tattletale", "fade": 3, "duration": "P", "desc": "Each hit raises the target's Overwatch Score by 1."},
    {"name": "Transcend Grid", "fade": 0, "duration": "—", "desc": "No penalty for acting across grids."},
]

# Sprites (p. 193): attributes as offsets from Level; Initiative (L x 2) + n + 4D6.
SPRITES = {
    "Courier": {"attack": 0, "sleaze": 3, "data_processing": 1, "firewall": 2, "init": 1,
                "skills": ["Electronics", "Cracking"], "powers": ["Cookie", "Hash"]},
    "Crack": {"attack": 0, "sleaze": 3, "data_processing": 2, "firewall": 1, "init": 2,
              "skills": ["Electronics", "Cracking"], "powers": ["Phantom", "Suppression"]},
    "Data": {"attack": -1, "sleaze": 0, "data_processing": 4, "firewall": 1, "init": 4,
             "skills": ["Electronics", "Cracking"], "powers": ["Camouflage", "Watermark"]},
    "Fault": {"attack": 3, "sleaze": 0, "data_processing": 1, "firewall": 2, "init": 1,
              "skills": ["Electronics", "Cracking"], "powers": ["Electron Storm", "Trap"]},
    "Machine": {"attack": 1, "sleaze": 0, "data_processing": 3, "firewall": 2, "init": 3,
                "skills": ["Electronics", "Engineering"], "powers": ["Diagnostics", "Override", "Stability"]},
}
# Compiling: Tasking + Resonance vs Level x 2; tasks = net hits; fading = sprite's hits.
# One unregistered sprite; registered sprites <= Resonance.

ECHOES = [
    {"name": "Living Network", "desc": "Your living persona can be a PAN master device."},
    {"name": "Machine Mind", "desc": "Benefits of a rating 1 control rig."},
    {"name": "Matrix Attribute Upgrade", "repeatable": True, "desc": "+1 to one living persona attribute (each at most twice)."},
    {"name": "NeuroFilter", "repeatable": True, "desc": "+1 die to resist biofeedback (max twice)."},
    {"name": "Overclocking", "desc": "+1 Minor Action and +1D6 Initiative in hot-sim VR."},
    {"name": "Resonance Link", "desc": "One-way empathic link with another technomancer."},
    {"name": "Skinlink", "desc": "Connect to a device by touch as if by DNI."},
]
# Submersion: Karma 10 + new grade; max Resonance 6 + grade; one echo per grade.

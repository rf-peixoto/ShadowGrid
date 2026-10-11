"""Shadowrun 6E reference data: every predefined list from the original
Shadowrun Manager (gear, spells, powers, foci, qualities, skills, wiki).

Ported verbatim from character.py / gui_wiki.py; only the Matrix sketch
icons and the old house-rule Edge/roll lists were dropped (the dice engine
now follows the official 6E Edge Boosts, see sr/dice.py).
"""

METATYPES = ["Human", "Elf", "Dwarf", "Ork", "Troll"]
ATTRIBUTES = ["Body", "Agility", "Reaction", "Strength", "Willpower",
              "Logic", "Intuition", "Charisma", "Edge", "Magic",
              "Resonance", "Essence"]
SKILLS = ["Astral", "Athletics", "Biotech", "Close Combat", "Con",
          "Conjuring", "Cracking", "Electronics", "Enchanting", "Engineering",
          "Exotic Weapons", "Firearms", "Influence", "Outdoors", "Perception",
          "Piloting", "Sorcery", "Stealth", "Tasking"]

SKILL_SPECIALIZATIONS = {
    "Firearms": ["Pistols", "Rifles", "Shotguns", "Machine Guns"],
    "Close Combat": ["Blades", "Clubs", "Unarmed Combat"],
    "Stealth": ["Urban", "Wilderness", "Vehicle"],
    "Perception": ["Visual", "Auditory", "Scent"],
    "Con": ["Fast Talk", "Impersonation", "Seduction"],
    "Electronics": ["Cyberdecks", "Commlinks", "Security Systems"],
    "Engineering": ["Aeronautics", "Automotive", "Marine"],
    "Biotech": ["First Aid", "Medicine", "Cybertechnology"],
    "Cracking": ["Hacking", "Cybercombat", "Electronic Warfare"],
    "Tasking": ["Compiling", "Decompiling", "Registering"],
    "Sorcery": ["Combat Spells", "Health Spells", "Illusion Spells"],
    "Conjuring": ["Summoning", "Banishing", "Binding"],
    "Enchanting": ["Alchemy", "Disenchanting", "Artificing"],
    "Influence": ["Leadership", "Negotiation", "Intimidation"],
    "Outdoors": ["Navigation", "Survival", "Tracking"],
    "Piloting": ["Ground Craft", "Aircraft", "Watercraft"],
    "Astral": ["Astral Combat", "Astral Tracking", "Astral Perception"]
}

MAGIC_TYPES = ["Mundane", "Magician", "Adept", "Aspected Magician", "Mystic Adept", "Technomancer"]
LIFESTYLES = ["Street", "Squatter", "Low", "Middle", "High", "Luxury"]
LIFESTYLE_NUYEN = {
    "Street": 1000,
    "Squatter": 2000,
    "Low": 5000,
    "Middle": 10000,
    "High": 100000,
    "Luxury": 1000000
}

ROLES = {
    "Street Samurai": {"Body": 1, "Agility": 1},
    "Decker": {"Logic": 2, "Intuition": 1},
    "Rigger": {"Reaction": 2, "Logic": 1},
    "Face": {"Charisma": 2, "Intuition": 1},
    "Mage": {"Magic": 2, "Willpower": 1},
    "Shaman": {"Magic": 2, "Charisma": 1},
    "Adept": {"Magic": 2, "Agility": 1},
    "Technomancer": {"Resonance": 2, "Logic": 1}
}

TRADITIONS = ["None", "Hermetic", "Shamanic", "Christian Theurgy", "Buddhist", "Islamic", "Voodoo"]

QUALITIES = {
    "Positive": ["Adept", "Ambidextrous", "Analytical Mind", "Astral Chameleon",
                 "Blandness", "Catlike", "Double-Jointed", "Guts", "High Pain Tolerance",
                 "Home Ground", "Human-Looking", "Indomitable", "Juryrigger", "Lucky",
                 "Magical Resistance", "Natural Athlete", "Photographic Memory",
                 "Quick Healer", "Spirit Affinity", "Toughness", "Will to Live"],
    "Negative": ["Addiction", "Allergy", "Astral Beacon", "Bad Luck", "Bad Rep",
                 "Code of Honor", "Dependents", "Gremlins", "Incompetent", "Insomnia",
                 "Magic Sense", "Mild Phobia", "Sensitive System", "Simsense Vertigo",
                 "Social Stress", "Spirit Bane", "Uncouth", "Uneducated"]
}

# Every quality's mechanical effect and Karma cost. "karma" is the cost
# to take a positive quality (paid) or the Karma awarded for a negative
# one (stored negative -- see add_pos_quality/add_neg_quality in
# gui_skills.py). Any other key is either an attribute name (applied as
# a flat bonus in recalculate()) or one of the special keys "Physical
# Boxes"/"Stun Boxes" (added to the condition monitors). Qualities with
# no numeric mechanical effect still get a Karma cost so the economy
# works, even though recalculate() has nothing further to apply.
QUALITY_EFFECTS = {
    # -- Positive --
    "Adept": {"karma": 5},
    "Ambidextrous": {"Agility": 1, "karma": 6},
    "Analytical Mind": {"Logic": 1, "karma": 7},
    "Astral Chameleon": {"karma": 5},
    "Blandness": {"karma": 8},
    "Catlike": {"Agility": 1, "karma": 9},
    "Double-Jointed": {"karma": 6},
    "Guts": {"karma": 8},
    "High Pain Tolerance": {"Physical Boxes": 2, "Stun Boxes": 2, "karma": 7},
    "Home Ground": {"karma": 5},
    "Human-Looking": {"karma": 7},
    "Indomitable": {"Willpower": 1, "karma": 8},
    "Juryrigger": {"karma": 7},
    "Lucky": {"Edge": 1, "karma": 12},
    "Magical Resistance": {"karma": 10},
    "Natural Athlete": {"Strength": 1, "Agility": 1, "karma": 10},
    "Photographic Memory": {"karma": 7},
    "Quick Healer": {"karma": 8},
    "Spirit Affinity": {"karma": 7},
    "Toughness": {"Body": 1, "karma": 9},
    "Will to Live": {"Physical Boxes": 3, "karma": 7},
    # -- Negative (karma is negative: Karma awarded for taking it) --
    "Addiction": {"karma": -8},
    "Allergy": {"karma": -10},
    "Astral Beacon": {"karma": -5},
    "Bad Luck": {"karma": -12},
    "Bad Rep": {"karma": -7},
    "Code of Honor": {"karma": -8},
    "Dependents": {"karma": -8},
    "Gremlins": {"karma": -8},
    "Incompetent": {"Logic": -1, "Intuition": -1, "karma": -14},
    "Insomnia": {"karma": -8},
    "Magic Sense": {"karma": -5},
    "Mild Phobia": {"karma": -5},
    "Sensitive System": {"karma": -12},
    "Simsense Vertigo": {"karma": -5},
    "Social Stress": {"karma": -8},
    "Spirit Bane": {"karma": -8},
    "Uncouth": {"Charisma": -2, "karma": -12},
    "Uneducated": {"Logic": -2, "karma": -10},
}

GEAR_CATEGORIES = ["Weapons", "Armor", "Cyberware", "Bioware", "Magic Items", "Electronics", "Medkits", "Other"]
WEAPON_TYPES = ["Blades", "Clubs", "Thrown", "Pistols", "Rifles", "Shotguns", "Machine Guns", "Special"]
ARMOR_TYPES = ["Clothing", "Armor Jacket", "Full Body Armor", "Helmet", "Shield"]
CYBERWARE_TYPES = ["Headware", "Eyeware", "Earware", "Bodyware", "Cyberlimbs", "Implants"]
MEDKIT_TYPES = ["Rating 1", "Rating 3", "Rating 6", "Rating 10"]

CONTACT_TYPES = ["Fixer", "Johnson", "Gang", "Corporate", "Police", "Media", "Talislegger", "Decker", "Street Doc"]
LOYALTY_LEVELS = ["Unknown", "Known", "Transactional", "Regular", "Professional", "Respectful",
                  "Reliable", "Supportive", "Loyal", "Devoted", "Family"]



PREDEFINED_SPELLS = [
    {"name": "Power Bolt", "type": "Combat", "drain": "F-3", "description": "Direct combat spell that deals physical damage to a single target."},
    {"name": "Stun Bolt", "type": "Combat", "drain": "F-4", "description": "Direct combat spell that deals stun damage to a single target."},
    {"name": "Fireball", "type": "Combat", "drain": "F-1", "description": "Indirect combat spell dealing physical damage in an area."},
    {"name": "Lightning Bolt", "type": "Combat", "drain": "F-2", "description": "Indirect combat spell dealing physical damage, hard to resist with cover."},
    {"name": "Acid Stream", "type": "Combat", "drain": "F-3", "description": "Direct combat spell that also damages armor and gear."},
    {"name": "Heal", "type": "Health", "drain": "F-4", "description": "Heals physical damage on the target."},
    {"name": "Detox", "type": "Health", "drain": "F-3", "description": "Neutralizes toxins in the target's system."},
    {"name": "Increase Reflexes", "type": "Health", "drain": "F-2", "description": "Temporarily boosts the target's Reaction and initiative."},
    {"name": "Resist Pain", "type": "Health", "drain": "F-3", "description": "Suppresses wound modifiers for the duration."},
    {"name": "Invisibility", "type": "Illusion", "drain": "F-4", "description": "Makes the target very hard to see."},
    {"name": "Silence", "type": "Illusion", "drain": "F-4", "description": "Removes all sound from the area of effect."},
    {"name": "Mask", "type": "Illusion", "drain": "F-3", "description": "Changes the caster's or target's apparent appearance."},
    {"name": "Chaos", "type": "Illusion", "drain": "F-2", "description": "Floods a target's sense with confusing false input."},
    {"name": "Levitate", "type": "Manipulation", "drain": "F-2", "description": "Allows the target to float and move through the air."},
    {"name": "Control Thoughts", "type": "Manipulation", "drain": "F-1", "description": "Lets the caster direct the target's next thought or action."},
    {"name": "Magic Fingers", "type": "Manipulation", "drain": "F-4", "description": "Telekinetically manipulates small objects at a distance."},
    {"name": "Armor", "type": "Manipulation", "drain": "F-3", "description": "Grants the target temporary armor rating."},
    {"name": "Manabolt", "type": "Combat", "drain": "F-2", "description": "Direct combat spell resisted by Willpower alone -- ignores physical armor."},
    {"name": "Stunbolt", "type": "Combat", "drain": "F-3", "description": "Direct combat spell dealing stun damage, resisted by Willpower."},
    {"name": "Deadly Wind", "type": "Combat", "drain": "F+1", "description": "Indirect area combat spell that shreds anything caught in it."},
    {"name": "Antidote", "type": "Health", "drain": "F-2", "description": "Removes a specific toxin from the target's system."},
    {"name": "Cure Disease", "type": "Health", "drain": "F-1", "description": "Cures a disease afflicting the target."},
    {"name": "Trid Phantasm", "type": "Illusion", "drain": "F-3", "description": "Creates a realistic illusion affecting all senses."},
    {"name": "Physical Barrier", "type": "Manipulation", "drain": "F-2", "description": "Creates a solid, physical wall out of nothing."},
    {"name": "Fling", "type": "Manipulation", "drain": "F-3", "description": "Telekinetically hurls an object at a target as a weapon."},
]

PREDEFINED_POWERS = [
    {"name": "Improved Reflexes", "activation": "Passive", "effect": "+1 Reaction, +1D6 Initiative", "Reaction": "1", "Initiative Dice": "1", "Cost": "2.5", "description": "Improves reaction time and initiative."},
    {"name": "Combat Sense", "activation": "Passive", "effect": "+1 Defense Rating", "Cost": "1.5", "description": "Enhances combat awareness, granting a bonus to defense tests."},
    {"name": "Killing Hands", "activation": "Simple Action", "effect": "Unarmed attacks deal physical damage", "Cost": "0.5", "description": "Channels energy into unarmed strikes so they deal physical rather than stun damage."},
    {"name": "Astral Perception", "activation": "Simple Action", "effect": "See into astral space", "Cost": "0.25", "description": "Perceives astral space at will."},
    {"name": "Pain Resistance", "activation": "Passive", "effect": "Ignore wound modifiers", "Cost": "0.5", "description": "Reduces the effect of pain, softening damage penalties."},
    {"name": "Improved Physical Attribute (Body)", "activation": "Passive", "effect": "+1 Body", "Body": "1", "Cost": "1", "description": "Adept training that raises the Body attribute."},
    {"name": "Improved Physical Attribute (Agility)", "activation": "Passive", "effect": "+1 Agility", "Agility": "1", "Cost": "1", "description": "Adept training that raises the Agility attribute."},
    {"name": "Improved Physical Attribute (Strength)", "activation": "Passive", "effect": "+1 Strength", "Strength": "1", "Cost": "1", "description": "Adept training that raises the Strength attribute."},
    {"name": "Mystic Armor", "activation": "Passive", "effect": "+3 Armor", "Armor": "3", "Cost": "1.5", "description": "Wraps the adept in a mystic barrier that adds to their Armor Rating."},
    {"name": "Improved Sense (Low-Light Vision)", "activation": "Passive", "effect": "See in low light", "Cost": "0.5", "description": "Grants low-light vision."},
    {"name": "Rapid Healing", "activation": "Passive", "effect": "Faster natural healing", "Cost": "0.5", "description": "Speeds up the character's natural recovery from damage."},
    {"name": "Enhanced Accuracy (Firearms)", "activation": "Passive", "effect": "+1 Accuracy with a chosen firearm", "Cost": "0.25", "description": "Hones the adept's aim with a specific firearm."},
    {"name": "Improved Physical Attribute (Reaction)", "activation": "Passive", "effect": "+1 Reaction", "Reaction": "1", "Cost": "1", "description": "Adept training that raises the Reaction attribute."},
    {"name": "Improved Reflexes (Rating 2)", "activation": "Passive", "effect": "+2 Reaction, +2D6 Initiative", "Reaction": "2", "Initiative Dice": "2", "Cost": "5", "description": "A stronger version of Improved Reflexes."},
    {"name": "Nerve Strike", "activation": "Simple Action", "effect": "Unarmed strikes can stun on a called shot", "Cost": "0.5", "description": "Focuses ki into pressure-point strikes."},
    {"name": "Traceless Walk", "activation": "Passive", "effect": "Leaves no tracks or scent", "Cost": "0.25", "description": "Adept training in silent, trackless movement."},
    {"name": "Voice Control", "activation": "Passive", "effect": "+2 dice to Con tests using voice", "Cost": "0.5", "description": "Fine control over vocal tone and mimicry."},
    {"name": "Mystic Armor (Rating 2)", "activation": "Passive", "effect": "+6 Armor", "Armor": "6", "Cost": "3", "description": "A stronger mystic barrier."},
]

PREDEFINED_FOCI = [
    {"name": "Power Focus", "type": "Power", "force": 3, "description": "Bonded, adds its Force directly to the caster's Magic attribute."},
    {"name": "Weapon Focus", "type": "Weapon", "force": 2, "description": "Enhances a specific melee weapon with its Force in dice/damage."},
    {"name": "Spellcasting Focus", "type": "Spell", "force": 1, "description": "Adds its Force to a specific spell's casting pool."},
    {"name": "Sustaining Focus", "type": "Sustaining", "force": 2, "description": "Sustains a spell for the caster without an ongoing dice pool penalty."},
    {"name": "Qi Focus", "type": "Adept", "force": 2, "description": "Enhances a specific adept power."},
    {"name": "Binding Focus", "type": "Binding", "force": 3, "description": "Aids in binding a specific type of spirit."},
    {"name": "Centering Focus", "type": "Adept", "force": 2, "description": "Reduces drain when used with a specific linked action."},
    {"name": "Attunement Focus", "type": "Spell", "force": 1, "description": "Improves the caster's connection to their tradition."},
]

# Cyberware/Bioware/Power items may carry extra keys named after an
# attribute in ATTRIBUTES (e.g. "Reaction": "1") to grant a flat bonus,
# and/or an "Initiative Dice" key to add bonus initiative dice. Both are
# picked up automatically by ``recalculate()`` -- no separate wiring
# needed to add more predefined (or custom) items like this.
PREDEFINED_GEAR = {
    "Weapons": [
        {"name": "Ares Predator V", "Damage": "5P", "Accuracy": "5", "AP": "-1", "Mode": "SA", "RC": "0", "Ammo": "15", "Type": "Pistols", "Price": 800},
        {"name": "Colt America L36", "Damage": "4P", "Accuracy": "6", "AP": "0", "Mode": "SA", "RC": "0", "Ammo": "11", "Type": "Pistols", "Price": 320},
        {"name": "Fichetti Security 600", "Damage": "3P", "Accuracy": "7", "AP": "0", "Mode": "SA/BF", "RC": "0", "Ammo": "30", "Type": "Pistols", "Price": 500},
        {"name": "Remington Roomsweeper", "Damage": "4P", "Accuracy": "4", "AP": "-1", "Mode": "SS", "RC": "0", "Ammo": "5", "Type": "Shotguns", "Price": 450},
        {"name": "Defiance EX Shocker", "Damage": "9S(e)", "Accuracy": "4", "AP": "-5", "Mode": "SS", "RC": "0", "Ammo": "4", "Type": "Shotguns", "Price": 700},
        {"name": "AK-97", "Damage": "6P", "Accuracy": "5", "AP": "-2", "Mode": "SA/BF/FA", "RC": "1", "Ammo": "38", "Type": "Rifles", "Price": 1200},
        {"name": "Remington 950", "Damage": "9P", "Accuracy": "6", "AP": "-4", "Mode": "SS", "RC": "0", "Ammo": "6", "Type": "Rifles", "Price": 2600},
        {"name": "Ultimax 100", "Damage": "8P", "Accuracy": "4", "AP": "-4", "Mode": "BF/FA", "RC": "2", "Ammo": "100", "Type": "Machine Guns", "Price": 4000},
        {"name": "Ares MP-LMG", "Damage": "9P", "Accuracy": "5", "AP": "-3", "Mode": "FA", "RC": "3", "Ammo": "50", "Type": "Machine Guns", "Price": 6500},
        {"name": "Combat Knife", "Damage": "3P", "Accuracy": "6", "AP": "-1", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Blades", "Price": 100},
        {"name": "Katana", "Damage": "5P", "Accuracy": "7", "AP": "-2", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Blades", "Price": 900},
        {"name": "Stun Baton", "Damage": "7S(e)", "Accuracy": "5", "AP": "0", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Clubs", "Price": 750},
        {"name": "Telescoping Combat Staff", "Damage": "6P", "Accuracy": "6", "AP": "0", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Clubs", "Price": 350},
        {"name": "Throwing Knife", "Damage": "2P", "Accuracy": "4", "AP": "-1", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Thrown", "Price": 25},
        {"name": "Fragmentation Grenade", "Damage": "9P", "Accuracy": "4", "AP": "-2", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Thrown", "Price": 100},
        {"name": "Defiance EX Shocker Taser", "Damage": "7S(e)", "Accuracy": "4", "AP": "-5", "Mode": "SS", "RC": "0", "Ammo": "4", "Type": "Special", "Price": 250},
        {"name": "Browning Ultra-Power", "Damage": "6P", "Accuracy": "5", "AP": "-1", "Mode": "SA", "RC": "0", "Ammo": "10", "Type": "Pistols", "Price": 640},
        {"name": "Ruger Super Warhawk", "Damage": "7P", "Accuracy": "5", "AP": "-1", "Mode": "SS", "RC": "0", "Ammo": "6", "Type": "Pistols", "Price": 380},
        {"name": "Enfield AS-7", "Damage": "5P", "Accuracy": "5", "AP": "-1", "Mode": "SA/BF", "RC": "0", "Ammo": "10", "Type": "Shotguns", "Price": 730},
        {"name": "HK XM30", "Damage": "5P", "Accuracy": "6", "AP": "-1", "Mode": "SA/BF/FA", "RC": "2", "Ammo": "40", "Type": "Rifles", "Price": 2600},
        {"name": "Ares Alpha", "Damage": "6P", "Accuracy": "5", "AP": "-1", "Mode": "SA/BF/FA", "RC": "2", "Ammo": "42", "Type": "Rifles", "Price": 3500},
        {"name": "Wakizashi", "Damage": "4P", "Accuracy": "6", "AP": "-1", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Blades", "Price": 400},
        {"name": "Survival Knife", "Damage": "2P", "Accuracy": "5", "AP": "0", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Blades", "Price": 220},
        {"name": "Sap", "Damage": "4S", "Accuracy": "4", "AP": "0", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Clubs", "Price": 30},
        {"name": "Grapple Gun (Weaponized)", "Damage": "2P", "Accuracy": "4", "AP": "0", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Special", "Price": 750},
        {"name": "Flash-Bang Grenade", "Damage": "10S", "Accuracy": "4", "AP": "0", "Mode": "-", "RC": "-", "Ammo": "-", "Type": "Thrown", "Price": 60},
    ],
    "Armor": [
        {"name": "Armor Vest", "Rating": "3", "Social": "0", "Capacity": "4", "Type": "Clothing", "Price": 400},
        {"name": "Lined Coat", "Rating": "6", "Social": "0", "Capacity": "8", "Type": "Clothing", "Price": 1500},
        {"name": "Armor Jacket", "Rating": "4", "Social": "0", "Capacity": "6", "Type": "Armor Jacket", "Price": 1000},
        {"name": "Full Body Armor", "Rating": "6", "Social": "-4", "Capacity": "10", "Type": "Full Body Armor", "Price": 2500},
        {"name": "Ballistic Mask", "Rating": "2", "Social": "-2", "Capacity": "0", "Type": "Helmet", "Price": 300},
        {"name": "Full Helmet", "Rating": "3", "Social": "-2", "Capacity": "2", "Type": "Helmet", "Price": 500},
        {"name": "Riot Shield", "Rating": "3", "Social": "-2", "Capacity": "0", "Type": "Shield", "Price": 2000},
        {"name": "Actioneer Business Clothes", "Rating": "2", "Social": "2", "Capacity": "2", "Type": "Clothing", "Price": 1000},
        {"name": "Urban Explorer Jumpsuit", "Rating": "6", "Social": "0", "Capacity": "8", "Type": "Armor Jacket", "Price": 1250},
        {"name": "Chameleon Suit", "Rating": "5", "Social": "-2", "Capacity": "6", "Type": "Full Body Armor", "Price": 1800},
        {"name": "Forearm Guards", "Rating": "1", "Social": "0", "Capacity": "0", "Type": "Clothing", "Price": 100},
    ],
    "Cyberware": [
        {"name": "Datajack", "Essence Cost": "0.2", "Capacity": "-", "Rating": "-", "Type": "Headware", "Price": 500},
        {"name": "Cybereyes (Rating 3)", "Essence Cost": "0.4", "Capacity": "6", "Rating": "3", "Type": "Eyeware", "Price": 2000},
        {"name": "Cyberears (Rating 3)", "Essence Cost": "0.4", "Capacity": "6", "Rating": "3", "Type": "Earware", "Price": 1500},
        {"name": "Wired Reflexes (Rating 1)", "Essence Cost": "2.0", "Capacity": "-", "Rating": "1", "Type": "Bodyware", "Reaction": "1", "Initiative Dice": "1", "Price": 15000},
        {"name": "Wired Reflexes (Rating 2)", "Essence Cost": "3.0", "Capacity": "-", "Rating": "2", "Type": "Bodyware", "Reaction": "2", "Initiative Dice": "2", "Price": 39000},
        {"name": "Reaction Enhancers (Rating 2)", "Essence Cost": "1.0", "Capacity": "-", "Rating": "2", "Type": "Bodyware", "Reaction": "2", "Price": 26000},
        {"name": "Muscle Replacement (Rating 2)", "Essence Cost": "1.0", "Capacity": "-", "Rating": "2", "Type": "Bodyware", "Strength": "2", "Price": 32000},
        {"name": "Bone Lacing (Plastic)", "Essence Cost": "0.5", "Capacity": "-", "Rating": "-", "Type": "Bodyware", "Body": "1", "Price": 8000},
        {"name": "Move-by-Wire System (Rating 1)", "Essence Cost": "1.5", "Capacity": "-", "Rating": "1", "Type": "Bodyware", "Reaction": "1", "Initiative Dice": "2", "Price": 50000},
        {"name": "Cyberlimb Arm (Standard)", "Essence Cost": "1.0", "Capacity": "10", "Rating": "-", "Type": "Cyberlimbs", "Price": 15000},
        {"name": "Smartlink", "Essence Cost": "0.2", "Capacity": "-", "Rating": "-", "Type": "Implants", "Price": 2000},
        {"name": "Cybereyes (Rating 4)", "Essence Cost": "0.5", "Capacity": "8", "Rating": "4", "Type": "Eyeware", "Price": 4000},
        {"name": "Tactical Computer (Rating 2)", "Essence Cost": "0.4", "Capacity": "-", "Rating": "2", "Type": "Headware", "Price": 16000},
        {"name": "Cyberlimb Leg (Standard)", "Essence Cost": "1.0", "Capacity": "10", "Rating": "-", "Type": "Cyberlimbs", "Price": 15000},
        {"name": "Dermal Plating (Rating 2)", "Essence Cost": "1.0", "Capacity": "-", "Rating": "2", "Type": "Bodyware", "Price": 18000},
        {"name": "Platelet Factory", "Essence Cost": "0.1", "Capacity": "-", "Rating": "-", "Type": "Bodyware", "Price": 15000},
    ],
    "Bioware": [
        {"name": "Muscle Augmentation (Rating 2)", "Essence Cost": "0.6", "Rating": "2", "Capacity": "-", "Type": "Muscle", "Strength": "2", "Price": 12000},
        {"name": "Muscle Toner (Rating 2)", "Essence Cost": "0.4", "Rating": "2", "Capacity": "-", "Type": "Muscle", "Agility": "2", "Price": 32000},
        {"name": "Synaptic Booster (Rating 2)", "Essence Cost": "0.8", "Rating": "2", "Capacity": "-", "Type": "Nervous", "Reaction": "2", "Initiative Dice": "1", "Price": 18000},
        {"name": "Cerebral Booster (Rating 2)", "Essence Cost": "0.4", "Rating": "2", "Capacity": "-", "Type": "Nervous", "Logic": "2", "Price": 31000},
        {"name": "Tailored Pheromones (Rating 3)", "Essence Cost": "0.4", "Rating": "3", "Capacity": "-", "Type": "Endocrine", "Charisma": "1", "Price": 10000},
        {"name": "Trauma Damper", "Essence Cost": "0.3", "Rating": "-", "Capacity": "-", "Type": "Nervous", "Price": 15000},
        {"name": "Orthoskin (Rating 2)", "Essence Cost": "0.5", "Rating": "2", "Capacity": "-", "Type": "Skin", "Price": 20000},
        {"name": "Synthacardium (Rating 2)", "Essence Cost": "0.4", "Rating": "2", "Capacity": "-", "Type": "Muscle", "Body": "1", "Price": 14000},
        {"name": "Sleep Regulator", "Essence Cost": "0.1", "Rating": "-", "Capacity": "-", "Type": "Nervous", "Price": 8000},
        {"name": "Pathogenic Defense (Rating 2)", "Essence Cost": "0.2", "Rating": "2", "Capacity": "-", "Type": "Immune", "Body": "1", "Price": 6000},
    ],
    "Magic Items": [
        {"name": "Reagents (10 units)", "Force": "-", "Type": "Reagent", "Binding": "-", "Price": 100},
        {"name": "Spell Formula", "Force": "-", "Type": "Formula", "Binding": "-", "Price": 500},
        {"name": "Fetish", "Force": "-", "Type": "Fetish", "Binding": "-", "Price": 50},
        {"name": "Sustaining Focus (Force 2)", "Force": "2", "Type": "Sustaining", "Binding": "Karma = Force", "Price": 8000},
        {"name": "Power Focus (Force 3)", "Force": "3", "Type": "Power", "Binding": "Karma = Force x2", "Price": 60000},
        {"name": "Weapon Focus (Force 2)", "Force": "2", "Type": "Weapon", "Binding": "Karma = Force x3", "Price": 40000},
        {"name": "Spirit Fetish", "Force": "-", "Type": "Fetish", "Binding": "-", "Price": 150},
        {"name": "Magical Lodge Materials", "Force": "4", "Type": "Lodge", "Binding": "-", "Price": 2000},
    ],
    "Electronics": [
        {"name": "Meta Link Commlink", "Rating": "1", "Capacity": "-", "Function": "Commlink", "Price": 100},
        {"name": "Renraku Sensei Commlink", "Rating": "4", "Capacity": "-", "Function": "Commlink", "Price": 2000},
        {"name": "Microdeck Cyberdeck", "Rating": "3", "Capacity": "-", "Function": "Cyberdeck", "Price": 8500},
        {"name": "Erika Elite Cyberdeck", "Rating": "5", "Capacity": "-", "Function": "Cyberdeck", "Price": 23500},
        {"name": "Subvocal Mic", "Rating": "-", "Capacity": "-", "Function": "Comm Accessory", "Price": 100},
        {"name": "Tag Eraser", "Rating": "-", "Capacity": "-", "Function": "Security Tool", "Price": 800},
        {"name": "AR Gloves", "Rating": "-", "Capacity": "-", "Function": "Comm Accessory", "Price": 50},
        {"name": "Micro-Transceiver", "Rating": "-", "Capacity": "-", "Function": "Comm Accessory", "Price": 100},
        {"name": "Sensor Jammer (Rating 4)", "Rating": "4", "Capacity": "-", "Function": "Security Tool", "Price": 2000},
        {"name": "Drone (Micro)", "Rating": "2", "Capacity": "-", "Function": "Drone", "Price": 1000},
    ],
    "Medkits": [
        {"name": "Basic Medkit", "Rating": "1", "Quantity": "5", "Type": "Rating 1", "Price": 100},
        {"name": "Field Trauma Kit", "Rating": "3", "Quantity": "5", "Type": "Rating 3", "Price": 500},
        {"name": "Professional Medkit", "Rating": "6", "Quantity": "5", "Type": "Rating 6", "Price": 2000},
        {"name": "Hospital-Grade Kit", "Rating": "10", "Quantity": "5", "Type": "Rating 10", "Price": 10000},
        {"name": "Combat Trauma Patch", "Rating": "2", "Quantity": "1", "Type": "Rating 1", "Price": 300},
        {"name": "Auto-Injector Medkit", "Rating": "4", "Quantity": "3", "Type": "Rating 3", "Price": 750},
    ],
    "Other": [
        {"name": "Fake SIN (Rating 4)", "Effect": "Identity cover", "Duration": "Permanent", "Potency": "4", "Price": 4000},
        {"name": "Grapple Gun", "Effect": "Climbing/mobility tool", "Duration": "-", "Potency": "-", "Price": 750},
        {"name": "Survival Kit", "Effect": "Outdoor survival gear", "Duration": "-", "Potency": "-", "Price": 200},
        {"name": "Lockpick Set", "Effect": "+2 dice to physical lock picking", "Duration": "-", "Potency": "2", "Price": 500},
        {"name": "Chemical Suit", "Effect": "Protection from toxins/chemicals", "Duration": "-", "Potency": "6", "Price": 1500},
        {"name": "Fake License (Rating 4)", "Effect": "Legal cover for restricted gear", "Duration": "Permanent", "Potency": "4", "Price": 500},
        {"name": "Climbing Gear", "Effect": "+2 dice to Climbing tests", "Duration": "-", "Potency": "2", "Price": 200},
        {"name": "Gas Mask", "Effect": "Protection from airborne toxins", "Duration": "-", "Potency": "4", "Price": 300},
        {"name": "Zip Ties (10)", "Effect": "Restrain a target", "Duration": "-", "Potency": "-", "Price": 15},
        {"name": "Tag Eraser Spray", "Effect": "Removes RFID tags", "Duration": "-", "Potency": "-", "Price": 40},
    ],
}

VEHICLE_TYPES = [
    "Motorcycle", "Sedan", "Sports Car", "Truck", "Helicopter",
    "Drone", "Boat", "VTOL", "Submarine", "Walker"
]

MINOR_ACTIONS = [
    "Free Action", "Simple Action", "Interrupt Action", "Change Gun Mode",
    "Drop Prone", "Stand Up", "Reload Weapon", "Activate Device"
]

MAJOR_ACTIONS = [
    "Complex Action", "Full Attack", "Cast Spell", "Summon Spirit",
    "Hack Device", "Pilot Vehicle", "Full Defense", "Overwatch"
]

WIKI_TOPICS = {
    "Weapons": "**Weapons**\n\nFirearms, blades, and other implements of destruction. Each weapon has:\n- Damage Value (DV)\n- Accuracy (ACC)\n- Armor Penetration (AP)\n- Mode (SA, BF, FA)\n- Recoil Compensation (RC)\n- Ammo Capacity\n\n**Special Rules**\n- Recoil affects burst fire\n- Smartgun systems add +2 ACC",
    "Armor": "**Armor**\n\nProtective gear to reduce damage. Each armor has:\n- Rating (protection value)\n- Social penalty\n- Capacity for modifications\n\n**Special Rules**\n- Stacking armor has diminishing returns\n- Full body armor provides best protection but high social penalty",
    "Cyberware": "**Cyberware**\n\nTechnological implants that enhance abilities but cost Essence. Each cyberware has:\n- Essence Cost\n- Capacity\n- Rating\n\n**Special Rules**\n- Essence loss affects magic users\n- Cyberlimbs can be customized",
    "Bioware": "**Bioware**\n\nBiological enhancements that integrate with the body. Each bioware has:\n- Essence Cost\n- Rating\n- Capacity\n\n**Special Rules**\n- Lower essence cost than cyberware\n- More natural integration",
    "Magic Items": "**Magic Items**\n\nItems with magical properties or that enhance magical abilities. Each item has:\n- Force\n- Type\n- Binding requirements\n\n**Special Rules**\n- Foci must be bound with karma\n- Sustaining foci reduce drain for sustained spells",
    "Electronics": "**Electronics**\n\nDevices and gadgets for the digital age. Each item has:\n- Rating\n- Capacity\n- Function\n\n**Special Rules**\n- Device rating affects functionality\n- Commlinks for communication\n- Cyberdecks for hacking",
    "Medkits": "**Medkits**\n\nMedical supplies for treating injuries. Each medkit has:\n- Rating (effectiveness)\n- Quantity (uses)\n\n**Special Rules**\n- Higher rating provides better healing\n- Each use consumes one charge",
    "Other": "**Other Gear**\n\nMiscellaneous equipment for various purposes. Each item has:\n- Effect\n- Duration\n- Potency\n\n**Special Rules**\n- Includes tools, chemicals, and special items",
    "Spells": "**Spells**\n\nMagical effects created through willpower and tradition. Each spell has:\n- Type (Combat, Health, Illusion, Manipulation)\n- Drain value (cost to cast)\n\n**Casting**\n- Spellcasting + Magic [Force] vs. Drain\n- Drain is Physical for combat spells, Stun for others",
    "Powers": "**Adept Powers**\n\nInnate magical abilities possessed by adepts. Each power has:\n- Activation type (Passive, Simple Action)\n- Effect\n\n**Special Rules**\n- Powered by Magic attribute\n- No drain but limited by power points",
    "Foci": "**Foci**\n\nMagical items that enhance or channel magic. Each focus has:\n- Type (Sustaining, Weapon, Spell, etc.)\n- Force (power level)\n\n**Special Rules**\n- Must be bound with karma\n- Can be overloaded or corrupted",
    "Traditions": "**Magical Traditions**\n\nDifferent approaches to magic:\n- Hermetic (Logic-based)\n- Shamanic (Charisma-based)\n- Christian Theurgy (Willpower-based)\n- Buddhist (Intuition-based)\n\n**Special Rules**\n- Tradition determines drain resistance attribute\n- Affects spirit types that can be summoned",
    "Motorcycle": "**Motorcycle**\n\n- Speed: 4\n- Handling: 5\n- Accel: 3\n- Body: 8\n- Armor: 6\n- Pilot: 1\n- Sensor: 1\n- Seats: 2\n- Price: 15,000¥",
    "Sedan": "**Sedan**\n\n- Speed: 3\n- Handling: 4\n- Accel: 2\n- Body: 12\n- Armor: 10\n- Pilot: 1\n- Sensor: 2\n- Seats: 4\n- Price: 25,000¥",
    "Sports Car": "**Sports Car**\n\n- Speed: 5\n- Handling: 5\n- Accel: 4\n- Body: 10\n- Armor: 8\n- Pilot: 2\n- Sensor: 3\n- Seats: 2\n- Price: 75,000¥",
    "Truck": "**Truck**\n\n- Speed: 2\n- Handling: 3\n- Accel: 1\n- Body: 18\n- Armor: 15\n- Pilot: 1\n- Sensor: 1\n- Seats: 3\n- Price: 40,000¥",
    "Helicopter": "**Helicopter**\n\n- Speed: 4\n- Handling: 4\n- Accel: 2\n- Body: 14\n- Armor: 10\n- Pilot: 3\n- Sensor: 4\n- Seats: 6\n- Price: 200,000¥",
    "Drone": "**Drone**\n\n- Speed: 3\n- Handling: 4\n- Accel: 2\n- Body: 6\n- Armor: 4\n- Pilot: 1\n- Sensor: 2\n- Seats: 0\n- Price: 10,000¥",
    "Free Action": "**Free Action**\n\nCan be performed any time during your turn\n- Speak a few words\n- Drop an item\n- Change gun mode\n- Take a small step",
    "Simple Action": "**Simple Action**\n\nRequires a simple action\n- Fire a weapon (simple)\n- Cast a spell\n- Make a skill test\n- Move up to walking speed",
    "Interrupt Action": "**Interrupt Action**\n\nCan be performed outside your turn\n- Defensive actions\n- Dodging\n- Using Edge",
    "Change Gun Mode": "**Change Gun Mode**\n\nSwitch between firing modes:\n- Single Shot (SS)\n- Semi-Automatic (SA)\n- Burst Fire (BF)\n- Full Automatic (FA)",
    "Complex Action": "**Complex Action**\n\nRequires significant effort\n- Full attack\n- Complex spell casting\n- Hacking attempt\n- Reloading",
    "Full Attack": "**Full Attack**\n\nUnleash a powerful attack\n- Add Edge to attack pool\n- Multiple attacks in one action\n- Requires complex action",
    "Combat": "**Combat Sequence**\n1. Roll initiative\n2. Characters act in initiative order\n3. Repeat for each combat turn\n\n**Actions**\n- Simple Action (1 per turn)\n- Complex Action (1 per turn)\n- Free Action (multiple)",
    "Magic System": "**Magic Rules**\n- Magic Rating determines spell power\n- Drain is physical/stun damage from spellcasting\n- Counterspelling defends against magic\n- Sustaining spells causes penalty",
    "Hacking": "**Matrix Actions**\n- Brute Force (attack)\n- Hack on the Fly (stealth)\n- Matrix Perception (detection)\n\n**Devices**\n- All devices have device rating (1-6)",
    "Vehicles": "**Vehicle Combat**\n- Piloting tests for maneuvers\n- Vehicle stats: Handling, Speed, Accel\n\n**Rigging**\n- Riggers can jump into vehicles directly",
}


# ---------------------------------------------------------------------------
# Item editor fields (from the original EditGearDialog)
GEAR_ATTRIBUTES = {
    "Weapons": ["Damage", "Accuracy", "AP", "Mode", "RC", "Ammo", "Type", "Price"],
    "Armor": ["Rating", "Social", "Capacity", "Type", "Price"],
    "Cyberware": ["Essence Cost", "Capacity", "Rating", "Type", "Price"],
    "Bioware": ["Essence Cost", "Rating", "Capacity", "Type", "Price"],
    "Magic Items": ["Force", "Type", "Binding", "Price"],
    "Medkits": ["Rating", "Quantity", "Type", "Price"],
    "Electronics": ["Rating", "Capacity", "Function", "Price"],
    "Other": ["Effect", "Duration", "Potency", "Price"],
    "Spell": ["Type", "Drain"],
    "Power": ["Activation", "Effect", "Cost"],
    "Focus": ["Type", "Force", "Price"],
}

GEAR_OPTIONS = {
    "Weapons.Type": WEAPON_TYPES,
    "Armor.Type": ARMOR_TYPES,
    "Cyberware.Type": CYBERWARE_TYPES,
    "Medkits.Type": MEDKIT_TYPES,
    "Spell.Type": ["Combat", "Health", "Illusion", "Manipulation"],
    "Power.Activation": ["Passive", "Simple Action", "Complex Action"],
    "Focus.Type": ["Power", "Sustaining", "Weapon", "Spell", "Adept", "Binding"],
}

EQUIPPABLE_CATEGORIES = ("Weapons", "Armor")

# Karma to bond a focus = Force x multiplier (from the original Magic tab).
FOCUS_BOND_MULTIPLIER = {"Power": 2, "Weapon": 1, "Spell": 1, "Sustaining": 1, "Adept": 1, "Binding": 1}

# Linked attribute for each skill test (SR6 core).
SKILL_ATTRIBUTE = {
    "Astral": "Intuition", "Athletics": "Agility", "Biotech": "Logic", "Close Combat": "Agility",
    "Con": "Charisma", "Conjuring": "Magic", "Cracking": "Logic", "Electronics": "Logic",
    "Enchanting": "Magic", "Engineering": "Logic", "Exotic Weapons": "Agility", "Firearms": "Agility",
    "Influence": "Charisma", "Outdoors": "Intuition", "Perception": "Intuition", "Piloting": "Reaction",
    "Sorcery": "Magic", "Stealth": "Agility", "Tasking": "Resonance",
}

# Attribute added to Willpower for drain resistance, per tradition.
TRADITION_DRAIN = {
    "Hermetic": "Logic", "Shamanic": "Charisma", "Christian Theurgy": "Willpower",
    "Buddhist": "Intuition", "Islamic": "Logic", "Voodoo": "Charisma",
}

# Weapon type -> skill used to attack with it (and the specialization that applies).
WEAPON_SKILL = {
    "Pistols": "Firearms", "Rifles": "Firearms", "Shotguns": "Firearms", "Machine Guns": "Firearms",
    "Special": "Firearms", "Blades": "Close Combat", "Clubs": "Close Combat", "Thrown": "Athletics",
}

# The original Wiki tab's tree.
WIKI_TREE = {
    "Gear": GEAR_CATEGORIES,
    "Magic": ["Spells", "Powers", "Foci", "Traditions"],
    "Vehicles": VEHICLE_TYPES,
    "Actions": ["Minor Actions", "Major Actions"],
    "Rules": ["Combat", "Magic System", "Hacking", "Vehicles", "Edge", "Wild Die", "Damage & Condition Monitors"],
}

WIKI_TOPICS.update({
    "Edge": "**Edge (SR6)**\n\nYou start each session with Edge equal to your Edge attribute and can hold at most 7.\nThe GM awards Edge during play and refreshes it.\n\n**Edge Boosts** (one per roll)\n- 1 Edge: reroll one die (1 Edge per die rerolled); +3 Initiative score\n- 2 Edge: +1 to one die; give an ally 1 Edge; negate 1 Edge of an opponent\n- 3 Edge: buy one automatic hit; heal 1 box of Stun\n- 4 Edge: reroll all failed dice; add your Edge rating to the pool with exploding 6s (declared before rolling); heal 1 box of Physical\n- 5 Edge: count 2s as glitches on a target's test; create a special effect with the GM",
    "Wild Die": "**Wild Die (SR6)**\n\nOne die in the pool is the Wild Die.\n- 5 or 6 on the Wild Die: it counts as 3 hits.\n- 1 on the Wild Die: none of the 5s in the roll count as hits.\n- 2-4: no effect (it is simply not a hit).",
    "Damage & Condition Monitors": "**Condition Monitors**\n\n- Physical boxes: 8 + Body/2 (rounded up)\n- Stun boxes: 8 + Willpower/2 (rounded up)\n- Wound modifier: -1 dice for every 3 boxes filled on each monitor\n- Stun monitor full: unconscious. Further Stun overflows into Physical.\n- Physical monitor full: dying. Overflow boxes equal to Body; past that the character is dead.",
})

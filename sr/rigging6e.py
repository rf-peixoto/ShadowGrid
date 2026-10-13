"""Shadowrun Sixth World rigging: vehicle and drone tests, autosofts, control rigs, vehicle combat
(core rulebook pp. 196-202). Every number lives here.

Control:
- manual: at the controls. Handling test: Piloting + Reaction, threshold Handling (+1 per 3 boxes of damage).
- jumped: jumped in with a control rig (VR). Mental attributes replace Physical ones (Reaction -> Intuition,
  Agility -> Logic, Body -> Willpower, Strength -> Charisma) and the rig adds its rating in dice.
- drone: a drone acting on its own or on a command: Pilot + the matching autosoft.
Mounted weapons: Engineering + Logic (jumped in or from inside); a drone's autopilot fires with
[Weapon] Targeting autosoft + Sensor (Sensor - 1 without the autosoft).
"""

CONTROL = {
    "manual": {"name": "At the controls", "pool": ("Piloting", "Reaction")},
    "jumped": {"name": "Jumped in", "pool": ("Piloting", "Intuition"), "needs": "control rig", "rig_bonus": True},
}
JUMPED_ATTRS = {"Body": "Willpower", "Strength": "Charisma", "Agility": "Logic", "Reaction": "Intuition"}
GUNNERY = {"manual": ("Engineering", "Logic"), "jumped": ("Engineering", "Logic")}

# autosoft -> (what it does, the drone attribute it is rolled with)
AUTOSOFTS = {
    "Clearsight": ("The drone's Perception.", "Sensor"),
    "Electronic Warfare": ("Cracking for jamming and overcoming ECM.", "Sensor"),
    "Evasion": ("Defense when the drone is fired at: Pilot + Evasion.", "Pilot"),
    "Maneuvering": ("The drone's Piloting.", "Pilot"),
    "Stealth": ("The drone's Stealth.", "Pilot"),
    "Targeting": ("The weapon skill for one mounted weapon: Targeting + Sensor (Sensor − 1 without it).", "Sensor"),
}
AUTOSOFT_RATING = (1, 9)     # errata

# speed (p. 199): track the current speed in meters per combat round; change it by at most Acceleration per
# round; distance this round = speed at the start ± half the change. Every Speed Interval passed costs −1 die
# (cumulative) on Handling tests and on attacks from the vehicle; ramming adds +1 DV per current interval.
# A crash does (speed / 10) damage to those inside.
CRASH_DV_DIVISOR = 10

# weapon mounts (p. 200): Body / 3 (round down) mounts; a heavy mount counts as two. Standard mounts hold an
# assault rifle or smaller (250 rounds), heavy ones any weapon (500 belted rounds or Body rockets/missiles).
MOUNT_BODY_DIVISOR = 3
MOUNTS = {"vehicles-standard-weapon-mount": {"slots": 1, "heavy": False},
          "vehicles-heavy-weapon-mount": {"slots": 2, "heavy": True}}
STANDARD_MOUNT_WEAPONS = {"Hold-outs", "Light Pistols", "Heavy Pistols", "Machine Pistols", "Submachine Guns", "Shotguns",
                          "Assault Rifles", "Tasers"}
HEAVY_MOUNT_WEAPONS = {"Sniper Rifles", "Machine Guns", "Launchers", "Special Weapons"}

# vehicle combat (p. 201)
MONITOR_BASE = 8             # Condition Monitor = (Body / 2) + 8, one track
DAMAGE_HANDLING_STEP = 3     # Handling (threshold) +1 per 3 boxes of damage
DR = ("pilot", "armor")      # Defense Rating = Piloting of the driver (Pilot of a drone) + Armor
SOAK = ("body",)             # damage resisted with Body
STUN_IMMUNE = True           # Stun damage with DV up to Body does nothing; above it, it's Physical
DRONE_INIT_DICE = 4          # drones on their own: Pilot x 2 + 4D6
RAM = {"name": "Ram", "skill": "Piloting", "type": "P",
       "desc": "Opposed Piloting + Reaction (vs Piloting + Reaction, or the target's Defense). Attack Rating Piloting + Sensor; "
               "DV (Body / 2, rounded up) + 1 per current Speed Interval + net hits, Physical. A soft target does (its Body / 4) back to the vehicle."}

"""Shadowrun Sixth World rigging: vehicle and drone tests, autosofts, control rigs, vehicle combat
(core rulebook, Riggers chapter, with the errata). Every number lives here.

Control modes:
- manual: you're at the controls. Piloting + Reaction.
- remote: through a commlink or RCC. Piloting + Logic.
- jumped: jumped in with a control rig (VR). Piloting + Intuition, + control rig rating in dice
  (the errata: the rig's rating is a dice bonus and a threshold reduction on every vehicle test).
- autonomous: the drone acts alone. Pilot rating + the matching autosoft's rating.
Mounted weapons use Engineering (Gunnery): Agility when operated by hand, Logic when remote or jumped in.
"""

CONTROL = {
    "manual": {"name": "At the controls", "pool": ("Piloting", "Reaction")},
    "remote": {"name": "Remote control", "pool": ("Piloting", "Logic"), "needs": "commlink or RCC"},
    "jumped": {"name": "Jumped in", "pool": ("Piloting", "Intuition"), "needs": "control rig", "rig_bonus": True},
}
GUNNERY = {"manual": ("Engineering", "Agility"), "remote": ("Engineering", "Logic"), "jumped": ("Engineering", "Logic")}

AUTOSOFTS = {
    "Maneuvering": "Piloting tests for a drone acting on its own: Pilot + Maneuvering.",
    "Targeting": "Attacks with one weapon type for a drone acting on its own: Pilot + Targeting.",
    "Clearsight": "Perception for a drone acting on its own: Pilot + Clearsight.",
    "Evasion": "Defense for a drone acting on its own: Pilot + Evasion.",
    "Electronic Warfare": "Matrix tests (jamming, signals) for a drone acting on its own.",
    "Stealth": "Sneaking for a drone acting on its own: Pilot + Stealth.",
}
AUTOSOFT_RATING = (1, 9)     # errata

# vehicle combat
MONITOR_BASE = 8             # Condition Monitor = (Body / 2, rounded up) + 8 (errata), one track
DR = ("pilot", "armor")      # Defense Rating = Piloting (driver) or Pilot (drone) + Armor (errata)
SOAK = ("body",)             # damage resisted with Body
STUN_IMMUNE = True           # Stun damage with DV up to Body does nothing; above it, it's Physical
RAM = {"name": "Ram", "skill": "Piloting", "dv_from": "body", "type": "P",
       "desc": "Use the vehicle as a weapon: Piloting test, DV = the vehicle's Body + net hits."}

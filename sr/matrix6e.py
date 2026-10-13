"""Shadowrun Sixth World Matrix: actions, Overwatch Score, convergence, IC (core rulebook pp. 174-188).

Tests: legal actions use Electronics, illegal ones Cracking. Attack Rating = Attack + Sleaze,
Defense Rating = Data Processing + Firewall (whoever is 4+ ahead gains Edge, 2 per round at most).

Each action: name, legal, action (major/minor), access needed, attacker pool (skill, attribute),
defense (text; "pool" is a list of the defender's Matrix/mental attributes, or "rating" for
Device/Host Rating x 2), effect text, and Matrix damage when it attacks.
"""

OS_LIMIT = 40                 # convergence
OS_PER_ILLEGAL_HIT = 1        # each hit the defender rolls on an illegal action
OS_PER_HACKING_PROGRAM = 1    # an action helped by a hacking program (once per action)
OS_PER_ROUND_USER = 1         # each host with illegal User access, per round
OS_PER_ROUND_ADMIN = 3        # each host with illegal Admin access, per round
DUMPSHOCK = {"cold": (3, "S"), "hot": (3, "P")}   # resisted with Willpower
DEVICE_PENALTY_STEP = 3       # -1 die per 3 boxes of Matrix damage on the device
NOISE_TABLE = [("Direct connection or under 100 m", 0), ("100 m to 1 km", 1), ("1 to 10 km", 3), ("10 to 100 km", 5), ("Over 100 km", 8)]

# What the programs do, beyond their description (core p. 184 and p. 198). Where a program grants Edge
# "for that action", the Edge is tied to the roll: spend it on a boost of that roll or it's gone.
PROGRAM_EDGE = {"Browse": "matrix_search", "Edit": "edit_file", "Stealth": "hide", "Trace": "trace_icon"}
PROGRAM_DICE = {"Encryption": ("encrypt_file", 2), "Decryption": ("crack_file", 2)}
OVERCLOCK = {"dice": 2, "wild": True}         # one of the two dice is the Wild Die
SIGNAL_SCRUBBER = 2                           # noise reduced by 2
VIRTUAL_MACHINE = {"slots": 2, "extra_damage": 1}
EXPLOIT_DR = -2                               # the hacking target's Defense Rating
NOISE_MAX = 20                                # each point of noise: −1 on Matrix tests; above the Device Rating: no access
PERSONA_ATTRS = ("attack", "sleaze", "data_processing", "firewall")

MATRIX_ACTIONS = {
    # ---- entry and access (hacking is Brute Force, or Probe followed by Backdoor Entry)
    "brute_force": {"name": "Brute Force", "legal": False, "action": "major", "access": "Outsider/User/Admin",
                    "pool": ("Cracking", "Logic"), "defense": ["Willpower", "Firewall"], "uses": "attack",
                    "effect": "Gain access by force. Admin access without User access first: the target gets +4 Defense Rating."},
    "backdoor_entry": {"name": "Backdoor Entry", "legal": False, "action": "major", "access": "Outsider",
                       "pool": ("Cracking", "Logic"), "defense": ["Willpower", "Firewall"], "uses": "sleaze",
                       "effect": "Enter a host through a weakness found with Probe (its net hits add dice)."},
    "probe": {"name": "Probe", "legal": False, "action": "extended (1 minute)", "access": "any",
              "pool": ("Cracking", "Logic"), "defense": ["Willpower", "Firewall"], "uses": "sleaze",
              "effect": "Find a weakness without raising an alarm: net hits become bonus dice for a later Backdoor Entry, for (10 − rating) hours."},
    # ---- information
    "matrix_perception": {"name": "Matrix Perception", "legal": True, "action": "major", "access": "any",
                          "pool": ("Electronics", "Intuition"), "defense": ["Willpower", "Sleaze"],
                          "effect": "Spot and analyse icons, including ones running silent (Minor with a cyberdeck, cyberjack or Resonance)."},
    "matrix_search": {"name": "Matrix Search", "legal": True, "action": "extended (10 minutes)", "access": "any",
                      "pool": ("Electronics", "Intuition"), "defense": None,
                      "effect": "Find information; the GM sets the threshold."},
    "check_os": {"name": "Check Overwatch Score", "legal": False, "action": "major", "access": "Admin",
                 "pool": ("Cracking", "Logic"), "defense": 4,
                 "effect": "On a success you learn your current Overwatch Score."},
    "snoop": {"name": "Snoop", "legal": False, "action": "major", "access": "Admin",
              "pool": ("Cracking", "Logic"), "defense": ["Logic", "Firewall"], "uses": "sleaze",
              "effect": "Intercept the target's traffic while you keep Admin access."},
    "trace_icon": {"name": "Trace Icon", "legal": False, "action": "major", "access": "Admin",
                   "pool": ("Electronics", "Intuition"), "defense": ["Willpower", "Sleaze"], "uses": "sleaze",
                   "effect": "Find the physical location of the target's device."},
    "hash_check": {"name": "Hash Check", "legal": False, "action": "major", "access": "User/Admin",
                   "pool": ("Electronics", "Logic"), "defense": None,
                   "effect": "Check a file's integrity: threshold 1 with the hash, 4 without."},
    # ---- attacks
    "data_spike": {"name": "Data Spike", "legal": False, "action": "major", "access": "any",
                   "pool": ("Cracking", "Logic"), "defense": ["Data Processing", "Firewall"], "uses": "attack",
                   "damage": "attack", "effect": "Matrix damage: half your Attack Rating (rounded up) + 1 per net hit."},
    "tarpit": {"name": "Tarpit", "legal": False, "action": "major", "access": "any",
               "pool": ("Cracking", "Logic"), "defense": ["Data Processing", "Firewall"], "uses": "attack",
               "damage": "one", "effect": "1 + net hits Matrix damage, and the target's Data Processing drops by as much."},
    "crash_program": {"name": "Crash Program", "legal": False, "action": "major", "access": "Admin",
                      "pool": ("Cracking", "Logic"), "defense": ["Data Processing", "Device Rating"], "uses": "attack",
                      "effect": "Crash a running program on the target."},
    # ---- defense and stealth
    "hide": {"name": "Hide", "legal": False, "action": "major", "access": "any",
             "pool": ("Cracking", "Intuition"), "defense": ["Intuition", "Data Processing"], "uses": "sleaze",
             "effect": "An icon that has spotted you loses track of you."},
    "erase_signature": {"name": "Erase Matrix Signature", "legal": False, "action": "major", "access": "User/Admin",
                        "pool": ("Electronics", "Logic"), "defense": ["Willpower", "Firewall"], "uses": "attack",
                        "effect": "Remove a Resonance signature (requires Resonance)."},
    "full_matrix_defense": {"name": "Full Matrix Defense", "legal": True, "action": "major", "access": "any",
                            "pool": None, "defense": None,
                            "effect": "Add Firewall to your Matrix Defense tests until the end of the round."},
    # ---- files
    "edit_file": {"name": "Edit File", "legal": True, "action": "major", "access": "User/Admin",
                  "pool": ("Electronics", "Logic"), "defense": ["Intuition", "Firewall"], "effect": "Create, change, copy or delete a file."},
    "encrypt_file": {"name": "Encrypt File", "legal": True, "action": "major", "access": "User/Admin",
                     "pool": ("Electronics", "Logic"), "defense": None, "effect": "Hits become the file's Encryption rating."},
    "crack_file": {"name": "Crack File", "legal": False, "action": "major", "access": "any",
                   "pool": ("Cracking", "Logic"), "defense": "rating", "uses": "attack", "effect": "Break a file's encryption (rating x 2 dice)."},
    "set_data_bomb": {"name": "Set Data Bomb", "legal": False, "action": "major", "access": "Admin",
                      "pool": ("Electronics", "Logic"), "defense": "rating", "uses": "sleaze", "effect": "Booby-trap a file; hits set the bomb's rating."},
    "disarm_data_bomb": {"name": "Disarm Data Bomb", "legal": True, "action": "major", "access": "any",
                         "pool": ("Cracking", "Logic"), "defense": "rating", "effect": "Defuse a data bomb (rating x 2 dice)."},
    # ---- devices
    "control_device": {"name": "Control Device", "legal": False, "action": "major", "access": "User/Admin",
                       "pool": ("Electronics", "Logic"), "defense": ["Willpower", "Firewall"],
                       "effect": "Use a device remotely. Fails against a device a rigger is jumped into."},
    "spoof_command": {"name": "Spoof Command", "legal": False, "action": "major", "access": "Outsider",
                      "pool": ("Cracking", "Logic"), "defense": ["Data Processing", "Firewall"], "uses": "sleaze",
                      "effect": "Send a command that looks like it comes from the device's owner (vs Pilot + Firewall for drones)."},
    "format_device": {"name": "Format Device", "legal": True, "action": "major", "access": "Admin",
                      "pool": ("Electronics", "Logic"), "defense": ["Willpower", "Firewall"], "effect": "The device's software is wiped on its next reboot."},
    "reboot_device": {"name": "Reboot Device", "legal": True, "action": "major", "access": "Admin",
                      "pool": ("Electronics", "Logic"), "defense": ["Willpower", "Firewall"],
                      "effect": "The device shuts down and is back at the end of the next combat round; Overwatch, exploits and backdoors reset."},
    "jam_signals": {"name": "Jam Signals", "legal": False, "action": "major", "access": "Admin",
                    "pool": ("Cracking", "Logic"), "defense": None, "uses": "attack", "effect": "Each hit adds 1 noise to Matrix actions within 100 m."},
    "jump_in": {"name": "Jump into Rigged Device", "legal": True, "action": "major", "access": "Admin",
                "pool": ("Electronics", "Logic"), "defense": ["Willpower", "Firewall"],
                "effect": "Take a rigged vehicle or drone over in VR (no test for your own devices)."},
    "jack_out": {"name": "Jack Out", "legal": True, "action": "major", "access": "any",
                 "pool": ("Electronics", "Willpower"), "defense": ["Charisma", "Data Processing"],
                 "effect": "Leave the Matrix; a test only when link-locked. Leaving VR this way causes dumpshock."},
}

# IC (p. 186): Host Rating x 2 for attack rolls, Attack Rating and Condition Monitor; (Data Processing x 2)
# + 3D6 Initiative. Each type has its own Defense pool for the target. damage: "matrix" (host rating + net
# hits Matrix damage), "bio" (the same as biofeedback only), "both", or None. reduce: the target's Matrix
# attribute that drops by 1 per net hit (restored after leaving the host).
IC_TYPES = {
    "Acid":     {"defense": ["Willpower", "Firewall"], "damage": None, "reduce": "firewall",
                 "effect": "Each net hit lowers the target's Firewall by 1 until they leave the host."},
    "Binder":   {"defense": ["Willpower", "Data Processing"], "damage": None, "reduce": "data_processing",
                 "effect": "Each net hit lowers the target's Data Processing by 1 until they leave the host."},
    "Black IC": {"defense": ["Intuition", "Firewall"], "damage": "both",
                 "effect": "Host rating + net hits as Matrix damage and the same as biofeedback (Stun cold-sim, Physical hot-sim)."},
    "Blaster":  {"defense": ["Logic", "Firewall"], "damage": "matrix", "linklock": True,
                 "effect": "Matrix damage and link-locks the target."},
    "Crash":    {"defense": ["Intuition", "Firewall"], "damage": None,
                 "effect": "No damage: crashes one random program until the device reboots."},
    "Jammer":   {"defense": ["Willpower", "Attack"], "damage": None, "reduce": "attack",
                 "effect": "Each net hit lowers the target's Attack by 1 until they leave the host."},
    "Killer":   {"defense": ["Intuition", "Firewall"], "damage": "matrix",
                 "effect": "Host rating + net hits as Matrix damage."},
    "Marker":   {"defense": ["Willpower", "Sleaze"], "damage": None, "reduce": "sleaze",
                 "effect": "Each net hit lowers the target's Sleaze by 1 until they leave the host."},
    "Patrol":   {"defense": None, "damage": None,
                 "effect": "Matrix Perception for the host every minute: spots intruders and raises the alarm."},
    "Scramble": {"defense": ["Willpower", "Firewall"], "damage": None,
                 "effect": "Forces the target to reboot on their next turn, unless link-locked."},
    "Sparky":   {"defense": ["Intuition", "Firewall"], "damage": "bio",
                 "effect": "Host rating + net hits as biofeedback damage, bypassing the device."},
    "Tar Baby": {"defense": ["Logic", "Firewall"], "damage": None, "linklock": True,
                 "effect": "Link-locks the target."},
    "Track":    {"defense": ["Willpower", "Sleaze"], "damage": None,
                 "effect": "Finds the target's physical location."},
}
IC = {k: v["effect"] for k, v in IC_TYPES.items()}
IC_CM_PER_RATING = 2                 # Condition Monitor = Host Rating x 2
IC_INIT_DICE = 3                     # (Data Processing x 2) + 3D6; the host's Data Processing is taken as its rating

# Matrix Edge actions (need a cyberjack or Resonance)
MATRIX_EDGE = [
    (1, "Emergency Boost", "+1 to one Matrix attribute for one test."),
    (2, "Hog", "Target's Data Processing −2 and one program slot fewer for Attack Rating rounds."),
    (2, "Signal Scream", "Ignore noise on your next action."),
    (2, "Technobabble", "Technomancers: use Charisma instead of Logic."),
    (3, "Under the Radar", "Your next illegal action this turn doesn't raise the Overwatch Score."),
]

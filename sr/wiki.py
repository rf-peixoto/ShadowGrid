"""In-app rules wiki, generated from the game data plus short rule summaries
written for this app (not the book's text)."""
from . import catalog as CAT
from . import core6e as K
from . import gear6e as G
from . import magic6e as M
from . import matrix6e as MX
from . import npc6e as N
from . import rigging6e as RIG

RULES = {
    "Tests and dice": """**Tests and dice**
Roll a pool of six-sided dice; every 5 or 6 is a hit.
- Simple test: hits must reach a threshold (Easy 1, Average 2, Hard 4, Very hard 6).
- Opposed test: both sides roll; the higher hits win, ties go to the attacker. The difference is the net hits.
- Glitch: more than half of the dice show 1. Critical glitch: a glitch with no hits.
- Untrained: a skill you don't have rolls its attribute -1 (some skills can't be used untrained).
- Specialization +2 dice, expertise +3 dice, when the test matches them.
- Wound modifiers apply to almost every test.""",
    "Edge": """**Edge**
Edge is a pool (maximum 7) that refreshes only when the GM says so.
- Gain Edge from the situation: Attack Rating beating Defense Rating by 4 or more, better vision, cover, and so on. At most 2 per combat round. In ShadowGrid the attack dialog awards the AR vs DR Edge for you (and keeps the 2-per-round limit); the GM awards the rest by hand.
- Before a roll, 4 Edge: add your Edge rating to the pool and 6s explode.
- After a roll, one boost per roll: 1 Edge rerolls one die, 2 Edge adds +1 to a die, 3 Edge buys an automatic hit, 4 Edge rerolls all failures.
- Outside rolls: +3 Initiative (1), heal 1 Stun (3) or 1 Physical (4), give an ally 1 Edge (2), negate 1 of an opponent's Edge (2), count 2s as glitches for a target (5), special effect (5).""",
    "Wild Die": """**Wild Die**
One die of the pool, usually given by the GM for dramatic moments.
- A 5 or 6 on the Wild Die counts as 3 hits.
- A 1 on the Wild Die means none of the 5s in the roll count as hits.""",
    "Combat": """**Combat**
An attack is an opposed test:
- Attack: weapon skill + Agility (Engineering + Logic for vehicle weapons; Sorcery + Magic for spells).
- Defense: Reaction + Intuition (direct spells: Willpower + Intuition; indirect spells: Reaction + Willpower).
- If the attack wins (ties go to the attacker), the Damage Value is the weapon's DV + net hits.
- Soak: Body; every hit reduces the damage by 1. Direct combat spells can't be soaked.
- Damage left over goes to the Physical (P) or Stun (S) monitor.
- If damage after soaking exceeds the target's Body, they are knocked Prone.
- Elemental damage adds a status: electricity Zapped, fire Burning, cold Chilled, chemical Corrosive.
- Ranges: Close 0-3 m, Near 4-50 m, Medium 51-250 m, Far 251-500 m, Extreme 500+ m. A weapon without an Attack Rating at a range can't be used there.
- Defending (interrupts, out of turn): Block (Minor, melee: +Close Combat), Dodge (Minor: +Athletics), Hit the Dirt (Minor, ranged: +2, then Prone and −2 on your next turn), Full Defense (Major: +Willpower on every Defense test this round).
- Cover I-IV adds its level to the Defense Rating and to the Defense test. ShadowGrid works out line of sight and cover from the map's walls and closed doors.
- Called shot (Minor, with the attack): −4 dice, +2 DV. Shank (melee, 1 Edge): only −2 dice. Vitals (5 Edge): +3 DV. Disarm (5 Edge): the target drops their weapon.
- Multiple Attacks (Minor): split the pool evenly among the targets; Anticipation (4 Edge) rolls the full pool for each.
- Statuses change the numbers: Zapped −1, Fatigued −2 per level, Confused −its value, Chilled −1 (and −4 Initiative), Immobilized −3 dice and AR (no Reaction on defense), Prone +2 defense against Medium+ ranged attacks and −2 against the rest, Wet −6 to resist cold and electricity.
- Burning, Corrosive and Poisoned: resist the value as Physical at the start of each round (the GM's 🔥 button).""",
    "Firing modes and ammo": """**Firing modes and ammo**
- SS, single shot: 1 round.
- SA, semi-automatic: 2 rounds, -2 Attack Rating, +1 DV.
- BF, burst fire: 4 rounds, -4 Attack Rating, +2 DV (narrow), or split the pool between two targets.
- FA, full auto: 10 rounds, -6 Attack Rating, split the pool among any targets.
- ShadowGrid removes the rounds from the weapon when you roll the attack, and grenades or throwing weapons from the inventory. Reload from your ammo stacks on the Gear tab.
- Ammo types: APDS +2 AR -1 DV; Explosive +1 DV; Flechette +1 AR -1 DV; Gel (Stun); Stick-n-Shock (electric Stun, +1 AR -1 DV).""",
    "Initiative and actions": """**Initiative and actions**
- Initiative Score = Reaction + Intuition + the total of your Initiative Dice (max 5D6). Highest acts first; ties: Edge, Reaction, Intuition, then a coin flip.
- Initiative is not rerolled between combat rounds.
- Each round you get 1 Major Action and 1 Minor Action, +1 Minor per Initiative Die (never more than 5 Minor).
- A Major can do a Minor's job, and 4 Minor make a Major.
- Matrix: AR Reaction + Intuition + 1D6; cold-sim VR Intuition + Data Processing + 2D6; hot-sim VR Intuition + Data Processing + 3D6.
- Astral: Logic + Intuition + 2D6.""",
    "Damage and condition monitors": """**Damage and condition monitors**
- Physical boxes: 8 + Body/2; Stun boxes: 8 + Willpower/2 (round up).
- Every 3 boxes filled on a track: -1 to dice pools (tracks add together).
- Stun full: unconscious; further Stun becomes Physical.
- Physical full: dying. Overflow boxes equal Body x 2; filling them means death.
- Grunts use one monitor (8 + half of the higher of Body or Willpower), take -1 per 2 boxes, and may flee when damage exceeds their Professional Rating.""",
    "Healing": """**Healing**
Overflow heals first. Each method works once per set of injuries.
- First aid (within a minute): Biotech + Logic, threshold 5 - patient's Essence (+1 hit if the patient has full Essence; -2 dice without a kit). Extra hits heal 1 Stun each, or 1 Physical per 2 hits.
- Medkit (within an hour): same test, +1 die for the wireless medkit; each extra hit heals 1 box of any kind. Uses one set of supplies, and can't be done without supplies.
- Without a medkit, first aid can't use Edge.
- Roll any of these from the dice roller (Healing group): pick the patient, and the healing is applied.
- Magic: Sorcery + Magic with a Heal spell, same threshold; each net hit heals 1 box.
- None of those heal drain.
- Natural recovery: Body + Willpower per hour of rest heals Stun; Body + Body per day heals Physical (overflow: minus wound modifiers). A Biotech-trained helper adds +2 dice.""",
    "Magic": """**Magic**
- Spellcasting: Sorcery + Magic. Attack Rating for spells: Magic + tradition attribute.
- Drain: resist the spell's Drain Value with Willpower + tradition attribute (Hermetic: Logic; Shamanic: Charisma). Drain is Stun unless the Drain Value is higher than your Magic, then Physical.
- Amp Up (combat spells): +1 DV for +2 drain. Increase Area: +2 m radius for +1 drain.
- Indirect combat spells do Magic/2 + net hits and are soaked with Body; direct spells do net hits and can't be soaked.
- Sustaining a spell: -2 dice on every other test for each spell (Focused Concentration makes some free). Sustained spells cast from the dice roller are tracked on the Magic tab until you drop them.
- Counterspelling: a magician protecting the target adds their Sorcery to the Defense test against a spell (pick the protector in the attack dialog).
- Astral combat: Astral + Willpower against Intuition + Logic; DV is half the attacker's Charisma (a spirit's Force), Stun, resisted with Willpower.
- Summoning: Conjuring + Magic vs Force x 2 dice; services = net hits; drain = the spirit's hits. Your spirits' total Force can't exceed Magic x 3.
- Essence loss lowers Magic: -1 for each full point of Essence lost (rounded up).
- Initiation: 10 + new grade Karma; each grade raises the Magic maximum by 1 and gives a metamagic.""",
    "Matrix": """**Matrix**
- A cyberdeck gives Attack and Sleaze; Data Processing and Firewall come from your cyberjack (or commlink, or RCC).
- Matrix Attack Rating = Attack + Sleaze; Matrix Defense Rating = Data Processing + Firewall. The side 4+ ahead gains Edge (2 per round at most).
- Legal actions use Electronics; illegal ones (hacking) use Cracking. Every action and its test is in the Matrix actions list.
- Devices and hosts defend with their rating x 2. In the dice roller, give the target's rating and ShadowGrid rolls its defense.
- Overwatch Score: on every illegal action the defender's hits are added (+1 when a hacking program helps). At 40 the GOD converges: the device is bricked, you are dumped (dumpshock in VR: 3 Stun cold-sim, 3 Physical hot-sim, resisted with Willpower) and your location is reported. The GM sees the score; you only know it after Check Overwatch Score.
- A device's Matrix condition monitor is 8 + Device Rating/2; every 3 boxes is −1 die on Matrix actions; full, it's bricked. A technomancer's living persona takes Matrix damage on the Stun track.
- Data Spike: half your Attack Rating (round up) + net hits Matrix damage. Matrix damage isn't resisted, unless Biofeedback Filter runs (then Device Rating or Body). Tarpit: 1 + net hits.
- IC uses the host rating x 2 for its tests and Defense. See the IC topics.
- Noise: −1 per point on Matrix tests (distance, walls, jamming, spam zones). Above your Device Rating you can't reach the Matrix at all. Set it in the Matrix section of your sheet.
- Reconfigure Matrix Attribute (Minor): swap two of your persona's ratings. With Configurator running, save a setup and switch to it at once.
- Programs: Toolbox +1 Data Processing; Armor +2 Matrix Defense Rating; Overclock +2 dice, one of them the Wild Die; Encryption +2 on Encrypt File, Decryption +2 on Crack File; Browse, Edit, Stealth and Trace give 1 Edge for Matrix Search, Edit File, Hide and Trace Icon (spend it on that roll or lose it); Signal Scrubber −2 noise; Virtual Machine +2 program slots, but 1 extra box when you're hit; Exploit −2 to your target's Defense Rating; Fork hits two targets without splitting the pool; Lockdown link-locks whoever you damage; Baby Monitor shows your Overwatch Score; Defuse lets you resist a Data Bomb.""",
    "Technomancers": """**Technomancers**
- Living persona: Attack = Charisma, Sleaze = Intuition, Data Processing = Logic, Firewall = Willpower.
- Threading a complex form: Electronics + Resonance (Resonance Spike uses Cracking). Fading: resist the form's Fade Value with Willpower + Logic; Physical if it exceeds Resonance.
- Compiling a sprite: Tasking + Resonance vs Level x 2 dice; tasks = net hits; fading = the sprite's hits. One unregistered sprite at a time; up to Resonance registered.
- Submersion: 10 + new grade Karma; each grade raises the Resonance maximum and gives an echo.""",
    "Rigging and vehicles": """**Rigging and vehicles**
- Vehicles and drones have Handling, Acceleration, Speed Interval, Top Speed, Body, Armor, Pilot and Sensor.
- Control: at the controls Piloting + Reaction; jumped in (control rig) Piloting + Intuition + the rig's rating. Handling tests have the vehicle's Handling as threshold.
- A drone on its own rolls its autosoft with Sensor (Clearsight, Electronic Warfare, Targeting) or Pilot (Maneuvering, Evasion, Stealth), and 4D6 initiative.
- Speed: track it in meters per combat round; change it by at most the Acceleration each round. Distance this round = the speed at the start ± half the change. Every Speed Interval passed is −1 die (cumulative) on Handling tests and attacks from the vehicle. A crash does (speed / 10) damage to those inside.
- Weapon mounts: Body / 3 (round down). A standard mount takes an assault rifle or smaller; a heavy mount (machine guns, sniper rifles, launchers) counts as two. Buy the mounts in the store and install them from your sheet.
- Firing a mounted weapon: Engineering + Logic (jumped in or at a gunner's station). A drone firing on its own: Targeting autosoft + Sensor (Sensor − 1 without the autosoft).
- A vehicle's condition monitor is 8 + Body/2 (one track); every 3 boxes of damage raise its Handling by 1.
- Defense Rating: the driver's Piloting (a drone's Pilot) + Armor. Damage is resisted with Body. Stun with a DV up to the Body does nothing; stronger Stun counts as Physical.
- Ramming: Attack Rating Piloting + Sensor; DV = Body / 2 (round up) + 1 per current Speed Interval + net hits, Physical. A soft target does its Body / 4 back.
- On the map: every vehicle and drone is an NPC template, and a runner's own vehicle can be placed as a marker that shares its damage with their sheet.""",
    "Toxins, drugs and diseases": """**Toxins, drugs and diseases**
- Exposure: resist with Body + Willpower; each hit lowers the Power by 1. Whatever Power is left applies.
- Damage (Stun or Physical) equals the Power left; effects add statuses: Nausea (Nauseated), Disorientation (Dazed), Paralysis (Immobilized), ongoing damage (Poisoned).
- Drugs: their bonuses last for the duration, then the crash applies. Taking a dose uses one up from your gear.
- Some substances call for an addiction test (Body + Willpower against a threshold). Failing gives the Addiction quality, or raises its level.
- The GM keeps the game's list of substances (the Companion's are built in) and exposes runners from their sheet.""",
    "Reputation and Heat": """**Reputation and Heat**
- Reputation is what the street thinks of you; Heat is how much attention the authorities pay you.
- Both are set by the GM; every change is noted in the table log.""",
    "Availability and contacts": """**Availability and contacts**
- Every item has an Availability (usually 1-6, up to 9). (L) needs a license; (I) is illegal.
- During character creation the limit is Availability 6.
- Afterwards, legal items up to Availability 2 are always on sale. Anything else needs a contact who covers that kind of goods and whose Connection is higher than the Availability.
- Contacts added or changed after approval must be confirmed by the GM before they unlock anything.
- Selling gear back pays the game's sell percentage, and also needs a contact who could handle the item.
- Implant grades: used (Essence x1.1, price x0.5, Availability -1), alphaware (x0.8, x1.2, +1), betaware (x0.7, x1.5, +2), deltaware (x0.5, x2.5, +3).
- Trolls pay 10% more for everything, dwarfs 10% more for armor and clothing.""",
    "Advancement": """**Advancement**
- Attribute or active skill: 5 x the new rating.
- Specialization 5; expertise 5 (needs the specialization and the skill at 5+; then you can learn a new specialization).
- Knowledge skill 3; language 3, then +5 per level (Specialist, Expert).
- Positive quality: 2 x its cost. Removing a negative quality: 2 x its bonus.
- Spell, ritual or complex form 5.
- Initiation / submersion: 10 + the new grade.
- Karma can be traded for nuyen at 2,000¥ each (5,000¥ with In Debt).""",
    "Grappling": """**Grappling**
- An unarmed Close Combat + Agility attack. On a hit, instead of damage: Strength + net hits vs the target's Strength. More hits and they're restrained.
- Restrained: they can only try to break free (spells and complex forms still work), take −4 on Defense tests, and every attacker gains 1 Edge on them. An attack that misses them may hit the one holding them (who defends against the same roll).
- The grappler, each as a Major Action with the unarmed Attack Rating: Restrain (Close Combat + Strength vs Close Combat + Strength, −4 for them; fail and they're free), Squeeze (vs Strength + Reaction, −4: Strength/2 + net hits Stun), Tackle (vs Body + Strength: they go Prone and take your Body + net hits Stun, resisted with Body).
- The one held: Break free (Close Combat + Strength vs the grappler's, no −4).
- In ShadowGrid: tick Grapple in the attack dialog; the follow-ups are in the combatant's menu on the initiative strip.""",
    "Edge actions in combat": """**Edge actions in combat**
They cost Edge, not actions, and count as your one Edge expenditure of the round.
- Shank (1, melee blade): the called shot at −2 instead of −4.
- Tumble (1, melee): damage above the target's Body knocks them Prone.
- Tactical Roll (1, with Hit the Dirt): no Prone penalty on your melee attacks this round, and no −2 from Prone against Close or Near attacks until the end of the next round.
- Knockout Blow (2, melee): damage above the target's Willpower fills their Stun track.
- Fire from Cover (2, ranged, from Cover IV): no −2 for attacking from full cover.
- Wrest (2, with a successful Block): Close Combat + Agility, threshold the attacker's Strength: equal, their weapon falls; more, you take it.
- Anticipation (4, ranged Multiple Attacks): the full pool against every target.
- Called shot: Vitals (5): +3 DV. Disarm (5): no damage, the weapon goes flying.""",
    "Lifestyles": "**Lifestyles**\nMonthly cost, charged by the GM at the start of each month:\n" + "\n".join(f"- {k}: {v:,}¥" for k, v in K.LIFESTYLES.items())
                  + "\n- SINner adds 10%; a suprathyroid gland adds 25%.\nNuyen can go negative: you're in debt.",
}

ACTIONS = {
    "Minor": ["Activate/Deactivate Focus", "Avoid Incoming", "Block", "Call a Shot", "Change Device Mode", "Command Drone",
              "Command Spirit", "Dismiss Spirit", "Dodge", "Drop Object", "Drop Prone", "Hit the Dirt", "Move",
              "Multiple Attacks", "Quick Draw", "Reload Smartgun", "Shift Perception", "Stand Up", "Take Aim", "Take Cover", "Trip"],
    "Major": ["Assist", "Astral Projection", "Attack", "Banish Spirit", "Cast Spell", "Cleanse", "Counterspell", "Full Defense", "Intercept",
              "Manifest", "Observe in Detail", "Pick Up/Put Down Object", "Ready Weapon", "Reload Weapon", "Rigger Jump In",
              "Sprint", "Summon Spirit", "Use Simple Device", "Use Skill"],
}
ACTION_NOTES = {
    "Move": "Move up to 10 meters. Once per turn.", "Sprint": "Move 15 meters, +1 per hit on Athletics + Agility.",
    "Block": "Add Close Combat to one melee defense test.", "Dodge": "Add Athletics to one defense test.",
    "Full Defense": "Add Willpower to every defense test until your next combat round.",
    "Hit the Dirt": "+2 dice on the defense test, then you're Prone (-2 on active skills until you stand up).",
    "Take Aim": "+1 die on your next attack with a firearm, bow or other ranged weapon; once per round, up to your Willpower. It carries over to later rounds, and is lost on a turn where you neither aim nor attack.",
    "Trip": "Melee, with the attack: −2 to the base DV; on a hit the target rolls Athletics + Agility with the DV as threshold, or goes Prone.",
    "Counterspell": "Sorcery + Magic. Boosted defense: the hits add to the Defense of everyone protected against spells, for Magic rounds. Dispelling: against a sustained spell, vs Drain Value × 2; each net hit cancels one of the spell's hits.",
    "Call a Shot": "With an attack: -4 dice for +2 DV.", "Multiple Attacks": "Split your pool between several targets.",
    "Intercept": "Interrupt: a melee attack on an enemy moving through your reach. Counts as your Attack Major Action.",
    "Reload Weapon": "Reload a weapon (Major). Reload Smartgun does it as a Minor.",
    "Drop Prone": "You gain the Prone status.", "Take Cover": "You gain Cover I-IV from what is around you.",
    "Attack": "Make one attack with a weapon or unarmed.", "Cast Spell": "Cast one spell.", "Summon Spirit": "Call a spirit.",
}


def _item_text(e):
    lines = [f"**{e['name']}**", f"{e['cat']} · {e.get('sub', '')}"]
    o = CAT.offer(e)
    rr = CAT.rating_range(e)
    av = f"{e.get('avail')}" if rr else CAT.avail_text(o["avail"], o["legal"])
    price = f"{e.get('cost')}¥ (R = rating {rr[0]}-{rr[1]})" if rr and isinstance(e.get("cost"), str) else f"{o['cost']:,}¥"
    lines.append(f"- Availability: {av}")
    lines.append(f"- Cost: {price}")
    for k, label in (("dv", "DV"), ("ar", "Attack Ratings"), ("modes", "Modes"), ("ammo", "Ammo"), ("dr", "Defense"),
                     ("capacity", "Capacity"), ("essence", "Essence"), ("device_rating", "Device Rating"),
                     ("attack", "Attack"), ("sleaze", "Sleaze"), ("data_processing", "Data Processing"),
                     ("firewall", "Firewall"), ("program_slots", "Program slots"), ("dv_gz", "DV ground zero"),
                     ("dv_close", "DV close"), ("dv_near", "DV near"), ("blast", "Blast"), ("handling", "Handling"),
                     ("accel", "Acceleration"), ("speed_interval", "Speed interval"), ("top_speed", "Top speed"),
                     ("body", "Body"), ("armor", "Armor"), ("pilot", "Pilot"), ("sensor", "Sensor"), ("seats", "Seats")):
        if e.get(k) not in (None, ""):
            lines.append(f"- {label}: {e[k]}")
    if e.get("skill"):
        lines.append(f"- Skill: {e['skill']}" + (f" ({e['spec']})" if e.get("spec") else ""))
    if e.get("desc"):
        lines += ["", e["desc"]]
    return "\n".join(lines)


def _npc_text(t):
    lines = [f"**{t['name']}**", t.get("kind", "") + (f" · Professional Rating {t['pr']}" if t.get("pr") is not None else "")]
    if t.get("attrs"):
        lines.append(" ".join(f"{k[:3].upper()} {v}" for k, v in t["attrs"].items()))
    for k, label in (("dr", "Defense Rating"), ("defense_rating", "Defense Rating"), ("init", "Initiative"), ("ac", "Actions"),
                     ("cm", "Condition monitor"), ("move", "Movement"), ("skills", "Skills"), ("knowledge_skills", "Knowledge"),
                     ("augmentations", "Augmentations"), ("powers", "Powers"), ("spells", "Spells"), ("gear", "Gear"),
                     ("weaknesses", "Weaknesses"), ("notes", "Notes"), ("note", "Notes")):
        if t.get(k):
            lines.append(f"- {label}: {t[k]}")
    for w in t.get("weapons") or []:
        lines.append(f"- Weapon: {w}")
    return "\n".join(lines)


def build():
    topics, tree = dict(RULES), []
    tree.append({"title": "Rules", "children": [{"title": t, "children": []} for t in RULES]})
    # statuses
    for name, s in K.STATUSES.items():
        topics[f"{name} (status)"] = f"**{name}**\n{s['icon']} {s['desc']}"
    tree.append({"title": "Statuses", "children": [{"title": f"{n} (status)", "children": []} for n in K.STATUSES]})
    # actions
    act = []
    for kind, names in ACTIONS.items():
        kids = []
        for n in names:
            t = f"{n} ({kind})"
            topics[t] = f"**{n}**\n{kind} Action.\n" + ACTION_NOTES.get(n, "")
            kids.append({"title": t, "children": []})
        act.append({"title": f"{kind} actions", "children": kids})
    tree.append({"title": "Actions", "children": act})
    # the Matrix: actions, IC, Edge actions
    mx_kids = []
    for a in MX.MATRIX_ACTIONS.values():
        t = f"{a['name']} (Matrix)"
        test = f"{a['pool'][0]} + {a['pool'][1]}" if a.get("pool") else "no test"
        dfn = (" vs " + " + ".join(a["defense"])) if isinstance(a.get("defense"), list) else (" vs rating x 2" if a.get("defense") == "rating" else (f" vs {a['defense']} dice" if a.get("defense") else ""))
        topics[t] = (f"**{a['name']}**\n{'Legal' if a['legal'] else 'Illegal'} · {a['action']} action · access: {a['access']}\n"
                     f"- Test: {test}{dfn}\n- {a['effect']}" + ("" if a["legal"] else "\n- Illegal: the defender's hits raise your Overwatch Score."))
        mx_kids.append({"title": t, "children": []})
    ic_kids = []
    for name, eff in MX.IC.items():
        t = f"{name} (IC)"
        topics[t] = f"**{name}**\nIC. Uses the host rating x 2 for its tests and Defense.\n- {eff}"
        ic_kids.append({"title": t, "children": []})
    topics["Matrix Edge actions"] = "**Matrix Edge actions**\nNeed a cyberjack or Resonance.\n" + "\n".join(f"- {n} ({k} Edge): {d}" for k, n, d in MX.MATRIX_EDGE)
    tree.append({"title": "Matrix", "children": [{"title": "Matrix actions", "children": mx_kids}, {"title": "IC", "children": ic_kids},
                                                  {"title": "Matrix Edge actions", "children": []}]})
    soft_kids = []
    for name, (d, attr) in RIG.AUTOSOFTS.items():
        t = f"{name} (autosoft)"
        topics[t] = f"**{name} autosoft**\nRating 1-{RIG.AUTOSOFT_RATING[1]}, rolled with the drone's {attr}.\n- {d}"
        soft_kids.append({"title": t, "children": []})
    tree.append({"title": "Rigging", "children": [{"title": "Autosofts", "children": soft_kids}]})
    # characters
    mt = []
    groups_mt = {}
    for name, m in K.METATYPES.items():
        lines = [f"**{name}**", m["desc"]]
        if m.get("base") not in (None, name):
            lines.append(f"{'Metasapient' if m['base'] == 'Metasapient' else m['base'] + ' variant'} ({m.get('source', 'core')}). "
                         f"Costs {m.get('karma', 0)} Karma at character creation.")
        lines.append("Attribute maximums (others 6):")
        lines += [f"- {k}: {v}" for k, v in m["max"].items()]
        if m.get("qualities"):
            racial = [q + (f" {m['quality_levels'][q]}" if m.get("quality_levels", {}).get(q) else "") +
                      (f" ({m['quality_choices'][q]})" if m.get("quality_choices", {}).get(q) else "") for q in m["qualities"]]
            lines.append("Racial qualities: " + ", ".join(racial))
        if m.get("weapons"):
            lines.append("Natural weapons: " + ", ".join(f"{w['name']} DV {w['dv']}, AR {w['ar']}" for w in m["weapons"]))
        if m.get("dr"):
            lines.append(f"Natural armor: +{m['dr']} Defense Rating.")
        if m.get("move"):
            lines.append(f"Movement: {m['move'][0]}/{m['move'][1]}/+{m['move'][2]}" + (f"; {m['move_note']}" if m.get("move_note") else ""))
        topics[name] = "\n".join(lines)
        groups_mt.setdefault(m.get("base") if m.get("base") not in (None, name) else name, []).append(name)
    for base in ("Human", "Elf", "Dwarf", "Ork", "Troll"):
        kids = [{"title": n, "children": []} for n in groups_mt.get(base, []) if n != base]
        mt.append({"title": base, "children": kids})
    mt.append({"title": "Metasapients", "children": [{"title": n, "children": []} for n in groups_mt.get("Metasapient", [])]})
    # Infected (HMHVV)
    infk = []
    from . import companion6e as C
    for name, inf in C.INFECTED.items():
        t = f"{name} (Infected)"
        bases = "; ".join(f"{b}: " + ", ".join(f"{k[:3].upper()} {v}" for k, v in mx.items()) for b, mx in inf["bases"].items())
        cost = f"{inf['karma']} Karma" + (f" (+{inf['non_human_extra']} for non-humans)" if inf.get("non_human_extra") else "") + \
            (f" (−{inf['awakened_discount']} if already Awakened)" if inf.get("awakened_discount") else "")
        lines = [f"**{name}**", f"Infected quality, {cost}. {C.STRAINS[inf['strain']]}",
                 f"Base metatype and new maximums: {bases}" + (" (other metatypes: base +1 BOD, STR, WIL, +2 REA, CHA)" if inf.get("any_base_mods") else ""),
                 "Powers: " + ", ".join(inf["powers"]) + (" (+1 Initiative Die)" if inf.get("init_dice") else "") + (" (+2 movement)" if inf.get("move") else "")]
        if inf.get("free_optional"):
            lines.append(f"Free optional power: {inf['free_optional']}.")
        if inf.get("optional"):
            lines.append("Optional powers: " + ", ".join(f"{o} ({C.INFECTED_OPTIONAL_POWERS.get(o, 8)} K)" for o in inf["optional"]))
        lines.append("Weaknesses: " + ", ".join(inf["weaknesses"]) + ("; " + ", ".join(f"−{n} {a}" for a, n in inf["minus"].items()) if inf.get("minus") else ""))
        lines.append("Attacks: " + ", ".join(f"{w} DV {dv}, AR {ar}" for w, dv, ar in inf.get("weapons") or []))
        if inf.get("notes"):
            lines.append(inf["notes"])
        lines.append("All Infected are dual-natured and Awakened (Magic 1 or more), can't be technomancers or take Magic Resistance, "
                     "and pay 30% more for their lifestyle.")
        topics[t] = "\n".join(lines)
        infk.append({"title": t, "children": []})
    for name, txt in C.CRITTER_POWERS.items():
        t = f"{name} (critter power)"
        topics[t] = f"**{name}**\n{txt}"
        infk.append({"title": t, "children": []})
    quals = {"Positive": [], "Negative": [], "Metagenic (positive)": [], "Metagenic (negative)": [], "Quality paths": [], "Racial traits": []}
    for name, q in K.QUALITIES.items():
        side = "Positive" if q["karma"] > 0 else "Negative"
        group = q.get("group", "")
        bucket = ("Racial traits" if q.get("racial_only") else "Quality paths" if group == "Quality path"
                  else f"Metagenic ({side.lower()})" if group not in ("", "Positive", "Negative") else side)
        t = f"{name} (quality)"
        kind = "Racial trait (comes with a metatype)" if q.get("racial_only") else f"{side} quality, {abs(q['karma'])} Karma" + \
            (f" per level (max {q['levels']})" if q.get("levels") else "")
        src = f" {q['source']}{', ' + group if group and group not in ('Positive', 'Negative') else ''}." if q.get("source") else ""
        topics[t] = f"**{name}**\n{kind}.{src}\n{q['desc']}"
        quals[bucket].append({"title": t, "children": []})
    skills = []
    for name, s in K.SKILLS.items():
        t = f"{name} (skill)"
        topics[t] = (f"**{name}**\nLinked attribute: {s['attr']}. " + ("Can be used untrained." if s["untrained"] else "Can't be used untrained.")
                     + "\nSpecializations: " + ", ".join(s["specs"]))
        skills.append({"title": t, "children": []})
    tree.append({"title": "Characters", "children": [{"title": "Metatypes", "children": mt}, {"title": "Infected (HMHVV)", "children": infk},
                                                     {"title": "Skills", "children": skills},
                                                     {"title": "Positive qualities", "children": quals["Positive"]},
                                                     {"title": "Negative qualities", "children": quals["Negative"]},
                                                     {"title": "Metagenic qualities (SURGE)", "children": quals["Metagenic (positive)"] + quals["Metagenic (negative)"]},
                                                     {"title": "Quality paths", "children": quals["Quality paths"]},
                                                     {"title": "Racial traits", "children": quals["Racial traits"]}]})
    # gear
    gear = []
    for cat in G.STORE_CATEGORIES:
        kids = []
        for e in CAT.ITEMS:
            if e["cat"] == cat:
                t = e["name"] if e["name"] not in topics else f"{e['name']} ({cat})"
                topics[t] = _item_text(e)
                kids.append({"title": t, "children": []})
        gear.append({"title": cat, "children": kids})
    from . import packs as PK
    pk = {}
    for e in PK.PACK_ENTRIES:
        t = e["name"] if e["name"] not in topics else f"{e['name']} (PACK)"
        lines = [f"**{e['name']}**", f"{e['sub']}, {e['cost']:,}¥ · Availability {e['avail']}" +
                 (f" · Essence {e['essenceN']}" if e.get("essenceN") else "") + f". {e['desc']}"]
        if e.get("packGrades"):
            lines.append("Other grades: " + ", ".join(f"{g} {v['cost']:,}¥ / {v['essence']} Essence" for g, v in e["packGrades"].items()))
        for k, lab in (("includes", "Includes"), ("skills", "Recommended skills"), ("licenses", "Fake licenses for")):
            if e.get(k):
                lines.append(f"{lab}: {e[k]}")
        lines.append("Contents:")
        lines += [f"- {x}" for x in e["contents"]]
        topics[t] = "\n".join(lines)
        pk.setdefault(e["sub"], []).append({"title": t, "children": []})
    gear.append({"title": "PACKs", "children": [{"title": g, "children": v} for g, v in pk.items()]})
    tree.append({"title": "Gear", "children": gear})
    # magic
    spells = {}
    for s in M.SPELLS:
        t = f"{s['name']} (spell)"
        topics[t] = (f"**{s['name']}**\n{s['category']} spell" + (f", {s['kind']}" if s.get("kind") else "")
                     + f"\n- Range: {s['range']}\n- Type: {'Mana' if s['type'] == 'M' else 'Physical'}\n- Duration: {s['duration']}"
                     + f"\n- Drain: {s['drain']}" + (f"\n- Damage: {s['damage']}" if s.get("damage") else "") + f"\n\n{s['desc']}")
        spells.setdefault(s["category"], []).append({"title": t, "children": []})
    magic = [{"title": f"{k} spells", "children": v} for k, v in spells.items()]
    rit = []
    for r in M.RITUALS:
        t = f"{r['name']} (ritual)"
        topics[t] = f"**{r['name']}**\nRitual ({r['keywords']}), threshold {r['threshold']}" + (f", {r['time']}" if r.get("time") else "") + f".\n{r['desc']}"
        rit.append({"title": t, "children": []})
    magic.append({"title": "Rituals", "children": rit})
    pw = []
    for p in M.ADEPT_POWERS:
        t = f"{p['name']} (power)"
        topics[t] = f"**{p['name']}**\n{p['cost']} PP" + (" per level" if p.get("levels") else "") + f", {p['activation']}.\n{p['desc']}"
        pw.append({"title": t, "children": []})
    magic.append({"title": "Adept powers", "children": pw})
    mm = []
    for m in M.METAMAGICS:
        t = f"{m['name']} (metamagic)"
        topics[t] = f"**{m['name']}**\n{m['desc']}"
        mm.append({"title": t, "children": []})
    magic.append({"title": "Metamagics", "children": mm})
    ms = []
    for name, txt in M.MENTOR_SPIRITS.items():
        t = f"{name} (mentor)"
        topics[t] = f"**{name}**\n" + txt.replace(". ", ".\n")
        ms.append({"title": t, "children": []})
    magic.append({"title": "Mentor spirits", "children": ms})
    sp = []
    for name, s in M.SPIRITS.items():
        t = f"Spirit of {name}" if name != "Beasts" else "Spirit of Beasts"
        offs = ", ".join(f"{k[:3].upper()} F{'+' if v >= 0 else ''}{v}" if v else f"{k[:3].upper()} F" for k, v in s["attrs"].items())
        topics[t] = (f"**{t}**\n{offs}\n- Initiative: {s['init'].replace('F', 'Force')} + {s.get('init_dice', 2)}D6\n- Defense Rating: {s['dr'].replace('F', 'Force')}"
                     f"\n- Skills (at Force): {', '.join(s['skills'])}\n- Powers: {', '.join(s['powers'])}\n- Optional (1 per 3 Force): {', '.join(s.get('optional', []))}")
        sp.append({"title": t, "children": []})
    magic.append({"title": "Spirits", "children": sp})
    tree.append({"title": "Magic", "children": magic})
    # resonance
    res = []
    cf = []
    for f in M.COMPLEX_FORMS:
        t = f"{f['name']} (complex form)"
        topics[t] = f"**{f['name']}**\nFade {f['fade']}, duration {f['duration']}.\n{f['desc']}"
        cf.append({"title": t, "children": []})
    res.append({"title": "Complex forms", "children": cf})
    spr = []
    for name, s in M.SPRITES.items():
        t = f"{name} sprite"
        topics[t] = (f"**{t}**\nAttack L{s['attack']:+d}, Sleaze L{s['sleaze']:+d}, Data Processing L{s['data_processing']:+d}, Firewall L{s['firewall']:+d}"
                     f"\n- Skills: {', '.join(s['skills'])}\n- Powers: {', '.join(s['powers'])}")
        spr.append({"title": t, "children": []})
    res.append({"title": "Sprites", "children": spr})
    ech = []
    for e in M.ECHOES:
        t = f"{e['name']} (echo)"
        topics[t] = f"**{e['name']}**\n{e['desc']}"
        ech.append({"title": t, "children": []})
    res.append({"title": "Echoes", "children": ech})
    prog = []
    for kind, ps in M.PROGRAMS.items():
        for name, desc in ps.items():
            t = f"{name} (program)"
            topics[t] = f"**{name}**\n{kind} program.\n{desc}"
            prog.append({"title": t, "children": []})
    res.append({"title": "Programs", "children": prog})
    tree.append({"title": "Matrix & Resonance", "children": res})
    # NPCs
    groups = {}
    for t in N.NPC_TEMPLATES:
        title = f"{t['name']} (NPC)"
        topics[title] = _npc_text(t)
        groups.setdefault({"Grunt": "Grunts", "Contact": "Contacts", "Critter": "Critters", "Infected": "Infected"}.get(t.get("kind"), "Other"), []).append({"title": title, "children": []})
    tree.append({"title": "NPCs", "children": [{"title": k, "children": v} for k, v in groups.items()]})
    return {"tree": tree, "topics": topics}

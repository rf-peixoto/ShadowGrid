"""In-app rules wiki, generated from the game data plus short rule summaries
written for this app (not the book's text)."""
from . import catalog as CAT
from . import core6e as K
from . import gear6e as G
from . import magic6e as M
from . import npc6e as N

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
- Gain Edge from the situation: Attack Rating beating Defense Rating by 4 or more, better vision, cover, and so on. At most 2 per combat round. In ShadowGrid the GM awards it by hand.
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
- Ranges: Close 0-3 m, Near 4-50 m, Medium 51-250 m, Far 251-500 m, Extreme 500+ m. A weapon without an Attack Rating at a range can't be used there.""",
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
- Medkit (within an hour): same test plus the medkit's rating; each extra hit heals 1 box of any kind. Uses one set of supplies.
- Magic: Sorcery + Magic with a Heal spell, same threshold; each net hit heals 1 box.
- None of those heal drain.
- Natural recovery: Body + Willpower per hour of rest heals Stun; Body + Body per day heals Physical (overflow: minus wound modifiers). A Biotech-trained helper adds +2 dice.""",
    "Magic": """**Magic**
- Spellcasting: Sorcery + Magic. Attack Rating for spells: Magic + tradition attribute.
- Drain: resist the spell's Drain Value with Willpower + tradition attribute (Hermetic: Logic; Shamanic: Charisma). Drain is Stun unless the Drain Value is higher than your Magic, then Physical.
- Amp Up (combat spells): +1 DV for +2 drain. Increase Area: +2 m radius for +1 drain.
- Indirect combat spells do Magic/2 + net hits and are soaked with Body; direct spells do net hits and can't be soaked.
- Sustaining a spell: -2 dice on other tests.
- Summoning: Conjuring + Magic vs Force x 2 dice; services = net hits; drain = the spirit's hits. Your spirits' total Force can't exceed Magic x 3.
- Essence loss lowers Magic: -1 for each full point of Essence lost (rounded up).
- Initiation: 10 + new grade Karma; each grade raises the Magic maximum by 1 and gives a metamagic.""",
    "Matrix": """**Matrix**
- A cyberdeck gives Attack and Sleaze; Data Processing and Firewall come from your cyberjack (or commlink).
- Matrix Attack Rating = Attack + Sleaze; Matrix Defense Rating = Data Processing + Firewall.
- A device's Matrix condition monitor is 8 + Device Rating/2.
- Programs run in the deck's program slots.
- In ShadowGrid, the Matrix itself is played on a GridMap map.""",
    "Technomancers": """**Technomancers**
- Living persona: Attack = Charisma, Sleaze = Intuition, Data Processing = Logic, Firewall = Willpower.
- Threading a complex form: Electronics + Resonance (Resonance Spike uses Cracking). Fading: resist the form's Fade Value with Willpower + Logic; Physical if it exceeds Resonance.
- Compiling a sprite: Tasking + Resonance vs Level x 2 dice; tasks = net hits; fading = the sprite's hits. One unregistered sprite at a time; up to Resonance registered.
- Submersion: 10 + new grade Karma; each grade raises the Resonance maximum and gives an echo.""",
    "Rigging and vehicles": """**Rigging and vehicles**
- Vehicles and drones have Handling, Acceleration, Speed Interval, Top Speed, Body, Armor, Pilot and Sensor.
- A vehicle's condition monitor is 8 + Body/2; Handling worsens by 1 every 3 boxes; it breaks down when full.
- A control rig adds its rating to vehicle tests while jumped in.
- Drones run autosofts in slots equal to half their Pilot (round up).""",
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
    "Lifestyles": "**Lifestyles**\nMonthly cost, charged by the GM at the start of each month:\n" + "\n".join(f"- {k}: {v:,}¥" for k, v in K.LIFESTYLES.items())
                  + "\n- SINner adds 10%; a suprathyroid gland adds 25%.\nNuyen can go negative: you're in debt.",
}

ACTIONS = {
    "Minor": ["Activate/Deactivate Focus", "Avoid Incoming", "Block", "Call a Shot", "Change Device Mode", "Command Drone",
              "Command Spirit", "Dismiss Spirit", "Dodge", "Drop Object", "Drop Prone", "Hit the Dirt", "Intercept", "Move",
              "Multiple Attacks", "Quick Draw", "Reload Smartgun", "Shift Perception", "Stand Up", "Take Aim", "Take Cover", "Trip"],
    "Major": ["Assist", "Astral Projection", "Attack", "Banish Spirit", "Cast Spell", "Cleanse", "Counterspell", "Full Defense",
              "Manifest", "Observe in Detail", "Pick Up/Put Down Object", "Ready Weapon", "Reload Weapon", "Rigger Jump In",
              "Sprint", "Summon Spirit", "Use Simple Device", "Use Skill"],
}
ACTION_NOTES = {
    "Move": "Move up to 10 meters. Once per turn.", "Sprint": "Move 15 meters, +1 per hit on Athletics + Agility.",
    "Block": "Add Close Combat to one melee defense test.", "Dodge": "Add Athletics to one defense test.",
    "Full Defense": "Add Willpower to every defense test until your next combat round.",
    "Hit the Dirt": "+2 dice on the defense test, then you're Prone (-2 on active skills until you stand up).",
    "Take Aim": "+1 die on your next attack; once per round, carries over while you keep aiming.",
    "Call a Shot": "With an attack: -4 dice for +2 DV.", "Multiple Attacks": "Split your pool between several targets.",
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
    # characters
    mt = []
    for name, m in K.METATYPES.items():
        lines = [f"**{name}**", m["desc"], "Attribute maximums (others 6):"]
        lines += [f"- {k}: {v}" for k, v in m["max"].items()]
        if m.get("qualities"):
            lines.append("Racial qualities: " + ", ".join(m["qualities"]))
        topics[name] = "\n".join(lines)
        mt.append({"title": name, "children": []})
    quals = {"Positive": [], "Negative": []}
    for name, q in K.QUALITIES.items():
        side = "Positive" if q["karma"] > 0 else "Negative"
        t = f"{name} (quality)"
        topics[t] = f"**{name}**\n{side} quality, {abs(q['karma'])} Karma" + (f" per level (max {q['levels']})" if q.get("levels") else "") + f".\n{q['desc']}"
        quals[side].append({"title": t, "children": []})
    skills = []
    for name, s in K.SKILLS.items():
        t = f"{name} (skill)"
        topics[t] = (f"**{name}**\nLinked attribute: {s['attr']}. " + ("Can be used untrained." if s["untrained"] else "Can't be used untrained.")
                     + "\nSpecializations: " + ", ".join(s["specs"]))
        skills.append({"title": t, "children": []})
    tree.append({"title": "Characters", "children": [{"title": "Metatypes", "children": mt}, {"title": "Skills", "children": skills},
                                                     {"title": "Positive qualities", "children": quals["Positive"]},
                                                     {"title": "Negative qualities", "children": quals["Negative"]}]})
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
        groups.setdefault({"Grunt": "Grunts", "Contact": "Sample contacts", "Critter": "Critters"}.get(t.get("kind"), "Other"), []).append({"title": title, "children": []})
    tree.append({"title": "NPCs", "children": [{"title": k, "children": v} for k, v in groups.items()]})
    return {"tree": tree, "topics": topics}

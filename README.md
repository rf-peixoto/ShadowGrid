# ShadowGrid

One Flask web app for a Shadowrun 6E table. It merges two earlier tools:

- the **Shadowrun Manager** character sheet (every tab, all of its predefined
  gear, spells, powers, foci, qualities and the wiki), now a web page per
  player;
- **GridMap**, the fog-of-war map builder, unchanged in spirit: players only
  see what has been revealed to them and what their token has seen.

The GM (admin) runs the game. Players join through invite links.

## Map views

The map has two views, toggled with **Isometric view** in the sidebar or the
<kbd>I</kbd> key:

- **Isometric** (default for players and for the GM's Play mode): the map is
  rotated 45° and tilted, in the style of the SNES Shadowrun. Floors become
  raised slabs, and tokens, markers and room names stand upright with a
  ground shadow.
- **Flat**: the top-down GridMap view. It's the default in the GM's Edit
  mode, where precise painting is easier.

Everything (clicking, dragging, doors, fog, pings) works the same in both. The
player view opens centred on your own token (<kbd>C</kbd> re-centres,
<kbd>F</kbd> fits the whole map). PNG export is always top-down.

## Quick start

```bash
pip install -r requirements.txt
python app.py
```

On first start the console prints the bootstrapped GM account:

```
Username: admin
Password: <generated>      <- save it now, it is not shown again
```

Open http://127.0.0.1:5000 and sign in as `admin`. Change the password any time:

```bash
python app.py set-password
# or force it at startup:
GRIDMAP_ADMIN_PASSWORD='long random string' python app.py
```

## Running on the internet

Exactly like GridMap: `serve.py` (waitress) behind a TLS reverse proxy.

```bash
GRIDMAP_HTTPS=1 GRIDMAP_TRUST_PROXY=1 GRIDMAP_PORT=8000 python serve.py
```

| Variable | Meaning |
|---|---|
| `GRIDMAP_DB` | SQLite path (default `shadowgrid.db` next to `app.py`) |
| `GRIDMAP_HTTPS=1` | Secure cookies. Only when really served over https |
| `GRIDMAP_TRUST_PROXY=1` | Rate limits read `X-Forwarded-For` (only behind your own proxy) |
| `GRIDMAP_HOST` / `GRIDMAP_PORT` | Bind address |
| `GRIDMAP_LOGIN_POW_BITS` | Hashcash difficulty of the sign-in and invite forms (default 13) |
| `GRIDMAP_SERVER_IDENT` | `Server` header (default `nginx`) |

nginx:

```
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header Host $host;
}
```

GridMap's hardening is kept: hashed passwords, signed HttpOnly cookies, CSRF
header on every write, proof of work on sign-in and invite forms, per-player
rate limits, strict CSP, server-side fog filtering.

## How a game runs

### GM
1. **New game** on the home page, then **New map** / **Generate map** (the
   GridMap editor and generator, unchanged).
2. **Invite player**: a single-use link valid for 7 days. The player picks a
   username and password; that account only opens this game. Revoke unused
   links on the game page.
3. Players build their characters. A sheet they submit shows a **Waiting for
   approval** tag on the home page, the game page and the map editor. Open it,
   then **Approve** or **Send back** with a note.
4. In the map editor's **Play** mode, place tokens (Token tool or **Place**
   next to a runner), reveal rooms, open doors and move enemies. Give an enemy
   marker a **Body/Willpower** to get Physical and Stun condition monitors, and
   click its boxes to mark damage.
5. The **game page** has everything else:
   - **Runners**: sheet status, condition, Edge (+1, −1, refresh; or
     **Refresh everyone's Edge**), Karma, Nuyen, location, **Award Karma /
     Nuyen** to one, several or all runners (negative amounts take it away),
     reset a password, remove a runner.
   - **Runs**: create contracts with a reward, tasks (mandatory ones marked *)
     and the runners who take them. Tick tasks as they happen. **Complete &
     pay** credits each assigned runner the payout (reward × share of tasks
     done, editable). Abandon, reopen and delete are also here.
   - **Dice & log**: the GM roller (pool, threshold, Wild Die, initiative,
     hidden rolls) and the shared table log.
   - **History**: every Karma/Nuyen change in the game.
   - **Wiki**.
6. The GM can open any sheet and change anything for free; changes are logged
   as GM changes. **Gear → Give an item…** gives an item for free. Pick it from
   the store presets (searchable, optionally edited before giving) or make a
   custom item.

### Players
Tabs: **Map · Character · Store · Runs · Wiki**. Edge, Karma, Nuyen and health
are always visible in the top bar.

- **Map**: the GridMap player view (drag your token, click a reachable room,
  open doors, travel, double-click to ping) with your condition monitors, the
  dice roller and the table log in the sidebar.
- **Character**: Overview (identity, portrait, quick stats, Karma & Nuyen,
  history), Attributes, Skills, Qualities, Magic & Resonance, Gear (inventory,
  equip, use medkits), Combat (monitors, Edge, roller, log), Contacts,
  Background & notes.
- **Store**: every predefined item by category, with search, plus custom items.
  Buying deducts the price.
- **Runs**: read-only contracts assigned to you, with tasks, progress and
  payout.

## Rules implemented

**Dice (SR6 core).** Hits on 5-6. Glitch when more than half the dice show 1;
critical glitch when that comes with no hits. Optional threshold (success =
hits ≥ threshold, net hits shown). Wound modifiers are applied automatically
and can be switched off per roll. Pools come from the sheet (linked attribute
+ skill, +2 for a matching specialization, untrained = attribute −1, weapons
and spells pick their skill). A free roll is also available.

**Wild Die (official).** On 5-6 it counts as 3 hits. On a 1, none of the 5s
in the roll count.

**Edge (official Edge Boosts, one per roll).** Before rolling: 4 Edge adds your
Edge rating to the pool, with exploding 6s. After rolling: 1 Edge rerolls one
die (1 per die, select the dice), 2 Edge gives +1 to one die, 3 Edge buys a
hit, 4 Edge rerolls every failed die. Outside rolls: +3 Initiative (1), heal
1 Stun (3), heal 1 Physical (4), give an ally 1 Edge (2), and the narrative
boosts (negate an enemy's Edge, 2s count as glitches, special effect), which
are logged for the table. Edge is capped at 7. **Only the GM refreshes or
awards Edge.**

**Condition monitors.** Physical 8 + Body/2, Stun 8 + Willpower/2 (rounded up),
plus quality bonuses. −1 die per 3 boxes on each track. A full Stun track means
unconscious, and further Stun overflows into Physical one box per box. A full
Physical track means dying, with overflow boxes equal to Body; past those the
character is dead. Enemy markers use the same rules.

**Economy and approval.**
- *Draft* (until the GM approves): free edits to attributes, skills and
  identity. Qualities, spells, powers and foci are added and removed freely,
  and any purchase is refunded in full when removed.
- *Approved*: the player can no longer type Karma or Nuyen; they only change
  through actions.
  - Raising an attribute or skill costs the new rating × 5 Karma, a
    specialization 5 Karma, and a new spell 5 Karma.
  - Bonding a focus costs Force × its type multiplier.
  - You can trade Karma for Nuyen at 1 = 2,000¥, pay rent, and buy in the
    store. Purchases are final: removing an item discards it.
  - Metatype, role, magic type, initiation and qualities are locked; the GM
    can still change them.
  - Weapons and armor can be equipped or stored; after approval only an
    item's name, description and equipped state can be edited.
- Custom store items are tagged **custom** so the GM can spot them.

**Kept from the Shadowrun Manager**: metatype minimums, role bonuses, quality
effects, gear attribute and Initiative Dice bonuses, Essence loss and its
effect on Magic, bonded Power Focus, Power Points, armor, weapon accuracy,
medkits, rest, and the predefined content and wiki. Trolls cap Logic at 5, and
raising an attribute below the metatype minimum now starts from that minimum,
so no Karma is wasted.

**Removed**: the Matrix tab (GridMap covers it), GridMap's generic `4d6+2`
roller (replaced by the Shadowrun roller), GridMap's plain HP counter (replaced
by condition monitors), the desktop file save/load (characters live in the
database), and the desktop app's per-character run tracker (runs are now
managed by the GM).

## Look

The palette follows the Sixth World's neon look: teal-black, magenta for
actions and the brand, AR cyan for focus and selection. Panels are framed like
AR windows. Fonts are Rajdhani (headings, buttons), Barlow (text) and Share
Tech Mono (dice and numbers). All three are SIL Open Font License fonts, served
from `static/fonts` so no third-party requests are made. New maps use the
matching map palette; existing maps keep their colours (change them in
**Colors & settings**).

## Files

- `app.py`: sign-in, invite pages, page routes, CLI
- `core.py`: app, database schema, shared helpers, player auth
- `maps.py`: GridMap APIs (GM editor, fog, doors, markers, snapshots) and the
  player map view
- `game.py`: games, invites, accounts, sheets, dice and Edge, runs, awards,
  catalog
- `sr/data.py`: all predefined Shadowrun content and the wiki
- `sr/rules.py`: character model, derived stats, every sheet action and the
  economy
- `sr/dice.py`: SR6 dice engine (hits, glitches, Wild Die, Edge Boosts)
- `security.py`: auth decorators, hashcash, rate limits, headers
- `geometry.py`: server-side grid adjacency, door blocking, reveal (from
  GridMap)
- `static/`
  - `gridcore.js`, `procgen.js`, `editor.js`, `home.js`: GridMap (adapted)
  - `srui.js`: monitors, Edge, dice roller, table log, item editor
  - `sheet.js`: the character sheet (player and GM)
  - `play.js`: the player app
  - `gamepage.js`: the GM game dashboard
  - `gmsheet.js`, `wiki.js`, `api.js`, `login.js`, `pow.js`
- `static/fonts/`: self-hosted OFL fonts and their licenses
- `smoke_test.py`: end-to-end API test (`python smoke_test.py`)

*Shadowrun is a trademark of Catalyst Game Labs. This project is not
affiliated with Catalyst Game Labs or The Topps Company.*

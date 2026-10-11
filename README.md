# ShadowGrid

A self-hosted web app for running a **Shadowrun Sixth World** table. The game
master builds fog-of-war maps and hands out contracts. Players manage their
character sheets, explore the map, and roll dice with Edge. Everything stays in
sync live in the browser.

![A generated map in the isometric view](docs/img/gm-play-isometric.png)

**[Read the user guide →](docs/index.html)** for a walkthrough for players and
game masters, with screenshots.

## What it does

- **Character sheets** for every runner: attributes, skills and
  specializations, qualities, spells, adept powers, foci, gear, contacts and
  background. Metatype, role, cyberware and quality bonuses are applied
  automatically.
- **Approval workflow.** Players build freely while their sheet is a draft. The
  GM approves it, and from then on upgrades cost Karma and purchases are final.
- **Store** with every predefined weapon, armor, cyberware, bioware, magic
  item, electronic, medkit and piece of gear, plus custom items.
- **Fog-of-war maps** on square or hex grids, drawn by hand or generated. Each
  player sees only what their runner has explored, and doors block movement and
  sight.
- **Isometric view** in the style of the SNES Shadowrun, or a flat top-down
  view. Toggle with <kbd>I</kbd>.
- **SR6 dice roller**: pools from the sheet, hits and glitches, thresholds, the
  Wild Die and Edge Boosts. Every roll goes to a shared table log, and the GM
  can make hidden rolls.
- **Condition monitors** for runners and enemies, with wound modifiers and
  Stun/Physical overflow.
- **Runs (contracts)**: the GM assigns tasks and runners, ticks tasks as they
  happen, and closes the run. Each runner is paid automatically.
- **GM tools**: invite links, Karma and nuyen awards, Edge refresh, a full
  history of every Karma and nuyen change, snapshots of the map state, and a
  rules wiki.

| | |
|---|---|
| ![Player map view](docs/img/player-map.png) | ![Character overview](docs/img/player-overview.png) |
| Players see only what their runner has explored. | The character sheet during creation. |
| ![Store](docs/img/player-store.png) | ![GM runners table](docs/img/gm-runners.png) |
| The store. | The GM's runners table, with a sheet waiting for approval. |

## Quick start

Requires Python 3.9 or newer.

```bash
pip install -r requirements.txt
python app.py
```

On first start the console prints the game master account:

```
Username: admin
Password: <generated>      <- save it now, it is not shown again
```

Open http://127.0.0.1:5000 and sign in as `admin`. Create a game, add a map,
then use **Invite player** to send each player a single-use link. Their account
only opens that game.

Change the GM password any time:

```bash
python app.py set-password
# or force it at startup:
GRIDMAP_ADMIN_PASSWORD='long random string' python app.py
```

## Running on the internet

Use `serve.py` (waitress) behind a reverse proxy that terminates TLS, such as
nginx or Caddy:

```bash
GRIDMAP_HTTPS=1 GRIDMAP_TRUST_PROXY=1 GRIDMAP_PORT=8000 python serve.py
```

| Variable | Meaning |
|---|---|
| `GRIDMAP_DB` | SQLite database path (default `shadowgrid.db` next to `app.py`) |
| `GRIDMAP_HTTPS=1` | Secure cookies. Only set it when the site is really served over https |
| `GRIDMAP_TRUST_PROXY=1` | Rate limits read `X-Forwarded-For`. Only set it behind your own proxy |
| `GRIDMAP_HOST` / `GRIDMAP_PORT` | Bind address |
| `GRIDMAP_ADMIN_PASSWORD` | Sets the GM password at startup |
| `GRIDMAP_LOGIN_POW_BITS` | Proof-of-work difficulty of the sign-in and invite forms (default 13) |
| `GRIDMAP_SERVER_IDENT` | `Server` response header (default `nginx`) |

Example nginx location:

```
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header Host $host;
}
```

Security measures:
- Passwords are hashed, and sessions use signed HttpOnly cookies.
- Every write needs a CSRF header.
- The sign-in and invite forms require a proof of work.
- Requests are rate-limited per player.
- A strict Content Security Policy is applied.
- Fog of war is filtered on the server: a player's browser never receives
  unexplored parts of the map.

## Rules implemented

- **Dice:**
  - A 5 or 6 is a hit.
  - A glitch is when more than half of the dice show 1; a critical glitch is a
    glitch with no hits.
  - The threshold is optional: the roll succeeds when hits reach it.
  - Wound modifiers are applied automatically.
  - An untrained skill rolls the attribute −1, and a matching specialization
    adds +2.
- **Wild Die:** a 5 or 6 counts as 3 hits; a 1 cancels the 5s in the roll.
- **Edge Boosts**, one per roll:
  - Before rolling: 4 Edge adds your Edge rating to the pool, with exploding
    6s.
  - After rolling: 1 Edge per die rerolls the selected dice, 2 Edge adds +1 to
    one die, 3 Edge buys a hit, and 4 Edge rerolls every failed die.
  - Outside rolls: +3 Initiative for 1 Edge, healing 1 Stun for 3 or 1 Physical
    for 4, giving an ally 1 Edge for 2, and the narrative boosts.
  - Edge is capped at 7, and only the GM refreshes or awards it.
- **Condition monitors:**
  - Physical is 8 + Body/2 and Stun is 8 + Willpower/2, rounded up.
  - −1 die for every 3 boxes filled on each track.
  - A full Stun track means unconscious, and further Stun overflows into
    Physical.
  - A full Physical track means dying, with overflow boxes equal to Body.
- **Advancement after approval:**
  - Raising an attribute or skill costs the new rating × 5 Karma.
  - A specialization costs 5 Karma, and a new spell 5 Karma.
  - Bonding a focus costs Force × its type multiplier in Karma.
  - Karma trades for nuyen at 1 = 2,000¥.

## Project layout

- `app.py`: sign-in, invite pages, page routes, CLI
- `core.py`: app setup, database schema, shared helpers, player auth
- `maps.py`: map editor API, fog of war, doors, markers, snapshots, and the
  player map view
- `game.py`: games, invites, accounts, character sheets, dice and Edge, runs,
  awards
- `sr/data.py`: predefined Shadowrun content and the wiki
- `sr/rules.py`: character model, derived stats, sheet actions and the Karma
  and nuyen economy
- `sr/dice.py`: SR6 dice engine
- `security.py`: auth decorators, proof of work, rate limits, security headers
- `geometry.py`: grid adjacency, door blocking, line-of-sight reveal
- `static/`: front end, with no build step. The main files are:
  - `play.js`: the player app
  - `sheet.js`: the character sheet
  - `editor.js`: the GM map editor
  - `gamepage.js`: the GM game dashboard
  - `gridcore.js`: the map renderer
  - `srui.js`: the dice and condition widgets
  - `fonts/`: self-hosted OFL fonts with their licenses
- `templates/`: HTML pages
- `docs/`: user guide and screenshots
- `smoke_test.py`: end-to-end API test. Run it with `python smoke_test.py`

## License notes

The fonts Rajdhani, Barlow and Share Tech Mono are used under the SIL Open Font
License; see `static/fonts/`.

*Shadowrun is a trademark of Catalyst Game Labs and The Topps Company. This is
an unofficial fan project, not affiliated with or endorsed by them.*

"""Games: invites, player accounts, character sheets, the Shadowrun dice roller,
Edge, runs (contracts), Karma/Nuyen grants and the reference catalog."""
import json
import re
import secrets

from flask import abort, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from core import (APPROVED, DRAFT, GM_COLOR, INVITE_DAYS, PLAYER_COLORS, SUBMITTED, add_roll, app, body,
                  campaign_version, clamp_int, display_name, err, fetch_player_row, game_settings, get_db, ledger_add,
                  ledger_rows, load_char, new_id, now, player_required, roll_rows, row_to_player, save_char)
from maps import player_view, row_to_map
from security import admin_required, rate_limited
from sr import catalog as CAT
from sr import combat as X
from sr import core6e as K
from sr import dice as DICE
from sr import gear6e as G
from sr import magic6e as M
from sr import packs as PK
from sr import companion6e as SWC
from sr import rules as R
from sr import wiki as WIKI

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
RESERVED = {"admin", "gm", "root", "system"}
BOOST_WINDOW = 15 * 60        # seconds after a roll during which Edge Boosts may still be applied


# ====================================================================== catalog (static reference data)
CATALOG = None


def catalog():
    global CATALOG
    if CATALOG is None:
        CATALOG = {
            "attributes": R.ATTRS, "physical": K.PHYSICAL, "mental": K.MENTAL,
            "skills": K.SKILLS, "skillMax": K.SKILL_MAX, "skillMaxCreation": K.SKILL_MAX_CREATION,
            "metatypes": K.METATYPES, "baseMetatypes": K.BASE_METATYPES, "defaultMax": K.DEFAULT_MAX, "roles": R.ROLES,
            "magicTypes": R.MAGIC_TYPES, "aspects": R.ASPECTS, "traditions": M.TRADITIONS,
            "mentorSpirits": M.MENTOR_SPIRITS, "lifestyles": K.LIFESTYLES,
            "qualities": K.QUALITIES, "statuses": K.STATUSES,
            "knowledgeExamples": K.KNOWLEDGE_EXAMPLES, "languageExamples": K.LANGUAGE_EXAMPLES,
            "languageLevels": K.LANGUAGE_LEVELS, "karma": K.KARMA,
            "store": {"categories": G.STORE_CATEGORIES, "supply": R.SUPPLY, "categorySupply": G.CATEGORY_SUPPLY,
                      "items": CAT.ITEMS, "grades": G.IMPLANT_GRADES, "firingModes": G.FIRING_MODES,
                      "ammoTypes": G.AMMO_TYPES, "ranges": G.RANGES, "rangeMeters": G.RANGE_METERS,
                      "creationMaxAvail": CAT.CREATION_MAX_AVAIL, "alwaysAvail": CAT.ALWAYS_AVAIL},
            "contactTypes": R.CONTACT_TYPES,
            "packs": PK.PACK_ENTRIES, "packGroups": SWC.PACK_GROUPS,
            "infected": {k: {"karma": v["karma"], "strain": v["strain"], "bases": list(v["bases"]), "any": bool(v.get("any_base_mods")),
                             "optional": v.get("optional", []), "free_optional": v.get("free_optional", ""),
                             "awakened_discount": v.get("awakened_discount", 0), "non_human_extra": v.get("non_human_extra", 0)}
                         for k, v in SWC.INFECTED.items()},
            "infectedPowerCost": SWC.INFECTED_OPTIONAL_POWERS, "contactTypeSupply": G.CONTACT_TYPE_SUPPLY,
            "spells": M.SPELLS, "rituals": M.RITUALS, "powers": M.ADEPT_POWERS, "metamagics": M.METAMAGICS,
            "spirits": list(M.SPIRITS), "complexForms": M.COMPLEX_FORMS, "sprites": M.SPRITES, "echoes": M.ECHOES,
            "programs": M.PROGRAMS, "matrixModes": list(M.MATRIX_INIT), "focusBond": G.FOCUS_BOND_KARMA,
            "edgeSpend": [{"key": k, "cost": v[0], "label": v[1]} for k, v in R.EDGE_SPEND.items()],
            "postBoosts": [{"key": k, "cost": v[0]} for k, v in DICE.POST_BOOSTS.items()],
            "npcTemplates": X.templates(),
            "rules": {"edgeCap": R.EDGE_CAP, "pushCost": DICE.PUSH_COST, "ampUpDrain": M.AMP_UP_DRAIN},
            "wiki": WIKI.build(),
        }
    return CATALOG


@app.route("/api/catalog")
def api_catalog():
    if not session.get("admin") and not session.get("pid"):
        return err("Sign in required.", 401)
    return jsonify(catalog())


# ====================================================================== shared payload builders
def run_to_dict(row):
    tasks = json.loads(row["tasks"])
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("completed"))
    scaled = row["reward"] if not total else int(row["reward"] * done / total)
    return {"id": row["id"], "campaignId": row["campaign_id"], "name": row["name"], "description": row["description"],
            "reward": row["reward"], "status": row["status"], "tasks": tasks, "assignees": json.loads(row["assignees"]),
            "payout": row["payout"], "progress": int(done / total * 100) if total else 0,
            "mandatoryDone": all(t.get("completed") for t in tasks if t.get("mandatory")),
            "scaledPayout": scaled, "createdAt": row["created_at"], "completedAt": row["completed_at"]}


def store_access(c, approved):
    """{item id: [ok, reason, price]} for the store tab."""
    out = {}
    mk = R.price_markup(c)
    for e in CAT.ITEMS:
        o = CAT.offer(e, None, "Standard", mk)
        ok, why = CAT.access(c, o["avail"], o["legal"], e["supply"], approved)
        out[e["id"]] = [ok, why, o["cost"]]
    for e in PK.PACK_ENTRIES:
        ok, why = PK.access(c, e, approved)
        out[e["id"]] = [ok, why, int(round(e["cost"] * (1 + mk[0])))]
    return out


def sheet_payload(row, admin):
    c = load_char(row)
    d = R.derive(c)
    approved = row["approved"] == APPROVED
    allies = [{"id": r["id"], "name": display_name(r), "color": r["color"]} for r in get_db().execute(
        "SELECT * FROM players WHERE campaign_id=? AND id<>? ORDER BY created_at", (row["campaign_id"], row["id"])).fetchall()]
    settings = game_settings(row["campaign_id"])
    return {"player": row_to_player(row, include_state=False), "char": c, "derived": d, "pools": R.pools(c, d),
            "approved": approved, "locked": approved and not admin, "admin": admin,
            "ledger": ledger_rows(pid=row["id"], limit=50), "allies": allies,
            "store": store_access(c, approved), "sellPct": settings["sellPct"],
            "spirits": [R.spirit_stats(s["type"], s["force"]) for s in c.get("spirits") or [] if s.get("type") in M.SPIRITS]}


def char_tx(pid, admin, mutate):
    """Load a character inside a write transaction, let ``mutate(c, ctx, row)`` change it,
    then persist it with ledger entries, log notes and rolls. Returns (row, ctx, message) or raises RuleError."""
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
        if not row:
            abort(404)
        c = load_char(row)
        start = {"karma": c["karma"], "nuyen": c["nuyen"]}
        ctx = R.Ctx(row["approved"] == APPROVED, admin, game_settings(row["campaign_id"])["sellPct"])
        msg = mutate(c, ctx, row)
        R.clamp_state(c)
        save_char(pid, c)
        running = dict(start)
        for kind, delta, reason in ctx.ledger:
            running[kind] += delta
            ledger_add(row["campaign_id"], pid, kind, delta, running[kind], reason, admin)
        who = display_name(row, c)
        for kind, data in ctx.rolls:
            add_roll(row["campaign_id"], pid, who, row["color"], kind, data)
        for note in ctx.log:
            add_roll(row["campaign_id"], pid, who, row["color"], "note", {"text": note})
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return db.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone(), ctx, msg


def do_char_action(pid, admin):
    b = body()
    action = str(b.get("action") or "")
    try:
        row, _ctx, msg = char_tx(pid, admin, lambda c, ctx, row: R.apply_action(c, action, b, ctx))
    except R.RuleError as e:
        return err(str(e))
    out = sheet_payload(row, admin)
    out["message"] = msg
    return jsonify(out)


# ====================================================================== admin: games
def game_or_404(cid):
    row = get_db().execute("SELECT * FROM campaigns WHERE id=?", (cid,)).fetchone()
    if not row:
        abort(404)
    return row


def touch_game(cid):
    get_db().execute("UPDATE campaigns SET updated_at=? WHERE id=?", (now(), cid))


@app.route("/api/overview")
@admin_required
def overview():
    db = get_db()
    games = []
    for c in db.execute("SELECT * FROM campaigns ORDER BY name COLLATE NOCASE").fetchall():
        players = [row_to_player(r, False) for r in db.execute("SELECT * FROM players WHERE campaign_id=? ORDER BY created_at", (c["id"],)).fetchall()]
        games.append({"id": c["id"], "name": c["name"], "createdAt": c["created_at"], "players": players,
                      "waiting": sum(1 for p in players if p["approved"] == SUBMITTED),
                      "activeRuns": db.execute("SELECT COUNT(*) FROM runs WHERE campaign_id=? AND status='Active'", (c["id"],)).fetchone()[0],
                      "openInvites": db.execute("SELECT COUNT(*) FROM invites WHERE campaign_id=? AND used_by IS NULL AND expires_at>?", (c["id"], now())).fetchone()[0]})
    maps = [row_to_map(r, False) for r in db.execute("SELECT * FROM maps ORDER BY updated_at DESC").fetchall()]
    return jsonify({"games": games, "campaigns": [{"id": g["id"], "name": g["name"]} for g in games], "maps": maps})


@app.route("/api/campaigns", methods=["POST"])
@admin_required
def create_campaign():
    cid = new_id()
    t = now()
    get_db().execute("INSERT INTO campaigns (id,name,created_at,updated_at) VALUES (?,?,?,?)",
                     (cid, str(body().get("name") or "New game").strip()[:120], t, t))
    get_db().commit()
    return jsonify({"id": cid}), 201


@app.route("/api/campaigns/<cid>", methods=["PUT"])
@admin_required
def rename_campaign(cid):
    get_db().execute("UPDATE campaigns SET name=?, updated_at=? WHERE id=?",
                     (str(body().get("name") or "Game").strip()[:120], now(), cid))
    get_db().commit()
    return jsonify({"ok": True})


@app.route("/api/campaigns/<cid>", methods=["DELETE"])
@admin_required
def delete_campaign(cid):
    get_db().execute("DELETE FROM campaigns WHERE id=?", (cid,))
    get_db().commit()
    return jsonify({"ok": True})


@app.route("/api/games/<cid>")
@admin_required
def game_detail(cid):
    g = game_or_404(cid)
    db = get_db()
    version = campaign_version(cid)
    if request.args.get("since") == version:
        return jsonify({"unchanged": True, "version": version})
    invites = [{"token": r["token"], "note": r["note"], "createdAt": r["created_at"], "expiresAt": r["expires_at"],
                "usedBy": r["used_by"], "usedAt": r["used_at"]}
               for r in db.execute("SELECT * FROM invites WHERE campaign_id=? ORDER BY created_at DESC", (cid,)).fetchall()]
    return jsonify({
        "game": {"id": g["id"], "name": g["name"], "settings": game_settings(cid)},
        "players": [row_to_player(r, False) for r in db.execute("SELECT * FROM players WHERE campaign_id=? ORDER BY created_at", (cid,)).fetchall()],
        "maps": [row_to_map(r, False) for r in db.execute("SELECT * FROM maps WHERE campaign_id=? ORDER BY name COLLATE NOCASE", (cid,)).fetchall()],
        "invites": invites,
        "runs": [run_to_dict(r) for r in db.execute("SELECT * FROM runs WHERE campaign_id=? ORDER BY CASE status WHEN 'Active' THEN 0 ELSE 1 END, created_at DESC", (cid,)).fetchall()],
        "ledger": ledger_rows(cid=cid, limit=100),
        "rolls": roll_rows(cid, admin=True),
        "version": version, "now": now(),
    })


# ====================================================================== admin: invites & accounts
@app.route("/api/games/<cid>/invites", methods=["POST"])
@admin_required
def create_invite(cid):
    game_or_404(cid)
    days = clamp_int(body().get("days"), 1, 60, INVITE_DAYS)
    token = secrets.token_urlsafe(24)
    t = now()
    get_db().execute("INSERT INTO invites (token,campaign_id,note,created_at,expires_at) VALUES (?,?,?,?,?)",
                     (token, cid, str(body().get("note") or "")[:80], t, t + days * 86400))
    touch_game(cid)
    get_db().commit()
    return jsonify({"token": token, "url": f"{request.host_url.rstrip('/')}/invite/{token}", "expiresAt": t + days * 86400}), 201


@app.route("/api/invites/<token>", methods=["DELETE"])
@admin_required
def revoke_invite(token):
    row = get_db().execute("SELECT campaign_id FROM invites WHERE token=?", (token,)).fetchone()
    get_db().execute("DELETE FROM invites WHERE token=? AND used_by IS NULL", (token,))
    if row:
        touch_game(row["campaign_id"])
    get_db().commit()
    return jsonify({"ok": True})


def invite_row(token):
    row = get_db().execute("SELECT i.*, c.name AS game_name FROM invites i JOIN campaigns c ON c.id=i.campaign_id WHERE token=?", (token,)).fetchone()
    if not row:
        return None, "This invite link is not valid. Ask your GM for a new one."
    if row["used_by"]:
        return None, "This invite link has already been used. Sign in instead, or ask your GM for a new link."
    if row["expires_at"] < now():
        return None, "This invite link has expired. Ask your GM for a new one."
    return row, None


@app.route("/api/invite/<token>", methods=["POST"])
@rate_limited("invite_accept", 10, burst=5)
def accept_invite(token):
    from security import LOGIN_POW_BITS, verify_pow
    b = body()
    if not verify_pow(b.get("challenge"), b.get("counter"), LOGIN_POW_BITS):
        return err("Browser check failed. Reload and try again.")
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        inv, problem = invite_row(token)
        if problem:
            db.rollback()
            return err(problem, 410)
        username = str(b.get("username") or "").strip()
        password = str(b.get("password") or "")
        if not USERNAME_RE.match(username):
            db.rollback()
            return err("Usernames are 3-24 characters: letters, numbers, dot, dash or underscore.")
        if username.lower() in RESERVED:
            db.rollback()
            return err("That username is reserved. Pick another.")
        if len(password) < 8:
            db.rollback()
            return err("Use a password of at least 8 characters.")
        if db.execute("SELECT 1 FROM players WHERE username=?", (username,)).fetchone():
            db.rollback()
            return err("That username is taken. Pick another.", 409)
        cid = inv["campaign_id"]
        count = db.execute("SELECT COUNT(*) FROM players WHERE campaign_id=?", (cid,)).fetchone()[0]
        pid = secrets.token_hex(8)
        t = now()
        c = R.new_character()
        db.execute("INSERT INTO players (id,campaign_id,username,pw_hash,pw_rev,color,radius,current_map_id,state,approved,character,created_at,updated_at,last_seen)"
                   " VALUES (?,?,?,?,0,?,1,NULL,?,0,?,?,?,?)",
                   (pid, cid, username, generate_password_hash(password), PLAYER_COLORS[count % len(PLAYER_COLORS)],
                    json.dumps({"maps": {}}), json.dumps(c), t, t, t))
        db.execute("UPDATE invites SET used_by=?, used_at=? WHERE token=?", (pid, t, token))
        db.commit()
    except BaseException:
        db.rollback()
        raise
    session.clear()
    session.permanent = True
    session["pid"] = pid
    session["pwv"] = 0
    return jsonify({"ok": True, "next": "/play"})


@app.route("/api/players/<pid>/password", methods=["POST"])
@admin_required
def admin_reset_password(pid):
    fetch_player_row(pid)
    pw = "-".join(secrets.token_urlsafe(4) for _ in range(3))
    get_db().execute("UPDATE players SET pw_hash=?, pw_rev=pw_rev+1 WHERE id=?", (generate_password_hash(pw), pid))
    get_db().commit()
    return jsonify({"password": pw})


@app.route("/api/players/<pid>", methods=["DELETE"])
@admin_required
def delete_player(pid):
    row = fetch_player_row(pid)
    get_db().execute("DELETE FROM players WHERE id=?", (pid,))
    touch_game(row["campaign_id"])
    get_db().commit()
    return jsonify({"ok": True})


@app.route("/api/players/<pid>/review", methods=["POST"])
@admin_required
def review_sheet(pid):
    row = fetch_player_row(pid)
    b = body()
    decision = b.get("decision")
    note = str(b.get("note") or "").strip()[:500] or None
    db = get_db()
    if decision == "approve":
        c = load_char(row)
        c["current_edge"] = R.derive(c)["edge_max"]
        for ct in c.get("contacts") or []:
            ct["verified"] = True
        db.execute("UPDATE players SET approved=?, review_note=NULL, character=?, char_rev=char_rev+1, updated_at=? WHERE id=?",
                   (APPROVED, json.dumps(c), now(), pid))
    elif decision in ("return", "reopen"):
        db.execute("UPDATE players SET approved=?, review_note=?, char_rev=char_rev+1, updated_at=? WHERE id=?", (DRAFT, note, now(), pid))
    else:
        return err("Unknown decision.")
    db.commit()
    return jsonify(sheet_payload(fetch_player_row(pid), True))


# ====================================================================== admin: sheets, grants, edge
@app.route("/api/players/<pid>/sheet")
@admin_required
def admin_sheet(pid):
    return jsonify(sheet_payload(fetch_player_row(pid), True))


@app.route("/api/players/<pid>/sheet/action", methods=["POST"])
@admin_required
def admin_sheet_action(pid):
    return do_char_action(pid, True)


def _target_rows(cid, who):
    db = get_db()
    if who == "all":
        return db.execute("SELECT * FROM players WHERE campaign_id=?", (cid,)).fetchall()
    ids = [str(i) for i in (who or [])][:200]
    return [r for i in ids for r in db.execute("SELECT * FROM players WHERE id=? AND campaign_id=?", (i, cid)).fetchall()]


@app.route("/api/games/<cid>/grant", methods=["POST"])
@admin_required
def grant(cid):
    """Give (positive) or take (negative) Karma and/or Nuyen from one, several or all players."""
    game_or_404(cid)
    b = body()
    karma = clamp_int(b.get("karma"), -10000, 10000, 0)
    nuyen = clamp_int(b.get("nuyen"), -100_000_000, 100_000_000, 0)
    reason = str(b.get("reason") or "").strip()[:120] or "GM award"
    if not karma and not nuyen:
        return err("Enter an amount of Karma and/or Nuyen.")
    rows = _target_rows(cid, b.get("players"))
    if not rows:
        return err("Pick at least one player.")
    for row in rows:
        def mutate(c, ctx, _row):
            for kind, amount in (("karma", karma), ("nuyen", nuyen)):
                if amount:
                    new = c[kind] + amount if amount > 0 else max(min(0, c[kind]), c[kind] + amount)
                    if new != c[kind]:
                        ctx.ledger.append((kind, new - c[kind], reason))
                        c[kind] = new
        char_tx(row["id"], True, mutate)
    return jsonify({"ok": True, "count": len(rows)})


@app.route("/api/games/<cid>/edge", methods=["POST"])
@admin_required
def gm_edge(cid):
    """refresh: Edge back to the Edge attribute. gain/lose: +-1 (0..7)."""
    game_or_404(cid)
    b = body()
    action = b.get("action")
    if action not in ("refresh", "gain", "lose"):
        return err("Unknown Edge action.")
    rows = _target_rows(cid, b.get("players"))
    if not rows:
        return err("Pick at least one player.")
    for row in rows:
        def mutate(c, ctx, _row):
            if action == "refresh":
                c["current_edge"] = R.derive(c)["edge_max"]
            elif action == "gain":
                c["current_edge"] = min(R.EDGE_CAP, c["current_edge"] + 1)
            else:
                c["current_edge"] = max(0, c["current_edge"] - 1)
        char_tx(row["id"], True, mutate)
    if action == "refresh":
        add_roll(cid, None, "GM", GM_COLOR, "note", {"text": "refreshed Edge for " + ("everyone" if b.get("players") == "all" else ", ".join(display_name(r) for r in rows)) + "."})
        get_db().commit()
    return jsonify({"ok": True})


@app.route("/api/games/<cid>/settings", methods=["PUT"])
@admin_required
def game_settings_update(cid):
    g = game_or_404(cid)
    b = body()
    cur = json.loads(g["settings"] or "{}") if "settings" in g.keys() else {}
    if "sellPct" in b:
        cur["sellPct"] = clamp_int(b.get("sellPct"), 0, 100, 50)
    get_db().execute("UPDATE campaigns SET settings=?, updated_at=? WHERE id=?", (json.dumps(cur), now(), cid))
    get_db().commit()
    return jsonify({"settings": game_settings(cid)})


@app.route("/api/games/<cid>/lifestyle", methods=["POST"])
@admin_required
def charge_lifestyle(cid):
    """Start of a new month: charge every runner's lifestyle (nuyen may go negative)."""
    game_or_404(cid)
    rows = _target_rows(cid, body().get("players") or "all")
    total = []
    for row in rows:
        def mutate(c, ctx, _row):
            cost = R.derive(c)["lifestyle_cost"]
            if cost:
                c["nuyen"] -= cost
                ctx.ledger.append(("nuyen", -cost, f"{c['lifestyle']} lifestyle, 1 month"))
            return cost
        _r, _ctx, cost = char_tx(row["id"], True, mutate)
        total.append(f"{display_name(row)} {cost:,}¥")
    add_roll(cid, None, "GM", GM_COLOR, "note", {"text": "charged a month of lifestyle: " + (", ".join(total) or "nobody") + "."})
    get_db().commit()
    return jsonify({"ok": True, "count": len(rows)})


# ====================================================================== healing
def _heal(patient_id, healer_row, method, b, admin):
    """Roll a healing test (healer's pool, or natural recovery) and apply it to the patient.
    Returns (error_response, None) or (None, message, roll id)."""
    if method not in R.HEAL_METHODS:
        return err("Unknown healing method."), None
    note = {}
    self_heal = healer_row is None or healer_row["id"] == patient_id
    hc0 = None if healer_row is None else load_char(healer_row)
    push = bool(b.get("push"))
    if hc0 is not None and method in ("first_aid", "medkit", "magic"):
        if method == "medkit":
            if not R.medkits(hc0):
                return err("The healer has no medkit."), None
            if not R.medkit_supplies(hc0) and not admin:
                return err("The medkit is out of supplies. Buy Medkit Supplies in the store."), None
        if push and method == "first_aid" and not R.medkits(hc0):
            return err("First aid without a medkit can't use Edge."), None
    if push and (hc0 is None or hc0["current_edge"] < DICE.PUSH_COST):
        return err(f"Pushing needs {DICE.PUSH_COST} Edge."), None

    def mutate(c, ctx, row):
        dmg = {"natural_stun": R._int(c["stun_damage"]), "natural_physical": R._int(c["physical_damage"])}.get(
            method, R._int(c["stun_damage"]) - R._int(c.get("drain_stun")) + R._int(c["physical_damage"]) - R._int(c.get("drain_phys")))
        if dmg <= 0:
            raise R.RuleError("Nothing to heal" + (" (drain only heals with rest)." if method in ("first_aid", "medkit", "magic") and (c["stun_damage"] or c["physical_damage"]) else "."))
        hc = c if self_heal else hc0
        hd = R.derive(hc)
        sp = None
        if method.startswith("natural"):
            parts = R.natural_pool(c, method, bool(b.get("assisted")))
        elif method == "magic":
            sp = next((s for s in hc.get("spells") or [] if s.get("name") in R.HEAL_SPELLS), None)
            if not sp and not admin:
                raise R.RuleError("The healer doesn't know a Heal spell.")
            prof = R.spell_profile(hc, hd, sp or {"name": "Heal", "drain": 3}) if hc.get("magic_type") in R.CASTERS else None
            if not prof:
                raise R.RuleError("The healer can't cast spells.")
            parts = list(prof["parts"])
        else:
            if method == "medkit" and not R.medkits(hc):
                raise R.RuleError("The healer has no medkit.")
            parts = [list(x) for x in R.pool_by_key(hc, method, hd)["parts"]]
        if b.get("wound", True) and hd["wound_modifier"] and not method.startswith("natural"):
            parts.append(["Wound modifier", hd["wound_modifier"]])
        mod = clamp_int(b.get("mod"), -30, 30, 0)
        if mod:
            parts.append(["Modifier", mod])
        pe = 0
        if push:
            pe = hd["edge_max"]
            parts.append(["Edge (pushed, exploding 6s)", pe])
            if self_heal:
                R.spend_edge(c, DICE.PUSH_COST)
        pool = max(1, sum(x[1] for x in parts) - pe)
        r = DICE.new_roll(pool, push_edge=pe)
        d = R.derive(c)
        if method in ("first_aid", "medkit") and d["essence"] >= 6:
            r["bought"] = r.get("bought", 0) + 1
            parts.append(["Full Essence (+1 hit)", 0])
        label = {"first_aid": "First aid", "medkit": "Medkit", "magic": "Heal spell", "natural_stun": "Rest (Stun)",
                 "natural_physical": "Rest (Physical)"}[method]
        r["label"] = f"{label} on {display_name(row, c)}" if not self_heal else f"{label} (self)" if not method.startswith("natural") else label
        r["parts"] = parts
        r["heal"] = method
        if method in ("first_aid", "medkit", "magic"):
            r["threshold"] = R.heal_threshold(d)
        DICE.evaluate(r)
        text = R.apply_heal(c, method, r["hits"], ctx)
        r["note"] = text
        actor = healer_row if healer_row is not None else row
        note["rid"] = add_roll(row["campaign_id"], actor["id"] if healer_row is not None else row["id"],
                               display_name(actor, hc if healer_row is not None else c) if healer_row is not None else "GM",
                               actor["color"], "sr", r)
        if method == "magic" and self_heal and healer_row is not None:
            R.after_cast(c, sp or {"name": "Heal", "drain": 3}, ctx)
        if method == "medkit" and self_heal and healer_row is not None:
            _use_supplies(c)
        return text
    try:
        _row, _ctx, msg = char_tx(patient_id, admin, mutate)
        if healer_row is not None and not self_heal:
            def after(c, ctx, row):
                if push:
                    R.spend_edge(c, DICE.PUSH_COST)
                if method == "medkit":
                    _use_supplies(c)
                if method == "magic":
                    sp = next((s for s in c.get("spells") or [] if s.get("name") in R.HEAL_SPELLS), None)
                    R.after_cast(c, sp or {"name": "Heal", "drain": 3}, ctx)
            char_tx(healer_row["id"], True, after)
    except R.RuleError as e:
        return err(str(e)), None
    return None, msg, note.get("rid")


def _use_supplies(c):
    sup = next((it for it in c["inventory"] if it.get("ref") == "medical-medkit-supplies"), None)
    if sup:
        sup["qty"] = R._int(sup.get("qty"), 1) - 1
        if sup["qty"] <= 0:
            c["inventory"].remove(sup)


@app.route("/api/me/heal", methods=["POST"])
@player_required
@rate_limited("player_heal", 30)
def me_heal(me):
    """Heal yourself or an ally (first aid, medkit, Heal spell) or rest (natural recovery, yourself only)."""
    b = body()
    method = str(b.get("method") or "")
    target = str(b.get("target") or me["id"])
    trow = get_db().execute("SELECT * FROM players WHERE id=? AND campaign_id=?", (target, me["campaign_id"])).fetchone()
    if not trow:
        return err("Pick a runner in your game.")
    if method.startswith("natural") and target != me["id"]:
        return err("Only the patient can rest.")
    res = _heal(target, me, method, b, False)
    if res[0] is not None:
        return res[0]
    return jsonify({"message": res[1], "rollId": res[2], "rolls": roll_rows(me["campaign_id"]),
                    "sheet": sheet_payload(fetch_player_row(me["id"]), False), "me": row_to_player(fetch_player_row(me["id"]), False)})


@app.route("/api/players/<pid>/heal", methods=["POST"])
@admin_required
def gm_heal(pid):
    b = body()
    row = fetch_player_row(pid)
    healer = None
    if b.get("healer"):
        healer = get_db().execute("SELECT * FROM players WHERE id=? AND campaign_id=?", (str(b["healer"]), row["campaign_id"])).fetchone()
    res = _heal(pid, healer, str(b.get("method") or ""), b, True)
    if res[0] is not None:
        return res[0]
    out = sheet_payload(fetch_player_row(pid), True)
    out["message"] = res[1]
    return jsonify(out)


# ====================================================================== runs (contracts)
def clean_tasks(raw):
    out = []
    for t in (raw or [])[:60]:
        if not isinstance(t, dict):
            continue
        desc = str(t.get("description") or "").strip()[:200]
        if desc:
            out.append({"description": desc, "mandatory": bool(t.get("mandatory")), "completed": bool(t.get("completed"))})
    return out


def run_row(rid):
    row = get_db().execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
    if not row:
        abort(404)
    return row


def clean_assignees(cid, raw):
    ids = {r["id"] for r in get_db().execute("SELECT id FROM players WHERE campaign_id=?", (cid,)).fetchall()}
    return [str(i) for i in (raw or []) if str(i) in ids]


@app.route("/api/games/<cid>/runs", methods=["POST"])
@admin_required
def create_run(cid):
    game_or_404(cid)
    b = body()
    name = str(b.get("name") or "").strip()[:120]
    if not name:
        return err("Give the run a name.")
    rid = new_id()
    t = now()
    get_db().execute("INSERT INTO runs (id,campaign_id,name,description,reward,status,tasks,assignees,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (rid, cid, name, str(b.get("description") or "")[:5000], clamp_int(b.get("reward"), 0, 100_000_000, 0), "Active",
                      json.dumps(clean_tasks(b.get("tasks"))), json.dumps(clean_assignees(cid, b.get("assignees"))), t, t))
    get_db().commit()
    return jsonify(run_to_dict(run_row(rid))), 201


@app.route("/api/runs/<rid>", methods=["PUT"])
@admin_required
def update_run(rid):
    row = run_row(rid)
    b = body()
    if row["status"] != "Active" and set(b) - {"description"}:
        return err("Only active runs can be changed.")
    name = str(b.get("name", row["name"]) or "").strip()[:120] or row["name"]
    desc = str(b.get("description", row["description"]))[:5000]
    reward = clamp_int(b.get("reward", row["reward"]), 0, 100_000_000, row["reward"])
    tasks = clean_tasks(b["tasks"]) if "tasks" in b else json.loads(row["tasks"])
    assignees = clean_assignees(row["campaign_id"], b["assignees"]) if "assignees" in b else json.loads(row["assignees"])
    get_db().execute("UPDATE runs SET name=?, description=?, reward=?, tasks=?, assignees=?, updated_at=? WHERE id=?",
                     (name, desc, reward, json.dumps(tasks), json.dumps(assignees), now(), rid))
    get_db().commit()
    return jsonify(run_to_dict(run_row(rid)))


@app.route("/api/runs/<rid>/complete", methods=["POST"])
@admin_required
def complete_run(rid):
    row = run_row(rid)
    run = run_to_dict(row)
    if run["status"] != "Active":
        return err("This run is not active.")
    if not run["mandatoryDone"]:
        return err("Tick every mandatory task (marked *) before completing the run.")
    payout = clamp_int(body().get("payout", run["scaledPayout"]), 0, 100_000_000, run["scaledPayout"])
    # claim the run first so a double click (or two GM tabs) can never pay twice
    t = now()
    db = get_db()
    cur = db.execute("UPDATE runs SET status='Completed', payout=?, completed_at=?, updated_at=? WHERE id=? AND status='Active'", (payout, t, t, rid))
    db.commit()
    if cur.rowcount != 1:
        return err("This run was already closed.")
    paid = []
    for pid in run["assignees"]:
        prow = get_db().execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
        if not prow:
            continue

        def mutate(c, ctx, _row):
            if payout:
                c["nuyen"] += payout
                ctx.ledger.append(("nuyen", payout, f"Run reward: {run['name']}"))
        char_tx(pid, True, mutate)
        paid.append(display_name(prow))
    add_roll(row["campaign_id"], None, "GM", GM_COLOR, "note",
             {"text": f"closed the contract “{run['name']}”." + (f" {', '.join(paid)} got {payout:,}¥ each." if paid and payout else "")})
    db.commit()
    return jsonify(run_to_dict(run_row(rid)))


@app.route("/api/runs/<rid>/abandon", methods=["POST"])
@admin_required
def abandon_run(rid):
    row = run_row(rid)
    if row["status"] != "Active":
        return err("This run is not active.")
    get_db().execute("UPDATE runs SET status='Abandoned', updated_at=? WHERE id=?", (now(), rid))
    get_db().commit()
    return jsonify(run_to_dict(run_row(rid)))


@app.route("/api/runs/<rid>/reopen", methods=["POST"])
@admin_required
def reopen_run(rid):
    row = run_row(rid)
    if row["status"] != "Abandoned":
        return err("Only abandoned runs can be reopened (completed runs have already paid out).")
    get_db().execute("UPDATE runs SET status='Active', updated_at=? WHERE id=?", (now(), rid))
    get_db().commit()
    return jsonify(run_to_dict(run_row(rid)))


@app.route("/api/runs/<rid>", methods=["DELETE"])
@admin_required
def delete_run(rid):
    row = run_row(rid)
    get_db().execute("DELETE FROM runs WHERE id=?", (rid,))
    touch_game(row["campaign_id"])
    get_db().commit()
    return jsonify({"ok": True})


# ====================================================================== GM dice
@app.route("/api/games/<cid>/roll", methods=["POST"])
@admin_required
@rate_limited("gm_roll", 90)
def gm_roll(cid):
    game_or_404(cid)
    b = body()
    label = str(b.get("label") or "").strip()[:80]
    hidden = bool(b.get("hidden"))
    try:
        if b.get("kind") == "initiative":
            score = clamp_int(b.get("score"), 0, 60, 0)
            res = DICE.initiative(score, clamp_int(b.get("dice"), 1, 5, 1))
            res["label"] = label or "Initiative"
            add_roll(cid, None, "GM", GM_COLOR, "init", res, hidden)
        else:
            pool = clamp_int(b.get("dice"), 0, DICE.MAX_POOL, 0)
            res = DICE.new_roll(pool, wild=bool(b.get("wild")), threshold=clamp_int(b.get("threshold"), 0, 30, 0))
            res["label"] = label or f"{pool} dice"
            res["parts"] = [["Dice", pool]]
            add_roll(cid, None, "GM", GM_COLOR, "sr", res, hidden)
    except DICE.DiceError as e:
        return err(str(e))
    get_db().commit()
    return jsonify({"rolls": roll_rows(cid, admin=True)})


@app.route("/api/games/<cid>/rolls")
@admin_required
def gm_rolls(cid):
    return jsonify({"rolls": roll_rows(cid, admin=True)})


# ====================================================================== player: state, sheet, rolls, edge, runs
def my_runs(me):
    rows = get_db().execute("SELECT * FROM runs WHERE campaign_id=? ORDER BY CASE status WHEN 'Active' THEN 0 ELSE 1 END, created_at DESC",
                            (me["campaign_id"],)).fetchall()
    return [run_to_dict(r) for r in rows if me["id"] in json.loads(r["assignees"])]


@app.route("/api/me/state")
@player_required
@rate_limited("player_state", 150)
def me_state(me):
    version = campaign_version(me["campaign_id"], me["current_map_id"])
    if request.args.get("since") == version:
        return jsonify({"unchanged": True, "version": version})
    g = game_or_404(me["campaign_id"])
    runs = my_runs(me)
    return jsonify({
        "version": version, "game": {"id": g["id"], "name": g["name"]},
        "me": row_to_player(me, include_state=False),
        "view": player_view(me), "rolls": roll_rows(me["campaign_id"]),
        "activeRuns": sum(1 for r in runs if r["status"] == "Active"), "runsSig": [[r["id"], r["status"], r["progress"]] for r in runs],
        "sheetRev": me["char_rev"],
    })


@app.route("/api/me/sheet")
@player_required
def me_sheet(me):
    return jsonify(sheet_payload(me, False))


@app.route("/api/me/sheet/action", methods=["POST"])
@player_required
@rate_limited("sheet_action", 240)
def me_sheet_action(me):
    if body().get("action") == "admin_set":
        return err("Only the GM can do that.", 403)
    return do_char_action(me["id"], False)


@app.route("/api/me/submit", methods=["POST"])
@player_required
def me_submit(me):
    want = bool(body().get("submit", True))
    if me["approved"] == APPROVED:
        return err("Your sheet is already approved.")
    get_db().execute("UPDATE players SET approved=?, updated_at=? WHERE id=?", (SUBMITTED if want else DRAFT, now(), me["id"]))
    get_db().commit()
    return jsonify(sheet_payload(fetch_player_row(me["id"]), False))


@app.route("/api/me/runs")
@player_required
def me_runs(me):
    return jsonify({"runs": my_runs(me)})


@app.route("/api/me/password", methods=["POST"])
@player_required
@rate_limited("password_change", 10)
def me_password(me):
    b = body()
    if not check_password_hash(me["pw_hash"], str(b.get("current") or "")):
        return err("Your current password is wrong.")
    new = str(b.get("new") or "")
    if len(new) < 8:
        return err("Use a password of at least 8 characters.")
    get_db().execute("UPDATE players SET pw_hash=?, pw_rev=pw_rev+1 WHERE id=?", (generate_password_hash(new), me["id"]))
    get_db().commit()
    session["pwv"] = me["pw_rev"] + 1
    return jsonify({"ok": True})


def _who(row, c):
    return display_name(row, c)


@app.route("/api/me/roll", methods=["POST"])
@player_required
@rate_limited("player_roll", 60)
def me_roll(me):
    b = body()
    out = {}

    def mutate(c, ctx, row):
        d = R.derive(c)
        key = str(b.get("key") or "")
        extra = []
        follow = None
        if key:
            pool = R.pool_by_key(c, key, d)
            parts = [list(p) for p in pool["parts"]]
            label = pool["label"]
            if key.startswith("weapon:") and key != "weapon:unarmed":
                it = R.find_item(c, key[7:])
                prof = R.weapon_profile(c, d, it, b.get("mode"), b.get("range"))
                note = R.consume_attack(c, it["uid"], prof["mode"])
                label = it["name"] + (f" ({G.FIRING_MODES[prof['mode']]['name']})" if prof["mode"] else "")
                if b.get("range") in G.RANGES and prof["ar_at"] is not None:
                    extra.append(f"AR {prof['ar_at']} at {b['range']}")
                extra.append(f"DV {prof['dv']}{prof['type']}" + (f" {prof['element']}" if prof["element"] else ""))
                if prof.get("grenade"):
                    extra.append(f"blast {prof.get('blast')}: {' / '.join(prof['grenade'])}")
                if note:
                    extra.append(note)
            elif key.startswith("natural:"):
                extra.append(f"DV {pool.get('dv')}")
                if b.get("range") in G.RANGES:
                    i = G.RANGES.index(b["range"])
                    ar = (pool.get("ar") or [None] * 5)[i]
                    extra.append(f"AR {ar} at {b['range']}" if ar is not None else f"can't reach {b['range']}")
            elif key.startswith("spell:"):
                sp = c["spells"][R._list_index(c["spells"], key[6:])]
                follow = ("spell", sp)
            elif key.startswith("form:"):
                f = c["complex_forms"][R._list_index(c["complex_forms"], key[5:])]
                follow = ("form", f)
        else:
            n = clamp_int(b.get("dice"), 0, DICE.MAX_POOL, 0)
            parts = [["Dice", n]]
            label = "Free roll"
        if b.get("label"):
            label = str(b["label"]).strip()[:80] or label
        if b.get("wound", True) and d["wound_modifier"]:
            parts.append(["Wound modifier", d["wound_modifier"]])
        mod = clamp_int(b.get("mod"), -30, 30, 0)
        if mod:
            parts.append(["Modifier", mod])
        pool_n = max(0, sum(p[1] for p in parts))
        push = 0
        if b.get("push"):
            R.spend_edge(c, DICE.PUSH_COST)
            push = d["edge_max"]
            parts.append(["Edge (pushed, exploding 6s)", push])
        try:
            res = DICE.new_roll(pool_n, wild=bool(b.get("wild")), push_edge=push, threshold=clamp_int(b.get("threshold"), 0, 30, 0))
        except DICE.DiceError as e:
            raise R.RuleError(str(e))
        res["label"] = label
        res["parts"] = parts
        if extra:
            res["note"] = " · ".join(extra)
        out["rid"] = add_roll(row["campaign_id"], row["id"], display_name(row, c), row["color"], "sr", res)
        if follow and follow[0] == "spell":
            R.after_cast(c, follow[1], ctx, clamp_int(b.get("drain"), 0, 20, 0))
        elif follow:
            R.after_form(c, follow[1], ctx)
        return "Rolled."
    try:
        char_tx(me["id"], False, mutate)
    except R.RuleError as e:
        return err(str(e))
    res = {"rollId": out["rid"], "rolls": roll_rows(me["campaign_id"]), "me": row_to_player(fetch_player_row(me["id"]), False)}
    if str(b.get("key") or "").startswith(("weapon:", "spell:", "form:")):
        res["sheet"] = sheet_payload(fetch_player_row(me["id"]), False)   # ammo, drain or fading changed
    return jsonify(res)


@app.route("/api/me/rolls/<rid>/boost", methods=["POST"])
@player_required
@rate_limited("player_boost", 30)
def me_boost(me, rid):
    b = body()
    db = get_db()
    roll = db.execute("SELECT * FROM rolls WHERE id=? AND player_id=? AND kind='sr'", (rid, me["id"])).fetchone()
    if not roll:
        return err("That roll isn't yours.", 404)
    if now() - roll["created_at"] > BOOST_WINDOW:
        return err("Too late to boost that roll.")

    def mutate(c, ctx, row):
        fresh = db.execute("SELECT data FROM rolls WHERE id=?", (rid,)).fetchone()   # inside the write lock
        if not fresh:
            raise R.RuleError("That roll is gone.")
        r = json.loads(fresh["data"])
        if r.get("heal"):
            raise R.RuleError("Healing is applied as soon as you roll; push before rolling instead.")
        try:
            cost = DICE.apply_boost(r, str(b.get("boost") or ""), b.get("dice") or [])
        except DICE.DiceError as e:
            raise R.RuleError(str(e))
        R.spend_edge(c, cost)
        db.execute("UPDATE rolls SET data=?, updated_at=? WHERE id=?", (json.dumps(r), now(), rid))
        return "Boosted."
    try:
        char_tx(me["id"], False, mutate)
    except R.RuleError as e:
        return err(str(e))
    return jsonify({"rolls": roll_rows(me["campaign_id"]), "me": row_to_player(fetch_player_row(me["id"]), False)})


@app.route("/api/me/initiative", methods=["POST"])
@player_required
@rate_limited("player_roll", 60)
def me_initiative(me):
    plus3 = bool(body().get("boost"))

    def mutate(c, ctx, row):
        d = R.derive(c)
        if plus3:
            R.spend_edge(c, 1)
        kind = str(body().get("kind") or "")
        score, dice = d["initiative_score"], d["initiative_dice"]
        label = "Initiative"
        if kind == "matrix" and d["matrix"].get("device"):
            score, dice, label = d["matrix"]["init_score"], d["matrix"]["init_dice"], f"Matrix initiative ({d['matrix']['mode']})"
        elif kind == "astral" and d["astral_initiative"]:
            score, dice, label = d["astral_initiative"]["score"], d["astral_initiative"]["dice"], "Astral initiative"
        res = DICE.initiative(score, dice, plus3)
        res["label"] = label + (" (+3 for 1 Edge)" if plus3 else "")
        res["actions"] = {"major": 1, "minor": min(R.MAX_MINOR, 1 + dice)}
        add_roll(row["campaign_id"], row["id"], _who(row, c), row["color"], "init", res)
        import fight
        fight.tracker_set_player(row["campaign_id"], row["id"], res["total"], d)
        return "Rolled."
    try:
        char_tx(me["id"], False, mutate)
    except R.RuleError as e:
        return err(str(e))
    return jsonify({"rolls": roll_rows(me["campaign_id"]), "me": row_to_player(fetch_player_row(me["id"]), False)})


@app.route("/api/me/edge", methods=["POST"])
@player_required
@rate_limited("player_edge", 30)
def me_edge(me):
    b = body()
    key = str(b.get("key") or "")
    if key not in R.EDGE_SPEND:
        return err("Unknown Edge Boost.")
    cost, label, effect = R.EDGE_SPEND[key]
    target = None
    if effect == "give":
        target = get_db().execute("SELECT * FROM players WHERE id=? AND campaign_id=? AND id<>?",
                                  (str(b.get("to") or ""), me["campaign_id"], me["id"])).fetchone()
        if not target:
            return err("Pick the ally who gets the Edge.")
        if load_char(target)["current_edge"] >= R.EDGE_CAP:
            return err(f"{display_name(target)} already has the maximum of {R.EDGE_CAP} Edge.")

    def mutate(c, ctx, row):
        R.spend_edge(c, cost)
        if effect == "heal_stun":
            c["stun_damage"] = max(0, c["stun_damage"] - 1)
        elif effect == "heal_physical":
            c["physical_damage"] = max(0, c["physical_damage"] - 1)
        text = f"spent {cost} Edge: {label}" + (f" ({display_name(target)})" if target else "") + "."
        ctx.log.append(text)
        return label + "."
    try:
        _row, _ctx, msg = char_tx(me["id"], False, mutate)
        if target:
            def give(c, ctx, row):
                c["current_edge"] = min(R.EDGE_CAP, c["current_edge"] + 1)
            char_tx(target["id"], True, give)
    except R.RuleError as e:
        return err(str(e))
    return jsonify({"message": msg, "rolls": roll_rows(me["campaign_id"]), "me": row_to_player(fetch_player_row(me["id"]), False)})

"""Session log: the GM starts a session at the table and ends it afterwards. Everything that happened in
between becomes a readable recap: fights and attacks, notable rolls (successes, glitches), Karma and
nuyen awards, runs completed and handouts shown, plus the GM's own notes. The recap is frozen when the
session ends, can be shared with the players, and exported as a Markdown file."""
import json
import time

from flask import Response, jsonify

from core import (GM_COLOR, add_roll, app, body, err, get_db, new_id, now, player_required)
from security import gamemaster_required

TITLE_MAX, NOTES_MAX = 120, 30000


def _fmt_money(n):
    return f"{int(n):,}¥"


def build_recap(cid, start, end, for_player=False):
    """Events and highlights between two times. Players never see hidden rolls or private purchases."""
    db = get_db()
    ev = []
    hidden_sql = " AND hidden=0" if for_player else ""
    for r in db.execute(f"SELECT * FROM rolls WHERE campaign_id=? AND created_at>=? AND created_at<=?{hidden_sql} ORDER BY created_at",
                        (cid, start, end)).fetchall():
        d = json.loads(r["data"])
        item = {"at": r["created_at"], "who": r["who"], "color": r["color"], "hidden": bool(r["hidden"])}
        if r["kind"] == "note":
            item.update(kind="note", text=d.get("text", ""))
        elif r["kind"] == "attack":
            if d.get("hit"):
                txt = f"{d.get('attacker')} hits {d.get('target')} with {d.get('weapon')}: " + (
                    f"{d.get('damage')} {'Stun' if d.get('type') == 'S' else 'Physical'}" if d.get("damage") else "no damage after soak")
            else:
                txt = f"{d.get('attacker')} misses {d.get('target')} ({d.get('weapon')})"
            if d.get("targets"):
                txt = d.get("summary") or txt
            item.update(kind="attack", text=txt, damage=d.get("damage") or 0, attacker=d.get("attacker"), target=d.get("target"))
        elif r["kind"] == "init":
            item.update(kind="init", text=f"{r['who']} rolls initiative {d.get('total')}")
        else:
            label = d.get("label") or "Roll"
            flag = "critical" if d.get("critical") else "glitch" if d.get("glitch") else ""
            res = f"{d.get('hits', 0)} hit{'s' if d.get('hits') != 1 else ''}"
            if d.get("threshold"):
                res += " · success" if d.get("success") else " · failure"
            item.update(kind="roll", text=f"{r['who']}: {label}, {res}" + (f" ({'critical glitch' if flag == 'critical' else 'glitch'})" if flag else ""),
                        hits=d.get("hits", 0), flag=flag, label=label)
        ev.append(item)
    by_gm = " AND l.by_gm=1" if for_player else ""
    for r in db.execute(f"SELECT l.*, p.username, p.character FROM ledger l JOIN players p ON p.id=l.player_id "
                        f"WHERE l.campaign_id=? AND l.created_at>=? AND l.created_at<=?{by_gm} ORDER BY l.created_at", (cid, start, end)).fetchall():
        try:
            name = (json.loads(r["character"]).get("name") or "").strip() or r["username"]
        except ValueError:
            name = r["username"]
        amount = f"{r['delta']:+d} Karma" if r["kind"] == "karma" else f"{'+' if r['delta'] >= 0 else '−'}{_fmt_money(abs(r['delta']))}"
        ev.append({"at": r["created_at"], "kind": "ledger", "who": name, "text": f"{name}: {amount} ({r['reason']})",
                   "resource": r["kind"], "delta": r["delta"], "gm": bool(r["by_gm"])})
    for r in db.execute("SELECT * FROM runs WHERE campaign_id=? AND ((created_at>=? AND created_at<=?) OR (completed_at>=? AND completed_at<=?))",
                        (cid, start, end, start, end)).fetchall():
        if start <= r["created_at"] <= end:
            ev.append({"at": r["created_at"], "kind": "run", "text": f"New run: {r['name']}"})
        if r["completed_at"] and start <= r["completed_at"] <= end:
            word = "completed" if r["status"] == "Completed" else r["status"].lower()
            pay = f", paid {_fmt_money(r['payout'])} each" if r["status"] == "Completed" and r["payout"] else ""
            ev.append({"at": r["completed_at"], "kind": "run", "text": f"Run {word}: {r['name']}{pay}"})
    for r in db.execute("SELECT * FROM handouts WHERE campaign_id=? AND shown=1 AND shown_at>=? AND shown_at<=?", (cid, start, end)).fetchall():
        ev.append({"at": r["shown_at"], "kind": "handout", "text": f"Handout: {r['title']}"})
    ev.sort(key=lambda e: e["at"])

    rolls = [e for e in ev if e["kind"] == "roll"]
    attacks = [e for e in ev if e["kind"] == "attack"]
    dealt = {}
    for a in attacks:
        if a.get("damage"):
            dealt[a["attacker"]] = dealt.get(a["attacker"], 0) + a["damage"]
    best = max(rolls, key=lambda e: e.get("hits", 0), default=None)
    stats = {
        "minutes": int(max(0, end - start) // 60), "rolls": len(rolls), "attacks": len(attacks),
        "hits": sum(1 for a in attacks if a.get("damage")),
        "glitches": sum(1 for e in rolls if e.get("flag") == "glitch"), "critical": sum(1 for e in rolls if e.get("flag") == "critical"),
        "karma": sum(e["delta"] for e in ev if e["kind"] == "ledger" and e["resource"] == "karma" and e["gm"] and e["delta"] > 0),
        "nuyen": sum(e["delta"] for e in ev if e["kind"] == "ledger" and e["resource"] == "nuyen" and e["gm"] and e["delta"] > 0),
        "fights": sum(1 for e in ev if e["kind"] == "note" and "started a combat" in e["text"]),
        "best": {"text": best["text"], "hits": best["hits"]} if best and best.get("hits") else None,
        "damage": sorted(([k, v] for k, v in dealt.items()), key=lambda x: -x[1])[:6],
    }
    return {"events": ev[-1500:], "stats": stats}


def _row(r, recap=None):
    return {"id": r["id"], "title": r["title"], "notes": r["notes"], "startedAt": r["started_at"], "endedAt": r["ended_at"],
            "shared": bool(r["shared"]), "active": r["ended_at"] is None, "recap": recap}


def game_sessions(cid):
    out = []
    for r in get_db().execute("SELECT * FROM sessions WHERE campaign_id=? ORDER BY started_at DESC", (cid,)).fetchall():
        if r["ended_at"] is None:
            recap = build_recap(cid, r["started_at"], now())
        else:
            recap = json.loads(r["recap"] or "null")
        out.append(_row(r, recap))
    return out


def player_sessions(me):
    out = []
    for r in get_db().execute("SELECT * FROM sessions WHERE campaign_id=? AND shared=1 AND ended_at IS NOT NULL ORDER BY started_at DESC",
                              (me["campaign_id"],)).fetchall():
        out.append(_row(r, build_recap(me["campaign_id"], r["started_at"], r["ended_at"], for_player=True)))
    return out


def _get(sid):
    return get_db().execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()


@app.route("/api/games/<cid>/sessions")
@gamemaster_required
def sessions_list(cid):
    return jsonify({"sessions": game_sessions(cid)})


@app.route("/api/games/<cid>/sessions", methods=["POST"])
@gamemaster_required
def sessions_start(cid):
    db = get_db()
    if not db.execute("SELECT 1 FROM campaigns WHERE id=?", (cid,)).fetchone():
        return err("Game not found.", 404)
    if db.execute("SELECT 1 FROM sessions WHERE campaign_id=? AND ended_at IS NULL", (cid,)).fetchone():
        return err("A session is already running. End it first.")
    n = db.execute("SELECT COUNT(*) FROM sessions WHERE campaign_id=?", (cid,)).fetchone()[0] + 1
    title = str(body().get("title") or "").strip()[:TITLE_MAX] or f"Session {n} · {time.strftime('%Y-%m-%d')}"
    sid, t = new_id(), now()
    db.execute("INSERT INTO sessions (id,campaign_id,title,started_at,updated_at) VALUES (?,?,?,?,?)", (sid, cid, title, t - 1, t))
    add_roll(cid, None, "GM", GM_COLOR, "note", {"text": f"started the session “{title}”."})
    db.commit()
    return jsonify({"id": sid, "sessions": game_sessions(cid)}), 201


@app.route("/api/sessions/<sid>", methods=["PUT"])
@gamemaster_required
def sessions_update(sid):
    r = _get(sid)
    if not r:
        return err("Session not found.", 404)
    b = body()
    title = str(b.get("title", r["title"]) or "").strip()[:TITLE_MAX] or r["title"]
    notes = str(b.get("notes", r["notes"]) or "")[:NOTES_MAX]
    shared = bool(b.get("shared", r["shared"]))
    get_db().execute("UPDATE sessions SET title=?, notes=?, shared=?, updated_at=? WHERE id=?", (title, notes, int(shared), now(), sid))
    get_db().commit()
    return jsonify({"sessions": game_sessions(r["campaign_id"])})


@app.route("/api/sessions/<sid>/end", methods=["POST"])
@gamemaster_required
def sessions_end(sid):
    r = _get(sid)
    if not r:
        return err("Session not found.", 404)
    if r["ended_at"] is not None:
        return err("That session has already ended.")
    db = get_db()
    add_roll(r["campaign_id"], None, "GM", GM_COLOR, "note", {"text": f"ended the session “{r['title']}”."})
    t = now()
    recap = build_recap(r["campaign_id"], r["started_at"], t)
    db.execute("UPDATE sessions SET ended_at=?, recap=?, updated_at=? WHERE id=?", (t, json.dumps(recap), t, sid))
    db.commit()
    return jsonify({"sessions": game_sessions(r["campaign_id"])})


@app.route("/api/sessions/<sid>", methods=["DELETE"])
@gamemaster_required
def sessions_delete(sid):
    r = _get(sid)
    if not r:
        return err("Session not found.", 404)
    get_db().execute("DELETE FROM sessions WHERE id=?", (sid,))
    get_db().execute("UPDATE campaigns SET updated_at=? WHERE id=?", (now(), r["campaign_id"]))
    get_db().commit()
    return jsonify({"sessions": game_sessions(r["campaign_id"])})


def recap_markdown(s):
    rc = s["recap"] or {"events": [], "stats": {}}
    st = rc.get("stats") or {}
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["startedAt"]))
    out = [f"# {s['title']}", "", f"*{when}, {st.get('minutes', 0)} minutes*", ""]
    if s["notes"].strip():
        out += ["## Notes", "", s["notes"].strip(), ""]
    out += ["## Highlights", "",
            f"- {st.get('fights', 0)} fight(s), {st.get('attacks', 0)} attacks, {st.get('hits', 0)} landed",
            f"- {st.get('rolls', 0)} rolls, {st.get('glitches', 0)} glitches, {st.get('critical', 0)} critical glitches",
            f"- Awarded: {st.get('karma', 0)} Karma, {_fmt_money(st.get('nuyen', 0))}"]
    if st.get("best"):
        out.append(f"- Best roll: {st['best']['text']}")
    for name, dmg in st.get("damage") or []:
        out.append(f"- {name} dealt {dmg} boxes of damage")
    out += ["", "## Timeline", ""]
    for e in rc.get("events") or []:
        if e["kind"] == "init":
            continue
        t = time.strftime("%H:%M", time.localtime(e["at"]))
        text = e["text"] if e["kind"] != "note" else f"{e.get('who', '')} {e['text']}"
        out.append(f"- {t} {'(hidden) ' if e.get('hidden') else ''}{text}")
    return "\n".join(out) + "\n"


@app.route("/api/sessions/<sid>/export")
@gamemaster_required
def sessions_export(sid):
    r = _get(sid)
    if not r:
        return err("Session not found.", 404)
    s = next(x for x in game_sessions(r["campaign_id"]) if x["id"] == sid)
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in s["title"]).strip() or "session"
    return Response(recap_markdown(s), mimetype="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.md"'})


@app.route("/api/me/sessions")
@player_required
def me_sessions(me):
    return jsonify({"sessions": player_sessions(me)})

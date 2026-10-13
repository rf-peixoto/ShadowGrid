"""ShadowGrid - Shadowrun Sixth World character sheets and fog-of-war maps for one table.

Install:                      ./install.sh
Play on your home network:    ./local.sh     (same as python app.py, reachable from the LAN)
Serve on the internet:        ./serve.sh
Set the gamemaster password:  python app.py set-password
"""
import getpass
import os
import re
import sqlite3
import sys
import time

from flask import Response, jsonify, make_response, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import backup  # noqa: F401  (registers routes)
import fight  # noqa: F401  (registers routes)
import game  # noqa: F401  (registers routes)
import handouts  # noqa: F401  (registers routes)
import sessions  # noqa: F401  (registers routes)
import maps  # noqa: F401  (registers routes)
import music  # noqa: F401  (registers routes)
from core import (BUS, DB_PATH, MAX_STREAMS, app, body, current_player_row, err, get_db, init_db, kv_get, kv_set, run_server)
from game import catalog_blob
from security import (GATE_ON, LOGIN_POW_BITS, gamemaster_required, gate_consume, gate_fail, gate_ok, gate_refused,
                      grant_gate_pass, issue_challenge, issue_gate_challenge, rate_limited, verify_gate, verify_pow)

NEXT_RE = re.compile(r"/(?![/\\])[A-Za-z0-9_\-./#?=&%]*")


def safe_next(v, default="/login"):
    return v if isinstance(v, str) and len(v) < 300 and NEXT_RE.fullmatch(v) else default


# ====================================================================== the gate (before the sign-in pages)
@app.route("/gate")
def gate():
    nxt = safe_next(request.args.get("next"))
    if session.get("gamemaster"):
        return redirect(url_for("index"))
    if current_player_row():
        return redirect(url_for("play"))
    if gate_ok():
        return redirect(nxt)
    return render_template("gate.html", next=nxt)


@app.route("/api/gate/challenge")
@rate_limited("gate_challenge", 6, burst=4)
def gate_challenge():
    return jsonify(issue_gate_challenge())


@app.route("/api/gate", methods=["POST"])
@rate_limited("gate_solve", 6, burst=4)
def gate_post():
    b = body()
    if not verify_gate(b.get("challenge"), b.get("counters")):
        return err("The connection check failed. Run it again.")
    grant_gate_pass()
    return jsonify({"ok": True, "next": safe_next(b.get("next"))})


def to_gate():
    return redirect(url_for("gate", next=request.full_path.rstrip("?")))


# ====================================================================== sign in / out
@app.route("/login")
def login():
    if session.get("gamemaster"):
        return redirect(url_for("index"))
    if current_player_row():
        return redirect(url_for("play"))
    if not gate_ok():
        return to_gate()
    return render_template("login.html", bits=LOGIN_POW_BITS)


@app.route("/api/login/challenge")
@rate_limited("login_challenge", 20)
def login_challenge():
    if not gate_ok():
        return gate_refused()
    return jsonify(issue_challenge(LOGIN_POW_BITS))


@app.route("/api/login", methods=["POST"])
@rate_limited("login", 8, burst=5)
def login_post():
    if not gate_ok():
        return gate_refused()
    b = body()
    if not verify_pow(b.get("challenge"), b.get("counter"), LOGIN_POW_BITS):
        return err("Browser check failed. Reload and try again.")
    username = str(b.get("username") or "").strip()
    pw = str(b.get("password") or "")
    db = get_db()
    nxt = b.get("next") if isinstance(b.get("next"), str) and re.fullmatch(r"/(?![/\\])[A-Za-z0-9_\-./#?=&]*", b.get("next")) else None
    if username.lower() == "gamemaster":
        if not check_password_hash(kv_get(db, "gamemaster_password"), pw):
            time.sleep(0.5)
            gate_fail()
            return err("Wrong username or password.", 401)
        gate_consume()
        session.clear()
        session.permanent = True
        session["t0"] = time.time()
        session["gamemaster"] = True
        return jsonify({"ok": True, "next": nxt if nxt and not nxt.startswith("/play") else "/"})
    row = db.execute("SELECT * FROM players WHERE username=?", (username,)).fetchone()
    if not row or not check_password_hash(row["pw_hash"], pw):
        time.sleep(0.5)
        gate_fail()
        return err("Wrong username or password.", 401)
    gate_consume()
    session.clear()
    session.permanent = True
    session["t0"] = time.time()
    session["pid"] = row["id"]
    session["pwv"] = row["pw_rev"]
    return jsonify({"ok": True, "next": "/play"})


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/invite/<token>")
@rate_limited("invite_page", 30)
def invite_page(token):
    if not gate_ok():
        return to_gate()
    inv, problem = game.invite_row(token)
    return render_template("invite.html", token=token, problem=problem,
                           game_name=inv["game_name"] if inv else "", bits=LOGIN_POW_BITS)


# ====================================================================== pages
# The app's screens (home, game, map, sheets, the player page) open inside a thin persistent frame
# (shell.html) that keeps the music playing while you move between them: browsers only allow sound on
# a newly loaded page after a click there. A top-level visit gets the frame, and the frame loads the
# screen itself (Sec-Fetch-Dest: iframe, or ?embed=1 for browsers that don't send that header).
SHELL = os.environ.get("SHADOWGRID_SHELL", "1") != "0"


def app_page(template, **kw):
    inner = request.headers.get("Sec-Fetch-Dest") in ("iframe", "frame") or request.args.get("embed") == "1"
    if SHELL and not inner:
        resp = make_response(render_template("shell.html", player=template == "play.html"))
    else:
        resp = make_response(render_template(template, **kw))
    resp.headers["Vary"] = "Sec-Fetch-Dest"
    return resp

@app.route("/")
@gamemaster_required
def index():
    return app_page("index.html")


@app.route("/game/<cid>")
@gamemaster_required
def game_page(cid):
    game.game_or_404(cid)
    return app_page("game.html", game_id=cid)


@app.route("/game/<cid>/sheet/<pid>")
@gamemaster_required
def gm_sheet_page(cid, pid):
    row = game.fetch_player_row(pid)
    if row["campaign_id"] != cid:
        return redirect(url_for("game_page", cid=row["campaign_id"]))
    return app_page("gm_sheet.html", game_id=cid, player_id=pid)


@app.route("/map/<map_id>")
@gamemaster_required
def editor(map_id):
    maps.fetch_map(map_id)
    return app_page("editor.html", map_id=map_id)


@app.route("/play")
def play():
    row = current_player_row()
    if not row:
        if session.get("gamemaster"):
            return redirect(url_for("index"))
        return redirect(url_for("login"))
    return app_page("play.html")


# ====================================================================== printable sheets
@app.route("/print/sheet")
def print_own_sheet():
    if not current_player_row():
        return redirect(url_for("index" if session.get("gamemaster") else "login"))
    return render_template("print.html", sheet_url="/api/me/sheet")


@app.route("/print/sheet/<pid>")
@gamemaster_required
def print_player_sheet(pid):
    game.fetch_player_row(pid)
    return render_template("print.html", sheet_url=f"/api/players/{pid}/sheet")


@app.route("/print/blank")
def print_blank_sheet():
    if not session.get("gamemaster") and not current_player_row():
        return redirect(url_for("login", next="/print/blank"))
    return render_template("print.html", sheet_url="")


# ====================================================================== live updates
@app.route("/api/events")
def events():
    """Server-sent events: "change" whenever anything was written, a comment every 20 s to keep the
    connection open. Pages refetch their state on "change". The stream ends after ~25 minutes and the
    browser reconnects on its own."""
    if not session.get("gamemaster") and not current_player_row():
        return jsonify({"error": "Sign in required."}), 401
    if BUS.streams >= MAX_STREAMS:
        return jsonify({"error": "Too many open pages."}), 503

    def gen():
        with BUS.cond:
            BUS.streams += 1
        try:
            seen = BUS.seq
            yield f"retry: 3000\nevent: hello\ndata: {seen}\n\n"
            end = time.time() + 25 * 60
            while time.time() < end:
                cur = BUS.wait(seen, 20)
                if cur != seen:
                    seen = cur
                    time.sleep(0.08)          # let a burst of writes settle into one event
                    seen = BUS.seq
                    yield f"event: change\ndata: {seen}\n\n"
                else:
                    yield ": ping\n\n"
        finally:
            with BUS.cond:
                BUS.streams -= 1

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# ====================================================================== errors
@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found."}), 404
    return render_template("error.html", code=404, text="Not Found"), 404


@app.errorhandler(401)
def unauthorized(_e):
    return jsonify({"error": "Unauthorized."}), 401


@app.errorhandler(403)
def forbidden(_e):
    return jsonify({"error": "Forbidden."}), 403


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "Request too large."}), 413


@app.errorhandler(500)
def server_error(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error."}), 500
    return render_template("error.html", code=500, text="Internal Server Error"), 500


# ====================================================================== CLI
def set_password_cli():
    init_db(quiet=True)
    pw = getpass.getpass("New gamemaster password: ")
    if len(pw) < 8:
        print("Use at least 8 characters.")
        sys.exit(1)
    if pw != getpass.getpass("Repeat: "):
        print("Passwords do not match.")
        sys.exit(1)
    db = sqlite3.connect(DB_PATH)
    kv_set(db, "gamemaster_password", generate_password_hash(pw))
    db.commit()
    db.close()
    print("Password updated. Sign in with username 'gamemaster'.")


def has_password_cli():
    """Exit 0 when a gamemaster password exists (used by install.sh)."""
    db = sqlite3.connect(DB_PATH)
    try:
        row = db.execute("SELECT v FROM kv WHERE k='gamemaster_password'").fetchone()
    except sqlite3.Error:
        row = None
    db.close()
    sys.exit(0 if row else 1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "set-password":
        set_password_cli()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "has-password":
        has_password_cli()
    init_db()
    catalog_blob()          # build the catalog now rather than on the first page load
    run_server(5000)
else:
    init_db()

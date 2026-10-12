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

from flask import Response, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import backup  # noqa: F401  (registers routes)
import fight  # noqa: F401  (registers routes)
import game  # noqa: F401  (registers routes)
import handouts  # noqa: F401  (registers routes)
import sessions  # noqa: F401  (registers routes)
import maps  # noqa: F401  (registers routes)
from core import (BUS, DB_PATH, MAX_STREAMS, app, body, current_player_row, err, get_db, init_db, kv_get, kv_set)
from security import LOGIN_POW_BITS, gamemaster_required, issue_challenge, rate_limited, verify_pow


# ====================================================================== sign in / out
@app.route("/login")
def login():
    if session.get("gamemaster"):
        return redirect(url_for("index"))
    if current_player_row():
        return redirect(url_for("play"))
    return render_template("login.html", bits=LOGIN_POW_BITS)


@app.route("/api/login/challenge")
@rate_limited("login_challenge", 20)
def login_challenge():
    return jsonify(issue_challenge(LOGIN_POW_BITS))


@app.route("/api/login", methods=["POST"])
@rate_limited("login", 8, burst=5)
def login_post():
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
            return err("Wrong username or password.", 401)
        session.clear()
        session.permanent = True
        session["gamemaster"] = True
        return jsonify({"ok": True, "next": nxt if nxt and not nxt.startswith("/play") else "/"})
    row = db.execute("SELECT * FROM players WHERE username=?", (username,)).fetchone()
    if not row or not check_password_hash(row["pw_hash"], pw):
        time.sleep(0.5)
        return err("Wrong username or password.", 401)
    session.clear()
    session.permanent = True
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
    inv, problem = game.invite_row(token)
    return render_template("invite.html", token=token, problem=problem,
                           game_name=inv["game_name"] if inv else "", bits=LOGIN_POW_BITS)


# ====================================================================== pages
@app.route("/")
@gamemaster_required
def index():
    return render_template("index.html")


@app.route("/game/<cid>")
@gamemaster_required
def game_page(cid):
    game.game_or_404(cid)
    return render_template("game.html", game_id=cid)


@app.route("/game/<cid>/sheet/<pid>")
@gamemaster_required
def gm_sheet_page(cid, pid):
    row = game.fetch_player_row(pid)
    if row["campaign_id"] != cid:
        return redirect(url_for("game_page", cid=row["campaign_id"]))
    return render_template("gm_sheet.html", game_id=cid, player_id=pid)


@app.route("/map/<map_id>")
@gamemaster_required
def editor(map_id):
    maps.fetch_map(map_id)
    return render_template("editor.html", map_id=map_id)


@app.route("/play")
def play():
    row = current_player_row()
    if not row:
        if session.get("gamemaster"):
            return redirect(url_for("index"))
        return redirect(url_for("login"))
    return render_template("play.html")


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
    app.run(debug=False, threaded=True, host=os.environ.get("SHADOWGRID_HOST", "127.0.0.1"), port=int(os.environ.get("SHADOWGRID_PORT", "5000")))
else:
    init_db()

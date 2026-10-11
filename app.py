"""ShadowGrid - Shadowrun 6E character sheets + GridMap fog-of-war maps for one table.

Run locally:      python app.py
Serve publicly:   python serve.py     (see README)
Set GM password:  python app.py set-password
"""
import getpass
import os
import re
import sqlite3
import sys
import time

from flask import jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import fight  # noqa: F401  (registers routes)
import game  # noqa: F401  (registers routes)
import maps  # noqa: F401  (registers routes)
from core import (DB_PATH, app, body, current_player_row, err, get_db, init_db, kv_get, kv_set)
from security import LOGIN_POW_BITS, admin_required, issue_challenge, rate_limited, verify_pow


# ====================================================================== sign in / out
@app.route("/login")
def login():
    if session.get("admin"):
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
    if username.lower() == "admin":
        if not check_password_hash(kv_get(db, "admin_password"), pw):
            time.sleep(0.5)
            return err("Wrong username or password.", 401)
        session.clear()
        session.permanent = True
        session["admin"] = True
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
@admin_required
def index():
    return render_template("index.html")


@app.route("/game/<cid>")
@admin_required
def game_page(cid):
    game.game_or_404(cid)
    return render_template("game.html", game_id=cid)


@app.route("/game/<cid>/sheet/<pid>")
@admin_required
def gm_sheet_page(cid, pid):
    row = game.fetch_player_row(pid)
    if row["campaign_id"] != cid:
        return redirect(url_for("game_page", cid=row["campaign_id"]))
    return render_template("gm_sheet.html", game_id=cid, player_id=pid)


@app.route("/map/<map_id>")
@admin_required
def editor(map_id):
    maps.fetch_map(map_id)
    return render_template("editor.html", map_id=map_id)


@app.route("/play")
def play():
    row = current_player_row()
    if not row:
        if session.get("admin"):
            return redirect(url_for("index"))
        return redirect(url_for("login"))
    return render_template("play.html")


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
    pw = getpass.getpass("New GM (admin) password: ")
    if len(pw) < 8:
        print("Use at least 8 characters.")
        sys.exit(1)
    if pw != getpass.getpass("Repeat: "):
        print("Passwords do not match.")
        sys.exit(1)
    db = sqlite3.connect(DB_PATH)
    kv_set(db, "admin_password", generate_password_hash(pw))
    db.commit()
    db.close()
    print("Password updated. Sign in with username 'admin'.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "set-password":
        set_password_cli()
        sys.exit(0)
    init_db()
    app.run(debug=False, threaded=True, host=os.environ.get("GRIDMAP_HOST", "127.0.0.1"), port=int(os.environ.get("GRIDMAP_PORT", "5000")))
else:
    init_db()

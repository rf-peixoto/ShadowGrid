"""Shared app object, database, and helpers used by every route module."""
import json
import os
import secrets
import sqlite3
import time
from datetime import timedelta
from functools import wraps

from flask import Flask, abort, g, jsonify, redirect, request, session, url_for
from werkzeug.security import generate_password_hash

from security import apply_security_headers, csrf_ok
from sr import rules as R

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("GRIDMAP_DB", os.path.join(BASE_DIR, "shadowgrid.db"))
HTTPS = os.environ.get("GRIDMAP_HTTPS") == "1"
INVITE_DAYS = 7

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=HTTPS,
    SESSION_COOKIE_NAME="sg_session",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
    JSON_SORT_KEYS=False,
)
app.json.sort_keys = False
app.after_request(apply_security_headers)

DEFAULT_SETTINGS = {
    # Sixth World palette: teal-black void, steel-teal floors, AR-cyan edges, neon magenta markers
    "colors": {
        "background": "#0b1214", "grid": "#1a2c30", "fog": "#050909",
        "cellDefault": "#1c4a52", "cellBorder": "#4fd8dc",
        "exploredTint": "#ffffff", "revealedTint": "#3e5c60",
        "secretHatch": "#ff2f7d", "markerDefault": "#ff2f7d", "markerText": "#12060b",
        "doorDefault": "#2de2e6", "doorOpen": "#6dff9c", "highlight": "#ffffff",
        "roomLabel": "#9ff3f5", "tokenOutline": "#ffffff",
    },
    "doorPalette": ["#2de2e6", "#ff2f7d", "#6dff9c", "#ffb02e", "#b98cff", "#ffffff"],
    "legendVisible": True, "showGrid": True, "showRoomLabels": True,
}
PLAYER_COLORS = ["#ff2f7d", "#2de2e6", "#6dff9c", "#ffb02e", "#b98cff", "#ff6b3d", "#3dffd0", "#ffffff"]
GM_COLOR = "#ffd23f"

DRAFT, SUBMITTED, APPROVED = 0, 1, 2
STATUS_NAMES = {DRAFT: "draft", SUBMITTED: "waiting", APPROVED: "approved"}


# ====================================================================== db
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA synchronous=NORMAL")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS campaigns (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS maps (
  id TEXT PRIMARY KEY, campaign_id TEXT REFERENCES campaigns(id) ON DELETE SET NULL,
  name TEXT NOT NULL, grid_type TEXT NOT NULL DEFAULT 'square',
  width INTEGER NOT NULL, height INTEGER NOT NULL, cell_size INTEGER NOT NULL DEFAULT 32,
  settings TEXT NOT NULL, data TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS players (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE, pw_hash TEXT NOT NULL, pw_rev INTEGER NOT NULL DEFAULT 0,
  color TEXT NOT NULL, radius INTEGER NOT NULL DEFAULT 1,
  current_map_id TEXT, state TEXT NOT NULL, ping TEXT,
  approved INTEGER NOT NULL DEFAULT 0, review_note TEXT,
  character TEXT NOT NULL, char_rev INTEGER NOT NULL DEFAULT 0,
  last_seen REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS invites (
  token TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  note TEXT, created_at REAL NOT NULL, expires_at REAL NOT NULL,
  used_by TEXT REFERENCES players(id) ON DELETE SET NULL, used_at REAL);
CREATE TABLE IF NOT EXISTS snapshots (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  name TEXT NOT NULL, state TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS rolls (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  player_id TEXT, who TEXT NOT NULL, color TEXT NOT NULL, kind TEXT NOT NULL,
  data TEXT NOT NULL, hidden INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', reward INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'Active', tasks TEXT NOT NULL DEFAULT '[]', assignees TEXT NOT NULL DEFAULT '[]',
  payout INTEGER, created_at REAL NOT NULL, updated_at REAL NOT NULL, completed_at REAL);
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, delta INTEGER NOT NULL, balance INTEGER NOT NULL, reason TEXT NOT NULL,
  by_gm INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_rolls_campaign ON rolls(campaign_id, created_at);
CREATE INDEX IF NOT EXISTS idx_maps_campaign ON maps(campaign_id);
CREATE INDEX IF NOT EXISTS idx_players_campaign ON players(campaign_id);
CREATE INDEX IF NOT EXISTS idx_runs_campaign ON runs(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ledger_player ON ledger(player_id, created_at);
"""


def kv_get(db, k):
    row = db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return row["v"] if row else None


def kv_set(db, k, v):
    db.execute("INSERT INTO kv (k,v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))


MIGRATIONS = [
    ("campaigns", "settings", "TEXT NOT NULL DEFAULT '{}'"),
    ("campaigns", "combat", "TEXT NOT NULL DEFAULT '{}'"),
]


def init_db(quiet=False):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    for table, col, decl in MIGRATIONS:
        cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    secret = kv_get(db, "secret_key")
    if not secret:
        secret = secrets.token_hex(32)
        kv_set(db, "secret_key", secret)
    env_pw = os.environ.get("GRIDMAP_ADMIN_PASSWORD")
    if env_pw:
        kv_set(db, "admin_password", generate_password_hash(env_pw))
    elif not kv_get(db, "admin_password"):
        pw = secrets.token_urlsafe(12)
        kv_set(db, "admin_password", generate_password_hash(pw))
        if not quiet:
            print("=" * 64)
            print("  Admin (GM) account bootstrapped.")
            print("  Username: admin")
            print(f"  Password: {pw}      <- save it now, it is not shown again")
            print("  Change it any time with:  python app.py set-password")
            print("=" * 64, flush=True)
    db.commit()
    db.close()
    app.secret_key = secret
    return secret


# ====================================================================== small helpers
def now():
    return time.time()


def new_id(n=12):
    return secrets.token_hex(n // 2)


def body():
    b = request.get_json(force=True, silent=True)
    return b if isinstance(b, dict) else {}


def clamp_int(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def clean_color(v, default):
    if isinstance(v, str) and len(v) == 7 and v[0] == "#":
        try:
            int(v[1:], 16)
            return v.lower()
        except ValueError:
            pass
    return default


def err(msg, code=400):
    return jsonify({"error": msg}), code


# ====================================================================== game settings
GAME_DEFAULTS = {"sellPct": 50}


def game_settings(cid):
    row = get_db().execute("SELECT settings FROM campaigns WHERE id=?", (cid,)).fetchone() if cid else None
    out = dict(GAME_DEFAULTS)
    if row:
        try:
            out.update({k: v for k, v in json.loads(row["settings"] or "{}").items() if k in GAME_DEFAULTS})
        except ValueError:
            pass
    return out


# ====================================================================== players & characters
def load_char(row):
    try:
        c = json.loads(row["character"])
    except (TypeError, ValueError):
        c = R.new_character()
    return R.normalize(c)


def display_name(row, c=None):
    c = c if c is not None else load_char(row)
    return (c.get("name") or "").strip() or row["username"]


def row_to_player(row, include_state=True):
    c = load_char(row)
    d = R.derive(c)
    p = {"id": row["id"], "campaignId": row["campaign_id"], "username": row["username"],
         "name": display_name(row, c), "color": row["color"], "radius": row["radius"],
         "currentMapId": row["current_map_id"], "createdAt": row["created_at"], "lastSeen": row["last_seen"],
         "approved": row["approved"], "status": STATUS_NAMES.get(row["approved"], "draft"),
         "reviewNote": row["review_note"],
         "cm": R.condition_summary(c, d), "edge": {"cur": c["current_edge"], "max": d["edge_max"]},
         "karma": c["karma"], "nuyen": c["nuyen"], "metatype": c["metatype"], "role": c.get("role", ""), "magicType": c["magic_type"],
         "statuses": c.get("statuses") or {},
         "pendingContacts": sum(1 for ct in c.get("contacts") or [] if not ct.get("verified", True)),
         "init": {"score": d["initiative_score"], "dice": d["initiative_dice"], "minor": d["minor_actions"]},
         "charRev": row["char_rev"],
         "ping": json.loads(row["ping"]) if row["ping"] else None}
    if include_state:
        p["state"] = json.loads(row["state"])
    return p


def fetch_player_row(pid):
    row = get_db().execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not row:
        abort(404)
    return row


def fetch_player(pid):
    return row_to_player(fetch_player_row(pid))


def save_player(p):
    """Persist the map-related fields of a player dict (as used by the map code)."""
    get_db().execute(
        "UPDATE players SET color=?, radius=?, current_map_id=?, state=?, updated_at=? WHERE id=?",
        (p["color"], p["radius"], p["currentMapId"], json.dumps(p["state"]), now(), p["id"]))


def save_char(pid, c):
    get_db().execute("UPDATE players SET character=?, char_rev=char_rev+1, updated_at=? WHERE id=?",
                     (json.dumps(c), now(), pid))


def ledger_add(cid, pid, kind, delta, balance, reason, by_gm):
    get_db().execute("INSERT INTO ledger (campaign_id,player_id,kind,delta,balance,reason,by_gm,created_at) VALUES (?,?,?,?,?,?,?,?)",
                     (cid, pid, kind, int(delta), int(balance), str(reason)[:200], 1 if by_gm else 0, now()))


def ledger_rows(pid=None, cid=None, limit=60):
    db = get_db()
    if pid:
        rows = db.execute("SELECT l.*, p.username FROM ledger l JOIN players p ON p.id=l.player_id WHERE l.player_id=? ORDER BY l.id DESC LIMIT ?", (pid, limit)).fetchall()
    else:
        rows = db.execute("SELECT l.*, p.username FROM ledger l JOIN players p ON p.id=l.player_id WHERE l.campaign_id=? ORDER BY l.id DESC LIMIT ?", (cid, limit)).fetchall()
    return [{"id": r["id"], "playerId": r["player_id"], "username": r["username"], "kind": r["kind"], "delta": r["delta"],
             "balance": r["balance"], "reason": r["reason"], "byGm": bool(r["by_gm"]), "at": r["created_at"]} for r in rows]


# ====================================================================== rolls (shared table log)
def add_roll(cid, pid, who, color, kind, data, hidden=False):
    rid = new_id()
    t = now()
    db = get_db()
    db.execute("INSERT INTO rolls (id,campaign_id,player_id,who,color,kind,data,hidden,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
               (rid, cid, pid, str(who)[:60], color, kind, json.dumps(data), 1 if hidden else 0, t, t))
    db.execute("DELETE FROM rolls WHERE campaign_id=? AND id NOT IN (SELECT id FROM rolls WHERE campaign_id=? ORDER BY created_at DESC LIMIT 300)", (cid, cid))
    return rid


def roll_rows(cid, admin=False, limit=40):
    if not cid:
        return []
    q = "SELECT * FROM rolls WHERE campaign_id=?" + ("" if admin else " AND hidden=0") + " ORDER BY created_at DESC LIMIT ?"
    rows = get_db().execute(q, (cid, limit)).fetchall()
    return [{"id": r["id"], "playerId": r["player_id"], "who": r["who"], "color": r["color"], "kind": r["kind"],
             "data": json.loads(r["data"]), "hidden": bool(r["hidden"]), "at": r["created_at"], "updatedAt": r["updated_at"]} for r in rows]


def campaign_version(cid, map_id=None):
    """Cheap change counter for polling: newest write anywhere in the game."""
    db = get_db()
    v = 0.0
    if cid:
        for table, col in (("players", "updated_at"), ("maps", "updated_at"), ("rolls", "updated_at"), ("runs", "updated_at")):
            row = db.execute(f"SELECT MAX({col}) FROM {table} WHERE campaign_id=?", (cid,)).fetchone()
            v = max(v, row[0] or 0.0)
        row = db.execute("SELECT updated_at FROM campaigns WHERE id=?", (cid,)).fetchone()
        v = max(v, row[0] if row else 0.0)
    if map_id:
        row = db.execute("SELECT updated_at FROM maps WHERE id=?", (map_id,)).fetchone()
        v = max(v, row[0] if row else 0.0)
    return repr(v)


# ====================================================================== player auth
def current_player_row():
    pid = session.get("pid")
    if not pid:
        return None
    row = get_db().execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not row or row["pw_rev"] != session.get("pwv"):
        session.clear()
        return None
    return row


def player_required(fn):
    """Signed-in player (not the GM). Passes the player row as ``me``."""
    @wraps(fn)
    def wrapper(*a, **kw):
        row = current_player_row()
        if not row:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Sign in required."}), 401
            if session.get("admin"):
                return redirect(url_for("index"))
            return redirect(url_for("login", next=request.path))
        if not csrf_ok():
            abort(403)
        if not row["last_seen"] or now() - row["last_seen"] > 30:
            get_db().execute("UPDATE players SET last_seen=? WHERE id=?", (now(), row["id"]))
            get_db().commit()
        return fn(row, *a, **kw)
    return wrapper

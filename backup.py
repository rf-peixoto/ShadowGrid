"""Backups (gamemaster only): one zip with a consistent copy of the database, the uploaded images
and a manifest. Backups are kept in data/backups (the newest ones), can be downloaded, and a backup
file can be restored. Restoring first saves the current state as a backup, so it can be undone.

A daily backup is also made automatically (on the first request of the day), keeping the last
AUTO_KEEP automatic ones. Automatic backups leave the (large) music files out; manual ones include
them unless asked not to. Restoring a backup without music keeps the music files already on the server.
"""
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile

from flask import jsonify, request, send_file, session

import core
from core import BACKUP_DIR, DB_PATH, UPLOAD_DIR, app, err
from security import gamemaster_required

FORMAT = "shadowgrid-backup-1"
AUTO_KEEP = 10
MANUAL_KEEP = 30
MAX_RESTORE = 2048 * 1024 * 1024
NAME_RE = re.compile(r"^shadowgrid-(auto|manual|before-restore)-\d{8}-\d{6}\.zip$")
UPLOAD_NAME_RE = re.compile(r"^[a-f0-9]{24}\.(png|jpg)$")
MUSIC_NAME_RE = re.compile(r"^[a-f0-9]{32}\.(webm|m4a)$")
REQUIRED_TABLES = {"kv", "campaigns", "maps", "players", "invites", "snapshots", "rolls", "runs", "ledger"}
_lock = threading.Lock()


def _stamp():
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())


def _db_copy(dst_path):
    """Consistent copy of the live database (works while it's in use)."""
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def make_backup(kind="manual", with_music=None):
    """Write data/backups/shadowgrid-<kind>-<time>.zip and return its file name."""
    import music
    if with_music is None:
        with_music = kind != "auto"
    with _lock:
        name = f"shadowgrid-{kind}-{_stamp()}.zip"
        while os.path.exists(os.path.join(BACKUP_DIR, name)):
            time.sleep(1)
            name = f"shadowgrid-{kind}-{_stamp()}.zip"
        path = os.path.join(BACKUP_DIR, name)
        with tempfile.TemporaryDirectory(dir=BACKUP_DIR) as tmp:
            db_tmp = os.path.join(tmp, "shadowgrid.db")
            _db_copy(db_tmp)
            uploads = sorted(f for f in os.listdir(UPLOAD_DIR) if UPLOAD_NAME_RE.match(f))
            tracks = sorted(f for f in os.listdir(music.MUSIC_DIR) if MUSIC_NAME_RE.match(f)) if with_music else []
            manifest = {"format": FORMAT, "created": time.time(), "kind": kind, "uploads": len(uploads),
                        "music": len(tracks), "withMusic": bool(with_music)}
            part = path + ".part"
            with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("manifest.json", json.dumps(manifest, indent=2))
                z.write(db_tmp, "shadowgrid.db")
                for f in uploads:
                    z.write(os.path.join(UPLOAD_DIR, f), f"uploads/{f}")
                for f in tracks:      # already compressed: store, don't deflate
                    z.write(os.path.join(music.MUSIC_DIR, f), f"music/{f}", compress_type=zipfile.ZIP_STORED)
            os.chmod(part, 0o600)
            os.replace(part, path)
        _prune()
        return name


def _prune():
    files = sorted((f for f in os.listdir(BACKUP_DIR) if NAME_RE.match(f)), reverse=True)
    autos = [f for f in files if "-auto-" in f]
    others = [f for f in files if "-auto-" not in f]
    for f in autos[AUTO_KEEP:] + others[MANUAL_KEEP:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, f))
        except OSError:
            pass


def list_backups():
    out = []
    for f in sorted((f for f in os.listdir(BACKUP_DIR) if NAME_RE.match(f)), reverse=True):
        st = os.stat(os.path.join(BACKUP_DIR, f))
        kind = "auto" if "-auto-" in f else "before-restore" if "-before-restore-" in f else "manual"
        out.append({"name": f, "size": st.st_size, "at": st.st_mtime, "kind": kind})
    return out


_last_auto = {"day": None}


@app.before_request
def _daily_backup():
    """First request of each day: make an automatic backup (quietly; never blocks a request on failure)."""
    day = time.strftime("%Y%m%d")
    if _last_auto["day"] == day:
        return
    _last_auto["day"] = day
    if any(f.startswith(f"shadowgrid-auto-{day}") for f in os.listdir(BACKUP_DIR)):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        has_data = conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0] > 0
        conn.close()
        if has_data:
            threading.Thread(target=lambda: _safe(make_backup, "auto"), daemon=True).start()
    except sqlite3.Error:
        pass


def _safe(fn, *a):
    try:
        fn(*a)
    except Exception as e:  # noqa: BLE001 - a failed automatic backup must never take the app down
        print("Automatic backup failed:", e, flush=True)


# ---------------------------------------------------------------- restore
class RestoreError(ValueError):
    pass


def _check_backup(zf):
    """Validate a backup zip; returns (db_bytes, {upload name: bytes}, [music member names])."""
    names = zf.namelist()
    if "manifest.json" not in names or "shadowgrid.db" not in names:
        raise RestoreError("This isn't a ShadowGrid backup (manifest or database missing).")
    try:
        manifest = json.loads(zf.read("manifest.json"))
    except ValueError:
        raise RestoreError("The backup's manifest is damaged.")
    if manifest.get("format") != FORMAT:
        raise RestoreError("This backup comes from another version of ShadowGrid.")
    total = sum(i.file_size for i in zf.infolist())
    if total > 2 * MAX_RESTORE:
        raise RestoreError("The backup is too large once unpacked.")
    uploads, tracks = {}, []
    for n in names:
        if n in ("manifest.json", "shadowgrid.db"):
            continue
        if n.startswith("music/") and MUSIC_NAME_RE.match(n[6:]):
            tracks.append(n)
            continue
        m = re.match(r"^uploads/([a-f0-9]{24}\.(?:png|jpg))$", n)
        if not m:
            raise RestoreError(f"Unexpected file in the backup: {n[:60]}")
        uploads[m.group(1)] = zf.read(n)
    return zf.read("shadowgrid.db"), uploads, tracks


def _check_db(path):
    conn = sqlite3.connect(path)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RestoreError("The backup's database is damaged.")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not REQUIRED_TABLES <= tables:
            raise RestoreError("The backup's database is missing tables.")
        if not conn.execute("SELECT v FROM kv WHERE k='gamemaster_password'").fetchone():
            raise RestoreError("The backup has no gamemaster account.")
    except sqlite3.DatabaseError:
        raise RestoreError("The backup's database can't be read.")
    finally:
        conn.close()


def restore_bytes(data):
    """Restore a backup zip given as bytes (tests). See restore_file."""
    return restore_file(io.BytesIO(data))


def restore_file(fileobj):
    """Restore a backup zip (a path or an open file). Saves the current state first. Returns that safety backup's name."""
    try:
        zf = zipfile.ZipFile(fileobj)
    except (zipfile.BadZipFile, OSError):
        raise RestoreError("That file isn't a zip backup.")
    db_bytes, uploads, tracks = _check_backup(zf)
    import music
    from core import init_db
    with tempfile.TemporaryDirectory(dir=BACKUP_DIR) as tmp:
        new_db = os.path.join(tmp, "restore.db")
        with open(new_db, "wb") as f:
            f.write(db_bytes)
        _check_db(new_db)
        safety = make_backup("before-restore")
        with _lock:
            # copy the backup into the live database file (other connections see the new content)
            src = sqlite3.connect(new_db)
            dst = sqlite3.connect(DB_PATH)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            for f in os.listdir(UPLOAD_DIR):
                if UPLOAD_NAME_RE.match(f) and f not in uploads:
                    os.remove(os.path.join(UPLOAD_DIR, f))
            for name, blob in uploads.items():
                with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
                    f.write(blob)
            for member in tracks:             # streamed: music can be large
                with zf.open(member) as src, open(os.path.join(music.MUSIC_DIR, member[6:]), "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
            _reconcile_music(music)
    init_db(quiet=True)      # schema of this version + the restored secret key (signs everyone out)
    return safety


def _reconcile_music(music):
    """After a restore: drop music files no track uses; tracks whose files are missing can't play."""
    conn = sqlite3.connect(DB_PATH)
    try:
        try:
            rows = conn.execute("SELECT id, status FROM music").fetchall()
        except sqlite3.Error:          # a backup from before music existed
            rows = []
        ids = {r[0] for r in rows}
        for f in os.listdir(music.MUSIC_DIR):
            if MUSIC_NAME_RE.match(f) and f[:32] not in ids:
                os.remove(os.path.join(music.MUSIC_DIR, f))
        for tid, status in rows:
            have = all(os.path.exists(os.path.join(music.MUSIC_DIR, f"{tid}.{e}")) for e in ("webm", "m4a"))
            if status != "ready" or not have:
                conn.execute("UPDATE music SET status='failed', error='Not in the restored backup. Upload it again.' WHERE id=? AND status!='failed'", (tid,))
                conn.execute("DELETE FROM music_state WHERE track_id=?", (tid,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- routes
@app.route("/api/backups")
@gamemaster_required
def backups_list():
    return jsonify({"backups": list_backups()})


@app.route("/api/backups", methods=["POST"])
@gamemaster_required
def backups_create():
    name = make_backup("manual", with_music=bool((request.get_json(silent=True) or {}).get("music", True)))
    return jsonify({"name": name, "backups": list_backups()}), 201


@app.route("/api/backups/<name>")
@gamemaster_required
def backups_download(name):
    if not NAME_RE.match(name) or not os.path.exists(os.path.join(BACKUP_DIR, name)):
        return err("Backup not found.", 404)
    return send_file(os.path.join(BACKUP_DIR, name), mimetype="application/zip", as_attachment=True, download_name=name)


@app.route("/api/backups/<name>", methods=["DELETE"])
@gamemaster_required
def backups_delete(name):
    if not NAME_RE.match(name):
        return err("Backup not found.", 404)
    try:
        os.remove(os.path.join(BACKUP_DIR, name))
    except FileNotFoundError:
        return err("Backup not found.", 404)
    return jsonify({"backups": list_backups()})


@app.route("/api/backups/<name>/restore", methods=["POST"])
@gamemaster_required
def backups_restore_saved(name):
    if not NAME_RE.match(name) or not os.path.exists(os.path.join(BACKUP_DIR, name)):
        return err("Backup not found.", 404)
    return _restore(os.path.join(BACKUP_DIR, name))


@app.route("/api/backup/restore", methods=["POST"])
@gamemaster_required
def backups_restore_upload():
    request.max_content_length = MAX_RESTORE
    f = request.files.get("file")
    if not f:
        return err("Choose a backup file.")
    with tempfile.NamedTemporaryFile(dir=BACKUP_DIR, suffix=".upload") as tmp:
        shutil.copyfileobj(f.stream, tmp, 1 << 20)
        tmp.flush()
        if tmp.tell() > MAX_RESTORE:
            return err("The backup is too large.", 413)
        return _restore(tmp.name)


def _restore(path):
    try:
        safety = restore_file(path)
    except RestoreError as e:
        return err(str(e))
    session.clear()
    core.BUS.notify()
    return jsonify({"ok": True, "safety": safety,
                    "message": "Backup restored. Everyone is signed out; sign in with the gamemaster password stored in that backup."})

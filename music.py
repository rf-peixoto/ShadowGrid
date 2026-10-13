"""Music: the gamemaster uploads tracks, ShadowGrid compresses them once, and one track at a time plays
for everyone in the game.

Uploads are transcoded in the background with ffmpeg (loudness-normalised, metadata and cover art
stripped) to Opus at MUSIC_KBPS in WebM, plus a small AAC fallback for browsers without Opus. The
original file is deleted afterwards.

"Live" means a shared timeline: the server stores which track started when, and every browser plays
that track from the same moment (late joiners drop in mid-song). Starting a track replaces the one
that was playing; Stop stops it for everyone.
"""
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time

from flask import jsonify, request, send_file, session

import core
from core import DATA_DIR, app, body, current_player_row, err, get_db, new_id, now
from security import gamemaster_required, rate_limited

MUSIC_DIR = os.path.join(DATA_DIR, "music")
os.makedirs(MUSIC_DIR, mode=0o700, exist_ok=True)
MAX_UPLOAD_MB = int(os.environ.get("SHADOWGRID_MUSIC_MAX_MB", "100"))
MAX_TOTAL_MB = int(os.environ.get("SHADOWGRID_MUSIC_TOTAL_MB", "2048"))
KBPS = max(16, min(160, int(os.environ.get("SHADOWGRID_MUSIC_KBPS", "48"))))
AAC_KBPS = max(KBPS + 16, 64)
MAX_SECONDS = 3600
TITLE_MAX = 80
# extension -> the ffmpeg demuxer to force (never let ffmpeg guess: playlists could point at other files)
FORMATS = {".mp3": "mp3", ".ogg": "ogg", ".oga": "ogg", ".opus": "ogg", ".wav": "wav", ".flac": "flac",
           ".m4a": "mov", ".mp4": "mov", ".aac": "aac", ".webm": "matroska", ".weba": "matroska", ".mka": "matroska"}
FILE_RE = re.compile(r"^([a-f0-9]{32})\.(webm|m4a)$")
MIME = {"webm": "audio/webm", "m4a": "audio/mp4"}

_jobs = threading.Semaphore(1)       # one transcode at a time: a small server stays responsive
_progress = {}                       # track id -> 0..100 while compressing
_active = set()                      # track ids queued or compressing in this process
_recovered = {"done": False}
_ffmpeg = {"path": None, "checked": False}


# ---------------------------------------------------------------- ffmpeg
def find_ffmpeg():
    """SHADOWGRID_FFMPEG, then the copy bundled with the imageio-ffmpeg package, then the system ffmpeg.
    It must have the libopus encoder."""
    if _ffmpeg["checked"]:
        return _ffmpeg["path"]
    cands = [os.environ.get("SHADOWGRID_FFMPEG")]
    try:
        import imageio_ffmpeg
        cands.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:  # noqa: BLE001 - not installed, or no binary for this platform
        pass
    cands.append(shutil.which("ffmpeg"))
    for c in cands:
        if not c or not os.path.exists(c):
            continue
        try:
            enc = subprocess.run([c, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        if "libopus" in enc:
            _ffmpeg["path"] = c
            break
    _ffmpeg["checked"] = True
    return _ffmpeg["path"]


def _transcode(tid, src, fmt):
    """Background job: src -> <tid>.webm (Opus) + <tid>.m4a (AAC). Updates the track row when done."""
    ff = find_ffmpeg()
    webm, m4a = os.path.join(MUSIC_DIR, f"{tid}.webm"), os.path.join(MUSIC_DIR, f"{tid}.m4a")
    status, error, duration = "failed", None, None
    with _jobs:
        _progress[tid] = 0
        try:
            src_dur = None
            with tempfile.TemporaryFile(dir=MUSIC_DIR) as log:
                cmd = [ff, "-nostdin", "-hide_banner", "-y", "-protocol_whitelist", "file", "-f", fmt, "-t", str(MAX_SECONDS), "-i", src,
                       "-vn", "-sn", "-dn", "-map_metadata", "-1",
                       "-filter_complex", "[0:a:0]aformat=channel_layouts=stereo|mono,loudnorm=I=-18:TP=-1.5:LRA=11,aresample=48000,asplit=2[o][a]",
                       "-map", "[o]", "-c:a", "libopus", "-b:a", f"{KBPS}k", "-vbr", "on", "-compression_level", "10",
                       "-application", "audio", "-f", "webm", webm + ".part",
                       "-map", "[a]", "-c:a", "aac", "-b:a", f"{AAC_KBPS}k", "-ar", "44100", "-movflags", "+faststart", "-f", "mp4", m4a + ".part",
                       "-progress", "pipe:1", "-nostats"]
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, text=True)
                t_end = time.time() + 20 * 60
                out_s = 0.0
                for line in p.stdout:
                    if time.time() > t_end:
                        p.kill()
                        break
                    if src_dur is None:
                        log.seek(0)
                        m = re.search(rb"Duration: (\d+):(\d+):(\d+\.?\d*)", log.read())
                        if m:
                            src_dur = min(MAX_SECONDS, int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])) or None
                    if line.startswith("out_time_us=") and line[12:].strip().isdigit():
                        out_s = int(line[12:]) / 1e6
                        if src_dur:
                            _progress[tid] = max(0, min(99, int(100 * out_s / src_dur)))
                rc = p.wait(timeout=60)
                if rc == 0 and out_s > 0.5 and os.path.getsize(webm + ".part") > 0:
                    os.replace(webm + ".part", webm)
                    os.replace(m4a + ".part", m4a)
                    os.chmod(webm, 0o600)
                    os.chmod(m4a, 0o600)
                    status, duration = "ready", round(out_s, 2)
                else:
                    log.seek(0)
                    tail = log.read().decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
                    print(f"Music: ffmpeg exit {rc} for {tid}: {tail[0][:300]}", flush=True)
                    error = "That file has no audio ShadowGrid can read." if ("does not contain any stream" in tail[0] or "Invalid data" in tail[0]
                                                                              or "matches no streams" in tail[0] or rc == 0) else "Compressing failed."
        except Exception as e:  # noqa: BLE001 - a broken upload must never take the app down
            print("Music transcode failed:", repr(e), flush=True)
            error = "Compressing failed."
        finally:
            _progress.pop(tid, None)
            for f in (src, webm + ".part", m4a + ".part"):
                try:
                    os.remove(f)
                except OSError:
                    pass
    import sqlite3
    db = sqlite3.connect(core.DB_PATH, timeout=30)
    try:
        sizes = [os.path.getsize(f) if status == "ready" else None for f in (webm, m4a)]
        db.execute("UPDATE music SET status=?, error=?, duration=?, opus_size=?, aac_size=?, updated_at=? WHERE id=?",
                   (status, error, duration, sizes[0], sizes[1], now(), tid))
        cid = db.execute("SELECT campaign_id FROM music WHERE id=?", (tid,)).fetchone()
        if cid:
            db.execute("UPDATE campaigns SET updated_at=? WHERE id=?", (now(), cid[0]))
        db.commit()
    finally:
        db.close()
    if status != "ready":
        _remove_files(tid)
    _active.discard(tid)
    core.BUS.notify()


def _start_job(tid, src, fmt):
    _active.add(tid)
    threading.Thread(target=_transcode, args=(tid, src, fmt), daemon=True, name=f"music-{tid[:6]}").start()


def _recover():
    """After a restart: compress again what was in the middle of compressing, if the upload is still there."""
    if _recovered["done"]:
        return
    _recovered["done"] = True
    db = get_db()
    for r in db.execute("SELECT id, src_ext FROM music WHERE status='processing'").fetchall():
        if r["id"] in _active:
            continue
        src = os.path.join(MUSIC_DIR, f"upload-{r['id']}{r['src_ext'] or ''}")
        if os.path.exists(src) and find_ffmpeg() and r["src_ext"] in FORMATS:
            _start_job(r["id"], src, FORMATS[r["src_ext"]])
        else:
            db.execute("UPDATE music SET status='failed', error='Interrupted by a restart. Upload it again.' WHERE id=?", (r["id"],))
    db.commit()


def _remove_files(tid):
    for ext in ("webm", "m4a"):
        try:
            os.remove(os.path.join(MUSIC_DIR, f"{tid}.{ext}"))
        except OSError:
            pass


def music_bytes():
    total = 0
    for f in os.listdir(MUSIC_DIR):
        if FILE_RE.match(f):
            total += os.path.getsize(os.path.join(MUSIC_DIR, f))
    return total


# ---------------------------------------------------------------- state
def _track(r):
    return {"id": r["id"], "title": r["title"], "status": r["status"], "error": r["error"], "duration": r["duration"],
            "srcSize": r["src_size"], "size": r["opus_size"], "aacSize": r["aac_size"], "createdAt": r["created_at"],
            "progress": _progress.get(r["id"]) if r["status"] == "processing" else None}


def tracks(cid):
    return [_track(r) for r in get_db().execute("SELECT * FROM music WHERE campaign_id=? ORDER BY title COLLATE NOCASE", (cid,)).fetchall()]


def now_playing(cid):
    """The track playing in this game (None when stopped, or when a non-looping track has ended)."""
    r = get_db().execute("SELECT s.*, m.title, m.duration, m.status FROM music_state s JOIN music m ON m.id=s.track_id WHERE s.campaign_id=?",
                         (cid,)).fetchone()
    if not r or r["status"] != "ready":
        return None
    if not r["loop"] and r["duration"] and time.time() > r["started_at"] + r["duration"] + 1:
        return None
    return {"trackId": r["track_id"], "title": r["title"], "duration": r["duration"], "startedAt": r["started_at"],
            "loop": bool(r["loop"]), "by": r["updated_at"],
            "src": {"opus": f"/music/{r['track_id']}.webm", "aac": f"/music/{r['track_id']}.m4a"}}


def _game(cid):
    return get_db().execute("SELECT id FROM campaigns WHERE id=?", (cid,)).fetchone()


def _touch(cid):
    get_db().execute("UPDATE campaigns SET updated_at=? WHERE id=?", (now(), cid))


def _state_out(cid):
    return {"playing": now_playing(cid), "serverNow": time.time()}


# ---------------------------------------------------------------- gamemaster routes
@app.route("/api/games/<cid>/music")
@gamemaster_required
def music_list(cid):
    if not _game(cid):
        return err("Game not found.", 404)
    _recover()
    return jsonify({"tracks": tracks(cid), **_state_out(cid), "ffmpeg": bool(find_ffmpeg()),
                    "maxMB": MAX_UPLOAD_MB, "usedMB": round(music_bytes() / 1048576, 1), "totalMB": MAX_TOTAL_MB,
                    "kbps": KBPS, "formats": sorted(FORMATS)})


@app.route("/api/games/<cid>/music", methods=["POST"])
@gamemaster_required
@rate_limited("music_upload", 30)
def music_upload(cid):
    if not _game(cid):
        return err("Game not found.", 404)
    if not find_ffmpeg():
        return err("ffmpeg with Opus support isn't installed on the server. Run ./install.sh again (it installs it).", 503)
    if music_bytes() > MAX_TOTAL_MB * 1048576:
        return err(f"The music library is full ({MAX_TOTAL_MB} MB). Delete some tracks first.")
    request.max_content_length = MAX_UPLOAD_MB * 1048576 + 65536
    f = request.files.get("file")
    if not f or not f.filename:
        return err("Choose an audio file.")
    ext = os.path.splitext(f.filename.lower())[1]
    if ext not in FORMATS:
        return err("Upload MP3, OGG, Opus, WAV, FLAC, M4A, AAC or WebM audio.")
    title = (str(request.form.get("title") or "").strip() or os.path.splitext(os.path.basename(f.filename))[0])
    title = re.sub(r"[\x00-\x1f]", "", title)[:TITLE_MAX] or "Untitled"
    tid = secrets.token_hex(16)
    src = os.path.join(MUSIC_DIR, f"upload-{tid}{ext}")
    size = 0
    with open(src, "wb") as out:
        os.chmod(src, 0o600)
        while True:
            chunk = f.stream.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1048576:
                out.close()
                os.remove(src)
                return err(f"Audio files can be up to {MAX_UPLOAD_MB} MB.", 413)
            out.write(chunk)
    if size == 0:
        os.remove(src)
        return err("The file is empty.")
    t = now()
    get_db().execute("INSERT INTO music (id,campaign_id,title,status,src_ext,src_size,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                     (tid, cid, title, "processing", ext, size, t, t))
    _touch(cid)
    get_db().commit()
    _start_job(tid, src, FORMATS[ext])
    return jsonify({"id": tid, "tracks": tracks(cid)}), 202


def _track_row(tid):
    return get_db().execute("SELECT * FROM music WHERE id=?", (tid,)).fetchone()


@app.route("/api/music/<tid>", methods=["PUT"])
@gamemaster_required
def music_rename(tid):
    r = _track_row(tid)
    if not r:
        return err("Track not found.", 404)
    title = re.sub(r"[\x00-\x1f]", "", str(body().get("title") or "")).strip()[:TITLE_MAX]
    if not title:
        return err("Give the track a name.")
    get_db().execute("UPDATE music SET title=?, updated_at=? WHERE id=?", (title, now(), tid))
    _touch(r["campaign_id"])
    get_db().commit()
    return jsonify({"tracks": tracks(r["campaign_id"]), **_state_out(r["campaign_id"])})


@app.route("/api/music/<tid>", methods=["DELETE"])
@gamemaster_required
def music_delete(tid):
    r = _track_row(tid)
    if not r:
        return err("Track not found.", 404)
    if r["status"] == "processing":
        return err("Wait until it has finished compressing.")
    db = get_db()
    db.execute("DELETE FROM music_state WHERE track_id=?", (tid,))
    db.execute("DELETE FROM music WHERE id=?", (tid,))
    _touch(r["campaign_id"])
    db.commit()
    _remove_files(tid)
    return jsonify({"tracks": tracks(r["campaign_id"]), **_state_out(r["campaign_id"])})


@app.route("/api/games/<cid>/music/play", methods=["POST"])
@gamemaster_required
def music_play(cid):
    """Start a track for everyone (replacing whatever was playing), or with only `loop`, change looping."""
    b = body()
    db = get_db()
    if "track" not in b and "loop" in b:
        db.execute("UPDATE music_state SET loop=? WHERE campaign_id=?", (int(bool(b["loop"])), cid))
    else:
        r = _track_row(str(b.get("track") or ""))
        if not r or r["campaign_id"] != cid:
            return err("Track not found.", 404)
        if r["status"] != "ready":
            return err("That track isn't ready yet.")
        db.execute("INSERT OR REPLACE INTO music_state (campaign_id,track_id,started_at,loop,updated_at) VALUES (?,?,?,?,?)",
                   (cid, r["id"], time.time() + 0.6, int(bool(b.get("loop", True))), now()))   # +0.6 s: everyone starts together
    _touch(cid)
    db.commit()
    return jsonify(_state_out(cid))


@app.route("/api/games/<cid>/music/stop", methods=["POST"])
@gamemaster_required
def music_stop(cid):
    get_db().execute("DELETE FROM music_state WHERE campaign_id=?", (cid,))
    _touch(cid)
    get_db().commit()
    return jsonify(_state_out(cid))


# ---------------------------------------------------------------- everyone
def _viewer_game(cid_hint=None, map_hint=None):
    if session.get("gamemaster"):
        if map_hint:
            r = get_db().execute("SELECT campaign_id FROM maps WHERE id=?", (map_hint,)).fetchone()
            return r["campaign_id"] if r else None
        return cid_hint
    me = current_player_row()
    return me["campaign_id"] if me else None


@app.route("/api/music/now")
@rate_limited("music_now", 240)
def music_now():
    if not session.get("gamemaster") and not current_player_row():
        return jsonify({"error": "Sign in required."}), 401
    cid = _viewer_game(request.args.get("game"), request.args.get("map"))
    out = _state_out(cid) if cid else {"playing": None, "serverNow": time.time()}
    if session.get("gamemaster") and cid:
        out["gameId"] = cid
        out["tracks"] = [{"id": t["id"], "title": t["title"], "duration": t["duration"]} for t in tracks(cid) if t["status"] == "ready"]
    return jsonify(out)


@app.route("/music/<name>")
def music_file(name):
    m = FILE_RE.match(name)
    if not m:
        return err("Not found.", 404)
    r = _track_row(m[1])
    if not r or r["status"] != "ready":
        return err("Not found.", 404)
    if not session.get("gamemaster"):
        me = current_player_row()
        if not me or me["campaign_id"] != r["campaign_id"]:
            return err("Not found.", 404)
    path = os.path.join(MUSIC_DIR, name)
    if not os.path.exists(path):
        return err("Not found.", 404)
    resp = send_file(path, mimetype=MIME[m[2]], conditional=True, download_name=f"{m[1]}.{m[2]}", max_age=86400)
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp

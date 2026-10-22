"""Handouts: notes, dossiers and pictures the GM gives to the runners. Text is Markdown (rendered
safely in the browser, no raw HTML); images are PNG or JPEG only, checked and re-encoded on upload
(which also strips their metadata) and served only to the GM and the runners who were given them."""
import io
import json
import os
import secrets

from flask import jsonify, request, send_file, session
from PIL import Image, UnidentifiedImageError

import aio

from core import (UPLOAD_DIR, app, body, current_player_row, err, get_db, new_id, now, player_required)
from security import gamemaster_required, rate_limited

ALLOWED_EXT = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}
MAX_UPLOAD = 8 * 1024 * 1024
MAX_SIDE = 4000
MAX_PIXELS = 40_000_000
TITLE_MAX, BODY_MAX = 120, 20000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS     # Pillow refuses decompression bombs above this


# ---------------------------------------------------------------- images
def store_image(filename, data):
    """Validate an uploaded image and save a clean re-encoded copy. Returns the stored name."""
    ext = os.path.splitext(str(filename or "").lower())[1]
    if ext not in ALLOWED_EXT:
        raise ValueError("Only .png, .jpg and .jpeg images can be uploaded.")
    if not data:
        raise ValueError("The file is empty.")
    if len(data) > MAX_UPLOAD:
        raise ValueError("Images can be up to 8 MB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            w, h = probe.size
            if w * h > MAX_PIXELS:
                raise ValueError("That image is too large (more than 40 megapixels).")
            probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise ValueError("That file isn't a readable image.")
    if fmt != ALLOWED_EXT[ext]:
        raise ValueError(f"The file is named {ext} but isn't a {ALLOWED_EXT[ext]} image.")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    name = secrets.token_hex(12) + (".jpg" if fmt == "JPEG" else ".png")
    out = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(out, "JPEG", quality=88, optimize=True)
    else:
        if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            img = img.convert("RGBA")
        img.save(out, "PNG", optimize=True)
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(out.getvalue())
    os.chmod(path, 0o600)
    return name


def _valid_name(name):
    return isinstance(name, str) and len(name) == 28 and name[:24].isalnum() and name[24:] in (".png", ".jpg")


def _drop_image_if_unused(name):
    if not _valid_name(name):
        return
    if get_db().execute("SELECT 1 FROM handouts WHERE image=?", (name,)).fetchone():
        return
    try:
        os.remove(os.path.join(UPLOAD_DIR, name))
    except OSError:
        pass


@app.route("/api/games/<cid>/uploads", methods=["POST"])
@gamemaster_required
@rate_limited("upload", 60)
def upload_image(cid):
    if not get_db().execute("SELECT 1 FROM campaigns WHERE id=?", (cid,)).fetchone():
        return err("Game not found.", 404)
    f = request.files.get("file")
    if not f:
        return err("Choose an image.")
    cleanup_orphans()
    try:
        name = aio.offload(store_image, f.filename, f.read(MAX_UPLOAD + 1))
    except ValueError as e:
        return err(str(e))
    return jsonify({"image": name}), 201


@app.route("/uploads/<name>")
def uploaded_image(name):
    if not _valid_name(name) or not os.path.exists(os.path.join(UPLOAD_DIR, name)):
        return err("Not found.", 404)
    if not session.get("gamemaster"):
        me = current_player_row()
        if not me or not any(name == h["image"] for h in visible_handouts(me)):
            return err("Not found.", 404)
    return send_file(os.path.join(UPLOAD_DIR, name), mimetype="image/jpeg" if name.endswith(".jpg") else "image/png",
                     download_name=name, conditional=True)


def cleanup_orphans(max_age=24 * 3600):
    """Remove uploaded images no handout uses (left over from abandoned edits) after a day."""
    used = {r["image"] for r in get_db().execute("SELECT image FROM handouts WHERE image IS NOT NULL").fetchall()}
    for f in os.listdir(UPLOAD_DIR):
        p = os.path.join(UPLOAD_DIR, f)
        if _valid_name(f) and f not in used and now() - os.path.getmtime(p) > max_age:
            try:
                os.remove(p)
            except OSError:
                pass


# ---------------------------------------------------------------- handouts
def _row(r):
    rec = json.loads(r["recipients"] or '"all"')
    return {"id": r["id"], "campaignId": r["campaign_id"], "title": r["title"], "body": r["body"], "image": r["image"],
            "recipients": rec if rec == "all" else [str(x) for x in rec], "shown": bool(r["shown"]),
            "shownAt": r["shown_at"], "createdAt": r["created_at"], "updatedAt": r["updated_at"]}


def game_handouts(cid):
    rows = get_db().execute("SELECT * FROM handouts WHERE campaign_id=? ORDER BY COALESCE(shown_at, created_at) DESC", (cid,)).fetchall()
    return [_row(r) for r in rows]


def visible_handouts(me):
    out = []
    for h in game_handouts(me["campaign_id"]):
        if h["shown"] and (h["recipients"] == "all" or me["id"] in h["recipients"]):
            out.append({k: h[k] for k in ("id", "title", "body", "image", "shownAt", "updatedAt")})
    return out


def _clean(b, cid, old=None):
    old = old or {}
    title = str(b.get("title", old.get("title", "")) or "").strip()[:TITLE_MAX]
    if not title:
        raise ValueError("Give the handout a title.")
    text = str(b.get("body", old.get("body", "")) or "")[:BODY_MAX]
    image = b.get("image", old.get("image"))
    if image in ("", None):
        image = None
    elif not _valid_name(image) or not os.path.exists(os.path.join(UPLOAD_DIR, image)):
        raise ValueError("Upload the image again.")
    rec = b.get("recipients", old.get("recipients", "all"))
    if rec != "all":
        ids = {r["id"] for r in get_db().execute("SELECT id FROM players WHERE campaign_id=?", (cid,)).fetchall()}
        rec = [str(x) for x in (rec or []) if str(x) in ids][:50]
    shown = bool(b.get("shown", old.get("shown", False)))
    return title, text, image, rec, shown


@app.route("/api/games/<cid>/handouts")
@gamemaster_required
def handouts_list(cid):
    return jsonify({"handouts": game_handouts(cid)})


@app.route("/api/games/<cid>/handouts", methods=["POST"])
@gamemaster_required
def handouts_create(cid):
    if not get_db().execute("SELECT 1 FROM campaigns WHERE id=?", (cid,)).fetchone():
        return err("Game not found.", 404)
    try:
        title, text, image, rec, shown = _clean(body(), cid)
    except ValueError as e:
        return err(str(e))
    hid, t = new_id(), now()
    get_db().execute("INSERT INTO handouts (id,campaign_id,title,body,image,recipients,shown,shown_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (hid, cid, title, text, image, json.dumps(rec), int(shown), t if shown else None, t, t))
    get_db().commit()
    return jsonify({"id": hid, "handouts": game_handouts(cid)}), 201


@app.route("/api/handouts/<hid>", methods=["PUT"])
@gamemaster_required
def handouts_update(hid):
    db = get_db()
    r = db.execute("SELECT * FROM handouts WHERE id=?", (hid,)).fetchone()
    if not r:
        return err("Handout not found.", 404)
    old = _row(r)
    try:
        title, text, image, rec, shown = _clean(body(), r["campaign_id"], old)
    except ValueError as e:
        return err(str(e))
    shown_at = r["shown_at"] if shown and old["shown"] else (now() if shown else None)
    db.execute("UPDATE handouts SET title=?, body=?, image=?, recipients=?, shown=?, shown_at=?, updated_at=? WHERE id=?",
               (title, text, image, json.dumps(rec), int(shown), shown_at, now(), hid))
    if old["image"] and old["image"] != image:
        _drop_image_if_unused(old["image"])
    db.commit()
    return jsonify({"handouts": game_handouts(r["campaign_id"])})


@app.route("/api/handouts/<hid>", methods=["DELETE"])
@gamemaster_required
def handouts_delete(hid):
    db = get_db()
    r = db.execute("SELECT * FROM handouts WHERE id=?", (hid,)).fetchone()
    if not r:
        return err("Handout not found.", 404)
    db.execute("DELETE FROM handouts WHERE id=?", (hid,))
    _drop_image_if_unused(r["image"])
    db.execute("UPDATE campaigns SET updated_at=? WHERE id=?", (now(), r["campaign_id"]))
    db.commit()
    return jsonify({"handouts": game_handouts(r["campaign_id"])})


@app.route("/api/me/handouts")
@player_required
def me_handouts(me):
    return jsonify({"handouts": visible_handouts(me)})

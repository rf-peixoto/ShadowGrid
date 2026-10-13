"""Auth, hashcash proof-of-work, rate limiting and hardening helpers."""
import hashlib
import os
import secrets
import threading
import time
from functools import wraps

from flask import abort, jsonify, redirect, request, session, url_for

# ---------- hashcash ----------
LOGIN_POW_BITS = int(os.environ.get("SHADOWGRID_LOGIN_POW_BITS", "13"))
CHALLENGE_TTL = 300

_challenges = {}
_lock = threading.Lock()


def issue_challenge(bits):
    with _lock:
        now = time.time()
        for k in [k for k, v in _challenges.items() if v[0] < now]:
            del _challenges[k]
        if len(_challenges) > 50000:      # memory guard
            _challenges.clear()
        ch = secrets.token_hex(16)
        _challenges[ch] = (now + CHALLENGE_TTL, bits)
    return {"challenge": ch, "bits": bits, "ttl": CHALLENGE_TTL}


def leading_zero_bits(digest):
    n = 0
    for b in digest:
        if b == 0:
            n += 8
            continue
        n += 8 - b.bit_length()
        break
    return n


def verify_pow(challenge, counter, min_bits):
    """One-time verification. Returns True if the proof is valid."""
    if not isinstance(challenge, str) or not isinstance(counter, (str, int)):
        return False
    with _lock:
        entry = _challenges.pop(challenge, None)
    if not entry or entry[0] < time.time() or entry[1] < min_bits:
        return False
    digest = hashlib.sha256(f"{challenge}:{counter}".encode()).digest()
    return leading_zero_bits(digest) >= entry[1]


# ---------- the gate: a hard proof of work before the sign-in page ----------
# Many independent sub-puzzles instead of one big one: the browser can spread them over its cores, the
# progress bar is real, and the solve time varies far less. Expected work = GATE_PUZZLES * 2**GATE_BITS hashes.
GATE_BITS = max(0, min(30, int(os.environ.get("SHADOWGRID_GATE_BITS", "22"))))
GATE_PUZZLES = max(1, min(256, int(os.environ.get("SHADOWGRID_GATE_PUZZLES", "64"))))
GATE_ON = GATE_BITS > 0
GATE_CHALLENGE_TTL = 30 * 60      # a slow phone still finishes in time
GATE_PASS_TTL = 30 * 60           # how long a solved gate keeps the sign-in page open
GATE_MAX_FAILS = 5                # wrong passwords per solved gate

_gate_challenges = {}             # challenge -> (expires, bits, puzzles)
_gate_passes = {}                 # pass id -> [expires, failures]


def issue_gate_challenge():
    with _lock:
        now = time.time()
        for k in [k for k, v in _gate_challenges.items() if v[0] < now]:
            del _gate_challenges[k]
        if len(_gate_challenges) > 20000:
            _gate_challenges.clear()
        ch = secrets.token_hex(16)
        _gate_challenges[ch] = (now + GATE_CHALLENGE_TTL, GATE_BITS, GATE_PUZZLES)
    return {"challenge": ch, "bits": GATE_BITS, "puzzles": GATE_PUZZLES, "ttl": GATE_CHALLENGE_TTL}


def verify_gate(challenge, counters):
    """One-time check of every sub-puzzle: sha256("<challenge>:<i>:<counter>") has `bits` leading zero bits."""
    if not isinstance(challenge, str) or not isinstance(counters, list):
        return False
    with _lock:
        entry = _gate_challenges.pop(challenge, None)
    if not entry or entry[0] < time.time() or len(counters) != entry[2]:
        return False
    for i, c in enumerate(counters):
        c = str(c)
        if not (c.isdigit() and len(c) <= 15):
            return False
        if leading_zero_bits(hashlib.sha256(f"{challenge}:{i}:{c}".encode()).digest()) < entry[1]:
            return False
    return True


def grant_gate_pass():
    """Remember a solved gate in this browser's session (the id is useless without the server's table)."""
    with _lock:
        now = time.time()
        for k in [k for k, v in _gate_passes.items() if v[0] < now]:
            del _gate_passes[k]
        if len(_gate_passes) > 20000:
            _gate_passes.clear()
        gid = secrets.token_urlsafe(18)
        _gate_passes[gid] = [now + GATE_PASS_TTL, 0]
    session["gate"] = gid


def gate_ok():
    """True when this browser may see the sign-in pages: the gate is off, it is signed in, or it solved the gate."""
    if not GATE_ON or session.get("gamemaster") or session.get("pid"):
        return True
    gid = session.get("gate")
    with _lock:
        entry = _gate_passes.get(gid) if isinstance(gid, str) else None
        return bool(entry and entry[0] > time.time() and entry[1] < GATE_MAX_FAILS)


def gate_fail():
    """A wrong password: after GATE_MAX_FAILS the browser has to solve the gate again."""
    gid = session.get("gate")
    with _lock:
        entry = _gate_passes.get(gid) if isinstance(gid, str) else None
        if entry:
            entry[1] += 1
            if entry[1] >= GATE_MAX_FAILS:
                _gate_passes.pop(gid, None)


def gate_consume():
    """A successful sign-in or sign-up uses up the pass; the next sign-in solves the gate again."""
    gid = session.get("gate")
    with _lock:
        _gate_passes.pop(gid, None) if isinstance(gid, str) else None


def gate_refused():
    resp = jsonify({"error": "Your connection check expired. Run it again.", "gate": True})
    resp.status_code = 403
    return resp


# ---------- rate limiting (token bucket, in memory) ----------
_buckets = {}
TRUST_PROXY = os.environ.get("SHADOWGRID_TRUST_PROXY") == "1"


def client_ip():
    if TRUST_PROXY:
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr or "?"


def rate_limited(name, per_minute, burst=None):
    """Decorator: per-IP token bucket. Returns 429 when exhausted."""
    burst = burst or per_minute
    rate = per_minute / 60.0

    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            # per signed-in player when there is one (a whole table often shares one IP at home)
            key = (name, client_ip(), session.get("pid") or ("gm" if session.get("gamemaster") else ""))
            now = time.time()
            with _lock:
                tokens, last = _buckets.get(key, (burst, now))
                tokens = min(burst, tokens + (now - last) * rate)
                if tokens < 1:
                    _buckets[key] = (tokens, now)
                    resp = jsonify({"error": "Too many requests. Slow down."})
                    resp.status_code = 429
                    resp.headers["Retry-After"] = "10"
                    return resp
                _buckets[key] = (tokens - 1, now)
                if len(_buckets) > 100000:
                    _buckets.clear()
            return fn(*a, **kw)
        return wrapper
    return deco


# ---------- auth ----------
def csrf_ok():
    """Cheap CSRF guard: browsers can't add this header cross-site without CORS."""
    return request.method not in ("POST", "PUT", "DELETE", "PATCH") or request.headers.get("X-Requested-With") == "ShadowGrid"


def gamemaster_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("gamemaster"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Sign in required."}), 401
            if session.get("pid"):
                return redirect(url_for("play"))
            return redirect(url_for("login", next=request.path))
        if not csrf_ok():
            abort(403)
        return fn(*a, **kw)
    return wrapper


# ---------- hardening headers ----------
SECURITY_HEADERS = {
    "Server": os.environ.get("SHADOWGRID_SERVER_IDENT", "nginx"),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",     # the app frames its own screens (shell.html), nobody else may
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; "
        "frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
    ),
}


def apply_security_headers(resp):
    for k, v in SECURITY_HEADERS.items():
        resp.headers[k] = v
    if os.environ.get("SHADOWGRID_HTTPS") != "1" and request.host.split(":")[0] not in ("localhost", "127.0.0.1", "[::1]"):
        # plain HTTP on a LAN address: browsers ignore this header there and log a warning on every page
        resp.headers.pop("Cross-Origin-Opener-Policy", None)
    if request.path.startswith("/uploads/"):
        # uploaded images: never run as a document, cached privately for an hour
        resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        resp.headers["Cache-Control"] = "private, max-age=3600"
    elif not request.path.startswith("/static/") and "Cache-Control" not in resp.headers:
        resp.headers["Cache-Control"] = "no-store"
    resp.headers.pop("X-Powered-By", None)
    return resp

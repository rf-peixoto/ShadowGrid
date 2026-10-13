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
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
}


def apply_security_headers(resp):
    for k, v in SECURITY_HEADERS.items():
        resp.headers[k] = v
    if request.path.startswith("/uploads/"):
        # uploaded images: never run as a document, cached privately for an hour
        resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        resp.headers["Cache-Control"] = "private, max-age=3600"
    elif not request.path.startswith("/static/") and "Cache-Control" not in resp.headers:
        resp.headers["Cache-Control"] = "no-store"
    resp.headers.pop("X-Powered-By", None)
    return resp

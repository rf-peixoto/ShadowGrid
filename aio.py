"""Server mode. With gevent installed, ShadowGrid serves every connection from one cooperative event loop:
an open live-update stream costs a greenlet (a few kB) instead of a thread, so hundreds of open pages are
fine. Without gevent (or with SHADOWGRID_SERVER=waitress) it falls back to waitress and its thread pool.

patch() must run before anything else is imported (serve.py and app.py call it first).
offload() runs CPU-heavy work (password hashes, image resizing) on a worker thread, so one sign-in does
not stall every other request while it hashes. Never call it inside an open write transaction."""
import os

MODE = "waitress"


def patch():
    global MODE
    if os.environ.get("SHADOWGRID_SERVER", "gevent").strip().lower() != "gevent":
        return MODE
    try:
        from gevent import monkey
    except ImportError:
        return MODE
    monkey.patch_all()
    MODE = "gevent"
    return MODE


def offload(fn, *args, **kwargs):
    if MODE == "gevent":
        import gevent
        return gevent.get_hub().threadpool.apply(fn, args, kwargs)
    return fn(*args, **kwargs)

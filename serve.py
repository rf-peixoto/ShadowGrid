"""ShadowGrid production server (waitress). Started by serve.sh, which sets the environment:

    SHADOWGRID_HOST / SHADOWGRID_PORT    where to listen (127.0.0.1:8000 behind nginx)
    SHADOWGRID_HTTPS=1                   secure cookies (only behind HTTPS)
    SHADOWGRID_TRUST_PROXY=1             trust X-Forwarded-For from the local nginx
"""
import os

from waitress import serve

from app import app, init_db

if __name__ == "__main__":
    init_db()
    # live updates keep one connection (and one thread) open per browser tab
    serve(app, host=os.environ.get("SHADOWGRID_HOST", "127.0.0.1"), port=int(os.environ.get("SHADOWGRID_PORT", "8000")),
          ident=os.environ.get("SHADOWGRID_SERVER_IDENT", "nginx"), threads=int(os.environ.get("SHADOWGRID_THREADS", "64")),
          connection_limit=int(os.environ.get("SHADOWGRID_CONNECTIONS", "200")), channel_timeout=120,
          max_request_body_size=600 * 1024 * 1024)

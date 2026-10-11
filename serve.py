"""ShadowGrid production entry point: waitress with a neutral Server header.

    GRIDMAP_HTTPS=1 GRIDMAP_TRUST_PROXY=1 python serve.py

Put nginx/caddy with TLS in front and forward to 127.0.0.1:8000.
"""
import os
from waitress import serve
from app import app, init_db

if __name__ == "__main__":
    init_db()
    serve(app, host=os.environ.get("GRIDMAP_HOST", "127.0.0.1"), port=int(os.environ.get("GRIDMAP_PORT", "8000")),
          ident=os.environ.get("GRIDMAP_SERVER_IDENT", "nginx"), threads=8)

"""ShadowGrid production server (waitress). Started by serve.sh, which sets the environment:

    SHADOWGRID_HOST / SHADOWGRID_PORT    where to listen (127.0.0.1:8000 behind nginx)
    SHADOWGRID_HTTPS=1                   secure cookies (only behind HTTPS)
    SHADOWGRID_TRUST_PROXY=1             trust X-Forwarded-For from the local nginx
    SHADOWGRID_THREADS / SHADOWGRID_CONNECTIONS   thread pool and connection limit (64 / 200)
"""
from app import init_db
from core import run_server
from game import catalog_blob

if __name__ == "__main__":
    init_db()
    catalog_blob()          # build the catalog now rather than on the first page load
    run_server(8000)

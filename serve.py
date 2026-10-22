"""ShadowGrid production server (gevent, or waitress without it). Started by serve.sh, which sets the environment:

    SHADOWGRID_HOST / SHADOWGRID_PORT    where to listen (127.0.0.1:8000 behind nginx)
    SHADOWGRID_HTTPS=1                   secure cookies (only behind HTTPS)
    SHADOWGRID_TRUST_PROXY=1             trust X-Forwarded-For from the local nginx
    SHADOWGRID_SERVER=waitress           use waitress and a thread pool even if gevent is installed
    SHADOWGRID_CONNECTIONS               open connections at once (gevent 1000; waitress 200)
    SHADOWGRID_THREADS                   waitress thread pool (64)
"""
import aio

aio.patch()     # first: makes sockets, locks and sleeps cooperative under gevent

from app import init_db  # noqa: E402
from core import run_server  # noqa: E402
from game import catalog_blob  # noqa: E402

if __name__ == "__main__":
    init_db()
    catalog_blob()          # build the catalog now rather than on the first page load
    run_server(8000)

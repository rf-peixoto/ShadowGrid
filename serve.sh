#!/usr/bin/env bash
# Run ShadowGrid for players on the internet.
#
# With nginx (set up by ./install.sh): listens on 127.0.0.1 only, and nginx
# (expected to be running already) adds HTTPS, rate limits and filtering.
# Without nginx: listens on every interface over plain HTTP. Not recommended:
# passwords then cross the internet unencrypted.
#
# If install.sh set up the background service, use systemctl instead:
#   sudo systemctl restart shadowgrid
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
[ -x .venv/bin/python ] || { echo "ShadowGrid isn't installed yet. Run ./install.sh first." >&2; exit 1; }
if [ -f shadowgrid.env ]; then set -a; # shellcheck disable=SC1091
    . ./shadowgrid.env; set +a; fi
case "${1:-}" in -h|--help) sed -n '2,10p' "$0"; exit 0 ;; esac

export SHADOWGRID_DATA="${SHADOWGRID_DATA:-$ROOT/data}"
export SHADOWGRID_PORT="${SHADOWGRID_PORT:-8000}"

# started by hand while the service already runs? Don't start a second copy.
if [ -z "${INVOCATION_ID:-}" ] && [ "${SHADOWGRID_SERVICE:-0}" = 1 ] && command -v systemctl >/dev/null 2>&1 \
        && systemctl is-active --quiet shadowgrid 2>/dev/null; then
    echo "ShadowGrid already runs as a service. Use: sudo systemctl restart shadowgrid  (logs: journalctl -u shadowgrid -f)"
    exit 0
fi

if [ "${SHADOWGRID_NGINX:-0}" = 1 ]; then
    export SHADOWGRID_HOST=127.0.0.1 SHADOWGRID_HTTPS=1 SHADOWGRID_TRUST_PROXY=1
    if ! pgrep -x nginx >/dev/null 2>&1; then
        echo "Warning: nginx doesn't seem to be running, so players can't reach ShadowGrid." >&2
        echo "         Start it with: sudo systemctl start nginx  (or: sudo nginx)" >&2
    fi
    echo "ShadowGrid behind nginx: https://${SHADOWGRID_DOMAIN:-${SHADOWGRID_ADDRESS:-<this server>}}  (app on 127.0.0.1:$SHADOWGRID_PORT)"
else
    export SHADOWGRID_HOST="${SHADOWGRID_HOST:-0.0.0.0}" SHADOWGRID_HTTPS=0 SHADOWGRID_TRUST_PROXY=0
    echo "Warning: serving plain HTTP on port $SHADOWGRID_PORT without nginx. Run ./install.sh and" >&2
    echo "         choose nginx to add HTTPS before playing over the internet." >&2
fi
exec .venv/bin/python serve.py

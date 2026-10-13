#!/usr/bin/env bash
# Run ShadowGrid for a table on your home network (same as `python app.py`,
# but reachable from the other computers and phones on the network).
#
#   ./local.sh              port 5000 (or SHADOWGRID_LOCAL_PORT from shadowgrid.env)
#   ./local.sh 8080         another port
#   ./local.sh --only-me    only this computer can connect
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
[ -x .venv/bin/python ] || { echo "ShadowGrid isn't installed yet. Run ./install.sh first." >&2; exit 1; }
if [ -f shadowgrid.env ]; then set -a; # shellcheck disable=SC1091
    . ./shadowgrid.env; set +a; fi

HOST=0.0.0.0
PORT="${SHADOWGRID_LOCAL_PORT:-5000}"
for arg in "$@"; do
    case "$arg" in
        --only-me) HOST=127.0.0.1 ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
        *) if [[ "$arg" =~ ^[0-9]+$ ]]; then PORT="$arg"; else echo "Unknown option: $arg" >&2; exit 1; fi ;;
    esac
done

export SHADOWGRID_DATA="${SHADOWGRID_DATA:-$ROOT/data}"
export SHADOWGRID_HOST="$HOST" SHADOWGRID_PORT="$PORT"
export SHADOWGRID_HTTPS=0 SHADOWGRID_TRUST_PROXY=0

echo "ShadowGrid (home network mode)"
echo "  On this computer:  http://127.0.0.1:$PORT"
if [ "$HOST" = 0.0.0.0 ]; then
    for ip in $(hostname -I 2>/dev/null || ip -4 -o addr show scope global 2>/dev/null | awk '{sub(/\/.*/,"",$4); print $4}'); do
        case "$ip" in *:*) ;; *) echo "  For your players:  http://$ip:$PORT" ;; esac
    done
    echo "  Not encrypted: use it on a network you trust. For the internet, use ./serve.sh."
fi
echo "  Stop with Ctrl+C."
exec .venv/bin/python app.py

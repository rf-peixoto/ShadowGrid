#!/usr/bin/env bash
# ShadowGrid installer.
#
#   ./install.sh
#
# 1. Creates a Python virtual environment in .venv and installs the dependencies.
# 2. Lets you set the gamemaster password.
# 3. Optionally installs and hardens nginx with HTTPS (Let's Encrypt for a domain,
#    or a self-signed certificate), opens the firewall, and installs a sandboxed
#    systemd service that starts ShadowGrid on boot.
#
# Safe to run again: it updates the dependencies and rewrites the nginx and
# service configuration from your answers.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
ENV_FILE="$ROOT/shadowgrid.env"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
DATA_DIR="$ROOT/data"
NGINX_SITE_NAME="shadowgrid"
ACME_ROOT="/var/www/shadowgrid-acme"
SELF_SSL_DIR="/etc/nginx/shadowgrid-ssl"
SERVICE_FILE="/etc/systemd/system/shadowgrid.service"
MIN_PY="3.9"

# ------------------------------------------------------------------ output helpers
if [ -t 1 ]; then B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; N=$'\e[0m'; else B=; G=; Y=; R=; N=; fi
say()  { printf '%s\n' "${B}==>${N} $*"; }
ok()   { printf '%s\n' "${G}  ✓${N} $*"; }
warn() { printf '%s\n' "${Y}  !${N} $*" >&2; }
die()  { printf '%s\n' "${R}  ✗ $*${N}" >&2; exit 1; }
trap 'die "Something failed on line $LINENO. Nothing after that point was changed."' ERR

# read answers from the terminal even when stdin is a pipe
TTY=/dev/tty
[ -r "$TTY" ] || TTY=/dev/stdin

ask_yes_no() {  # ask_yes_no "Question" default(y|n)
    local q="$1" def="${2:-n}" a hint="[y/N]"
    [ "$def" = y ] && hint="[Y/n]"
    while true; do
        read -r -p "    $q $hint " a <"$TTY" || a=""
        a="${a:-$def}"
        case "${a,,}" in y|yes) return 0 ;; n|no) return 1 ;; esac
        echo "    Please answer y or n."
    done
}

ask_value() {  # ask_value "Question" default -> echoes the answer
    local q="$1" def="${2:-}" a
    if [ -n "$def" ]; then read -r -p "    $q [$def] " a <"$TTY" || a=""; else read -r -p "    $q " a <"$TTY" || a=""; fi
    printf '%s' "${a:-$def}"
}

# ------------------------------------------------------------------ privileges
SUDO=""
need_root() {
    if [ "$(id -u)" -eq 0 ]; then SUDO=""; return; fi
    command -v sudo >/dev/null 2>&1 || die "This step needs root. Install sudo or run ./install.sh as root."
    SUDO="sudo"
    $SUDO -v || die "sudo was refused."
}

# ------------------------------------------------------------------ package manager
PM=""
detect_pm() {
    for p in apt-get dnf yum zypper pacman apk; do
        if command -v "$p" >/dev/null 2>&1; then PM="$p"; return; fi
    done
    PM=""
}

pkg_install() {  # pkg_install name... (distro-neutral names, mapped below)
    detect_pm
    [ -n "$PM" ] || die "No supported package manager found (apt, dnf, yum, zypper, pacman, apk). Install these yourself: $*"
    need_root
    local pkgs=() n
    for n in "$@"; do
        case "$PM:$n" in
            apt-get:python)  pkgs+=(python3 python3-venv python3-pip) ;;
            dnf:python|yum:python|zypper:python) pkgs+=(python3 python3-pip) ;;
            pacman:python)   pkgs+=(python python-pip) ;;
            apk:python)      pkgs+=(python3 py3-pip) ;;
            *:openssl)       pkgs+=(openssl) ;;
            *:nginx)         pkgs+=(nginx) ;;
            *:certbot)       pkgs+=(certbot) ;;
            dnf:ffmpeg|yum:ffmpeg) pkgs+=(ffmpeg-free) ;;
            *)               pkgs+=("$n") ;;
        esac
    done
    say "Installing ${pkgs[*]} with $PM"
    case "$PM" in
        apt-get) $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -q && $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -q "${pkgs[@]}" ;;
        dnf)     $SUDO dnf install -y "${pkgs[@]}" ;;
        yum)     $SUDO yum install -y "${pkgs[@]}" ;;
        zypper)  $SUDO zypper --non-interactive install "${pkgs[@]}" ;;
        pacman)  $SUDO pacman -S --needed --noconfirm "${pkgs[@]}" ;;
        apk)     $SUDO apk add --no-cache "${pkgs[@]}" ;;
    esac
}

version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]; }

# ------------------------------------------------------------------ settings file
# Previous answers are kept in shadowgrid.env (mode 600) and offered as defaults.
SHADOWGRID_NGINX=0
SHADOWGRID_DOMAIN=""
SHADOWGRID_PORT=8000
SHADOWGRID_LOCAL_PORT=5000
SHADOWGRID_SERVICE=0
SHADOWGRID_ADDRESS=""
# tuning (edit shadowgrid.env; install.sh keeps your values)
SHADOWGRID_GATE_BITS=22            # connection check before sign-in: 2^bits hashes per sector (0 turns it off)
SHADOWGRID_GATE_PUZZLES=64         # sectors per check
SHADOWGRID_SESSION_HOURS=12        # a sign-in lasts this long after the last activity (at least 4)
SHADOWGRID_SESSION_MAX_HOURS=24    # and never longer than this after signing in
SHADOWGRID_MUSIC_KBPS=48           # Opus bitrate music is compressed to
SHADOWGRID_MUSIC_MAX_MB=100        # largest audio upload
SHADOWGRID_MUSIC_TOTAL_MB=2048     # music library limit
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
fi

write_env() {
    umask 077
    cat >"$ENV_FILE" <<EOF
# ShadowGrid settings, written by install.sh. Read by local.sh and serve.sh.
SHADOWGRID_DATA='$DATA_DIR'
SHADOWGRID_LOCAL_PORT='$SHADOWGRID_LOCAL_PORT'
SHADOWGRID_PORT='$SHADOWGRID_PORT'
SHADOWGRID_NGINX='$SHADOWGRID_NGINX'
SHADOWGRID_DOMAIN='$SHADOWGRID_DOMAIN'
SHADOWGRID_SERVICE='$SHADOWGRID_SERVICE'
SHADOWGRID_ADDRESS='$SHADOWGRID_ADDRESS'

# Tuning. Restart ShadowGrid after changing these.
# Connection check before the sign-in page: each check solves GATE_PUZZLES sectors of 2^GATE_BITS
# hashes (22 and 64: roughly 15-30 s on a laptop, about a minute on a phone). 0 bits turns it off.
SHADOWGRID_GATE_BITS='$SHADOWGRID_GATE_BITS'
SHADOWGRID_GATE_PUZZLES='$SHADOWGRID_GATE_PUZZLES'
# A sign-in lasts SESSION_HOURS after the last activity (at least 4) and at most SESSION_MAX_HOURS.
SHADOWGRID_SESSION_HOURS='$SHADOWGRID_SESSION_HOURS'
SHADOWGRID_SESSION_MAX_HOURS='$SHADOWGRID_SESSION_MAX_HOURS'
# Music: Opus bitrate, largest upload and library size in MB.
SHADOWGRID_MUSIC_KBPS='$SHADOWGRID_MUSIC_KBPS'
SHADOWGRID_MUSIC_MAX_MB='$SHADOWGRID_MUSIC_MAX_MB'
SHADOWGRID_MUSIC_TOTAL_MB='$SHADOWGRID_MUSIC_TOTAL_MB'
EOF
    chmod 600 "$ENV_FILE"
}

# ================================================================== 1. Python
find_python() {
    local c
    for c in python3 python3.13 python3.12 python3.11 python3.10 python3.9 python; do
        if command -v "$c" >/dev/null 2>&1; then
            local v
            v="$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo 0)"
            if version_ge "$v" "$MIN_PY"; then command -v "$c"; return 0; fi
        fi
    done
    return 1
}

say "ShadowGrid installer ($ROOT)"
SYS_PY="$(find_python || true)"
if [ -z "$SYS_PY" ]; then
    warn "Python $MIN_PY or newer was not found."
    if ask_yes_no "Install Python with the system package manager?" y; then
        pkg_install python
        SYS_PY="$(find_python || true)"
    fi
    [ -n "$SYS_PY" ] || die "Python $MIN_PY+ is required."
fi
ok "Python: $SYS_PY ($("$SYS_PY" -V 2>&1))"

# ================================================================== 2. virtual environment
if [ ! -x "$PY" ]; then
    say "Creating the virtual environment in .venv"
    if ! "$SYS_PY" -m venv "$VENV" 2>/dev/null; then
        rm -rf "$VENV"
        warn "Python's venv module is missing (Debian and Ubuntu ship it separately)."
        ask_yes_no "Install it with the system package manager?" y || die "Install python3-venv and run ./install.sh again."
        pkg_install python
        "$SYS_PY" -m venv "$VENV" || die "Could not create the virtual environment."
    fi
fi
say "Installing dependencies"
"$PY" -m pip install --quiet --disable-pip-version-check --upgrade pip
"$PY" -m pip install --quiet --disable-pip-version-check -r "$ROOT/requirements.txt"
ok "Dependencies installed in .venv"

# music needs ffmpeg with the Opus encoder: the imageio-ffmpeg package ships one for most systems
has_ffmpeg() {
    "$PY" - <<'PYEOF'
import shutil, subprocess, sys
cands = []
try:
    import imageio_ffmpeg
    cands.append(imageio_ffmpeg.get_ffmpeg_exe())
except Exception:
    pass
cands.append(shutil.which("ffmpeg"))
for c in cands:
    try:
        if c and "libopus" in subprocess.run([c, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20).stdout:
            sys.exit(0)
    except Exception:
        pass
sys.exit(1)
PYEOF
}
if has_ffmpeg; then
    ok "ffmpeg with Opus found (music uploads work)"
else
    warn "No ffmpeg with Opus support was found; the gamemaster can't upload music without it."
    if ask_yes_no "Install ffmpeg with the system package manager?" y; then
        pkg_install ffmpeg || true
    fi
    has_ffmpeg && ok "ffmpeg installed" || warn "Still no ffmpeg with Opus. Everything else works; install ffmpeg later and restart ShadowGrid."
fi

mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"
chmod +x "$ROOT/local.sh" "$ROOT/serve.sh" 2>/dev/null || true

# ================================================================== 3. gamemaster password
say "Gamemaster account (username: gamemaster)"
if SHADOWGRID_DATA="$DATA_DIR" "$PY" "$ROOT/app.py" has-password; then
    if ask_yes_no "A gamemaster password is already set. Change it?" n; then
        SHADOWGRID_DATA="$DATA_DIR" "$PY" "$ROOT/app.py" set-password
    fi
else
    echo "    Choose the password you will sign in with (at least 8 characters)."
    until SHADOWGRID_DATA="$DATA_DIR" "$PY" "$ROOT/app.py" set-password; do echo "    Try again."; done
fi
ok "Gamemaster password set"

# ================================================================== 4. nginx (optional)
echo
say "Internet play"
echo "    To play over the internet, ShadowGrid runs behind nginx, which adds HTTPS,"
echo "    rate limits and request filtering. For games on your home network only,"
echo "    answer no and use ./local.sh."
DEF=n; [ "$SHADOWGRID_NGINX" = 1 ] && DEF=y
if ! ask_yes_no "Install and configure nginx for internet play?" "$DEF"; then
    SHADOWGRID_NGINX=0
    write_env
    echo
    ok "Done."
    echo "    Home network:  ./local.sh"
    echo "    Internet without nginx (no HTTPS, not recommended):  ./serve.sh"
    exit 0
fi

need_root
SHADOWGRID_NGINX=1
command -v nginx >/dev/null 2>&1 || pkg_install nginx
command -v openssl >/dev/null 2>&1 || pkg_install openssl
NGINX_VER="$(nginx -v 2>&1 | sed -nE 's|.*nginx/([0-9.]+).*|\1|p')"
NGINX_VER="${NGINX_VER:-1.18.0}"
ok "nginx $NGINX_VER"

echo
echo "    With a domain name that points to this server (for example game.example.com),"
echo "    you get a free trusted certificate from Let's Encrypt. Without one, a"
echo "    self-signed certificate is used and browsers show a warning the first time."
SHADOWGRID_DOMAIN="$(ask_value "Domain name (leave empty for none):" "$SHADOWGRID_DOMAIN")"
SHADOWGRID_DOMAIN="${SHADOWGRID_DOMAIN,,}"
if [ -n "$SHADOWGRID_DOMAIN" ] && ! [[ "$SHADOWGRID_DOMAIN" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$ ]]; then
    die "\"$SHADOWGRID_DOMAIN\" is not a valid domain name."
fi
SHADOWGRID_PORT="$(ask_value "Internal port for ShadowGrid (only nginx talks to it):" "$SHADOWGRID_PORT")"
if ! { [[ "$SHADOWGRID_PORT" =~ ^[0-9]+$ ]] && [ "$SHADOWGRID_PORT" -ge 1024 ] && [ "$SHADOWGRID_PORT" -le 65535 ]; }; then
    die "Use a port between 1024 and 65535."
fi

# ---------- where nginx reads site files
NGINX_CONF="$(nginx -V 2>&1 | sed -nE 's/.*--conf-path=([^ ]+).*/\1/p')"
NGINX_CONF="${NGINX_CONF:-/etc/nginx/nginx.conf}"
NGINX_DIR="$(dirname "$NGINX_CONF")"
if grep -Eq '^\s*include\s+[^;]*conf\.d/\*\.conf' "$NGINX_CONF"; then SITE_DIR="$NGINX_DIR/conf.d"
elif grep -Eq '^\s*include\s+[^;]*http\.d/\*\.conf' "$NGINX_CONF"; then SITE_DIR="$NGINX_DIR/http.d"
else
    SITE_DIR="$NGINX_DIR/conf.d"
    warn "nginx.conf doesn't include conf.d; adding the include to its http block."
    $SUDO cp -n "$NGINX_CONF" "$NGINX_CONF.before-shadowgrid"
    $SUDO sed -i -E "0,/^\s*http\s*\{/s||&\n    include $SITE_DIR/*.conf;|" "$NGINX_CONF"
fi
$SUDO mkdir -p "$SITE_DIR"
SITE_FILE="$SITE_DIR/$NGINX_SITE_NAME.conf"

# other default_server blocks would clash with ours (Debian's "default" site, Alpine's default.conf...)
disable_other_defaults() {
    local f
    for f in "$NGINX_DIR"/sites-enabled/* "$SITE_DIR"/*.conf; do
        [ -e "$f" ] || continue
        [ "$(readlink -f "$f")" = "$(readlink -f "$SITE_FILE")" ] && continue
        if grep -Eq 'listen[^;]*default_server' "$f"; then
            # moved out of the included folders, so nginx no longer loads it
            $SUDO mkdir -p "$NGINX_DIR/disabled-by-shadowgrid"
            warn "Disabling $f (it claims the default server). Moved to $NGINX_DIR/disabled-by-shadowgrid/"
            $SUDO mv "$f" "$NGINX_DIR/disabled-by-shadowgrid/$(basename "$f")"
        fi
    done
}

nginx_reload() {
    $SUDO nginx -t -q || die "The nginx configuration test failed; see the message above."
    if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
        $SUDO systemctl enable nginx >/dev/null 2>&1 || true
        if $SUDO systemctl is-active --quiet nginx; then $SUDO systemctl reload nginx; else $SUDO systemctl start nginx; fi
    elif command -v rc-service >/dev/null 2>&1; then
        $SUDO rc-update add nginx default >/dev/null 2>&1 || true
        $SUDO rc-service nginx reload 2>/dev/null || $SUDO rc-service nginx start
    elif pgrep -x nginx >/dev/null 2>&1; then $SUDO nginx -s reload
    else $SUDO nginx
    fi
}

# ---------- shared http-level settings (zones are named so they never clash with other sites)
HTTP2_LISTEN=" http2"; HTTP2_DIRECTIVE=""
if version_ge "$NGINX_VER" "1.25.1"; then HTTP2_LISTEN=""; HTTP2_DIRECTIVE="    http2 on;"; fi
REJECT_TLS=0; version_ge "$NGINX_VER" "1.19.4" && REJECT_TLS=1
# IPv6 listeners only where the machine has IPv6 (nginx refuses to start otherwise)
L6=""; [ -s /proc/net/if_inet6 ] && L6=1
listen6() { [ -n "$L6" ] && echo "    listen [::]:$1;"; return 0; }

write_site() {  # write_site <cert> <key>   (empty cert = HTTP-only, for the Let's Encrypt challenge)
    local cert="$1" key="$2" name="${SHADOWGRID_DOMAIN:-_}" tmp
    tmp="$(mktemp)"
    {
        cat <<EOF
# ShadowGrid, written by install.sh. Run ./install.sh again to regenerate it.
limit_req_zone \$binary_remote_addr zone=shadowgrid_req:10m rate=20r/s;
limit_req_zone \$binary_remote_addr zone=shadowgrid_auth:10m rate=30r/m;
limit_conn_zone \$binary_remote_addr zone=shadowgrid_conn:10m;

upstream shadowgrid_app {
    server 127.0.0.1:$SHADOWGRID_PORT;
    keepalive 16;
}

# Anything that doesn't ask for this site by name is dropped without a reply.
server {
    listen 80 default_server;
$(listen6 "80 default_server")
    server_name _;
    server_tokens off;
EOF
        if [ -n "$SHADOWGRID_DOMAIN" ]; then
            cat <<EOF
    location ^~ /.well-known/acme-challenge/ { root $ACME_ROOT; default_type text/plain; }
EOF
        fi
        if [ -n "$cert" ]; then
            if [ -n "$SHADOWGRID_DOMAIN" ]; then
                cat <<EOF
    location / { if (\$host = $SHADOWGRID_DOMAIN) { return 301 https://\$host\$request_uri; } return 444; }
}
EOF
            else
                cat <<EOF
    location / { return 301 https://\$host\$request_uri; }
}
EOF
            fi
        else
            echo "    location / { return 444; }"
            echo "}"
        fi
        [ -n "$cert" ] || return 0
        if [ "$REJECT_TLS" = 1 ] && [ -n "$SHADOWGRID_DOMAIN" ]; then
            cat <<EOF

server {
    listen 443 ssl default_server;
$(listen6 "443 ssl default_server")
    server_name _;
    server_tokens off;
    ssl_reject_handshake on;
}
EOF
        fi
        cat <<EOF

server {
    listen 443 ssl$HTTP2_LISTEN;
$(listen6 "443 ssl$HTTP2_LISTEN")
$HTTP2_DIRECTIVE
    server_name $name;
    server_tokens off;

    # TLS: modern protocols and forward-secret AEAD ciphers only
    ssl_certificate     $cert;
    ssl_certificate_key $key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers off;
    ssl_ecdh_curve X25519:prime256v1:secp384r1;
    ssl_session_cache shared:shadowgrid_ssl:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    add_header Strict-Transport-Security "max-age=63072000" always;

    # slow or oversized requests are cut off early
    client_max_body_size 10m;
    client_body_buffer_size 64k;
    client_header_buffer_size 2k;
    large_client_header_buffers 4 8k;
    client_body_timeout 15s;
    client_header_timeout 15s;
    send_timeout 30s;
    keepalive_timeout 30s;
    keepalive_requests 1000;
    limit_conn shadowgrid_conn 40;
    limit_req_status 429;
    limit_conn_status 429;

    # only the methods the app uses
    if (\$request_method !~ ^(GET|HEAD|POST|PUT|DELETE)\$) { return 405; }

    # no hidden files, no probes for other platforms
    location ~ /\.(?!well-known/) { return 404; }
    location ~* \.(php|asp|aspx|jsp|cgi|env|git|svn|bak|sql|ini|log)\$ { return 404; }

    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-For \$remote_addr;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_hide_header X-Powered-By;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    proxy_send_timeout 60s;

    # sign-in and invite forms: few attempts per minute per address
    location ~ ^/api/(login|invite/) {
        limit_req zone=shadowgrid_auth burst=24 nodelay;
        proxy_pass http://shadowgrid_app;
    }

    # live updates: a long-lived stream that must not be buffered
    location = /api/events {
        limit_req zone=shadowgrid_req burst=20 nodelay;
        proxy_pass http://shadowgrid_app;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
    }

    # backup restore is the largest upload (gamemaster only)
    location = /api/backup/restore {
        limit_req zone=shadowgrid_auth burst=5 nodelay;
        client_max_body_size 2048m;
        client_body_timeout 120s;
        proxy_request_buffering on;
        proxy_read_timeout 300s;
        proxy_pass http://shadowgrid_app;
    }

    # music uploads (gamemaster only; compressed on the server afterwards)
    location ~ ^/api/games/[A-Za-z0-9]+/music\$ {
        limit_req zone=shadowgrid_req burst=20 nodelay;
        client_max_body_size 110m;
        client_body_timeout 300s;
        proxy_request_buffering on;
        proxy_read_timeout 300s;
        proxy_pass http://shadowgrid_app;
    }

    # music streams: range requests straight through, no buffering
    location /music/ {
        limit_req zone=shadowgrid_req burst=60 nodelay;
        proxy_pass http://shadowgrid_app;
        proxy_buffering off;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
    }

    # versioned scripts and styles: ShadowGrid marks them cacheable for a year (and compresses them)
    location /static/ {
        limit_req zone=shadowgrid_req burst=200 nodelay;
        proxy_pass http://shadowgrid_app;
    }

    location / {
        limit_req zone=shadowgrid_req burst=60 nodelay;
        proxy_pass http://shadowgrid_app;
    }
}
EOF
    } >"$tmp"
    $SUDO install -m 644 "$tmp" "$SITE_FILE"
    rm -f "$tmp"
}

# ---------- certificate
if [ -n "$SHADOWGRID_DOMAIN" ]; then
    LE_DIR="/etc/letsencrypt/live/$SHADOWGRID_DOMAIN"
    CERT="$LE_DIR/fullchain.pem"; KEY="$LE_DIR/privkey.pem"
    if ! $SUDO test -s "$CERT"; then
        CERTBOT="$(command -v certbot || true)"
        if [ -z "$CERTBOT" ]; then
            pkg_install certbot || true
            CERTBOT="$(command -v certbot || true)"
        fi
        if [ -z "$CERTBOT" ]; then
            warn "No certbot package for this system; installing it in its own environment (/opt/shadowgrid-certbot)."
            $SUDO "$SYS_PY" -m venv /opt/shadowgrid-certbot
            $SUDO /opt/shadowgrid-certbot/bin/pip install --quiet --disable-pip-version-check certbot
            CERTBOT=/opt/shadowgrid-certbot/bin/certbot
            $SUDO ln -sf "$CERTBOT" /usr/local/bin/certbot
            CERTBOT_RENEW_JOB=1
        fi
        EMAIL="$(ask_value "Email for certificate expiry notices (optional):" "")"
        $SUDO mkdir -p "$ACME_ROOT/.well-known/acme-challenge"
        disable_other_defaults
        write_site "" ""
        nginx_reload
        say "Requesting a Let's Encrypt certificate for $SHADOWGRID_DOMAIN"
        EMAIL_ARGS=(--register-unsafely-without-email)
        [ -n "$EMAIL" ] && EMAIL_ARGS=(-m "$EMAIL")
        $SUDO "$CERTBOT" certonly --webroot -w "$ACME_ROOT" -d "$SHADOWGRID_DOMAIN" --agree-tos --non-interactive \
            --key-type ecdsa "${EMAIL_ARGS[@]}" \
            || die "Let's Encrypt refused. Check that $SHADOWGRID_DOMAIN points to this server and port 80 is open, then run ./install.sh again."
    fi
    # reload nginx whenever the certificate renews
    $SUDO mkdir -p /etc/letsencrypt/renewal-hooks/deploy
    printf '#!/bin/sh\nnginx -s reload\n' | $SUDO tee /etc/letsencrypt/renewal-hooks/deploy/shadowgrid-nginx.sh >/dev/null
    $SUDO chmod 755 /etc/letsencrypt/renewal-hooks/deploy/shadowgrid-nginx.sh
    if [ "${CERTBOT_RENEW_JOB:-0}" = 1 ]; then
        if [ -d /run/systemd/system ]; then
            $SUDO tee /etc/systemd/system/shadowgrid-certbot.service >/dev/null <<EOF
[Unit]
Description=Renew the ShadowGrid HTTPS certificate
[Service]
Type=oneshot
ExecStart=/opt/shadowgrid-certbot/bin/certbot renew --quiet
EOF
            $SUDO tee /etc/systemd/system/shadowgrid-certbot.timer >/dev/null <<EOF
[Unit]
Description=Renew the ShadowGrid HTTPS certificate twice a day
[Timer]
OnCalendar=*-*-* 03,15:17:00
RandomizedDelaySec=1h
Persistent=true
[Install]
WantedBy=timers.target
EOF
            $SUDO systemctl daemon-reload
            $SUDO systemctl enable --now shadowgrid-certbot.timer
        else
            echo "17 3,15 * * * root /opt/shadowgrid-certbot/bin/certbot renew --quiet" | $SUDO tee /etc/cron.d/shadowgrid-certbot >/dev/null
        fi
    fi
    ok "Let's Encrypt certificate in place (renews automatically)"
else
    CERT="$SELF_SSL_DIR/cert.pem"; KEY="$SELF_SSL_DIR/key.pem"
    if ! $SUDO test -s "$CERT"; then
        IP="$(ask_value "Public IP address or host name players will use:" "$(hostname -I 2>/dev/null | awk '{print $1}')")"
        [ -n "$IP" ] || die "An address is needed for the certificate."
        SHADOWGRID_ADDRESS="$IP"
        SAN="DNS:$IP"; [[ "$IP" =~ ^[0-9.]+$|: ]] && SAN="IP:$IP"
        $SUDO mkdir -p "$SELF_SSL_DIR"
        $SUDO chmod 700 "$SELF_SSL_DIR"
        $SUDO openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 825 \
            -subj "/CN=$IP" -addext "subjectAltName=$SAN" -keyout "$KEY" -out "$CERT" 2>/dev/null
        $SUDO chmod 600 "$KEY"
    fi
    ok "Self-signed certificate in $SELF_SSL_DIR (players accept the browser warning once)"
fi

disable_other_defaults
write_site "$CERT" "$KEY"
nginx_reload
ok "nginx configured ($SITE_FILE)"

# ---------- firewall
if command -v ufw >/dev/null 2>&1 && $SUDO ufw status 2>/dev/null | grep -q "Status: active"; then
    if ask_yes_no "ufw is active. Allow HTTP and HTTPS (ports 80 and 443)?" y; then
        $SUDO ufw allow 80/tcp >/dev/null && $SUDO ufw allow 443/tcp >/dev/null && ok "ufw: 80 and 443 open"
    fi
elif command -v firewall-cmd >/dev/null 2>&1 && $SUDO firewall-cmd --state >/dev/null 2>&1; then
    if ask_yes_no "firewalld is running. Allow HTTP and HTTPS?" y; then
        $SUDO firewall-cmd --permanent --add-service=http --add-service=https >/dev/null && $SUDO firewall-cmd --reload >/dev/null && ok "firewalld: http and https open"
    fi
else
    echo "    No active ufw or firewalld found. Make sure ports 80 and 443 reach this machine,"
    echo "    and that port $SHADOWGRID_PORT is NOT reachable from outside."
fi
# SELinux (Fedora, RHEL...): let nginx connect to the app
if command -v getenforce >/dev/null 2>&1 && [ "$(getenforce 2>/dev/null)" = "Enforcing" ]; then
    $SUDO setsebool -P httpd_can_network_connect 1 && ok "SELinux: nginx may connect to ShadowGrid"
fi

# ================================================================== 5. systemd service (optional)
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
    echo
    DEF=y; [ "$SHADOWGRID_SERVICE" = 0 ] && [ -f "$SERVICE_FILE" ] && DEF=n
    if ask_yes_no "Run ShadowGrid as a background service that starts on boot?" "$DEF"; then
        SVC_USER="${SUDO_USER:-$(id -un)}"
        if [ "$SVC_USER" = root ]; then
            # never run the app as root: use a dedicated account
            id shadowgrid >/dev/null 2>&1 || $SUDO useradd --system --no-create-home --shell /usr/sbin/nologin shadowgrid 2>/dev/null \
                || $SUDO adduser -S -H -s /sbin/nologin shadowgrid
            SVC_USER=shadowgrid
            $SUDO chown -R shadowgrid: "$DATA_DIR"
            $SUDO chown shadowgrid: "$ENV_FILE" 2>/dev/null || true
            as_shadowgrid() { if command -v runuser >/dev/null 2>&1; then runuser -u shadowgrid -- "$@"; else su -s /bin/sh shadowgrid -c "$*"; fi; }
            as_shadowgrid test -r "$ROOT/app.py" || die "The shadowgrid account can't read $ROOT. Move ShadowGrid to a folder like /opt/shadowgrid and run ./install.sh again."
        fi
        SVC_GROUP="$(id -gn "$SVC_USER")"
        $SUDO tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=ShadowGrid (Shadowrun table)
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=simple
User=$SVC_USER
Group=$SVC_GROUP
WorkingDirectory=$ROOT
ExecStart="$ROOT/serve.sh"
Restart=on-failure
RestartSec=3
UMask=0077

# sandbox: the app can write only to its data folder and can't gain privileges
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths="$DATA_DIR"
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
ProtectProc=invisible
ProcSubset=pid
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
MemoryDenyWriteExecute=yes
SystemCallArchitectures=native
SystemCallFilter=@system-service
SystemCallFilter=~@privileged @resources
SystemCallErrorNumber=EPERM

[Install]
WantedBy=multi-user.target
EOF
        $SUDO systemctl daemon-reload
        $SUDO systemctl enable shadowgrid >/dev/null 2>&1
        $SUDO systemctl restart shadowgrid
        SHADOWGRID_SERVICE=1
        ok "Service installed and started (systemctl status shadowgrid)"
    else
        SHADOWGRID_SERVICE=0
        if [ -f "$SERVICE_FILE" ]; then
            $SUDO systemctl disable --now shadowgrid >/dev/null 2>&1 || true
            $SUDO rm -f "$SERVICE_FILE"
            $SUDO systemctl daemon-reload
            ok "Old service removed"
        fi
    fi
fi

write_env
[ "${SVC_USER:-}" = shadowgrid ] && $SUDO chown shadowgrid: "$ENV_FILE"

echo
ok "Done."
URL="https://${SHADOWGRID_DOMAIN:-${SHADOWGRID_ADDRESS:-your-server}}"
if [ "$SHADOWGRID_SERVICE" = 1 ]; then
    echo "    ShadowGrid is running: $URL"
    echo "    Logs: journalctl -u shadowgrid -f    Restart: sudo systemctl restart shadowgrid"
else
    echo "    Start it with ./serve.sh, then open $URL"
fi
echo "    Sign in as: gamemaster"

#!/usr/bin/env bash
###############################################################################
# docker/entrypoint.sh
#
# Konteyner içinde masaüstü ortamını ayağa kaldırır:
#   1) Xvfb        — sanal X ekranı (fiziksel monitör yok)
#   2) fluxbox     — pencere yöneticisi (pencere kenarlıkları, taşıma, boyutlandırma)
#   3) x11vnc      — sanal ekranı VNC protokolüyle yayınlar
#   4) websockify  — noVNC'yi tarayıcıya açar (http://localhost:6080)
#   5) main.py     — PyQt6 uygulaması
#
# Uygulama kapandığında konteyner de kapanır.
###############################################################################
set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-99}"
export DISPLAY=":${DISPLAY_NUM}"

SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1400x900x24}"
VNC_PORT="${VNC_PORT:-5900}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_PASSWORD="${VNC_PASSWORD:-}"

log() { printf '[entrypoint] %s\n' "$*"; }

BG_PIDS=()
APP_PID=""

shutdown() {
    trap - TERM INT EXIT

    # Önce uygulamaya nazikçe kapanmasını söyle
    if [[ -n "$APP_PID" ]] && kill -0 "$APP_PID" 2>/dev/null; then
        kill -TERM "$APP_PID" 2>/dev/null || true
        for _ in $(seq 1 20); do
            kill -0 "$APP_PID" 2>/dev/null || break
            sleep 0.25
        done
        kill -KILL "$APP_PID" 2>/dev/null || true
    fi

    # Ardından yardımcı servisleri kapat
    for pid in "${BG_PIDS[@]:-}"; do
        [[ -n "$pid" ]] && kill -TERM "$pid" 2>/dev/null || true
    done
}
trap shutdown TERM INT EXIT

mkdir -p /app/data /app/models /app/cache

# Qt'nin "XDG_RUNTIME_DIR not set" uyarısını önler
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-$(id -u)}"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# ── 1) Sanal ekran ───────────────────────────────────────────────────────────
rm -f "/tmp/.X${DISPLAY_NUM}-lock"
Xvfb "$DISPLAY" -screen 0 "$SCREEN_GEOMETRY" -nolisten tcp -ac +extension GLX +render -noreset &
BG_PIDS+=("$!")

for _ in $(seq 1 100); do
    [[ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]] && break
    sleep 0.1
done
if [[ ! -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]]; then
    log "HATA: sanal ekran (Xvfb) başlatılamadı."
    exit 1
fi
log "Sanal ekran hazır: ${DISPLAY} @ ${SCREEN_GEOMETRY}"

# ── 2) Pencere yöneticisi ────────────────────────────────────────────────────
fluxbox -log /dev/null >/dev/null 2>&1 &
BG_PIDS+=("$!")

# ── 3) VNC sunucusu ──────────────────────────────────────────────────────────
x11vnc_auth=(-nopw)
if [[ -n "$VNC_PASSWORD" ]]; then
    x11vnc -storepasswd "$VNC_PASSWORD" "$HOME/.vncpasswd" >/dev/null 2>&1
    x11vnc_auth=(-rfbauth "$HOME/.vncpasswd")
    log "VNC parola korumalı."
else
    log "UYARI: VNC parolasız yayında. Portları dışarı açacaksanız VNC_PASSWORD tanımlayın."
fi

x11vnc -display "$DISPLAY" -rfbport "$VNC_PORT" -forever -shared -noxdamage \
       -quiet "${x11vnc_auth[@]}" &
BG_PIDS+=("$!")

# ── 4) noVNC (tarayıcı istemcisi) ────────────────────────────────────────────
websockify --web=/usr/share/novnc "$NOVNC_PORT" "localhost:${VNC_PORT}" >/dev/null 2>&1 &
BG_PIDS+=("$!")
log "Arayüz hazır  ->  http://localhost:${NOVNC_PORT}"

# ── 5) Uygulama penceresini ekrana yay ───────────────────────────────────────
# Uygulama 1200x740 boyutunda açılır; sanal ekranın tamamını kaplaması için
# pencere yöneticisine büyütme komutu gönderiyoruz (arka planda bekler).
maximize_when_ready() {
    local win=""
    for _ in $(seq 1 120); do
        # Normal (masaüstü 0'daki) ilk pencereyi al; -1 olanlar panel/dock'tur.
        # Pencere yöneticisi henüz hazır değilken wmctrl hata döner; "|| true"
        # olmadan "set -o pipefail" bu alt kabuğu öldürür.
        win="$(wmctrl -l 2>/dev/null | awk '$2 ~ /^[0-9]+$/ { print $1; exit }' || true)"
        if [[ -n "$win" ]]; then
            # Pencerenin yerleşimi otursun diye kısa bir soluklanma
            sleep 0.5
            wmctrl -i -r "$win" -b add,maximized_vert,maximized_horz 2>/dev/null || true
            log "Pencere ekrana yayıldı ($win)."
            return 0
        fi
        sleep 0.5
    done
    log "Pencere bulunamadı, büyütme atlandı."
}

if [[ "${START_MAXIMIZED:-1}" == "1" ]]; then
    maximize_when_ready &
    BG_PIDS+=("$!")
fi

# ── 6) Uygulama ──────────────────────────────────────────────────────────────
cd /app
python main.py &
APP_PID=$!

wait "$APP_PID"

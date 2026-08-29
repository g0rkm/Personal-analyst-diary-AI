# syntax=docker/dockerfile:1

###############################################################################
# Personal Analyst — Docker imajı
#
# PyQt6 bir masaüstü uygulaması olduğu için konteyner içinde sanal bir X ekranı
# (Xvfb) çalıştırılır ve arayüz noVNC üzerinden tarayıcıya sunulur:
#     http://localhost:6080
###############################################################################

###############################################################################
# Aşama 1 — builder: Python bağımlılıklarını izole bir venv içine kurar.
###############################################################################
FROM python:3.11-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# llama-cpp-python kaynaktan derlendiği için derleme araçları gerekli
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV" \
    && pip install --upgrade pip setuptools wheel

# llama-cpp-python'u kaynaktan derle.
#
# NOT: abetlen'in hazır wheel deposundaki (whl/cpu) "linux_x86_64" paketleri
# musl (Alpine) libc ile derlenmiştir ve Debian tabanlı bu imajda
# "libc.musl-x86_64.so.1: cannot open shared object file" hatası verir.
# Bu yüzden o depo kullanılmıyor, paket burada kaynaktan derleniyor.
#
# GGML_NATIVE=OFF -> "-march=native" kapatılır; imaj, derlendiği makineden
# farklı CPU'larda da çalışır.
ARG LLAMA_CPP_VERSION=0.3.19
RUN CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_CCACHE=OFF" \
    CMAKE_BUILD_PARALLEL_LEVEL="$(nproc)" \
    pip install --no-binary llama-cpp-python "llama-cpp-python==${LLAMA_CPP_VERSION}"

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Derlenen kütüphanenin gerçekten yüklenebildiğini derleme aşamasında doğrula
RUN python -c "import llama_cpp; print('llama-cpp-python OK', llama_cpp.__version__)"

###############################################################################
# Aşama 2 — runtime: sadece çalışma zamanı kütüphaneleri + venv + kaynak kod.
###############################################################################
FROM python:3.11-slim-bookworm AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        # ── Sanal ekran, pencere yöneticisi ve VNC/noVNC köprüsü ──
        xvfb \
        x11vnc \
        fluxbox \
        wmctrl \
        novnc \
        websockify \
        # ── Qt6 (PyQt6) çalışma zamanı bağımlılıkları ──
        libgl1 \
        libegl1 \
        libglib2.0-0 \
        libdbus-1-3 \
        libfontconfig1 \
        libfreetype6 \
        libx11-6 \
        libx11-xcb1 \
        libxext6 \
        libxrender1 \
        libxi6 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libxcb1 \
        libxcb-cursor0 \
        libxcb-glx0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-shm0 \
        libxcb-sync1 \
        libxcb-util1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libsm6 \
        libice6 \
        # ── llama.cpp OpenMP + fontlar ──
        libgomp1 \
        fonts-dejavu-core \
        fonts-noto-color-emoji \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# "Segoe UI" bir Windows fontudur; Linux'ta DejaVu Sans'a yönlendirilir
COPY docker/fonts-local.conf /etc/fonts/local.conf

# X soketi klasörü: Xvfb, root olmayan kullanıcıyla bunu kendisi oluşturamaz
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

# noVNC ana sayfası: kök adrese girildiğinde doğrudan bağlan
RUN printf '%s' '<!doctype html><meta http-equiv="refresh" content="0; url=vnc.html?autoconnect=true&resize=scale&reconnect=true">' \
        > /usr/share/novnc/index.html

# Uygulama root olarak çalışmaz
RUN useradd --create-home --uid 1000 --shell /bin/bash app

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # ── Qt / görüntü ──
    QT_QPA_PLATFORM=xcb \
    QT_X11_NO_MITSHM=1 \
    DISPLAY=:99 \
    # ── Kalıcı veri yolları (docker-compose'daki volume'lerle eşleşir) ──
    DIARY_DB_PATH=/app/data/diary.db \
    DIARY_VECTOR_DB_PATH=/app/data/lance_db \
    DIARY_MODEL_PATH=/app/models/qwen2.5-3b-instruct-q4_k_m.gguf \
    # ── Gizlilik: onnxruntime telemetrisi kapalı (çevrimdışı uygulama) ──
    ORT_DISABLE_TELEMETRY=1 \
    # ── Model önbellekleri ──
    FASTEMBED_CACHE_PATH=/app/cache/fastembed \
    HF_HOME=/app/cache/huggingface \
    XDG_CACHE_HOME=/app/cache

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

COPY . /app

# Volume bağlanmadığında da yazılabilir olmaları için klasörleri hazırla
RUN mkdir -p /app/data /app/models /app/cache \
    && chown -R app:app /app

USER app

EXPOSE 6080 5900

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('127.0.0.1', 6080), 3).close()"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

###############################################################################
# Aşama 3 — tests: runtime imajının üzerine yalnızca test bağımlılıkları.
#
# Üretim imajı (runtime) pytest içermez. Testler için bu aşama derlenir:
#   docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm tests
###############################################################################
FROM runtime AS tests

USER root
RUN pip install --no-cache-dir pytest pytest-qt \
    && chown -R app:app /opt/venv
USER app

# Testler sanal ekran gerektirmez; Qt offscreen platformu yeterlidir
ENV QT_QPA_PLATFORM=offscreen

ENTRYPOINT ["pytest"]
CMD []

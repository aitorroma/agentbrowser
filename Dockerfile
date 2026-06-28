FROM ghcr.io/selkies-project/selkies-gstreamer/gst-py-example:main-ubuntu24.04

USER 0
ARG DEBIAN_FRONTEND=noninteractive
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install --no-install-recommends -y \
    python3-venv \
    python3-dev \
    build-essential \
    ca-certificates \
    curl \
    locales \
    nodejs \
    npm \
    tzdata \
    unzip \
    dbus-x11 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libatspi2.0-0 \
    libasound2t64 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libu2f-udev \
    libvulkan1 \
    libwayland-client0 \
    libx11-6 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    fonts-liberation \
    fonts-liberation2 \
    fonts-noto-color-emoji \
    fonts-freefont-ttf \
    fonts-dejavu-core \
    fonts-ubuntu \
    fonts-roboto \
    fonts-font-awesome \
    fonts-terminus \
    fonts-powerline \
    fonts-open-sans \
    fonts-mononoki \
    fonts-lato \
    scrot \
    socat \
    wmctrl \
    xclip \
    xdotool \
    xdg-utils \
    && sed -i 's/^# *es_ES.UTF-8 UTF-8/es_ES.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen es_ES.UTF-8 \
    && update-locale LANG=es_ES.UTF-8 LANGUAGE=es_ES:es LC_ALL=es_ES.UTF-8 \
    && ln -snf /usr/share/zoneinfo/Europe/Madrid /etc/localtime \
    && echo Europe/Madrid >/etc/timezone \
    && npm install -g @bitwarden/cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/appliance
COPY app/requirements.txt /opt/appliance/requirements.txt
RUN python3 -m venv /opt/appliance/venv \
    && /opt/appliance/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/appliance/venv/bin/pip install -r /opt/appliance/requirements.txt \
    && /opt/appliance/venv/bin/playwright install chromium \
    && mkdir -p /opt/playwright /data/profile /data/output \
    && chown -R 1000:1000 /opt/appliance /opt/playwright /data

COPY app/ /opt/appliance/app/
COPY scripts/browser-launcher.sh /opt/appliance/browser-launcher.sh
COPY scripts/browser-supervisor.conf /etc/supervisor/conf.d/browser-appliance.conf
COPY scripts/nginx-default.conf /etc/nginx/sites-available/default
COPY scripts/selkies-gstreamer-entrypoint.sh /etc/selkies-gstreamer-entrypoint.sh
RUN chmod 755 /opt/appliance/browser-launcher.sh \
    /etc/selkies-gstreamer-entrypoint.sh \
    && sed -i 's#command=bash -c "until nc -z localhost ${SELKIES_PORT:-8081}; do sleep 0.5; done; /usr/sbin/nginx -g \\"daemon off;\\""#command=/usr/sbin/nginx -g "daemon off;"#' /etc/supervisord.conf \
    && chown -R 1000:1000 /opt/appliance /etc/supervisor/conf.d/browser-appliance.conf /etc/selkies-gstreamer-entrypoint.sh \
    && chown 1000:1000 /etc/nginx/sites-available/default

USER 1000
WORKDIR /home/ubuntu

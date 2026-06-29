FROM ghcr.io/linuxserver/baseimage-selkies:arch

SHELL ["/bin/bash", "-lc"]

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

RUN pacman -Syu --noconfirm \
    && pacman -S --noconfirm --needed --overwrite '*' \
        at-spi2-core \
        at-spi2-atk \
        atk \
        base-devel \
        cairo \
        chromium \
        cups \
        curl \
        dbus \
        dolphin \
        firefox \
        foot \
        fontconfig \
        fuzzel \
        git \
        glib2 \
        gtk3 \
        freetype2 \
        jemalloc \
        libdrm \
        libglvnd \
        libpipewire \
        libqalculate \
        librsvg \
        libwebp \
        libxcomposite \
        libxdamage \
        libxfixes \
        libxkbcommon \
        libxrandr \
        meson \
        nodejs \
        ninja \
        noto-fonts \
        noto-fonts-emoji \
        nspr \
        nss \
        npm \
        niri \
        pango \
        pam \
        pipewire \
        polkit \
        pkgconf \
        python \
        python-gobject \
        python-pip \
        python-setuptools \
        python-wheel \
        python-atspi \
        scrot \
        sdbus-cpp \
        socat \
        thunar \
        ttf-dejavu \
        ttf-droid \
        ttf-font-awesome \
        ttf-lato \
        ttf-liberation \
        ttf-mononoki-nerd \
        ttf-opensans \
        ttf-roboto \
        ttf-ubuntu-font-family \
        wayland \
        wayland-protocols \
        wl-clipboard \
        wmctrl \
        wtype \
        ydotool \
        terminus-font \
        ttf-nerd-fonts-symbols-mono \
        vulkan-icd-loader \
        xclip \
        xwayland-satellite \
        xdg-utils \
        xdotool \
    && printf '%s\n' 'es_ES.UTF-8 UTF-8' 'en_US.UTF-8 UTF-8' >> /etc/locale.gen \
    && locale-gen \
    && echo 'LANG=es_ES.UTF-8' > /etc/locale.conf \
    && npm install -g @bitwarden/cli \
    && useradd -m -U builduser \
    && git clone https://aur.archlinux.org/noctalia-git.git /tmp/noctalia-git \
    && chown -R builduser:builduser /tmp/noctalia-git \
    && su builduser -c 'cd /tmp/noctalia-git && makepkg -s --noconfirm --needed' \
    && pacman -U --noconfirm /tmp/noctalia-git/*.pkg.tar.zst \
    && git clone https://aur.archlinux.org/google-chrome.git /tmp/google-chrome \
    && chown -R builduser:builduser /tmp/google-chrome \
    && su builduser -c 'cd /tmp/google-chrome && makepkg -s --noconfirm --needed' \
    && pacman -U --noconfirm /tmp/google-chrome/*.pkg.tar.zst \
    && rm -rf /tmp/noctalia-git /tmp/google-chrome /home/builduser/.cache /home/builduser/.cargo /home/builduser/.local \
    && pacman -Scc --noconfirm

WORKDIR /opt/appliance

COPY app/requirements.txt /opt/appliance/requirements.txt
RUN python -m venv /opt/appliance/venv \
    && /opt/appliance/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/appliance/venv/bin/pip install -r /opt/appliance/requirements.txt \
    && /opt/appliance/venv/bin/playwright install chromium

COPY app/ /opt/appliance/app/
COPY scripts/niri-launcher.sh /opt/appliance/niri-launcher.sh
COPY scripts/noctalia-launcher.sh /opt/appliance/noctalia-launcher.sh
COPY scripts/niri-run-app.sh /opt/appliance/niri-run-app.sh
COPY scripts/terminal-launcher.sh /opt/appliance/terminal-launcher.sh
COPY scripts/test_dogtail.py /opt/appliance/scripts/test_dogtail.py
COPY scripts/thunar_dogtail.py /opt/appliance/scripts/thunar_dogtail.py
COPY assets/niri/config.kdl /opt/appliance/niri/config.kdl

COPY root/defaults/autostart /defaults/autostart
COPY root/defaults/autostart /defaults/autostart_wayland
COPY root/defaults/noctalia-state /defaults/noctalia-state
COPY root/defaults/selkies-web /defaults/selkies-web
COPY root/defaults/wallpapers /defaults/wallpapers
COPY root/defaults/nginx-default.conf /defaults/default.conf
COPY root/defaults/browser-launcher.sh /opt/appliance/browser-launcher.sh
COPY root/defaults/startwm_wayland.sh /defaults/startwm_wayland.sh
COPY root/defaults/startup.sh /defaults/startup.sh
COPY root/defaults/shell/bashrc /config/.bashrc
COPY root/defaults/shell/foot.ini /config/.config/foot/foot.ini

RUN git clone --depth=1 https://github.com/ohmybash/oh-my-bash.git /config/.oh-my-bash

RUN chmod 755 \
    /opt/appliance/browser-launcher.sh \
    /opt/appliance/niri-launcher.sh \
    /opt/appliance/noctalia-launcher.sh \
    /opt/appliance/niri-run-app.sh \
    /opt/appliance/terminal-launcher.sh \
    /opt/appliance/scripts/test_dogtail.py \
    /opt/appliance/scripts/thunar_dogtail.py \
    /defaults/startwm_wayland.sh \
    /defaults/startup.sh \
    && mkdir -p /data/profile /data/output /opt/playwright \
    && chown -R abc:abc /opt/appliance /data /opt/playwright \
    && chown -R abc:abc /config

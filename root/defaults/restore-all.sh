#!/bin/bash
# Restore all persistent components on startup

# Restore wdotool
if [ -f /config/wdotool ]; then
    cp /config/wdotool /usr/local/bin/wdotool
    chmod +x /usr/local/bin/wdotool
    echo "[restore] wdotool restored"
fi

# Restore nginx config
if [ -f /config/nginx-default.conf ]; then
    cp /config/nginx-default.conf /etc/nginx/conf.d/default.conf
    nginx -s reload 2>/dev/null || true
    echo "[restore] Nginx config restored"
fi

# Restore selkies web branding
if [ -d /config/selkies-web ]; then
    cp -a /config/selkies-web/. /usr/share/selkies/web/ 2>/dev/null || true
    chown -R root:root /usr/share/selkies/web/ 2>/dev/null || true
    echo "[restore] Selkies web branding restored"
fi

# Ensure wallpaper is set
if [ -f /config/wallpapers/wallpaper.png ]; then
    echo "[restore] Wallpaper exists: /config/wallpapers/wallpaper.png"
fi

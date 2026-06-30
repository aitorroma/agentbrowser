#!/bin/bash
# Restore selkies branding and nginx config on startup

# Restore nginx config to serve from /config/selkies-web/
if [ -f /config/nginx-default.conf ]; then
    cp /config/nginx-default.conf /etc/nginx/conf.d/default.conf
    nginx -s reload 2>/dev/null || true
    echo "[branding] Nginx config restored"
fi

# Restore selkies web branding
if [ -d /config/selkies-branding ]; then
    cp -a /config/selkies-branding/* /usr/share/selkies/web/ 2>/dev/null || true
    echo "[branding] Selkies web branding restored"
fi

# Ensure wallpaper is set
if [ -f /config/wallpapers/wallpaper.png ]; then
    echo "[branding] Wallpaper exists: /config/wallpapers/wallpaper.png"
fi

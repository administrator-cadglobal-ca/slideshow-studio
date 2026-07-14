#!/bin/bash
# Slideshow Studio — Deploy Script
# Run after uploading app files to /var/www/slideshow/

set -e
APP_DIR="/var/www/slideshow"
cd $APP_DIR

echo "=== Deploying Slideshow Studio ==="

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3.12 -m venv venv
fi

echo "Installing dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# ── Gunicorn service ──────────────────────────────────────────────────────────
cat > /etc/systemd/system/slideshow.service << 'SERVICE'
[Unit]
Description=Slideshow Studio Flask App
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/slideshow
Environment="PATH=/var/www/slideshow/venv/bin"
EnvironmentFile=/var/www/slideshow/.env
ExecStart=/var/www/slideshow/venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:5001 \
    --timeout 300 \
    --access-logfile /var/log/slideshow/access.log \
    --error-logfile /var/log/slideshow/error.log \
    "run:app"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

mkdir -p /var/log/slideshow

# ── Cloudflare Tunnel service ─────────────────────────────────────────────────
cat > /etc/systemd/system/slideshow-tunnel.service << 'SERVICE'
[Unit]
Description=Cloudflare Tunnel for Slideshow Studio
After=network.target

[Service]
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run --token TUNNEL_TOKEN_PLACEHOLDER
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable slideshow
systemctl enable slideshow-tunnel

echo "=== Deploy complete ==="
echo ""
echo "Next steps:"
echo "1. Edit /etc/systemd/system/slideshow-tunnel.service"
echo "   Replace TUNNEL_TOKEN_PLACEHOLDER with your tunnel token"
echo "2. systemctl start slideshow"
echo "3. systemctl start slideshow-tunnel"
echo "4. Check: systemctl status slideshow"

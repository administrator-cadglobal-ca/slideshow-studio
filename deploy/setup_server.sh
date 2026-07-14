#!/bin/bash
# ── Slideshow Studio — Hetzner x4d-prod-01 setup ─────────────────────────────
# Run as root on AlmaLinux 9
# ssh root@49.13.23.98

set -e
echo "=== Slideshow Studio Server Setup ==="

# ── System packages ────────────────────────────────────────────────────────────
dnf update -y
dnf install -y python3.11 python3.11-pip python3-devel gcc git redis nginx certbot \
    python3-certbot-nginx ffmpeg

# ── Redis ─────────────────────────────────────────────────────────────────────
systemctl enable --now redis

# ── App directory ─────────────────────────────────────────────────────────────
mkdir -p /var/slideshow/{app,storage,engine,logs}
useradd -r -s /bin/false slideshow 2>/dev/null || true
chown -R slideshow:slideshow /var/slideshow

# ── Python virtualenv ─────────────────────────────────────────────────────────
python3.11 -m venv /var/slideshow/venv
source /var/slideshow/venv/bin/activate
pip install --upgrade pip
pip install -r /var/slideshow/app/requirements.txt
pip install moviepy Pillow numpy opencv-python-headless

# ── Copy slideshow_maker.py to engine folder ──────────────────────────────────
echo "→ Copy slideshow_maker.py to /var/slideshow/engine/"

# ── Environment file ──────────────────────────────────────────────────────────
if [ ! -f /var/slideshow/app/.env ]; then
    cp /var/slideshow/app/.env.example /var/slideshow/app/.env
    echo "→ Edit /var/slideshow/app/.env with your real values"
fi

# ── Systemd: Gunicorn web server ──────────────────────────────────────────────
cat > /etc/systemd/system/slideshow-web.service << 'EOF'
[Unit]
Description=Slideshow Studio Web App
After=network.target redis.service

[Service]
User=slideshow
Group=slideshow
WorkingDirectory=/var/slideshow/app
Environment="PATH=/var/slideshow/venv/bin"
EnvironmentFile=/var/slideshow/app/.env
ExecStart=/var/slideshow/venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:5000 \
    --timeout 300 \
    --log-file /var/slideshow/logs/gunicorn.log \
    run:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# ── Systemd: Celery worker ─────────────────────────────────────────────────────
cat > /etc/systemd/system/slideshow-worker.service << 'EOF'
[Unit]
Description=Slideshow Studio Celery Worker
After=network.target redis.service

[Service]
User=slideshow
Group=slideshow
WorkingDirectory=/var/slideshow/app
Environment="PATH=/var/slideshow/venv/bin"
EnvironmentFile=/var/slideshow/app/.env
ExecStart=/var/slideshow/venv/bin/celery \
    -A app.extensions.celery_app worker \
    --loglevel=info \
    --concurrency=1 \
    --logfile=/var/slideshow/logs/celery.log
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# ── Nginx ─────────────────────────────────────────────────────────────────────
cp /var/slideshow/app/deploy/nginx.conf /etc/nginx/conf.d/slideshow.conf
nginx -t && systemctl reload nginx

# ── SSL cert ──────────────────────────────────────────────────────────────────
echo "→ Run: certbot --nginx -d slideshow.x4dglobal.com"

# ── Enable and start services ─────────────────────────────────────────────────
systemctl daemon-reload
systemctl enable --now slideshow-web slideshow-worker

echo ""
echo "=== Setup complete ==="
echo "1. Edit /var/slideshow/app/.env"
echo "2. Run: certbot --nginx -d slideshow.x4dglobal.com"
echo "3. Add slideshow.x4dglobal.com to Cloudflare ZT access policy"
echo "4. Copy slideshow_maker.py to /var/slideshow/engine/"
echo "5. Visit https://slideshow.x4dglobal.com"

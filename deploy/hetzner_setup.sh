#!/bin/bash
# Slideshow Studio — Hetzner Setup Script
# Run as root on x4d-prod-01 (AlmaLinux 9)
# Usage: bash hetzner_setup.sh

set -e
echo "=== Slideshow Studio — Hetzner Setup ==="

# ── Python 3.12 ───────────────────────────────────────────────────────────────
echo "Installing Python 3.12..."
dnf install -y python3.12 python3.12-pip python3.12-devel gcc git

# ── App directory ─────────────────────────────────────────────────────────────
APP_DIR="/var/www/slideshow"
mkdir -p $APP_DIR
echo "App directory: $APP_DIR"

# ── Cloudflared ───────────────────────────────────────────────────────────────
echo "Installing cloudflared..."
curl -L --output /usr/local/bin/cloudflared \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x /usr/local/bin/cloudflared
cloudflared --version

# ── ffmpeg ────────────────────────────────────────────────────────────────────
echo "Installing ffmpeg..."
dnf install -y epel-release
dnf install -y ffmpeg || dnf install -y https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz || true
which ffmpeg || echo "ffmpeg not found - install manually"

echo "=== Setup complete ==="
echo "Next: upload app files and run deploy.sh"

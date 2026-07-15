#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Tailwind CSS build script
# Uses the standalone Tailwind CLI binary — no Node.js required.
#
# Usage:
#   ./build.sh              # one-shot build (production, minified)
#   ./build.sh --watch      # watch mode for development
#
# Called by deploy/deploy.sh at deploy time.
# ─────────────────────────────────────────────────────────────────────────

set -e

APP_ROOT="${APP_ROOT:-/var/www/slideshow}"
INPUT="$APP_ROOT/app/static/css/input.css"
OUTPUT="$APP_ROOT/app/static/css/app.css"
CONFIG="$APP_ROOT/tailwind.config.js"

# Ensure the standalone Tailwind CLI is installed
if ! command -v tailwindcss &> /dev/null; then
    echo "Installing standalone Tailwind CLI..."
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  BINARY="tailwindcss-linux-x64" ;;
        aarch64) BINARY="tailwindcss-linux-arm64" ;;
        *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    curl -sL -o /usr/local/bin/tailwindcss \
        "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/$BINARY"
    chmod +x /usr/local/bin/tailwindcss
    echo "Installed: $(tailwindcss --help | head -1)"
fi

if [ "$1" = "--watch" ]; then
    echo "Watching for changes to templates and rebuilding..."
    tailwindcss -i "$INPUT" -o "$OUTPUT" --config "$CONFIG" --watch
else
    echo "Building minified CSS..."
    tailwindcss -i "$INPUT" -o "$OUTPUT" --config "$CONFIG" --minify
    SIZE=$(du -h "$OUTPUT" | cut -f1)
    echo "Built $OUTPUT ($SIZE)"
fi

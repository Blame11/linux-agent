#!/bin/bash

set -e

APP_DIR="/opt/linux-ai-agent"
VENV_DIR="$APP_DIR/venv"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [ "$EUID" -ne 0 ]; then
    echo "Error: please run this installer with sudo."
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required."
    exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)'; then
    echo "Error: Python 3.14 or newer is required."
    echo "Detected Python: $(python3 --version)"
    exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "Error: Python venv support is required."
    exit 1
fi


echo "Installing application to $APP_DIR"

mkdir -p "$APP_DIR"

echo "Creating Python virtual environment..."

python3 -m venv "$VENV_DIR"

echo "Installing Python package..."

"$VENV_DIR/bin/python" -m pip install "$SOURCE_DIR"

echo "Installing CLI commands..."

ln -sf "$VENV_DIR/bin/ai" /usr/local/bin/ai
ln -sf "$VENV_DIR/bin/ai-context" /usr/local/bin/ai-context

echo
echo "Installation completed."
echo
echo "Commands:"
echo "  ai"
echo "  ai-context"
echo
echo "Configuration:"
echo "  ~/.linux_ai_agent/.env"

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

check_cli_destination() {
    local destination="$1"
    local expected_target="$2"

    if [[ ! -e "$destination" && ! -L "$destination" ]]; then
        return 0
    fi

    if [[ -L "$destination" ]] \
        && [[ "$(readlink -- "$destination")" == "$expected_target" ]]; then
        return 0
    fi

    echo "Error: refusing to overwrite existing path: $destination"
    echo "Move it aside or remove it explicitly, then run the installer again."
    return 1
}

check_cli_destination \
    "/usr/local/bin/ai" \
    "$VENV_DIR/bin/ai"
check_cli_destination \
    "/usr/local/bin/ai-context" \
    "$VENV_DIR/bin/ai-context"

echo "Installing application to $APP_DIR"

mkdir -p "$APP_DIR"

echo "Creating Python virtual environment..."

if ! python3 -m venv "$VENV_DIR"; then
    echo "Error: could not create the Python virtual environment at $VENV_DIR."
    echo "Check that Python's venv/ensurepip support is installed and that"
    echo "the installer can write to $APP_DIR."
    exit 1
fi

echo "Installing Python package..."

if ! "$VENV_DIR/bin/python" -m pip install --upgrade --force-reinstall "$SOURCE_DIR"; then
    echo "Error: package installation failed in $VENV_DIR."
    exit 1
fi

echo "Installing CLI commands..."

ln -sf "$VENV_DIR/bin/ai" /usr/local/bin/ai
ln -sf "$VENV_DIR/bin/ai-context" /usr/local/bin/ai-context

if [[ ! -x "$VENV_DIR/bin/ai" ]] || [[ ! -x "$VENV_DIR/bin/ai-context" ]]; then
    echo "Error: expected CLI entry points are missing or not executable."
    exit 1
fi

if [[ "$(readlink -- /usr/local/bin/ai)" != "$VENV_DIR/bin/ai" ]] \
    || [[ "$(readlink -- /usr/local/bin/ai-context)" != "$VENV_DIR/bin/ai-context" ]]; then
    echo "Error: installed CLI links do not point to the application environment."
    exit 1
fi

if ! "$VENV_DIR/bin/ai-context" >/dev/null; then
    echo "Error: ai-context failed to run from the installed environment."
    exit 1
fi

echo
echo "Installation completed."
echo
echo "Commands:"
echo "  ai"
echo "  ai-context"
echo
echo "Configuration:"
echo "  ~/.linux_ai_agent/.env"

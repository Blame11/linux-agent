import json
import os
import platform
import subprocess
from pathlib import Path


CACHE_FILE = Path.home() / ".linux_ai_context.json"


def run_command(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return "unknown"

        return result.stdout.strip()

    except Exception:
        return "unknown"


def get_static_context():

    os_name = run_command(
        "grep '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '\"'"
    )

    return {
        "os": os_name,
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "user": os.getenv("USER", "unknown"),
        "shell": os.getenv("SHELL", "unknown"),
        "working_directory": os.getcwd(),
    }


def save_context(context):

    with open(CACHE_FILE, "w") as file:
        json.dump(context, file, indent=2)


def load_context():

    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r") as file:
            return json.load(file)

    except Exception:
        return None


def get_cached_static_context():

    context = load_context()

    if context is None:
        context = get_static_context()
        save_context(context)

    return context
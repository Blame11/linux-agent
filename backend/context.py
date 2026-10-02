import os
import platform
import subprocess


def run_command(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )

        return result.stdout.strip()

    except Exception:
        return "unknown"


def get_static_context():

    context = {
        "os": run_command("cat /etc/os-release | grep '^PRETTY_NAME='"),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "user": os.getenv("USER", "unknown"),
        "shell": os.getenv("SHELL", "unknown"),
        "working_directory": os.getcwd()
    }

    return context
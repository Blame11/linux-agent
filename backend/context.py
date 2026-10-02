import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
import re

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


# -----------------------------------
# STATIC CONTEXT
# -----------------------------------

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
    }


# -----------------------------------
# DYNAMIC CONTEXT PROVIDERS
# -----------------------------------

def get_location_context():
    return {
        "working_directory": os.getcwd()
    }


def get_storage_context():
    result = shutil.disk_usage("/")

    total_gb = round(result.total / (1024 ** 3), 2)
    used_gb = round(result.used / (1024 ** 3), 2)
    free_gb = round(result.free / (1024 ** 3), 2)
    used_percent = round((result.used / result.total) * 100, 1)

    return {
        "root_filesystem": {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "used_percent": used_percent
        }
    }


def get_resources_context():
    load = os.getloadavg()

    memory = run_command(
        "free -b | awk 'NR==2 {print $2, $3, $4}'"
    )

    try:
        total, used, free = map(int, memory.split())

        return {
            "load_average": {
                "1_min": round(load[0], 2),
                "5_min": round(load[1], 2),
                "15_min": round(load[2], 2)
            },
            "memory": {
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb": round(used / (1024 ** 3), 2),
                "free_gb": round(free / (1024 ** 3), 2),
                "used_percent": round((used / total) * 100, 1)
            }
        }

    except (ValueError, ZeroDivisionError):
        return {
            "load_average": {
                "1_min": round(load[0], 2),
                "5_min": round(load[1], 2),
                "15_min": round(load[2], 2)
            },
            "memory": "unknown"
        }

def get_network_context(question=""):
    question = question.lower()

    import re

    port_match = re.search(r"\bport\s+(\d+)\b", question)

    if port_match:
        port = port_match.group(1)

        listening_ports = run_command(
        f"ss -lntup | grep -E ':{port}([[:space:]]|$)' || true"
        )

        if not listening_ports:
            listening_ports = "No listening process found."

        return {
            "port": int(port),
            "listening_process": listening_ports
        }

    return {
        "listening_ports": run_command("ss -lntup")
    }

def get_processes_context():
    cpu_output = run_command(
        "ps -eo pid=,comm=,%cpu= --sort=-%cpu | head -5"
    )

    memory_output = run_command(
        "ps -eo pid=,comm=,%mem= --sort=-%mem | head -5"
    )

    def parse_processes(output):
        processes = []

        for line in output.splitlines():
            parts = line.split()

            if len(parts) < 3:
                continue

            try:
                processes.append({
                    "pid": int(parts[0]),
                    "command": parts[1],
                    "usage_percent": float(parts[2])
                })
            except ValueError:
                continue

        return processes

    return {
        "top_cpu_processes": parse_processes(cpu_output),
        "top_memory_processes": parse_processes(memory_output)
    }
def get_services_context():
    services = run_command(
        "systemctl --type=service --state=running --no-pager"
    )

    return {
        "running_services": services
    }


# -----------------------------------
# CACHE
# -----------------------------------

def save_static_context(context):
    with open(CACHE_FILE, "w") as file:
        json.dump(context, file, indent=2)


def load_static_context():
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r") as file:
            return json.load(file)

    except Exception:
        return None


def get_cached_static_context():
    context = load_static_context()

    if context is None:
        context = get_static_context()
        save_static_context(context)

    return context


# -----------------------------------
# CONTEXT SELECTOR
# -----------------------------------
def contains_keyword(question, keyword):
    pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
    return re.search(pattern, question) is not None

def select_context(question):
    question = question.lower()

    selected = []

    # Storage
    if any(contains_keyword(question, word) for word in [
        "disk", "storage", "filesystem", "file system",
        "space", "full", "df", "du"
    ]):
        selected.append("storage")

    # Network
    if any(contains_keyword(question, word) for word in [
        "network", "networking", "interface", "ip address",
        "route", "routing", "connection", "connectivity",
        "dns", "port", "socket"
    ]):
        selected.append("network")

    # Resources
    if any(contains_keyword(question, word) for word in [
        "slow", "cpu", "load",
        "performance", "resource", "high usage",
        "ram", "memory"
    ]):
        selected.append("resources")

    # Processes
    if any(contains_keyword(question, word) for word in [
        "top process",
        "top processes",
        "process",
        "processes",
        "pid",
        "running process"
    ]):
        selected.append("processes")

    # Services
    if any(contains_keyword(question, word) for word in [
        "service", "systemctl", "daemon",
        "nginx", "apache", "ssh", "sshd"
    ]):
        selected.append("services")

    # Location
    if any(contains_keyword(question, word) for word in [
        "directory", "folder", "path",
        "pwd", "current location"
    ]):
        selected.append("location")

    return list(dict.fromkeys(selected))

# -----------------------------------
# BUILD SELECTED CONTEXT
# -----------------------------------

def get_selected_context(question):
    selected = select_context(question)

    context = {
        "system": get_cached_static_context()
    }

    providers = {
        "location": get_location_context,
        "storage": get_storage_context,
        "resources": get_resources_context,
        "network": get_network_context,
        "processes": get_processes_context,
        "services": get_services_context,
    }

    for name in selected:
        if name == "network":
            context[name] = get_network_context(question)
        else:
            context[name] = providers[name]()

    return context
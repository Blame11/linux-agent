import shlex


READ_ONLY_COMMANDS = {
    "ls",
    "pwd",
    "cat",
    "grep",
    "find",
    "ps",
    "top",
    "df",
    "du",
    "free",
    "uptime",
    "ss",
    "ip",
    "ping",
    "systemctl",
    "journalctl",
    "mount",
}

MODIFYING_COMMANDS = {
    "chmod",
    "chown",
    "cp",
    "mv",
    "mkdir",
    "touch",
    "rm",
    "apt",
    "dnf",
    "yum",
    "docker",
    "kubectl",
    "terraform",
    "ansible",
}

DANGEROUS_COMMANDS = {
    "rm",
    "mkfs",
    "fdisk",
    "parted",
    "dd",
    "shutdown",
    "reboot",
    "poweroff",
}


SENSITIVE_PATHS = {
    "/etc/shadow",
    "/etc/gshadow",
    "/etc/sudoers",
    "/etc/sudoers.d",
}


BLOCKED_PATTERNS = {
    "find /",
    "find /*",
    "cat /etc/shadow",
    "cat /etc/gshadow",
}


def get_base_command(command):
    try:
        parts = shlex.split(command)

        if not parts:
            return ""

        if parts[0] == "sudo" and len(parts) > 1:
            return parts[1]

        return parts[0]

    except ValueError:
        return ""


def contains_shell_operator(command):
    operators = [
        ";",
        "&&",
        "||",
        "|",
        ">",
        ">>",
        "<",
        "$(",
        "`",
    ]

    return any(operator in command for operator in operators)


def contains_sensitive_path(command):
    try:
        parts = shlex.split(command)
    except ValueError:
        return True

    return any(
        path in SENSITIVE_PATHS
        for path in parts
    )


def contains_blocked_pattern(command):
    normalized = " ".join(command.split()).lower()

    return any(
        pattern in normalized
        for pattern in BLOCKED_PATTERNS
    )


def classify_command(command):
    if not command.strip():
        return "UNKNOWN"

    if contains_shell_operator(command):
        return "UNKNOWN"

    if contains_sensitive_path(command):
        return "UNKNOWN"

    if contains_blocked_pattern(command):
        return "UNKNOWN"

    base_command = get_base_command(command)

    if base_command in DANGEROUS_COMMANDS:
        return "DANGEROUS"

    if base_command in MODIFYING_COMMANDS:
        return "MODIFICATION"

    if base_command in READ_ONLY_COMMANDS:
        return "READ_ONLY"

    return "UNKNOWN"
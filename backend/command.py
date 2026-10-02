import re


COMMANDS = (
    "ls|cd|pwd|cat|grep|find|ps|top|df|du|free|uptime|"
    "ss|ip|ping|curl|wget|systemctl|journalctl|mount|"
    "chmod|chown|cp|mv|mkdir|touch|rm|apt|dnf|yum|"
    "docker|kubectl|terraform|ansible"
)

COMMAND_PATTERN = re.compile(
    rf"(?<![\w/-])(?:sudo\s+)?(?:{COMMANDS})\b"
)


def extract_commands(text):
    commands = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        matches = list(COMMAND_PATTERN.finditer(line))

        for index, match in enumerate(matches):
            start = match.start()
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(line)
            )

            command = line[start:end].strip()

            # Remove natural-language connectors
            command = re.split(
                r"\s+(?:and then|then|and)\s+",
                command,
                maxsplit=1,
                flags=re.IGNORECASE
            )[0].strip()

            if command and command not in commands:
                commands.append(command)

    return commands
import json


def parse_action(response):
    response = response.strip()

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    if data.get("action") != "command":
        return None

    command = data.get("command")

    if not isinstance(command, str) or not command.strip():
        return None

    return {
        "action": "command",
        "command": command.strip()
    }
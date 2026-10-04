import json
import re


TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>",
    re.IGNORECASE | re.DOTALL
)


def _normalize_action(data):
    if not isinstance(data, dict):
        return None

    if data.get("action") == "answer":
        content = data.get("content")
        if isinstance(content, str):
            return {
                "action": "answer",
                "content": content
            }
        return None

    if data.get("action") == "command":
        command = data.get("command")
        if isinstance(command, str) and command.strip():
            return {
                "action": "command",
                "command": command.strip()
            }

    return None


def _strip_code_fence(text):
    text = text.strip()
    if not text.startswith("```") or not text.endswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) < 3:
        return text

    if lines[0].strip().lower() in ("```", "```json"):
        return "\n".join(lines[1:-1]).strip()

    return text


def _command_from_tool_payload(payload):
    payload = _strip_code_fence(payload)

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict):
        function = data.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            arguments = function.get("arguments")
        else:
            name = data.get("name", function)
            arguments = data.get("arguments")

        if name != "execute_bash":
            return None

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return None

        if not isinstance(arguments, dict):
            return None

        command = arguments.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
        return None

    function_match = re.match(
        r"^function\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*>?\s*(.*)$",
        payload,
        re.DOTALL
    )
    if not function_match or function_match.group(1) != "execute_bash":
        return None

    command_text = _strip_code_fence(function_match.group(2))
    if not command_text:
        return None

    try:
        arguments = json.loads(command_text)
    except json.JSONDecodeError:
        arguments = None

    if isinstance(arguments, dict):
        command = arguments.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
        return None

    return command_text


def parse_ai_response(response):
    if not isinstance(response, str) or not response.strip():
        return None

    text = response.strip()
    json_text = _strip_code_fence(text)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        data = None
    else:
        return _normalize_action(data)

    tool_calls = TOOL_CALL_PATTERN.findall(text)
    if tool_calls:
        if len(tool_calls) != 1:
            return None

        command = _command_from_tool_payload(tool_calls[0])
        if command is None:
            return None
        return {
            "action": "command",
            "command": command
        }

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue

        action = _normalize_action(data)
        if action is not None:
            return action

    if text.startswith(("{", "[")) or text.startswith("```json"):
        return None

    if "<tool_call>" in text.lower():
        return None

    return {
        "action": "answer",
        "content": text
    }


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
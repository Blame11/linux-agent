import json

from action import parse_action
from command_safety import classify_command
from approval import request_approval
from executor import execute_command


MAX_STEPS = 20


def process_action(response):
    action = parse_action(response)

    if action is None:
        return {
            "type": "invalid",
            "message": "AI did not return a valid command action."
        }

    command = action["command"]
    classification = classify_command(command)

    if classification == "INVALID":
        return {
            "type": "rejected",
            "message": "AI returned an empty command.",
            "command": command
        }

    if not request_approval(command, classification):
        return {
            "type": "cancelled",
            "message": "Command execution cancelled.",
            "command": command
        }

    result = execute_command(command)

    return {
        "type": "result",
        "command": command,
        "classification": classification,
        "result": result
    }
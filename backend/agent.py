from action import parse_action
from command_safety import classify_command
from approval import request_approval
from executor import execute_command


def process_action(response):
    action = parse_action(response)

    if action is None:
        return {
            "type": "invalid",
            "message": "AI did not return a valid command action."
        }

    command = action["command"]
    classification = classify_command(command)

    if classification == "UNKNOWN":
        return {
            "type": "rejected",
            "message": "Command rejected by safety policy.",
            "command": command
        }

    if classification == "DANGEROUS":
        return {
            "type": "rejected",
            "message": "Dangerous commands are not executable yet.",
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
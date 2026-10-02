def classify_command(command):
    command = command.strip()

    if not command:
        return "INVALID"

    return "USER_APPROVAL"
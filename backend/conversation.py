MAX_MESSAGES = 4


def add_message(messages, role, content):
    messages.append({
        "role": role,
        "content": content
    })

    trim_messages(messages)


def trim_messages(messages):
    if not messages:
        return

    system_message = messages[0]

    if system_message.get("role") != "system":
        return

    recent_messages = messages[1:]

    if len(recent_messages) > MAX_MESSAGES:
        recent_messages = recent_messages[-MAX_MESSAGES:]

    messages[:] = [system_message] + recent_messages


def get_messages(messages):
    return messages.copy()
MAX_MESSAGES = 6


def add_message(messages, role, content):
    messages.append({
        "role": role,
        "content": content
    })

    trim_messages(messages)


def trim_messages(messages):
    if not messages:
        return

    system_messages = [
        message
        for message in messages
        if message["role"] == "system"
    ]

    conversation_messages = [
        message
        for message in messages
        if message["role"] != "system"
    ]

    conversation_messages = conversation_messages[-MAX_MESSAGES:]

    messages[:] = system_messages + conversation_messages


def get_messages(messages):
    return messages.copy()
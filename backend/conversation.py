MAX_MESSAGES = 12
MAX_CONVERSATION_RESULT_CHARS = 2000


def compact_text(text, max_chars=MAX_CONVERSATION_RESULT_CHARS):
    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    half = max_chars // 2

    return (
        text[:half]
        + "\n...[conversation result truncated]...\n"
        + text[-half:]
    )


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
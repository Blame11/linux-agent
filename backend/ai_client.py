import json
import os
import sys

from dotenv import load_dotenv
from groq import Groq

from context import get_selected_context
from conversation import add_message


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL")

if not api_key:
    raise ValueError("GROQ_API_KEY is not configured")

if not model:
    raise ValueError("GROQ_MODEL is not configured")


client = Groq(api_key=api_key)


SYSTEM_PROMPT = """You are a concise Linux Bash terminal assistant.

Your job is to help users with Linux commands and troubleshooting.

Rules:
- Assume Linux with Bash unless the user says otherwise.
- Give the most appropriate command first.
- Keep answers short, normally 1-4 lines.
- Do not use Markdown code fences.
- Never execute commands. Only suggest commands.
- For destructive commands, prefer the least destructive appropriate option.
- Do not suggest rm -rf unless force deletion is specifically required.
- Warn briefly before potentially destructive operations.
- If the request is ambiguous, ask a short clarification question.
- Treat provided system context as observed evidence.
- Do not invent system information.
- Do not claim a cause unless the provided evidence supports it.
- Clearly distinguish observed facts from possible causes.
- If evidence is insufficient, say so.
- When troubleshooting, prefer the next diagnostic command over speculation.
- Do not assume a process is problematic solely because it has the highest CPU or memory usage.
"""


def ask_ai(messages):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        reasoning_effort="none"
    )

    return response.choices[0].message.content


def build_request_messages(conversation, question):
    context = get_selected_context(question)

    messages = conversation.copy()

    context_message = {
        "role": "system",
        "content": (
            "Current Linux system context for this request:\n"
            + json.dumps(context, indent=2)
        )
    }

    messages.append(context_message)

    messages.append({
        "role": "user",
        "content": question
    })

    return messages


def single_question(prompt):
    conversation = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    messages = build_request_messages(
        conversation,
        prompt
    )

    return ask_ai(messages)


def interactive_mode():
    conversation = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    print("Linux AI Assistant")
    print("Type 'exit' or 'quit' to leave.")
    print()

    while True:
        try:
            user_input = read_terminal_input()

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        try:
            messages = build_request_messages(
                conversation,
                user_input
            )

            answer = ask_ai(messages)

            print(f"AI: {answer}\n")

            add_message(
                conversation,
                "user",
                user_input
            )

            add_message(
                conversation,
                "assistant",
                answer
            )

        except Exception as error:
            print(f"Error: {error}\n")

TROUBLESHOOTING_PROMPT = """You are troubleshooting a Linux system.

Use the provided Linux context as evidence.

Follow this process:

1. OBSERVATION
   State only what the collected evidence shows.

2. ANALYSIS
   Explain what the evidence suggests.
   Do not claim a cause unless supported by evidence.

3. NEXT STEP
   Give exactly ONE diagnostic command when more information is needed.

Rules:
- Never execute commands.
- Never invent command output.
- Prefer read-only diagnostic commands.
- Do not give multiple diagnostic commands at once.
- Do not repeat a command whose result is already available.
- If the evidence is sufficient, explain the likely cause and stop.
- Clearly distinguish facts from hypotheses.
"""
def is_command_result(text):
    indicators = [
        "PID",
        "UID",
        "COMMAND",
        "LISTEN",
        "Mem:",
        "Filesystem",
        "Load average",
        "systemctl",
        "Active:",
        "State:",
    ]

    return any(indicator in text for indicator in indicators)

def build_troubleshooting_message(user_input):
    if is_command_result(user_input):
        return (
            "The following is terminal output collected from the Linux system. "
            "Treat it as observed evidence. Do not assume anything beyond "
            "what the output shows.\n\n"
            + user_input
        )

    return user_input

def read_multiline():
    print("Paste terminal output.")
    print("Type END on a new line when finished.")

    lines = []

    while True:
        line = input()

        if line.strip() == "END":
            break

        lines.append(line)

    return "\n".join(lines)

def read_terminal_input():
    first_line = input("You: ")

    # Normal single-line question
    if not first_line.strip():
        return ""

    # Explicit paste mode
    if first_line.strip().lower() == "paste":
        print("Paste terminal output. Type END on a new line.")

        lines = []

        while True:
            line = input()

            if line.strip() == "END":
                break

            lines.append(line)

        return "\n".join(lines)

    return first_line.strip()

def troubleshooting_mode():
    conversation = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    },
    {
        "role": "system",
        "content": TROUBLESHOOTING_PROMPT
    }
    ]

    print("Linux AI Troubleshooter")
    print("Describe the problem. Type 'exit' to leave.")
    print()

    while True:
        try:
            user_input = read_terminal_input()

            if user_input.lower() == "paste":
                user_input = read_multiline()

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        try:
            troubleshooting_input = build_troubleshooting_message(
            user_input
            )

            messages = build_request_messages(
                conversation,
                troubleshooting_input
            )

            answer = ask_ai(messages)

            print(f"\nAI: {answer}\n")

            add_message(
                conversation,
                "user",
                user_input
            )

            add_message(
                conversation,
                "assistant",
                answer
            )

        except Exception as error:
            print(f"Error: {error}\n")

def main():
    if len(sys.argv) > 1:

        if sys.argv[1] == "--troubleshoot":
            troubleshooting_mode()
            return

        prompt = " ".join(sys.argv[1:])
        print(single_question(prompt))

    else:
        interactive_mode()

if __name__ == "__main__":
    main()
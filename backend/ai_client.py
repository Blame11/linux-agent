import json
import os
import sys

from dotenv import load_dotenv
from groq import Groq

from context import get_selected_context
from conversation import add_message
from agent import process_action


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL")

if not api_key:
    raise ValueError("GROQ_API_KEY is not configured")

if not model:
    raise ValueError("GROQ_MODEL is not configured")


client = Groq(api_key=api_key)


SYSTEM_PROMPT = """You are a concise Linux Bash terminal AI assistant.

You help users understand, diagnose, and manage Linux systems.

You can inspect the Linux system by proposing commands.

IMPORTANT:
Return ONLY valid JSON.

You have exactly two possible response types.

For a command:
{"action":"command","command":"COMMAND"}

For a final answer:
{"action":"answer","content":"ANSWER"}

Rules:
- Assume Linux with Bash unless the user says otherwise.
- Use provided system context as observed evidence.
- Do not invent system information.
- Do not claim a cause unless evidence supports it.
- If more information is needed, request exactly ONE diagnostic command.
- Never request multiple commands in one response.
- Commands must be executable without a shell.
- Do NOT use pipes, redirects, command substitution, semicolons, &&, ||, backticks, or shell operators.
- Prefer read-only diagnostic commands.
- Never request rm -rf or other destructive commands unless explicitly required.
- Do not use sudo.
- Keep final answers concise.
"""


TROUBLESHOOTING_PROMPT = """You are troubleshooting a Linux system.

Follow this process:

1. OBSERVATION
   Use only collected evidence.

2. ANALYSIS
   Explain what the evidence suggests.
   Do not invent causes.

3. NEXT STEP
   If more information is needed, request exactly ONE diagnostic command.

Rules:
- Prefer read-only commands.
- Never request multiple commands.
- Do not repeat a command whose result is already available.
- Clearly distinguish facts from hypotheses.
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

    context_message = {
        "role": "system",
        "content": (
            "Current Linux system context for this request:\n"
            + json.dumps(context, indent=2)
        )
    }

    messages = conversation.copy()
    messages.append(context_message)

    messages.append({
        "role": "user",
        "content": question
    })

    return messages


def get_ai_action(conversation, question):
    messages = build_request_messages(
        conversation,
        question
    )

    response = ask_ai(messages)

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {
            "action": "answer",
            "content": response
        }


def handle_agent_turn(conversation, question):
    action = get_ai_action(
        conversation,
        question
    )

    if action.get("action") == "answer":
        answer = action.get(
            "content",
            "No answer returned."
        )

        print(f"AI: {answer}\n")

        add_message(
            conversation,
            "user",
            question
        )

        add_message(
            conversation,
            "assistant",
            answer
        )

        return

    if action.get("action") != "command":
        print("AI returned an invalid action.\n")
        return

    command = action.get("command")

    if not command:
        print("AI returned an empty command.\n")
        return

    print(f"\nAI wants to run: {command}")

    result = process_action(
        json.dumps({
            "action": "command",
            "command": command
        })
    )

    if result["type"] != "result":
        print(f"{result['message']}\n")
        return

    output = result["result"]

    execution_message = (
        "The following command was executed on the Linux system.\n\n"
        f"Command: {command}\n\n"
        f"Result:\n{json.dumps(output, indent=2)}"
    )

    add_message(
        conversation,
        "user",
        question
    )

    add_message(
        conversation,
        "assistant",
        json.dumps(action)
    )

    follow_up_messages = build_request_messages(
        conversation,
        execution_message
    )

    follow_up = ask_ai(follow_up_messages)

    try:
        follow_up_action = json.loads(follow_up)
    except json.JSONDecodeError:
        follow_up_action = {
            "action": "answer",
            "content": follow_up
        }

    if follow_up_action.get("action") == "command":
        print(f"AI wants to run: {follow_up_action.get('command')}\n")
    else:
        print(
            f"AI: {follow_up_action.get('content', follow_up)}\n"
        )

    add_message(
        conversation,
        "user",
        execution_message
    )

    add_message(
        conversation,
        "assistant",
        follow_up
    )


def read_terminal_input():
    first_line = input("You: ")

    if not first_line.strip():
        return ""

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


def interactive_mode(extra_prompt=None):
    conversation = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    if extra_prompt:
        conversation.append({
            "role": "system",
            "content": extra_prompt
        })

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
            handle_agent_turn(
                conversation,
                user_input
            )

        except Exception as error:
            print(f"Error: {error}\n")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--troubleshoot":
            interactive_mode(
                TROUBLESHOOTING_PROMPT
            )
            return

        prompt = " ".join(sys.argv[1:])

        conversation = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        handle_agent_turn(
            conversation,
            prompt
        )

        return

    interactive_mode()


if __name__ == "__main__":
    main()
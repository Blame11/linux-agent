import json
import os
import sys

from dotenv import load_dotenv
from groq import Groq

from context import get_selected_context
from conversation import add_message
from agent import process_action
from task_state import (
    create_task,
    update_task_status,
    add_command,
    add_result,
    get_task_history,
    initialize_database,
)
MAX_STEPS = 20
MAX_STEPS = 20
MAX_TASK_HISTORY = 2
MAX_RESULT_CHARS = 4000

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL")

if not api_key:
    raise ValueError("GROQ_API_KEY is not configured")

if not model:
    raise ValueError("GROQ_MODEL is not configured")


client = Groq(api_key=api_key)


COMMON_PROMPT = """You are a Linux Bash terminal AI agent.

Return ONLY valid JSON:
{"action":"command","command":"COMMAND"}
or
{"action":"answer","content":"ANSWER"}

Core rules:
- Use system context and command results as evidence.
- Never invent system information or command output.
- Preserve exact observed values.
- Do not present inference as fact.
- If evidence is insufficient, request another command.
- Return ONE command at a time.
- The user must explicitly approve every command.
- Never execute commands yourself.
- Return the exact Bash command.
- Normal Bash syntax is allowed, including pipes, redirects, &&, ||,
  command substitution, and other shell operators.
- After execution, use the actual result to decide the next step.
- Never assume a command succeeded.
- If a command fails, analyze the actual error before continuing.
- Complete the task until finished or unable to continue.
- When finished, return an answer action.
- Keep answers concise.
"""

NORMAL_PROMPT = COMMON_PROMPT + """

Normal operation:
- For current/live/check/verify requests, prefer a live command.
- Use system context directly when it is sufficient.
- Answer only what is relevant to the user's request.
- Do not infer CPU load, health, performance, or other conditions
  unless the relevant evidence was collected.
- Preserve exact OS names, versions, codenames, kernel versions,
  paths, IP addresses, and process information.
"""

TROUBLESHOOTING_PROMPT = COMMON_PROMPT + """

Troubleshooting:
- Diagnose the reported problem using available evidence.
- Prefer read-only diagnostic commands initially.
- Clearly distinguish observed facts from hypotheses.
- Do not claim a root cause without supporting evidence.
- If a fix is required, propose the least invasive appropriate command.
- After making a change, verify the result.
- Stop when the problem is resolved or cannot be diagnosed further.
"""

def ask_ai(messages):
    input_chars = sum(
        len(message.get("content", ""))
        for message in messages
    )

    estimated_input_tokens = input_chars / 4

    print(
        f"[Token estimate] "
        f"input chars={input_chars}, "
        f"~{estimated_input_tokens:.0f} tokens"
    )

    response = client.chat.completions.create(
        model=model,
        messages=messages
    )

    output = response.choices[0].message.content

    output_chars = len(output)
    estimated_output_tokens = output_chars / 4

    print(
        f"[Token estimate] "
        f"output chars={output_chars}, "
        f"~{estimated_output_tokens:.0f} tokens"
    )

    return output

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
def compact_text(text, max_chars=MAX_RESULT_CHARS):
    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    half = max_chars // 2

    return (
        text[:half]
        + "\n...[middle of result truncated]...\n"
        + text[-half:]
    )

def compact_result(result):
    text = json.dumps(result, indent=2)
    return compact_text(text)

def handle_agent_turn(conversation, question):
    task_id = create_task(question)

    try:
        for step in range(MAX_STEPS):

            task_history = get_task_history(
                task_id,
                limit=MAX_TASK_HISTORY
            )

            messages = [
                conversation[0],
                {
                    "role": "system",
                    "content": (
                        "Current Linux system context:\n"
                        + json.dumps(
                            get_selected_context(question),
                            indent=2
                        )
                    )
                },
                {
                    "role": "user",
                    "content": (
                        "Original user task:\n"
                        + question
                    )
                }
            ]

            for item in task_history:
                output = item["output"] or ""

                if len(output) > MAX_RESULT_CHARS:
                    half = MAX_RESULT_CHARS // 2

                    output = (
                        output[:half]
                        + "\n...[middle of result truncated]...\n"
                        + output[-half:]
                    )

                return_code = item["return_code"]

                messages.append({
                    "role": "user",
                    "content": (
                        "COMPLETED COMMAND\n"
                        "The following command has already been executed. "
                        "Do not execute it again unless the task specifically "
                        "requires repeating it.\n\n"
                        f"Command:\n{item['command']}\n\n"
                        f"Return code: {return_code}\n\n"
                        f"Actual output:\n{output}"
                    )
                })

            if task_history:
                messages.append({
                    "role": "user",
                    "content": (
                        "The completed commands above are historical evidence "
                        "for this task. Do not repeat a successful command "
                        "unless its result is insufficient or the task requires "
                        "verification. Decide whether to return the final answer "
                        "or request one new command."
                    )
                })

            for index, message in enumerate(messages):
                content = message.get("content", "")
                print(
                    f"[Prompt part {index}] "
                    f"role={message.get('role')} "
                    f"chars={len(content)} "
                    f"~tokens={len(content) / 4:.0f}"
                )
            response = ask_ai(messages)

            try:
                action = json.loads(response)
            except json.JSONDecodeError:
                start = response.find("{")
                end = response.rfind("}")

                if start != -1 and end != -1 and end > start:
                    try:
                        action = json.loads(response[start:end + 1])
                    except json.JSONDecodeError:
                        print(f"\nAI returned invalid JSON:\n{response}\n")
                        update_task_status(task_id, "FAILED")
                        return
                else:
                    print(f"\nAI returned invalid JSON:\n{response}\n")
                    update_task_status(task_id, "FAILED")
                    return
                
            if action.get("action") == "answer":
                answer = action.get(
                    "content",
                    "No answer returned."
                )

                print(f"\nAI: {answer}\n")
                update_task_status(task_id, "COMPLETED")
                return

            if action.get("action") != "command":
                print("AI returned an invalid action.\n")
                update_task_status(task_id, "FAILED")
                return

            command = action.get("command")

            if not command:
                print("AI returned an empty command.\n")
                update_task_status(task_id, "FAILED")
                return

            print(f"\nAI wants to run: {command}")

            result = process_action(
                json.dumps({
                    "action": "command",
                    "command": command
                })
            )

            if result["type"] == "cancelled":
                add_command(
                    task_id,
                    command,
                    False,
                    status="CANCELLED"
                )

                update_task_status(
                    task_id,
                    "CANCELLED"
                )

                print("Task cancelled.\n")
                return

            if result["type"] == "rejected":
                add_command(
                    task_id,
                    command,
                    False,
                    status="FAILED"
                )

                update_task_status(
                    task_id,
                    "FAILED"
                )

                print(f"{result['message']}\n")
                return

            if result["type"] != "result":
                update_task_status(
                    task_id,
                    "FAILED"
                )

                print("Command execution failed.\n")
                return

            execution_result = result["result"]

            command_id = add_command(
                task_id,
                command,
                True,
                execution_result.get("return_code"),
                result.get("status", "FAILED")
            )

            output = compact_result(execution_result)

            add_result(
                command_id,
                output
            )

        update_task_status(
            task_id,
            "MAX_STEPS"
        )

        print(
            f"\nTask stopped after {MAX_STEPS} steps "
            "to prevent an endless loop.\n"
        )

    except Exception as error:
        update_task_status(
            task_id,
            "FAILED"
        )

        raise error

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
            "content": NORMAL_PROMPT
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
                "content": NORMAL_PROMPT
            }
        ]
        initialize_database()

        handle_agent_turn(
            conversation,
            prompt
        )

        return

    interactive_mode()


if __name__ == "__main__":
    main()
import json
import os
import sys

from dotenv import load_dotenv
from groq import Groq

from .action import parse_ai_response
from .context import get_selected_context
from .conversation import add_message
from .agent import process_action
from .task_state import (
    create_task,
    update_task_status,
    add_command,
    add_result,
    get_task_history,
    initialize_database,
)
MAX_STEPS = 20
MAX_TASK_HISTORY = 2
MAX_RESULT_CHARS = 4000

CONFIG_DIR = os.path.expanduser("~/.linux_ai_agent")
ENV_FILE = os.path.join(CONFIG_DIR, ".env")

load_dotenv(ENV_FILE)

load_dotenv(ENV_FILE)

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL")

if not api_key:
    raise ValueError(
        f"GROQ_API_KEY is not configured. "
        f"Expected configuration file: {ENV_FILE}"
    )

if not model:
    raise ValueError(
        f"GROQ_MODEL is not configured. "
        f"Expected configuration file: {ENV_FILE}"
    )

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
- Commands that are still running after the executor's five-second startup
  window are left running in the background. Use their returned PID and actual
  output to verify them; do not claim that they exited.
- When the task is to start a service, prefer launching it detached, redirect
  stdout/stderr to /dev/null or a requested log, and print its PID.
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
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages
        )
    except Exception as error:
        print(
            f"\nAI API request failed: "
            f"{type(error).__name__}: {error}\n"
        )
        return None

    output = response.choices[0].message.content

    if not output:
        print("\nAI returned an empty response.\n")
        return None

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
    if response is None:
        return None
    return parse_ai_response(response)
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
    add_message(
        conversation,
        "user",
        question
    )
    try:
        for step in range(MAX_STEPS):

            task_history = get_task_history(
                task_id,
                limit=MAX_TASK_HISTORY
            )

            messages = []

            # Keep the main AI instruction as the first system message.
            if conversation and conversation[0]["role"] == "system":
                messages.append(conversation[0])

            # Add current system context immediately after the main prompt.
            messages.append({
                "role": "system",
                "content": (
                    "Current Linux system context:\n"
                    + json.dumps(
                        get_selected_context(question),
                        indent=2
                    )
                )
            })

            # Add previous conversation history.
            messages.extend(conversation[1:])

            for item in task_history:
                output = compact_text(item["output"] or "")
                return_code = item["return_code"]
                status = item["status"]

                if status == "RUNNING":
                    command_label = "COMMAND STILL RUNNING"
                    result_details = (
                        "The command did not exit during its startup window "
                        "and was left running in the background. Do not "
                        "repeat it; inspect or verify the process using "
                        "its actual output and PID."
                    )
                else:
                    command_label = "COMMAND EXECUTION RESULT"
                    result_details = (
                        "Do not repeat a successful command unless its result "
                        "is insufficient or the task requires verification."
                    )

                messages.append({
                    "role": "user",
                    "content": (
                        f"{command_label}\n"
                        f"{result_details}\n\n"
                        f"Command:\n{item['command']}\n\n"
                        f"Status: {status}\n\n"
                        f"Return code: {return_code}\n\n"
                        f"Actual output:\n{output}"
                    )
                })

            if task_history:
                messages.append({
                    "role": "user",
                    "content": (
                        "The command results above are evidence for this task. "
                        "Do not repeat a successful command unless its result "
                        "is insufficient or the task requires verification. "
                        "Decide whether to return the final answer or request "
                        "one new command."
                    )
                })

            response = ask_ai(messages)
            if response is None:
                update_task_status(task_id, "FAILED")
                return
            
            action = parse_ai_response(response)
            if action is None:
                print(
                    "\nAI returned an invalid response/action."
                    f"\nRaw response:\n{response}\n"
                )
                update_task_status(task_id, "FAILED")
                return

            if not isinstance(action, dict):
                print(
                    "\nAI returned an invalid action."
                    f"\nParsed action: {action}"
                    f"\nRaw response: {response}\n"
                )
                update_task_status(
                    task_id,
                    "FAILED"
                )
                return

            if action.get("action") == "answer":
                answer = action.get(
                    "content",
                    "No answer returned."
                )

                if not isinstance(answer, str):
                    print(
                        "\nAI returned an invalid answer."
                        f"\nParsed action: {action}"
                        f"\nRaw response: {response}\n"
                    )
                    update_task_status(
                        task_id,
                        "FAILED"
                    )
                    return

                print(f"\nAI: {answer}\n")

                add_message(
                    conversation,
                    "assistant",
                    answer
                )

                update_task_status(
                    task_id,
                    "COMPLETED"
                )
                return

            if action.get("action") != "command":
                print(
                    "\nAI returned an invalid action."
                    f"\nParsed action: {action}"
                    f"\nRaw response: {response}\n"
                )
                update_task_status(
                    task_id,
                    "FAILED"
                )
                return

            command = action.get("command")

            if not isinstance(command, str) or not command.strip():
                print(
                    "\nAI returned an empty command."
                    f"\nParsed action: {action}"
                    f"\nRaw response: {response}\n"
                )
                update_task_status(
                    task_id,
                    "FAILED"
                )
                return

            command = command.strip()

            print(f"\nAI wants to run: {command}")
            add_message(
                conversation,
                "assistant",
                json.dumps({
                    "action": "command",
                    "command": command
                })
            )
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
            if result["status"] == "RUNNING":
                print(f"\n{execution_result['message']}\n")

            conversation_result = compact_result(execution_result)

            add_message(
                conversation,
                "user",
                (
                    f"Command execution status: {result['status']}\n"
                    f"Command: {command}\n"
                    f"Return code: "
                    f"{execution_result.get('return_code')}\n"
                    f"Output:\n{conversation_result}"
                )
            )
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
        
    except KeyboardInterrupt:
        update_task_status(
            task_id,
            "CANCELLED"
        )

        print("\nTask cancelled.\n")
        return
    
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
            "content": extra_prompt or NORMAL_PROMPT
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
            handle_agent_turn(
                conversation,
                user_input
            )

        except Exception as error:
            print(f"Error: {error}\n")


def main():
    initialize_database()
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

        handle_agent_turn(
            conversation,
            prompt
        )

        return

    interactive_mode()


if __name__ == "__main__":
    main()
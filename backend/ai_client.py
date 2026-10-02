import os
import sys

from dotenv import load_dotenv
from groq import Groq


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
- Do not discuss Windows or macOS unless explicitly asked.
- Never execute commands. Only suggest commands.
- For destructive commands, prefer the least destructive appropriate option.
- Do not suggest rm -rf unless force deletion is specifically required.
- Warn briefly before potentially destructive operations.
- If the request is ambiguous, ask a short clarification question.
"""


def ask_ai(messages):

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        reasoning_effort="none"
    )

    return response.choices[0].message.content


def single_question(prompt):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    return ask_ai(messages)


def interactive_mode():

    messages = [
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
            user_input = input("You: ").strip()

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        messages.append(
            {
                "role": "user",
                "content": user_input
            }
        )

        try:
            answer = ask_ai(messages)

            print(f"AI: {answer}\n")

            messages.append(
                {
                    "role": "assistant",
                    "content": answer
                }
            )

        except Exception as error:

            print(f"Error: {error}\n")

            # Remove the unanswered user message
            messages.pop()


def main():

    if len(sys.argv) > 1:

        prompt = " ".join(sys.argv[1:])

        answer = single_question(prompt)

        print(answer)

    else:

        interactive_mode()


if __name__ == "__main__":
    main()
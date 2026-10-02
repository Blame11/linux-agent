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


def ask_ai(prompt):

    response = client.chat.completions.create(
        model=model,
        messages=[
    {
        "role": "system",
        "content": """You are a Linux terminal assistant.

Your job is to help users with Linux commands and troubleshooting.

Rules:
- Assume Linux with Bash unless the user says otherwise.
- Be concise.
- Give the most appropriate command first.
- Do not use Markdown code fences for commands.
- Do not provide unnecessary explanations.
- Do not discuss Windows or macOS unless explicitly asked.
- If a command is potentially destructive, give a short warning.
- If the user's request is ambiguous, ask a short clarification question.
- For simple questions, answer in 1-4 lines.
- Never execute commands yourself. Only suggest commands.
"""
    },
    {
        "role": "user",
        "content": prompt
    }
],
        reasoning_effort="none"
    )

    return response.choices[0].message.content


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: ai \"your question\"")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])

    answer = ask_ai(prompt)

    print(answer)
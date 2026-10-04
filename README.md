# Linux AI Agent

Linux AI Agent is a Bash-oriented assistant for Linux terminal tasks. It sends a
user request and selected Linux context to GroqCloud, asks the model for either
an answer or one Bash command, and requires the user to approve a command before
the local executor runs it. The agent records task and command results in
SQLite and can use those results to continue a multi-step task.

The project is an early-stage command-line tool, not a web application. Linux
commands and their observed output are the source of truth; the AI's role is to
interpret evidence and suggest the next step.

## Implementation status

- **COMPLETED** — the basic Bash-to-Groq request, user-approved Bash execution,
  result feedback, and SQLite persistence loop.
- **IN PROGRESS** — reliability work, including error handling, history,
  malformed-response handling, and prompt/token optimization.
- **PLANNED** — broader Linux diagnostics, persistent intelligence, and more
  advanced investigate/observe/verify workflows.
- **SKIPPED** — Prompt Guard, command allowlists, and a broader additional
  security model for now.

These labels describe the current project state. The completed core still has
the limitations called out below.

## Features

**COMPLETED — implemented behavior in the current source:**

- Bash launchers for a one-shot request (`ai "..."`), an interactive prompt
  (`ai`), and a troubleshooting entry point (`ai --troubleshoot`).
- GroqCloud chat completions using the Groq Python client. The model and API
  key are read from `GROQ_MODEL` and `GROQ_API_KEY`.
- A static Linux context (OS, kernel, architecture, hostname, user, and shell)
  cached in `~/.linux_ai_context.json`; dynamic context is gathered selectively
  for a request.
- Dynamic context providers for the current directory, root filesystem
  capacity, load and memory, listening sockets, top CPU/memory processes, and
  running systemd services.
- Word-aware context keyword matching, which avoids matching a keyword merely
  because it appears inside another word.
- JSON actions for a command or an answer:

  ```json
  {"action":"command","command":"..."}
  ```

  ```json
  {"action":"answer","content":"..."}
  ```

- Response parsing for valid JSON actions, JSON actions embedded in text, and
  explicit `execute_bash` tool-call markup. A recovered tool call becomes a
  proposed command and still requires the normal `y/N` approval.
- A prompt policy that asks for one command at a time, requires approval, and
  tells the model to use actual results, preserve observed values, and not
  invent output.
- A confirmation prompt before each command. Only `y` or `yes` approves;
  anything else cancels the task.
- Bash execution through `/bin/bash`, including pipes and other shell syntax,
  with captured stdout/stderr and a return code. If a command has not exited
  after a five-second startup window, it is left running in the background
  and its PID and startup output are returned.
- A task loop capped at 20 command steps. After each approved command, its
  result is recorded and supplied to the model on the next step.
- SQLite records for tasks, commands, approval state, command status, return
  codes, and captured results.
- Bounded output handling and approximate character-based token estimates for
  development visibility.

These are implementation facts, not a guarantee that every host tool or
provider request will succeed. See [Current limitations](#current-limitations)
for gaps and partial behavior.

## Architecture

```text
User
  |
  v
CLI: ai
  |
  v
backend/ai_client.py
  |                         \
  | request + selected       \ task / command / result history
  | Linux context             v
  v                       SQLite
GroqCloud (GROQ_MODEL)       ~/.linux_ai_agent/agent.db
  |
  | JSON answer or one command
  v
Approval prompt -- no --> cancel and record
  |
 yes
  v
/bin/bash executor
  |
  | actual output + return code
  +---------------------------> task history and next AI step
```

## How the agent works

1. The CLI receives a request, or waits for a request in interactive mode.
2. The backend attaches static system facts and only the dynamic context
   categories selected for that request.
3. GroqCloud returns either an answer or one command in the expected JSON
   action shape.
4. For a command, the exact command text is displayed and awaits explicit
   approval.
5. An approved command runs locally through Bash. The executor captures its
   output and return code. If it is still running after five seconds, the
   executor leaves it running in the background and returns its PID and
   startup output so the agent can continue with verification.
6. The task and command result are stored in SQLite. For another step, the
   agent sends recent command history and actual results back to the model.
7. The loop ends with an answer, a cancellation/failure, or the 20-step limit.

The application does not treat a suggested command as evidence that it ran or
succeeded. The result and return code are the evidence used for subsequent
steps.

## Project structure

```text
linux_ai_agent/
├── backend/
│   ├── action.py          # Parse command actions
│   ├── agent.py           # Approval, execution, and result status
│   ├── ai_client.py       # CLI flow, prompts, Groq calls, and task loop
│   ├── approval.py        # User confirmation
│   ├── command.py         # Text command extraction helper
│   ├── command_safety.py  # Empty-command check and approval classification
│   ├── context.py         # Linux context providers, cache, and selection
│   ├── conversation.py   # Message-list helper
│   ├── executor.py        # Bash subprocess execution
│   └── task_state.py      # SQLite schema and persistence
├── bash/
│   ├── ai                # Main CLI launcher
│   └── ai-context        # Print static Linux context
├── .env                  # Local configuration; ignored by Git
├── .gitignore
├── LICENSE
└── LICENSE.txt
```

There is no dependency manifest or automated test suite in the current tracked
project.

## Requirements

- Linux with `/bin/bash` and Python 3.
- A GroqCloud account and API key.
- Python packages `groq` and `python-dotenv`.
- The Bash launchers currently expect the project at
  `~/linux_ai_agent`.
- Some optional context providers use host commands such as `free`, `ss`,
  `ps`, and `systemctl`. Context may be unavailable or reported as unknown
  where a command or service manager is absent.

The development environment noted for this project is Ubuntu 26.04.1 LTS on
WSL2.

## Installation

The launchers set `PROJECT_DIR="$HOME/linux_ai_agent"`, so place or clone the
project at that location:

```bash
git clone https://github.com/Blame11/linux-agent.git "$HOME/linux_ai_agent"
cd "$HOME/linux_ai_agent"

python3 -m venv venv
source venv/bin/activate
python -m pip install groq python-dotenv
```

Make the `ai` launcher available in the current shell:

```bash
export PATH="$HOME/linux_ai_agent/bash:$PATH"
```

To make this available in future Bash sessions, add that `export` line to
`~/.bashrc`, then open a new shell or source the file.

Initialize task storage before using interactive or troubleshooting mode on a
fresh installation:

```bash
python backend/task_state.py
```

The one-shot CLI initializes the database itself. The explicit initialization
step is needed because the current interactive path does not initialize the
SQLite schema.

## Environment configuration

Create a local `.env` file in the project root. Do not commit or publish the
API key:

```dotenv
GROQ_API_KEY=<your GroqCloud API key>
GROQ_MODEL=qwen/qwen3.8-27b
```

`.env` is ignored by Git. The application requires both variables and raises an
error if either is unset; there is no model fallback in the source. Keep the
key private and replace the placeholder locally with the key from your
provider.

## Running the agent

With the project installed at `~/linux_ai_agent` and `bash/` on `PATH`, send a
one-shot request:

```bash
ai "what is my current kernel version?"
```

The request runs as a task. The agent can answer from context or propose a
command such as `uname -r`; it will show the command and wait for approval
before execution.

The `ai-context` helper prints the static system facts directly:

```bash
ai-context
```

It does not print all dynamic providers or select context based on a question.

## Interactive mode

Start the prompt without arguments:

```bash
ai
```

Enter one request per prompt. Type `exit` or `quit` to leave. To paste
multi-line terminal output into a prompt, enter `paste`, paste the text, then
enter `END` on its own line.

Interactive requests are processed as separate tasks; prior requests are not
currently added to later turns as conversational memory. On a new installation,
initialize SQLite first as shown above.

## Troubleshooting mode

The troubleshooting entry point is:

```bash
ai --troubleshoot
```

It opens the interactive prompt. A troubleshooting-specific prompt is defined
in the source, but the current task loop sends only the first system prompt on
each request. As a result, this entry point currently does not reliably apply
the specialized troubleshooting instructions and behaves like normal mode.
This is a known limitation, not a completed troubleshooting workflow.

## Command approval behavior

Every non-empty proposed command is displayed before execution. The user must
enter `y` or `yes` to approve it. Any other response rejects the execution and
cancels the task. The action parser strips surrounding whitespace; otherwise
the command is passed through to Bash without an allowlist or shell-syntax
rewrite.

The current command classifier labels non-empty commands `USER_APPROVAL`; it
does not perform a meaningful risk assessment. Approval is a user checkpoint,
not a security sandbox or a guarantee that an approved command is safe.

## Example interactions

Read-only kernel check:

```text
You: what is my current kernel version?
AI wants to run: uname -r
Command: uname -r
Risk: USER_APPROVAL
Execute this command? [y/N]: y
AI: The kernel version is <value returned by uname -r>.
```

The value is supplied by the host command at runtime; the example does not
assert a specific kernel version.

Illustrative multi-step request:

```text
You: find why the root filesystem is nearly full and show me the largest top-level directories
AI wants to run: df -h /
...
Execute this command? [y/N]: y
... actual output is returned to the model ...
AI wants to run: sudo du -xhd1 / 2>/dev/null | sort -h
...
Execute this command? [y/N]: y
... actual output is returned to the model ...
AI: The observed output shows ...
```

The commands and number of steps are model-generated and can differ. Each
command requires its own approval; `sudo` is not automatically granted.

## Context selection

Static context is always attached to a request and cached at
`~/.linux_ai_context.json`. It includes the OS name, kernel, architecture,
hostname, current user, and shell. The static cache is created on first use and
is not automatically refreshed by the current code.

Dynamic context is selected using word-aware matching against the user's
question. For example, storage terms can select root filesystem usage, and a
question mentioning a port can select listening information for that port.
The implemented categories are:

| Category | Current collected information |
| --- | --- |
| Location | Current working directory |
| Storage | Capacity and usage for the root filesystem |
| Resources | Load average and memory; memory uses `free` |
| Network | Listening sockets from `ss`, optionally narrowed to a mentioned port |
| Processes | Up to five top CPU and memory processes from `ps` |
| Services | Running systemd services from `systemctl` |

The selector avoids sending unrelated dynamic context, but it is a keyword
selector rather than a semantic classifier. Logs, package inventories, and
general-purpose diagnostics are not collected as context providers today; the
model may still propose a command to inspect them, subject to approval.

## SQLite and task history

The database is stored at:

```text
~/.linux_ai_agent/agent.db
```

It contains `tasks`, `commands`, and `results` tables. Records include the
original task, command text, whether it was approved, command status, return
code when available, result output, and timestamps. Command statuses include
`RUNNING`, `SUCCESS`, `FAILED`, and `CANCELLED` (older records may also contain
`TIMEOUT`). Tasks also receive overall statuses such as `RUNNING`, `COMPLETED`,
`FAILED`, `CANCELLED`, or `MAX_STEPS`.

The current agent supplies at most the latest two command records from the
active task back to the model. There is no user-facing history browser or
cross-task memory interface yet.

## Configuration and output limits

- `GROQ_API_KEY`: required GroqCloud credential; keep it out of source control.
- `GROQ_MODEL`: required model name; the documented current value is
  `qwen/qwen3.8-27b`.
- `~/.linux_ai_context.json`: cached static system context.
- `~/.linux_ai_agent/agent.db`: task, command, and result history.

The executor truncates combined stdout/stderr after 12,000 characters,
retaining the beginning. Stored result text is further limited to about 4,000
characters, retaining the beginning and end with a truncation marker. These are
deterministic character limits, not semantic compression. Token figures printed
by the client are rough estimates based on four characters per token, not
provider-reported usage.

## Development and testing

Backend modules are plain Python files, and the Bash wrappers live in `bash/`.
There is no tracked requirements file, test configuration, or automated test
suite yet. A syntax smoke check can be run in the project virtual environment:

```bash
python -m compileall backend
```

For manual testing, use a disposable Linux environment, a test GroqCloud key,
and read-only requests first. Check that the exact proposed command is shown,
that declining it cancels execution, and that approved command output and
return codes are recorded in SQLite. Do not use production data to test
destructive commands.

## Current limitations

- `ai --troubleshoot` opens an interactive prompt but currently does not pass
  its specialized prompt into each task request: the task loop builds request
  messages from only the first system prompt in the conversation.
- The one-shot CLI initializes SQLite, but interactive and troubleshooting
  modes do not. On a fresh install, initialize the database with
  `python backend/task_state.py` before starting those modes.
- There is no cross-request conversational memory or user-facing task history
  browser, although task history is stored in SQLite and used internally for
  the active task.
- Groq request exceptions are not handled specifically at the API call. The
  task-level exception handler marks the task `FAILED` and propagates the
  exception; interactive mode catches it and prints an error, while the
  one-shot path has no equivalent outer CLI handler.
- AI output parsing accepts JSON and attempts to extract an embedded JSON
  object when needed. Comprehensive action-schema validation is not
  implemented.
- Command approval is not an allowlist, sandbox, or complete security model.
- Context providers cover a limited set of host facts and commonly available
  Linux tools; availability and permissions vary by distribution and WSL
  configuration.
- Command output is bounded: the executor truncates combined output after
  12,000 characters, while stored results retain the beginning and end within
  a 4,000-character limit. Token counts are approximate character-based
  estimates.
- No automated test suite or formal packaging/install metadata is included.

## Roadmap

Current implementation status and developer-facing work items are maintained
in [PLAN.md](./PLAN.md). In short, the core loop is present; reliability work is
in progress; expanded Linux diagnostics and persistent intelligence remain
planned. Prompt Guard and command allowlists are skipped for now.

## License

The project includes the Mozilla Public License, Version 2.0. See
[LICENSE](./LICENSE) and [LICENSE.txt](./LICENSE.txt).

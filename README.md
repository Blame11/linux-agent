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

- CLI entry points for a one-shot request (`ai "..."`), an interactive prompt
  (`ai`), a troubleshooting entry point (`ai --troubleshoot`), and static
  context output (`ai-context`).
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

- Response parsing for valid JSON actions and standalone explicit
  `execute_bash` tool-call markup. A recovered tool call becomes a proposed
  command and still requires the normal `y/N` approval. JSON examples embedded
  in prose are treated as prose, not executable actions.
- A prompt policy that asks for one command at a time, requires approval, and
  tells the model to use actual results, preserve observed values, and not
  invent output.
- A confirmation prompt before each command. Only `y` or `yes` approves;
  anything else cancels the task.
- Bash execution through `/bin/bash`, including pipes and other shell syntax,
  with captured stdout/stderr and a return code. If a command has not exited
  after a five-second startup window, it is left running in the background
  and its PID, process group, startup output, and private log path are returned.
  A background monitor refreshes its status and output independently of AI
  turns. Long-running command logs are capped at 1 MiB and kept for up to
  seven days after completion. Logs for commands that finish within the
  startup window are removed after their output has been recorded.
- A task loop capped at 20 command steps. After each approved command, its
  result is recorded and supplied to the model on the next step.
- SQLite records for tasks, commands, approval state, command status, return
  codes, and captured results.
- Bounded command output and task-result handling.

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
   executor leaves it running in the background and returns its PID, process
   group, private log path, and startup output so the agent can continue with
   verification. A detached monitor refreshes status and output every second.
   Long-running command logs are capped at 1 MiB and removed seven days after
   completion; short-command temporary logs are removed after output capture.
   Process-group signals and log reads still require approved shell commands.
6. The task and command result are stored in SQLite. For another step, the
   agent sends recent command history and actual results back to the model.
7. The loop ends with an answer, a cancellation/failure, or the 20-step limit.

The application does not treat a suggested command as evidence that it ran or
succeeded. The result and return code are the evidence used for subsequent
steps.

For the complete current module reference, request flow, and architecture
diagrams, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Requirements

- Linux with `/bin/bash` and Python 3.14 or newer.
- A GroqCloud account and API key.
- `sudo` access to install the application system-wide. The installer creates
  an isolated environment under `/opt/linux-ai-agent/venv` and installs the
  Python dependencies there.
- Some optional context providers use host commands such as `free`, `ss`,
  `ps`, and `systemctl`. Context may be unavailable or reported as unknown
  where a command or service manager is absent.

The development environment noted for this project is Ubuntu 26.04.1 LTS on
WSL2.

## Installation

Clone the repository wherever you prefer, then run the included installer:

```bash
git clone https://github.com/Blame11/linux-agent.git "$HOME/linux-agent"
cd "$HOME/linux-agent"
sudo ./install.sh
```

The installer creates its environment at `/opt/linux-ai-agent/venv` and
installs `ai` and `ai-context` under `/usr/local/bin`. It refuses to overwrite
an existing path unless it is already the matching symlink managed by this
installer. User configuration and task data remain under
`~/.linux_ai_agent/`. To update, pull the latest changes and run
`sudo ./install.sh` again.

## Environment configuration

Create `~/.linux_ai_agent/.env` for the user account that will run `ai`. Do not
put this file in the repository or expose the API key:

```dotenv
GROQ_API_KEY=<your GroqCloud API key>
GROQ_MODEL=qwen/qwen3.8-27b
```

The application requires both variables and raises an error if either is
unset; there is no model fallback in the source. Keep this file private with
permissions such as `chmod 600 ~/.linux_ai_agent/.env`, and replace the
placeholder locally with the key from your provider. Run `ai` as that user,
not with `sudo`; `ai-context` does not require Groq credentials.

## Running the agent

After installation, send a one-shot request:

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
currently added to later turns as conversational memory. SQLite is initialized
when the CLI starts.

## Troubleshooting mode

The troubleshooting entry point is:

```bash
ai --troubleshoot
```

It opens the interactive prompt with troubleshooting-specific instructions.

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

It contains `tasks`, `commands`, `results`, and `processes` tables. Records
include the original task, command text, whether it was approved, command
status, return code when available, result output, process identifiers, log
paths, and timestamps. Command statuses include `RUNNING`, `SUCCESS`, `FAILED`,
`STOPPED`, and `CANCELLED` (older records may also contain `TIMEOUT`). Tasks
also receive overall statuses such as `RUNNING`, `COMPLETED`, `FAILED`,
`CANCELLED`, or `MAX_STEPS`.

The current agent supplies at most the latest two command records from the
active task back to the model. There is no user-facing history browser or
cross-task memory interface yet.

## Configuration and output limits

- `GROQ_API_KEY`: required GroqCloud credential; keep it out of source control.
- `GROQ_MODEL`: required model name; the documented current value is
  `qwen/qwen3.8-27b`.
- `~/.linux_ai_context.json`: cached static system context.
- `~/.linux_ai_agent/agent.db`: task, command, and result history.

For a command that completes in its five-second startup window, the executor
returns up to 12,000 characters of combined output. A longer-running command
continues writing to a private log capped at 1 MiB; excess output is discarded
after a truncation marker is written. The detached monitor refreshes its
process state and latest output every second. Logs for long-running commands
are removed seven days after completion.

Stored result text is further limited to about 4,000 characters, retaining the
beginning and end with a truncation marker. These are deterministic limits,
not semantic compression.

## Development and testing

Backend modules are plain Python files and package metadata is in
`pyproject.toml`. Run the tests with:

```bash
python -m pytest -q
```

For manual testing, use a disposable Linux environment, a test GroqCloud key,
and read-only requests first. Check that the exact proposed command is shown,
that declining it cancels execution, and that approved command output and
return codes are recorded in SQLite. Do not use production data to test
destructive commands.

## Current limitations

- There is no cross-request conversational memory or user-facing task history
  browser, although task history is stored in SQLite and used internally for
  the active task.
- Groq request exceptions are not handled specifically at the API call. The
  task-level exception handler marks the task `FAILED` and propagates the
  exception; interactive mode catches it and prints an error, while the
  one-shot path has no equivalent outer CLI handler.
- AI output parsing accepts valid JSON actions and standalone recognized
  `execute_bash` tool-call blocks. JSON examples embedded in prose are treated
  as prose; comprehensive action-schema validation is not implemented.
- Command approval is not an allowlist, sandbox, or complete security model.
- Context providers cover a limited set of host facts and commonly available
  Linux tools; availability and permissions vary by distribution and WSL
  configuration.
- Command output is bounded: completed command output is limited to 12,000
  characters, persistent process logs to 1 MiB, and stored result text to
  about 4,000 characters.
- The `USER_APPROVAL` command label is not a risk assessment. Every non-empty
  command still requires explicit user approval, but approval is not a
  sandbox or guarantee that a command is safe.

## Roadmap

Current implementation status and developer-facing work items are maintained
in [PLAN.md](./PLAN.md). In short, the core loop is present; reliability work is
in progress; expanded Linux diagnostics and persistent intelligence remain
planned. Prompt Guard and command allowlists are skipped for now.

## License

The project includes the Mozilla Public License, Version 2.0. See
[LICENSE](./LICENSE) and [LICENSE.txt](./LICENSE.txt).

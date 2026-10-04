# Development Plan

This plan describes the current Bash/Linux agent and possible next steps. The
status labels distinguish existing code from work that is incomplete or only
being considered. No phase in this plan is permission to change the project
architecture or introduce an unrequested dependency.

## PHASE 1 — CORE AGENT

**Status: COMPLETED**

The repository has a working baseline for the core request/approval/execute
loop:

- Bash interface:
  - `ai "question"` sends a one-shot request.
  - `ai` opens an interactive prompt.
  - `ai --troubleshoot` opens an interactive prompt with troubleshooting
    instructions.
- GroqCloud integration through the Groq Python client, with model and API
  credential loaded from `GROQ_MODEL` and `GROQ_API_KEY`.
- Linux context with cached static facts and dynamic providers for location,
  storage, resources, network sockets, processes, and running services.
- Selective dynamic context chosen through word-aware keyword matching.
- Structured JSON actions for either a command or a final answer.
- User approval before every non-empty command is executed.
- Bash executor using `/bin/bash`, capturing combined stdout/stderr and return
  codes, and leaving long-running commands active with their PID reported.
- SQLite state for tasks, commands, approval values, command status, return
  codes, output, and timestamps.
- A multi-step loop that feeds actual execution results and return codes back
  to the model, with a 20-step cap.
- Result capture with bounded output and deterministic character truncation.

**Completion boundary:** this phase means the basic end-to-end mechanisms are
present. It does not mean every CLI path is initialized correctly on a fresh
database, that troubleshooting-specific instructions are currently applied,
or that command execution is sandboxed. Those limitations remain explicit.

## PHASE 2 — RELIABILITY

**Status: IN PROGRESS**

The code already contains basic mechanisms in several of these areas. The work
remaining is to make them consistent, observable, and tested rather than to
claim the concerns are fully solved.

| Area | Existing baseline | Remaining reliability work |
| --- | --- | --- |
| API error handling | A task-level exception path marks the task failed and re-raises; interactive mode prints an error. | Classify provider/configuration/network failures clearly; provide useful CLI feedback and bounded recovery where appropriate. |
| Better task history | SQLite stores tasks, commands, and results; current-task context uses up to two prior command records. | Add a deliberate way to inspect/search task history and improve task summaries without treating stale data as current evidence. |
| Deterministic output compression | Executor output has a character cap; persisted results retain beginning and end above the history limit. | Consolidate duplicated truncation logic, define boundary behavior, and cover it with tests. This is truncation, not semantic compression. |
| Long-running commands | Commands still active after five seconds are left running with a private, 1 MiB-capped log and recorded PID/process group. A detached monitor refreshes status and captured output each second; long-running command logs are removed seven days after completion. | Add a user-facing process-list/management interface and configurable retention if needed. |
| Execution-state tracking | Tasks and commands persist statuses, approval, return codes, and output; active commands use `RUNNING`. | Define and validate state transitions; address unset return codes for active and cancelled commands consistently. |
| Malformed AI response handling | The client normalizes valid JSON actions, plain-text answers, and standalone explicit `execute_bash` tool-call markup; malformed structured responses fail without executing. JSON embedded in prose is not interpreted as an action. Recovered commands still pass through user approval. | Expand provider-format coverage and keep parser behavior consistent across all AI response paths. |
| Robust command execution | Commands run with Bash syntax, captured output, and generic exception handling. | Test launch failures, large output, and terminal interruption; ensure recorded evidence always matches what was executed. |
| Prompt/token optimization | Prompts are separated into common/normal/troubleshooting forms; prompt and token-estimate debug messages are not printed to the terminal. | Reduce duplicated context/history construction and evaluate prompt size without presenting estimates as exact token usage. |

The SQLite schema is initialized when the CLI starts, and `--troubleshoot`
passes its troubleshooting prompt to interactive tasks. Continue expanding
automated coverage as reliability work proceeds.

## PHASE 3 — SECURITY

**Status: SKIPPED FOR NOW**

- Prompt Guard is not implemented.
- Command allowlists are not planned at this stage.
- A broader additional security model is deferred.
- The existing approval prompt is a user checkpoint only. The current command
  classification is not a risk analysis, and Bash execution is not sandboxed.

Do not implement work from this phase as part of reliability or Linux
capability work. Revisit the scope only if the project direction changes.

## PHASE 4 — LINUX CAPABILITIES

**Status: PLANNED**

Expand useful evidence gathering in focused, reusable Linux context providers
and diagnostic flows:

- Logs: selected journal or service logs, with clear time/window limits.
- Packages: package-manager identification and package inspection.
- Services: service-specific state and recent failure details, beyond the
  current list of running systemd services.
- Network diagnostics: targeted interfaces, routes, DNS, and connectivity
  evidence, beyond the current listening-socket snapshot.
- Processes: targeted process details in addition to the current top CPU and
  memory lists.
- System information: fill gaps in the current OS/kernel/host context.
- Storage: filesystem and directory-level evidence beyond root filesystem
  capacity.
- Resources: focused CPU and memory inspection beyond current load and memory
  figures.

These are potential extensions, not current providers unless listed in
[README.md](./README.md). Keep diagnosis evidence-driven and modular. Do not
turn the agent into a large hardcoded `if`/`else` troubleshooting tree.

## PHASE 5 — PERSISTENT INTELLIGENCE

**Status: PLANNED**

- Investigate semantic compression only after deterministic truncation and
  task summaries are measured against real usage.
- Improve task memory while retaining the distinction between historical
  observations and live system state.
- Reuse relevant troubleshooting evidence when it is demonstrably applicable,
  with provenance and age made explicit.
- Improve historical context selection so irrelevant old command output is
  not sent to the model.
- Consider embeddings/vector search only if later evidence shows ordinary
  SQLite history lookup is insufficient. This is an optional evaluation, not a
  current feature or immediate commitment; no vector database or RAG system
  exists.

No semantic compression, reusable troubleshooting memory, embedding index, or
vector search is implemented today.

## PHASE 6 — ADVANCED AGENT BEHAVIOR

**Status: PLANNED**

Target workflow:

```text
Understand
    → Investigate
    → Observe
    → Reason
    → Command
    → Approval
    → Execute
    → Observe
    → Repeat
    → Verify
    → Final answer
```

Possible future workflows include:

- Diagnosing Apache by gathering service state and relevant logs, proposing
  one change at a time, and verifying the observed result.
- Disk troubleshooting by locating filesystem pressure, investigating
  directory usage, and confirming the effect of any user-approved action.
- Network troubleshooting by collecting interface, route, DNS, and
  connectivity evidence before proposing a targeted next step.
- Service troubleshooting by inspecting service status and recent failure
  evidence, then verifying recovery after an approved change.

These are target workflows, not implemented claims. They should use the same
evidence-first approval loop, keep Linux command output as the source of truth,
and avoid assuming either that a command succeeded or that a proposed fix
resolved the problem. Keep the architecture simple and modular.

## PHASE 7 — MODEL PROVIDERS

**Status: PLANNED**

The current implementation uses GroqCloud. Provider configuration and local
model-server support are not implemented.

Potential work:

- Make the provider, API base URL, and model configurable without changing the
  request/response handling contract used by the agent.
- Support OpenAI-compatible local servers, such as Ollama, LM Studio, or
  vLLM, where their API compatibility permits.
- Make API-key authentication optional for endpoints that do not require it;
  keep credentials out of source control and user-visible logs.
- Report connection, authentication, and model errors clearly, including
  unreachable local endpoints.
- Test provider-specific request/response behavior and configuration while
  preserving the current GroqCloud path.

Provider selection must not bypass the existing approval step: every
non-empty proposed command must still be shown to the user and explicitly
approved before local Bash execution. These are planning goals, not supported
configuration or behavior today.

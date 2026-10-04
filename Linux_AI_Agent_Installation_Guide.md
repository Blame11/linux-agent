# Linux AI Agent — Installation Guide

## Requirements

- Linux
- Python 3.14 or newer
- Python `venv` support
- `sudo` access
- A Groq API key

## 1. Clone the Repository

```bash
git clone https://github.com/Blame11/linux-agent.git
cd linux-agent
```

## 2. Configure `.env`

The API credentials are stored outside the Git repository.

Create the configuration directory:

```bash
mkdir -p ~/.linux_ai_agent
```

Create the environment file:

```bash
nano ~/.linux_ai_agent/.env
```

Add:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=qwen/qwen3.8-27b
```

Replace `your_groq_api_key_here` with your actual Groq API key.

Save the file, then protect it:

```bash
chmod 600 ~/.linux_ai_agent/.env
```

Verify:

```bash
ls -l ~/.linux_ai_agent/.env
```

It should have permissions similar to:

```text
-rw------- ... ~/.linux_ai_agent/.env
```

**Never commit or share this file or your API key.**

## 3. Install the Agent

From the cloned repository:

```bash
sudo ./install.sh
```

The installer:

1. Checks for Python 3.14+
2. Checks Python `venv` support
3. Creates the application environment at `/opt/linux-ai-agent/venv`
4. Installs the Python package and dependencies
5. Installs the `ai` and `ai-context` commands

The commands are linked at:

```text
/usr/local/bin/ai
/usr/local/bin/ai-context
```

## 4. Verify Installation

Check the commands:

```bash
which ai
which ai-context
```

Then:

```bash
ai-context
```

This displays the Linux system context available to the agent.

## 5. Run the Agent

Start interactive mode:

```bash
ai
```

Or ask a question directly:

```bash
ai "what is my current kernel version?"
```

When the agent proposes a command, it asks for your authorization before execution.

Example:

```text
Proposed command:
uname -r

Execute this command? [y/N]:
```

Enter `y` to execute or `n` to reject.

## 6. Runtime and Configuration Files

User-specific configuration and runtime data are stored under:

```text
~/.linux_ai_agent/
```

Important files include:

```text
~/.linux_ai_agent/.env
~/.linux_ai_agent/agent.db
```

The project also uses a local context cache:

```text
.linux_ai_context.json
```

This cache is ignored by Git.

## 7. Updating the Installation

Pull the latest code and reinstall:

```bash
cd ~/linux-agent
git pull
sudo ./install.sh
```

Then verify:

```bash
ai-context
```

## 8. Troubleshooting

### Check Python

```bash
python3 --version
```

Python 3.14 or newer is required.

### Check `.env`

```bash
ls -l ~/.linux_ai_agent/.env
```

If required:

```bash
chmod 600 ~/.linux_ai_agent/.env
```

### Check installed commands

```bash
which ai
which ai-context
```

### Check the installed environment

```bash
ls -l /opt/linux-ai-agent/venv/bin/ai
ls -l /opt/linux-ai-agent/venv/bin/ai-context
```

### Test the agent

```bash
ai "what is my current kernel version?"
```

## 9. Uninstall

Remove the installed application and CLI commands:

```bash
sudo rm -rf /opt/linux-ai-agent
sudo rm -f /usr/local/bin/ai
sudo rm -f /usr/local/bin/ai-context
```

If you also want to remove the user's configuration and runtime data:

```bash
rm -rf ~/.linux_ai_agent
```

Only run the last command if you intentionally want to delete the API configuration and stored runtime state.

## Quick Installation

For a new Linux machine:

```bash
git clone https://github.com/Blame11/linux-agent.git
cd linux-agent

mkdir -p ~/.linux_ai_agent
nano ~/.linux_ai_agent/.env
```

Add:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=qwen/qwen3.8-27b
```

Then:

```bash
chmod 600 ~/.linux_ai_agent/.env
sudo ./install.sh
```

Verify:

```bash
ai-context
```

Run:

```bash
ai
```

## Security Notes

- Never commit `.env`.
- Never share your API key.
- Keep `~/.linux_ai_agent/.env` at permission `600`.
- The agent asks for user approval before executing proposed commands.
- The user remains responsible for approving commands.

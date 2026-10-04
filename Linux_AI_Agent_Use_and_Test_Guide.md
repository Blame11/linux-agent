# Linux AI Agent — User & Test Guide

This guide covers how to use the Linux AI Agent and provides practical test prompts for validating command execution, troubleshooting, and multi-step Linux tasks.

---

## 1. Start the Agent

After installation, run:

```bash
ai
```

You can also provide a prompt directly:

```bash
ai "what is my current kernel version?"
```

The agent will analyze the request and propose Linux commands.

### Command authorization

The agent requires explicit approval before executing a command.

Example:

```text
Proposed command:
uname -r

Execute this command? [y/N]:
```

- Enter `y` to execute.
- Enter `n` to reject.
- Press Enter to reject.

The agent should execute only commands that you explicitly approve.

---

# 2. Basic Test Prompts

These are good first tests because they are simple and mostly read-only.

### System information

```text
What operating system am I running?
```

```text
What is my current kernel version?
```

```text
Show me my hostname and current user.
```

```text
How much RAM is available?
```

```text
How much disk space is available?
```

```text
Show the current CPU and system load.
```

### Network

```text
What ports are currently listening?
```

```text
What process is listening on port 80?
```

```text
What is my current IP address?
```

```text
Show my network interfaces.
```

---

# 3. Web Server Test

This is a useful end-to-end test because it checks whether the agent can plan and execute multiple commands.

Use:

```text
Create a simple web server and host a page that says "Hello Tushar Kand".
```

The agent should determine an appropriate approach, create the required files, start the server, and verify that it is working.

For a simple Python HTTP server, the agent may propose commands similar to:

```bash
mkdir -p ~/hello-tushar && printf '%s
' '<!doctype html><html><body><h1>Hello Tushar Kand</h1></body></html>' > ~/hello-tushar/index.html
```

and then:

```bash
cd ~/hello-tushar && python3 -m http.server 8080
```

**Important:** Do not blindly approve commands. Review each command before entering `y`.

If the approved server command is still running after five seconds, the agent
returns control while leaving the server running and reports its PID. Then
test it with:

```text
Check whether my web server is running and verify that it serves "Hello Tushar Kand".
```

You can also manually test:

```bash
curl http://127.0.0.1:8080
```

You should see:

```text
Hello Tushar Kand
```

---

# 4. Multi-Step Linux Test

Try:

```text
Create a directory called ~/ai-test, create a file inside it containing "Linux AI Agent", and verify the file contents.
```

This tests:

- Directory creation
- File creation
- Command sequencing
- Verification

---

# 5. Process Troubleshooting Test

Start a simple process:

```bash
sleep 300
```

Then ask:

```text
Find the sleep process and tell me its PID.
```

Then test:

```text
Terminate the sleep process.
```

The agent should first identify the process and then propose a command to terminate it.

---

# 6. Disk Troubleshooting Test

Create a test file:

```bash
dd if=/dev/zero of=/tmp/ai-test-file bs=1M count=100
```

Then ask:

```text
Why is my disk usage higher than before?
```

The agent should inspect disk usage rather than guessing.

After testing, remove the file:

```bash
rm -f /tmp/ai-test-file
```

---

# 7. Service Troubleshooting Test

Ask:

```text
Check whether SSH is running. If it is not running, explain why before making any changes.
```

This tests whether the agent can:

1. Inspect the service.
2. Read the actual status/error.
3. Avoid assuming the cause.
4. Propose a fix only when appropriate.

---

# 8. Port Troubleshooting Test

Ask:

```text
Check whether port 8080 is listening and tell me what process is using it.
```

Then:

```text
If port 8080 is occupied, explain what is using it before changing anything.
```

This tests evidence-based troubleshooting.

---

# 9. File Permission Test

Create a test file:

```bash
echo "Linux AI Agent" > /tmp/ai-permission-test.txt
```

Then ask:

```text
Check the permissions of /tmp/ai-permission-test.txt and explain them.
```

Then test a modification:

```text
Change /tmp/ai-permission-test.txt so only my user can read and write it.
```

The agent should propose a command such as:

```bash
chmod 600 /tmp/ai-permission-test.txt
```

Review and approve it.

---

# 10. Command Failure Test

Ask:

```text
Run a command to check whether /tmp/this-file-does-not-exist exists, and tell me what happens.
```

Then:

```text
Try to read /tmp/this-file-does-not-exist and explain the actual error.
```

This tests whether the agent uses the real command output instead of inventing a result.

---

# 11. Network Connectivity Test

Ask:

```text
Check whether I can reach example.com and explain the result.
```

Then:

```text
Check DNS resolution for example.com.
```

The agent should use actual command output as evidence.

---

# 12. Package Test

Ask:

```text
Check whether curl is installed. If it is not installed, tell me what package would provide it but do not install anything yet.
```

Then:

```text
If curl is installed, show me its version.
```

This tests whether the agent distinguishes between checking and changing the system.

---

# 13. Command Rejection Test

Use a harmless test command and reject it:

```text
Show me the current working directory.
```

When the agent proposes:

```bash
pwd
```

enter:

```text
n
```

The agent should handle the rejection instead of pretending the command was executed.

---

# 14. Troubleshooting Scenario

Create a simple failure:

```bash
mkdir -p ~/ai-web-test
```

Then ask:

```text
I want to host a website from ~/ai-web-test on port 8080. Check the directory and help me start the server.
```

After starting it, stop the server and ask:

```text
My web server is not responding on port 8080. Diagnose the problem using commands and do not assume the cause.
```

This is a good test of the troubleshooting workflow.

---

# 15. Advanced Test — Build a Small Web Service

Try:

```text
Create a simple web application that displays "Hello Tushar Kand", run it locally on port 8080, and verify it with curl. Use only files under ~/ai-web-app.
```

The important part of this test is that the agent should:

1. Create the application directory.
2. Create the required application files.
3. Start the service.
4. Check the listening port.
5. Test the HTTP response.
6. Report the actual result.

---

# 16. Security / Authorization Test

The project intentionally uses the user as the authorization layer.

Test this with:

```text
Create a file ~/ai-test/authorized.txt containing "authorized".
```

When the agent proposes the command, approve it.

Then:

```text
Create a file ~/ai-test/rejected.txt containing "rejected".
```

Reject the command.

Finally:

```text
Check which files exist in ~/ai-test.
```

The expected result is that only the approved operation should have been performed.

---

# 17. Good Prompts

For the best results, describe the desired outcome clearly.

Good:

```text
Create a simple web server under ~/hello-tushar and host a page saying "Hello Tushar Kand". Start it on port 8080 and verify it with curl.
```

Good:

```text
My SSH service is not working. Diagnose the problem using actual command output. Do not change anything until you identify the likely cause.
```

Good:

```text
Find what is using port 8080 and explain it before making any changes.
```

Less useful:

```text
Fix my server.
```

The more specific the goal, the easier it is for the agent to choose the correct commands and verify the result.

---

# 18. Recommended First Test Sequence

Run these in order:

### Test 1 — Read-only

```text
What is my current kernel version?
```

### Test 2 — Network

```text
What ports are currently listening?
```

### Test 3 — File operation

```text
Create ~/ai-test/test.txt containing "Linux AI Agent" and verify it.
```

### Test 4 — Web server

```text
Create a simple web server and host a page that says "Hello Tushar Kand". Run it on port 8080 and verify it with curl.
```

### Test 5 — Troubleshooting

```text
Check whether port 8080 is listening and tell me what process is using it.
```

### Test 6 — Rejection

```text
Create ~/ai-test/rejected.txt containing "rejected".
```

Reject the proposed command.

### Test 7 — Verification

```text
Check which files exist in ~/ai-test.
```

This sequence tests the core agent workflow:

```text
User request
     ↓
AI reasoning
     ↓
Command proposal
     ↓
User approval
     ↓
Command execution
     ↓
Real command output
     ↓
Next action
     ↓
Verification
     ↓
Final answer
```

---

## Important

Always review a proposed command before approving it, especially commands involving:

- `rm`
- `mv`
- `chmod`
- `chown`
- `systemctl`
- package installation/removal
- network configuration
- disks and filesystems
- `sudo`
- firewall configuration

The agent is designed to ask for authorization, but **you are still responsible for approving the command**.

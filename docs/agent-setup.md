# Setting up an AI coding agent

We install the agents **during the course**, on purpose: the point is that you can do
this yourself afterward, on your own laptop or server, not just in our preconfigured
Codespace. This initial environment ships **no agent**, only Node.js so the install is
a single command.

We will use **three** command-line agents in class so you can compare them. All three
are CLIs that install with `npm` and run right in the browser Codespace:

- **OpenAI Codex CLI**
- **Anthropic Claude Code**
- **Google Gemini CLI**

## One-step install

From a terminal in your Codespace:

```bash
bash scripts/setup-agents.sh
```

This installs all three CLIs globally via `npm`. It does **not** log you in;
authentication is a separate step (below), because how we hand out access to the whole
class is still being finalized.

## Manual install (what the script does)

```bash
# OpenAI Codex CLI
npm install -g @openai/codex

# Anthropic Claude Code
npm install -g @anthropic-ai/claude-code

# Google Gemini CLI
npm install -g @google/gemini-cli
```

Verify:

```bash
codex --version
claude --version
gemini --version
```

## Authentication

For **Claude Code** (and any other instructor-provided credential), the class uses a
shared secret that is stored **encrypted** in the repo and unlocked with a **class
passcode** the instructor gives out on the day.

### Students: unlock in one step

From a terminal in your Codespace:

```bash
source scripts/agent-login.sh
```

Enter the class passcode when prompted. This decrypts the shared credential(s) into
environment variables in your current shell, and `claude` (and `codex`, if a key is
provided) will use them automatically. Nothing is written to disk in plaintext.

- You must use `source` (not `bash scripts/agent-login.sh`), or the variables will not
  stick to your shell.
- You only need to do this **once per Codespace**. The unlock also saves the token to
  your `~/.bashrc`, so new terminals and a Codespace restart stay logged in. (If you
  ever rebuild the container from scratch, run it again.)
- Wrong passcode just fails cleanly; ask the instructor and retry.

Then start the agent **in the terminal**:

```bash
claude --dangerously-skip-permissions
```

Use the terminal, not the VS Code "Claude Code" side panel. In a Codespace the panel
starts before you unlock and cannot see the shared token, so it will show a login
screen; the terminal is the supported path for this class.

That flag lets the agent read, edit, and run commands **without stopping to ask each
time**. We use it on purpose so you see what an autonomous agent actually does, and it
is safe here because your Codespace is a disposable container, not your own machine.
`source scripts/agent-login.sh` already completed Claude Code's first-run setup for you,
so it opens straight to the prompt with no login screen. (Codex: run `codex` the same
way once its key is provided.)

### Gemini: bring your own free login

Gemini CLI has a generous free tier. Just run `gemini` and sign in with any Google
account. This is also the **backup** if the shared credential is unavailable.

### Instructor: create / rotate the encrypted secret

Run this on your own machine (it never prints the secret and never writes plaintext):

```bash
# 1. Mint a long-lived Claude Code token (valid ~1 year):
claude setup-token          # copy the CLAUDE_CODE_OAUTH_TOKEN it prints

# 2. Encrypt it under the class passcode:
scripts/secret-encrypt.sh CLAUDE_CODE_OAUTH_TOKEN
#    paste the token, then type the class passcode twice

# 3. Commit the encrypted blob (only the .enc file is safe to commit):
git add secrets/CLAUDE_CODE_OAUTH_TOKEN.enc && git commit -m "Add encrypted agent token"
```

To also share an OpenAI key for Codex, repeat with `scripts/secret-encrypt.sh
OPENAI_API_KEY`. (Codex has no long-lived subscription token like Claude's, so use an
`OPENAI_API_KEY` here.) The env-var **name** you pass is exactly what students receive.

**Encryption details:** AES-256-CBC, PBKDF2-SHA256 at 600k iterations, random salt,
base64 armored. Only `secrets/*.enc` can be committed; `.gitignore` blocks any plaintext
that lands in `secrets/`.

**After the course:** revoke access by rotating the credential at its source (re-run
`claude setup-token` to invalidate the old one, or delete the OpenAI key), so any copies
students kept stop working.

> Golden rule: **credentials never get committed in plaintext and never get pasted into a
> notebook cell.** Only the encrypted `.enc` blob and the spoken passcode leave your hands.

## If you cannot get an agent working

That is fine. Every exercise ships a **pre-filled solution notebook** (the "Plan B"
path) so you can follow along without an agent. You will not be blocked.

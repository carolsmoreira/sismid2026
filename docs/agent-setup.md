# Setting up an AI coding agent

We install the agents **during the course**, on purpose: the point is that you can do
this yourself afterward, on your own laptop or server, not just in our preconfigured
Codespace. This initial environment ships **no agent**, only Node.js so the install is
a single command.

We will use **two** agents so you can compare them:

- **OpenAI Codex CLI**
- **Anthropic Claude Code**

## One-step install

From a terminal in your Codespace:

```bash
bash scripts/setup-agents.sh
```

This installs both CLIs globally via `npm`. It does **not** log you in; authentication
is a separate step (below), because how we hand out access to the whole class is still
being finalized.

## Manual install (what the script does)

```bash
# OpenAI Codex CLI
npm install -g @openai/codex

# Anthropic Claude Code
npm install -g @anthropic-ai/claude-code
```

Verify:

```bash
codex --version
claude --version
```

## Authentication (to be finalized before the course)

> The class-wide authentication method is **not decided yet**. Do not hard-code any
> shared key into a notebook or commit a key to the repo. Instructors will provide the
> agreed method on the day. The options we are weighing:

- **Bring your own login.** Sign in with your own OpenAI / Anthropic account.
  - Codex: `codex login`
  - Claude Code: `claude login` (or `claude` and follow the prompt)
- **Instructor-provided key or token** exported as an environment variable in your
  Codespace for the session, for example:
  ```bash
  export OPENAI_API_KEY=...        # Codex
  export ANTHROPIC_API_KEY=...     # Claude Code
  ```
  If we go this route, the key is provided in class and is short-lived; never commit it.
- **A shared gateway / proxy** that issues per-student short-lived tokens.

Whichever method we use, the golden rule is the same: **keys never get committed to the
repository and never get pasted into a notebook cell.**

## If you cannot get an agent working

That is fine. Every exercise ships a **pre-filled solution notebook** (the "Plan B"
path) so you can follow along without an agent. You will not be blocked.

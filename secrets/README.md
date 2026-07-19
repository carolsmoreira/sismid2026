# secrets/

Encrypted agent credentials for the course. **Only `*.enc` files live here**, and
each one is AES-256 encrypted with the class passcode (PBKDF2-SHA256, 600k
iterations, base64 armored). Plaintext is blocked from this folder by `.gitignore`.

- Instructor creates a blob:  `scripts/secret-encrypt.sh CLAUDE_CODE_OAUTH_TOKEN`
- Student unlocks in class:    `source scripts/agent-login.sh`  (enter the passcode)

The `.enc` files are safe to commit. The passcode is **never** stored in the repo;
the instructor says it out loud on the day. See `docs/agent-setup.md`.

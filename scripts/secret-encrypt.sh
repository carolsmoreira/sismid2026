#!/usr/bin/env bash
# Encrypt one agent secret into secrets/<NAME>.enc so it can be committed safely.
#
# Run this on YOUR machine (the instructor's). It never prints the secret, never
# writes plaintext to disk, and never passes the secret or passphrase on a command
# line (so it cannot leak via `ps`). Only the encrypted, base64-armored .enc file
# is written, and that is the only thing safe to commit.
#
# Usage:
#   scripts/secret-encrypt.sh CLAUDE_CODE_OAUTH_TOKEN
#   scripts/secret-encrypt.sh OPENAI_API_KEY
#
# The NAME you pass is the environment variable students will get when they unlock.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <ENV_VAR_NAME>" >&2
  echo "Example: $0 CLAUDE_CODE_OAUTH_TOKEN" >&2
  exit 1
fi

NAME="$1"
if [[ ! "$NAME" =~ ^[A-Z][A-Z0-9_]*$ ]]; then
  echo "Refusing: '$NAME' is not a valid UPPER_SNAKE_CASE env var name." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_DIR="$REPO_ROOT/secrets"
mkdir -p "$SECRETS_DIR"
OUT="$SECRETS_DIR/${NAME}.enc"

# Prefer /dev/tty (hidden, immune to a piped stdin); fall back to stdin if no tty.
if { : < /dev/tty; } 2>/dev/null; then TTY=/dev/tty; else TTY=/dev/stdin; fi

# Read the secret value (hidden).
printf 'Paste the value for %s (input hidden): ' "$NAME" >&2
IFS= read -rs SECRET_VALUE < "$TTY"; echo >&2
if [[ -z "$SECRET_VALUE" ]]; then echo "Empty value, aborting." >&2; exit 1; fi

# Read the class passcode twice (hidden) and confirm they match.
printf 'Class passcode (input hidden): ' >&2
IFS= read -rs PASSPHRASE < "$TTY"; echo >&2
printf 'Confirm passcode: ' >&2
IFS= read -rs PASSPHRASE2 < "$TTY"; echo >&2
if [[ "$PASSPHRASE" != "$PASSPHRASE2" ]]; then echo "Passcodes do not match, aborting." >&2; exit 1; fi
if [[ -z "$PASSPHRASE" ]]; then echo "Empty passcode, aborting." >&2; exit 1; fi

# Encrypt: AES-256-CBC, PBKDF2 (SHA-256, 600k iterations), random salt, base64 armor.
# Secret goes in via stdin (printf is a builtin -> not visible in `ps`);
# passphrase goes in via env: (also not on any command line).
export SECRET_ENC_PASS="$PASSPHRASE"
if printf '%s' "$SECRET_VALUE" \
  | openssl enc -aes-256-cbc -md sha256 -pbkdf2 -iter 600000 -salt -a \
      -pass env:SECRET_ENC_PASS > "$OUT"; then
  unset SECRET_ENC_PASS SECRET_VALUE PASSPHRASE PASSPHRASE2
  echo "Wrote $OUT" >&2
  echo "This .enc file is safe to commit. Students unlock it with scripts/agent-login.sh." >&2
else
  unset SECRET_ENC_PASS SECRET_VALUE PASSPHRASE PASSPHRASE2
  rm -f "$OUT"
  echo "Encryption failed." >&2
  exit 1
fi

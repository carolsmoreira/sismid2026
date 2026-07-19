# Unlock the class agent secrets into your current shell.
#
# IMPORTANT: run this with `source`, not `bash`, or the variables won't stick:
#
#     source scripts/agent-login.sh
#
# It asks once for the class passcode (given by the instructor in class), decrypts
# every secrets/*.enc into an environment variable, and the agents (claude, codex)
# pick those up automatically. Nothing is written to disk in plaintext.

# Resolve repo root whether sourced from bash or zsh.
if [ -n "${BASH_SOURCE:-}" ]; then
  _al_src="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
  _al_src="${(%):-%N}"
else
  _al_src="$0"
fi
_AL_ROOT="$(cd "$(dirname "$_al_src")/.." && pwd)"
_AL_SECRETS="$_AL_ROOT/secrets"

_al_cleanup() { unset _al_src _AL_ROOT _AL_SECRETS _AL_PASS _al_files _al_f _al_name _al_val _al_ok _al_cleanup; }

if [ ! -d "$_AL_SECRETS" ]; then
  echo "No secrets/ directory found at $_AL_SECRETS" >&2
  _al_cleanup; return 1 2>/dev/null || exit 1
fi

_al_files=$(ls "$_AL_SECRETS"/*.enc 2>/dev/null || true)
if [ -z "$_al_files" ]; then
  echo "No .enc secrets to unlock in $_AL_SECRETS" >&2
  _al_cleanup; return 1 2>/dev/null || exit 1
fi

printf 'Class passcode (input hidden): '
if { : < /dev/tty; } 2>/dev/null; then
  IFS= read -rs _AL_PASS < /dev/tty; echo
else
  IFS= read -rs _AL_PASS; echo
fi
if [ -z "$_AL_PASS" ]; then
  echo "No passcode entered." >&2
  _al_cleanup; return 1 2>/dev/null || exit 1
fi

export SECRET_ENC_PASS="$_AL_PASS"
_al_ok=0
for _al_f in $_al_files; do
  _al_name="$(basename "$_al_f" .enc)"
  if _al_val="$(openssl enc -d -aes-256-cbc -md sha256 -pbkdf2 -iter 600000 -a \
                  -in "$_al_f" -pass env:SECRET_ENC_PASS 2>/dev/null)" && [ -n "$_al_val" ]; then
    export "$_al_name=$_al_val"
    # Masked confirmation: first 4 and last 4 chars only.
    printf '  set %s = %s...%s\n' "$_al_name" "$(printf '%s' "$_al_val" | cut -c1-4)" "$(printf '%s' "$_al_val" | rev | cut -c1-4 | rev)"
    _al_ok=$((_al_ok+1))
  else
    echo "  FAILED to decrypt $_al_name (wrong passcode?)" >&2
  fi
  unset _al_val
done
unset SECRET_ENC_PASS _AL_PASS

# Pre-complete Claude Code's first-run onboarding so interactive `claude` opens
# straight to the prompt using the shared token, instead of showing the login
# wizard (which would otherwise send a student into their OWN account). Also
# pre-accept the folder-trust dialog for this repo. Idempotent; safe to re-run.
if [ "$_al_ok" -gt 0 ] && command -v python3 >/dev/null 2>&1; then
  python3 - "$_AL_ROOT" <<'PY' 2>/dev/null || true
import json, os, sys
root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
p = os.path.expanduser("~/.claude.json")
try:
    d = json.load(open(p)) if os.path.exists(p) else {}
except Exception:
    d = {}
d["hasCompletedOnboarding"] = True
d.setdefault("theme", "dark")
proj = d.setdefault("projects", {})
proj.setdefault(root, {})["hasTrustDialogAccepted"] = True
json.dump(d, open(p, "w"), indent=2)
PY
fi

if [ "$_al_ok" -gt 0 ]; then
  echo "Unlocked $_al_ok secret(s). The agents will use them automatically."
  echo "Start Claude Code with:  claude --dangerously-skip-permissions"
  echo "  (that flag lets the agent run commands without asking each time; fine here"
  echo "   because your Codespace is a throwaway container.)"
  _al_cleanup; return 0 2>/dev/null || exit 0
else
  echo "Nothing unlocked. Check the passcode with your instructor." >&2
  _al_cleanup; return 1 2>/dev/null || exit 1
fi

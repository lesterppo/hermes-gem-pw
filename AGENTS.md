# AGENTS.md — Hermes Agent Guide

## What This Tool Does

`gem-pw` is a browser-automated CLI for interacting with **Gemini Gems**. It
bypasses `gemini-webapi`'s broken RPC authentication by driving the real Gemini
web UI through a Chromium browser (CDP-first, headed fallback).

**One tool.** This repo ships only `gem-pw`. The older `gem.py` is superseded
and removed.

## When an Agent Should Use This

- User shares a Gemini Gem link (`gemini.google.com/gem/...`).
- `gemini-webapi` or `gem-cli` returns UNAUTHENTICATED / timeout.
- Need to chat, create, edit, delete Gems, upload files, or generate images.
- Need multi-turn conversation with memory across turns.
- Need **token-efficient code/design iteration** via `--collab` surgical diffs.
- Need Pro + Extended Thinking with large knowledge bases.

## How to Invoke

```bash
# Chat
gem-pw <gem-id> "prompt"
gem-pw <gem-id> -c sess.json "prompt"     # Multi-turn
gem-pw <gem-id> -m pro --thinking extended -t 600 "deep"

# Surgical-diff iteration (token-efficient)
gem-pw --collab <gem-id> -f file "instruction" -o resp.md -t 300
python3 apply_gem_diff.py resp.md file            # apply
python3 apply_gem_diff.py resp.md file --dry      # preview

# Gem CRUD
gem-pw --create "Name" "Instructions" -m pro --thinking extended
gem-pw --create "Name" "Instr" \
  --knowledge-file paper.pdf \
  --knowledge-code https://github.com/user/repo \
  --knowledge-folder /path/to/project
gem-pw --edit <gem-id> --name "New Name"
gem-pw --edit <gem-id> --instructions "New prompt..."
gem-pw --edit <gem-id> --knowledge-code https://github.com/user/repo
gem-pw --edit <gem-id> -m pro --thinking extended
gem-pw --delete <gem-id>

# Upload / Image
gem-pw --upload <gem-id> -f file "Q"
gem-pw --img <gem-id> "description"

# Help
gem-pw --help
```

## Setup (one-time)

```bash
pip install playwright aiohttp
playwright install chromium
gem-pw-login  # Opens Chromium window — sign into Gemini (needs X display)
```

Optionally start a persistent CDP browser for the fast path:
`cr-server start --headed` (listens on `http://127.0.0.1:9223`).

## Output Format

All commands return JSON on stdout:
```json
{"ok": true, "f": "/home/USER/.hermes/gem_pw_output/gem-pw-<ts>.md", "s": 123, "t": 15.2}
```
The response is saved to the file path in `f` — read it with `read_file`.
The JSON is ~100 chars — intentionally token-efficient for agent consumption.
Output dir is profile-aware (`$HERMES_HOME/gem_pw_output/`, else
`~/.hermes/gem_pw_output/`); override with `-o <file>` or `GEM_PW_OUTPUT_DIR`.

## Error Handling

| Error Code | Meaning | Action |
|-----------|---------|--------|
| NOT_SIGNED_IN | Chromium not signed into Gemini | Run `gem-pw-login` |
| NOT_FOUND | Gem ID doesn't exist | Check the ID |
| NO_INPUT | Chat input not found on page | Page may not have loaded fully; retry |
| EMPTY | No response within timeout | Retry with `-t 600` for large knowledge |
| BAD_URL | Invalid Gem ID or URL | Use `gem-pw --help` for usage |
| FILE_NOT_FOUND | Upload file doesn't exist | Check file path |
| LOCKED | Another gem-pw holds the Chromium profile lock | Wait; lock self-heals from dead PIDs |
| NO_DISPLAY | No X display and no xvfb-run | Set DISPLAY or install xvfb |
| USAGE | Missing required arguments | Check command syntax |

## Multi-Turn Chat

Use `-c <session.json>` to persist conversation across turns:
```bash
gem-pw <id> -c /tmp/session.json "Remember that my favorite color is blue"
gem-pw <id> -c /tmp/session.json "What is my favorite color?"
# Second call restores the conversation — Gem remembers the prior context
```

## Gem Knowledge Management

Create Gems with persistent knowledge or edit existing ones:
```bash
gem-pw --create "Analyzer" "Instructions" \
  --knowledge-file paper.pdf \
  --knowledge-code https://github.com/user/repo \
  --knowledge-folder /path/to/project \
  -m pro --thinking extended

gem-pw --edit <gem-id> --knowledge-code https://github.com/user/new-repo
gem-pw --edit <gem-id> --knowledge-file new-doc.pdf
```
Knowledge types: files (`--knowledge-file`), GitHub repos (`--knowledge-code`),
photos (`--knowledge-photo`), directories (`--knowledge-folder` — auto-zipped).

## `--collab` diff protocol (important)

`--collab` asks the Gem for a **unified diff only**, not a full file. Apply it
with `apply_gem_diff.py` (ships in this repo). The protocol prompt forces the
exact uploaded filename as the diff header and real content. A
knowledge/persona Gem may append an off-protocol essay after the diff —
`apply_gem_diff.py` ignores the trailing prose (extracts only the first diff
block). Prefer a dedicated *coding* Gem for cleanest diffs.

## Native Hermes tool (drop-in)

Copy `gem_tool.py` → `<hermes-agent>/tools/gem_tool.py` and
`apply_gem_diff.py` → `<hermes-agent>/tools/apply_gem_diff.py` (or keep it at
`~/.hermes/scripts/apply_gem_diff.py`). Enable the `gem` toolset. This exposes
`gem_collab` and `gem_chat` as model tools (gem-pw-only backend). See README
"For Hermes Agents".

## File Locations

- Profile: `~/.gemini-cli/cr-profile/` (or `$HERMES_HOME/.gemini-cli/cr-profile/`)
- Output: `$HERMES_HOME/gem_pw_output/gem-pw-<ts>.md` (or `-o <file>`)
- Session files: wherever `-c` points

## Dependencies

- Python 3.10+
- playwright (with Chromium)
- aiohttp

## Privacy

No API keys, tokens, cookies, or personal identifiers in this repo. The browser
profile created at runtime holds the user's Gemini session — it is git-ignored
and must never be committed.

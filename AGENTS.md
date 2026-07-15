# AGENTS.md — Hermes Agent Guide

## What This Tool Does

`gem-pw` is a browser-automated CLI for interacting with Gemini Gems.
It bypasses gemini-webapi's broken RPC authentication by driving the
real Gemini web UI through a headful Chromium browser.

## When an Agent Should Use This

- User shares a Gemini Gem link (gemini.google.com/gem/...)
- gemini-webapi or gem-cli returns UNAUTHENTICATED / timeout
- Need to chat, create, edit, delete Gems, upload files, or generate images
- Need multi-turn conversation with memory across turns
- Need Pro + Extended Thinking with large knowledge bases

## How to Invoke

```bash
# Chat
gem-pw <gem-id> "prompt"
gem-pw <gem-id> -c sess.json "prompt"     # Multi-turn
gem-pw <gem-id> -m pro --thinking extended -t 600 "deep"

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
gem-pw-login  # Opens Chromium window — sign into Gemini
```

## Output Format

All commands return JSON on stdout:
```json
{"ok": true, "f": "/tmp/gem-pw-<ts>.md", "s": 123, "t": 15.2}
```

The response is saved to the file path in `f`. Read it with `read_file`.
The JSON is ~100 chars — intentionally token-efficient for agent consumption.

## Error Handling

| Error Code | Meaning | Action |
|-----------|---------|--------|
| NOT_SIGNED_IN | Chromium not signed into Gemini | Run `gem-pw-login` |
| NOT_FOUND | Gem ID doesn't exist | Check the ID |
| NO_INPUT | Chat input not found on page | Page may not have loaded fully |
| EMPTY | No response within timeout | Retry with `-t 600` for large knowledge |
| BAD_URL | Invalid Gem ID or URL | Use `gem-pw --help` for usage |
| FILE_NOT_FOUND | Upload file doesn't exist | Check file path |
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
# Create with knowledge
gem-pw --create "Analyzer" "Instructions" \
  --knowledge-file paper.pdf \
  --knowledge-code https://github.com/user/repo \
  --knowledge-folder /path/to/project \
  -m pro --thinking extended

# Edit to add knowledge later
gem-pw --edit <gem-id> --knowledge-code https://github.com/user/new-repo
gem-pw --edit <gem-id> --knowledge-file new-doc.pdf
```

Knowledge types: files (`--knowledge-file`), GitHub repos (`--knowledge-code`),
photos (`--knowledge-photo`), directories (`--knowledge-folder` — auto-zipped).

## File Locations

- Profile: `~/.gemini-cli/cr-profile/` (or `$HERMES_HOME/.gemini-cli/cr-profile/`)
- Output: `/tmp/gem-pw-<ts>.md` (or specified via `-o`)
- Session files: wherever `-c` points

## Dependencies

- Python 3.10+
- playwright (with Chromium)
- aiohttp

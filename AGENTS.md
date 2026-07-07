# AGENTS.md — Hermes Agent Guide

## What This Tool Does

`gem-pw` is a browser-automated CLI for interacting with Gemini Gems.
It bypasses gemini-webapi's broken RPC authentication by driving the
real Gemini web UI through a headful Chromium browser.

## When an Agent Should Use This

- User shares a Gemini Gem link (gemini.google.com/gem/...)
- gemini-webapi or gem-cli returns UNAUTHENTICATED / timeout
- Need to chat with a Gem, create/delete Gems, upload files, or generate images
- Need multi-turn conversation with memory across turns

## How to Invoke

```bash
# Start here — these are the commands:
gem-pw <gem-id> "prompt"                  # Chat
gem-pw <gem-id> -c sess.json "prompt"     # Multi-turn chat
gem-pw --create "Name" "Instructions"      # Create Gem
gem-pw --delete <gem-id>                   # Delete Gem
gem-pw --upload <gem-id> -f file "Q"       # File upload
gem-pw --img <gem-id> "description"        # Image generation
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
| EMPTY | No response within timeout | Retry |
| FILE_NOT_FOUND | Upload file doesn't exist | Check file path |

## Multi-Turn Chat

Use `-c <session.json>` to persist conversation across turns:
```bash
gem-pw <id> -c /tmp/session.json "I am Peter"
gem-pw <id> -c /tmp/session.json "What is my name?"
# Second call restores the conversation — Gem remembers "Peter"
```

## File Locations

- Profile: `~/.gemini-cli/pw-profile/` (or `$HERMES_HOME/.gemini-cli/pw-profile/`)
- Output: `/tmp/gem-pw-<ts>.md` (or `$HERMES_OUTPUT/`)
- Session files: wherever `-c` points

## Dependencies

- Python 3.10+
- playwright (with Chromium)
- aiohttp

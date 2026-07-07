# gem-pw — Gemini Gem CLI via Browser Automation

AI-agent-native CLI for interacting with Gemini Gems through browser automation.
No API keys, no cookie extraction, no external server. Sign in once, then all
commands work.

```
gem-pw <gem-id> "prompt"                  → Chat
gem-pw <gem-id> -c sess.json "prompt"     → Multi-turn
gem-pw --create "Name" "Instructions"      → Create Gem
gem-pw --delete <gem-id>                   → Delete Gem
gem-pw --upload <gem-id> -f file "Q"       → Upload + ask
gem-pw --img <gem-id> "description"        → Generate image
```

## Why

gemini-webapi's internal RPC API returns UNAUTHENTICATED for Gem operations
(as of July 2026). gem-pw bypasses this by driving the real Gemini web UI
through a headful Chromium browser via Playwright.

## Install

```bash
git clone https://github.com/lesterppo/hermes-gem-pw
cd hermes-gem-pw
bash install.sh
```

## Setup

```bash
gem-pw-login  # Opens Chromium → sign into Gemini
```

## Usage

```bash
# Chat with a Gem (from URL or ID)
gem-pw 9d8c15f86f8b "Explain EBITDA in 2 sentences"

# Multi-turn conversation
gem-pw 9d8c15f86f8b -c /tmp/session.json "I am Peter"
gem-pw 9d8c15f86f8b -c /tmp/session.json "What is my name?"
# Second call remembers "Peter"

# Create a Gem
gem-pw --create "My Bot" "You are a helpful assistant"

# Delete a Gem
gem-pw --delete abc123

# Upload a file and ask about it
gem-pw --upload 9d8c15f86f8b -f report.pdf "Summarize this"

# Generate an image
gem-pw --img 9d8c15f86f8b "A cat on a rainbow"
```

## Output

All commands return compact JSON on stdout. Response saved to file.

```json
{"ok": true, "f": "/tmp/gem-pw-1783463794.md", "s": 16, "t": 11.7}
```

## For Hermes Agents

This tool is built for AI agent consumption. Key properties:

- **Token-efficient**: ~100 char JSON stdout (~25 tokens)
- **Self-describing errors**: Error codes tell the agent what to do next
- **Multi-turn**: `-c session.json` persists conversation across agent turns
- **File-based I/O**: Responses on disk, pointer JSON on stdout
- **Stateless**: Each call launches its own browser, no server to manage

Read `AGENTS.md` for the full agent integration guide.

## Requirements

- Python 3.10+
- Playwright + Chromium
- aiohttp
- X display (for Chromium window during login)

## How It Works

```
gem-pw → launch_persistent_context → Chromium (headful)
         └─ uses ~/.gemini-cli/pw-profile/
         └─ profile persists session across calls
         └─ page.evaluate() for custom element interaction
```

## License

MIT

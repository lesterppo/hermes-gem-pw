---
name: gem-pw
description: Browser-automated Gemini Gem CLI via Chromium CDP.
version: 3.0.0
author: lesterppo
tags: [gemini, gem, cli, playwright, cdp, browser-automation]
platforms: [linux, macos, wsl]
metadata:
  hermes:
    category: automation
    related_skills: [browser-cdp, gem-cli]
    config:
      gem_pw_profile: "~/.gemini-cli/pw-profile"
      gem_pw_output: "/tmp"
---

# gem-pw Skill

Browser-automated CLI for interacting with Gemini Gems. Launches its own
Chromium with persistent profile — no API keys, no external server, no
cookie extraction needed. Sign in once with `gem-pw-login`, then all
commands work.

## When to Use

- Need to interact with a shared Gemini Gem via URL
- gemini-webapi returns UNAUTHENTICATED for Gem operations
- Need file upload, image generation via Gem web UI
- Need multi-turn conversation with conversation persistence
- Need Gem CRUD (create/delete)

## Prerequisites

- Python 3.10+
- Playwright: `pip install playwright && playwright install chromium`
- aiohttp: `pip install aiohttp`
- One-time login: `gem-pw-login`

## Quick Start

```bash
# One-time setup
gem-pw-login

# Single-turn chat
gem-pw <gem-id> "prompt"

# Multi-turn (conversation persists across calls)
gem-pw <gem-id> -c session.json "turn 1"
gem-pw <gem-id> -c session.json "turn 2"

# Create a Gem
gem-pw --create "MyGem" "System instructions here"

# Delete a Gem
gem-pw --delete <gem-id>

# File upload
gem-pw --upload <gem-id> -f document.pdf "summarize this"

# Image generation
gem-pw --img <gem-id> "a cat on a rainbow"
```

## How to Run

### Chat

```bash
gem-pw <gem-url-or-id> "prompt"
gem-pw <gem-id> -c sess.json "multi-turn message"
```

The `-c` flag persists the conversation URL. Subsequent calls reload the same
page, preserving Gem memory of previous turns.

### Create Gem

```bash
gem-pw --create "GemName" "System instructions for the gem"
# Returns: {"ok":true,"action":"create-gem","id":"abc123","name":"GemName"}
```

### Delete Gem

```bash
gem-pw --delete <gem-id>
```

### File Upload

```bash
gem-pw --upload <gem-id> -f report.pdf "summarize this document"
```

### Image Generation

```bash
gem-pw --img <gem-id> "a red apple on a white table"
```

## Architecture

```
gem-pw → launch_persistent_context → Chromium (headful)
         └─ uses ~/.gemini-cli/pw-profile/
         └─ profile persists session across calls
         └─ JS evaluate() for custom element interaction
```

Self-contained: launches its own Chromium each call. No external server needed.

## Token Efficiency

- JSON stdout: ~100 chars (~25 tokens)
- Response saved to `/tmp/gem-pw-<ts>.md` (configurable via `HERMES_OUTPUT`)
- Follows agent-native pointer pattern: `{"ok":true,"f":"/tmp/...","s":123,"t":12.3}`

## Output Format

**Success:**
```json
{"ok":true,"f":"/tmp/gem-pw-1783463794.md","s":16,"b":16,"t":11.7,"gem":"9d8c15f86f8b"}
```

**Error:**
```json
{"ok":false,"err":"NOT_SIGNED_IN","msg":"Sign into Gemini in the Chromium window"}
```

Error codes: `NOT_SIGNED_IN`, `NOT_FOUND`, `NO_INPUT`, `EMPTY`, `NO_CREATE_BTN`,
`DELETE_FAILED`, `FILE_NOT_FOUND`, `NO_UPLOAD`

## Pitfalls

- **Must run `gem-pw-login` once.** Signs into Gemini in visible Chromium.
- **Profile at `~/.gemini-cli/pw-profile/`.** Set `HERMES_HOME` for Hermes profile isolation.
- **One call at a time.** Chromium launches per call — no concurrency.
- **~20-25s per call.** Includes browser launch, page load, and response wait.
- **Image gen needs a Gem that supports it.** Finance/specialist Gems may not generate images.
- **Chinese UI selectors used.** Adapt for non-Chinese Gemini UI if needed.
- **Memory pressure can kill Chromium.** If calls fail, retry.

## Verification

```bash
# Login
gem-pw-login

# Chat test
gem-pw 9d8c15f86f8b "1+1=?"

# Multi-turn test
gem-pw 9d8c15f86f8b -c /tmp/test.json "my name is Alice"
gem-pw 9d8c15f86f8b -c /tmp/test.json "what is my name?"

# Create + delete test
ID=$(gem-pw --create "TestGem" "Be helpful" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
gem-pw --delete "$ID"
```

---
name: gem-pw
description: Browser-automated Gemini Gem CLI via Chromium CDP.
version: 4.0.0
author: lesterppo
tags: [gemini, gem, cli, playwright, cdp, browser-automation]
platforms: [linux, macos, wsl]
metadata:
  hermes:
    category: automation
    related_skills: [browser-cdp, gem-cli]
    config:
      gem_pw_profile: "~/.gemini-cli/cr-profile"
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
- Need Gem CRUD (create, edit, delete)
- Need Pro + Extended Thinking with configurable timeout

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

# Pro + Extended Thinking
gem-pw <gem-id> -m pro --thinking extended -t 600 "deep analysis"

# Create a Gem
gem-pw --create "MyGem" "System instructions here"
gem-pw --create "Analyzer" "Instructions" \
  --knowledge-file paper.pdf \
  --knowledge-code https://github.com/user/repo \
  --knowledge-folder /path/to/project \
  -m pro --thinking extended

# Edit a Gem
gem-pw --edit <gem-id> --name "New Name"
gem-pw --edit <gem-id> --instructions "New system prompt..."
gem-pw --edit <gem-id> --knowledge-code https://github.com/user/repo
gem-pw --edit <gem-id> -m pro --thinking extended

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
gem-pw <gem-id> -m pro --thinking extended -t 600 "complex analysis"
```

The `-c` flag persists the conversation URL. Subsequent calls reload the same
page, preserving Gem memory of previous turns.

`-t` sets `_wait_response()` timeout in seconds (default 120, max 600). Use
for Pro+Extended Thinking with large knowledge bases.

### Create Gem

```bash
gem-pw --create "GemName" "System instructions for the gem"
gem-pw --create "Analyzer" "Instructions" \
  --knowledge-file paper.pdf \
  --knowledge-code https://github.com/user/repo \
  --knowledge-folder /path/to/project \
  -m pro --thinking extended
# Returns: {"ok":true,"action":"create-gem","id":"abc123","name":"GemName"}
```

Knowledge flags:
- `--knowledge-file <path>` — attach file(s) to Gem knowledge (repeatable)
- `--knowledge-code <url>` — import GitHub repo to knowledge (single URL)
- `--knowledge-photo <path>` — attach photo(s) to knowledge (repeatable)
- `--knowledge-folder <dir>` — zip & upload directory as knowledge (repeatable)

### Edit Gem

```bash
gem-pw --edit <gem-id> --name "New Name"
gem-pw --edit <gem-id> --instructions "New system prompt..."
gem-pw --edit <gem-id> --knowledge-code https://github.com/user/repo
gem-pw --edit <gem-id> --knowledge-file document.pdf
gem-pw --edit <gem-id> -m pro --thinking extended
```

Supports all the same knowledge flags as `--create`. Navigates to edit page,
makes changes, saves. Falls back to view page → options menu → "編輯/Edit"
if direct edit URL fails.

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
         └─ uses ~/.gemini-cli/cr-profile/
         └─ profile persists session across calls
         └─ JS evaluate() for custom element interaction
```

Self-contained: launches its own Chromium each call. No external server needed.

## Token Efficiency

- JSON stdout: ~100 chars (~25 tokens)
- Response saved to `/tmp/gem-pw-<ts>.md`
- Follows agent-native pointer pattern: `{"ok":true,"f":"/tmp/...","s":123,"t":12.3}`
- `--json-out` strips metadata for minimal token overhead

## Output Format

**Success:**
```json
{"ok":true,"f":"/tmp/gem-pw-1783463794.md","s":16,"b":16,"t":11.7,"gem":"9d8c15f86f8b"}
```
**Edit:**
```json
{"ok":true,"action":"edit-gem","id":"a24c05b8089f","changed":["name","code:repo-name"]}
```
**Error:**
```json
{"ok":false,"err":"NOT_SIGNED_IN","msg":"Sign into Gemini in the Chromium window"}
```

Error codes: `NOT_SIGNED_IN`, `NOT_FOUND`, `NO_INPUT`, `EMPTY`, `BAD_URL`,
`NO_NAME_INPUT`, `NO_INST_INPUT`, `TYPE_FAILED`, `FILE_NOT_FOUND`, `NO_UPLOAD`,
`USAGE`, `NO_PROMPT`.

## Pitfalls

- **Must run `gem-pw-login` once.** Signs into Gemini in visible Chromium.
- **Profile at `~/.gemini-cli/cr-profile/`.** Set `HERMES_HOME` for Hermes profile isolation.
- **One call at a time.** Chromium launches per call — no concurrency.
- **~5-25s per call.** Includes browser launch, page load, response wait. Faster for Flash, slower for Pro+Extended.
- **Pro + Extended Thinking with large knowledge**: May exceed default 120s timeout. Use `-t 600`.
- **`--help` works.** Fixed Jul 2026 (was crashing with TypeError).
- **Stale profile locks auto-cleaned** on launch. Kill orphaned Chrome if persistent.
- **Xvfb required in WSL.** `Xvfb :0 -screen 0 1920x1080x24 &>/dev/null &`
- **Image gen needs a Gem that supports it.** Finance/specialist Gems may not generate images.
- **Chinese UI selectors used.** Adapt for non-Chinese Gemini UI if needed.

## Verification

```bash
# Login
gem-pw-login

# Help
gem-pw --help

# Chat test
gem-pw <gem-id> "1+1=?"

# Multi-turn test
gem-pw <gem-id> -c /tmp/test.json "my name is Alice"
gem-pw <gem-id> -c /tmp/test.json "what is my name?"

# Create + edit + delete test
ID=$(gem-pw --create "TestGem" "Be helpful" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
gem-pw --edit "$ID" --name "TestGem v2"
gem-pw --delete "$ID"
```

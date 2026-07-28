# gem-pw — Gemini Gem CLI & Browser Automation (No API Key)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20%7C%20WSL2-lightgrey.svg)]()

**AI-agent-native CLI for Google Gemini — chat, create/edit/delete Gems, image
generation, file upload, and surgical-diff collaboration. No API key, no cookie
extraction, no external server. Sign in once via browser, then all commands
work through a real Chromium (CDP or self-launched).**

```text
gem-pw <gem-id> "prompt"                  → Chat with a Gem (single-turn)
gem-pw <gem-id> -c sess.json "prompt"     → Multi-turn (persists conversation)
gem-pw --collab <gem-id> -f file "instr"  → Request a UNIFIED DIFF only (token-efficient)
gem-pw --create "Name" "Instructions"      → Create a Gem (with knowledge upload)
gem-pw --edit <gem-id> --name "New"        → Edit Gem name/instructions/model
gem-pw --delete <gem-id>                   → Delete a Gem
gem-pw --upload <gem-id> -f file "Q"       → Upload file + ask
gem-pw --img [<gem-id>] "description"     → Generate image (Imagen)
gemini-web chat "prompt"                   → Direct chat (no Gem needed)
gemini-web img "description"               → Image generation (main app)
gemini-web research "topic"                → Deep research
gemini-web account                         → Account info
```

> **One tool, two CLIs.** This repo ships **`gem-pw`** (Gem operations: chat,
> CRUD, upload, collab, image) and **`gemini-web`** (non-Gem operations: direct
> chat, image gen, deep research, account). Both drive a real Chromium browser
> — the only backend that reliably reaches Google's browser-gated Gemini
> endpoints.

---

## Why Browser Automation?

Gemini's internal RPC API (`gemini-webapi`) is **browser-gated** as of July 2026.
`batchexecute` and `StreamGenerate` POST endpoints silently drop connections
from ALL non-browser HTTP clients (curl, urllib, curl_cffi, httpx). Additionally,
Gem operations return `UNAUTHENTICATED` for some accounts.

**Only a real browser** — with its TLS fingerprint, HTTP/2 stack, and header
ordering — can reach these endpoints. `gem-pw` and `gemini-web` drive a real
Chromium via Playwright, bypassing both gates.

A **Gem is a UI construct** — its bundled instruction + knowledge are NOT
exposed by the raw Gemini API (Interactions API / `GEMINI_API_KEY` cannot
target a specific Gem). The ONLY working backend for Gem operations is the
browser.

## Features

- **Gem Chat** — Single-turn or multi-turn (`-c session.json`) with any Gem
- **Gem CRUD** — Create, edit (name/instructions/model/knowledge), delete Gems
- **Token-Efficient Collaboration** — `--collab` returns a surgical unified diff
  only (not the whole file), ~10x cheaper than re-emitting artifacts
- **Image Generation** — Imagen via "Upload & tools → Create image" drawer
- **Deep Research** — `gemini-web research` triggers multi-step web research
- **No API Key** — Browser sign-in via `gem-pw-login` (one-time, profile persists)
- **CDP-First** — Connects to a warm Chromium page server when available
- **Self-Healing** — Stale profile locks auto-cleaned, dead PID detection
- **Headless Fallback** — `xvfb-run` auto-detected when DISPLAY is unset
- **Locale-Agnostic** — Selectors try zh-TW → English → structural fallback
- **Agent-Native** — ~100-char JSON pointer on stdout, full response on disk

## Install

```bash
git clone https://github.com/lesterppo/hermes-gem-pw
cd hermes-gem-pw
bash install.sh
```

## Setup

```bash
gem-pw-login   # Opens Chromium → sign into Gemini once
```

`gem-pw` is **CDP-first**: if a running Chromium with remote debugging is alive,
it connects to that warm browser (multi-turn, no cold-start). Otherwise it
launches its own headed Chromium (profile at `~/.gemini-cli/cr-profile/`).

For CDP mode, start a persistent Chromium:
```bash
google-chrome-stable --remote-debugging-port=9224 --user-data-dir=~/.gemini-cli/cr-profile &
# Then all commands auto-connect via CDP (set GEM_PW_CDP or --cdp flag)
```

## Quick Start

```bash
# Chat with a Gem
gem-pw abc123def456 "Explain machine learning in 2 sentences"

# Multi-turn conversation (Gem remembers context)
gem-pw abc123def456 -c /tmp/session.json "My name is Alex"
gem-pw abc123def456 -c /tmp/session.json "What is my name?"

# Create a Gem with knowledge + Pro model
gem-pw --create "Code Reviewer" "Review code for bugs" \
  --knowledge-file style-guide.pdf \
  --knowledge-code https://github.com/user/repo \
  -m pro --thinking extended

# Surgical-diff collaboration (token-efficient)
gem-pw --collab abc123def456 -f app.py "Add error handling" -o resp.md -t 300
python3 apply_gem_diff.py resp.md app.py       # apply the diff
python3 apply_gem_diff.py resp.md app.py --dry  # preview only

# Image generation
gem-pw --img "a cat riding a unicorn"           # main app
gem-pw --img abc123def456 "a red circle"        # inside a Gem

# Direct chat (no Gem) — fastest path
gemini-web chat "What is the capital of France?"
gemini-web img "a sunset over mountains"

# Deep research
gemini-web research "Latest advancements in CRISPR gene editing"
```

## `--collab` Protocol

Instead of re-emitting the whole file each turn, `--collab` asks the Gem to
return a **unified diff only** (`diff -u`, `patch -p0` applicable). This cuts
later-round token cost dramatically (~10x savings).

```bash
gem-pw --collab <gem-id> -f current.py "Add a retry() helper" -o resp.md -t 300
python3 apply_gem_diff.py resp.md current.py           # apply
python3 apply_gem_diff.py resp.md current.py --dry      # preview
```

`apply_gem_diff.py` extracts the first `diff` block, runs `patch -p0 --dry-run`,
and applies it. Rejects empty/whitespace-only diffs (`EMPTY_DIFF`).

## Output Format

All commands return compact JSON on stdout (~100 chars). Full response saved to
disk at `~/.hermes/gem_pw_output/` (or `$HERMES_HOME/gem_pw_output/`).

```json
{"ok": true, "f": "/home/USER/.hermes/gem_pw_output/gem-pw-1783463794.md", "s": 16, "t": 11.7}
```

## Related Projects

- **[hermes-gem-cli](https://github.com/lesterppo/hermes-gem-cli)** — WebAPI-based
  Gemini Gem CLI. 3-10x faster on native Linux (~4s vs ~15-40s). Uses browser
  cookies (no API key). Best for direct chat, cron/headless use, and quick Gem
  ops. Does NOT support knowledge upload at Gem creation — for that, use gem-pw.

## For Hermes Agents

This tool is built for AI-agent consumption. See [AGENTS.md](AGENTS.md) for the
full agent integration guide.

- **Native Hermes tool**: Drop `gem_tool.py` + `apply_gem_diff.py` into a Hermes
  checkout, enable the `gem` toolset. Exposes `gem_collab` and `gem_chat` as
  model tools.
- **Token-efficient**: Pointer JSON on stdout, artifact on disk.
- **Self-describing errors**: `NOT_SIGNED_IN`, `LOCKED`, `NO_INPUT`, `EMPTY`, etc.
- **Headless fallback**: `xvfb-run` auto-detected for cron/remote use.

## Requirements

- Python 3.10+
- Playwright + Chromium (`playwright install chromium`)
- aiohttp
- An X display (or `xvfb-run` for headless)

## Comparison: gem-pw vs gem-cli vs Gemini API

| Feature | gem-pw (CDP) | gem-cli (WebAPI) | Gemini API Key |
|---------|:---:|:---:|:---:|
| Gem chat (target specific Gem) | ✅ | ✅ | ❌ (UI construct) |
| Gem CRUD (create/edit/delete) | ✅ | ✅ | ❌ |
| Direct chat (no Gem) | ✅ | ✅ | ✅ |
| Image generation (Imagen) | ✅ | ✅ | ✅ |
| Deep research | ✅ | ✅ | ❌ |
| File upload into Gem | ✅ | ✅ | ❌ |
| Multi-turn conversation | ✅ | ✅ | ✅ |
| No API key required | ✅ | ✅ | ❌ |
| Knowledge at Gem creation | ✅ | ❌ | ❌ |
| Chat speed | ~15-40s | **~4s** | ~2-5s |
| Works on WSL2 | ✅ | ❌ (hangs) | ✅ |
| Works on native Linux | ✅ | ✅ | ✅ |

## Repository

- **gem-pw**: Gem-focused CLI — chat, CRUD, upload, collab, image gen
- **gemini-web**: General Gemini CLI — direct chat, image gen, deep research, account
- **apply_gem_diff.py**: Diff application tool for the `--collab` workflow
- **gem-pw-login**: One-time browser sign-in helper
- **gem_tool.py**: Native Hermes agent tool (drop-in for Hermes agent)
- **install.sh**: Installs dependencies + copies CLIs to `~/.local/bin/`

## Changelog

### v4.4 (Jul 2026)
- `cmd_delete`: fixed — navigates to `/gems/view`, matches Gem card by href,
  clicks "More options → Delete → confirm" (was broken on Gem detail page)
- `cmd_image`: uses "Upload & tools → Create image" drawer flow with retry;
  gem_id now optional (falls back to main `/app` page)
- `--img` parsing: strips flags (`-t`, `-o`, `-m`) before resolving gem_id vs
  description
- `gemini-web`: added to repo; default CDP URL now `127.0.0.1:9224`; `cmd_img`
  uses same drawer flow
- `_pick`: logs exceptions instead of silently swallowing them

### v4.3 — Headless fallback + native Hermes tool
### v4.2 — Multi-account guard + verified model picker
### v4.1 — Locale-agnostic selectors (zh-TW + English verified)
### v4 — `--edit`, `-t` timeout, `-o` output path, `--help` JSON

## Privacy

This repo contains **no API keys, tokens, cookies, or personal identifiers**.
All paths use `Path.home()` / `$HOME` / `$HERMES_HOME`. The browser profile at
runtime holds your Gemini session — git-ignored, never committed.

## License

MIT — see [LICENSE](LICENSE)

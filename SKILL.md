---
name: gem-pw
description: Browser-automated Gemini Gem CLI (CDP-first) — chat, CRUD, image gen, deep research, --collab surgical-diff review. No API key.
version: 4.4.0
author: Peter (lesterppo)
tags: [gemini, gem, cli, playwright, cdp, browser-automation, image-generation, deep-research, no-api-key, free]
platforms: [linux, macos, wsl]
metadata:
  hermes:
    category: automation
    related_skills: [gem-collab, browser-cdp, gem-cli]
    config:
      gem_cdp_endpoint: "http://127.0.0.1:9224"
      gem_pw_output_dir: "$HERMES_HOME/gem_pw_output"
---

# gem-pw — Gemini CLI via Browser Automation (No API Key)

Two CLIs, one repo: **gem-pw** (Gem operations) and **gemini-web** (non-Gem
operations). Both drive a real Chromium browser via Playwright — the only
backend that reliably reaches Google's browser-gated Gemini endpoints. Zero API
keys, zero cookie extraction, zero external servers.

## When to Use

- Chat with any Gemini Gem via URL/id (single or multi-turn)
- Gem CRUD: create, edit (name/instructions/model/knowledge), delete
- Image generation via Imagen (Upload & tools → Create image drawer)
- Deep research via `gemini-web research`
- Token-efficient code/design iteration via `--collab` surgical diffs
- Direct chat without a Gem (fastest path, no Gem overhead)
- `gemini-webapi` returns UNAUTHENTICATED — real browser bypasses this gate

## Prerequisites

1. Python 3.10+ and `pip install playwright aiohttp && playwright install chromium`
2. One-time sign-in: `gem-pw-login` (opens Chromium, profile persists at `~/.gemini-cli/cr-profile/`)
3. CDP path: a headed Chromium on `http://127.0.0.1:9224` (default; override with `GEM_PW_CDP` or `--cdp`). Without CDP, falls back to self-launched headed Chromium.

## Quick Reference

| Need | Command |
|------|---------|
| Chat with a Gem | `gem-pw <id> "prompt"` |
| Multi-turn chat | `gem-pw <id> -c sess.json "prompt"` |
| Diff-based iteration | `gem-pw --collab <id> -f file "instr" -o r.md` |
| Apply the diff | `python3 apply_gem_diff.py r.md file [--dry]` |
| Create a Gem | `gem-pw --create "Name" "Instructions" [-m model] [--knowledge-*]` |
| Edit a Gem | `gem-pw --edit <id> --name "New" --instructions "..."` |
| Delete a Gem | `gem-pw --delete <id>` |
| Upload + ask | `gem-pw --upload <id> -f file "question"` |
| Image gen (Gem) | `gem-pw --img <id> "description"` |
| Image gen (main app) | `gem-pw --img "description"` |
| Direct chat (no Gem) | `gemini-web chat "prompt"` |
| Deep research | `gemini-web research "topic"` |
| Account info | `gemini-web account` |

## Output Format

Success:
```json
{"ok": true, "f": "~/.hermes/gem_pw_output/gem-pw-<ts>.md", "s": 123, "t": 12.3}
```

Error codes: `NOT_SIGNED_IN`, `MULTI_ACCOUNT`, `NO_INPUT`, `EMPTY`, `FILE_NOT_FOUND`, `NO_PROMPT`, `BAD_URL`, `LOCKED`, `NO_DISPLAY`.

## Pitfalls

- **Correct account required.** Non-Advanced account silently downgrades Pro→Flash.
- **One browser at a time.** Concurrent gem-pw runs → second gets `LOCKED`. Lock self-heals from dead PIDs.
- **Pro + Extended Thinking is slow** (1-3 min). Use `-t 300+`.
- **Headless blocked by Google.** Use headed Chromium. `xvfb-run` fallback for cron/remote.
- **Image generation geo-blocked in some regions** (returns "can't create it right now").
- **`--collab` must force exact filename + real content** in diff header. `apply_gem_diff.py` rejects empty/whitespace-only diffs.
- **`apply_gem_diff.py`** previously crashed with `SameFileError` on in-place patch (fixed).

## gemini-web (companion CLI)

For non-Gem operations, use `gemini-web`:
```bash
gemini-web chat "prompt"           # Direct chat (fastest)
gemini-web multi "turn1" "turn2"   # Multi-turn
gemini-web img "description"       # Image generation
gemini-web research "topic"        # Deep research
gemini-web account                 # Account info + model
gemini-web gems                    # List Gems
gemini-web history                 # Chat history
```

Set `GEMINI_CDP` env var to point to your CDP server (default: `http://127.0.0.1:9224`).

## Verification

```bash
gem-pw --help                       # JSON help
gem-pw <id> "1+1=?" -o /tmp/c.md    # chat → read /tmp/c.md
gemini-web chat "hello"             # direct chat
gemini-web account                  # account status
```

## License

MIT

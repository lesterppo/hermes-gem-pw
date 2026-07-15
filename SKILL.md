---
name: gem-pw
description: Browser-automated Gemini Gem driver (CDP) with create, review, chat, upload, delete, img.
version: 5.0.0
author: lesterppo
tags: [gemini, gem, cli, playwright, cdp, browser-automation]
platforms: [linux, macos, wsl]
metadata:
  hermes:
    category: automation
    related_skills: [browser-cdp, gem-cli]
    config:
      gem_cdp_endpoint: "http://127.0.0.1:9223"
      gem_output: "/tmp"
---

# gem-pw — Gemini Gem driver via live CDP browser

Single agent-native CLI for driving Gemini Gems through the live, signed-in
browser that is already running on the host. No API keys, no cookie
extraction, no launcher. It connects to the browser's Chrome DevTools Protocol
(CDP) endpoint and drives the real Gemini web UI.

Two front-ends share the same backend ideas:

- **`gem.py`** (recommended) — connects to a running CDP browser on port 9223
  (the Hermes-headed-Chromium server). Subcommands: `create | review | chat |
  upload | delete | img`. This is the consolidated, tested tool.
- **`gem-pw`** (legacy) — launches its own persistent Chromium per call. Useful
  when no CDP server is available.

## When to Use

- Need to interact with a shared Gemini Gem via URL/id.
- gemini-webapi returns UNAUTHENTICATED for Gem operations (Jul 2026).
- Need file upload, image generation, or multi-round review via the Gem web UI.
- Need Pro + Extended Thinking with conversation continuity.
- Need Gem CRUD (create, edit, delete).

## Prerequisites (gem.py)

1. A CDP-capable browser is running with remote debugging.
   - **Hermes headed Chromium server:** port **9223** (default).
   - **Windows Chrome (alternative):** port **9222**, launched with
     `--remote-debugging-port=9222`. Reachable from WSL only after ADMIN
     PowerShell `netsh interface portproxy` + a `New-NetFirewallRule` for 9222.
2. The browser is signed into a Google account with **Gemini Advanced**, so the
   model picker offers **3.1 Pro + Extended thinking**. An account without
   Gemini Advanced silently downgrades a "Pro" review to Flash and invalidates
   it — verify the picker label before reviewing.
3. Python + Playwright: `pip install playwright && playwright install chromium`.
4. `browser.allow_private_urls: true` is NOT required (we use `connect_over_cdp`,
   not raw `Page.navigate`).

## How to Run (gem.py)

Global flags `--cdp` (default `http://127.0.0.1:9223`), `--json` (compact JSON
to STDOUT), and `-q` (quiet STDERR) may appear before or after the subcommand.
Pass `--json` when driven by an agent — the full Gem reply is always written to
a file on disk; STDOUT only carries the pointer.

### 1. Create the Gem (one time) under the correct account

`gem.py create` aborts if more than one Google account is detected (so you never
create the Gem under the wrong account), selects **3.1 Pro + Extended thinking**
by default, saves, and prints `GEM_ID=...`. Optional `--knowledge-file` /
`--knowledge-folder` attach knowledge.

```bash
python3 gem.py create \
  --name "Double Pendulum Sim Designer" \
  --instructions /path/to/instructions.txt \
  --cdp http://127.0.0.1:9223            # or --json for agent parsing
```

### 2. Run the review (continuous conversation)

`gem.py review` attaches file(s) + a prompt, sends, waits for the Gem's reply,
writes it to `--out`, and **persists the conversation URL to `--conv`**. On the
next call, if `--conv` exists, it *resumes the same thread* (continuous context)
— the key to a valid multi-round review.

```bash
# Round 1 (new conversation)
python3 gem.py review \
  --gem <GEM_ID> --prompt /path/to/round1.txt --out /tmp/review_r1.md \
  --conv /tmp/conv_url.txt --cdp http://127.0.0.1:9223 \
  /path/to/source.py /path/to/diagram.png

# Round 2+ (resume same conversation — do NOT change --conv path)
python3 gem.py review \
  --gem <GEM_ID> --prompt /path/to/round2.txt --out /tmp/review_r2.md \
  --conv /tmp/conv_url.txt --cdp http://127.0.0.1:9223 \
  /path/to/source.py
```

Run each call in the background with `notify_on_complete=true` (Gem Pro+Extended
can take several minutes; foreground caps at 600s).

### 3. Other commands

```bash
# Upload a file then ask the Gem (single turn)
python3 gem.py upload \
  --gem <GEM_ID> --file /path/to/data.csv --prompt "Summarize this" -o /tmp/up.md

# Plain chat (continuous with --conv)
python3 gem.py chat --gem <GEM_ID> --prompt "Explain X" -o /tmp/c.md --conv /tmp/c_conv.txt

# Delete a Gem
python3 gem.py delete --gem <GEM_ID>

# Generate an image inside the Gem
python3 gem.py img --gem <GEM_ID> --prompt "A schematic of a double pendulum" -o /tmp/img.md
```

## Quick Reference

- One tool: `gem.py` with subcommands `create | review | chat | upload | delete | img`.
- `review` = multi-round file+ppt review (resumes thread via `--conv`); `chat` = plain
  text chat (also continuous with `--conv`); both share the same reply-capture + model-picker logic.
- CDP endpoint default: `http://127.0.0.1:9223` (Hermes server) · alt `9222` (Windows Chrome).
- `--json` → compact JSON result on STDOUT (`{"ok":true,"f":"/tmp/...","s":1234,"t":12.3,...}`);
  full Gem reply always saved to file (path in `"f"`); progress logs on STDERR only.
- Gem chat URL: `https://gemini.google.com/gem/<GEM_ID>` (NOT `/gems/<id>` — that 404s).
- File attach: click **Upload & tools** → **Upload files**, then `input[type=file]` (hidden,
  set via `set_input_files`).
- Image generation: open **Upload & tools** → **Create image**, type prompt, send; the tool
  waits for the generated image and captures the response. (Account may hit a daily image quota.)
- Account-safety: `create` aborts if >1 Google account is detected.
- Output dir defaults to `$HOME/.cache/gem-pw/` (or `--out` to override).

## Output Format

**Success (chat/review/upload/img):**
```json
{"ok": true, "action": "review", "f": "/tmp/review_r1.md", "s": 1234, "t": 12.3, "gem": "<GEM_ID>", "conv": "/tmp/conv_url.txt"}
```
**Create:**
```json
{"ok": true, "action": "create-gem", "id": "<GEM_ID>", "name": "Double Pendulum Sim Designer"}
```
**Error:**
```json
{"ok": false, "err": "NO_SIGNED_IN", "msg": "..."}
```

Error codes: `NO_SIGNED_IN`, `MULTI_ACCOUNT`, `NO_SAVE`, `NO_REDIRECT`, `NO_INPUT`,
`EMPTY`, `FILE_NOT_FOUND`, `NO_PROMPT`, `NO_CONV`, `MODE_PICKER`, `NAV_FAIL`, `BAD_URL`.

## Pitfalls

- **Correct account required.** A non-Gemini-Advanced account silently downgrades Pro to Flash.
- **One CDP session at a time.** The tool reuses the shared browser context; don't run two
  `gem.py` calls against the same Gem page concurrently.
- **Pro + Extended Thinking is slow.** First-turn reviews can take 1-3 min; run in background.
- **Gemini "Refining / Answer now" interstitial** is treated as still-loading (not a final answer).
- **Save → redirect is slow** on a fresh Gem (can exceed 40s); the tool falls back to a name
  lookup to capture `GEM_ID`.
- **Image gen quota.** Gemini may decline image generation once a daily limit is reached.
- **Xvfb required in WSL** for the headed Chromium CDP server: `Xvfb :0 -screen 0 1920x1080x24 &`.

## Verification

```bash
# Help
python3 gem.py --help

# Create a throwaway Gem
ID=$(python3 gem.py create --name "TestGem" --instructions /tmp/inst.txt --json | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")

# Chat
python3 gem.py chat --gem "$ID" --prompt "1+1=?" -o /tmp/c.md

# Delete it
python3 gem.py delete --gem "$ID"
```

## Legacy: gem-pw (standalone)

`gem-pw` launches its own persistent Chromium per call (profile at
`~/.gemini-cli/cr-profile/`). It covers the same Gem operations but does not
reuse a running CDP server. Use it when no CDP endpoint is available. See its
`--help` for the full flag set.

As of v4.2 (2026-07-15) gem-pw also gained: a multi-account guard before
create/edit (refuses >1 signed-in account to avoid silent Pro→Flash
downgrade), a verified model picker that retries until Pro+Extended is
confirmed (and logs `model not confirmed` if the base model won't engage via
automation), and a fix for a `_click_text_button` crash that broke all saves.

## License

MIT

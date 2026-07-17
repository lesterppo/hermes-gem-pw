# gem-pw — Gemini Gem CLI via Browser Automation

AI-agent-native CLI for interacting with **Gemini Gems** through browser
automation. No API keys, no cookie extraction, no external server. Sign in
once, then all commands work.

> **One tool, not two.** This repo ships a single self-contained CLI: **`gem-pw`**.
> It contains the full consolidated feature set (chat, create, edit, delete,
> upload, image, **and `--collab`** — the token-efficient surgical-diff protocol).
> An older `gem.py` existed historically but is now superseded by `gem-pw` and is
> **no longer in this repo**. Do not look for it.

```text
gem-pw <gem-id> "prompt"                  → Chat (single turn)
gem-pw <gem-id> -c sess.json "prompt"     → Multi-turn (persists conversation)
gem-pw --collab <gem-id> -f file "instr"  → Request a UNIFIED DIFF only (token-efficient)
gem-pw --create "Name" "Instructions"      → Create Gem
gem-pw --edit <gem-id> --name "New"        → Edit Gem
gem-pw --delete <gem-id>                   → Delete Gem
gem-pw --upload <gem-id> -f file "Q"       → Upload + ask
gem-pw --img <gem-id> "description"        → Generate image
gem-pw --help                              → Full help (JSON)
```

## Why

`gemini-webapi`'s internal RPC API returns **UNAUTHENTICATED** for Gem
operations (as of July 2026). `gem-pw` bypasses this by driving the real
Gemini web UI through a **headless/headed Chromium** browser via Playwright.

A **Gem is a UI construct** — its bundled instruction + knowledge are NOT
exposed by the raw Gemini API, so the Gemini Interactions API /
`GEMINI_API_KEY` **cannot target a specific Gem**. The ONLY working backend is
`gem-pw` (browser). Do not build or claim an API fallback that would silently
ignore the Gem. (This is why the Hermes-native `gem_collab`/`gem_chat` tools
are gem-pw-only — see "For Hermes Agents" below.)

## Install

```bash
git clone https://github.com/lesterppo/hermes-gem-pw
cd hermes-gem-pw
bash install.sh
```

`install.sh` installs `playwright`/`aiohttp`, downloads Chromium, and copies
`gem-pw` + `gem-pw-login` to `~/.local/bin/`.

## Setup (one-time)

```bash
gem-pw-login   # Opens Chromium → sign into Gemini (needs an X display)
```

`gem-pw` is **CDP-first**: if a running headed Chromium page server is alive on
`http://127.0.0.1:9223` (e.g. the Hermes `hermes_cdp_server.py` / `cr-server`),
it connects to that warm browser (multi-turn, no cold-start). Otherwise it
launches its own headed Chromium (profile at `~/.gemini-cli/cr-profile/`).

## Usage

```bash
# Chat with a Gem (from URL or ID)
gem-pw 9d8c15f86f8b "Explain EBITDA in 2 sentences"

# Multi-turn conversation
gem-pw 9d8c15f86f8b -c /tmp/session.json "Remember that my favorite color is blue"
gem-pw 9d8c15f86f8b -c /tmp/session.json "What is my favorite color?"

# Model selection + extended thinking
gem-pw 9d8c15f86f8b -m pro --thinking extended -t 600 "deep analysis"

# Create a Gem with knowledge
gem-pw --create "My Bot" "You are a helpful assistant" -m pro
gem-pw --create "Analyzer" "Analyze code" \
  --knowledge-file paper.pdf \
  --knowledge-code https://github.com/user/repo \
  --knowledge-folder /path/to/project

# Edit / Delete / Upload / Image
gem-pw --edit <id> --name "New Name"
gem-pw --delete abc123
gem-pw --upload 9d8c15f86f8b -f report.pdf "Summarize this"
gem-pw --img 9d8c15f86f8b "A cat on a rainbow"
```

### `--collab` — the token-efficient diff protocol

Instead of re-emitting the whole file every turn, `--collab` asks the Gem to
return a **unified diff only**. This cuts later-round token cost dramatically.

```bash
gem-pw --collab <gem-id> -f current.py "Add a retry() helper" -o resp.md -t 300
# Gem returns a diff block:  --- a/current.py / +++ b/current.py / @@ ...
python3 apply_gem_diff.py resp.md current.py           # apply it
python3 apply_gem_diff.py resp.md current.py --dry      # preview only
```

`apply_gem_diff.py` (ships in this repo) extracts the **first** diff block from
the Gem's response (ignoring any off-protocol prose the model appends), runs a
`patch -p0 --dry-run`, and applies it. It **rejects empty / whitespace-only
diffs** (`EMPTY_DIFF`) so a no-op never reports success.

**Protocol rule (verified):** the `--collab` prompt MUST force the exact
uploaded filename as the diff header (`--- a/<name>` / `+++ b/<name>`) and at
least one real added/removed line. A knowledge/persona Gem (e.g. a
paper-knowledge Gem) follows the protocol less tightly and may append an essay
after the diff — `apply_gem_diff.py` ignores the trailing prose, but prefer a
**dedicated coding Gem** for cleanest results.

## For Hermes Agents

This tool is built for AI-agent consumption:

- **Token-efficient**: ~100-char JSON pointer on STDOUT; full reply on disk.
- **Self-describing errors**: error codes tell the agent what to do next.
- **File-based I/O**: responses on disk, pointer JSON on stdout.
- **Multi-turn**: `-c session.json` persists conversation across agent turns.
- **Headless fallback**: if `DISPLAY` is unset and `xvfb-run` exists, gem-pw
  transparently re-execs under `xvfb-run -a` (still headed mode, anti-detection
  preserved). Set `GEM_PW_XVFB=0` to disable. This makes cron/remote use work
  with zero config.

### Native Hermes tool (recommended integration)

To expose Gem collaboration directly as Hermes model tools, drop two files into
a Hermes agent checkout and enable the toolset:

1. Copy `gem_tool.py` → `<hermes-agent>/tools/gem_tool.py`
2. Copy `apply_gem_diff.py` → `<hermes-agent>/tools/apply_gem_diff.py` (or keep
   it at `~/.hermes/scripts/apply_gem_diff.py` and point the tool at it)
3. Add `"gem"` to `CONFIGURABLE_TOOLSETS` in `hermes_cli/tools_config.py` (or
   rely on the auto-enable: the `gem` toolset auto-appears when `gem-pw` is on
   PATH — see the resolver's `_gem_pw_present()` auto-enable, mirroring the
   `x_search` / `homeassistant` convention).
4. The `gem` toolset provides two agent-native tools:
   - **`gem_collab`** — `gem-pw --collab` + optional auto-apply. Args:
     `gem_id`, `file_path`, `instruction`, `apply` (bool), `timeout`.
   - **`gem_chat`** — `gem-pw` single/multi-turn chat. Args: `gem_id`,
     `message`, `session_file`, `model`, `thinking`, `timeout`.

Both return the same pointer JSON `{ok, f, s, t}` and write the full Gem reply
to disk. They are **gem-pw-only** (no API fallback) for the UI-construct reason
above.

## Output

All commands return compact JSON on stdout. Response saved to file.

```json
{"ok": true, "f": "/home/USER/.hermes/gem_pw_output/gem-pw-1783463794.md", "s": 16, "t": 11.7}
```

Output directory is profile-aware: `$HERMES_HOME/gem_pw_output/` when
`HERMES_HOME` is set, else `~/.hermes/gem_pw_output/`. Override with
`GEM_PW_OUTPUT_DIR` or `-o <file>`.

## Requirements

- Python 3.10+
- Playwright + Chromium (`playwright install chromium`)
- aiohttp
- An X display for headed login (or `xvfb-run` for headless fallback)

## How It Works

```text
gem-pw → (CDP if 9223 alive) else launch_persistent_context → Chromium (headed)
         └─ uses ~/.gemini-cli/cr-profile/  (or $HERMES_HOME/.gemini-cli/cr-profile/)
         └─ profile persists session across calls
         └─ page.evaluate() for custom element interaction
```

## Changelog

### v4.3 (Jul 2026) — xvfb fallback + native Hermes tool
- **Headless fallback**: when `DISPLAY` is unset and `xvfb-run` exists, re-exec
  under `xvfb-run -a` (headed Chromium on a virtual display). Gated by
  `GEM_PW_XVFB` (default auto; `0` disables). Sentinel env var prevents re-exec
  loops. Enables cron/remote use with zero config.
- **`--collab` strict protocol**: prompt now forces the exact uploaded filename
  as the diff header + real content (no empty diffs).
- **Native Hermes tool** `gem_tool.py` (`gem_collab` + `gem_chat`) + the `gem`
  toolset (auto-enabled when gem-pw is on PATH). `apply_gem_diff.py` rejects
  empty/whitespace-only diffs and no longer crashes with SameFileError.

### v4.2 (Jul 2026) — Ported safety + verified model picker
- Multi-account guard before `--create`/`--edit -m` (refuses >1 signed-in
  account to avoid silent Pro→Flash downgrade).
- Verified model picker: retries until Pro + Extended confirmed; logs
  `model not confirmed` if the account's quota only offers Flash-Lite.
- Fixed `_click_text_button` crash (evaluate → evaluate_handle + real click).

### v4.1 (Jul 2026) — Locale-agnostic + English verified
- Selectors try zh-TW → English → structural fallback. No code change needed to
  switch Gemini language.
- Pro + Extended Thinking: reopens the model menu before the Extended-thinking
  click (Google closes the menu after every selection).

### v4 (Jul 2026)
- `--edit`, `-t` (timeout), `--help` (JSON), `-o` (output path).

## Privacy

This repo contains **no API keys, tokens, cookies, or personal identifiers**.
All paths use `Path.home()` / `$HOME` / `$HERMES_HOME`. The browser profile it
creates at runtime holds YOUR Gemini session — that profile is git-ignored and
must never be committed.

## License

MIT

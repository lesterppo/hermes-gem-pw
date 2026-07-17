---
name: gem-pw
description: Browser-automated Gemini Gem driver (CDP-first) with chat, create, edit, delete, upload, img, and --collab surgical-diff review.
version: 4.3.0
author: Peter (lesterppo)
tags: [gemini, gem, cli, playwright, cdp, browser-automation]
platforms: [linux, macos, wsl]
metadata:
  hermes:
    category: automation
    related_skills: [gem-collab, browser-cdp, gem-cli]
    config:
      gem_cdp_endpoint: "http://127.0.0.1:9223"
      gem_pw_output_dir: "$HERMES_HOME/gem_pw_output"
---

# gem-pw — Gemini Gem driver via browser automation

Single agent-native CLI for driving Gemini Gems through a live / launched
Chromium browser. No API keys, no cookie extraction, no launcher. It is
**CDP-first**: connects to a running headed Chromium page server (default
`http://127.0.0.1:9223`) when one is alive, and falls back to launching its own
headed Chromium (profile at `~/.gemini-cli/cr-profile/`) only when CDP is
unavailable. This bypasses `gemini-webapi`'s broken RPC auth by driving the
real Gemini web UI.

> One tool, not two. This repo ships only `gem-pw` (fully consolidated: chat,
> create, edit, delete, upload, img, **and `--collab`**). The older `gem.py` is
> superseded and not in the repo.

## When to Use

- Need to interact with a shared Gemini Gem via URL/id.
- `gemini-webapi` returns UNAUTHENTICATED for Gem operations (Jul 2026).
- Need file upload, image generation, or multi-round review via the Gem web UI.
- Need Pro + Extended Thinking with conversation continuity.
- Need **token-efficient code/design iteration** via `--collab` surgical diffs.
- Need Gem CRUD (create, edit, delete).

## Prerequisites

1. Python 3.10+ and `pip install playwright aiohttp && playwright install chromium`.
2. A Gemini session: run `gem-pw-login` once (opens Chromium → sign in). The
   profile persists at `~/.gemini-cli/cr-profile/` (or
   `$HERMES_HOME/.gemini-cli/cr-profile/`).
3. For the prioritized CDP path, a headed Chromium page server must be alive:
   `cr-server start --headed` (or `hermes_cdp_server.py`) on port **9223**.
   Without it, gem-pw falls back to its own headed Chromium (needs an X display,
   or `xvfb-run` — see Pitfalls).
4. A Gemini Advanced (Pro+Extended) account is required for Pro/Extended — a
   non-Advanced account silently downgrades Pro→Flash.

## How to Run

Global flags `--cdp` (default `http://127.0.0.1:9223`), `--no-cdp` (force own
browser), `--json-out` (compact JSON to STDOUT), `-o <file>` (output path),
`-t <seconds>` (timeout, default 120, max 600), `--brief`, `--new` may appear
before or after the subcommand. Pass `--json-out` when driven by an agent.

### 1. Chat / multi-turn

```bash
gem-pw <gem-id> "prompt"
gem-pw <gem-id> -c /tmp/sess.json "prompt"     # persists conversation
gem-pw <gem-id> -m pro --thinking extended -t 600 "deep analysis"
```

### 2. `--collab` — surgical-diff iteration (preferred for code/design)

```bash
gem-pw --collab <gem-id> -f current.py "Add a retry() helper" -o resp.md -t 300
python3 apply_gem_diff.py resp.md current.py            # apply
python3 apply_gem_diff.py resp.md current.py --dry      # preview
```

The Gem returns a UNIFIED DIFF only. `apply_gem_diff.py` extracts the first
diff block, dry-runs `patch -p0`, and applies. **Never pass `-m/--thinking` at
collab time** unless overriding — it can silently downgrade Pro→Flash.

### 3. Gem CRUD

```bash
gem-pw --create "Name" "Instructions" -m pro --thinking extended
gem-pw --create "Analyzer" "Analyze code" --knowledge-file paper.pdf \
  --knowledge-code https://github.com/user/repo --knowledge-folder /path/to/proj
gem-pw --edit <id> --name "New" --instructions "New prompt..."
gem-pw --delete <id>
gem-pw --upload <id> -f file "Summarize this"
gem-pw --img <id> "A schematic of a double pendulum"
```

## Quick Reference

| Need | Command |
|------|---------|
| Chat | `gem-pw <id> "prompt"` |
| Multi-turn | `gem-pw <id> -c sess.json "prompt"` |
| Diff-based iteration | `gem-pw --collab <id> -f file "instr" -o r.md` |
| Apply the diff | `python3 apply_gem_diff.py r.md file [--dry]` |
| Create / edit / delete | `gem-pw --create/--edit/--delete <id> ...` |
| Upload / image | `gem-pw --upload/--img <id> ...` |
| Force own browser (no CDP) | `gem-pw --no-cdp ...` |
| Headless auto-wrap | (automatic when DISPLAY unset + xvfb-run present) |

## Output Format

Success (chat/collab/upload/img):
```json
{"ok": true, "f": "/home/USER/.hermes/gem_pw_output/gem-pw-<ts>.md", "s": 123, "t": 12.3}
```
The full Gem reply is saved to `f` (read it with `read_file`). The JSON is
~100 chars — intentionally token-efficient. Output dir is profile-aware
(`$HERMES_HOME/gem_pw_output/`, else `~/.hermes/gem_pw_output/`; override with
`GEM_PW_OUTPUT_DIR` or `-o`).

Error codes: `NO_SIGNED_IN`, `MULTI_ACCOUNT`, `NO_SAVE`, `NO_REDIRECT`,
`NO_INPUT`, `EMPTY`, `FILE_NOT_FOUND`, `NO_PROMPT`, `NO_CONV`, `MODE_PICKER`,
`NAV_FAIL`, `BAD_URL`, `LOCKED`, `NO_DISPLAY`.

## Pitfalls

- **Correct account required.** A non-Gemini-Advanced account silently
  downgrades Pro to Flash.
- **One browser at a time.** Concurrent gem-pw runs collide on the Chromium
  profile → second returns `LOCKED`. Run sequentially. The lock self-heals
  (steals from a dead PID) so a crashed run doesn't wedge future calls.
- **Pro + Extended Thinking is slow** (1-3 min). Run in the background;
  foreground caps at ~60s in some hosts.
- **Headless fails on Gemini** (anti-bot "Just a moment..."). Use **headed**.
  The xvfb fallback keeps headed mode on a virtual display for cron/remote.
- **`--collab` prompt MUST force the exact filename + real content** (verified
  Jul 2026). Left vague, the Gem emits `--- a/file.py` (wrong name → `patch -p0`
  can't apply) and/or an empty diff. `apply_gem_diff.py` rejects empty /
  whitespace-only diffs (`EMPTY_DIFF`).
- **A knowledge/persona Gem** (e.g. a paper-knowledge Gem) follows the diff
  protocol less tightly and may append an essay after the diff —
  `apply_gem_diff.py` ignores the trailing prose (extracts only the first diff
  block). Prefer a dedicated *coding* Gem for cleanest results.
- **`apply_gem_diff.py` gotchas (verified Jul 2026):** rejects empty /
  whitespace-only diffs; previously crashed with `SameFileError` when `patch`
  applied in place with a non-zero exit (now `out` is only `orig` when applied,
  fallback copies to a distinct `.applied` path). Re-test with a real AND an
  empty diff after any edit.

## Verification

```bash
gem-pw --help                       # JSON help
gem-pw <id> "1+1=?" -o /tmp/c.md    # chat; read /tmp/c.md
# CDP path: log shows "connected via CDP (http://127.0.0.1:9223)"
# Apply: apply_gem_diff.py reports {"ok": true, "applied": true}
```

## Hermes-native integration

`gem_tool.py` (ships alongside this skill / repo) registers two agent-native
tools — `gem_collab` and `gem_chat` — backed by gem-pw (browser only, no API
fallback). Enable the `gem` toolset (auto-enabled when gem-pw is on PATH; or add
`gem` to `CONFIGURABLE_TOOLSETS` in `hermes_cli/tools_config.py`). See README
"For Hermes Agents" for the drop-in steps.

## License

MIT

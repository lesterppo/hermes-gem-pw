"""
Gem collaboration tools — agent-native bridge to Gemini Gems via gem-pw.

Why gem-pw (browser) is the backend, not the Gemini API:
  A "Gem" is a UI construct — it bundles a system instruction + uploaded
  knowledge that the raw Generative Language API does not expose. The
  gemini.google.com/gem/<id> endpoint is the ONLY way to target a specific
  Gem's instructions and knowledge base. So every Gem-targeting operation
  (chat inside a Gem, upload, collab) MUST go through the browser backend.
  We do NOT fake an API fallback that silently ignores the Gem — that would
  produce wrong results. gem-pw is the working, verified path.

Tools:
  gem_collab  — upload a current artifact + ask the Gem for a SURGICAL diff
                only (token-efficient review loop). Optionally auto-applies the
                returned unified diff via apply_gem_diff.py.
  gem_chat    — single-turn (or -c multi-turn) chat inside a Gem; saves the
                full response to disk and returns a pointer JSON.

Pointer pattern: the real artifact lives on disk; stdout is a compact JSON
pointer ({ok, f, s, t}) so the agent loop stays token-cheap.

Backend discovery: gem-pw is resolved on PATH, then the canonical copy at
~/.local/bin/gem-pw, then ~/gemini-cli/gem-pw. The tool is gated (check_fn)
on gem-pw being present AND a DISPLAY being available (headed Chromium needs
an X server; the tool degrades to a clear error if not).

CDP mode: gem-pw auto-connects to a running hermes_cdp_server.py (9223) when
alive, which keeps the signed-in Pro/Extended session warm. No flags needed.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from tools.registry import registry


# ── Path resolution ────────────────────────────────────────────────────────

def _gem_pw_path() -> str | None:
    """Return the gem-pw executable path, or None if not found."""
    on_path = shutil.which("gem-pw")
    if on_path:
        return on_path
    candidates = [
        Path.home() / ".local" / "bin" / "gem-pw",
        Path.home() / "gemini-cli" / "gem-pw",
        Path.home() / "hermes-gem-pw" / "gem-pw",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _apply_diff_path() -> str | None:
    candidates = [
        Path.home() / ".hermes" / "scripts" / "apply_gem_diff.py",
        Path.home() / "hermes-gem-pw" / "apply_gem_diff.py",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _check_requirements() -> bool:
    """Service-gate: gem-pw must exist. DISPLAY is checked at call time
    (the agent may run headless; we surface a clear error rather than hide)."""
    return _gem_pw_path() is not None


# ── Helpers ────────────────────────────────────────────────────────────────

def _run_gem_pw(args: list[str], timeout: int = 300) -> dict:
    """Run gem-pw and return parsed JSON. Never raises — always JSON."""
    gp = _gem_pw_path()
    if not gp:
        return {"ok": False, "err": "GEM_PW_MISSING",
                "msg": "gem-pw not found on PATH or in ~/.local/bin/gem-pw, "
                       "~/gemini-cli/gem-pw. Install it from lesterppo/hermes-gem-pw."}
    if not os.environ.get("DISPLAY"):
        return {"ok": False, "err": "NO_DISPLAY",
                "msg": "gem-pw needs a headed Chromium (X server). DISPLAY is not "
                       "set. Run the agent under an X session (e.g. Xvfb :0) or "
                       "start hermes_cdp_server.py."}
    cmd = [gp] + args + ["--json-out"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "err": "TIMEOUT",
                "msg": f"gem-pw exceeded {timeout}s (Gem Pro+Extended codegen is slow)."}

    # gem-pw prints ONE JSON object on the last line; logs go to stderr.
    out = (proc.stdout or "").strip().splitlines()
    last_json = None
    for line in reversed(out):
        line = line.strip()
        if line.startswith("{"):
            last_json = line
            break
    if not last_json:
        # Stderr may carry the reason (e.g. NOT_SIGNED_IN, LOCKED).
        err = (proc.stderr or "").strip().splitlines()[-1] if proc.stderr else ""
        return {"ok": False, "err": "NO_JSON",
                "msg": f"gem-pw returned no JSON. exit={proc.returncode}. "
                       f"last_log={err[:200]}"}
    try:
        return json.loads(last_json)
    except json.JSONDecodeError as e:
        return {"ok": False, "err": "BAD_JSON", "msg": f"parse error: {e} :: {last_json[:200]}"}


def _apply_diff(resp_file: str, orig_file: str) -> dict:
    """Apply the Gem's returned diff via apply_gem_diff.py (if available)."""
    ap = _apply_diff_path()
    if not ap:
        return {"applied": False, "note": "apply_gem_diff.py not found; manual apply needed"}
    try:
        proc = subprocess.run(
            ["python3", ap, resp_file, orig_file],
            capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return {"applied": False, "note": "apply_gem_diff.py timed out"}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {"applied": False}
    except (json.JSONDecodeError, IndexError):
        return {"applied": False, "note": f"apply failed: {proc.stderr[:200]}"}


# ── Tool handlers ──────────────────────────────────────────────────────────

def gem_collab(param: str = "", task_id: str = None, **kw) -> str:
    """Upload a current artifact to a Gem and request a surgical diff only.

    Args (passed as a JSON string in `param`):
      gem_id   (str, required): the Gem id from gemini.google.com/gem/<id>
      file     (str, required): absolute path of the artifact to upload
      instruction (str, required): what change to make
      out      (str, optional): where to save the Gem's response (default auto)
      apply    (bool, optional): if true, auto-apply the returned diff to `file`
      timeout  (int, optional): seconds (default 300)

    Returns: pointer JSON {ok, f (response path), applied, s, t, ...}
    """
    try:
        args = json.loads(param) if param else {}
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "err": "BAD_ARGS",
                           "msg": "param must be JSON: {gem_id, file, instruction, [out], [apply], [timeout]}"})

    gem_id = args.get("gem_id") or args.get("gem") or ""
    file_path = args.get("file") or args.get("file_path") or ""
    instruction = args.get("instruction") or args.get("task") or ""
    out = args.get("out")
    do_apply = bool(args.get("apply", False))
    timeout = int(args.get("timeout", 300))

    if not gem_id or not file_path or not instruction:
        return json.dumps({"ok": False, "err": "USAGE",
                           "msg": "gem_collab needs gem_id, file, and instruction"})
    if not Path(file_path).exists():
        return json.dumps({"ok": False, "err": "FILE_NOT_FOUND", "msg": file_path})

    cli = ["--collab", gem_id, "-f", file_path, instruction]
    if out:
        cli += ["-o", out]
    res = _run_gem_pw(cli, timeout=timeout)
    if not res.get("ok"):
        return json.dumps(res)

    # Enrich with apply result if requested and a diff was returned.
    if do_apply and res.get("f"):
        res["apply"] = _apply_diff(res["f"], file_path)
        res["applied"] = res["apply"].get("applied", False)
    return json.dumps(res)


def gem_chat(param: str = "", task_id: str = None, **kw) -> str:
    """Single-turn (or multi-turn) chat inside a Gem; saves response to disk.

    Args (JSON string in `param`):
      gem_id   (str, required): Gem id from gemini.google.com/gem/<id>
      prompt   (str, required): the message
      conv     (str, optional): conversation session file for multi-turn (-c)
      out      (str, optional): response output path
      new      (bool, optional): start a fresh conversation (ignore conv)
      timeout  (int, optional): seconds (default 120)

    Returns: pointer JSON {ok, f, s, t, ...}
    """
    try:
        args = json.loads(param) if param else {}
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "err": "BAD_ARGS",
                           "msg": "param must be JSON: {gem_id, prompt, [conv], [out], [new], [timeout]}"})

    gem_id = args.get("gem_id") or args.get("gem") or ""
    prompt = args.get("prompt") or ""
    conv = args.get("conv")
    out = args.get("out")
    new = bool(args.get("new", False))
    timeout = int(args.get("timeout", 120))

    if not gem_id or not prompt:
        return json.dumps({"ok": False, "err": "USAGE", "msg": "gem_chat needs gem_id and prompt"})

    cli = [gem_id, prompt]
    if conv:
        cli += ["-c", conv]
    if new:
        cli += ["--new"]
    if out:
        cli += ["-o", out]
    return json.dumps(_run_gem_pw(cli, timeout=timeout))


# ── Schemas ─────────────────────────────────────────────────────────────────

GEM_COLLAB_SCHEMA = {
    "name": "gem_collab",
    "description": (
        "Collaborate with a Gemini Gem on a code/artifact file: uploads the file "
        "and asks the Gem for a SURGICAL unified diff (token-efficient review loop). "
        "Set apply=true to auto-apply the returned diff. Backed by gem-pw (browser); "
        "the Gem's instructions/knowledge are only reachable via the Gem UI, not the raw API. "
        "Args: gem_id (Gem id from gemini.google.com/gem/<id>), file (abs path), "
        "instruction (change to make), optional out/apply/timeout."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "gem_id": {"type": "string", "description": "Gem id from gemini.google.com/gem/<id>"},
            "file": {"type": "string", "description": "Absolute path of the artifact to upload"},
            "instruction": {"type": "string", "description": "What change to request (e.g. 'add a subtract function')"},
            "out": {"type": "string", "description": "Optional output path for the Gem's response"},
            "apply": {"type": "boolean", "description": "If true, auto-apply the returned diff to file"},
            "timeout": {"type": "integer", "description": "Seconds to wait (default 300; Pro+Extended is slow)"},
        },
        "required": ["gem_id", "file", "instruction"],
    },
}

GEM_CHAT_SCHEMA = {
    "name": "gem_chat",
    "description": (
        "Chat with a Gemini Gem (single or multi-turn). Saves the full response to disk "
        "and returns a pointer JSON. Backed by gem-pw (browser) — the only path that "
        "targets a Gem's instructions/knowledge. "
        "Args: gem_id, prompt, optional conv (multi-turn session file)/new/out/timeout."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "gem_id": {"type": "string", "description": "Gem id from gemini.google.com/gem/<id>"},
            "prompt": {"type": "string", "description": "The message to send"},
            "conv": {"type": "string", "description": "Optional conversation session file for multi-turn (-c)"},
            "new": {"type": "boolean", "description": "Start a fresh conversation (ignore conv)"},
            "out": {"type": "string", "description": "Optional output path for the response"},
            "timeout": {"type": "integer", "description": "Seconds to wait (default 120)"},
        },
        "required": ["gem_id", "prompt"],
    },
}

registry.register(
    name="gem_collab",
    toolset="gem",
    schema=GEM_COLLAB_SCHEMA,
    handler=lambda args, **kw: gem_collab(param=args.get("param", ""), task_id=kw.get("task_id")),
    check_fn=_check_requirements,
    description=GEM_COLLAB_SCHEMA["description"],
    emoji="💎",
)

registry.register(
    name="gem_chat",
    toolset="gem",
    schema=GEM_CHAT_SCHEMA,
    handler=lambda args, **kw: gem_chat(param=args.get("param", ""), task_id=kw.get("task_id")),
    check_fn=_check_requirements,
    description=GEM_CHAT_SCHEMA["description"],
    emoji="💬",
)

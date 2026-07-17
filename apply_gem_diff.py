#!/usr/bin/env python3
"""
apply_gem_diff.py — Agent-native apply side for gem-pw --collab.

The Gem (via `gem-pw --collab <id> -f file.md "instr" -o resp.md`) returns a
surgical change set: a unified diff (diff -u, patch -p0 applicable) and/or
fenced ```newcode blocks for entirely new functions. This tool turns that
response into an applied file.

Usage:
  apply_gem_diff.py <resp.md> <orig_file> [--out <applied.html>] [--dry]

Behavior:
  - Extracts the first ```diff ... ``` (or a raw unified-diff block) and applies
    it to <orig_file> with `patch -p0 --dry-run` first; if clean, applies for real.
  - Any ```newcode blocks are written to <out>.newcode.txt as reference (agent
    decides where to splice them).
  - Emits compact JSON: {ok, applied, newcode_blocks, out, bytes}.

Pointer pattern: the real artifact lives on disk; stdout is just a pointer.
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

def extract_first_diff(text):
    # 1) Prefer a fenced ```diff block.
    m = re.search(r"```diff\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip() + "\n"
    # 2) A raw unified-diff region: starts with a line containing '--- ' and
    #    '+++ ' (Gem sometimes prefixes with the word "Diff" on its own line).
    m = re.search(r"(?:^|\n)((?:--- \S+.*\n(?:\+\+\+ \S+.*\n)(?:[ @+\-].*(?:\n|$))*))", text)
    if m:
        return m.group(1).strip() + "\n"
    # 3) Fallback: any contiguous 'diff -u' region.
    m = re.search(r"(diff -u .*?)(?:\n\n|\Z)", text, re.DOTALL)
    if m:
        return m.group(1).strip() + "\n"
    return None

def extract_newcode(text):
    blocks = re.findall(r"```newcode\s*\n(.*?)```", text, re.DOTALL)
    if not blocks:
        # fall back to generic ``` code blocks if model didn't use 'newcode'
        blocks = re.findall(r"```(?!\w*diff\b)(?:[a-z]*)?\s*\n(.*?)```", text, re.DOTALL)
    return [b.strip() for b in blocks if b.strip()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("resp"); ap.add_argument("orig")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    resp = Path(a.resp); orig = Path(a.orig)
    if not resp.exists(): print(json.dumps({"ok": False, "err": "RESP_NOT_FOUND", "msg": str(resp)})); sys.exit(1)
    if not orig.exists(): print(json.dumps({"ok": False, "err": "ORIG_NOT_FOUND", "msg": str(orig)})); sys.exit(1)

    text = resp.read_text(encoding="utf-8")
    diff = extract_first_diff(text)
    newcode = extract_newcode(text)

    out = Path(a.out) if a.out else (orig.parent / (orig.stem + ".applied" + orig.suffix))
    applied = False
    err = None

    if diff:
        # Reject no-op / whitespace-only diffs: a diff with no real +/- lines
        # (only context, or only blank-line additions) would "apply" cleanly
        # and report success while changing nothing useful — the agent would
        # wrongly believe a change landed. Catch it.
        real_changes = [l for l in diff.splitlines()
                        if (l.startswith("+") or l.startswith("-"))
                        and not l.startswith("+++") and not l.startswith("---")]
        # A +/- line that is only the marker + whitespace is a no-op (e.g.
        # adding a blank line). Require at least one line with real content.
        real_changes = [l for l in real_changes if l[1:].strip() != ""]
        if not real_changes:
            applied = False
            err = "EMPTY_DIFF: diff has no added/removed lines; nothing to apply"
            # Copy orig->out so caller has a base to splice into.
            import shutil as _sh
            _sh.copyfile(orig, out)
        else:
            # Write diff to a temp file, dry-run first.
            tf = tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False, encoding="utf-8")
            tf.write(diff); tf.close()
            dry = subprocess.run(["patch", "-p0", "--dry-run", "-i", tf.name, str(orig)],
                                 capture_output=True, text=True)
            if dry.returncode == 0:
                if not a.dry:
                    res = subprocess.run(["patch", "-p0", "-i", tf.name, str(orig)],
                                         capture_output=True, text=True)
                    applied = (res.returncode == 0)
                    if not applied: err = res.stderr[:400]
                else:
                    applied = True  # dry-run clean
            else:
                err = "DRY_RUN_FAILED: " + dry.stderr[:400]
            Path(tf.name).unlink(missing_ok=True)
            # patch edits `orig` in place. If it applied cleanly, the modified
            # file IS `orig`; report that. If not, leave `out` as the distinct
            # .applied path and copy orig into it below (never orig->orig).
            if applied:
                out = orig
    else:
        err = "NO_DIFF_FOUND"

    # If diff not applied, copy orig->out (a DISTINCT path; never orig itself)
    # so the caller has a base to splice into without clobbering the original.
    if not applied:
        import shutil
        if out.resolve() == orig.resolve():
            out = orig.parent / (orig.stem + ".applied" + orig.suffix)
        shutil.copyfile(orig, out)

    # Always persist newcode blocks as reference.
    if newcode:
        nc_path = out.parent / (out.stem + ".newcode.txt")
        nc_path.write_text("\n\n".join(newcode), encoding="utf-8")

    result = {
        "ok": True,
        "applied": applied,
        "out": str(out),
        "bytes": out.stat().st_size if out.exists() else 0,
        "newcode_blocks": len(newcode),
        "diff_found": bool(diff),
    }
    if err: result["note"] = err
    print(json.dumps(result))

if __name__ == "__main__":
    main()

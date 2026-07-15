#!/usr/bin/env python3
"""gem.py — single AI-agent-native tool for driving Gemini Gems via the
Hermes CDP browser on port 9223 (signed-in, English Gemini, Pro+Extended).

Consolidates gem_create.py + gem_review.py (gemini-gem-review skill) and adds
the full functionality of gem-pw v4 (create w/ knowledge, upload, delete, img,
continuous multi-round review).

Transport: connect_over_cdp to the live headed browser the user is logged into
(A signed-in Gemini Advanced account is required for Pro+Extended reviews). No API key, no launcher, no zh-TW hacks.

Commands:
  gem.py create  --name N --instructions FILE [--model pro] [--thinking extended]
                 [--knowledge-file F ...] [--knowledge-folder D ...] [--cdp URL] [--json]
  gem.py review  --gem ID --prompt FILE --out FILE --conv FILE
                 [--cdp URL] [--timeout 560] [--json] [attachments...]
  gem.py upload  --gem ID --file F --prompt "Q" [-o OUT] [--cdp URL] [--json]
  gem.py delete  --gem ID [--cdp URL] [--json]
  gem.py img     --gem ID --prompt "desc" [-o OUT] [--cdp URL] [--json]

Output contract (token-efficient, agent-native):
  * Logs / progress go to STDERR only (never pollute STDOUT).
  * Result on STDOUT is compact JSON when --json is passed:
      {"ok":true,"action":"review","f":"/tmp/...","s":1234,"t":12.3,
       "conv":"/tmp/conv.txt","gem":"ID"}
      {"ok":false,"err":"CODE","msg":"..."}
  * Without --json, a few compact human lines are printed to STDOUT
    (GEM_ID=..., RESPONSE_CHARS=..., CONV_URL:...).
  * The full Gem reply is always written to a file (pointer in "f").

Continuous review: --conv holds the conversation URL. Pass the SAME --conv path
every round to resume the thread (Gem keeps all prior context). Do NOT open a
new chat per round — that loses context and invalidates the review.
"""
import sys, time, re, json, argparse, zipfile, tempfile
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.stderr.write("FATAL: playwright not importable. pip install playwright && playwright install chromium\n")
    sys.exit(1)

DEFAULT_CDP = "http://127.0.0.1:9223"
OUTPUT_DIR = Path("/tmp")
JSON_OUT = False
QUIET = False

# Gem URLs whose trailing id is a built-in, not a user Gem
_BUILTIN = ("view", "create", "storybook", "brainstormer", "career-guide",
            "coding-partner", "learning-coach", "productivity-helper",
            "writing-editor")


def _log(msg):
    if QUIET:
        return
    ts = datetime.now().strftime("%H:%M:%S")
    sys.stderr.write(f"[gem {ts}] {msg}\n")
    sys.stderr.flush()


def _emit(d):
    """Print result to STDOUT. JSON when --json, else compact lines.
    Guard against BrokenPipeError (e.g. foreground timeout SIGTERM mid-flush)."""
    try:
        if JSON_OUT:
            sys.stdout.write(json.dumps(d) + "\n")
        else:
            if not d.get("ok"):
                sys.stdout.write(f"ERR {d.get('err')}: {d.get('msg')}\n")
                return
            a = d.get("action", "")
            if a == "create-gem":
                sys.stdout.write(f"GEM_ID={d.get('id')}\n")
            elif a == "review":
                sys.stdout.write(f"RESPONSE_CHARS={d.get('s')} -> {d.get('f')}\n")
                sys.stdout.write(f"CONV_URL: {d.get('conv')}\n")
            elif a == "upload":
                sys.stdout.write(f"UPLOAD_CHARS={d.get('s')} -> {d.get('f')}\n")
            elif a == "chat":
                sys.stdout.write(f"CHAT_CHARS={d.get('s')} -> {d.get('f')}\n")
            elif a == "delete-gem":
                sys.stdout.write(f"DELETED {d.get('id')}\n")
            elif a == "img":
                sys.stdout.write(f"IMG_CHARS={d.get('s')} -> {d.get('f')} images={d.get('images')}\n")
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        pass


def _ok(**kw):
    d = {"ok": True}
    d.update(kw)
    return d


def _err(code, msg, **extra):
    d = {"ok": False, "err": code, "msg": msg}
    d.update(extra)
    return d


def connect(cdp):
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(cdp)
    return p, b


def new_page(b):
    ctx = b.contexts[0]
    return ctx.new_page()


# ───────────────────────────── CREATE ─────────────────────────────

def _pick_menu_item(page, text):
    return page.evaluate("""(t) => {
      const items = document.querySelectorAll('[role=menuitem],[role=option],[role=menuitemradio],[role=menuitemcheckbox]');
      for (const it of items) { if ((it.innerText||'').includes(t)) { it.click(); return true; } }
      return false;
    }""", text)


def cmd_create(args):
    name, instr = args.name, Path(args.instructions).read_text(encoding="utf-8")
    p, b = connect(args.cdp)
    try:
        # SAFETY: require exactly one signed-in account (wrong account = Flash-only downgrade)
        v = new_page(b)
        v.goto("https://gemini.google.com/gems/view", wait_until="domcontentloaded", timeout=20000)
        v.wait_for_timeout(4000)
        accts = v.evaluate("""() => {
          const o=[]; document.querySelectorAll('div,span,a').forEach(e=>{
            const t=(e.innerText||'').trim(); if(/^[\\w.+-]+@gmail\\.com$/.test(t)){ if(!o.includes(t)) o.push(t); }});
          return o;
        }""")
        _log(f"accounts: {accts}")
        if len(accts) != 1:
            v.close()
            return _err("MULTI_ACCOUNT",
                        f"expected exactly 1 account, got {len(accts)}. Log out the wrong one first.")
        v.close()

        page = new_page(b)
        page.goto("https://gemini.google.com/gems/create", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        ni = page.query_selector('#gem-name-input')
        if not ni:
            return _err("NO_NAME_INPUT", "name input not found")
        ni.click(); page.wait_for_timeout(300); ni.fill(name)
        _log(f"name: {name}")

        ie = page.query_selector('div.ql-editor[aria-label="Enter a prompt for Gemini"]')
        if not ie:
            return _err("NO_INST_INPUT", "instructions input not found")
        ie.click(); page.wait_for_timeout(300)
        page.keyboard.insert_text(instr)
        page.wait_for_timeout(1200)
        _log("instructions typed")

        # model picker enabled only after name + instructions filled
        btn = None
        for _ in range(30):
            btn = page.query_selector('button[aria-label^="Open mode picker"]')
            if btn and btn.is_enabled():
                break
            page.wait_for_timeout(500)
        if not (btn and btn.is_enabled()):
            return _err("MODE_PICKER", "model picker never enabled")
        model = (args.model or "pro").lower()
        thinking = (args.thinking or "extended").lower()
        base_label = {"pro": "3.1 Pro", "flash": "3.5 Flash", "flash-lite": "Flash-Lite"}.get(model, "3.1 Pro")
        want_ext = thinking in ("extended", "extend")

        def _picker_label():
            return page.evaluate("""() => {
                const b = document.querySelector('button[aria-label^="Open mode picker"]');
                return b ? (b.getAttribute('aria-label')||'') + '|' + (b.innerText||'') : '';
            }""")

        # Select base model, then (optionally) Extended thinking. Verify the
        # picker label reflects the choice; retry a few times (Gem UI is racy).
        for attempt in range(4):
            btn = page.query_selector('button[aria-label^="Open mode picker"]')
            if not (btn and btn.is_enabled()):
                return _err("MODE_PICKER", "model picker never enabled")
            btn.click(); page.wait_for_timeout(2000)
            _pick_menu_item(page, base_label)
            page.wait_for_timeout(1200)
            if want_ext:
                btn2 = page.query_selector('button[aria-label^="Open mode picker"]')
                if btn2:
                    btn2.click(); page.wait_for_timeout(2000)
                    _pick_menu_item(page, "Extended")
                    page.wait_for_timeout(1200)
            label = _picker_label()
            has_base = base_label.split()[-1] in label  # "Pro" / "Flash" / "Lite"
            has_ext = ("Extended" in label) if want_ext else True
            if has_base and has_ext:
                break
            _log(f"model not confirmed (attempt {attempt+1}): label='{label[:60]}' — retrying")
        _log(f"model label: {_picker_label()[:80]}")

        # knowledge files / folders
        kfiles = list(args.knowledge_file or [])
        for d in (args.knowledge_folder or []):
            fd = Path(d)
            if not fd.is_dir():
                _log(f"SKIP not a dir: {d}"); continue
            zp = Path(tempfile.mktemp(suffix=".zip"))
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in fd.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(fd))
            _log(f"zipped {fd.name} -> {zp.name}")
            kfiles.append(str(zp))
        if kfiles:
            _log(f"attaching {len(kfiles)} knowledge file(s)")
            page.evaluate("""() => {
              const c=[...document.querySelectorAll('button,[aria-label]')];
              for(const x of c){ const a=(x.getAttribute('aria-label')||''); if(a==='Upload & tools'){ x.click(); return true; } }
              return false;
            }""")
            page.wait_for_timeout(1500)
            for fp in kfiles:
                if not Path(fp).exists():
                    _log(f"SKIP missing: {fp}"); continue
                page.evaluate("""() => {
                  const c=[...document.querySelectorAll('[role=menuitem],[role=option],button,[aria-label]')];
                  for(const x of c){ const a=(x.getAttribute('aria-label')||''); if(a.includes('Upload files')){ x.click(); return true; } }
                  return false;
                }""")
                page.wait_for_timeout(2000)
                fi = page.query_selector_all('input[type=file]')
                if fi:
                    fi[0].set_input_files(fp)
                    _log(f"uploaded: {Path(fp).name}")
                page.wait_for_timeout(2500)

        sb = page.query_selector('button[aria-label="Save Gem"]')
        if not sb:
            return _err("NO_SAVE", "save button not found")
        sb.click()
        _log("save clicked; waiting for redirect...")

        gid = None
        # Gemini save→redirect to /gem/<id> can take >40s on a fresh save
        for _ in range(90):
            page.wait_for_timeout(1000)
            m = re.search(r'/gem/([a-zA-Z0-9_-]+)', page.url or '')
            if m:
                g = m.group(1)
                if g not in _BUILTIN:
                    gid = g; break
        # Fallback: the manage list + the new Gem's own page are slow to populate.
        # Retry the URL check and a name lookup several times before giving up.
        if not gid:
            _log("redirect capture failed; falling back to name lookup")
            for attempt in range(8):
                try:
                    m = re.search(r'/gem/([a-zA-Z0-9_-]+)', page.url or '')
                    if m and m.group(1) not in _BUILTIN:
                        gid = m.group(1); break
                    page.goto("https://gemini.google.com/gems/view", wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3000)
                    m = re.search(r'/gem/([a-zA-Z0-9_-]+)', page.url or '')
                    if m and m.group(1) not in _BUILTIN:
                        gid = m.group(1); break
                    found = page.evaluate("""(nm) => {
                        const links = document.querySelectorAll('a[href*="/gem/"]');
                        for (const a of links) {
                            if ((a.innerText||'').includes(nm)) {
                                const href = a.href; const idx = href.indexOf('/gem/');
                                if (idx >= 0) { const after = href.slice(idx+5);
                                    const end = after.search(/[^a-zA-Z0-9_-]/);
                                    return end >= 0 ? after.slice(0,end) : after; }
                            }
                        }
                        return null;
                    }""", name)
                    if found:
                        gid = found; break
                except Exception as e:
                    _log(f"name lookup attempt {attempt+1} failed: {e}")
                page.wait_for_timeout(3000)
        if not gid:
            return _err("NO_GEM_ID", "could not capture Gem id after save")
        _log(f"created: {gid}")
        return _ok(action="create-gem", id=gid, name=name)
    finally:
        try:
            b.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass


# ───────────────────────────── REVIEW ─────────────────────────────

def _body_text(page):
    return page.evaluate("() => document.body.innerText || ''")


def _wait_reply(page, timeout=560):
    """Wait until the Gem's latest reply is stable. Self-terminating: returns as
    soon as a non-loading response is detected (or on the first stable snapshot),
    never burning the full timeout. Multiple extraction patterns cover Gem UI drift.
    """
    PATTERNS = [
        # English Gem UI real structure: "<Name>\nCustom Gem\n<Name> said\n<reply>"
        # stop at first blank line so trailing model labels ("Pro") don't leak in
        r'([^\n]+)\nCustom Gem\s*\n\1 said\s*\n(.*?)(?:\n\s*\n|$)',
        # Fallback: "Custom Gem\n<Name> said\n<reply>"
        r'Custom Gem\s*\n(.+?)said\s*\n(.*?)(?:\n\s*\n|$)',
        # Last-resort: "You said\n<prompt>\n\n<Name> said\n<reply>"
        r'(?:You said)\s*\n.*?\n\n(.+?)said\s*\n(.*?)(?:\n\s*\n|$)',
    ]
    # Phrases that mean "still working, answer not final yet"
    LOADING = re.compile(r'Generating|Thinking|is thinking|Finalizing|Edited just now|'
                          r'Refining|Answer now|Drafting|Summarizing', re.I)
    # Status strings that are NOT real answers (interstitial UI labels)
    STATUS = re.compile(r'^(Answer now|Refining|Generating|Thinking|Drafting|Summarizing|'
                        r'Finalizing|Edited just now)$', re.I)

    def _extract(txt):
        for pat in PATTERNS:
            m = re.findall(pat, txt, re.S)
            if m:
                cand = m[-1][1].strip()
                if STATUS.match(cand):
                    continue
                return cand
        return ""

    def _is_loading(txt):
        if LOADING.search(txt):
            return True
        return page.evaluate("""() => !!document.querySelector('button[aria-label*="Stop"], button[aria-label*="stop"], .loading-dots, [data-test-id=loading], .thinking-indicator')""")

    start = time.time(); prev = ""; stable = 0; polls = 0
    while time.time() - start < timeout:
        time.sleep(2.0)
        polls += 1
        txt = _body_text(page)
        loading = _is_loading(txt)
        reply = _extract(txt)
        if reply:
            if not loading:
                if reply == prev:
                    stable += 1
                else:
                    stable = 0
                if stable >= 2:                       # stable for ~4s → done
                    _log(f"reply stable after {polls} polls ({int(time.time()-start)}s)")
                    return reply
            prev = reply
        # early-out: no loading indicator AND we already have some reply text
        elif not loading and prev:
            _log(f"no new text, not loading -> returning after {int(time.time()-start)}s")
            return prev
    # timeout: return best-effort capture (or full body so caller can see state)
    txt = _body_text(page)
    reply = _extract(txt)
    _log(f"timeout after {int(time.time()-start)}s; reply_len={len(reply)}")
    return reply or txt


def _open_gem(b, gem_id, conv_url):
    page = new_page(b)
    url = conv_url or f"https://gemini.google.com/gem/{gem_id}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)
    try:
        page.wait_for_selector('div.ql-editor[aria-label="Enter a prompt for Gemini"]', timeout=6000)
    except Exception:
        page.evaluate("""() => {
          const c=[...document.querySelectorAll('button,a')];
          for(const x of c){ const t=(x.innerText||'').toLowerCase();
            if(t.includes('start chat')||t.includes('chat with')){ x.click(); return true; } }
          return false;
        }""")
        page.wait_for_timeout(4000)
        page.wait_for_selector('div.ql-editor[aria-label="Enter a prompt for Gemini"]', timeout=8000)
    return page


def _attach_and_send(page, prompt_text, files):
    if files:
        page.evaluate("""() => {
          const c=[...document.querySelectorAll('button,[aria-label]')];
          for(const x of c){ const a=(x.getAttribute('aria-label')||''); if(a==='Upload & tools'){ x.click(); return true; } }
          return false;
        }""")
        page.wait_for_timeout(1500)
        page.evaluate("""() => {
          const c=[...document.querySelectorAll('[role=menuitem],[role=option],button,[aria-label]')];
          for(const x of c){ const a=(x.getAttribute('aria-label')||''); if(a.includes('Upload files')){ x.click(); return true; } }
          return false;
        }""")
        page.wait_for_timeout(2000)
        fi = page.query_selector_all('input[type=file]')
        if fi and files:
            fi[0].set_input_files(files)
            _log(f"attached: {files}")
        page.wait_for_timeout(2000)

    box = _find_input(page)
    if not box:
        return _err("NO_INPUT", "chat input not found")
    box.click(); page.wait_for_timeout(300)
    page.keyboard.insert_text(prompt_text)
    page.wait_for_timeout(700)
    sent = page.evaluate("""() => {
      const c=[...document.querySelectorAll('button[aria-label="Send message"]')];
      if(c.length){ c[0].click(); return true; }
      return false;
    }""")
    if not sent:
        page.keyboard.press("Enter")
    _log("submitted; waiting for reply...")


def _find_input(page, timeout=15000):
    """Find the Gemini chat/compose input, which has different markup in normal
    vs image-gen mode. Returns the element handle or None."""
    sel = ('div.ql-editor[aria-label="Enter a prompt for Gemini"], '
           'div[contenteditable="true"][role="textbox"], '
           'div[role="textbox"][contenteditable="true"]')
    try:
        return page.wait_for_selector(sel, timeout=timeout)
    except Exception:
        # last resort: any visible contenteditable
        return page.evaluate("""() => {
          const els = document.querySelectorAll('[contenteditable="true"]');
          for (const e of els) { if (e.offsetParent && e.innerText !== undefined) return e; }
          return null;
        }""")


def cmd_review(args):
    prompt = Path(args.prompt).read_text(encoding="utf-8")
    conv_path = Path(args.conv)
    conv_url = conv_path.read_text().strip() if conv_path.exists() else None
    mode = "resume" if conv_url else "new"
    _log(f"mode={mode} gem={args.gem} conv={conv_url}")
    out_path = Path(args.out) if args.out else (OUTPUT_DIR / f"gem-review-{int(time.time())}.md")

    p, b = connect(args.cdp)
    try:
        page = _open_gem(b, args.gem, conv_url)
        _attach_and_send(page, prompt, args.files)
        t0 = time.time()
        txt = _wait_reply(page, args.timeout)
        elapsed = time.time() - t0
        out_path.write_text(txt, encoding="utf-8")
        conv_path.write_text(page.url)
        _log(f"{elapsed:.1f}s {len(txt)}c -> {out_path}")
        if not txt.strip():
            return _err("EMPTY", "Gem returned no reply (timeout?)")
        return _ok(action="review", f=str(out_path), s=len(txt),
                   t=round(elapsed, 1), conv=str(conv_path), gem=args.gem,
                   url=page.url)
    finally:
        try:
            b.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass


# ───────────────────────────── UPLOAD ─────────────────────────────

def cmd_upload(args):
    fp = Path(args.file)
    if not fp.exists():
        return _err("FILE_NOT_FOUND", str(args.file))
    prompt = args.prompt or ""
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt.strip():
        return _err("NO_PROMPT", "provide --prompt or --prompt-file")
    p, b = connect(args.cdp)
    try:
        page = _open_gem(b, args.gem, None)
        out_path = Path(args.out) if args.out else (OUTPUT_DIR / f"gem-upload-{int(time.time())}.md")
        _attach_and_send(page, prompt, [str(fp)])
        t0 = time.time()
        txt = _wait_reply(page, args.timeout)
        elapsed = time.time() - t0
        out_path.write_text(txt, encoding="utf-8")
        _log(f"{elapsed:.1f}s {len(txt)}c -> {out_path}")
        if not txt.strip():
            return _err("EMPTY", "Gem returned no reply")
        return _ok(action="upload", f=str(out_path), s=len(txt), t=round(elapsed, 1), gem=args.gem)
    finally:
        try:
            b.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass


# ───────────────────────────── CHAT ─────────────────────────────

def _select_model_english(page, model, thinking):
    """Click the model picker (English Gemini UI) and pick base model + thinking tier."""
    if not (model or thinking):
        return
    btn = page.query_selector('button[aria-label^="Open mode picker"]')
    if not btn:
        _log("model picker not found, skipping model selection")
        return
    btn.click(); page.wait_for_timeout(2500)
    if model:
        model_map = {"pro": "3.1 Pro", "flash": "3.5 Flash", "flash-lite": "Flash-Lite"}
        _pick_menu_item(page, model_map.get(model.lower(), model))
        page.wait_for_timeout(1200)
    if thinking and thinking.lower() in ("extended", "extend"):
        btn2 = page.query_selector('button[aria-label^="Open mode picker"]')
        if btn2:
            btn2.click(); page.wait_for_timeout(2500)
            _pick_menu_item(page, "Extended")
            page.wait_for_timeout(1200)


def cmd_chat(args):
    prompt = args.prompt or ""
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if args.brief:
        prompt = "Be concise. " + prompt
    conv_path = Path(args.conv) if args.conv else None
    conv_url = conv_path.read_text().strip() if (conv_path and conv_path.exists()) else None
    mode = "resume" if conv_url else "new"
    _log(f"chat mode={mode} gem={args.gem} model={args.model} thinking={args.thinking}")
    out_path = Path(args.out) if args.out else (OUTPUT_DIR / f"gem-chat-{int(time.time())}.md")
    p, b = connect(args.cdp)
    try:
        page = _open_gem(b, args.gem, conv_url)
        if args.model or args.thinking:
            _select_model_english(page, args.model, args.thinking)
        _attach_and_send(page, prompt, [])
        t0 = time.time()
        txt = _wait_reply(page, args.timeout)
        elapsed = time.time() - t0
        out_path.write_text(txt, encoding="utf-8")
        if conv_path:
            conv_path.write_text(page.url)
        _log(f"{elapsed:.1f}s {len(txt)}c -> {out_path}")
        if not txt.strip():
            return _err("EMPTY", "Gem returned no reply")
        d = _ok(action="chat", f=str(out_path), s=len(txt), t=round(elapsed, 1), gem=args.gem)
        if conv_path:
            d["conv"] = str(conv_path)
        return d
    finally:
        try:
            b.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass


# ───────────────────────────── DELETE ─────────────────────────────

def cmd_delete(args):
    p, b = connect(args.cdp)
    try:
        page = new_page(b)
        nav_ok = False
        for _ in range(3):
            try:
                page.goto(f"https://gemini.google.com/gem/{args.gem}", wait_until="domcontentloaded", timeout=30000)
                nav_ok = True
                break
            except Exception as e:
                _log(f"delete nav retry: {e}")
                page.wait_for_timeout(2000)
        if not nav_ok:
            return _err("NAV_FAIL", "could not open Gem page for delete")
        page.wait_for_timeout(5000)
        clicked = page.evaluate("""(gid) => {
            const btns = document.querySelectorAll('button, [role="button"]');
            for (const b of btns) {
                const ar = (b.getAttribute('aria-label')||'').toLowerCase();
                const tx = (b.innerText||'').toLowerCase();
                if ((ar.includes('gem') || ar.includes('options') || ar.includes('more')) && b.offsetParent) {
                    b.click(); return 'clicked:'+ar.slice(0,40);
                }
            }
            return 'not-found';
        }""", args.gem)
        _log(f"menu: {clicked}")
        page.wait_for_timeout(2000)
        deleted = page.evaluate("""() => {
            const all = document.querySelectorAll('*');
            for (const el of all) {
                const tx = (el.innerText||'').trim();
                if ((tx === 'Delete' || tx === 'Delete Gem' || tx === 'Delete gem') && el.offsetParent && tx.length < 20) {
                    el.click(); return 'clicked:'+tx;
                }
            }
            const items = document.querySelectorAll('[role="menuitem"]');
            for (const item of items) {
                if ((item.innerText||'').trim() === 'Delete') { item.click(); return 'clicked:menuitem'; }
            }
            return 'not-found';
        }""")
        _log(f"delete item: {deleted}")
        page.wait_for_timeout(2000)
        confirmed = page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const tx = (b.innerText||'').trim();
                if ((tx === 'Delete' || tx === 'Delete Gem') && b.offsetParent) { b.click(); return 'confirmed:'+tx; }
            }
            return 'no-confirm';
        }""")
        _log(f"confirm: {confirmed}")
        page.wait_for_timeout(3000)
        return _ok(action="delete-gem", id=args.gem)
    finally:
        try:
            b.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass


# ───────────────────────────── IMG ─────────────────────────────

def cmd_img(args):
    p, b = connect(args.cdp)
    try:
        page = _open_gem(b, args.gem, None)
        out_path = Path(args.out) if args.out else (OUTPUT_DIR / f"gem-img-{int(time.time())}.md")
        # Open tools -> Create image
        tools = page.query_selector('[aria-label="Upload & tools"]')
        if tools:
            tools.click(); page.wait_for_timeout(2000)
        clicked = page.evaluate("""() => {
            const items = document.querySelectorAll('toolbox-drawer-item, [role="menuitem"], [aria-label]');
            for (const item of items) {
                const tx = (item.getAttribute('aria-label')||item.innerText||'').trim();
                if (tx.startsWith('Create image') || tx.startsWith('製作圖像')) { item.click(); return 'ok'; }
            }
            return 'not-found';
        }""")
        _log(f"img btn: {clicked}")
        page.wait_for_timeout(3000)

        box = _find_input(page)
        if not box:
            return _err("NO_INPUT", "image prompt input not found")
        box.click(); page.wait_for_timeout(300)
        page.keyboard.insert_text(args.prompt)
        page.wait_for_timeout(700)
        sent = page.evaluate("""() => {
          const c=[...document.querySelectorAll('button[aria-label="Send message"]')];
          if(c.length){ c[0].click(); return true; } return false;
        }""")
        if not sent:
            page.keyboard.press("Enter")
        _log("generating...")

        resp, elapsed = "", 0.0
        t0 = time.time()
        for _ in range(40):
            page.wait_for_timeout(3000)
            t = page.evaluate("""() => {
                const msgs = document.querySelectorAll('.response-content, message-content, model-response');
                return msgs.length ? msgs[msgs.length-1].innerText : '';
            }""")
            if t: resp = t
            has_img = page.evaluate("""() => document.querySelectorAll('.response-content img[src], message-content img[src]').length""")
            if has_img > 0:
                page.wait_for_timeout(2000)
                break
        elapsed = time.time() - t0

        images = []
        try:
            img_els = page.query_selector_all('.response-content img, message-content img')
            for idx, img_el in enumerate(img_els):
                fname = OUTPUT_DIR / f"gem-img-{int(time.time())}-{idx}.png"
                try:
                    img_el.screenshot(path=str(fname))
                    images.append(str(fname))
                    _log(f"image: {fname.name}")
                except Exception as e:
                    _log(f"img screenshot err: {e}")
        except Exception as e:
            _log(f"img err: {e}")

        if resp.strip():
            out_path.write_text(resp, encoding="utf-8")
        if not resp.strip() and not images:
            return _err("EMPTY", "No image generated")
        d = _ok(action="img", t=round(elapsed, 1))
        if resp.strip():
            d["s"] = len(resp); d["f"] = str(out_path)
        if images:
            d["images"] = images
        return d
    finally:
        try:
            b.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass


# ───────────────────────────── MAIN ─────────────────────────────

def main():
    global JSON_OUT, QUIET
    # shared flags valid BEFORE or AFTER the subcommand (matches old --cdp-at-end usage)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--cdp", default=DEFAULT_CDP, help="CDP endpoint (default %(default)s)")
    common.add_argument("--json", action="store_true", help="emit compact JSON result to STDOUT")
    common.add_argument("-q", "--quiet", action="store_true", help="suppress STDERR progress logs")
    ap = argparse.ArgumentParser(prog="gem.py", description="Gemini Gem driver via CDP 9223",
                                 parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", parents=[common], help="create a Gem (Pro+Extended default)")
    c.add_argument("--name", required=True)
    c.add_argument("--instructions", required=True)
    c.add_argument("--model", default="pro", choices=["pro", "flash", "flash-lite"])
    c.add_argument("--thinking", default="extended", choices=["extended", "none"])
    c.add_argument("--knowledge-file", action="append", default=[])
    c.add_argument("--knowledge-folder", action="append", default=[])

    c = sub.add_parser("review", parents=[common], help="continuous multi-round review (resume if --conv exists)")
    c.add_argument("--gem", required=True)
    c.add_argument("--prompt", required=True)
    c.add_argument("--out")
    c.add_argument("--conv", required=True)
    c.add_argument("--timeout", type=int, default=560)
    c.add_argument("files", nargs="*")

    c = sub.add_parser("chat", parents=[common], help="plain chat with a Gem (continuous with --conv)")
    c.add_argument("--gem", required=True)
    c.add_argument("--prompt", help="prompt text (or use --prompt-file)")
    c.add_argument("--prompt-file", help="read prompt from file")
    c.add_argument("--model", default=None, choices=["pro", "flash", "flash-lite"])
    c.add_argument("--thinking", default=None, choices=["extended", "none"])
    c.add_argument("--brief", action="store_true", help="prefix with 'Be concise.'")
    c.add_argument("-o", "--out")
    c.add_argument("--conv")
    c.add_argument("--timeout", type=int, default=560)

    c = sub.add_parser("upload", parents=[common], help="upload a file then ask the Gem")
    c.add_argument("--gem", required=True)
    c.add_argument("--file", required=True)
    c.add_argument("--prompt", help="prompt text (or use --prompt-file)")
    c.add_argument("--prompt-file", help="read prompt from file")
    c.add_argument("-o", "--out")
    c.add_argument("--timeout", type=int, default=560)

    c = sub.add_parser("delete", parents=[common], help="delete a Gem")
    c.add_argument("--gem", required=True)

    c = sub.add_parser("img", parents=[common], help="generate an image in the Gem")
    c.add_argument("--gem", required=True)
    c.add_argument("--prompt", required=True)
    c.add_argument("-o", "--out")

    a = ap.parse_args()
    JSON_OUT = a.json
    QUIET = a.quiet

    try:
        if a.cmd == "create":
            res = cmd_create(a)
        elif a.cmd == "review":
            res = cmd_review(a)
        elif a.cmd == "chat":
            res = cmd_chat(a)
        elif a.cmd == "upload":
            res = cmd_upload(a)
        elif a.cmd == "delete":
            res = cmd_delete(a)
        elif a.cmd == "img":
            res = cmd_img(a)
        else:
            res = _err("USAGE", "unknown command")
    except Exception as e:
        res = _err(type(e).__name__, str(e)[:300])

    _emit(res)
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()

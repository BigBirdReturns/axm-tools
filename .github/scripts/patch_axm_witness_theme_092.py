from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path.cwd()
APP = ROOT / "axm-witness" / "index.html"
RECEIPT = ROOT / ".github" / "receipts" / "axm-witness-theme-0.9.2.json"
OLD_WORKFLOW = ROOT / ".github" / "workflows" / "axm-witness-0.9.1.yml"
BASE_BYTES = 497_004
BASE_SHA256 = "d5d1f33f6cb2981497489f24468939f752cc5de39e66ebcf4ff11838ad1843f7"
RELEASE = "axm-witness-department-ledger/0.9.2"
THEME_KEY = "axm-witness-theme"

THEME_BOOT = r'''<script id="axm-theme-boot">
(() => {
  let theme = "dark";
  try {
    const saved = localStorage.getItem("axm-witness-theme");
    if (saved === "light" || saved === "dark") theme = saved;
  } catch (error) {
    console.warn("Theme preference could not be read", error);
  }
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
})();
</script>'''

THEME_BUTTON = r'''<button class="icon-button theme-toggle" type="button" id="themeToggle" aria-pressed="true" aria-label="Switch to light theme" title="Switch to light theme">
        <svg class="theme-icon theme-icon-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41"></path></svg>
        <svg class="theme-icon theme-icon-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15.2A8.4 8.4 0 0 1 8.8 4 8.5 8.5 0 1 0 20 15.2z"></path></svg>
        <span class="sr-only">Toggle light and dark theme</span>
      </button>'''

THEME_STYLE = r'''<style id="axm-v092-theme">
:root[data-theme="dark"] {
  --r8-bg: #0f1117 !important;
  --r8-canvas: #14171f !important;
  --r8-surface: #1b1e27 !important;
  --r8-surface-2: #181b23 !important;
  --r8-surface-3: #222631 !important;
  --r8-text: #f4f4f6 !important;
  --r8-text-2: #d0d3db !important;
  --r8-muted: #969dac !important;
  --r8-line: #313747 !important;
  --r8-line-strong: #4a5267 !important;
  --r8-orange: #f36b2f !important;
  --r8-orange-hover: #ff7d46 !important;
  --r8-blue: #6ea0ff !important;
  --r8-green: #65d39a !important;
  --r8-yellow: #e5b858 !important;
  --r8-red: #ef7d82 !important;
  --r8-shadow: 0 8px 30px rgba(0,0,0,.28) !important;
  --line-soft: #272c38 !important;
  --gold-bright: #ff936d !important;
  --violet: #a88bff !important;
  --rp-violet: #a88bff !important;
  --shadow: 0 18px 60px rgba(0,0,0,.38) !important;
}
html[data-theme="dark"] { color-scheme: dark !important; background: var(--r8-bg) !important; }
html[data-theme="light"] { color-scheme: light !important; background: var(--r8-bg) !important; }
body.replit-v08,
body.replit-v08 .topbar,
body.replit-v08 .global-rail,
body.replit-v08 .workspace-frame,
body.replit-v08 .workspace-canvas,
body.replit-v08 .context-guide,
body.replit-v08 .modal,
body.replit-v08 .palette-dialog { transition: background-color .16s ease, border-color .16s ease, color .16s ease; }
#themeToggle .theme-icon { display: none !important; }
html[data-theme="dark"] #themeToggle .theme-icon-sun { display: block !important; }
html[data-theme="light"] #themeToggle .theme-icon-moon { display: block !important; }
html[data-theme="dark"] body.replit-v08 * { scrollbar-color: #4a5267 transparent; }
html[data-theme="dark"] body.replit-v08 ::selection { background: #69331f; color: #fff; }
html[data-theme="dark"] body.replit-v08 .topbar { background: rgba(18,21,28,.97) !important; }
html[data-theme="dark"] body.replit-v08 .workbench-mark i { border-color: #17191f !important; }
html[data-theme="dark"] body.replit-v08 .global-rail { background: #11141b !important; }
html[data-theme="dark"] body.replit-v08 .global-nav button[aria-current="page"],
html[data-theme="dark"] body.replit-v08 .review-tabs button[aria-current="page"] { background: #252a36 !important; }
html[data-theme="dark"] body.replit-v08 .review-tabs .badge { background: #2a2f3b !important; }
html[data-theme="dark"] body.replit-v08 .sidebar-command { background: #191d26 !important; }
html[data-theme="dark"] body.replit-v08 .sidebar-item:hover { background: #1d212b !important; }
html[data-theme="dark"] body.replit-v08 .sidebar-item.active { background: #252a36 !important; }
html[data-theme="dark"] body.replit-v08 .sidebar-review-card { background: #181c25 !important; }
html[data-theme="dark"] body.replit-v08 .review-context-bar { background: #151821 !important; }
html[data-theme="dark"] body.replit-v08 th,
html[data-theme="dark"] body.replit-v08 .receipt-family-summary div,
html[data-theme="dark"] body.replit-v08 .flow-step,
html[data-theme="dark"] body.replit-v08 .start-answer-stack article { background: var(--r8-surface-2) !important; }
html[data-theme="dark"] body.replit-v08 .modal::backdrop,
html[data-theme="dark"] body.replit-v08 .palette-backdrop { background: rgba(0,0,0,.66) !important; }
html[data-theme="dark"] body.replit-v08 .toast { background: #f4f4f6 !important; color: #17191f !important; }
html[data-theme="dark"] body.replit-v08 input,
html[data-theme="dark"] body.replit-v08 select,
html[data-theme="dark"] body.replit-v08 textarea { color-scheme: dark; }
@media (max-width: 700px) {
  body.replit-v08 .topbar-actions .theme-toggle { display: grid !important; width: 40px !important; min-width: 40px !important; height: 40px !important; min-height: 40px !important; }
}
@media (prefers-reduced-motion: reduce) {
  body.replit-v08,
  body.replit-v08 .topbar,
  body.replit-v08 .global-rail,
  body.replit-v08 .workspace-frame,
  body.replit-v08 .workspace-canvas,
  body.replit-v08 .context-guide,
  body.replit-v08 .modal,
  body.replit-v08 .palette-dialog { transition: none !important; }
}
</style>'''

THEME_RUNTIME = r'''<script id="axm-theme-toggle-runtime">
(() => {
  const key = "axm-witness-theme";
  const root = document.documentElement;
  const button = document.getElementById("themeToggle");
  if (!button) return;

  const normalize = value => value === "light" ? "light" : "dark";
  const apply = (value, persist = false) => {
    const theme = normalize(value);
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    const dark = theme === "dark";
    button.setAttribute("aria-pressed", String(dark));
    button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    button.title = dark ? "Switch to light theme" : "Switch to dark theme";
    if (persist) {
      try { localStorage.setItem(key, theme); }
      catch (error) { console.warn("Theme preference could not be saved", error); }
    }
    window.dispatchEvent(new CustomEvent("axm-witness-theme-change", { detail: { theme } }));
    return theme;
  };

  let current = normalize(root.dataset.theme);
  apply(current);
  button.addEventListener("click", () => {
    current = apply(current === "dark" ? "light" : "dark", true);
  });
  window.addEventListener("storage", event => {
    if (event.key === key && (event.newValue === "light" || event.newValue === "dark")) {
      current = apply(event.newValue);
    }
  });
})();
</script>'''


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_app() -> tuple[int, str]:
    raw = APP.read_bytes()
    text = raw.decode("utf-8")
    already = 'id="axm-theme-toggle-runtime"' in text
    if not already:
        if len(raw) != BASE_BYTES or sha256(raw) != BASE_SHA256:
            raise SystemExit(f"unexpected base application: bytes={len(raw)} sha256={sha256(raw)}")

        text = replace_once(text, '<meta name="color-scheme" content="light">', '<meta name="color-scheme" content="dark light">', "color-scheme meta")
        csp_pattern = r'(<meta http-equiv="Content-Security-Policy"[^>]*>)'
        text, csp_count = re.subn(csp_pattern, lambda match: match.group(1) + "\n" + THEME_BOOT, text, count=1)
        if csp_count != 1:
            raise SystemExit(f"theme boot insertion: expected one CSP meta element, found {csp_count}")
        text = replace_once(text, '<meta name="axm-release" content="axm-witness-department-ledger/0.9.1">', '<meta name="axm-release" content="axm-witness-department-ledger/0.9.2">', "release meta")
        text = replace_once(text, '<meta name="axm-native-acceptance" content="qualified-system-chromium-file-static-host-native-indexeddb-webcrypto-crash-recovery">', '<meta name="axm-native-acceptance" content="qualified-0.9.1-core-plus-0.9.2-persistent-theme-toggle">', "acceptance meta")
        text = replace_once(text, '/* 0.9.1 retains the light conversation-and-preview workbench. The custody engine and\n   application objects below remain the same. */', '/* 0.9.2 adds a persistent light/dark theme while preserving the conversation-and-preview workbench.\n   The custody engine, IndexedDB name, and application objects below remain the same. */', "theme style comment")
        text = replace_once(text, '  const RELEASE = "axm-witness-department-ledger/0.9.1";', '  const RELEASE = "axm-witness-department-ledger/0.9.2";', "release constant")
        text = replace_once(text, 'AXM Witness department ledger 0.9.1', 'AXM Witness department ledger 0.9.2', "footer release")
        text = replace_once(text, '"axm-witness-department-ledger-v0.9.1-offline.html"', '"axm-witness-department-ledger-v0.9.2-offline.html"', "offline filename")
        text = replace_once(text, '"axm-witness-public-corpus-ledger-v0.9.1.json"', '"axm-witness-public-corpus-ledger-v0.9.2.json"', "corpus filename")
        contrast_anchor = '      <button class="icon-button" type="button" id="contrastToggle" aria-pressed="false" title="Toggle high contrast">'
        text = replace_once(text, contrast_anchor, '      ' + THEME_BUTTON + '\n' + contrast_anchor, "theme button")
        head_end = text.rfind("</head>")
        if head_end < 0:
            raise SystemExit("head close missing")
        text = text[:head_end] + THEME_STYLE + "\n" + text[head_end:]
        body_end = text.rfind("</body>")
        if body_end < 0:
            raise SystemExit("body close missing")
        text = text[:body_end] + THEME_RUNTIME + "\n" + text[body_end:]
        APP.write_text(text, encoding="utf-8", newline="\n")

    final = APP.read_bytes()
    rendered = final.decode("utf-8")
    required = [
        'id="axm-theme-boot"',
        'id="axm-v092-theme"',
        'id="themeToggle"',
        'id="axm-theme-toggle-runtime"',
        'content="axm-witness-department-ledger/0.9.2"',
        'const RELEASE = "axm-witness-department-ledger/0.9.2";',
        'const DB_NAME = "axm-witness-department-ledger-v0-9-1";',
    ]
    for marker in required:
        if rendered.count(marker) != 1:
            raise SystemExit(f"required marker count failed: {marker!r} -> {rendered.count(marker)}")
    return len(final), sha256(final)


def patch_docs() -> None:
    for relative in ("README.md", "index.html", "CONTINUITY.md"):
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        if "AXM Witness Department Ledger 0.9.1" in text:
            text = text.replace("AXM Witness Department Ledger 0.9.1", "AXM Witness Department Ledger 0.9.2")
        if relative == "index.html" and "persistent light/dark theme toggle" not in text:
            anchor = "The native release qualification passes 30 of 30 controls; upstream delivery completeness remains outside the ledger."
            if anchor not in text:
                raise SystemExit("root directory AXM Witness description anchor missing")
            text = text.replace(anchor, anchor + " The display adds a persistent light/dark theme toggle, with dark as the first-run default.", 1)
        path.write_text(text, encoding="utf-8", newline="\n")


def write_receipt(app_bytes: int, app_sha: str) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "axm-witness/theme-patch-qualification@1",
        "release": RELEASE,
        "base_release": "axm-witness-department-ledger/0.9.1",
        "base_application": {"bytes": BASE_BYTES, "sha256": BASE_SHA256},
        "patched_application": {"bytes": app_bytes, "sha256": app_sha},
        "theme": {
            "default": "dark",
            "options": ["dark", "light"],
            "preference_store": "localStorage",
            "preference_key": THEME_KEY,
            "mobile_interaction_floor_px": 40,
            "high_contrast_control_preserved": True,
        },
        "storage_compatibility": {
            "indexeddb_name": "axm-witness-department-ledger-v0-9-1",
            "changed": False,
            "reason": "Theme patch must retain existing department-ledger origin storage.",
        },
        "qualification_boundary": "The 0.9.1 native 30/30 campaign remains evidence for the unchanged custody and workflow engine. The 0.9.2 workflow separately qualifies the additive theme boot, toggle, persistence, accessibility, mobile visibility, inline-script parsing, and live static route.",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    app_bytes, app_sha = patch_app()
    patch_docs()
    write_receipt(app_bytes, app_sha)
    if OLD_WORKFLOW.exists():
        OLD_WORKFLOW.unlink()
    print(json.dumps({"release": RELEASE, "bytes": app_bytes, "sha256": app_sha}, indent=2))


if __name__ == "__main__":
    main()

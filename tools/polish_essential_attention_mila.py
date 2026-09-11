from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EA = ROOT / "essential-attention"
INDEX = EA / "index.html"
STATIC = EA / "tests" / "public_contract_test.py"
BROWSER = EA / "tests" / "browser_test.py"
README = EA / "README.md"


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact anchor, found {count}")
    return text.replace(old, new, 1)


def patch_index() -> None:
    html = INDEX.read_text(encoding="utf-8")
    if "MILA_RECEIVER_POLISH_V1_2_1" in html:
        raise SystemExit("receiver polish already present")

    replacements = {
        "Mila executive projection · draft only": "Essential Attention · Mila executive review · local draft only",
        "Five decisions. No reconstructed universe.": "Five decisions. Everything needed to decide them.",
        "This view contains only the questions that require Manzanita executive authority, the obligations whose status matters now, and the evidence already ready for disposition. It contains zero participant records and zero field cases. Every action remains a local draft until an accepted external authority receipt changes official state.": "These are the five choices that require Manzanita’s decision. Everything else stays in its existing state. The page contains no participant records or field cases, and every selection remains a local draft until Manzanita records it through its own accepted process.",
        "No accepted return receipt exists. Silence remains unresolved and supplies no evidence of rejection, hostility, consent, availability, or duty.": "No response has been recorded. Silence stays unresolved; it does not mean rejection, hostility, consent, availability, or obligation.",
    }
    for old, new in replacements.items():
        html = once(html, old, new, f"copy replacement {old[:28]}")

    html = once(
        html,
        '<div class="detail"><b>Safe progress without external decision</b>${esc(d.safe_next)}</div>',
        '<div class="detail"><b>${isMilaProjection()?\'What can proceed now\':\'Safe progress without external decision\'}</b>${esc(d.safe_next)}</div>',
        "receiver decision label",
    )

    css = r'''

/* MILA_RECEIVER_POLISH_V1_2_1 */
body.mila-projection{background:var(--paper-alt)}
body.mila-projection .app{display:block;min-height:100vh;background:var(--paper-alt)}
body.mila-projection .rail,
body.mila-projection .topbar,
body.mila-projection footer,
body.mila-projection .decision-summary,
body.mila-projection .executive-generic{display:none!important}
body.mila-projection .main{min-width:0;width:100%}
body.mila-projection .content{width:min(1240px,100%);max-width:none;margin:0 auto;padding:clamp(26px,4vw,58px) clamp(14px,4vw,54px) 72px}
body.mila-projection #view-executive{min-width:0;min-height:0;padding:clamp(24px,4vw,46px);border:1px solid var(--rule);background:var(--paper);box-shadow:0 24px 70px rgba(24,20,12,.13)}
body.mila-projection #view-executive::before,
body.mila-projection #view-executive::after{display:none}
body.mila-projection .mila-return-intro{margin:0 0 24px;padding:0 0 30px;border:0;border-bottom:4px solid var(--ink);background:transparent;box-shadow:none}
body.mila-projection .mila-return-intro h2{max-width:980px;margin:.35rem 0 .8rem;font-size:clamp(3rem,6vw,5.8rem);line-height:.91;letter-spacing:-.04em;text-wrap:balance;overflow-wrap:normal;word-break:normal}
body.mila-projection .mila-return-intro>p{max-width:900px;font-size:1rem;line-height:1.6}
body.mila-projection .mila-communication{max-width:900px;margin-top:20px;padding:14px 16px;font-size:.86rem;line-height:1.55}
body.mila-projection .mila-return-counts{margin-top:20px}
body.mila-projection .mila-return-queues{margin:24px 0 28px}
body.mila-projection .mila-queue-grid{gap:12px}
body.mila-projection .mila-queue header{min-height:68px}
body.mila-projection .mila-queue li{min-height:0}
body.mila-projection .decision-grid{gap:14px}
body.mila-projection .decision-card{min-width:0;box-shadow:none}
body.mila-projection .decision-card h3,
body.mila-projection .decision-card p,
body.mila-projection .decision-card .detail,
body.mila-projection .mila-queue h3,
body.mila-projection .mila-queue strong,
body.mila-projection .mila-queue p,
body.mila-projection .mila-queue span,
body.mila-projection .mila-draft-row strong,
body.mila-projection .mila-draft-row p{max-width:100%;overflow-wrap:anywhere}
body.mila-projection .mila-drafts{margin-top:28px;padding:clamp(20px,3vw,30px)}
body.mila-projection #exportMilaPacketButton{min-width:220px}
@media(max-width:780px){
  body.mila-projection .content{padding:12px 10px 40px}
  body.mila-projection #view-executive{padding:24px 18px}
  body.mila-projection .mila-return-intro{padding-bottom:24px}
  body.mila-projection .mila-return-intro h2{font-size:clamp(2.35rem,11vw,4.2rem)}
  body.mila-projection .mila-return-intro>p{font-size:.94rem;line-height:1.52}
  body.mila-projection .mila-communication{font-size:.8rem}
  body.mila-projection .decision-card h3{font-size:1.25rem}
  body.mila-projection #exportMilaPacketButton{min-width:0;width:100%}
}
@media(max-width:430px){
  body.mila-projection .content{padding-inline:8px}
  body.mila-projection #view-executive{padding:20px 14px}
  body.mila-projection .mila-return-intro h2{font-size:clamp(1.25rem,10vw,2rem);line-height:.96;letter-spacing:-.025em;text-wrap:balance}
  body.mila-projection .mila-return-intro>p{font-size:.86rem;line-height:1.45}
  body.mila-projection .mila-communication{padding:12px;font-size:.76rem}
  body.mila-projection .mila-return-counts article{padding:12px}
  body.mila-projection .mila-queue header,
  body.mila-projection .mila-queue li{padding:13px 12px}
  body.mila-projection .mila-queue header h3{font-size:.92rem}
  body.mila-projection .mila-queue li strong{font-size:.82rem}
  body.mila-projection .mila-queue li p{font-size:.74rem}
  body.mila-projection .decision-card h3{font-size:clamp(.95rem,5vw,1.18rem)}
  body.mila-projection .mila-drafts{padding-inline:11px}
}
'''
    html = once(html, "\n</style>", css + "\n</style>", "polish CSS insertion")
    INDEX.write_text(html, encoding="utf-8")


def patch_static() -> None:
    text = STATIC.read_text(encoding="utf-8")
    text = once(
        text,
        '"mila_body_projection": "mila-projection" in source and "Five decisions. No reconstructed universe." in source,',
        '"mila_body_projection": "mila-projection" in source and "Five decisions. Everything needed to decide them." in source,',
        "static headline gate",
    )
    anchor = '    "mila_readme": "## Mila return projection (v1.2.1)" in readme,'
    text = once(
        text,
        anchor,
        '    "mila_receiver_polish": "MILA_RECEIVER_POLISH_V1_2_1" in source and "body.mila-projection .rail" in source and "body.mila-projection footer" in source,\n' + anchor,
        "static polish gate",
    )
    STATIC.write_text(text, encoding="utf-8")


def patch_browser() -> None:
    text = BROWSER.read_text(encoding="utf-8")

    anchor = '    check("Mila projection suppresses unrelated navigation", mila_page.locator(\'.seat-nav button:not([data-view="executive"])\').evaluate_all("els => els.every(el => getComputedStyle(el).display === \'none\')"))'
    addition = anchor + '\n    check("Mila projection removes the operating shell", mila_page.locator(".rail").evaluate("el => getComputedStyle(el).display === \'none\'") and mila_page.locator(".topbar").evaluate("el => getComputedStyle(el).display === \'none\'") and mila_page.locator("footer").evaluate("el => getComputedStyle(el).display === \'none\'"))\n    check("Mila projection removes duplicate decision totals", mila_page.locator("#decisionSummary").evaluate("el => getComputedStyle(el).display === \'none\'"))'
    text = once(text, anchor, addition, "browser shell gates")

    desktop_anchor = '    mila_page.screenshot(path=str(OUT / "mila-review-desktop.png"), full_page=True)'
    mobile_block = desktop_anchor + '''

    mila_page.set_viewport_size({"width": 390, "height": 844})
    mila_page.wait_for_timeout(100)
    mila_mobile = mila_page.evaluate("""() => ({
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
      titleScroll: document.querySelector('#milaReturnTitle').scrollWidth,
      titleClient: document.querySelector('#milaReturnTitle').clientWidth
    })""")
    check("Mila mobile surface has no horizontal overflow", mila_mobile["documentWidth"] <= mila_mobile["viewportWidth"], json.dumps(mila_mobile))
    check("Mila mobile headline is fully visible", mila_mobile["titleScroll"] <= mila_mobile["titleClient"] + 1, json.dumps(mila_mobile))
    mila_page.screenshot(path=str(OUT / "mila-review-mobile.png"), full_page=True)
    mila_page.set_viewport_size({"width": 1440, "height": 1000})
    mila_page.wait_for_timeout(100)'''
    text = once(text, desktop_anchor, mobile_block, "normal mobile visual gate")

    old_geometry = '''    mila_geometry = mila_page.evaluate("""() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      exportWidth: document.querySelector('#exportMilaPacketButton').getBoundingClientRect().width,
      exportHeight: document.querySelector('#exportMilaPacketButton').getBoundingClientRect().height
    })""")
    check("Mila projection remains bounded at 320px and 200 percent text", mila_geometry["scrollWidth"] <= mila_geometry["clientWidth"], json.dumps(mila_geometry))
    check("Mila export remains operable at narrow text zoom", mila_geometry["exportWidth"] > 0 and mila_geometry["exportHeight"] >= 44, json.dumps(mila_geometry))'''
    new_geometry = '''    mila_geometry = mila_page.evaluate("""() => {
      const title = document.querySelector('#milaReturnTitle');
      const selectors = '#milaReturnTitle, .mila-return-intro p, .mila-communication, .mila-queue h3, .mila-queue li strong, .mila-queue li p, .decision-card h3, .decision-card p, .decision-card .detail, .mila-draft-row strong, .mila-draft-row p, #exportMilaPacketButton';
      const clipped = [...document.querySelectorAll(selectors)].flatMap(element => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        if (style.display === 'none' || rect.width <= 0 || rect.height <= 0 || element.scrollWidth <= element.clientWidth + 1) return [];
        return [{tag: element.tagName, className: element.className, text: (element.textContent || '').trim().slice(0, 80), scrollWidth: element.scrollWidth, clientWidth: element.clientWidth}];
      });
      return {
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        titleScroll: title.scrollWidth,
        titleClient: title.clientWidth,
        exportWidth: document.querySelector('#exportMilaPacketButton').getBoundingClientRect().width,
        exportHeight: document.querySelector('#exportMilaPacketButton').getBoundingClientRect().height,
        clipped
      };
    })""")
    check("Mila projection remains bounded at 320px and 200 percent text", mila_geometry["scrollWidth"] <= mila_geometry["clientWidth"], json.dumps(mila_geometry))
    check("Mila headline remains fully visible at 320px and 200 percent text", mila_geometry["titleScroll"] <= mila_geometry["titleClient"] + 1, json.dumps(mila_geometry))
    check("Mila receiver text has no horizontal clipping", len(mila_geometry["clipped"]) == 0, json.dumps(mila_geometry["clipped"]))
    check("Mila export remains operable at narrow text zoom", mila_geometry["exportWidth"] > 0 and mila_geometry["exportHeight"] >= 44, json.dumps(mila_geometry))'''
    text = once(text, old_geometry, new_geometry, "narrow clipping gate")
    text = once(
        text,
        '"screenshots": ["operating-desk-mobile.png", "mila-review-desktop.png", "mila-review-320-200pct.png"],',
        '"screenshots": ["operating-desk-mobile.png", "mila-review-desktop.png", "mila-review-mobile.png", "mila-review-320-200pct.png"],',
        "browser receipt screenshot list",
    )
    BROWSER.write_text(text, encoding="utf-8")


def patch_readme() -> None:
    text = README.read_text(encoding="utf-8")
    marker = "## Mila receiver polish (v1.2.1)"
    if marker not in text:
        text += '''

## Mila receiver polish (v1.2.1)

The direct Mila route removes the general operating shell, duplicate decision totals, footer provenance string, tour, onboarding, guidance, and unrelated navigation. It opens as one centered executive folio with five choices, three current queues, and one local export. The headline and every receiver-facing text block are explicitly checked for horizontal clipping at ordinary mobile size and at 320 CSS pixels with 200 percent root text.
'''
    README.write_text(text, encoding="utf-8")


def main() -> None:
    patch_index()
    patch_static()
    patch_browser()
    patch_readme()
    print("Mila receiver polish materialized")


if __name__ == "__main__":
    main()

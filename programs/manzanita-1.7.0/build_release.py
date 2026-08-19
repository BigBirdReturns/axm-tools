#!/usr/bin/env python3
"""Build the exact Manzanita Works v1.7.0 public release from a sealed review donor."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

RELEASE = "1.7.0"
VISUAL_SYSTEM = "semantic-source-adaptive-place-fabric"
PUBLIC_ROUTE = "https://bigbirdreturns.github.io/axm-tools/manzanita/"


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(repo: Path, donor: Path, donor_commit: str) -> dict:
    target = repo / "manzanita"
    program = repo / "programs/manzanita-1.7.0"
    evidence = program / "evidence"

    predecessor_commit = run("git", "rev-parse", "HEAD", cwd=repo)
    predecessor_tree = run("git", "rev-parse", "HEAD:manzanita", cwd=repo)
    predecessor_files: dict[str, dict[str, object]] = {}
    for line in run("git", "ls-tree", "-r", "HEAD", "manzanita", cwd=repo).splitlines():
        meta, relative = line.split("\t", 1)
        _mode, _type, blob = meta.split()
        source = repo / relative
        predecessor_files[relative] = {
            "git_blob_sha1": blob,
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
        }

    candidate_receipt = json.loads(
        (donor / "qualification/final-v57/RELEASE_CANDIDATE_RECEIPT.json").read_text(encoding="utf-8")
    )
    if candidate_receipt.get("result") != "PASS" or candidate_receipt.get("candidate_release") != RELEASE:
        raise SystemExit("Donor is not the sealed passing 1.7.0 candidate")

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    html = (donor / "index.html").read_text(encoding="utf-8")
    references = set(re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html))
    core = {"index.html"} | {
        value for value in references if not re.match(r"^(?:https?:|data:|#)", value)
    }
    core.update(
        path.relative_to(donor).as_posix()
        for path in (donor / "assets").iterdir()
        if path.is_file()
    )
    for optional in (
        "data.json",
        "V53_SEMANTIC_SNAP_RECEIPTS.json",
        "V561_ASSET_CATALOG.json",
        "V5_BUILD_RECEIPT.json",
        "LICENSE_VISUAL_ASSETS.md",
    ):
        if (donor / optional).is_file():
            core.add(optional)

    for relative in sorted(core):
        source = donor / relative
        if not source.is_file():
            raise SystemExit(f"Donor dependency is absent: {relative}")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    index = target / "index.html"
    text = index.read_text(encoding="utf-8")
    text = re.sub(r'data-release="[^"]+"', f'data-release="{RELEASE}"', text, count=1)
    if "data-visual-system=" in text:
        text = re.sub(
            r'data-visual-system="[^"]+"',
            f'data-visual-system="{VISUAL_SYSTEM}"',
            text,
            count=1,
        )
    else:
        text = text.replace("<html ", f'<html data-visual-system="{VISUAL_SYSTEM}" ', 1)
    text = text.replace("semantic Access review v4", "semantic source-adaptive place fabric")
    text = text.replace("SEMANTIC ACCESS REVIEW V4", "SEMANTIC SOURCE-ADAPTIVE PLACE FABRIC")
    text = text.replace("REVIEW OBJECT", "PUBLIC-SAFE OPERATING SURFACE")
    text = text.replace("review-only", "public-safe read-only")
    text = text.replace("source-adaptive-semantic-v4", RELEASE)
    if "Content-Security-Policy" not in text:
        text = text.replace(
            "</head>",
            "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self'; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'\">\n</head>",
            1,
        )
    index.write_text(text, encoding="utf-8")

    for path in target.glob("*.js"):
        data = path.read_text(encoding="utf-8")
        data = re.sub(r"source-adaptive-semantic-v(?:4|5(?:\.\d+)?)", RELEASE, data)
        data = data.replace(
            "review_evidence_not_public_release",
            "public_release_read_only_no_external_effect",
        )
        path.write_text(data, encoding="utf-8")

    if (target / "data.json").is_file():
        data = json.loads((target / "data.json").read_text(encoding="utf-8"))
        data["release"] = RELEASE
        write(target / "data.json", json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    write(
        target / "README.md",
        f"""# Manzanita Works v{RELEASE}

Manzanita Works is a public-safe source-adaptive place fabric. Seven operating apertures, eight evidence instruments, five functional seats, exact source envelopes, asset-bound semantic geometry, bounded natural-border refinement, local correction export, nonspatial evidence mechanisms, and a guided operating path share one read-only public surface.

Spatial Access, Shade, and Water geometry appears only when the exact displayed asset has a matching semantic receipt. Unknown provider scenes, map-only operation, held evidence, failed image payloads, and blocked terms render no local geometry. Care, Heat, Air, Fire, and Assistance use attention, temporal, provider-state, regional-context, and workflow mechanisms rather than decorative image overlays.

The application makes no purchase, dispatch, inspection, work, eligibility, insurance, enforcement, evacuation, safety, or other external decision. Exported records preserve source, uncertainty, authority, refusal, and no-effect boundaries.
""",
    )

    served = [
        path
        for path in sorted(target.rglob("*"))
        if path.is_file() and path.name != "QUALIFICATION.json" and "tests" not in path.parts
    ]
    files = {
        path.relative_to(target).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in served
    }
    qualification = {
        "schema": "manzanita-works/public-qualification@1",
        "release": RELEASE,
        "visual_system": VISUAL_SYSTEM,
        "source_donor": {
            "branch": "agent/manzanita-semantic-instruments-v5",
            "commit": donor_commit,
            "receipt": "review/manzanita-semantic-instruments-v5/qualification/final-v57/RELEASE_CANDIDATE_RECEIPT.json",
        },
        "predecessor": {
            "release": "1.6.0",
            "commit": predecessor_commit,
            "tree": predecessor_tree,
        },
        "files": files,
        "required_counts": {"apertures": 7, "instruments": 8, "seats": 5},
        "external_effects": 0,
        "public_route": PUBLIC_ROUTE,
    }
    write(target / "QUALIFICATION.json", json.dumps(qualification, indent=2, sort_keys=True) + "\n")

    tests = target / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    write(
        tests / "public_contract_test.py",
        '''#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
q=json.loads((ROOT/'QUALIFICATION.json').read_text())
assert q['release']=='1.7.0'
assert q['visual_system']=='semantic-source-adaptive-place-fabric'
html=(ROOT/'index.html').read_text()
assert 'data-release="1.7.0"' in html
assert 'data-visual-system="semantic-source-adaptive-place-fabric"' in html
for rel,expected in q['files'].items():
    path=ROOT/rel
    assert path.is_file(),rel
    payload=path.read_bytes()
    assert len(payload)==expected['bytes'],rel
    assert hashlib.sha256(payload).hexdigest()==expected['sha256'],rel
scripts='\n'.join(p.read_text(errors='replace') for p in ROOT.glob('*.js'))
for marker in ('__MANZANITA_SEMANTIC_INSTRUMENTS_V5__','__MANZANITA_SEMANTIC_LOCK_V51__','semantic-correction-patch@1','source-envelope@1','rendered_nonspatial_mechanism','__MANZANITA_GUIDE_V56__'):
    assert marker in scripts,marker
assert 'generic gradient registration' not in scripts.lower()
assert len(list((ROOT/'assets').iterdir()))>=10
print(json.dumps({'result':'PASS','release':q['release'],'qualified_files':len(q['files'])},indent=2))
''',
    )

    write(
        tests / "browser_test.py",
        '''#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,contextlib,json,socket,threading
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Q(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
@contextlib.contextmanager
def serve():
    class H(Q):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    server=ThreadingHTTPServer(('127.0.0.1',port),H);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{port}/index.html'
    finally:server.shutdown();thread.join(timeout=5)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target');parser.add_argument('--output',type=Path);args=parser.parse_args();out=args.output or ROOT/'browser-evidence';out.mkdir(parents=True,exist_ok=True)
    context=serve() if not args.target else contextlib.nullcontext(args.target)
    report={'schema':'manzanita-works/public-browser-campaign@1','release':'1.7.0','result':'HOLD','captures':[],'failures':[],'console_errors':[],'page_errors':[],'external_requests':[]}
    with context as url, sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome')
        origin=url.split('/index.html')[0] if '/index.html' in url else '/'.join(url.split('/')[:3])
        for label,w,h in [('desktop',1600,1000),('laptop',1024,900),('mobile',390,844),('compact',320,720)]:
            ctx=browser.new_context(viewport={'width':w,'height':h},accept_downloads=True,reduced_motion='reduce' if label=='mobile' else 'no-preference');page=ctx.new_page();page.on('console',lambda m:report['console_errors'].append(m.text) if m.type=='error' else None);page.on('pageerror',lambda e:report['page_errors'].append(str(e)));page.on('request',lambda r:report['external_requests'].append(r.url) if not r.url.startswith(origin) else None);page.goto(url,wait_until='networkidle')
            if page.locator('html').get_attribute('data-release')!='1.7.0':report['failures'].append(f'{label} release marker')
            if page.locator('[data-aperture]').count()!=7 or page.locator('[data-instrument]').count()!=8 or page.locator('[data-seat]').count()!=5:report['failures'].append(f'{label} control counts')
            for sel in ('[data-aperture="street"]','[data-mode="reference"]','[data-instrument="access"]'):page.locator(sel).first.click();page.wait_for_timeout(70)
            sem=page.evaluate('window.__MANZANITA_SEMANTIC_INSTRUMENTS_V5__');lock=page.evaluate('window.__MANZANITA_SEMANTIC_LOCK_V51__');features=page.locator('[data-feature-id]').count()
            if sem.get('result')!='rendered_exact_asset_semantics' or lock.get('result')!='locked_to_rendered_asset' or not features:report['failures'].append(f'{label} semantic access')
            page.locator('[data-aperture="region"]').first.click();page.locator('[data-instrument="fire"]').first.click();page.wait_for_timeout(60);non=page.evaluate('window.__MANZANITA_NONSPATIAL_V55__')
            if non.get('result')!='rendered_nonspatial_mechanism' or page.locator('[data-feature-id]').count() or page.locator('#overlay > *,svg.overlay > *').count():report['failures'].append(f'{label} fire nonspatial')
            page.locator('[data-aperture="street"]').first.click();page.locator('[data-instrument="access"]').first.click();page.locator('[data-mode="map"]').first.click();page.wait_for_timeout(50)
            if page.locator('[data-feature-id]').count() or page.locator('#overlay > *,svg.overlay > *').count():report['failures'].append(f'{label} map geometry')
            page.locator('[data-mode="reference"]').first.click();page.wait_for_timeout(50);page.locator('.v51-badge').first.click();page.locator('#v52Edit').click();page.wait_for_timeout(40)
            if not page.locator('.v52-handle').count():report['failures'].append(f'{label} editor')
            page.locator('#v56GuideOpen').click();page.wait_for_timeout(30)
            if not page.locator('#v56Guide').is_visible():report['failures'].append(f'{label} guide')
            page.locator('#v56Exit').click();page.locator('#v54SourceToggle').click();page.wait_for_timeout(30)
            if not page.locator('#v54SourceDrawer').is_visible():report['failures'].append(f'{label} source drawer')
            overflow=page.evaluate('Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-innerWidth');floor=page.evaluate('Math.min(...[...document.querySelectorAll("button")].filter(n=>{const b=n.getBoundingClientRect(),s=getComputedStyle(n);return b.width>0&&b.height>0&&s.display!=="none"&&s.visibility!=="hidden"}).map(n=>n.getBoundingClientRect().height))')
            if overflow>2 or floor<43.5:report['failures'].append(f'{label} responsive {overflow}/{floor}')
            shot=out/f'{label}.png';page.screenshot(path=str(shot),full_page=False);report['captures'].append({'label':label,'screenshot':shot.name,'features':features,'overflow':overflow,'minimum_button_height':floor});ctx.close()
        browser.close()
    if report['console_errors']:report['failures'].append('console errors')
    if report['page_errors']:report['failures'].append('page errors')
    if report['external_requests']:report['failures'].append('external requests')
    report['result']='PASS' if not report['failures'] else 'FAIL';(out/'BROWSER_CAMPAIGN.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['result']=='PASS',report['failures']
if __name__=='__main__':main()
''',
    )

    program.mkdir(parents=True, exist_ok=True)
    source_record = {
        "schema": "manzanita-works/release-source-donor@1",
        "release": RELEASE,
        "donor_branch": "agent/manzanita-semantic-instruments-v5",
        "donor_commit": donor_commit,
        "candidate_receipt": "review/manzanita-semantic-instruments-v5/qualification/final-v57/RELEASE_CANDIDATE_RECEIPT.json",
        "candidate_manifest": "review/manzanita-semantic-instruments-v5/qualification/final-v57/FINAL_FILE_MANIFEST.json",
        "claim": "Exact internally qualified public-safe donor. Public standing begins only after merge, Pages deployment, exact public-byte proof, and live browser replay.",
    }
    write(program / "SOURCE_DONOR.json", json.dumps(source_record, indent=2) + "\n")
    write(
        program / "ROLLBACK_MANIFEST.json",
        json.dumps(
            {
                "schema": "manzanita-works/rollback-manifest@1",
                "release": "1.6.0",
                "commit": predecessor_commit,
                "tree": predecessor_tree,
                "files": predecessor_files,
                "activation": "Deploy the exact predecessor tree or exact manifest bytes.",
                "standing": "historical public rollback donor",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    write(
        program / "RELEASE_CONTRACT.json",
        json.dumps(
            {
                "schema": "manzanita-works/release-contract@1",
                "release": RELEASE,
                "classification": "semantic_source_adaptive_public_release",
                "public_route": "manzanita/",
                "source_donor": source_record,
                "rollback": {
                    "release": "1.6.0",
                    "commit": predecessor_commit,
                    "tree": predecessor_tree,
                },
                "required_gates": [
                    "static contract",
                    "exact candidate browser campaign",
                    "responsive rendered evidence",
                    "merge to main",
                    "successful Pages deployment",
                    "exact public-byte equality",
                    "live browser replay",
                ],
                "external_effects": "none",
                "successor_program_effect": "none",
                "canonical_task_count_effect": "none",
            },
            indent=2,
        )
        + "\n",
    )

    evidence.mkdir(parents=True, exist_ok=True)
    for relative in (
        "qualification/final-v57/RELEASE_CANDIDATE_RECEIPT.json",
        "qualification/final-v57/FINAL_FILE_MANIFEST.json",
        "qualification/final-v57/FINAL_BROWSER_CAMPAIGN.json",
        "qualification/final-v57/FINAL_CANDIDATE_CONTACT_SHEET.jpg",
        "qualification/semantic-snap-v53/SEMANTIC_SEED_TO_SNAP.jpg",
        "qualification/semantic-editor-v52/SEMANTIC_GRAMMAR_AND_EDITOR.jpg",
        "qualification/source-envelope-v54/SOURCE_STATE_CONTINUUM.jpg",
        "qualification/nonspatial-v55/NONSPATIAL_MECHANISMS.jpg",
        "qualification/guided-v56/GUIDED_APERTURE_PATHS.jpg",
    ):
        source = donor / relative
        if source.is_file():
            destination = evidence / source.name
            shutil.copy2(source, destination)

    for relative in ("README.md", "index.html"):
        path = repo / relative
        if path.is_file():
            data = path.read_text(encoding="utf-8")
            data = data.replace("Manzanita Works v1.6.0", "Manzanita Works v1.7.0")
            data = data.replace("Manzanita Works v1.6", "Manzanita Works v1.7")
            data = data.replace("photographic place fabric", "semantic source-adaptive place fabric")
            path.write_text(data, encoding="utf-8")

    write(
        repo / ".github/workflows/manzanita-check.yml",
        '''name: Manzanita Works v1.7.0 semantic source-adaptive contract

on:
  push:
    paths:
      - "manzanita/**"
      - "programs/manzanita-1.7.0/**"
      - ".github/workflows/manzanita-check.yml"
  pull_request:
    paths:
      - "manzanita/**"
      - "programs/manzanita-1.7.0/**"
      - ".github/workflows/manzanita-check.yml"
  workflow_dispatch: {}

permissions:
  contents: read

jobs:
  qualify:
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Static exact-byte contract
        run: python manzanita/tests/public_contract_test.py
      - name: Parse every runtime
        run: |
          for file in manzanita/*.js; do node --check "$file"; done
      - name: Install browser library
        run: python -m pip install --disable-pip-version-check playwright==1.57.0
      - name: Drive the exact candidate
        run: python manzanita/tests/browser_test.py --output ${{ runner.temp }}/manzanita-v17-browser
      - uses: actions/upload-artifact@v4
        with:
          name: manzanita-v1.7.0-browser-${{ github.sha }}
          path: ${{ runner.temp }}/manzanita-v17-browser
          if-no-files-found: error
          retention-days: 30
''',
    )

    write(
        repo / ".github/workflows/manzanita-live-check.yml",
        '''name: Manzanita Works v1.7.0 live Pages gate

on:
  workflow_run:
    workflows: ["PTA tracker fetch + deploy"]
    types: [completed]
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  live:
    if: >-
      github.event_name == 'workflow_dispatch' ||
      (github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.head_branch == 'main')
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    env:
      PUBLIC_URL: https://bigbirdreturns.github.io/axm-tools/manzanita/
      SOURCE_SHA: ${{ github.event.workflow_run.head_sha || github.sha }}
      PAGES_RUN_ID: ${{ github.event.workflow_run.id || github.run_id }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install browser library
        run: python -m pip install --disable-pip-version-check playwright==1.57.0
      - name: Wait for exact release markers and public bytes
        run: |
          set -euo pipefail
          mkdir -p /tmp/manzanita-live/files /tmp/manzanita-live/browser
          for attempt in $(seq 1 36); do
            code=$(curl -L -sS -o /tmp/manzanita-live/index.html -w '%{http_code}' "$PUBLIC_URL?v=$SOURCE_SHA" || true)
            if [ "$code" = 200 ] && grep -q 'data-release="1.7.0"' /tmp/manzanita-live/index.html && grep -q 'data-visual-system="semantic-source-adaptive-place-fabric"' /tmp/manzanita-live/index.html; then break; fi
            if [ "$attempt" = 36 ]; then echo "Public route did not expose v1.7.0"; exit 1; fi
            sleep 10
          done
          python - <<'PY'
          import hashlib,json,os
          from pathlib import Path
          from urllib.parse import quote,urljoin
          from urllib.request import Request,urlopen
          base=os.environ['PUBLIC_URL'];source=quote(os.environ['SOURCE_SHA'],safe='')
          q=json.loads(Path('manzanita/QUALIFICATION.json').read_text());observed={}
          for rel,expected in sorted(q['files'].items()):
              url=urljoin(base,rel)+f'?v={source}'
              with urlopen(Request(url,headers={'User-Agent':'manzanita-live-gate/1.7.0'}),timeout=45) as response:payload=response.read()
              digest=hashlib.sha256(payload).hexdigest()
              if len(payload)!=expected['bytes'] or digest!=expected['sha256']:raise SystemExit(f'public byte mismatch: {rel}')
              target=Path('/tmp/manzanita-live/files')/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload);observed[rel]={'bytes':len(payload),'sha256':digest}
          Path('/tmp/manzanita-live/EXACT_PUBLIC_BYTES.json').write_text(json.dumps({'schema':'manzanita-works/exact-public-bytes@1','release':'1.7.0','result':'PASS','source_sha':os.environ['SOURCE_SHA'],'files':observed},indent=2)+'\n')
          PY
      - name: Replay the browser campaign against GitHub Pages
        run: python manzanita/tests/browser_test.py --target "$PUBLIC_URL?v=$SOURCE_SHA" --output /tmp/manzanita-live/browser
      - name: Build durable live receipt
        run: |
          python - <<'PY'
          import json,os
          from datetime import datetime,timezone
          from pathlib import Path
          bytes_data=json.loads(Path('/tmp/manzanita-live/EXACT_PUBLIC_BYTES.json').read_text());browser=json.loads(Path('/tmp/manzanita-live/browser/BROWSER_CAMPAIGN.json').read_text())
          receipt={'schema':'manzanita-works/live-pages-receipt@3','release':'1.7.0','state':'PASS' if bytes_data['result']==browser['result']=='PASS' else 'FAIL','observed_at':datetime.now(timezone.utc).isoformat(),'public_route':os.environ['PUBLIC_URL'],'source_sha':os.environ['SOURCE_SHA'],'pages_run_id':os.environ['PAGES_RUN_ID'],'exact_public_bytes':bytes_data,'browser':browser,'external_effects':'none','successor_program_effect':'none','canonical_task_count_effect':'none'}
          Path('/tmp/manzanita-live/LIVE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');assert receipt['state']=='PASS'
          PY
      - uses: actions/upload-artifact@v4
        with:
          name: manzanita-v1.7.0-live-${{ env.PAGES_RUN_ID }}
          path: /tmp/manzanita-live
          if-no-files-found: error
          retention-days: 90
      - name: Retain receipt on the isolated evidence branch
        run: |
          set -euo pipefail
          cp /tmp/manzanita-live/LIVE_RECEIPT.json /tmp/LIVE_RECEIPT.json
          if git fetch origin evidence/manzanita-live; then
            git switch -C evidence/manzanita-live origin/evidence/manzanita-live
          else
            git switch --orphan evidence/manzanita-live
            git rm -rf . || true
          fi
          mkdir -p receipts/v1.7.0
          cp /tmp/LIVE_RECEIPT.json "receipts/v1.7.0/$PAGES_RUN_ID.json"
          git config user.name "manzanita-live-gate"
          git config user.email "actions@users.noreply.github.com"
          git add "receipts/v1.7.0/$PAGES_RUN_ID.json"
          git commit -m "Manzanita: retain v1.7.0 live receipt $PAGES_RUN_ID"
          git push origin HEAD:evidence/manzanita-live
''',
    )

    return {
        "result": "BUILT",
        "release": RELEASE,
        "visual_system": VISUAL_SYSTEM,
        "donor_commit": donor_commit,
        "predecessor_commit": predecessor_commit,
        "predecessor_tree": predecessor_tree,
        "served_files": len(files),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--donor-root", type=Path, required=True)
    parser.add_argument("--donor-commit", required=True)
    args = parser.parse_args()
    result = build(args.repo_root.resolve(), args.donor_root.resolve(), args.donor_commit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
q = json.loads((ROOT / 'QUALIFICATION.json').read_text(encoding='utf-8'))
r = json.loads((ROOT / 'RELEASE_RECEIPT.json').read_text(encoding='utf-8'))
assert q['schema'] == 'manzanita-works/pages-qualification@6'
assert q['release'] == '1.6.0'
assert q['visual_system'] == 'photographic-place-fabric'
assert q['apertures'] == 7 and q['overlays'] == 8 and q['operating_seats'] == 5
assert q['external_effect_adapters'] == 0
assert q['distinct_aperture_assets'] == 7
assert r['release'] == '1.6.0'
assert r['authority']['successor_program_effect'] == 'none'
assert r['authority']['external_campaign_effect'] == 'none'
assert r['authority']['canonical_task_count_effect'] == 'none'
for name, expected in q['files'].items():
    data = (ROOT / name).read_bytes()
    assert len(data) == expected['bytes'], (name, len(data), expected['bytes'])
    assert hashlib.sha256(data).hexdigest() == expected['sha256'], name
html = (ROOT / 'index.html').read_text(encoding='utf-8')
css = (ROOT / 'style.css').read_text(encoding='utf-8')
js = (ROOT / 'app.js').read_text(encoding='utf-8')
for phrase in ('data-release="1.6.0"','photographic-place-fabric','The place is the operating record.','Fresh catnip exposed the entire system.','Change the aperture. Keep the record.','Prevention data stays prevention data.','Automatic insurance denial','Essential Attention','Every image says what it is.'):
    assert phrase in html, phrase
assert len(re.findall(r"id:'(?:plant|household|property|street|neighborhood|region|stewardship)'", js)) == 7
assert len(re.findall(r"id:'(?:habitat|shade|water|fire|air|access|labor|authority)'", js)) == 8
assert len(re.findall(r"id:'(?:resident|nursery|crew|planner|successor)'", js)) == 5
assert 'history.replaceState' in js and 'URLSearchParams' in js
assert 'window.print()' in js and 'new Blob' in js
assert "'ArrowRight'" in js and "'Home'" in js and "'End'" in js
for forbidden in ('XMLHttpRequest','WebSocket','EventSource','navigator.sendBeacon'):
    assert forbidden not in js
assert 'window.MANZANITA_SCENES' in js
assert 'fetch(' not in js
assert '@media print' in css and '@media(max-width:420px)' in css and '@media(prefers-reduced-motion:reduce)' in css
assert len(list((ROOT / 'assets').glob('*.webp'))) == 7
scene = json.loads((ROOT / 'assets/scene-data.json').read_text(encoding='utf-8'))
assert set(scene) == {'plant','household','property','street','neighborhood','region','stewardship'}
assert all(Path(ROOT / row['asset']).is_file() for row in scene.values())
assert all(set(row['registration']) == {'habitat','shade','water','fire','air','access','labor','authority'} for row in scene.values())
print('Manzanita Works v1.6.0 photographic public contract: PASS')

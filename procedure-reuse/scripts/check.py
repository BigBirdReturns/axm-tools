"""Standard-library release validation; exits nonzero on drift."""
from pathlib import Path
import hashlib, json
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'v1/manifest.json').read_text())
for name,want in manifest['sha256'].items():
    path=root/'v1'/name
    assert path.is_relative_to(root/'v1') and '..' not in Path(name).parts
    assert hashlib.sha256(path.read_bytes()).hexdigest()==want, name
html=(root/'v1/fixture.html').read_text()
assert "connect-src 'none'" in html and "form-action 'none'" in html
js=(root/'v1/fixture.mjs').read_text()
for forbidden in ['fetch(', 'XMLHttpRequest', 'sendBeacon', 'WebSocket', 'document.cookie', 'innerHTML=']:
    assert forbidden not in js, forbidden
assert 'axm.procedure-reuse.v1.' in js
assert not list(root.rglob('package.json'))
print(f"Release hashes and static boundaries: {len(manifest['sha256'])} files PASS")

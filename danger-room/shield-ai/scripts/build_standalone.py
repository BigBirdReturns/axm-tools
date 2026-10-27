"""Build the complete local application using only Python's standard library."""
import base64
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

def source_hash(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode('utf-8')).digest()).decode('ascii') + "'"

def build():
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    script_hashes, style_hashes = [], []
    def script(match):
        path = ROOT / match.group(1)
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Script path leaves module')
        # Escape document-closing strings as well as script closers. Static preview
        # servers can inject live-reload markup at a literal </body> inside a JS
        # template; JS escaped slashes preserve the generated document verbatim.
        body = '\n' + re.sub(r'</(script|body|head|html)\b', r'<\\/\1', path.read_text(encoding='utf-8'), flags=re.I) + '\n'
        script_hashes.append(source_hash(body))
        return '<script>' + body + '</script>'
    def style(match):
        body = '\n' + (ROOT / match.group(1)).read_text(encoding='utf-8') + '\n'
        style_hashes.append(source_hash(body))
        return '<style>' + body + '</style>'
    html = re.sub(r'<script src="([^"]+)"></script>', script, html)
    html = re.sub(r'<link rel="stylesheet" href="([^"]+)">', style, html)
    policy = "default-src 'none'; script-src " + ' '.join(script_hashes) + "; style-src " + ' '.join(style_hashes) + "; img-src data:; connect-src 'none'; font-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"
    html = re.sub(r'(<meta http-equiv="Content-Security-Policy" content=")[^"]*(">)', lambda m: m.group(1) + policy + m.group(2), html)
    if len(script_hashes) < 6 or not style_hashes:
        raise RuntimeError('Expected all application scripts and the style sheet')
    out = ROOT / 'standalone.html'
    out.write_text(html, encoding='utf-8')
    print(out.name + ': ' + str(out.stat().st_size) + ' bytes; ' + str(len(script_hashes)) + ' embedded scripts; CSP hashes retained')

if __name__ == '__main__':
    build()

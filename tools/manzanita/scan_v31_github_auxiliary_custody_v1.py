#!/usr/bin/env python3
"""Bounded exact-byte scan of GitHub wiki and public issue/PR attachment custody."""
from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

REPO = os.environ.get('GH_REPO', 'BigBirdReturns/axm-tools')
OUT = Path(os.environ.get('V31_AUX_OUT', '/tmp/v31-github-auxiliary-custody-v1')).resolve()
MAX_SINGLE = int(os.environ.get('V31_AUX_MAX_SINGLE_BYTES', '550000000'))
MAX_TOTAL = int(os.environ.get('V31_AUX_MAX_TOTAL_BYTES', '2000000000'))
MAX_ATTACHMENTS = int(os.environ.get('V31_AUX_MAX_ATTACHMENTS', '500'))
MAX_DEPTH = 7
KNOWN_RETAINED = {'neighborhood_cached'}

TARGETS = {
    'accepted_parent_archive': (['mw-habitat-live-photo-030-r1.zip'], 82813564, '8a480a3bd05afb6cdcc007d98b0ef63e80576fb1912763c147a3739647299f91'),
    'v20_archive': (['mw-habitat-live-photo-020.zip'], 146305044, '98b81d0f3f56a8aa6a12613fe7ae06b8b9e860f82ddaa02aa48e6f66547c25bd'),
    'public_convergence': (['PUBLIC_CONVERGENCE.json'], 127413, 'fd9dfd98532a21759754cb8969b2ad2d7a94fedce78ea8a428e584bf14aea1d9'),
    'admission_source': (['admit_v31_exact_inputs.py'], 38969, 'c3eed78862ae53a975d13b94f2cf82eeea832466a46bdb3e771fd798bd12534a'),
    'neighborhood_reference': (['neighborhood-reference.png', 'neighborhood-systems-ae49e0308b30.png'], 2797021, 'ae49e0308b302e5bdce1cdb5913b009c2743d1043ddcb8c2e29b6934e1353b9b'),
    'neighborhood_cached': (['neighborhood-cached.webp', 'neighborhood-reference-5ec9252f1615.webp'], 500586, '5ec9252f1615e86a239384a76a508554b2bd9e9221d5e202abce109e804f29d8'),
    'neighborhood_map': (['neighborhood-map.svg', 'neighborhood-map-2d1d6abe3784.svg'], 2038, '2d1d6abe37845ed2b65070a9198d301c3e6e4df779139003499eb8ff406d6e3b'),
}
BY_ID = {(size, digest): name for name, (_, size, digest) in TARGETS.items()}
BY_SIZE: dict[int, list[str]] = {}
BY_NAME: dict[str, str] = {}
for target, (names, size, _) in TARGETS.items():
    BY_SIZE.setdefault(size, []).append(target)
    for name in names:
        BY_NAME[name.lower()] = target

ATTACHMENT_RE = re.compile(
    r'https://(?:github\.com/user-attachments/(?:assets|files)/[^\s<>()\[\]{}"\']+'
    r'|private-user-images\.githubusercontent\.com/[^\s<>()\[\]{}"\']+'
    r'|user-images\.githubusercontent\.com/[^\s<>()\[\]{}"\']+'
    r'|objects\.githubusercontent\.com/github-production-user-asset-[^\s<>()\[\]{}"\']+)',
    re.I,
)
DATA_URL_RE = re.compile(
    rb'data:[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+(?:;[A-Za-z0-9_.=:+-]+)*;base64,([A-Za-z0-9+/=\r\n]{16,})'
)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def run(args: list[str], *, cwd: Path | None = None, timeout: int = 1200, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=check,
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_member(name: str) -> bool:
    normalized = name.replace('\\', '/')
    p = PurePosixPath(normalized)
    return bool(normalized) and not p.is_absolute() and not re.match(r'^[A-Za-z]:', normalized) and all(part not in ('', '.', '..') for part in p.parts)


def sanitize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    clean = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    return clean.rstrip('.,;:!?)\\]}\'"')


def flatten_pages(payload: Any, list_key: str | None = None) -> list[Any]:
    pages = payload if isinstance(payload, list) else [payload]
    rows: list[Any] = []
    for page in pages:
        if list_key and isinstance(page, dict):
            rows.extend(page.get(list_key, []))
        elif isinstance(page, list):
            rows.extend(page)
        elif isinstance(page, dict):
            rows.append(page)
    return rows


class Scan:
    def __init__(self) -> None:
        self.started = now()
        self.download_dir = OUT / '_downloads'
        self.hit_dir = OUT / 'exact-hits'
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.hit_dir.mkdir(parents=True, exist_ok=True)
        self.counts = {
            'text_records': 0,
            'attachment_urls': 0,
            'attachment_download_attempts': 0,
            'attachment_downloads': 0,
            'attachment_download_bytes': 0,
            'attachment_count_limit_skips': 0,
            'attachment_total_byte_limit_skips': 0,
            'attachment_download_failures': 0,
            'wiki_objects': 0,
            'wiki_blobs': 0,
            'wiki_blob_bytes': 0,
            'wiki_blob_skips': 0,
            'blobs_hashed': 0,
            'bytes_hashed': 0,
            'zip_containers': 0,
            'zip_members': 0,
            'zip_member_skips': 0,
            'unsafe_paths': 0,
            'data_urls': 0,
            'decoded_data_urls': 0,
            'exact_hits': 0,
            'name_candidates': 0,
            'size_candidates': 0,
            'reference_records': 0,
            'errors': 0,
        }
        self.errors: list[dict[str, Any]] = []
        self.hits: list[dict[str, Any]] = []
        self.candidates: list[dict[str, Any]] = []
        self.references: list[dict[str, Any]] = []
        self.seen: set[tuple[int, str]] = set()
        self.exact_targets: set[str] = set()
        self.api_calls: list[dict[str, Any]] = []
        self.wiki: dict[str, Any] = {}
        self.attachments: list[dict[str, Any]] = []

    def error(self, lane: str, source: str, exc: Any) -> None:
        self.counts['errors'] += 1
        if len(self.errors) < 1000:
            self.errors.append({'lane': lane, 'source': source, 'error': str(exc)[:3000]})

    def retain_hit(self, target: str, data: bytes, source: str, source_class: str, basename: str | None) -> None:
        filename = TARGETS[target][0][0]
        path = self.hit_dir / target / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        if sha256(path.read_bytes()) != TARGETS[target][2]:
            raise RuntimeError(f'exact-hit retention collision for {target}')
        row = {
            'target': target,
            'source': source,
            'source_class': source_class,
            'basename': basename,
            'bytes': len(data),
            'sha256': sha256(data),
            'retained_path': path.relative_to(OUT).as_posix(),
        }
        if row not in self.hits:
            self.hits.append(row)
        self.exact_targets.add(target)
        self.counts['exact_hits'] = len(self.hits)

    def inspect_blob(self, data: bytes, source: str, source_class: str, basename: str | None = None, depth: int = 0) -> None:
        digest = sha256(data)
        size = len(data)
        self.counts['blobs_hashed'] += 1
        self.counts['bytes_hashed'] += size
        target = BY_ID.get((size, digest))
        if target:
            self.retain_hit(target, data, source, source_class, basename)
        elif basename and basename.lower() in BY_NAME:
            self.counts['name_candidates'] += 1
            if len(self.candidates) < 5000:
                self.candidates.append({
                    'kind': 'basename_mismatch',
                    'target': BY_NAME[basename.lower()],
                    'source': source,
                    'basename': basename,
                    'bytes': size,
                    'sha256': digest,
                })
        if size in BY_SIZE and not target:
            self.counts['size_candidates'] += 1
            if len(self.candidates) < 5000:
                self.candidates.append({
                    'kind': 'exact_size_hash_mismatch',
                    'targets': sorted(BY_SIZE[size]),
                    'source': source,
                    'basename': basename,
                    'bytes': size,
                    'sha256': digest,
                })

        key = (size, digest)
        if key in self.seen:
            return
        self.seen.add(key)

        if depth <= MAX_DEPTH and data[:4] in (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'):
            self.inspect_zip(data, source, depth + 1)
        if size <= 64 * 1024 * 1024:
            for index, match in enumerate(DATA_URL_RE.finditer(data)):
                self.counts['data_urls'] += 1
                try:
                    decoded = base64.b64decode(re.sub(rb'\s+', b'', match.group(1)), validate=True)
                except (binascii.Error, ValueError) as exc:
                    self.error('data-url-decode', f'{source}#{index}', exc)
                    continue
                self.counts['decoded_data_urls'] += 1
                self.inspect_blob(decoded, f'{source}#data-url-{index}', 'embedded_data_url', None, depth + 1)

    def inspect_zip(self, data: bytes, source: str, depth: int) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.counts['zip_containers'] += 1
                bad = archive.testzip()
                if bad is not None:
                    self.error('zip-crc', source, bad)
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    self.counts['zip_members'] += 1
                    if not safe_member(info.filename):
                        self.counts['unsafe_paths'] += 1
                        continue
                    if info.file_size > MAX_SINGLE:
                        self.counts['zip_member_skips'] += 1
                        continue
                    member_source = f'{source}!/{info.filename}'
                    try:
                        member = archive.read(info)
                    except Exception as exc:
                        self.error('zip-member', member_source, exc)
                        continue
                    self.inspect_blob(member, member_source, 'zip_member', PurePosixPath(info.filename).name, depth)
        except Exception as exc:
            self.error('zip-open', source, exc)

    def api(self, endpoint: str, lane: str) -> list[Any]:
        try:
            cp = run(['gh', 'api', '--paginate', '--slurp', endpoint], timeout=1200)
            payload = json.loads(cp.stdout)
            pages = payload if isinstance(payload, list) else [payload]
            count = sum(len(page) if isinstance(page, list) else 1 for page in pages)
            self.api_calls.append({'lane': lane, 'endpoint': endpoint, 'result': 'PASS', 'pages': len(pages), 'page_items': count})
            return flatten_pages(payload)
        except Exception as exc:
            self.api_calls.append({'lane': lane, 'endpoint': endpoint, 'result': 'FAIL', 'error': str(exc)[:2000]})
            self.error('api', lane, exc)
            return []

    def collect_attachment_urls(self) -> list[dict[str, Any]]:
        sources: list[tuple[str, str, str]] = []
        for row in self.api(f'repos/{REPO}/issues?state=all&per_page=100', 'issues-and-pr-bodies'):
            sources.append((f"issue:{row.get('number')}:body", str(row.get('html_url') or ''), str(row.get('body') or '')))
        for row in self.api(f'repos/{REPO}/issues/comments?per_page=100', 'issue-comments'):
            sources.append((f"issue-comment:{row.get('id')}", str(row.get('html_url') or ''), str(row.get('body') or '')))
        for row in self.api(f'repos/{REPO}/pulls/comments?per_page=100', 'pull-review-comments'):
            sources.append((f"pull-review-comment:{row.get('id')}", str(row.get('html_url') or ''), str(row.get('body') or '')))
        for row in self.api(f'repos/{REPO}/comments?per_page=100', 'commit-comments'):
            sources.append((f"commit-comment:{row.get('id')}", str(row.get('html_url') or ''), str(row.get('body') or '')))
        for row in self.api(f'repos/{REPO}/releases?per_page=100', 'release-bodies'):
            sources.append((f"release:{row.get('id')}:body", str(row.get('html_url') or ''), str(row.get('body') or '')))

        self.counts['text_records'] = len(sources)
        found: dict[str, dict[str, Any]] = {}
        target_tokens = [token for names, _, digest in TARGETS.values() for token in [*names, digest]]
        for source_id, venue, text in sources:
            matched_tokens = sorted({token for token in target_tokens if token in text})
            if matched_tokens:
                self.counts['reference_records'] += 1
                if len(self.references) < 1000:
                    self.references.append({
                        'source_id': source_id,
                        'venue': venue,
                        'matched_tokens': matched_tokens,
                        'standing': 'TEXTUAL_REFERENCE_ONLY',
                    })
            for raw_url in ATTACHMENT_RE.findall(text):
                clean = sanitize_url(raw_url)
                if clean not in found:
                    found[clean] = {
                        'sanitized_url': clean,
                        'host': urllib.parse.urlsplit(clean).netloc,
                        'path': urllib.parse.urlsplit(clean).path,
                        'first_source_id': source_id,
                        'first_venue': venue,
                        'url_sha256': sha256(clean.encode('utf-8')),
                    }
        rows = sorted(found.values(), key=lambda row: (row['host'], row['path']))
        self.counts['attachment_urls'] = len(rows)
        return rows

    def download_attachments(self, urls: list[dict[str, Any]]) -> None:
        total = 0
        token = os.environ.get('GH_TOKEN', '')
        for index, row in enumerate(urls):
            if index >= MAX_ATTACHMENTS:
                self.counts['attachment_count_limit_skips'] += 1
                continue
            if total >= MAX_TOTAL:
                self.counts['attachment_total_byte_limit_skips'] += 1
                continue
            self.counts['attachment_download_attempts'] += 1
            target = self.download_dir / f'attachment-{index:04d}.bin'
            headers = self.download_dir / f'attachment-{index:04d}.headers'
            cmd = [
                'curl', '-L', '--fail', '--silent', '--show-error',
                '--max-time', '300', '--max-filesize', str(MAX_SINGLE),
                '--dump-header', str(headers), '--output', str(target),
                '--header', 'Accept: application/octet-stream',
            ]
            if token:
                cmd.extend(['--header', f'Authorization: Bearer {token}'])
            cmd.append(row['sanitized_url'])
            cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=330)
            if cp.returncode != 0 or not target.is_file():
                self.counts['attachment_download_failures'] += 1
                self.attachments.append({**row, 'result': 'FAIL', 'curl_returncode': cp.returncode, 'error': cp.stderr[-1000:]})
                target.unlink(missing_ok=True)
                headers.unlink(missing_ok=True)
                continue
            size = target.stat().st_size
            if total + size > MAX_TOTAL:
                self.counts['attachment_total_byte_limit_skips'] += 1
                self.attachments.append({**row, 'result': 'SKIP_TOTAL_BYTE_LIMIT', 'bytes': size})
                target.unlink(missing_ok=True)
                headers.unlink(missing_ok=True)
                continue
            total += size
            self.counts['attachment_downloads'] += 1
            self.counts['attachment_download_bytes'] += size
            data = target.read_bytes()
            basename = PurePosixPath(row['path']).name or None
            observation = {
                **row,
                'result': 'PASS',
                'bytes': size,
                'sha256': sha256(data),
                'basename': basename,
            }
            self.attachments.append(observation)
            self.inspect_blob(data, f"attachment:{row['url_sha256']}", 'github_attachment', basename)
            target.unlink(missing_ok=True)
            headers.unlink(missing_ok=True)

    def scan_wiki(self) -> None:
        wiki_dir = OUT / '_wiki.git'
        url = f'https://github.com/{REPO}.wiki.git'
        cp = run(['git', 'clone', '--mirror', url, str(wiki_dir)], timeout=900, check=False)
        if cp.returncode != 0:
            message = (cp.stdout + '\n' + cp.stderr)[-4000:]
            absent = any(token in message.lower() for token in ('repository not found', 'does not appear to be a git repository', 'not found'))
            self.wiki = {
                'result': 'PASS_WIKI_REPOSITORY_ABSENT_OR_EMPTY' if absent else 'HOLD_WIKI_CLONE_FAILED',
                'clone_returncode': cp.returncode,
                'message': message,
                'objects': 0,
                'blobs': 0,
            }
            if not absent:
                self.error('wiki-clone', url, message)
            shutil.rmtree(wiki_dir, ignore_errors=True)
            return
        refs = run(['git', '--git-dir', str(wiki_dir), 'for-each-ref', '--format=%(refname) %(objectname)'], timeout=120).stdout.splitlines()
        rows = run([
            'git', '--git-dir', str(wiki_dir), 'cat-file', '--batch-all-objects',
            '--batch-check=%(objectname) %(objecttype) %(objectsize)'
        ], timeout=600).stdout.splitlines()
        objects = 0
        blobs = 0
        for line in rows:
            parts = line.split()
            if len(parts) != 3 or not parts[2].isdigit():
                self.error('wiki-object-row', line, 'unparsed')
                continue
            oid, kind, size_text = parts
            size = int(size_text)
            objects += 1
            if kind != 'blob':
                continue
            blobs += 1
            self.counts['wiki_blob_bytes'] += size
            if size > MAX_SINGLE:
                self.counts['wiki_blob_skips'] += 1
                continue
            raw = subprocess.run(
                ['git', '--git-dir', str(wiki_dir), 'cat-file', 'blob', oid],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, check=False,
            )
            if raw.returncode != 0:
                self.error('wiki-blob', oid, raw.stderr.decode(errors='replace')[-1000:])
                continue
            self.inspect_blob(raw.stdout, f'wiki-git:{oid}', 'wiki_git_blob', None)
        self.counts['wiki_objects'] = objects
        self.counts['wiki_blobs'] = blobs
        fsck = run(['git', '--git-dir', str(wiki_dir), 'fsck', '--full', '--no-reflogs', '--unreachable'], timeout=600, check=False)
        self.wiki = {
            'result': 'PASS_WIKI_GIT_OBJECTS_SCANNED' if fsck.returncode in (0, 1) else 'HOLD_WIKI_FSCK_FAILED',
            'clone_returncode': cp.returncode,
            'refs': refs,
            'ref_count': len(refs),
            'objects': objects,
            'blobs': blobs,
            'blob_bytes': self.counts['wiki_blob_bytes'],
            'blob_skips': self.counts['wiki_blob_skips'],
            'fsck_returncode': fsck.returncode,
            'fsck_output': (fsck.stdout + '\n' + fsck.stderr)[-4000:],
        }
        if fsck.returncode not in (0, 1):
            self.error('wiki-fsck', url, fsck.stderr)
        shutil.rmtree(wiki_dir, ignore_errors=True)

    def finish(self) -> None:
        exact = sorted(self.exact_targets)
        new_exact = sorted(self.exact_targets - KNOWN_RETAINED)
        missing = sorted(set(TARGETS) - self.exact_targets)
        limits_hit = any(self.counts[key] for key in (
            'attachment_count_limit_skips', 'attachment_total_byte_limit_skips', 'wiki_blob_skips', 'zip_member_skips'
        ))
        api_complete = all(row['result'] == 'PASS' for row in self.api_calls)
        wiki_complete = self.wiki.get('result') in ('PASS_WIKI_REPOSITORY_ABSENT_OR_EMPTY', 'PASS_WIKI_GIT_OBJECTS_SCANNED')
        coverage_complete = api_complete and wiki_complete and not limits_hit and self.counts['errors'] == 0
        if set(TARGETS) <= self.exact_targets:
            result = 'PASS_COMPLETE_V31_TARGET_SET_RECOVERED_REQUIRES_EXISTING_V2_INTAKE'
        elif new_exact:
            result = 'PARTIAL_NEW_EXACT_V31_TARGET_BYTES_RECOVERED_REQUIRES_COMPLETE_SET_ASSEMBLY'
        elif coverage_complete:
            result = 'PASS_GITHUB_AUXILIARY_CUSTODY_SURFACES_SCANNED_NO_NEW_EXACT_V31_BYTES'
        else:
            result = 'HOLD_GITHUB_AUXILIARY_CUSTODY_SCAN_NO_NEW_EXACT_BYTES_WITH_COVERAGE_GAPS'
        ended = now()
        census = {
            'schema': 'manzanita/v31-github-auxiliary-custody-census@1',
            'repository': REPO,
            'started_at': self.started,
            'ended_at': ended,
            'result': result,
            'targets': {name: {'filenames': spec[0], 'bytes': spec[1], 'sha256': spec[2]} for name, spec in TARGETS.items()},
            'known_retained_targets_before_campaign': sorted(KNOWN_RETAINED),
            'exact_targets_observed_in_campaign': exact,
            'new_exact_targets_observed_in_campaign': new_exact,
            'missing_targets_after_campaign': missing,
            'counts': self.counts,
            'api_calls': self.api_calls,
            'wiki': self.wiki,
            'attachments': self.attachments,
            'hits': self.hits,
            'candidates': self.candidates,
            'references': self.references,
            'errors': self.errors,
            'coverage': {
                'complete_within_declared_scope': coverage_complete,
                'api_complete': api_complete,
                'wiki_complete': wiki_complete,
                'limits_hit': limits_hit,
                'scope': 'Public GitHub wiki Git object database plus GitHub-hosted attachment URLs present in issue/PR bodies, issue comments, inline pull-review comments, commit comments, and release bodies.',
                'exclusions': [
                    'deleted or inaccessible comments',
                    'expired Actions artifacts',
                    'File Library raw objects',
                    'private external storage',
                    'URLs not hosted on recognized GitHub attachment domains',
                ],
                'limits': {
                    'max_single_bytes': MAX_SINGLE,
                    'max_total_attachment_bytes': MAX_TOTAL,
                    'max_attachment_count': MAX_ATTACHMENTS,
                    'max_nested_archive_depth': MAX_DEPTH,
                },
            },
        }
        write_json(OUT / 'V31_GITHUB_AUXILIARY_CUSTODY_CENSUS_V1.json', census)
        receipt = {
            'schema': 'manzanita/v31-github-auxiliary-custody-receipt@1',
            'observed_at': ended,
            'result': result,
            'campaign': {
                'wiki_git_scan': self.wiki.get('result'),
                'issue_pr_attachment_graph': 'performed',
                'attachment_urls_observed': self.counts['attachment_urls'],
                'attachments_downloaded': self.counts['attachment_downloads'],
                'attachment_bytes_scanned': self.counts['attachment_download_bytes'],
                'coverage_complete': coverage_complete,
            },
            'findings': {
                'exact_targets_observed': exact,
                'new_exact_targets_observed': new_exact,
                'missing_targets': missing,
                'raw_public_convergence_members': [row for row in self.hits if row['target'] == 'public_convergence'],
            },
            'receiving': {
                'v2_intake_invoked': False,
                'reason': 'No complete newly assembled production input set was retained by this auxiliary-surface campaign.',
                'terminal_pair_retained': False,
            },
            'queue': {
                'controlling_state': 'V14_REMAINS_GOVERNED_HOLD',
                'advanced': False,
                'v15_created': False,
            },
            'authority': {
                'product_files_modified': 0,
                'merge_authorized': False,
                'release_authorized': False,
                'public_route_effect': 'none',
                'pages_effect': 'none',
                'external_effect': 'none',
            },
            'next_execution_item': {
                'class': 'RAW_FILE_LIBRARY_EXPORT_OR_EXACT_HISTORICAL_RUNTIME_SNAPSHOT',
                'preferred_target': 'mw-habitat-live-photo-020.zip',
                'admission_rule': 'Complete ordered bytes must independently match the registered size and SHA-256 before V2 intake.',
            },
        }
        write_json(OUT / 'V31_GITHUB_AUXILIARY_CUSTODY_RECEIPT_V1.json', receipt)
        summary = {
            'schema': 'manzanita/v31-github-auxiliary-custody-public-summary@1',
            'observed_at': ended,
            'result': result,
            'counts': self.counts,
            'wiki_result': self.wiki.get('result'),
            'exact_targets_observed': exact,
            'new_exact_targets_observed': new_exact,
            'coverage_complete': coverage_complete,
            'controlling_state': 'V14_REMAINS_GOVERNED_HOLD',
            'queue_advanced': False,
            'v15_created': False,
        }
        write_json(OUT / 'V31_GITHUB_AUXILIARY_CUSTODY_PUBLIC_SUMMARY_V1.json', summary)
        status = f'''# V31 GitHub auxiliary custody scan\n\nResult: `{result}`\n\nThe campaign scanned the public GitHub wiki object surface and the GitHub-hosted attachment graph reachable from issue and pull-request bodies, issue comments, inline review comments, commit comments, and release bodies. It observed {self.counts['attachment_urls']} unique attachment URL(s), downloaded {self.counts['attachment_downloads']} object(s) comprising {self.counts['attachment_download_bytes']} bytes, and scanned {self.counts['wiki_blobs']} wiki blob(s).\n\nNew exact V31 targets: {', '.join(new_exact) if new_exact else 'none'}. The controlling state remains `V14_REMAINS_GOVERNED_HOLD`; V2 intake was not invoked, the terminal pair was not retained, and no product, merge, release, route, Pages, or external effect was authorized.\n'''
        (OUT / 'V31_GITHUB_AUXILIARY_CUSTODY_V1_RELEASE_STATUS.md').write_text(status, encoding='utf-8')
        manifest_files = sorted(path for path in OUT.rglob('*') if path.is_file() and '_downloads' not in path.parts)
        manifest = {
            'schema': 'manzanita/v31-github-auxiliary-custody-artifact-manifest@1',
            'files': [
                {'path': path.relative_to(OUT).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha256(path.read_bytes())}
                for path in manifest_files
            ],
        }
        write_json(OUT / 'V31_GITHUB_AUXILIARY_CUSTODY_ARTIFACT_MANIFEST_V1.json', manifest)
        shutil.rmtree(self.download_dir, ignore_errors=True)
        print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    scan = Scan()
    urls = scan.collect_attachment_urls()
    scan.download_attachments(urls)
    scan.scan_wiki()
    scan.finish()


if __name__ == '__main__':
    main()

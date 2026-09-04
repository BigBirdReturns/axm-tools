"""Hostile witnesses for the deterministic, byte-addressed page product.

The committed `index.html` is rebuilt by every workflow leg and compared across
legs, so the build has to emit the same bytes on every admitted runtime. Two
things used to decide those bytes for it: the gzip container header, which
CPython 3.11 and 3.12 inherit from zlib and stamp with a platform OS byte, and
text-mode newline translation, which turns the same source into a different
tracked file on Windows. Both are owned by `render` now, and these witnesses
hold them there.
"""

from __future__ import annotations

import base64
import contextlib
import gzip
import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import render  # noqa: E402
from lab import command_main, page_identity  # noqa: E402
from planner import build_plan, read_json  # noqa: E402

PAGE = ROOT / "index.html"
FIXED_NOW = "2026-08-05T00:00:00Z"
PAYLOAD_RE = re.compile(
    r'<script id="embedded-data" type="application/octet-stream">([A-Za-z0-9+/=]+)</script>'
)


def committed_inputs() -> dict:
    data = ROOT / "data"
    estate = read_json(data / "estate.json")
    goals = read_json(data / "goals.json")
    experiments = read_json(data / "experiments.json")
    evidence = read_json(data / "evidence.json")
    return {
        "estate": estate,
        "goals": goals,
        "experiments": experiments,
        "evidence": evidence,
        "plan": build_plan(estate, goals, experiments, evidence, generated_at=FIXED_NOW),
    }


class CanonicalGzipTests(unittest.TestCase):
    def test_gzip_header_is_written_here_not_inherited_from_the_interpreter(self):
        """Fixed magic, method, flags, mtime, XFL, and OS byte on every runtime."""
        header = render.canonical_gzip(b"any payload at all")[:10]
        self.assertEqual(header, bytes.fromhex("1f8b08000000000002ff"))
        self.assertEqual(header[9], 255, "the OS byte must be 'unknown', never the build platform")
        self.assertEqual(header[4:8], (0).to_bytes(4, "little"), "mtime must be zero")
        self.assertEqual(header[8], 2, "XFL must record best compression")

    def test_interpreter_gzip_header_is_the_variable_this_replaces(self):
        """The regression this exists for: gzip.compress does not fix the header.

        On CPython 3.11 and 3.12 the OS byte is zlib's platform code; on 3.10
        and 3.13 it is 0xff. The canonical framing is 0xff on all of them, and
        the deflate body is identical either way, which is why the committed
        product bytes did not have to change.
        """
        raw = b"home-lab-gradient" * 500
        inherited = gzip.compress(raw, compresslevel=9, mtime=0)
        canonical = render.canonical_gzip(raw)
        self.assertEqual(inherited[10:-8], canonical[10:-8], "the deflate body is not the variable")
        self.assertEqual(canonical[9], 255)
        self.assertIn(inherited[9], (3, 10, 11, 255), "unexpected interpreter OS byte")

    def test_canonical_payload_round_trips_through_the_standard_gzip_reader(self):
        for raw in (b"", b"a", b"x" * 100000, json.dumps(committed_inputs()).encode("utf-8")):
            with self.subTest(size=len(raw)):
                framed = render.canonical_gzip(raw)
                self.assertEqual(gzip.decompress(framed), raw)
                self.assertEqual(zlib.decompress(framed, 31), raw)

    def test_compressor_fingerprint_is_the_behavioural_identity_of_the_deflater(self):
        self.assertEqual(render.compressor_fingerprint(), render.AUTHORITATIVE_COMPRESSOR_SHA256)
        self.assertEqual(render.compressor_fingerprint(), render.assert_authoritative_compressor())
        self.assertEqual(len(render.AUTHORITATIVE_COMPRESSOR_SHA256), 64)


class CommittedPageTests(unittest.TestCase):
    def test_committed_page_is_reproduced_byte_for_byte_on_this_runtime(self):
        rebuilt = render.build_page(**committed_inputs()).encode("utf-8")
        self.assertEqual(
            hashlib.sha256(rebuilt).hexdigest(),
            hashlib.sha256(PAGE.read_bytes()).hexdigest(),
            "this runtime does not reproduce the committed page bytes",
        )

    def test_committed_page_is_lf_only_and_bom_free(self):
        raw = PAGE.read_bytes()
        self.assertNotIn(b"\r", raw, "the product must carry LF on every platform")
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))

    def test_write_page_emits_lf_whatever_the_platform_newline_is(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "index.html"
            render.write_page(target, **committed_inputs())
            written = target.read_bytes()
        self.assertNotIn(b"\r", written)
        self.assertEqual(written, PAGE.read_bytes())

    def test_embedded_payload_decompresses_to_the_committed_plan(self):
        text = PAGE.read_bytes().decode("utf-8")
        match = PAYLOAD_RE.search(text)
        self.assertIsNotNone(match)
        embedded = json.loads(gzip.decompress(base64.b64decode(match.group(1))).decode("utf-8"))
        self.assertEqual(embedded["plan"], committed_inputs()["plan"])


class BuildRefusalTests(unittest.TestCase):
    def test_build_refuses_on_a_non_authoritative_compressor(self):
        """A runtime that cannot reproduce the product must not rewrite it."""
        before = PAGE.read_bytes()
        with mock.patch.object(render, "AUTHORITATIVE_COMPRESSOR_SHA256", "0" * 64):
            with self.assertRaises(render.RenderError) as raised:
                render.assert_authoritative_compressor()
            message = str(raised.exception)

            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = command_main(["build", "--now", FIXED_NOW])

        self.assertIn("not the authoritative page builder", message)
        self.assertIn(render.compressor_fingerprint(), message)
        self.assertEqual(code, 4, "a refused build must exit nonzero")
        self.assertIn("not the authoritative page builder", stderr.getvalue())
        self.assertEqual(PAGE.read_bytes(), before, "a refused build rewrote the tracked product")

    def test_page_identity_reports_the_committed_product(self):
        identity = page_identity()["identity"]
        raw = PAGE.read_bytes()
        self.assertEqual(identity["page_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(identity["page_bytes"], len(raw))
        self.assertIs(identity["page_carries_cr"], False)
        self.assertEqual(identity["compressor_fingerprint"], render.AUTHORITATIVE_COMPRESSOR_SHA256)
        self.assertEqual(
            identity["authoritative_compressor_fingerprint"], render.AUTHORITATIVE_COMPRESSOR_SHA256
        )
        payload = base64.b64decode(PAYLOAD_RE.search(raw.decode("utf-8")).group(1))
        self.assertEqual(identity["payload_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(
            identity["embedded_sha256"], hashlib.sha256(gzip.decompress(payload)).hexdigest()
        )


if __name__ == "__main__":
    unittest.main()

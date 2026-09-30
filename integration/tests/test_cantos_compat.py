"""Exercise compatibility staging against real temporary Git trees."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from integration import cantos_compat as compat


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


class CantosCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        base = os.environ.get("AXM_COMPAT_TEST_TMP")
        if base:
            Path(base).mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        self.repo = self.root / "axm"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Cantos compatibility test")
        git(self.repo, "config", "user.email", "compat-test@example.invalid")
        git(self.repo, "config", "core.autocrlf", "false")
        self.binary = bytes(range(256)) + b"\x00legacy\xff\n"
        files = {
            **{f"{root}/index.html": f"<html>historical {root}</html>\n".encode() for root in compat.ROOTS},
            "research-desk/app.html": b"<html>offline app</html>\n",
            "compute/compute-kit.zip": self.binary,
        }
        self.old_files = files
        for name, body in files.items():
            path = self.repo / Path(*name.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        git(self.repo, "add", "--all")
        git(self.repo, "commit", "-m", "historical source")
        self.source = git(self.repo, "rev-parse", "HEAD")

        # Simulate the migration commit: the six kept aliases are present,
        # historical deep files are absent, and shelf/index.html was dropped.
        for root in (root for root in compat.ROOTS if root != "shelf"):
            alias = self.repo / root / "index.html"
            alias.write_text(
                '<title>Moved to Cantos</title><meta http-equiv="refresh" '
                f'content="0; url={compat.CANTOS_BASE}{root}/">\n',
                encoding="utf-8",
            )
        (self.repo / "research-desk" / "app.html").unlink()
        (self.repo / "compute" / "compute-kit.zip").unlink()
        (self.repo / "shelf" / "index.html").unlink()
        git(self.repo, "add", "--all")
        git(self.repo, "commit", "-m", "migration")

        # A second real Git repository supplies the exact Cantos path mapping.
        self.cantos = self.root / "cantos"
        self.cantos.mkdir()
        git(self.cantos, "init", "-b", "main")
        git(self.cantos, "config", "user.name", "Cantos compatibility test")
        git(self.cantos, "config", "user.email", "compat-test@example.invalid")
        git(self.cantos, "config", "core.autocrlf", "false")
        for name in files:
            path = self.cantos / Path(*name.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"destination exists\n")
        git(self.cantos, "add", "--all")
        git(self.cantos, "commit", "-m", "destination tree")
        # This unit fixture uses a hand-built local snapshot because it has no
        # network remote; production `--cantos-repo` validates the remote URL.
        entries = compat._tree(self.cantos, "HEAD", compat.ROOTS)
        self.destination = compat.DestinationSnapshot(
            commit=git(self.cantos, "rev-parse", "HEAD"),
            tree_sha=git(self.cantos, "rev-parse", "HEAD^{tree}"),
            entries=entries,
            source="test Git tree",
        )
        self.output = self.root / "stage"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_stage(self, destination=None):
        return compat.stage_compat(
            self.repo, self.output, self.source,
            destination or self.destination,
        )

    def test_html_deep_route_redirect_preserves_query_and_fragment(self) -> None:
        document = compat.redirect_document("research-desk/app.html").decode("utf-8")
        target = "https://bigbirdreturns.github.io/cantos/research-desk/app.html"
        self.assertIn(target, document)
        self.assertIn("window.location.search + window.location.hash", document)
        self.assertIn("rel=\"canonical\"", document)
        self.assertIn("href=\"" + target + "\"", document)

        self.run_stage()
        staged = (self.output / "research-desk" / "app.html").read_text(encoding="utf-8")
        self.assertIn("window.location.search + window.location.hash", staged)

    def test_non_html_route_retains_exact_historical_bytes(self) -> None:
        self.run_stage()
        target = self.output / "compute" / "compute-kit.zip"
        self.assertEqual(target.read_bytes(), self.binary)

    def test_root_aliases_are_installed_and_known_aliases_are_refreshed(self) -> None:
        result = self.run_stage()
        self.assertEqual(result["redirect_count"], 8)
        self.assertTrue((self.output / "shelf" / "index.html").is_file())
        self.assertIn(
            "window.location.search + window.location.hash",
            (self.output / "compute" / "index.html").read_text(encoding="utf-8"),
        )

    def test_source_tree_has_all_seven_root_aliases(self) -> None:
        repo = Path(compat.__file__).resolve().parents[1]
        for route in compat.ROOT_ALIASES:
            with self.subTest(route=route):
                page = repo.joinpath(*route.split("/"))
                self.assertTrue(page.is_file())
                self.assertEqual(
                    page.read_text(encoding="utf-8"),
                    compat.redirect_document(route).decode("utf-8"),
                )

    def test_partial_rerun_is_idempotent(self) -> None:
        self.output.mkdir()
        preexisting_html = self.output / "research-desk" / "app.html"
        preexisting_html.parent.mkdir(parents=True)
        preexisting_html.write_bytes(compat.redirect_document("research-desk/app.html"))
        preexisting_binary = self.output / "compute" / "compute-kit.zip"
        preexisting_binary.parent.mkdir(parents=True)
        preexisting_binary.write_bytes(self.binary)
        first = self.run_stage()
        before = {
            path.relative_to(self.output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.output.rglob("*") if path.is_file()
        }
        second = self.run_stage()
        after = {
            path.relative_to(self.output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.output.rglob("*") if path.is_file()
        }
        self.assertEqual(first["newly_written_path_count"], 7)
        self.assertEqual(first["already_staged_path_count"], 2)
        self.assertEqual(second["newly_written_path_count"], 0)
        self.assertEqual(before, after)

    def test_manifest_can_be_reused_on_an_idempotent_rerun(self) -> None:
        manifest = self.root / "compat-manifest.json"
        compat.stage_compat(self.repo, self.output, self.source, self.destination, manifest)
        first = manifest.read_bytes()
        compat.stage_compat(self.repo, self.output, self.source, self.destination, manifest)
        self.assertEqual(manifest.read_bytes(), first)
        self.assertNotIn(b"newly_written_path_count", first)
        record = json.loads(first)
        self.assertEqual(record["historical_route_count"], 9)
        self.assertEqual(len(record["routes"]), 9)

    def test_existing_unrelated_file_is_never_overwritten(self) -> None:
        self.output.mkdir()
        target = self.output / "compute" / "compute-kit.zip"
        target.parent.mkdir()
        target.write_bytes(b"user file")
        with self.assertRaisesRegex(compat.CompatError, "Refusing to overwrite"):
            self.run_stage()
        self.assertEqual(target.read_bytes(), b"user file")

    def test_unresolved_destination_fails_before_writing(self) -> None:
        missing = dict(self.destination.entries)
        del missing["research-desk/app.html"]
        unresolved = compat.DestinationSnapshot(
            self.destination.commit, self.destination.tree_sha, missing, "incomplete test tree"
        )
        with self.assertRaisesRegex(compat.CompatError, "destination is missing"):
            self.run_stage(unresolved)
        self.assertFalse(self.output.exists())

    def test_source_and_destination_git_symlinks_are_refused(self) -> None:
        linked_entries = dict(self.destination.entries)
        app = linked_entries["research-desk/app.html"]
        linked_entries[app.path] = compat.TreeEntry(
            app.path, "120000", "blob", app.sha, app.size
        )
        linked_destination = compat.DestinationSnapshot(
            self.destination.commit, self.destination.tree_sha,
            linked_entries, "symlink destination fixture",
        )
        with self.assertRaisesRegex(compat.CompatError, "destination route is a symlink"):
            self.run_stage(linked_destination)
        self.assertFalse(self.output.exists())

        # Git can record a symlink mode without requiring Windows symlink
        # privileges by setting the temporary repository index directly.
        git(self.repo, "checkout", "--detach", self.source)
        payload = b"outside-target"
        result = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"], cwd=self.repo,
            input=payload, check=True, stdout=subprocess.PIPE,
        )
        blob = result.stdout.decode("ascii").strip()
        git(self.repo, "update-index", "--cacheinfo", f"120000,{blob},compute/compute-kit.zip")
        git(self.repo, "commit", "-m", "temporary symlink mode fixture")
        link_source = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaisesRegex(compat.CompatError, "Historical route is a symlink"):
            compat.stage_compat(self.repo, self.output, link_source, self.destination)
        self.assertFalse(self.output.exists())

    def test_unsafe_and_traversal_paths_are_refused(self) -> None:
        for path in ("../compute/file.bin", "/compute/file.bin", "compute\\file.bin", "other/file.bin"):
            with self.subTest(path=path), self.assertRaises(compat.CompatError):
                compat.validate_path(path)

    def test_symlink_parent_is_refused(self) -> None:
        self.output.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        link = self.output / "research-desk"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Directory symlinks are unavailable: {exc}")
        with self.assertRaisesRegex(compat.CompatError, "symlink directory"):
            self.run_stage()
        self.assertEqual(list(outside.iterdir()), [])

    def test_every_pages_publisher_tests_gates_stages_and_fetches_history(self) -> None:
        repo = Path(compat.__file__).resolve().parents[1]
        native_test = "python -B -m unittest integration.tests.test_cantos_compat -v"
        for workflow in compat.PUBLISHERS:
            path = repo / ".github" / "workflows" / workflow
            source = path.read_text(encoding="utf-8")
            with self.subTest(workflow=workflow):
                test_at = source.index(native_test)
                gate_at = source.index("integration/release_gate.py --timeout")
                stage_at = source.index("integration/cantos_compat.py stage")
                upload_at = source.index("actions/upload-pages-artifact")
                receipt_at = source.rfind("actions/upload-artifact@v4", stage_at, upload_at)
                self.assertLess(test_at, gate_at)
                self.assertLess(gate_at, stage_at)
                self.assertLess(stage_at, receipt_at)
                self.assertLess(receipt_at, upload_at)
                stage_begin = source.rfind("      - name: Stage historical Cantos compatibility routes", 0, stage_at)
                stage_and_receipt = source[stage_begin:upload_at]
                self.assertIn("GH_TOKEN: ${{ github.token }}", stage_and_receipt)
                self.assertIn("name: cantos-compat-${{ github.run_id }}-${{ github.run_attempt }}", stage_and_receipt)
                self.assertIn("path: ${{ runner.temp }}/cantos-compat-manifest.json", stage_and_receipt)
                self.assertIn("if-no-files-found: error", stage_and_receipt)
                self.assertIn("retention-days: 30", stage_and_receipt)
                checkout_at = source.rfind("actions/checkout", 0, stage_at)
                fetch_depth_at = source.find("fetch-depth: 0", checkout_at, stage_at)
                self.assertGreaterEqual(checkout_at, 0)
                self.assertGreaterEqual(fetch_depth_at, checkout_at)


if __name__ == "__main__":
    unittest.main()

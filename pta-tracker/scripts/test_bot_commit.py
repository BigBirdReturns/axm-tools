#!/usr/bin/env python3
"""Replays pta-fetch.yml's bot commits against main moving under the run.

Each test drives the shell of the real workflow steps, read out of the YAML,
through real git against a local bare repo standing in for GitHub. A copy of
the steps here could pass while the workflow stayed broken.

    python -B pta-tracker/scripts/test_bot_commit.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/pta-fetch.yml"
HELPER = "pta-tracker/scripts/bot_commit.py"
COMMIT_STEP = "Commit updated data"
RECEIPT_STEP = "Record successful Pages deployment"
DATA_SUBJECT = "pta-tracker: nightly data refresh"
RECEIPT_SUBJECT = "pages: record successful deployment"
STALE = "2026-11-01T00:00:00.000000Z"
FRESH = "2026-11-06T12:30:00.000000Z"


def step_script(name):
    """The exact shell the named pta-fetch.yml step runs."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"      - name: {name}")
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    body = []
    for line in lines[run + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) < 10:
            break
        body.append(line[10:])
    return "\n".join(body) + "\n"


def git(cwd, *args, check=True):
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    if check and done.returncode:
        raise AssertionError(f"git {' '.join(args)}: {done.stdout}{done.stderr}")
    return done.stdout.strip()


def write_json(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


class Runner:
    """One Actions job: a clone of main that runs the workflow's own steps."""

    def __init__(self, base, origin, name, event="push"):
        self.path = base / name
        self.base, self.event = base, event
        git(base, "clone", "-q", "--branch", "main", str(origin), str(self.path))
        git(self.path, "config", "user.name", "test")
        git(self.path, "config", "user.email", "test@example.test")
        self.sha = git(self.path, "rev-parse", "HEAD")

    def refresh(self, title=None):
        """What fetch.py leaves behind: new stamps, plus an item if the feed moved."""
        data = self.path / "pta-tracker/data"
        items = json.loads((data / "items.json").read_text(encoding="utf-8"))
        derived = json.loads((data / "derived.json").read_text(encoding="utf-8"))
        gaps = json.loads((data / "gaps.json").read_text(encoding="utf-8"))
        items["generated"] = derived["generated"] = gaps["checked"] = FRESH
        if title:
            items["items"].insert(0, {"id": title, "title": title})
        write_json(data / "items.json", items)
        write_json(data / "derived.json", derived)
        write_json(data / "gaps.json", gaps)

    def step(self, name, *, script=None):
        path = self.base / f"step-{self.path.name}-{name.split()[0]}.sh"
        path.write_text(script or step_script(name), encoding="utf-8", newline="\n")
        env = {
            **os.environ,
            "GITHUB_EVENT_NAME": self.event,
            "GITHUB_SHA": self.sha,
            "GITHUB_RUN_ID": "1",
            "GITHUB_RUN_ATTEMPT": "1",
            "PAGE_URL": "https://example.test/",
            "SCHOOLS_BUILT": "success",
        }
        return subprocess.run(
            ["bash", "-e", str(path)],
            cwd=self.path,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def dirty_like_the_pages_steps(self):
        """The receipt step runs after staging wrote into the checkout."""
        (self.path / "index.html").write_text("rewritten in place\n", encoding="utf-8")
        (self.path / "staged-route").mkdir()
        (self.path / "staged-route/index.html").write_text("x\n", encoding="utf-8")


class BotCommitTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.origin = self.base / "origin.git"
        git(self.base, "init", "-q", "--bare", "-b", "main", str(self.origin))
        seed = self.base / "seed"
        git(self.base, "init", "-q", "-b", "main", str(seed))
        data = seed / "pta-tracker/data"
        write_json(data / "items.json", {"generated": STALE, "sources": [], "items": []})
        write_json(data / "derived.json", {"generated": STALE, "coming_up": []})
        write_json(data / "gaps.json", {"checked": STALE, "reviewed": 0, "gaps": []})
        write_json(data / "archive.json", {"items": []})
        write_json(seed / ".github/pages-deployment.json", {"source_sha": "seed"})
        write_json(seed / "team-commons/manifest.json", {})
        for path in (
            "index.html",
            "README.md",
            "identity/axm/PROPERTY-FLAVORS.md",
            "team-commons/downloads/kit.zip",
            "pta-tracker/holly-avenue/index.html",
        ):
            (seed / path).parent.mkdir(parents=True, exist_ok=True)
            (seed / path).write_text("seed\n", encoding="utf-8")
        (seed / HELPER).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / HELPER, seed / HELPER)
        git(seed, "add", "-A")
        git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed")
        git(seed, "push", "-q", str(self.origin), "main")
        self.human = Runner(self.base, self.origin, "human")

    def merge(self, name):
        """A human merge landing on main while a run is in flight."""
        git(self.human.path, "pull", "-q", "--rebase", "origin", "main")
        (self.human.path / f"{name}.txt").write_text(name, encoding="utf-8")
        git(self.human.path, "add", "-A")
        git(self.human.path, "commit", "-qm", name)
        git(self.human.path, "push", "-q", "origin", "HEAD:main")

    def log(self):
        return git(self.origin, "log", "--format=%s", "main").splitlines()

    def show(self, path):
        return git(self.origin, "show", f"main:{path}")

    def assertStep(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_control_a_bare_push_is_the_reported_failure(self):
        """Proves the harness reproduces the fault the rest of the file fixes."""
        run = Runner(self.base, self.origin, "run")
        run.refresh("new item")
        self.merge("merged-during-run")
        script = step_script(COMMIT_STEP).replace(
            f"python -B {HELPER} land", "git push"
        )
        result = run.step(COMMIT_STEP, script=script)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rejected", result.stderr)
        self.assertNotIn(DATA_SUBJECT, self.log())

    def test_steps_have_no_bare_push_left(self):
        for name in (COMMIT_STEP, RECEIPT_STEP):
            lines = step_script(name).splitlines()
            commands = [line for line in lines if not line.lstrip().startswith("#")]
            self.assertFalse([line for line in commands if "git push" in line])

    def test_data_commit_survives_a_merge_during_the_run(self):
        run = Runner(self.base, self.origin, "run")
        run.refresh("new item")
        self.merge("merged-during-run")
        self.assertStep(run.step(COMMIT_STEP))
        self.assertEqual(self.log()[:2], [DATA_SUBJECT, "merged-during-run"])
        self.assertEqual(json.loads(self.show("pta-tracker/data/items.json"))["generated"], FRESH)
        self.assertEqual(git(run.path, "rev-parse", "HEAD"), git(self.origin, "rev-parse", "main"))

    def test_receipt_survives_a_merge_after_deploy_on_a_dirty_tree(self):
        run = Runner(self.base, self.origin, "run")
        run.refresh("new item")
        self.assertStep(run.step(COMMIT_STEP))
        run.dirty_like_the_pages_steps()
        self.merge("merged-after-deploy")
        self.assertStep(run.step(RECEIPT_STEP))
        self.assertEqual(
            self.log()[:3], [RECEIPT_SUBJECT, "merged-after-deploy", DATA_SUBJECT]
        )
        self.assertEqual(
            json.loads(self.show(".github/pages-deployment.json"))["source_sha"], run.sha
        )

    def test_push_run_with_only_new_stamps_commits_just_the_receipt(self):
        run = Runner(self.base, self.origin, "run")
        run.refresh()
        self.assertStep(run.step(COMMIT_STEP))
        self.merge("merged-during-run")
        run.dirty_like_the_pages_steps()
        self.assertStep(run.step(RECEIPT_STEP))
        self.assertEqual(self.log()[:2], [RECEIPT_SUBJECT, "merged-during-run"])
        self.assertNotIn(DATA_SUBJECT, self.log())
        self.assertEqual(
            git(self.origin, "show", "--format=", "--name-only", "main"),
            ".github/pages-deployment.json",
        )
        self.assertEqual(json.loads(self.show("pta-tracker/data/items.json"))["generated"], STALE)

    def test_nightly_run_still_commits_a_bare_refresh(self):
        """The page raises its stale alert off items.json `generated`, and a
        clean-checkout redeploy only has what is committed."""
        run = Runner(self.base, self.origin, "run", event="schedule")
        run.refresh()
        self.assertStep(run.step(COMMIT_STEP))
        self.assertEqual(self.log()[0], DATA_SUBJECT)
        for path, key in (("items", "generated"), ("derived", "generated"), ("gaps", "checked")):
            self.assertEqual(json.loads(self.show(f"pta-tracker/data/{path}.json"))[key], FRESH)

    def test_push_run_with_new_content_commits_all_of_it(self):
        run = Runner(self.base, self.origin, "run")
        run.refresh("new item")
        self.assertStep(run.step(COMMIT_STEP))
        self.assertEqual(self.log()[0], DATA_SUBJECT)
        self.assertEqual(json.loads(self.show("pta-tracker/data/gaps.json"))["checked"], FRESH)

    def test_run_behind_another_runs_data_commit_keeps_its_own_output(self):
        """Both commits rewrite the same stamp lines, so a plain rebase stops."""
        behind = Runner(self.base, self.origin, "behind")
        behind.refresh("from the later run")
        ahead = Runner(self.base, self.origin, "ahead")
        ahead.refresh("from the earlier run")
        self.assertStep(ahead.step(COMMIT_STEP))
        self.assertStep(behind.step(COMMIT_STEP))
        items = json.loads(self.show("pta-tracker/data/items.json"))
        self.assertEqual(items["items"][0]["title"], "from the later run")

    def test_two_pushes_in_quick_succession(self):
        """The reported burst: merges keep landing while runs commit and push."""
        first = Runner(self.base, self.origin, "first")
        second = Runner(self.base, self.origin, "second")
        first.refresh("first item")
        second.refresh("second item")
        results = {}

        def job(run):
            results[run.path.name, "data"] = run.step(COMMIT_STEP)
            run.dirty_like_the_pages_steps()
            results[run.path.name, "receipt"] = run.step(RECEIPT_STEP)

        def burst():
            for n in range(4):
                self.merge(f"burst-{n}")

        threads = [
            threading.Thread(target=job, args=(first,)),
            threading.Thread(target=job, args=(second,)),
            threading.Thread(target=burst),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for result in results.values():
            self.assertStep(result)
        log = self.log()
        self.assertEqual(log.count(RECEIPT_SUBJECT), 2)
        for n in range(4):
            self.assertIn(f"burst-{n}", log)
        self.assertEqual(git(self.origin, "log", "--merges", "--oneline", "main"), "")
        json.loads(self.show("pta-tracker/data/items.json"))
        json.loads(self.show(".github/pages-deployment.json"))

    def land(self, run, *flags):
        return subprocess.run(
            [sys.executable, "-B", HELPER, "land", *flags],
            cwd=run.path,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_gives_up_loudly_after_its_attempts(self):
        run = Runner(self.base, self.origin, "run")
        hook = self.origin / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        (run.path / "x.txt").write_text("x", encoding="utf-8")
        git(run.path, "add", "-A")
        git(run.path, "commit", "-qm", "bot commit")
        result = self.land(run, "--attempts", "2", "--pause", "0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error", result.stdout)

    def test_unresolvable_conflict_stops_the_run_and_restores_the_tree(self):
        run = Runner(self.base, self.origin, "run")
        git(self.human.path, "rm", "-q", "README.md")
        git(self.human.path, "commit", "-qm", "human deleted it")
        git(self.human.path, "push", "-q", "origin", "HEAD:main")
        (run.path / "README.md").write_text("bot edit\n", encoding="utf-8")
        git(run.path, "add", "-A")
        git(run.path, "commit", "-qm", "bot commit")
        result = self.land(run, "--pause", "0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error", result.stdout)
        self.assertEqual(git(run.path, "status", "--porcelain"), "")
        self.assertEqual(self.log()[0], "human deleted it")

    def stamp_only(self, run):
        done = subprocess.run(
            [sys.executable, "-B", HELPER, "stamp-only"], cwd=run.path, capture_output=True
        )
        return done.returncode == 0

    def test_stamp_only_refuses_everything_but_bare_stamps(self):
        run = Runner(self.base, self.origin, "run")
        self.assertFalse(self.stamp_only(run), "nothing staged")
        run.refresh()
        git(run.path, "add", "pta-tracker/data")
        self.assertTrue(self.stamp_only(run))
        (run.path / "team-commons/downloads/kit.zip").write_bytes(b"\0binary")
        git(run.path, "add", "team-commons/downloads")
        self.assertFalse(self.stamp_only(run), "a binary file rode along")
        git(run.path, "reset", "-q", "team-commons/downloads")
        write_json(run.path / "pta-tracker/data/gaps.json", {"checked": FRESH, "reviewed": 9, "gaps": []})
        git(run.path, "add", "pta-tracker/data")
        self.assertFalse(self.stamp_only(run), "a real field moved")
        (run.path / "pta-tracker/data/gaps.json").write_text("{not json", encoding="utf-8")
        git(run.path, "add", "pta-tracker/data")
        self.assertFalse(self.stamp_only(run), "unreadable counts as a change")


if __name__ == "__main__":
    unittest.main()

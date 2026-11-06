#!/usr/bin/env python3
"""Git steps for the bot commits in .github/workflows/pta-fetch.yml.

    bot_commit.py stamp-only   exit 0 if everything staged is just the refresh
                               timestamps, nonzero otherwise
    bot_commit.py land         push HEAD to main, replaying it onto whatever
                               main became while this run was working

Why this exists: a run spends a minute or more between its checkout and its
pushes, and main does not hold still for it. Human merges arrive in bursts,
and the release workflows (decision-floor, estate-action-study, knowledge-pack)
push to main about 30 seconds after the same merge that started this workflow.
A bare `git push` is then rejected, which fails the run and, at the data step,
skips that run's Pages deploy. See the 6 November 2026 entry in CLAUDE.md.
"""

import argparse
import json
import random
import subprocess
import sys
import time

# Every data file fetch.py rewrites each run, and the one top-level key that
# moves on every run even when nothing in the feeds changed. All three have to
# be listed: items.json alone is enough to make every run look like new data.
STAMPS = {
    "pta-tracker/data/items.json": "generated",
    "pta-tracker/data/derived.json": "generated",
    "pta-tracker/data/gaps.json": "checked",
}


def git(*args, check=True):
    return subprocess.run(
        ["git", *args], check=check, capture_output=True, text=True, encoding="utf-8"
    )


def _without_stamp(rev, path):
    doc = json.loads(git("show", f"{rev}:{path}").stdout)
    doc.pop(STAMPS[path], None)
    return doc


def stamp_only():
    """True when the index differs from HEAD only by the STAMPS timestamps.

    Compares parsed JSON rather than diff lines so a binary file or a reordered
    key can't pass as "nothing changed". Anything it can't read counts as a real
    change: the safe mistake is one extra commit, not a lost data refresh.
    """
    staged = git("diff", "--cached", "--name-only", "-z").stdout.split("\0")
    staged = [path for path in staged if path]
    try:
        return bool(staged) and all(
            path in STAMPS and _without_stamp("HEAD", path) == _without_stamp("", path)
            for path in staged
        )
    except (subprocess.CalledProcessError, ValueError):
        return False


def land(attempts=6, pause=2.0):
    """Push HEAD to main, rebasing onto the new main after each rejection.

    --autostash because the tree is dirty by design: the data step leaves
    unstaged stamps behind, and the receipt step runs after the Pages staging
    steps have written into the checkout. -X theirs because in a rebase "theirs"
    is the commit being replayed, so where this run and main edited the same
    lines, this run's freshly generated output wins. A conflict that can't be
    settled that way (a file deleted on one side) stops the run, loudly.
    """
    for attempt in range(1, attempts + 1):
        push = git("push", "origin", "HEAD:main", check=False)
        if push.returncode == 0:
            print(f"landed on main, attempt {attempt}")
            return 0
        print(push.stderr, end="", file=sys.stderr)
        if attempt == attempts:
            break
        # jittered so two writers that collided don't collide again in step
        time.sleep(pause * attempt + random.uniform(0, pause))
        if git("fetch", "--no-tags", "origin", "main", check=False).returncode:
            continue
        rebase = git("rebase", "--autostash", "-X", "theirs", "FETCH_HEAD", check=False)
        if rebase.returncode:
            print(rebase.stdout + rebase.stderr, end="", file=sys.stderr)
            git("rebase", "--abort", check=False)
            print("::error title=Bot commit not landed::could not rebase onto main")
            return 1
    print(f"::error title=Bot commit not landed::push rejected {attempts} times")
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("stamp-only")
    landing = commands.add_parser("land")
    landing.add_argument("--attempts", type=int, default=6)
    landing.add_argument("--pause", type=float, default=2.0)
    args = parser.parse_args(argv)
    if args.command == "stamp-only":
        return 0 if stamp_only() else 1
    return land(args.attempts, args.pause)


if __name__ == "__main__":
    sys.exit(main())

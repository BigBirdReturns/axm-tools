"""Replay the public six-task Second Run case against a pinned Cantos checkout."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


REVISION = "0c9594b4d0c302e5b6da41f32fb983256c0e1391"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="Clean Git checkout of the public Cantos source")
    parser.add_argument("--output", type=Path, default=Path.cwd(), help="Parent for a new result directory")
    args = parser.parse_args()
    repo = args.checkout.resolve()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=repo)
    if revision != REVISION or dirty:
        parser.error("Use a clean Cantos checkout at " + REVISION)
    example = repo / "integration" / "examples" / "work.json"
    request = json.loads(example.read_bytes())
    for task in request["tasks"]:
        task["source"] = str((example.parent / task["source"]).resolve())

    args.output.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="second-run-", dir=args.output.resolve()))
    print("Results:", output, flush=True)
    baseline = {}
    for index, stage in enumerate(("first-run", "same-work", "changed-price")):
        if stage == "changed-price":
            request["tasks"][0]["price_scenario"] = {"rate_usd_per_gpu_hour": 2.0}
        request_path = output / (stage + "-request.json")
        request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
        run = subprocess.run([sys.executable, "-B", str(repo / "integration/work.py"),
                              "--request", str(request_path), "--store", str(output / "store")],
                             cwd=repo, stdout=subprocess.PIPE)
        if not run.stdout:
            raise SystemExit(run.returncode or "Runner returned no receipt")
        receipt = json.loads(run.stdout)
        print(stage, json.dumps(receipt["summary"]), receipt["receipt"], flush=True)
        if run.returncode:
            for row in receipt["tasks"]:
                if row["status"] == "held":
                    print(row["id"], row["reason"], file=sys.stderr)
            raise SystemExit(run.returncode)
        expected = (6, 0, 1)[index]
        if receipt["summary"] != {"executed": expected, "reused": 6 - expected, "held": 0}:
            raise SystemExit("Receipt counts differ from the reference case")
        for row in receipt["tasks"]:
            identity = row["key"], row["value_sha256"]
            if index == 0:
                baseline[row["id"]] = identity
                continue
            changed = stage == "changed-price" and row["id"] == "latitude-offer"
            expected_status = "executed" if changed else "reused"
            if row["status"] != expected_status or ((identity == baseline[row["id"]]) == changed):
                raise SystemExit("Unexpected task identity or status: " + row["id"])
    print("Verified all three receipts. Inspect their task records and result paths above.")


if __name__ == "__main__":
    main()

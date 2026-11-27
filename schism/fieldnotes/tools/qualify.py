#!/usr/bin/env python3
"""Exercise Fieldnotes through the public launcher, SCHISM CLI and loopback HTTP."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
CASES = []


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def passed(name):
    CASES.append({"case": name, "status": "PASS"})
    print("PASS " + name, flush=True)


def http(path, token=None, data=None, headers=None, expect=200):
    head = dict(headers or {})
    if token:
        head["Authorization"] = "Bearer " + token
    body = None
    if data is not None:
        head["Content-Type"] = "application/json"
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:8787" + path, data=body, headers=head)
    try:
        response = OPENER.open(request, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read()
        require(response.status == expect, f"HTTP {path}: expected {expect}, observed {response.status}; {raw[:240]!r}")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schism", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--wheelhouse", type=Path)
    args = parser.parse_args()
    schism = args.schism.expanduser().resolve()
    work = args.work.expanduser().resolve() if args.work else Path(tempfile.mkdtemp(prefix="fieldnotes-acceptance-"))
    work.mkdir(parents=True, exist_ok=False) if args.work else None
    runtime = (args.runtime or work / "runtime").resolve()
    first, second = work / "first-operator", work / "second-operator"
    log = work / "private-command-output.txt"
    report = {"schema": "fieldnotes.qualification/v1", "application_versions": ["1.0.0", "1.1.0"], "controller": "0.1.1",
              "host": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "python": platform.python_version()},
              "surface": "Public launcher and command line plus real loopback HTTP; browser interaction and reboot recovery are outside this receipt.",
              "cases": CASES, "status": "FAIL"}
    launcher = [sys.executable, str(ROOT / "open-fieldnotes.py"), "--schism", str(schism), "--runtime", str(runtime), "--no-browser"]
    if args.wheelhouse:
        launcher.extend(["--wheelhouse", str(args.wheelhouse.resolve())])
    if schism.is_dir() and (schism / "schism.py").exists():
        prefix = [str(runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")), str(schism / "schism.py")]
    else:
        native = schism / ("schism.exe" if os.name == "nt" else "schism") if schism.is_dir() else schism
        prefix = [str(native)]

    def run(command, succeeds=True):
        result = subprocess.run([str(p) for p in command], capture_output=True, text=True, encoding="utf-8", timeout=240)
        with log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps([str(p) for p in command]) + "\n" + result.stdout + "\n" + result.stderr + "\n")
        require((result.returncode == 0) == succeeds, "Command result disagrees with expectation: " + (result.stderr or result.stdout)[-1400:])
        return result

    def cli(state, *args_, succeeds=True):
        result = run([*prefix, "--state", state, *args_], succeeds=succeeds)
        return json.loads(result.stdout) if result.stdout.strip() else json.loads(result.stderr)

    def app(state):
        return next((row for row in cli(state, "status")["applications"] if row["id"] == "fieldnotes"), None)

    def session(state):
        selected = app(state)
        value = json.loads((state / "work" / "fieldnotes" / selected["run_id"] / "fieldnotes-open.json").read_text(encoding="utf-8"))
        return value["token"]

    def notebook(token):
        return json.loads(http("/api/notebook", token))

    try:
        with socket.socket() as sock:
            require(sock.connect_ex(("127.0.0.1", 8787)) != 0, "Port 8787 already serves another application; qualification stopped without touching it.")
        run([*launcher, "--state", first, "--app-version", "1.0.0"])
        first_identity = cli(first, "identity")
        first_key = first_identity["key_id"]
        first_app = app(first)
        require(first_app["status"] == "running" and first_app["version"] == "1.0.0", "Initial application did not start")
        token = session(first)
        require(notebook(token)["notes"] == [], "Fresh notebook must start empty")
        passed("Public launcher self-packs, imports and starts an empty notebook under the operator's own identity")
        http("/api/notebook", expect=403)
        http("/api/notebook", token, headers={"Origin": "https://foreign.example"}, expect=403)
        http("/api/notebook", token, headers={"Host": "foreign.example"}, expect=403)
        http("/api/notebook", token, headers={"Sec-Fetch-Site": "cross-site"}, expect=403)
        passed("Notebook reads refuse missing tokens, foreign origins, hostile Host and cross-site metadata")
        draft = {"id": None, "revision": 0, "title": "Workshop repair log", "body": "Replaced the workbench hinge.\nPart: M6 × 20 mm\nNext inspection: December.\nRésumé 日本語 <script>literal text only</script>", "tags": ["workshop", "repairs"], "archived": False, "pinned": False}
        http("/api/notes", token, draft, {"Origin": "https://foreign.example"}, expect=403)
        note = json.loads(http("/api/notes", token, draft))["note"]
        require(note["revision"] == 1 and note["body"] == draft["body"], "Note creation changed input")
        passed("Create a real Unicode note; foreign-origin mutations are refused")
        old_note = dict(note)
        note["body"] += "\nPhotographs are in the local project folder."
        note = json.loads(http("/api/notes", token, note))["note"]
        http("/api/notes", token, old_note, expect=409)
        require(notebook(token)["notes"][0] == note, "Stale save replaced the current revision")
        passed("Editing advances the revision; stale writes preserve the newer saved note")
        note_path = first / "data" / "fieldnotes" / "notes" / (note["id"] + ".json")
        require(json.loads(note_path.read_text(encoding="utf-8")) == note, "Portable data file differs from UI data")
        passed("Saved notes are ordinary UTF-8 JSON with the documented fields")
        raw_text = http("/api/text?id=" + note["id"], token)
        require(raw_text.decode("utf-8") == note["title"] + "\n\n" + note["body"], "Text export changed content")
        with zipfile.ZipFile(io.BytesIO(http("/api/export", token))) as archive:
            require(json.loads(archive.read("notes/" + note["id"] + ".json")) == note, "Notebook export changed record")
            require(archive.read("text/" + note["id"] + ".txt") == raw_text, "Notebook text differs")
            require(all(token.encode() not in archive.read(name) for name in archive.namelist()), "Export leaked session token")
        passed("Individual text and complete notebook ZIP exports retain content and exclude browser tokens")
        first_token = token
        run([*launcher, "--state", first, "--app-version", "1.1.0"])
        token = session(first)
        view = notebook(token)
        require(view["version"] == "1.1.0" and view["pinning"] and view["notes"] == [note], "Update lost data or pin feature")
        require(token != first_token, "Restart reused browser token")
        http("/api/notebook", first_token, expect=403)
        passed("Updating 1.0.0 to 1.1.0 retains the note, enables pinning and invalidates the old private link")
        note["pinned"] = True
        note = json.loads(http("/api/notes", token, note))["note"]
        require(note["pinned"] and note["revision"] == 3, "Pin action did not persist")
        passed("The new pin feature saves a real compatible data update")
        run([*launcher, "--state", first, "--rollback"])
        token = session(first)
        view = notebook(token)
        require(view["version"] == "1.0.0" and not view["pinning"] and view["notes"] == [note], "Rollback changed current data")
        require(app(first)["generation"] == 3, "Rollback generation mismatch")
        passed("Restoring version 1.0.0 retains the current note and its compatible new field")
        run([*launcher, "--state", first, "--stop"])
        backup = cli(first, "backup", "fieldnotes", "--output", work / "notebook-backup.zip")
        evidence = cli(first, "export-evidence", "--output", work / "original-evidence.zip")
        require(backup["key_id"] == first_key and evidence["key_id"] == first_key, "Original records have unexpected signer")
        with zipfile.ZipFile(work / "notebook-backup.zip") as archive:
            require("data/notes/" + note["id"] + ".json" in archive.namelist(), "Backup missing note")
            require(all(not name.startswith(("work/", "logs/", "config/")) for name in archive.namelist()), "Backup includes runtime material")
        passed("Stopped application backup carries code and notes; original signed evidence is exported separately")
        second_identity = cli(second, "identity")
        require(second_identity["key_id"] != first_key, "Replacement copied the operator identity")
        restored = cli(second, "restore", work / "notebook-backup.zip", "--key-id", first_key)
        require(restored["status"] == "stopped" and not restored["trusted"], "Restore started or authorized code")
        require(json.loads((second / "data" / "fieldnotes" / "notes" / (note["id"] + ".json")).read_text(encoding="utf-8")) == note, "Restore changed note")
        passed("A fresh operator restores the identical notebook while remaining stopped and separately owned")
        denied = cli(second, "start", "fieldnotes", "--expect", app(second)["generation"], succeeds=False)
        require(denied["status"] == "failed" and "authorized" in denied["error"], "Foreign publisher was not explicitly refused")
        passed("The replacement operator refuses execution before scoped publisher authorization")
        verdict = cli(second, "verify-evidence", work / "original-evidence.zip", "--key-id", first_key)
        require(verdict["valid"] and verdict["identity_pinned"], "Original historical evidence did not verify")
        passed("The replacement independently verifies the old operator's separate signed record against its fingerprint")
        package = first / "packages" / (first_app["release_id"] + ".schism")
        cli(second, "trust", package, "--app", "fieldnotes")
        cli(second, "start", "fieldnotes", "--expect", app(second)["generation"])
        new_token = session(second)
        require(new_token != token and notebook(new_token)["notes"] == [note], "Replacement startup changed note or reused token")
        note["body"] += "\nContinued under the replacement operator."
        continued = json.loads(http("/api/notes", new_token, note))["note"]
        require(continued["revision"] == 4 and notebook(new_token)["notes"] == [continued], "Replacement could not continue work")
        require(json.loads(note_path.read_text(encoding="utf-8"))["revision"] == 3, "Replacement mutated original data")
        passed("Explicit app-scoped trust enables continuation under the replacement's identity; the old copy remains unchanged")
        next_evidence = cli(second, "export-evidence", "--output", work / "replacement-evidence.zip")
        next_verdict = cli(second, "verify-evidence", work / "replacement-evidence.zip", "--key-id", second_identity["key_id"])
        require(next_verdict["valid"] and next_evidence["key_id"] != evidence["key_id"], "New evidence lost separate identity")
        with zipfile.ZipFile(work / "replacement-evidence.zip") as archive:
            envelope = json.loads(archive.read("evidence.json"))
        restore_events = [event for event in envelope["payload"]["events"] if event["payload"]["kind"] == "application.restored"]
        require(len(restore_events) == 1 and restore_events[0]["payload"]["body"]["archive_sha256"] == backup["sha256"], "New history does not bind the restored backup")
        passed("The new signed history binds the restored backup while the original evidence remains independently verifiable")
        if (schism / "schism.py").is_file() and (schism / "scripts" / "verify_source.py").is_file() and (schism / "SOURCE-MANIFEST.json").is_file():
            run([sys.executable, schism / "scripts" / "verify_source.py"])
            passed("The published controller's closed source inventory remains unchanged after the journey")
        report["status"] = "PASS"
        report["passed"] = len(CASES)
        report["data_contract"] = "fieldnotes.note/v1 in UTF-8 JSON; two code releases use fieldnotes/1"
        report["continuity"] = "1.0.0 → 1.1.0 → 1.0.0 → stopped signed backup → independently authorized new operator"
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        for state in (first, second):
            if state.exists() and (state / "state.sqlite").exists():
                try:
                    selected = app(state)
                    if selected:
                        cli(state, "stop", "fieldnotes", "--expect", selected["generation"])
                except Exception as error:
                    report.setdefault("cleanup_errors", []).append(str(error))
                    report["status"] = "FAIL"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Qualification " + report["status"] + "; report: " + str(args.output), flush=True)


if __name__ == "__main__":
    main()

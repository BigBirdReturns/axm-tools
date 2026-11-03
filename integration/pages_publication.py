#!/usr/bin/env python3
"""Bind every Pages publisher to the exact uploaded bytes and live readback.

Publication infrastructure only. Individual tools keep their independent runtimes.
No credential is stored here; Actions supplies its existing scoped token.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request


SCHEMA = "axm-tools/pages-deployment@1"
MARKER = "pages-build.json"
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")


class PublicationError(ValueError):
    pass


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(encode(value))
    os.replace(temporary, path)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def assert_current(root):
    """A queued run must not overwrite a newer public source tree."""
    head = git(root, "rev-parse", "HEAD")
    remote = git(root, "ls-remote", "origin", "refs/heads/main").split()
    if not remote or remote[0] != head:
        raise PublicationError("source_advanced: main changed after this checkout; retain this attempt")
    return head


def visible_paths(root):
    """Mirror upload-pages' dotfile exclusion without following symlinks."""
    root = Path(root)
    for base, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = sorted(d for d in directories if not d.startswith(".") and d != "__pycache__")
        for directory in directories:
            if (Path(base) / directory).is_symlink():
                raise PublicationError("symlink_in_public_tree")
        for name in sorted(filenames):
            if name.startswith(".") or name.endswith((".pyc", ".pyo")):
                continue
            path = Path(base) / name
            if path.is_symlink() or not path.is_file():
                raise PublicationError("non_regular_public_file")
            yield path, path.relative_to(root).as_posix()


def prepare(root, stage, receipt_path, *, context, check_current=True):
    root, stage, receipt_path = Path(root).resolve(), Path(stage).resolve(), Path(receipt_path).resolve()
    if stage == root or root in stage.parents or stage in root.parents:
        raise PublicationError("stage_must_be_disjoint_from_source")
    if receipt_path == stage or stage in receipt_path.parents:
        raise PublicationError("private_receipt_must_be_outside_stage")
    if stage.exists():
        raise PublicationError("stage_exists: inspect the retained attempt before retrying")
    head = assert_current(root) if check_current else git(root, "rev-parse", "HEAD")
    for key in ("repository", "trigger_sha", "run_id", "run_attempt", "artifact_name"):
        if not isinstance(context.get(key), str) or not context[key]:
            raise PublicationError("missing_context_" + key)
    if not HEX40.fullmatch(context["trigger_sha"]) or not HEX40.fullmatch(head):
        raise PublicationError("invalid_commit_identity")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", context["repository"]):
        raise PublicationError("invalid_repository")
    stage.mkdir(parents=True)
    files = []
    for source, relative in visible_paths(root):
        if relative == MARKER:
            raise PublicationError("reserved_build_marker_present_in_source")
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        sha = file_digest(target)
        if file_digest(source) != sha:
            raise PublicationError("source_changed_during_staging")
        files.append({"path": relative, "bytes": target.stat().st_size, "sha256": sha})
    files.sort(key=lambda row: row["path"])
    if not any(row["path"] == "index.html" for row in files):
        raise PublicationError("missing_site_index")
    marker = {
        "schema": "axm-tools/pages-build@1",
        **context,
        "built_sha": head,
        "content_manifest_sha256": digest(encode(files)),
        "file_count": len(files),
    }
    marker_bytes = encode(marker)
    (stage / MARKER).write_bytes(marker_bytes)
    files.append({"path": MARKER, "bytes": len(marker_bytes), "sha256": digest(marker_bytes)})
    files.sort(key=lambda row: row["path"])
    receipt = {
        "schema": SCHEMA,
        "state": "PREPARED",
        **context,
        "built_sha": head,
        "source_sha": context["trigger_sha"],
        "source_sha_semantics": "legacy alias of trigger_sha; built_sha identifies the uploaded checkout",
        "content_manifest_sha256": marker["content_manifest_sha256"],
        "files": files,
        "marker": marker,
        "axm_readiness_release": "readiness-equipment-evidence/1.0",
    }
    write_json(receipt_path, receipt)
    return receipt


def verify_archive(archive, expected_files):
    expected = {row["path"]: row for row in expected_files}
    seen = {}
    with tarfile.open(archive, "r:*") as bundle:
        for member in bundle:
            if member.isdir():
                continue
            name = member.name[2:] if member.name.startswith("./") else member.name
            if not member.isfile() or name not in expected or name in seen or ".." in PurePosixPath(name).parts:
                raise PublicationError("unexpected_archive_member")
            stream = bundle.extractfile(member)
            h = hashlib.sha256()
            total = 0
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(part)
                total += len(part)
            row = {"path": name, "bytes": total, "sha256": h.hexdigest()}
            if row != expected[name]:
                raise PublicationError("archive_content_mismatch")
            seen[name] = row
    if seen.keys() != expected.keys():
        raise PublicationError("archive_missing_files")
    return {"sha256": file_digest(archive), "bytes": Path(archive).stat().st_size, "file_count": len(seen)}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PublicationError("unexpected_http_redirect")


def get_bytes(url, *, token=None, max_bytes=8 * 1024 * 1024):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise PublicationError("invalid_https_url")
    headers = {"User-Agent": "axm-tools-pages-publication/1", "Cache-Control": "no-cache", "Accept-Encoding": "identity"}
    if token:
        if parsed.netloc != "api.github.com":
            raise PublicationError("token_origin_mismatch")
        headers.update({"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"})
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
        if response.status != 200:
            raise PublicationError("unexpected_http_status")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise PublicationError("response_too_large")
        return body


def api_get(repository, path, token):
    return json.loads(get_bytes("https://api.github.com/repos/" + repository + "/" + path, token=token))


def bind_artifact(receipt, archive, artifact):
    uploaded = verify_archive(archive, receipt["files"])
    if str(artifact.get("id", "")) == "" or artifact.get("name") != receipt["artifact_name"]:
        raise PublicationError("artifact_identity_mismatch")
    if str(artifact.get("workflow_run", {}).get("id", "")) != receipt["run_id"]:
        raise PublicationError("artifact_run_mismatch")
    provider_digest = artifact.get("digest", "")
    if not provider_digest.startswith("sha256:") or not HEX64.fullmatch(provider_digest[7:]):
        raise PublicationError("artifact_provider_digest_missing")
    receipt["artifact"] = {
        "id": artifact["id"], "name": artifact["name"],
        "provider_digest": provider_digest, "provider_size_bytes": artifact.get("size_in_bytes"),
        "tar": uploaded,
    }
    receipt["state"] = "UPLOADED_ARTIFACT_VERIFIED"
    return receipt


def matching_deployment(receipt, deployments, statuses):
    """Use observed provider IDs, correlated by the Actions run's log URL."""
    prefix = "https://github.com/" + receipt["repository"] + "/actions/runs/" + receipt["run_id"]
    matches = []
    for deployment in deployments:
        if deployment.get("environment") != "github-pages" or deployment.get("sha") != receipt["trigger_sha"]:
            continue
        for status in statuses(deployment["id"]):
            url = status.get("log_url", "")
            if url == prefix or url.startswith(prefix + "/"):
                matches.append({
                    "provider": "github-pages", "kind": "github-environment-deployment",
                    "id": deployment["id"], "url": deployment.get("url"),
                    "sha": deployment["sha"], "run_log_url": url,
                    "status_observed": status.get("state"),
                })
                break
    if len(matches) != 1:
        raise PublicationError("deployment_identity_unresolved")
    return matches[0]


def verify_live(receipt, page_url, fetch, *, attempts=30, pause=5, sleep=time.sleep):
    if not receipt.get("artifact"):
        raise PublicationError("uploaded_artifact_required")
    parsed = urllib.parse.urlsplit(page_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PublicationError("invalid_page_url")
    page_url = page_url.rstrip("/") + "/"
    manifest = {row["path"]: row for row in receipt["files"]}
    checked = [MARKER, "index.html"]
    if "publications/index.html" in manifest:
        checked.append("publications/index.html")
    last_error = None
    for attempt in range(attempts):
        try:
            readings = []
            for relative in checked:
                url = page_url + urllib.parse.quote(relative, safe="/")
                queried = url + "?axm_run=" + urllib.parse.quote(receipt["run_id"]) + "&attempt=" + str(attempt)
                body = fetch(queried)
                row = manifest[relative]
                if len(body) != row["bytes"] or digest(body) != row["sha256"]:
                    raise PublicationError("live_content_mismatch")
                readings.append({"path": relative, "url": url, "http_status": 200, "bytes": len(body), "sha256": digest(body)})
            now = datetime.now(timezone.utc).isoformat()
            return {"observed_at": now, "checks": readings}
        except (PublicationError, urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = type(error).__name__
            if attempt + 1 < attempts:
                sleep(pause)
    raise PublicationError("live_readback_failed_" + str(last_error))


def commit_receipt(root, receipt_path, worktree):
    """Write only the observed receipt on current main; normal push is the lease."""
    root, worktree = Path(root).resolve(), Path(worktree).resolve()
    receipt = json.loads(Path(receipt_path).read_text())
    if receipt.get("state") != "DEPLOYED_AND_READ_BACK":
        raise PublicationError("live_acceptance_required_before_receipt_commit")
    if worktree.exists() or root == worktree or root in worktree.parents:
        raise PublicationError("receipt_worktree_must_be_new_and_external")
    git(root, "fetch", "--no-tags", "origin", "main")
    git(root, "worktree", "add", "--detach", str(worktree), "origin/main")
    subprocess.run(["git", "-C", str(worktree), "merge-base", "--is-ancestor", receipt["built_sha"], "HEAD"], check=True)
    public_receipt = {key: value for key, value in receipt.items() if key != "files"}
    target = worktree / ".github/pages-deployment.json"
    write_json(target, public_receipt)
    git(worktree, "add", ".github/pages-deployment.json")
    if not git(worktree, "diff", "--cached", "--name-only"):
        return {"status": "unchanged", "commit": git(worktree, "rev-parse", "HEAD")}
    git(worktree, "-c", "user.name=pages-deploy-bot", "-c", "user.email=actions@users.noreply.github.com", "commit", "-m", "pages: retain exact artifact and live deployment receipt")
    git(worktree, "push", "origin", "HEAD:main")
    return {"status": "committed", "commit": git(worktree, "rev-parse", "HEAD")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--root", default=".")
    p.add_argument("--stage", required=True)
    p.add_argument("--receipt", required=True)
    p.add_argument("--artifact-name", required=True)
    p = sub.add_parser("bind-artifact")
    p.add_argument("--receipt", required=True)
    p.add_argument("--archive", required=True)
    p.add_argument("--artifact-id", required=True)
    p = sub.add_parser("assert-current")
    p.add_argument("--root", default=".")
    p = sub.add_parser("readback")
    p.add_argument("--receipt", required=True)
    p.add_argument("--page-url", required=True)
    p = sub.add_parser("commit")
    p.add_argument("--root", default=".")
    p.add_argument("--receipt", required=True)
    p.add_argument("--worktree", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            context = {"repository": os.environ.get("GITHUB_REPOSITORY", ""), "trigger_sha": os.environ.get("GITHUB_SHA", ""), "run_id": os.environ.get("GITHUB_RUN_ID", ""), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""), "artifact_name": args.artifact_name, "workflow": os.environ.get("GITHUB_WORKFLOW", "")}
            result = prepare(args.root, args.stage, args.receipt, context=context)
        elif args.command == "assert-current":
            result = {"built_sha": assert_current(args.root)}
        elif args.command == "commit":
            result = commit_receipt(args.root, args.receipt, args.worktree)
        else:
            receipt = json.loads(Path(args.receipt).read_text())
            token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
            if not token:
                raise PublicationError("existing_actions_token_required")
            if args.command == "bind-artifact":
                if not args.artifact_id.isdecimal():
                    raise PublicationError("invalid_artifact_id")
                artifact = api_get(receipt["repository"], "actions/artifacts/" + args.artifact_id, token)
                result = bind_artifact(receipt, args.archive, artifact)
            else:
                receipt["state"] = "DEPLOYMENT_COMPLETED_READBACK_PENDING"
                receipt["page_url"] = args.page_url
                write_json(args.receipt, receipt)
                receipt["live_readback"] = verify_live(receipt, args.page_url, get_bytes)
                query = "deployments?environment=github-pages&sha=" + receipt["trigger_sha"] + "&per_page=100"
                deployments = api_get(receipt["repository"], query, token)
                receipt["deployment"] = matching_deployment(receipt, deployments, lambda ident: api_get(receipt["repository"], f"deployments/{ident}/statuses?per_page=100", token))
                receipt["state"] = "DEPLOYED_AND_READ_BACK"
                receipt["deployed_at"] = receipt["live_readback"]["observed_at"]
                result = receipt
            write_json(args.receipt, result)
        print(json.dumps({key: value for key, value in result.items() if key not in {"files", "marker"}}, sort_keys=True, indent=2))
        return 0
    except (PublicationError, OSError, subprocess.CalledProcessError, KeyError, json.JSONDecodeError) as error:
        # Do not emit tokens, HTTP bodies or subprocess credential details.
        print(json.dumps({"error": str(error) if isinstance(error, PublicationError) else type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

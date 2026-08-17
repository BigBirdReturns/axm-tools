#!/usr/bin/env python3
"""Build and locally qualify the byte-addressed internal Manzanita release candidate."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.server
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator

CONTRACT_SCHEMA = "axm-tools/manzanita-release-control-contract@1"
LEDGER_SCHEMA = "axm-tools/manzanita-external-campaign-ledger@1"
MANIFEST_SCHEMA = "axm-tools/manzanita-portable-release-manifest@1"
DECISION_SCHEMA = "axm-tools/manzanita-release-decision@1"
CONTINUITY_SCHEMA = "axm-tools/manzanita-continuity-receipt@1"
BUILD_SCHEMA = "axm-tools/manzanita-release-control-build@1"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
CAMPAIGN_STATES = {
    "not_performed",
    "scheduled",
    "in_progress",
    "blocked",
    "failed",
    "passed",
}
AUTOMATED_PROOF_KEYS = {
    "archive_reimport",
    "bounded_secret_scan",
    "isolated_same_runner_successor",
    "local_candidate_served_bytes",
    "local_rollback_served_bytes",
    "atomic_local_rollback",
}
SECRET_PATTERNS = (
    ("pem_private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{40,255})\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
    ("stripe_live_key", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{20,}\b")),
    (
        "bearer_token",
        re.compile(r"(?i)\b(?:authorization\s*[:=]\s*bearer|bearer)\s+[A-Za-z0-9._~+/=-]{20,}"),
    ),
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|authorization|password|secret|private[_-]?key)"
            r"\b\s*[:=]\s*[\"']([A-Za-z0-9._~+/=-]{20,})[\"']"
        ),
    ),
)


class ReleaseControlError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseControlError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseControlError(f"Cannot load {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def recursive_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(str(key).lower())
            found.update(recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(recursive_keys(item))
    return found


def resolve_repo_path(repo_root: Path, value: Path | str, label: str) -> Path:
    root = repo_root.resolve()
    raw = Path(value)
    candidate = raw if raw.is_absolute() else root / raw
    require(not candidate.is_symlink(), f"{label} may not be a symlink: {candidate}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ReleaseControlError(f"{label} escapes the repository root: {value}") from exc
    return resolved


def resolve_contract_path(repo_root: Path, value: Any, label: str) -> Path:
    require(isinstance(value, str) and value, f"{label} must be a repository-relative path")
    safe_archive_path(value)
    return resolve_repo_path(repo_root, Path(value), label)


def portable_path(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise ReleaseControlError(f"Source path is outside the repository root: {path}") from exc


def safe_archive_path(value: str) -> str:
    path = PurePosixPath(value)
    require(
        bool(value)
        and value != "."
        and "\x00" not in value
        and "\\" not in value
        and not path.is_absolute()
        and ".." not in path.parts
        and not (path.parts and ":" in path.parts[0]),
        f"Unsafe archive path: {value!r}",
    )
    return path.as_posix()


def validate_regular_tree(root: Path, label: str) -> None:
    require(root.exists(), f"{label} is missing: {root}")
    require(root.is_dir(), f"{label} is not a directory: {root}")
    require(not root.is_symlink(), f"{label} may not be a symlink: {root}")
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in sorted(directories):
            path = current_path / name
            mode = path.lstat().st_mode
            require(not stat.S_ISLNK(mode), f"{label} contains a symlink: {path}")
            require(stat.S_ISDIR(mode), f"{label} contains a non-directory node: {path}")
        for name in sorted(files):
            path = current_path / name
            mode = path.lstat().st_mode
            require(not stat.S_ISLNK(mode), f"{label} contains a symlink: {path}")
            require(stat.S_ISREG(mode), f"{label} contains a non-regular file: {path}")


def require_regular_file(path: Path, label: str) -> None:
    require(path.exists(), f"{label} is missing: {path}")
    mode = path.lstat().st_mode
    require(not stat.S_ISLNK(mode), f"{label} may not be a symlink: {path}")
    require(stat.S_ISREG(mode), f"{label} is not a regular file: {path}")


def iter_files(root: Path) -> Iterator[Path]:
    validate_regular_tree(root, "Manifest tree")
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        mode = path.lstat().st_mode
        require(not stat.S_ISLNK(mode), f"Manifest tree contains a symlink: {path}")
        require(stat.S_ISREG(mode), f"Manifest tree contains a non-regular file: {path}")
        if "__pycache__" not in path.parts and path.suffix != ".pyc":
            yield path


def manifest_rows(root: Path, prefix: str) -> list[dict[str, Any]]:
    rows = []
    for path in iter_files(root):
        payload = path.read_bytes()
        rows.append(
            {
                "path": safe_archive_path(
                    f"{prefix}/{path.relative_to(root).as_posix()}"
                ),
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
        )
    return rows


def manifest_digest(rows: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_bytes(rows))


def current_head(repo_root: Path) -> str:
    override = os.environ.get("REVIEW_HEAD_SHA", "").strip()
    if len(override) == 40 and all(char in "0123456789abcdef" for char in override):
        return override
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    observed = result.stdout.strip()
    return observed if len(observed) == 40 else "WORKTREE"


def copy_tree(source: Path, target: Path, label: str) -> None:
    validate_regular_tree(source, label)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        copy_function=shutil.copy2,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    validate_regular_tree(target, f"Copied {label}")


def scan_tree_for_secrets(root: Path, label: str) -> dict[str, Any]:
    validate_regular_tree(root, label)
    scanned_files = 0
    text_files = 0
    binary_files = 0
    for path in iter_files(root):
        scanned_files += 1
        payload = path.read_bytes()
        if b"\x00" in payload[:8192]:
            binary_files += 1
            continue
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            binary_files += 1
            continue
        text_files += 1
        for pattern_id, pattern in SECRET_PATTERNS:
            require(
                pattern.search(text) is None,
                f"{label} contains a high-confidence secret pattern {pattern_id}: "
                f"{path.relative_to(root).as_posix()}",
            )
    return {
        "result": "PASS",
        "scope": label,
        "scanner": "bounded_high_confidence_static_patterns@1",
        "pattern_ids": [pattern_id for pattern_id, _ in SECRET_PATTERNS],
        "scanned_files": scanned_files,
        "text_files": text_files,
        "binary_files": binary_files,
        "finding_count": 0,
    }


def validate_json_boundary(
    path: Path,
    prohibited_keys: set[str],
) -> dict[str, Any]:
    value = load_json(path)
    findings = sorted(recursive_keys(value) & prohibited_keys)
    require(not findings, f"{path} contains prohibited keys: {findings}")
    serialized = json.dumps(value, sort_keys=True).lower()
    for token in (
        "email_sent",
        "calendar_event_created",
        "payment_executed",
        "publication_completed",
        "institutional_acceptance_recorded",
        "external_effect_completed",
    ):
        require(token not in serialized, f"{path} implies an external effect: {token}")
    return value


def validate_donor_chain(values: dict[str, dict[str, Any]]) -> None:
    experience = values["experience_data"]
    require(
        experience.get("schema") == "axm-tools/manzanita-whole-experience-data@1",
        "Unexpected P7 experience schema",
    )
    require(experience.get("place", {}).get("public_safe") is True, "P7 place is not public safe")
    require(experience.get("public_effect") == "none", "P7 carries a public effect")
    require(
        experience.get("constitutional_count_effect") == "none",
        "P7 carries a constitutional-count effect",
    )
    require(experience.get("release_effect") == "none", "P7 carries release authority")
    require(len(experience.get("apertures", [])) == 7, "P7 aperture count drifted")
    require(len(experience.get("overlays", [])) == 8, "P7 overlay count drifted")
    require(len(experience.get("roles", [])) == 5, "P7 role count drifted")

    experience_build = values["experience_build"]
    require(experience_build.get("result") == "PASS", "P7 build did not pass")
    require(experience_build.get("public_effect") == "none", "P7 build carries a public effect")
    require(
        experience_build.get("constitutional_count_effect") == "none",
        "P7 build carries a count effect",
    )
    require(experience_build.get("release_effect") == "none", "P7 build carries release authority")

    experience_browser = values["experience_browser"]
    require(experience_browser.get("result") == "PASS", "P7 browser campaign did not pass")
    require(experience_browser.get("console_errors") == [], "P7 browser has console errors")
    require(experience_browser.get("page_errors") == [], "P7 browser has page errors")
    require(experience_browser.get("external_requests") == [], "P7 browser made external requests")

    p8 = values["p8_report"]
    require(
        p8.get("schema") == "axm-tools/manzanita-resilience-qualification@1",
        "Unexpected P8 report schema",
    )
    require(p8.get("result") == "PASS", "P8 qualification did not pass")
    require(p8.get("campaign_count") == 19, "P8 campaign count drifted")
    require(all(row.get("result") == "PASS" for row in p8.get("campaigns", [])), "A P8 campaign failed")
    for field in (
        "physical_campaigns_performed",
        "real_assistive_technology_claim",
        "real_device_claim",
        "actual_network_claim",
        "private_projection_claim",
        "credentialed_provider_claim",
        "field_operation_claim",
    ):
        require(p8.get(field) is False, f"P8 improperly claims {field}")
    require(p8.get("public_effect") == "none", "P8 carries a public effect")
    require(p8.get("constitutional_count_effect") == "none", "P8 carries a count effect")
    require(p8.get("release_effect") == "none", "P8 carries release authority")

    p8_board = values["p8_board"]
    require(p8_board.get("result") == "PASS", "P8 contained review did not pass")
    require(p8_board.get("outcome") == "admit_with_holds", "P8 review outcome drifted")
    require(p8_board.get("open_vetoes") == [], "P8 has an open veto")
    require(
        p8_board.get("open_critical_or_high_defects") == [],
        "P8 has an open critical or high defect",
    )
    require(
        p8_board.get("release_effect") == "internal_candidate_only",
        "P8 board release boundary drifted",
    )

    p9 = values["p9_register"]
    require(
        p9.get("schema") == "axm-tools/manzanita-estate-parity-register@1",
        "Unexpected P9 register schema",
    )
    require(p9.get("surface_count") == 10, "P9 surface count drifted")
    require(p9.get("component_count") == 104, "P9 component count drifted")
    require(p9.get("uncovered_surfaces") == [], "P9 leaves uncovered surfaces")
    require(p9.get("unknown_components") == [], "P9 leaves unknown components")
    require(
        p9.get("successor_candidate", {}).get("state") == "qualified_internal_candidate",
        "P9 successor candidate state drifted",
    )
    require(
        p9.get("successor_candidate", {}).get("campaign_count") == 19,
        "P9 successor campaign count drifted",
    )
    require(
        p9.get("successor_candidate", {}).get("public_release_authorized") is False,
        "P9 authorizes public release",
    )
    require(p9.get("public_effect") == "none", "P9 carries a public effect")
    require(p9.get("constitutional_count_effect") == "none", "P9 carries a count effect")
    require(p9.get("release_effect") == "none", "P9 carries release authority")

    p9_build = values["p9_build"]
    require(p9_build.get("result") == "PASS", "P9 build did not pass")
    require(p9_build.get("public_effect") == "none", "P9 build carries a public effect")
    require(p9_build.get("constitutional_count_effect") == "none", "P9 build carries a count effect")
    require(p9_build.get("release_effect") == "none", "P9 build carries release authority")

    p9_board = values["p9_board"]
    require(p9_board.get("result") == "PASS", "P9 contained review did not pass")
    require(p9_board.get("outcome") == "admit_with_holds", "P9 review outcome drifted")
    require(p9_board.get("open_vetoes") == [], "P9 has an open veto")
    require(
        p9_board.get("open_critical_or_high_defects") == [],
        "P9 has an open critical or high defect",
    )
    require(
        p9_board.get("release_effect") == "internal_candidate_only",
        "P9 board release boundary drifted",
    )


def copy_evidence(
    sources: dict[str, Path],
    target: Path,
    repo_root: Path,
    prohibited_keys: set[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    target.mkdir(parents=True, exist_ok=True)
    values: dict[str, dict[str, Any]] = {}
    receipts = []
    for label, source in sorted(sources.items()):
        require_regular_file(source, f"Required evidence file {label}")
        value = validate_json_boundary(source, prohibited_keys)
        values[label] = value
        destination = target / f"{label}.json"
        shutil.copy2(source, destination)
        receipts.append(
            {
                "label": label,
                "source_path": portable_path(source, repo_root),
                "archive_path": f"evidence/{destination.name}",
                "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
        )
    return values, receipts


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(safe_archive_path(name), FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = ((stat.S_IFREG | 0o644) & 0xFFFF) << 16
    return info


def build_archive(package_root: Path, archive_path: Path) -> str:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in iter_files(package_root):
            archive.writestr(
                zip_info(path.relative_to(package_root).as_posix()),
                path.read_bytes(),
            )
    return sha256_file(archive_path)


def extract_archive(archive_path: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        normalized = [safe_archive_path(name) for name in names]
        require(len(normalized) == len(set(normalized)), "Portable archive contains duplicate names")
        for info in infos:
            mode = (info.external_attr >> 16) & 0xFFFF
            require(not stat.S_ISLNK(mode), f"Portable archive contains a symlink: {info.filename}")
            require(info.is_dir() or mode == 0 or stat.S_ISREG(mode), f"Portable archive contains an unsupported node: {info.filename}")
        archive.extractall(target)
    validate_regular_tree(target, "Reimported portable archive")


def verify_rows(root: Path, rows: list[dict[str, Any]]) -> None:
    require(isinstance(rows, list), "Manifest rows must be a list")
    expected = {row["path"]: row for row in rows}
    require(len(expected) == len(rows), "Manifest rows contain duplicate paths")
    validate_regular_tree(root, "Verified manifest tree")
    observed: dict[str, dict[str, Any]] = {}
    for path in iter_files(root):
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        observed[relative] = {
            "path": relative,
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
    require(set(observed) == set(expected), f"Manifest path drift: {sorted(set(observed) ^ set(expected))}")
    for relative, row in expected.items():
        require(observed[relative]["bytes"] == row["bytes"], f"Byte count drift: {relative}")
        require(observed[relative]["sha256"] == row["sha256"], f"SHA-256 drift: {relative}")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@contextlib.contextmanager
def serve(directory: Path) -> Iterator[str]:
    class BoundHandler(QuietHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), BoundHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def served_byte_proof(
    directory: Path,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    observations = []
    with serve(directory) as base_url:
        for row in rows:
            url = base_url + urllib.parse.quote(row["path"], safe="/")
            with urllib.request.urlopen(url, timeout=20) as response:
                payload = response.read()
                status = response.status
                content_type = response.headers.get_content_type()
            require(status == 200, f"Served path failed: {row['path']}")
            require(len(payload) == row["bytes"], f"Served byte count drift: {row['path']}")
            require(sha256_bytes(payload) == row["sha256"], f"Served digest drift: {row['path']}")
            observations.append(
                {
                    "path": row["path"],
                    "status": status,
                    "content_type": content_type,
                    "bytes": len(payload),
                    "sha256": sha256_bytes(payload),
                }
            )
    return {
        "result": "PASS",
        "file_count": len(observations),
        "observations": observations,
        "manifest_sha256": manifest_digest(rows),
    }


def write_active_pointer(
    workspace: Path,
    target: str,
    manifest_sha256: str,
) -> dict[str, Any]:
    require(target in {"candidate", "rollback"}, f"Unknown active target: {target}")
    pointer: dict[str, Any] = {
        "schema": "axm-tools/manzanita-local-release-pointer@1",
        "target": target,
        "manifest_sha256": manifest_sha256,
    }
    pointer["payload_sha256"] = sha256_bytes(canonical_bytes(pointer))
    temporary = workspace / "ACTIVE.json.next"
    active = workspace / "ACTIVE.json"
    write_json(temporary, pointer)
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, active)
    return pointer


def verify_active_pointer(
    workspace: Path,
    expected_target: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pointer = load_json(workspace / "ACTIVE.json")
    payload = dict(pointer)
    supplied = payload.pop("payload_sha256", None)
    require(supplied == sha256_bytes(canonical_bytes(payload)), "Active pointer checksum is invalid")
    require(pointer.get("target") == expected_target, "Active pointer target drifted")
    expected_digest = manifest_digest(rows)
    require(pointer.get("manifest_sha256") == expected_digest, "Active pointer manifest drifted")
    verify_rows(workspace / "versions" / expected_target, rows)
    return pointer


def rollback_simulation(
    candidate: Path,
    rollback: Path,
    candidate_rows: list[dict[str, Any]],
    rollback_rows: list[dict[str, Any]],
    workspace: Path,
) -> dict[str, Any]:
    if workspace.exists():
        shutil.rmtree(workspace)
    versions = workspace / "versions"
    versions.mkdir(parents=True)
    copy_tree(candidate, versions / "candidate", "Candidate rollback-simulation version")
    copy_tree(rollback, versions / "rollback", "Historical rollback-simulation version")
    candidate_pointer = write_active_pointer(
        workspace,
        "candidate",
        manifest_digest(candidate_rows),
    )
    verify_active_pointer(workspace, "candidate", candidate_rows)
    rollback_pointer = write_active_pointer(
        workspace,
        "rollback",
        manifest_digest(rollback_rows),
    )
    verify_active_pointer(workspace, "rollback", rollback_rows)
    return {
        "result": "PASS",
        "mechanism": "atomic_pointer_file_replace",
        "pointer_path": "ACTIVE.json",
        "candidate_pointer_sha256": candidate_pointer["payload_sha256"],
        "rollback_pointer_sha256": rollback_pointer["payload_sha256"],
        "candidate_manifest_sha256": manifest_digest(candidate_rows),
        "rollback_manifest_sha256": manifest_digest(rollback_rows),
        "active_after_simulation": "rollback",
        "public_deployment_claim": False,
        "deployed_rollback_claim": False,
        "claim_boundary": "This proves an exact local atomic pointer-file replacement over retained candidate and rollback directories. It does not prove that a public deployment or public rollback occurred.",
    }


def standalone_verifier_source() -> str:
    return r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

MANIFEST_SCHEMA = "axm-tools/manzanita-portable-release-manifest@1"


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def safe_path(value):
    path = PurePosixPath(value)
    if (
        not isinstance(value, str)
        or not value
        or value == "."
        or "\x00" in value
        or "\\" in value
        or path.is_absolute()
        or ".." in path.parts
        or (path.parts and ":" in path.parts[0])
    ):
        raise SystemExit(f"Unsafe manifest path: {value!r}")
    return path.as_posix()


def group_digest(rows):
    return sha256_bytes(canonical_bytes(sorted(rows, key=lambda row: row["path"])))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = root / "RELEASE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise SystemExit("Unexpected release manifest schema")
    payload = dict(manifest)
    supplied = payload.pop("payload_sha256", None)
    if supplied != sha256_bytes(canonical_bytes(payload)):
        raise SystemExit("Release manifest payload checksum is invalid")
    if manifest.get("release_state") != "HOLD":
        raise SystemExit("Portable release state is not HOLD")
    if manifest.get("public_release_authorized") is not False:
        raise SystemExit("Portable manifest authorizes public release")
    if manifest.get("public_effect") != "none" or manifest.get("constitutional_count_effect") != "none":
        raise SystemExit("Portable manifest carries an effect")
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise SystemExit("Manifest files must be a list")
    expected = {}
    groups = {"candidate": [], "rollback": [], "evidence": []}
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit("Every manifest row must be an object")
        path = safe_path(row.get("path"))
        prefix = path.split("/", 1)[0]
        if prefix not in groups or "/" not in path:
            raise SystemExit(f"Manifest path has an invalid group: {path}")
        if path in expected:
            raise SystemExit(f"Manifest rows contain a duplicate path: {path}")
        if not isinstance(row.get("bytes"), int) or row["bytes"] < 0:
            raise SystemExit(f"Manifest row has an invalid byte count: {path}")
        digest = row.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise SystemExit(f"Manifest row has an invalid digest: {path}")
        normalized = {"path": path, "bytes": row["bytes"], "sha256": digest}
        expected[path] = normalized
        groups[prefix].append(normalized)
    for prefix in groups:
        count_key = f"{prefix}_file_count"
        digest_key = f"{prefix}_manifest_sha256"
        if manifest.get(count_key) != len(groups[prefix]):
            raise SystemExit(f"{prefix} file count drifted")
        if manifest.get(digest_key) != group_digest(groups[prefix]):
            raise SystemExit(f"{prefix} manifest digest drifted")
    observed = {}
    for prefix in groups:
        for path in sorted((root / prefix).rglob("*")):
            if path.is_symlink():
                raise SystemExit(f"Portable archive contains a symlink: {path}")
            if not path.is_file():
                continue
            relative = safe_path(path.relative_to(root).as_posix())
            payload_bytes = path.read_bytes()
            observed[relative] = {
                "path": relative,
                "bytes": len(payload_bytes),
                "sha256": sha256_bytes(payload_bytes),
            }
    if set(observed) != set(expected):
        raise SystemExit(f"Manifest path drift: {sorted(set(observed) ^ set(expected))}")
    for relative, row in expected.items():
        if observed[relative]["bytes"] != row["bytes"]:
            raise SystemExit(f"Byte drift: {relative}")
        if observed[relative]["sha256"] != row["sha256"]:
            raise SystemExit(f"Hash drift: {relative}")
    print(json.dumps({
        "result": "PASS",
        "release_id": manifest["release_id"],
        "source_commit": manifest["source_commit"],
        "file_count": len(rows),
        "candidate_manifest_sha256": manifest["candidate_manifest_sha256"],
        "rollback_manifest_sha256": manifest["rollback_manifest_sha256"],
        "evidence_manifest_sha256": manifest["evidence_manifest_sha256"],
        "public_release_authorized": manifest["public_release_authorized"],
        "public_effect": manifest["public_effect"],
        "constitutional_count_effect": manifest["constitutional_count_effect"],
        "manifest_sha256": supplied,
    }, indent=2))


if __name__ == "__main__":
    main()
'''


def run_isolated_verifier(extracted: Path) -> dict[str, Any]:
    verifier = extracted / "VERIFY_RELEASE.py"
    require(verifier.is_file(), "Portable archive lacks the standalone verifier")
    result = subprocess.run(
        [sys.executable, "-I", str(verifier), "--root", str(extracted)],
        cwd=extracted,
        check=False,
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
        },
    )
    require(result.returncode == 0, f"Isolated verifier failed: {result.stdout}\n{result.stderr}")
    value = json.loads(result.stdout)
    require(value.get("result") == "PASS", "Isolated verifier did not pass")
    return {
        "result": "PASS",
        "process_isolation": "python_-I",
        "repository_imports": False,
        "private_credentials": False,
        "independent_operator_claim": False,
        "independent_machine_claim": False,
        "independent_archive_claim": False,
        "verifier_output": value,
        "stderr": result.stderr,
        "claim_boundary": "This is a same-runner isolated replay from the portable archive. An independently controlled operator, machine, account, and archive remain external campaigns.",
    }


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def validate_campaign_ledger(
    contract: dict[str, Any],
    ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    require(ledger.get("schema") == LEDGER_SCHEMA, "Unexpected external campaign ledger schema")
    require(ledger.get("release_state") == "HOLD", "External campaign ledger is not held")
    require(ledger.get("public_release_authorized") is False, "External campaign ledger authorizes release")
    require(ledger.get("public_effect") == "none", "External campaign ledger carries a public effect")
    require(
        ledger.get("constitutional_count_effect") == "none",
        "External campaign ledger carries a count effect",
    )
    campaigns = ledger.get("campaigns")
    require(isinstance(campaigns, list), "External campaign ledger lacks campaigns")
    campaign_ids = [row.get("id") if isinstance(row, dict) else None for row in campaigns]
    require(campaign_ids == contract["external_campaign_ids"], "External campaign identities drifted")
    require(
        len(campaign_ids) == len(set(campaign_ids)) == 10,
        "External campaign identities are incomplete or duplicated",
    )
    classes: list[str] = []
    for row in campaigns:
        require(isinstance(row, dict), "Every external campaign must be an object")
        campaign_id = row["id"]
        campaign_class = row.get("class")
        require(
            isinstance(campaign_class, str) and len(campaign_class) >= 8,
            f"Campaign {campaign_id} lacks a class",
        )
        classes.append(campaign_class)
        state = row.get("state")
        require(state in CAMPAIGN_STATES, f"Campaign {campaign_id} has invalid state {state!r}")
        require(
            isinstance(row.get("required_for_public_release"), bool),
            f"Campaign {campaign_id} lacks a public-release requirement flag",
        )
        receipts = row.get("evidence_receipts")
        require(isinstance(receipts, list), f"Campaign {campaign_id} evidence_receipts must be a list")
        if state == "passed":
            for field in ("operator", "venue", "procedure", "acceptance", "failure_disposition"):
                value = row.get(field)
                require(
                    isinstance(value, str) and len(value) >= 8,
                    f"Passed campaign {campaign_id} lacks complete {field}",
                )
            require(receipts, f"Passed campaign {campaign_id} lacks evidence receipts")
            receipt_ids: list[str] = []
            for receipt in receipts:
                require(
                    isinstance(receipt, dict),
                    f"Passed campaign {campaign_id} has a non-object evidence receipt",
                )
                receipt_id = receipt.get("receipt_id")
                source = receipt.get("source")
                require(
                    isinstance(receipt_id, str) and receipt_id,
                    f"Passed campaign {campaign_id} has an invalid receipt id",
                )
                require(
                    isinstance(source, str) and len(source) >= 8,
                    f"Passed campaign {campaign_id} has an invalid receipt source",
                )
                require(
                    is_sha256(receipt.get("sha256")),
                    f"Passed campaign {campaign_id} has an invalid receipt digest",
                )
                receipt_ids.append(receipt_id)
            require(
                len(receipt_ids) == len(set(receipt_ids)),
                f"Passed campaign {campaign_id} repeats an evidence receipt",
            )
    require(len(classes) == len(set(classes)), "External campaign classes are duplicated")
    return campaigns


def release_decision(
    contract: dict[str, Any],
    ledger: dict[str, Any],
    automated_proofs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    require(set(automated_proofs) == AUTOMATED_PROOF_KEYS, "Automated proof coverage drifted")
    require(all(row.get("result") == "PASS" for row in automated_proofs.values()), "An automated proof failed")
    campaigns = validate_campaign_ledger(contract, ledger)
    blocking = [
        row["id"]
        for row in campaigns
        if row.get("required_for_public_release")
        and (
            row.get("state") != "passed"
            or not row.get("operator")
            or not row.get("venue")
            or not row.get("procedure")
            or not row.get("evidence_receipts")
            or not row.get("acceptance")
            or not row.get("failure_disposition")
        )
    ]
    state = "HOLD" if blocking else "READY_FOR_PUBLIC_RELEASE_REVIEW"
    decision: dict[str, Any] = {
        "schema": DECISION_SCHEMA,
        "decision_id": "M99-RELEASE-DECISION-001",
        "state": state,
        "automated_candidate_state": "QUALIFIED_INTERNAL_RELEASE_CANDIDATE",
        "public_release_authorized": False,
        "blocking_campaigns": blocking,
        "blocking_campaign_count": len(blocking),
        "automated_proofs": {
            name: {
                "result": row["result"],
                "payload_sha256": sha256_bytes(canonical_bytes(row)),
            }
            for name, row in sorted(automated_proofs.items())
        },
        "release_law": contract["release_law"],
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    decision["payload_sha256"] = sha256_bytes(canonical_bytes(decision))
    return decision


def build(
    repo_root: Path,
    contract_path: Path,
    ledger_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    require(repo_root.is_dir(), f"Repository root is missing: {repo_root}")
    contract_path = resolve_repo_path(repo_root, contract_path, "Release contract")
    ledger_path = resolve_repo_path(repo_root, ledger_path, "External campaign ledger")
    require_regular_file(contract_path, "Release contract")
    require_regular_file(ledger_path, "External campaign ledger")
    output_root = (repo_root / output_root).resolve() if not output_root.is_absolute() else output_root.resolve()
    require(output_root != repo_root, "Output root may not replace the repository root")
    require(output_root not in repo_root.parents, "Output root may not contain the repository root")
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    contract = load_json(contract_path)
    ledger = load_json(ledger_path)
    require(contract.get("schema") == CONTRACT_SCHEMA, "Unexpected release-control contract schema")
    require(contract["object"].get("release_state") == "HOLD", "Release contract is not held")
    require(contract["object"].get("public_effect") == "none", "Release contract carries a public effect")
    require(contract["object"].get("constitutional_count_effect") == "none", "Release contract carries a count effect")
    validate_campaign_ledger(contract, ledger)

    candidate_site = resolve_contract_path(
        repo_root,
        contract["candidate_site"],
        "Candidate site",
    )
    rollback_site = resolve_contract_path(
        repo_root,
        contract["rollback_site"],
        "Historical rollback site",
    )
    require(candidate_site.is_dir(), "The exact P7 candidate site is missing")
    require(rollback_site.is_dir(), "The historical rollback site is missing")

    evidence_inputs = contract.get("evidence_inputs")
    require(isinstance(evidence_inputs, dict) and evidence_inputs, "Release contract lacks evidence inputs")
    evidence_sources = {
        label: resolve_contract_path(repo_root, relative, f"Evidence input {label}")
        for label, relative in evidence_inputs.items()
    }
    evidence_sources["release_contract"] = contract_path
    evidence_sources["external_campaign_ledger"] = ledger_path

    package = output_root / "package"
    candidate_target = package / "candidate"
    rollback_target = package / "rollback"
    evidence_target = package / "evidence"
    copy_tree(candidate_site, candidate_target, "Exact P7 candidate site")
    copy_tree(rollback_site, rollback_target, "Historical rollback donor")
    values, evidence_receipts = copy_evidence(
        evidence_sources,
        evidence_target,
        repo_root,
        set(contract["prohibited_keys"]),
    )
    validate_donor_chain(values)
    secret_scan = {
        "result": "PASS",
        "scanner": "bounded_high_confidence_static_patterns@1",
        "scopes": [
            scan_tree_for_secrets(candidate_target, "Candidate package"),
            scan_tree_for_secrets(rollback_target, "Rollback package"),
            scan_tree_for_secrets(evidence_target, "Evidence package"),
        ],
        "finding_count": 0,
    }

    candidate_rows_prefixed = manifest_rows(candidate_target, "candidate")
    rollback_rows_prefixed = manifest_rows(rollback_target, "rollback")
    evidence_rows_prefixed = manifest_rows(evidence_target, "evidence")
    limits = contract["performance_limits"]
    require(0 < len(candidate_rows_prefixed) <= limits["maximum_candidate_files"], "Candidate file count exceeds the contract")
    require(0 < len(rollback_rows_prefixed) <= limits["maximum_rollback_files"], "Rollback file count exceeds the contract")
    require(0 < len(evidence_rows_prefixed) <= limits["maximum_evidence_files"], "Evidence file count exceeds the contract")

    files = sorted(
        candidate_rows_prefixed + rollback_rows_prefixed + evidence_rows_prefixed,
        key=lambda row: row["path"],
    )
    source_commit = current_head(repo_root)
    experience = values["experience_data"]
    p8 = values["p8_report"]
    p9 = values["p9_register"]
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "release_id": "M99-INTERNAL-RC-001",
        "release_version": "0.1.0-internal",
        "source_commit": source_commit,
        "place_id": experience["place"]["id"],
        "source_run_id": experience["source_run_id"],
        "experience_payload_sha256": experience["payload_sha256"],
        "p8_payload_sha256": p8["payload_sha256"],
        "p9_payload_sha256": p9["payload_sha256"],
        "candidate_file_count": len(candidate_rows_prefixed),
        "rollback_file_count": len(rollback_rows_prefixed),
        "evidence_file_count": len(evidence_rows_prefixed),
        "candidate_manifest_sha256": manifest_digest(candidate_rows_prefixed),
        "rollback_manifest_sha256": manifest_digest(rollback_rows_prefixed),
        "evidence_manifest_sha256": manifest_digest(evidence_rows_prefixed),
        "files": files,
        "evidence_receipts": evidence_receipts,
        "rollback_target": {
            "path": contract["rollback_site"],
            "manifest_sha256": manifest_digest(rollback_rows_prefixed),
            "claim_boundary": "The historical public route is retained byte-for-byte as the rollback donor. Inclusion in this archive does not alter, promote, or redeploy it.",
        },
        "release_state": "HOLD",
        "public_release_authorized": False,
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    manifest["payload_sha256"] = sha256_bytes(canonical_bytes(manifest))
    write_json(package / "RELEASE_MANIFEST.json", manifest)
    verifier_path = package / "VERIFY_RELEASE.py"
    verifier_path.write_text(standalone_verifier_source(), encoding="utf-8")
    verifier_path.chmod(0o755)

    archive_path = output_root / "MANZANITA_INTERNAL_RELEASE_CANDIDATE.zip"
    archive_sha256 = build_archive(package, archive_path)
    require(archive_path.stat().st_size <= limits["maximum_archive_bytes"], "Portable archive exceeds the contract")

    extracted = output_root / "reimported"
    extract_archive(archive_path, extracted)
    imported_manifest = load_json(extracted / "RELEASE_MANIFEST.json")
    require(imported_manifest == manifest, "Reimported release manifest drifted")
    candidate_rows = [
        {**row, "path": row["path"].removeprefix("candidate/")}
        for row in candidate_rows_prefixed
    ]
    rollback_rows = [
        {**row, "path": row["path"].removeprefix("rollback/")}
        for row in rollback_rows_prefixed
    ]
    evidence_rows = [
        {**row, "path": row["path"].removeprefix("evidence/")}
        for row in evidence_rows_prefixed
    ]
    verify_rows(extracted / "candidate", candidate_rows)
    verify_rows(extracted / "rollback", rollback_rows)
    verify_rows(extracted / "evidence", evidence_rows)
    reimport = {
        "result": "PASS",
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": archive_sha256,
        "file_count": len(files),
        "manifest_payload_sha256": manifest["payload_sha256"],
    }
    cold = run_isolated_verifier(extracted)
    candidate_served = served_byte_proof(extracted / "candidate", candidate_rows)
    rollback_served = served_byte_proof(extracted / "rollback", rollback_rows)
    rollback_receipt = rollback_simulation(
        extracted / "candidate",
        extracted / "rollback",
        candidate_rows,
        rollback_rows,
        output_root / "rollback-simulation",
    )
    automated_proofs = {
        "archive_reimport": reimport,
        "bounded_secret_scan": secret_scan,
        "isolated_same_runner_successor": cold,
        "local_candidate_served_bytes": candidate_served,
        "local_rollback_served_bytes": rollback_served,
        "atomic_local_rollback": rollback_receipt,
    }
    decision = release_decision(contract, ledger, automated_proofs)
    write_json(output_root / "RELEASE_DECISION.json", decision)

    continuity: dict[str, Any] = {
        "schema": CONTINUITY_SCHEMA,
        "result": "PASS",
        "source_commit": source_commit,
        "release_id": manifest["release_id"],
        "archive": {
            "path": archive_path.name,
            "bytes": archive_path.stat().st_size,
            "sha256": archive_sha256,
        },
        "release_manifest_payload_sha256": manifest["payload_sha256"],
        "archive_reimport": reimport,
        "bounded_secret_scan": secret_scan,
        "isolated_same_runner_successor": cold,
        "candidate_served_byte_proof": candidate_served,
        "rollback_served_byte_proof": rollback_served,
        "rollback_simulation": rollback_receipt,
        "release_decision_state": decision["state"],
        "public_release_authorized": decision["public_release_authorized"],
        "blocking_campaigns": decision["blocking_campaigns"],
        "public_endpoint_claim": False,
        "real_deployed_rollback_claim": False,
        "independent_cold_successor_claim": False,
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    continuity["payload_sha256"] = sha256_bytes(canonical_bytes(continuity))
    write_json(output_root / "CONTINUITY_RECEIPT.json", continuity)

    receipt: dict[str, Any] = {
        "schema": BUILD_SCHEMA,
        "result": "PASS",
        "release_state": decision["state"],
        "automated_candidate_state": decision["automated_candidate_state"],
        "public_release_authorized": False,
        "source_commit": source_commit,
        "archive": continuity["archive"],
        "release_manifest": {
            "path": "package/RELEASE_MANIFEST.json",
            "sha256": sha256_file(package / "RELEASE_MANIFEST.json"),
            "payload_sha256": manifest["payload_sha256"],
            "candidate_file_count": manifest["candidate_file_count"],
            "rollback_file_count": manifest["rollback_file_count"],
            "evidence_file_count": manifest["evidence_file_count"],
            "candidate_manifest_sha256": manifest["candidate_manifest_sha256"],
            "rollback_manifest_sha256": manifest["rollback_manifest_sha256"],
            "evidence_manifest_sha256": manifest["evidence_manifest_sha256"],
        },
        "proofs": {
            name: {
                "result": row["result"],
                "payload_sha256": sha256_bytes(canonical_bytes(row)),
            }
            for name, row in sorted(automated_proofs.items())
        },
        "blocking_campaigns": decision["blocking_campaigns"],
        "blocking_campaign_count": decision["blocking_campaign_count"],
        "public_endpoint_claim": False,
        "real_deployed_rollback_claim": False,
        "independent_cold_successor_claim": False,
        "public_effect": "none",
        "constitutional_count_effect": "none",
        "claim_boundary": contract["object"]["claim_boundary"],
        "control_question": contract["control_question"],
    }
    receipt["payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    write_json(output_root / "BUILD_RECEIPT.json", receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("manzanita-next/release-control/RELEASE_CONTRACT.json"),
    )
    parser.add_argument(
        "--campaign-ledger",
        type=Path,
        default=Path("manzanita-next/release-control/EXTERNAL_CAMPAIGN_LEDGER.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("manzanita-next/release-control/out"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = build(
        args.repo_root,
        args.contract,
        args.campaign_ledger,
        args.output,
    )
    print(
        json.dumps(
            {
                "result": receipt["result"],
                "release_state": receipt["release_state"],
                "automated_candidate_state": receipt["automated_candidate_state"],
                "public_release_authorized": receipt["public_release_authorized"],
                "archive": receipt["archive"],
                "candidate_file_count": receipt["release_manifest"]["candidate_file_count"],
                "rollback_file_count": receipt["release_manifest"]["rollback_file_count"],
                "evidence_file_count": receipt["release_manifest"]["evidence_file_count"],
                "blocking_campaign_count": receipt["blocking_campaign_count"],
                "public_effect": receipt["public_effect"],
                "constitutional_count_effect": receipt["constitutional_count_effect"],
                "receipt_sha256": receipt["payload_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except ReleaseControlError as exc:
        raise SystemExit(str(exc)) from exc

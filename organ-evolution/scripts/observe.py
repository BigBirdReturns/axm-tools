#!/usr/bin/env python3
"""Compile neutral repository and local observations for Organ Evolution.

The compiler records observed implementation state. It cannot change organ anatomy,
health, candidate fitness, hard gates, interest claims, mandates, or decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

FORMAT = "axm-organ-observations/1"
SOURCES_FORMAT = "axm-organ-sources/1"
LOCAL_FORMAT = "axm-organ-local-observations/1"
MAX_JSON_BYTES = 2_000_000
MAX_REPOSITORIES = 128
MAX_LOCAL_OBSERVATIONS = 512
BAD_WORKFLOW_CONCLUSIONS = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}
SUCCESS_WORKFLOW_CONCLUSIONS = {"success", "neutral", "skipped"}
FORBIDDEN_AUTHORITY_KEYS = {"decision", "decisions", "candidate", "candidates", "dimensions", "gates", "health", "mandates", "interests"}


class ObservationError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def age_days(value: str | None, now: datetime) -> int | None:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds() // 86400))


def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ObservationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path, expected_format: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        raise ObservationError(f"missing JSON source: {path}")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ObservationError(f"JSON source exceeds {MAX_JSON_BYTES} bytes: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObservationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ObservationError(f"JSON root must be an object: {path}")
    if expected_format and value.get("format") != expected_format:
        raise ObservationError(f"{path} must use format {expected_format}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def assert_no_authority_mutation(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        bad = FORBIDDEN_AUTHORITY_KEYS & set(value)
        if bad:
            raise ObservationError(f"observation product attempts to carry authority keys at {path}: {sorted(bad)}")
        for key, child in value.items():
            assert_no_authority_mutation(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_authority_mutation(child, f"{path}[{index}]")


@dataclass
class SourceRules:
    stale_commit_days: int = 180
    stale_draft_days: int = 45
    stale_workflow_days: int = 30

    @classmethod
    def from_value(cls, value: dict[str, Any] | None) -> "SourceRules":
        value = value or {}
        fields = {
            "stale_commit_days": value.get("staleCommitDays", 180),
            "stale_draft_days": value.get("staleDraftDays", 45),
            "stale_workflow_days": value.get("staleWorkflowDays", 30),
        }
        for key, raw in fields.items():
            if not isinstance(raw, int) or not 1 <= raw <= 3650:
                raise ObservationError(f"{key} must be an integer from 1 to 3650")
        return cls(**fields)


class Provider:
    def repository(self, full_name: str) -> dict[str, Any]:
        raise NotImplementedError

    def commit(self, full_name: str, ref: str) -> dict[str, Any]:
        raise NotImplementedError

    def runs(self, full_name: str, ref: str) -> dict[str, Any]:
        raise NotImplementedError

    def pulls(self, full_name: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def tags(self, full_name: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def tree(self, full_name: str, tree_sha: str) -> dict[str, Any]:
        raise NotImplementedError


class GitHubProvider(Provider):
    def __init__(self, token: str | None, api_root: str = "https://api.github.com") -> None:
        self.token = token
        self.api_root = api_root.rstrip("/")

    def _get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        url = self.api_root + path
        if query:
            url += "?" + urlencode(query)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "axm-organ-evolution-observer/1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read(MAX_JSON_BYTES + 1)
        except HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            raise ObservationError(f"GitHub HTTP {exc.code} for {path}: {detail}") from exc
        except URLError as exc:
            raise ObservationError(f"GitHub request failed for {path}: {exc.reason}") from exc
        if len(body) > MAX_JSON_BYTES:
            raise ObservationError(f"GitHub response exceeds {MAX_JSON_BYTES} bytes for {path}")
        try:
            return json.loads(body.decode("utf-8"), object_pairs_hook=no_duplicates)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ObservationError(f"GitHub returned invalid JSON for {path}: {exc}") from exc

    @staticmethod
    def _repo_path(full_name: str) -> str:
        if full_name.count("/") != 1:
            raise ObservationError(f"invalid repository full name: {full_name}")
        owner, repo = full_name.split("/", 1)
        return f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"

    def repository(self, full_name: str) -> dict[str, Any]:
        return self._get(self._repo_path(full_name))

    def commit(self, full_name: str, ref: str) -> dict[str, Any]:
        return self._get(self._repo_path(full_name) + f"/commits/{quote(ref, safe='')}")

    def runs(self, full_name: str, ref: str) -> dict[str, Any]:
        return self._get(self._repo_path(full_name) + "/actions/runs", {"branch": ref, "per_page": 100})

    def pulls(self, full_name: str) -> list[dict[str, Any]]:
        return self._get(self._repo_path(full_name) + "/pulls", {"state": "open", "per_page": 100})

    def tags(self, full_name: str) -> list[dict[str, Any]]:
        return self._get(self._repo_path(full_name) + "/tags", {"per_page": 10})

    def tree(self, full_name: str, tree_sha: str) -> dict[str, Any]:
        return self._get(self._repo_path(full_name) + f"/git/trees/{quote(tree_sha, safe='')}", {"recursive": 1})


class FixtureProvider(Provider):
    def __init__(self, fixture: dict[str, Any]) -> None:
        repos = fixture.get("repositories")
        if not isinstance(repos, dict):
            raise ObservationError("fixture must contain a repositories object")
        self.repos = repos

    def _repo(self, full_name: str) -> dict[str, Any]:
        value = self.repos.get(full_name)
        if not isinstance(value, dict):
            raise ObservationError(f"fixture has no repository {full_name}")
        if value.get("error"):
            raise ObservationError(str(value["error"]))
        return value

    def repository(self, full_name: str) -> dict[str, Any]:
        return self._repo(full_name)["repository"]

    def commit(self, full_name: str, ref: str) -> dict[str, Any]:
        value = self._repo(full_name)
        commits = value.get("commits") or {}
        return commits.get(ref) or value["commit"]

    def runs(self, full_name: str, ref: str) -> dict[str, Any]:
        return self._repo(full_name).get("runs", {"workflow_runs": []})

    def pulls(self, full_name: str) -> list[dict[str, Any]]:
        return self._repo(full_name).get("pulls", [])

    def tags(self, full_name: str) -> list[dict[str, Any]]:
        return self._repo(full_name).get("tags", [])

    def tree(self, full_name: str, tree_sha: str) -> dict[str, Any]:
        return self._repo(full_name).get("tree", {"tree": []})


def validate_sources(value: dict[str, Any]) -> tuple[list[dict[str, Any]], SourceRules]:
    organs = value.get("organs")
    if not isinstance(organs, list) or not organs:
        raise ObservationError("sources must contain a non-empty organs array")
    if len(organs) > MAX_REPOSITORIES:
        raise ObservationError("sources contains too many organ mappings")
    seen_organs: set[str] = set()
    seen_repos: set[str] = set()
    count = 0
    for row in organs:
        if not isinstance(row, dict) or not isinstance(row.get("organId"), str):
            raise ObservationError("each source organ requires organId")
        organ_id = row["organId"]
        if not organ_id.startswith("organ."):
            raise ObservationError(f"invalid organ id: {organ_id}")
        if organ_id in seen_organs:
            raise ObservationError(f"duplicate organ mapping: {organ_id}")
        seen_organs.add(organ_id)
        repositories = row.get("repositories")
        if not isinstance(repositories, list) or not repositories:
            raise ObservationError(f"{organ_id} must map at least one repository")
        for repository in repositories:
            if not isinstance(repository, dict) or not isinstance(repository.get("fullName"), str):
                raise ObservationError(f"{organ_id} repository requires fullName")
            full_name = repository["fullName"]
            if full_name in seen_repos:
                raise ObservationError(f"repository mapped more than once: {full_name}")
            seen_repos.add(full_name)
            count += 1
    if count > MAX_REPOSITORIES:
        raise ObservationError("sources maps too many repositories")
    return organs, SourceRules.from_value(value.get("rules"))


def validate_local(value: dict[str, Any], organ_ids: set[str]) -> list[dict[str, Any]]:
    rows = value.get("observations")
    if not isinstance(rows, list):
        raise ObservationError("local observation file requires observations array")
    if len(rows) > MAX_LOCAL_OBSERVATIONS:
        raise ObservationError("too many local observations")
    seen: set[str] = set()
    accepted: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ObservationError("local observation must be an object")
        required = {"id", "organId", "observedAt", "kind", "state", "claim", "source", "limits"}
        missing = required - set(row)
        if missing:
            raise ObservationError(f"local observation missing keys: {sorted(missing)}")
        if row["id"] in seen:
            raise ObservationError(f"duplicate local observation id: {row['id']}")
        seen.add(row["id"])
        if row["organId"] not in organ_ids:
            raise ObservationError(f"local observation references unknown organ: {row['organId']}")
        if parse_time(row["observedAt"]) is None:
            raise ObservationError(f"invalid local observedAt: {row['id']}")
        clean = {
            "id": str(row["id"]),
            "organId": str(row["organId"]),
            "observedAt": str(row["observedAt"]),
            "kind": str(row["kind"]),
            "state": str(row["state"]),
            "claim": str(row["claim"]),
            "source": str(row["source"]),
            "limits": str(row["limits"]),
            "evidenceRefs": [str(item) for item in row.get("evidenceRefs", [])],
        }
        accepted.append(clean)
    return sorted(accepted, key=lambda row: (row["organId"], row["observedAt"], row["id"]))


def latest_workflows(raw_runs: dict[str, Any]) -> list[dict[str, Any]]:
    runs = raw_runs.get("workflow_runs", []) if isinstance(raw_runs, dict) else []
    if not isinstance(runs, list):
        return []
    sorted_runs = sorted(runs, key=lambda row: row.get("created_at") or "", reverse=True)
    latest: dict[str, dict[str, Any]] = {}
    for run in sorted_runs:
        key = str(run.get("workflow_id") or run.get("name") or run.get("id"))
        if key in latest:
            continue
        latest[key] = {
            "id": run.get("id"),
            "name": run.get("name") or f"workflow-{key}",
            "event": run.get("event"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "headSha": run.get("head_sha"),
            "createdAt": run.get("created_at"),
            "updatedAt": run.get("updated_at"),
            "url": run.get("html_url"),
        }
    return sorted(latest.values(), key=lambda row: (str(row.get("name")), str(row.get("id"))))


def tree_signals(raw_tree: dict[str, Any]) -> dict[str, Any]:
    rows = raw_tree.get("tree", []) if isinstance(raw_tree, dict) else []
    paths = {str(row.get("path")) for row in rows if isinstance(row, dict) and row.get("type") == "blob"}
    upper = {path.upper(): path for path in paths}
    has_readme = any(path == "README" or path.startswith("README.") for path in upper)
    has_license = any(path == "LICENSE" or path.startswith("LICENSE.") or path == "COPYING" for path in upper)
    succession_names = {"CONTINUITY.MD", "AGENTS.MD", "CLAUDE.MD", "MAINTAINERS.MD", "CONTRIBUTING.MD"}
    succession = sorted(path for path in paths if path.upper() in succession_names)
    workflows = sorted(path for path in paths if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")))
    return {
        "readme": has_readme,
        "license": has_license,
        "successionFiles": succession,
        "workflowFiles": workflows,
        "treeTruncated": bool(raw_tree.get("truncated")),
    }


def repository_findings(repository: dict[str, Any], rules: SourceRules, now: datetime) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(code: str, severity: str, summary: str, refs: list[str] | None = None) -> None:
        findings.append({"code": code, "severity": severity, "summary": summary, "sourceRefs": refs or []})

    full_name = repository["fullName"]
    if repository.get("archived"):
        add("repository_archived", "critical", f"{full_name} is archived.", [repository.get("url")])
    head_age = repository.get("headAgeDays")
    if isinstance(head_age, int) and head_age > rules.stale_commit_days:
        add("default_branch_stale", "attention", f"{full_name} default branch has no commit for {head_age} days.", [repository.get("commitUrl")])
    signals = repository.get("signals", {})
    if not signals.get("readme"):
        add("readme_absent", "attention", f"{full_name} has no root README in the observed tree.")
    if not signals.get("license") and not repository.get("license"):
        add("license_absent", "attention", f"{full_name} exposes no repository license or root license file.")
    if not signals.get("successionFiles"):
        add("succession_record_absent", "attention", f"{full_name} has no root continuity, agent, maintainer, or contribution handoff file.")
    workflows = repository.get("workflows", [])
    if not workflows and not signals.get("workflowFiles"):
        add("workflow_absent", "attention", f"{full_name} has no observed workflow run or workflow file.")
    for workflow in workflows:
        conclusion = workflow.get("conclusion")
        status = workflow.get("status")
        age = age_days(workflow.get("updatedAt") or workflow.get("createdAt"), now)
        if conclusion in BAD_WORKFLOW_CONCLUSIONS:
            add("workflow_not_green", "critical", f"{full_name}: {workflow.get('name')} concluded {conclusion}.", [workflow.get("url")])
        elif status and status != "completed":
            add("workflow_pending", "attention", f"{full_name}: {workflow.get('name')} is {status}.", [workflow.get("url")])
        elif isinstance(age, int) and age > rules.stale_workflow_days:
            add("workflow_stale", "attention", f"{full_name}: latest {workflow.get('name')} receipt is {age} days old.", [workflow.get("url")])
    for pull in repository.get("openPullRequests", []):
        age = pull.get("ageDays")
        if pull.get("draft") and isinstance(age, int) and age > rules.stale_draft_days:
            add("stale_draft_pr", "attention", f"{full_name} draft PR #{pull.get('number')} has remained open for {age} days.", [pull.get("url")])
    if not repository.get("latestTag"):
        add("release_tag_absent", "attention", f"{full_name} has no observed repository tag.")
    return sorted(findings, key=lambda row: (row["severity"], row["code"], row["summary"]))


def collect_repository(
    provider: Provider,
    full_name: str,
    requested_ref: str | None,
    rules: SourceRules,
    now: datetime,
) -> dict[str, Any]:
    repo = provider.repository(full_name)
    default_branch = str(repo.get("default_branch") or "main")
    observed_ref = requested_ref or default_branch
    commit = provider.commit(full_name, observed_ref)
    commit_sha = str(commit.get("sha") or "")
    commit_info = commit.get("commit") or {}
    committer = commit_info.get("committer") or {}
    author = commit_info.get("author") or {}
    commit_at = committer.get("date") or author.get("date")
    tree_sha = ((commit_info.get("tree") or {}).get("sha")) or ""
    runs = latest_workflows(provider.runs(full_name, observed_ref))
    pulls_raw = provider.pulls(full_name)
    pulls = []
    for row in pulls_raw[:100]:
        pulls.append(
            {
                "number": row.get("number"),
                "title": row.get("title"),
                "draft": bool(row.get("draft")),
                "createdAt": row.get("created_at"),
                "updatedAt": row.get("updated_at"),
                "ageDays": age_days(row.get("created_at"), now),
                "headSha": ((row.get("head") or {}).get("sha")),
                "headRef": ((row.get("head") or {}).get("ref")),
                "baseRef": ((row.get("base") or {}).get("ref")),
                "url": row.get("html_url"),
            }
        )
    tags_raw = provider.tags(full_name)
    tags = [{"name": row.get("name"), "sha": ((row.get("commit") or {}).get("sha"))} for row in tags_raw[:10]]
    signals = tree_signals(provider.tree(full_name, tree_sha)) if tree_sha else {
        "readme": False,
        "license": False,
        "successionFiles": [],
        "workflowFiles": [],
        "treeTruncated": True,
    }
    license_value = repo.get("license") or {}
    output = {
        "fullName": full_name,
        "url": repo.get("html_url") or f"https://github.com/{full_name}",
        "visibility": repo.get("visibility") or ("private" if repo.get("private") else "public"),
        "archived": bool(repo.get("archived")),
        "fork": bool(repo.get("fork")),
        "defaultBranch": default_branch,
        "observedRef": observed_ref,
        "headSha": commit_sha,
        "headAt": commit_at,
        "headAgeDays": age_days(commit_at, now),
        "commitUrl": commit.get("html_url"),
        "license": license_value.get("spdx_id") or license_value.get("key") or None,
        "latestTag": tags[0]["name"] if tags else None,
        "tags": tags,
        "workflows": runs,
        "openPullRequests": sorted(pulls, key=lambda row: (row.get("number") or 0)),
        "signals": signals,
        "source": {
            "provider": "github",
            "repositoryApi": repo.get("url"),
            "collectedRef": observed_ref,
        },
    }
    output["findings"] = repository_findings(output, rules, now)
    return output


def compile_observations(
    sources: dict[str, Any],
    local: dict[str, Any],
    provider: Provider,
    now: datetime,
) -> dict[str, Any]:
    source_rows, rules = validate_sources(sources)
    organ_ids = {row["organId"] for row in source_rows}
    local_rows = validate_local(local, organ_ids)
    local_by_organ: dict[str, list[dict[str, Any]]] = {organ_id: [] for organ_id in organ_ids}
    for row in local_rows:
        local_by_organ[row["organId"]].append(row)

    organs: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for source_row in sorted(source_rows, key=lambda row: row["organId"]):
        repositories: list[dict[str, Any]] = []
        aggregate_findings: list[dict[str, Any]] = []
        for repository in sorted(source_row["repositories"], key=lambda row: row["fullName"]):
            try:
                observed = collect_repository(provider, repository["fullName"], repository.get("ref"), rules, now)
                repositories.append(observed)
                aggregate_findings.extend(observed["findings"])
            except ObservationError as exc:
                failure = {
                    "organId": source_row["organId"],
                    "fullName": repository["fullName"],
                    "error": str(exc),
                }
                unavailable.append(failure)
                aggregate_findings.append(
                    {
                        "code": "repository_unavailable",
                        "severity": "critical",
                        "summary": f"{repository['fullName']} could not be observed: {exc}",
                        "sourceRefs": [],
                    }
                )
        organs.append(
            {
                "organId": source_row["organId"],
                "repositories": repositories,
                "localObservations": local_by_organ.get(source_row["organId"], []),
                "findings": sorted(aggregate_findings, key=lambda row: (row["severity"], row["code"], row["summary"])),
            }
        )

    stable = {
        "format": FORMAT,
        "source": {
            "sourcesFormat": SOURCES_FORMAT,
            "localFormat": LOCAL_FORMAT,
            "provider": "github",
            "rules": {
                "staleCommitDays": rules.stale_commit_days,
                "staleDraftDays": rules.stale_draft_days,
                "staleWorkflowDays": rules.stale_workflow_days,
            },
        },
        "organs": organs,
        "unavailable": sorted(unavailable, key=lambda row: (row["organId"], row["fullName"])),
    }
    result = {
        "format": FORMAT,
        "generatedAt": iso_z(now),
        "sourceDigest": "organobs1_" + digest(stable),
        **{key: value for key, value in stable.items() if key != "format"},
    }
    assert_no_authority_mutation(result)
    return result


def write_outputs(value: dict[str, Any], output: Path, js_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    js_output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(text, encoding="utf-8", newline="\n")
    js_output.write_text("window.AXM_ORGAN_OBSERVATIONS = " + text.rstrip() + ";\n", encoding="utf-8", newline="\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--observed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--js-output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--now", help="ISO-8601 time override for deterministic tests")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        sources = load_json(args.sources, SOURCES_FORMAT)
        local = load_json(args.observed, LOCAL_FORMAT)
        now = parse_time(args.now) if args.now else utc_now()
        if now is None:
            raise ObservationError("--now must be valid ISO-8601")
        if args.fixture:
            provider: Provider = FixtureProvider(load_json(args.fixture))
        else:
            provider = GitHubProvider(os.environ.get(args.token_env))
        result = compile_observations(sources, local, provider, now)
        write_outputs(result, args.output, args.js_output)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"PASS: {len(result['organs'])} organs observed, "
        f"{sum(len(row['repositories']) for row in result['organs'])} repositories available, "
        f"{len(result['unavailable'])} unavailable, {result['sourceDigest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


PRIMARY_TOPIC_LABELS = {
    "device": "adb device handling",
    "runtime": "runtime flow handling",
    "battle-runtime": "battle runtime logic",
    "command-card": "command card recognition",
    "support-recognition": "support recognition",
    "perception": "perception detection",
    "shared": "shared configuration",
    "scripts": "project scripts",
    "skill": "git commit skill",
    "docs": "project documentation",
    "tests": "targeted test coverage",
    "config": "runtime configuration",
    "assets": "ui assets",
    "root-meta": "repository metadata",
}

PRIMARY_TOPIC_TYPES = {
    "docs": "docs",
    "tests": "test",
    "config": "chore",
    "assets": "chore",
    "root-meta": "chore",
}

ALLOW_EMPTY_VERIFICATION_TOPICS = {"docs"}

TOPIC_TEST_PATTERNS = {
    "device": ['uv run python -m unittest discover -s tests -p "test_adb_controller.py" -v'],
    "runtime": ['uv run python -m unittest discover -s tests -p "test_runtime*.py" -v'],
    "battle-runtime": ['uv run python -m unittest discover -s tests -p "test_battle*.py" -v'],
    "command-card": ['uv run python -m unittest discover -s tests -p "test_command_card*.py" -v'],
    "support-recognition": ['uv run python -m unittest discover -s tests -p "test_support*.py" -v'],
    "perception": ["uv run python -m unittest discover -s tests -v"],
    "shared": ["uv run python -m unittest discover -s tests -v"],
    "scripts": ["uv run python -m unittest discover -s tests -v"],
    "skill": ['uv run python -m unittest discover -s tests -p "test_git_commit_skill.py" -v'],
    "config": ["uv run python -m unittest discover -s tests -v"],
    "root-meta": ["uv run python -m unittest discover -s tests -v"],
}

IGNORED_PATHS = {
    "TODO.md": "local_notes",
    "Pro项目指导文档.md": "local_notes",
    "DevLog.md": "local_notes",
    "DevRecord.md": "local_notes",
}


def parse_status_line(line: str) -> dict[str, str] | None:
    line = line.rstrip("\n")
    if not line:
        return None
    if line.startswith("?? "):
        path = line[3:].strip()
        return {"path": path, "index_status": "?", "worktree_status": "?"}
    if len(line) < 4:
        raise ValueError(f"unsupported git status line: {line!r}")
    path = line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()
    return {
        "path": path,
        "index_status": line[0],
        "worktree_status": line[1],
    }


def parse_porcelain_z(data: bytes) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not data:
        return entries
    parts = data.split(b"\0")
    index = 0
    while index < len(parts):
        part = parts[index]
        index += 1
        if not part:
            continue
        if part.startswith(b"?? "):
            entries.append(
                {
                    "path": part[3:].decode("utf-8"),
                    "index_status": "?",
                    "worktree_status": "?",
                }
            )
            continue
        if len(part) < 4:
            raise ValueError(f"unsupported git status entry: {part!r}")
        x = chr(part[0])
        y = chr(part[1])
        path = part[3:].decode("utf-8")
        entries.append(
            {
                "path": path,
                "index_status": x,
                "worktree_status": y,
            }
        )
        if x in {"R", "C"} or y in {"R", "C"}:
            index += 1
    return entries


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def classify_path(path: str) -> dict[str, str]:
    normalized = normalize_path(path)
    if normalized.startswith("core/device/"):
        return {"kind": "primary", "topic": "device"}
    if normalized.startswith("core/runtime/"):
        return {"kind": "primary", "topic": "runtime"}
    if normalized.startswith("core/battle_runtime/"):
        return {"kind": "primary", "topic": "battle-runtime"}
    if normalized.startswith("core/command_card_recognition/"):
        return {"kind": "primary", "topic": "command-card"}
    if normalized.startswith("core/support_recognition/"):
        return {"kind": "primary", "topic": "support-recognition"}
    if normalized.startswith("core/perception/"):
        return {"kind": "primary", "topic": "perception"}
    if normalized.startswith("core/shared/"):
        return {"kind": "primary", "topic": "shared"}
    if normalized.startswith("scripts/"):
        return {"kind": "primary", "topic": "scripts"}
    if normalized.startswith("skill/"):
        return {"kind": "primary", "topic": "skill"}
    if normalized.startswith("tests/"):
        return {"kind": "support", "topic": "tests"}
    if normalized.startswith("config/"):
        return {"kind": "support", "topic": "config"}
    if normalized.startswith("assets/"):
        return {"kind": "support", "topic": "assets"}
    if normalized.startswith("test_image/"):
        return {"kind": "support", "topic": "assets"}
    if normalized.startswith("docs/"):
        return {"kind": "support", "topic": "docs"}
    if normalized in {
        "README.md",
        "PROJECT_HANDOFF.md",
        "DevGuide.md",
        "AGENTS.md",
        "TODO.md",
        "main.py",
        "pyproject.toml",
        "uv.lock",
        ".gitignore",
    } or normalized.endswith(".md"):
        return {"kind": "support", "topic": "docs"}
    return {"kind": "support", "topic": "root-meta"}


def infer_test_topic(path: str) -> str | None:
    name = Path(path).name.lower()
    if "git_commit_skill" in name:
        return "skill"
    if "command_card" in name or "card_plan" in name:
        return "command-card"
    if "adb" in name or "device" in name:
        return "device"
    if "startup_check" in name:
        return "runtime"
    if "action_executor" in name:
        return "battle-runtime"
    if "state_detection" in name:
        return "perception"
    if "support_verifier" in name:
        return "support-recognition"
    if "runtime" in name or "workflow" in name or "session" in name or "handler" in name:
        return "runtime"
    if "battle" in name or "planner" in name or "snapshot" in name:
        return "battle-runtime"
    if "support" in name:
        return "support-recognition"
    if "perception" in name or "state_detector" in name:
        return "perception"
    if "config" in name or "resource" in name:
        return "shared"
    return None


def make_workspace_record(entry: dict[str, str]) -> dict[str, Any]:
    classification = classify_path(entry["path"])
    return {
        "path": entry["path"],
        "index_status": entry["index_status"],
        "worktree_status": entry["worktree_status"],
        "is_untracked": entry["index_status"] == "?" and entry["worktree_status"] == "?",
        "kind": classification["kind"],
        "topic": classification["topic"],
        "ignored": normalize_path(entry["path"]) in IGNORED_PATHS,
    }


def ensure_group(groups: dict[str, dict[str, Any]], topic: str) -> dict[str, Any]:
    if topic not in groups:
        groups[topic] = {
            "group_id": topic,
            "primary_topic": topic,
            "files": [],
            "support_files": [],
            "suggested_type": "",
            "suggested_summary": "",
            "suggested_verification_commands": [],
            "blocking_reasons": [],
        }
    return groups[topic]


def attach_support_file(
    record: dict[str, Any],
    primary_topics: set[str],
) -> str | None:
    topic = record["topic"]
    if topic == "tests":
        inferred = infer_test_topic(record["path"])
        if inferred and inferred in primary_topics:
            return inferred
        if len(primary_topics) == 1:
            return next(iter(primary_topics))
        return None
    if topic in {"docs", "config", "assets", "root-meta"}:
        if len(primary_topics) == 1:
            return next(iter(primary_topics))
        return None
    return None


def suggest_review_topics(
    record: dict[str, Any],
    primary_topics: set[str],
) -> list[str]:
    candidate_topics: list[str] = []
    if record["topic"] == "tests":
        inferred = infer_test_topic(record["path"])
        if inferred:
            candidate_topics.append(inferred)
    elif record["topic"] in {"docs", "config", "assets", "root-meta"}:
        candidate_topics.append(record["topic"])
    candidate_topics.extend(sorted(primary_topics))

    unique_topics: list[str] = []
    for topic in candidate_topics:
        if topic and topic not in unique_topics:
            unique_topics.append(topic)
    return unique_topics


def build_test_commands(paths: list[str]) -> list[str]:
    commands: list[str] = []
    for path in sorted(paths):
        name = Path(path).name
        commands.append(
            f'uv run python -m unittest discover -s tests -p "{name}" -v'
        )
    return commands


def suggest_verification_commands(topic: str, files: list[str], support_files: list[str]) -> list[str]:
    test_files = [path for path in [*files, *support_files] if normalize_path(path).startswith("tests/")]
    if topic == "docs":
        return []
    if topic == "tests":
        return build_test_commands(files)
    if topic == "assets":
        return []
    if test_files:
        return build_test_commands(test_files)
    return TOPIC_TEST_PATTERNS.get(topic, [])


def suggest_commit_type(topic: str) -> str:
    return PRIMARY_TOPIC_TYPES.get(topic, "fix")


def suggest_commit_summary(topic: str) -> str:
    commit_type = suggest_commit_type(topic)
    label = PRIMARY_TOPIC_LABELS.get(topic, topic.replace("-", " "))
    return f"{commit_type}: update {label}"


def finalize_groups(groups: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []
    for topic in sorted(groups):
        group = groups[topic]
        group["files"] = sorted(group["files"])
        group["support_files"] = sorted(group["support_files"])
        group["suggested_type"] = suggest_commit_type(topic)
        group["suggested_summary"] = suggest_commit_summary(topic)
        group["suggested_verification_commands"] = suggest_verification_commands(
            topic,
            group["files"],
            group["support_files"],
        )
        if (
            not group["suggested_verification_commands"]
            and topic not in ALLOW_EMPTY_VERIFICATION_TOPICS
        ):
            group["blocking_reasons"].append("missing_verification_commands")
        finalized.append(group)
    return finalized


def inspect_status_entries(entries: list[dict[str, str]]) -> dict[str, Any]:
    workspace_files = sorted(
        (make_workspace_record(entry) for entry in entries),
        key=lambda item: item["path"],
    )
    ignored_files = sorted(
        [
            {
                "path": record["path"],
                "reason": IGNORED_PATHS[normalize_path(record["path"])],
            }
            for record in workspace_files
            if record["ignored"]
        ],
        key=lambda item: item["path"],
    )
    partially_staged_files = sorted(
        {
            entry["path"]
            for entry in entries
            if entry["index_status"] not in {" ", "?"}
            and entry["worktree_status"] not in {" ", "?"}
        }
    )
    if not workspace_files:
        return {
            "workspace_files": [],
            "proposed_groups": [],
            "review_candidates": [],
            "unassigned_files": [],
            "ignored_files": [],
            "partially_staged_files": [],
            "global_blocking_reasons": ["no_workspace_changes"],
        }

    groups: dict[str, dict[str, Any]] = {}
    review_candidates: list[dict[str, Any]] = []
    unassigned_files: list[dict[str, str]] = []

    active_records = [record for record in workspace_files if not record["ignored"]]
    primary_records = [record for record in active_records if record["kind"] == "primary"]
    support_records = [record for record in active_records if record["kind"] == "support"]
    primary_topics = {record["topic"] for record in primary_records}

    if primary_records:
        for record in primary_records:
            ensure_group(groups, record["topic"])["files"].append(record["path"])
        for record in support_records:
            attached_topic = attach_support_file(record, primary_topics)
            if attached_topic:
                ensure_group(groups, attached_topic)["support_files"].append(record["path"])
            else:
                candidate_topics = suggest_review_topics(record, primary_topics)
                if candidate_topics:
                    review_candidates.append(
                        {
                            "path": record["path"],
                            "reason": "shared_support_file",
                            "candidate_topics": candidate_topics,
                        }
                    )
                else:
                    unassigned_files.append(
                        {"path": record["path"], "reason": "shared_support_file"}
                    )
    else:
        for record in support_records:
            ensure_group(groups, record["topic"])["files"].append(record["path"])

    proposed_groups = finalize_groups(groups)
    global_blocking_reasons: list[str] = []
    if partially_staged_files:
        global_blocking_reasons.append("partial_staging_present")
    if unassigned_files:
        global_blocking_reasons.append("unassigned_files")
    if any(group["blocking_reasons"] for group in proposed_groups):
        global_blocking_reasons.append("group_missing_verification_commands")
    if not proposed_groups and not review_candidates:
        global_blocking_reasons.append("no_commit_candidates")

    return {
        "workspace_files": workspace_files,
        "proposed_groups": proposed_groups,
        "review_candidates": sorted(review_candidates, key=lambda item: item["path"]),
        "unassigned_files": sorted(unassigned_files, key=lambda item: item["path"]),
        "ignored_files": ignored_files,
        "partially_staged_files": partially_staged_files,
        "global_blocking_reasons": global_blocking_reasons,
    }


def collect_repo_status(repo: Path) -> list[dict[str, str]]:
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "-z"],
        check=True,
        capture_output=True,
    )
    return parse_porcelain_z(result.stdout)


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"workspace_files: {[item['path'] for item in report['workspace_files']]}",
        f"proposed_groups: {[group['group_id'] for group in report['proposed_groups']]}",
        f"review_candidates: {report['review_candidates']}",
        f"unassigned_files: {report['unassigned_files']}",
        f"ignored_files: {report['ignored_files']}",
        f"partially_staged_files: {report['partially_staged_files']}",
        f"global_blocking_reasons: {report['global_blocking_reasons']}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect current git status and propose grouped local commits."
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository root to inspect. Defaults to current directory.",
    )
    parser.add_argument(
        "--status-json",
        help="Read mocked status entries from a JSON file instead of calling git.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format. Defaults to text.",
    )
    args = parser.parse_args()

    if args.status_json:
        entries = json.loads(Path(args.status_json).read_text(encoding="utf-8"))
    else:
        entries = collect_repo_status(Path(args.repo).resolve())

    report = inspect_status_entries(entries)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Checks docs for time-based and path-based staleness. Outputs a JSON report."""

import argparse
import glob
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import yaml

from frontmatter import parse_frontmatter


def run_git_log(since: str, paths: list[str], repo_root: str) -> str:
    """Run git log --since for the given paths. Returns stdout."""
    cmd = ["git", "log", "--oneline", f"--since={since}", "--"] + paths
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def check_time_staleness(last_validated: str, max_age_days: int) -> dict | None:
    """Check if a doc is time-stale. Returns a dict with reason if stale, None otherwise.

    Raises ``ValueError`` if *max_age_days* cannot be converted to ``int``.
    """
    # Validate max_age_days is numeric
    max_age_days = int(max_age_days)

    try:
        validated_date = date.fromisoformat(last_validated)
    except (ValueError, TypeError):
        return {"reason": "time", "detail": f"Invalid lastValidated: {last_validated}"}

    threshold = validated_date + timedelta(days=max_age_days)
    if date.today() >= threshold:
        days_over = (date.today() - threshold).days
        return {
            "reason": "time",
            "detail": f"Last validated {last_validated}, {days_over} days past {max_age_days}-day threshold",
        }
    return None


def check_path_staleness(paths: list[str], last_validated: str, repo_root: str) -> dict | None:
    """Check if code paths have changed since lastValidated. Returns dict if stale."""
    if not paths:
        return None

    output = run_git_log(last_validated, paths, repo_root)
    if output:
        commit_count = len(output.strip().split("\n"))
        return {
            "reason": "paths",
            "detail": f"{commit_count} commit(s) touching tracked paths since {last_validated}",
        }
    return None


def check_all_docs(docs_dir: str, default_max_age: int, repo_root: str) -> list[dict]:
    """Check all docs for staleness. Returns list of flagged doc reports."""
    pattern = os.path.join(docs_dir, "*.md")
    files = sorted(glob.glob(pattern))

    flagged = []
    for filepath in files:
        fm = parse_frontmatter(filepath)
        if not fm:
            continue

        last_validated = fm.get("lastValidated")
        if not last_validated:
            continue

        max_age = fm.get("maxAgeDays", default_max_age)
        paths = fm.get("paths", [])

        # Validate maxAgeDays is numeric; skip docs with bad values
        try:
            max_age_int = int(max_age)
        except (ValueError, TypeError):
            print(f"Warning: skipping {filepath} — maxAgeDays is not numeric: {max_age!r}", file=sys.stderr)
            continue

        time_result = check_time_staleness(str(last_validated), max_age_int)
        path_result = check_path_staleness(paths, str(last_validated), repo_root)

        if time_result or path_result:
            reasons = []
            details = []
            if time_result:
                reasons.append("time")
                details.append(time_result["detail"])
            if path_result:
                reasons.append("paths")
                details.append(path_result["detail"])

            flagged.append({
                "file": os.path.relpath(filepath, repo_root),
                "title": fm.get("title", os.path.basename(filepath)),
                "reason": " + ".join(reasons),
                "details": details,
                "lastValidated": str(last_validated),
                "maxAgeDays": max_age_int,
            })

    return flagged


def load_default_max_age(repo_root: str) -> int:
    """Load default maxAgeDays from .agentsrc.yaml, falling back to 90."""
    config_path = os.path.join(repo_root, ".agentsrc.yaml")
    if not os.path.exists(config_path):
        return 90

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("defaults", {}).get("maxAgeDays", 90)
    except (yaml.YAMLError, TypeError):
        return 90


def main():
    parser = argparse.ArgumentParser(description="Check docs for staleness.")
    parser.add_argument(
        "--docs-dir",
        default="docs",
        help="Path to docs directory (default: docs)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to repo root (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report without taking any action.",
    )
    args = parser.parse_args()

    default_max_age = load_default_max_age(args.repo_root)
    results = check_all_docs(args.docs_dir, default_max_age, args.repo_root)

    report = json.dumps(results, indent=2, ensure_ascii=False)
    print(report)

    if not args.dry_run and results:
        report_path = os.path.join(args.repo_root, "staleness-report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()

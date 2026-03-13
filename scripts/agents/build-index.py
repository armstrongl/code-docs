#!/usr/bin/env python3
"""Reads frontmatter from docs/*.md and regenerates the AGENTS.md index table."""

import argparse
import glob
import json
import os
import re
import sys

import yaml

from frontmatter import parse_frontmatter


START_MARKER = "<!-- AGENTS-INDEX-START -->"
END_MARKER = "<!-- AGENTS-INDEX-END -->"

TABLE_HEADER = "| Doc | When to load | Last validated | Status | Paths |\n|---|---|---|---|---|"


def build_table_row(filepath: str, frontmatter: dict, status: str = "current") -> str:
    """Build one Markdown table row from a doc's filepath and frontmatter.

    Args:
        filepath: Relative path to the doc (used in the link).
        frontmatter: Parsed frontmatter dict.
        status: Staleness status string. One of ``current``,
            ``stale (time)``, ``stale (paths)``, ``stale (time + paths)``.
            Defaults to ``current``.
    """
    title = frontmatter.get("title")
    description = frontmatter.get("description")
    last_validated = frontmatter.get("lastValidated")
    max_age_days = frontmatter.get("maxAgeDays")

    # Check for missing required fields — all four are required per the spec
    missing = []
    if not title:
        missing.append("title")
    if not description:
        missing.append("description")
    if not last_validated:
        missing.append("lastValidated")
    if max_age_days is None:
        missing.append("maxAgeDays")

    if missing:
        display_title = title or os.path.basename(filepath)
        return (
            f"| [{display_title}]({filepath}) "
            f"| Missing fields: {', '.join(missing)} "
            f"| {last_validated or 'missing'} "
            f"| {status} "
            f"| |"
        )

    paths = frontmatter.get("paths", [])
    paths_cell = "<br>".join(f"`{p}`" for p in paths) if paths else ""

    if paths_cell:
        paths_segment = f"| {paths_cell} |"
    else:
        paths_segment = "| |"

    return (
        f"| [{title}]({filepath}) "
        f"| {description} "
        f"| {last_validated} "
        f"| {status} "
        f"{paths_segment}"
    )


def build_index_table(docs_dir: str, staleness_data: dict | None = None) -> str:
    """Build the full index table from all Markdown files in a directory.

    Args:
        docs_dir: Path to the docs directory.
        staleness_data: Optional dict keyed by relative filepath mapping to a
            status string (e.g. ``"stale (time)"``). When provided, the status
            value is passed through to each row. Defaults to ``None`` which
            means every row gets ``"current"``.
    """
    if staleness_data is None:
        staleness_data = {}

    pattern = os.path.join(docs_dir, "*.md")
    files = sorted(glob.glob(pattern))

    rows = []
    for filepath in files:
        fm = parse_frontmatter(filepath)
        if not fm:
            continue
        # Use path relative to repo root (parent of docs_dir)
        rel_path = os.path.relpath(filepath, os.path.dirname(docs_dir))
        status = staleness_data.get(rel_path, "current")
        rows.append((fm.get("title", ""), build_table_row(rel_path, fm, status=status)))

    # Sort alphabetically by title
    rows.sort(key=lambda r: r[0].lower())

    lines = [TABLE_HEADER] + [row for _, row in rows]
    return "\n".join(lines) + "\n"


def replace_index_in_file(filepath: str, table: str) -> None:
    """Replace content between index markers in a file. Appends markers if missing."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER in content and END_MARKER in content:
        pattern = re.compile(
            re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
            re.DOTALL,
        )
        new_content = pattern.sub(
            f"{START_MARKER}\n\n{table}\n{END_MARKER}",
            content,
        )
    else:
        new_content = content.rstrip() + f"\n\n{START_MARKER}\n\n{table}\n{END_MARKER}\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)


def _load_staleness_report(path: str) -> dict:
    """Load a staleness-report.json and return a dict keyed by filepath.

    The staleness report is a JSON list of objects, each with a ``file`` key
    (relative path) and a ``reason`` key (e.g. ``"time"``, ``"paths"``,
    ``"time + paths"``). This function converts it into the format expected
    by ``build_index_table``.
    """
    if not path or not os.path.isfile(path):
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    staleness_data = {}
    for entry in data:
        filepath = entry.get("file", "")
        reason = entry.get("reason", "")
        if filepath and reason:
            staleness_data[filepath] = f"stale ({reason})"
    return staleness_data


def main():
    parser = argparse.ArgumentParser(description="Regenerate AGENTS.md index table.")
    parser.add_argument(
        "--docs-dir",
        default="docs",
        help="Path to docs directory (default: docs)",
    )
    parser.add_argument(
        "--agents-md",
        default="AGENTS.md",
        help="Path to AGENTS.md (default: AGENTS.md)",
    )
    parser.add_argument(
        "--staleness-report",
        default=None,
        help="Path to staleness-report.json (optional). When provided, the "
        "status column reflects staleness signals from the report.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the table without writing to file.",
    )
    args = parser.parse_args()

    staleness_data = _load_staleness_report(args.staleness_report)
    table = build_index_table(args.docs_dir, staleness_data=staleness_data)

    if args.dry_run:
        print(table)
        return

    replace_index_in_file(args.agents_md, table)
    print(f"Updated {args.agents_md}")


if __name__ == "__main__":
    main()

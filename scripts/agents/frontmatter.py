#!/usr/bin/env python3
"""Shared frontmatter parser used by build-index.py and check-staleness.py."""

import re

import yaml


def parse_frontmatter(filepath: str) -> dict:
    """Extract YAML frontmatter from a Markdown file.

    Returns the parsed frontmatter as a dict, or an empty dict if no valid
    frontmatter is found. Handles UTF-8 BOM and both LF and CRLF line endings.
    Defaults ``paths`` and ``tags`` to empty lists when absent.
    """
    with open(filepath, "r", encoding="utf-8-sig") as f:
        content = f.read()

    match = re.match(r"^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
    if not match:
        return {}

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}

    if not isinstance(fm, dict):
        return {}

    # Normalize optional list fields
    fm.setdefault("paths", [])
    fm.setdefault("tags", [])
    return fm

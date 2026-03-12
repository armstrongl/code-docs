"""Tests for build-index.py — the AGENTS.md index table generator."""

import importlib
import json
import os
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "agents"))
# The script is named build-index.py (hyphen) which isn't a valid Python
# identifier, so we use importlib to load it.
_mod = importlib.import_module("build-index")
build_table_row = _mod.build_table_row
build_index_table = _mod.build_index_table
replace_index_in_file = _mod.replace_index_in_file


class TestBuildTableRow:
    def test_full_row_with_status_default(self):
        row = build_table_row(
            filepath="docs/auth-flow.md",
            frontmatter={
                "title": "Auth flow",
                "description": "Load when modifying auth.",
                "lastValidated": "2025-03-01",
                "maxAgeDays": 60,
                "paths": ["src/auth/**", "src/middleware/session.ts"],
            },
        )
        assert row == (
            "| [Auth flow](docs/auth-flow.md) "
            "| Load when modifying auth. "
            "| 2025-03-01 "
            "| current "
            "| `src/auth/**`<br>`src/middleware/session.ts` |"
        )

    def test_full_row_with_explicit_status(self):
        row = build_table_row(
            filepath="docs/auth-flow.md",
            frontmatter={
                "title": "Auth flow",
                "description": "Load when modifying auth.",
                "lastValidated": "2025-03-01",
                "maxAgeDays": 60,
                "paths": ["src/auth/**"],
            },
            status="stale (time)",
        )
        assert "| stale (time) |" in row

    def test_status_column_stale_paths(self):
        row = build_table_row(
            filepath="docs/auth-flow.md",
            frontmatter={
                "title": "Auth flow",
                "description": "Load when modifying auth.",
                "lastValidated": "2025-03-01",
                "maxAgeDays": 60,
                "paths": ["src/auth/**"],
            },
            status="stale (paths)",
        )
        assert "| stale (paths) |" in row

    def test_status_column_stale_time_plus_paths(self):
        row = build_table_row(
            filepath="docs/auth-flow.md",
            frontmatter={
                "title": "Auth flow",
                "description": "Load when modifying auth.",
                "lastValidated": "2025-03-01",
                "maxAgeDays": 60,
                "paths": ["src/auth/**"],
            },
            status="stale (time + paths)",
        )
        assert "| stale (time + paths) |" in row

    def test_empty_paths(self):
        row = build_table_row(
            filepath="docs/overview.md",
            frontmatter={
                "title": "Overview",
                "description": "Load when orienting.",
                "lastValidated": "2025-01-01",
                "maxAgeDays": 90,
                "paths": [],
            },
        )
        assert "| |" in row  # empty paths cell

    def test_missing_required_field_title(self):
        row = build_table_row(
            filepath="docs/broken.md",
            frontmatter={
                "description": "Load when testing.",
                "lastValidated": "2025-01-01",
                "maxAgeDays": 90,
            },
        )
        assert "missing fields" in row.lower()
        assert "title" in row.lower()

    def test_missing_required_field_description(self):
        row = build_table_row(
            filepath="docs/broken.md",
            frontmatter={
                "title": "Broken",
                "lastValidated": "2025-01-01",
                "maxAgeDays": 90,
            },
        )
        assert "missing fields" in row.lower()
        assert "description" in row.lower()

    def test_missing_required_field_lastvalidated(self):
        row = build_table_row(
            filepath="docs/broken.md",
            frontmatter={
                "title": "Broken",
                "description": "Load when testing.",
                "maxAgeDays": 90,
            },
        )
        assert "missing fields" in row.lower()
        assert "lastvalidated" in row.lower()

    def test_missing_required_field_maxagedays(self):
        row = build_table_row(
            filepath="docs/broken.md",
            frontmatter={
                "title": "Broken",
                "description": "Load when testing.",
                "lastValidated": "2025-01-01",
            },
        )
        assert "missing fields" in row.lower()
        assert "maxagedays" in row.lower()


class TestBuildIndexTable:
    def test_sorted_alphabetically_by_title(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        for name, title in [("z-doc.md", "Zebra"), ("a-doc.md", "Apple")]:
            (docs_dir / name).write_text(textwrap.dedent(f"""\
                ---
                title: "{title}"
                description: "Load when testing."
                lastValidated: "2025-01-01"
                maxAgeDays: 90
                ---

                # {title}
            """))
        table = build_index_table(str(docs_dir))
        lines = table.strip().split("\n")
        # Header + separator + 2 rows = 4 lines
        assert len(lines) == 4
        assert "Apple" in lines[2]
        assert "Zebra" in lines[3]

    def test_table_header_includes_status_column(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "test.md").write_text(textwrap.dedent("""\
            ---
            title: "Test"
            description: "Load when testing."
            lastValidated: "2025-01-01"
            maxAgeDays: 90
            ---

            # Test
        """))
        table = build_index_table(str(docs_dir))
        assert "| Status |" in table

    def test_staleness_data_sets_status(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "stale-doc.md").write_text(textwrap.dedent("""\
            ---
            title: "Stale doc"
            description: "Load when testing."
            lastValidated: "2024-01-01"
            maxAgeDays: 90
            ---

            # Stale doc
        """))
        staleness_data = {
            "docs/stale-doc.md": "stale (time)",
        }
        table = build_index_table(str(docs_dir), staleness_data=staleness_data)
        assert "stale (time)" in table

    def test_no_staleness_data_defaults_to_current(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "fresh.md").write_text(textwrap.dedent("""\
            ---
            title: "Fresh"
            description: "Load when testing."
            lastValidated: "2025-01-01"
            maxAgeDays: 90
            ---

            # Fresh
        """))
        table = build_index_table(str(docs_dir))
        assert "| current |" in table


class TestReplaceIndexInFile:
    def test_replaces_between_markers(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(textwrap.dedent("""\
            Preamble text.

            <!-- AGENTS-INDEX-START -->
            old table content
            <!-- AGENTS-INDEX-END -->
        """))
        new_table = "| Doc | When to load | Last validated | Status | Paths |\n|---|---|---|---|---|\n| [Test](docs/test.md) | Load when testing. | 2025-01-01 | current | |\n"
        replace_index_in_file(str(agents_md), new_table)
        content = agents_md.read_text()
        assert "old table content" not in content
        assert "| [Test](docs/test.md)" in content
        assert "Preamble text." in content

    def test_appends_markers_if_missing(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("Preamble only.\n")
        new_table = "| Doc | When to load | Last validated | Status | Paths |\n|---|---|---|---|---|\n"
        replace_index_in_file(str(agents_md), new_table)
        content = agents_md.read_text()
        assert "<!-- AGENTS-INDEX-START -->" in content
        assert "<!-- AGENTS-INDEX-END -->" in content
        assert "Preamble only." in content

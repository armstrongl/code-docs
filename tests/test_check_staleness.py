"""Tests for check-staleness.py — the doc staleness checker."""

import importlib.util
import json
import os
import sys
import textwrap
from datetime import date, timedelta
from unittest.mock import patch

import pytest

# Ensure scripts/agents is on sys.path so `from frontmatter import ...` works
# when check-staleness.py is loaded.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "agents"))

# Import from hyphenated filename using importlib
_spec = importlib.util.spec_from_file_location(
    "check_staleness",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "agents", "check-staleness.py"),
)
check_staleness = importlib.util.module_from_spec(_spec)
sys.modules["check_staleness"] = check_staleness
_spec.loader.exec_module(check_staleness)

from check_staleness import check_time_staleness, check_path_staleness, check_all_docs


class TestTimeStaleness:
    def test_not_stale(self):
        result = check_time_staleness(
            last_validated=date.today().isoformat(),
            max_age_days=90,
        )
        assert result is None

    def test_stale(self):
        old_date = (date.today() - timedelta(days=100)).isoformat()
        result = check_time_staleness(
            last_validated=old_date,
            max_age_days=90,
        )
        assert result is not None
        assert "time" in result["reason"]

    def test_exactly_at_threshold(self):
        threshold_date = (date.today() - timedelta(days=90)).isoformat()
        result = check_time_staleness(
            last_validated=threshold_date,
            max_age_days=90,
        )
        # At exactly the threshold, should be stale
        assert result is not None

    def test_non_numeric_max_age_days(self):
        """maxAgeDays that cannot be parsed as int should raise ValueError."""
        with pytest.raises(ValueError):
            check_time_staleness(
                last_validated=date.today().isoformat(),
                max_age_days="not-a-number",
            )


class TestPathStaleness:
    def test_no_paths_returns_none(self):
        result = check_path_staleness(
            paths=[],
            last_validated=date.today().isoformat(),
            repo_root="/tmp/fake",
        )
        assert result is None

    @patch("check_staleness.run_git_log")
    def test_no_commits_not_stale(self, mock_git):
        mock_git.return_value = ""
        result = check_path_staleness(
            paths=["src/auth/**"],
            last_validated=date.today().isoformat(),
            repo_root="/tmp/fake",
        )
        assert result is None

    @patch("check_staleness.run_git_log")
    def test_commits_found_is_stale(self, mock_git):
        mock_git.return_value = "abc123 fix auth bug\ndef456 update tokens\n"
        result = check_path_staleness(
            paths=["src/auth/**"],
            last_validated="2025-01-01",
            repo_root="/tmp/fake",
        )
        assert result is not None
        assert "paths" in result["reason"]


class TestCheckAllDocs:
    def test_returns_list_of_flagged_docs(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        old_date = (date.today() - timedelta(days=100)).isoformat()
        (docs_dir / "stale.md").write_text(textwrap.dedent(f"""\
            ---
            title: "Stale doc"
            description: "Load when testing."
            lastValidated: "{old_date}"
            maxAgeDays: 90
            ---

            # Stale doc
        """))
        (docs_dir / "fresh.md").write_text(textwrap.dedent(f"""\
            ---
            title: "Fresh doc"
            description: "Load when testing."
            lastValidated: "{date.today().isoformat()}"
            maxAgeDays: 90
            ---

            # Fresh doc
        """))

        with patch("check_staleness.check_path_staleness", return_value=None):
            results = check_all_docs(str(docs_dir), default_max_age=90, repo_root=str(tmp_path))

        assert len(results) == 1
        assert results[0]["title"] == "Stale doc"

    @patch("check_staleness.run_git_log")
    def test_combined_time_and_paths_staleness(self, mock_git, tmp_path):
        """A doc that is both time-stale and path-stale should report reason 'time + paths'."""
        mock_git.return_value = "abc123 some commit\n"
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        old_date = (date.today() - timedelta(days=100)).isoformat()
        (docs_dir / "both.md").write_text(textwrap.dedent(f"""\
            ---
            title: "Both stale"
            description: "Load when testing."
            lastValidated: "{old_date}"
            maxAgeDays: 90
            paths:
              - "src/auth/**"
            ---

            # Both stale
        """))

        results = check_all_docs(str(docs_dir), default_max_age=90, repo_root=str(tmp_path))

        assert len(results) == 1
        assert results[0]["reason"] == "time + paths"
        assert len(results[0]["details"]) == 2

    def test_non_numeric_maxagedays_skipped(self, tmp_path):
        """A doc with non-numeric maxAgeDays should be skipped gracefully."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "bad.md").write_text(textwrap.dedent("""\
            ---
            title: "Bad maxAgeDays"
            description: "Load when testing."
            lastValidated: "2025-01-01"
            maxAgeDays: "not-a-number"
            ---

            # Bad maxAgeDays
        """))

        with patch("check_staleness.check_path_staleness", return_value=None):
            results = check_all_docs(str(docs_dir), default_max_age=90, repo_root=str(tmp_path))

        # Should not crash; the doc is skipped
        assert len(results) == 0

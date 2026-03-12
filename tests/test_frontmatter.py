"""Tests for the shared frontmatter parser module."""

import os
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "agents"))
from frontmatter import parse_frontmatter


class TestParseFrontmatter:
    def test_extracts_all_fields(self, tmp_path):
        doc = tmp_path / "test.md"
        doc.write_text(textwrap.dedent("""\
            ---
            title: "Auth flow"
            description: "Load when modifying auth."
            lastValidated: "2025-03-01"
            maxAgeDays: 60
            paths:
              - "src/auth/**"
            tags:
              - auth
            ---

            # Auth flow
        """))
        fm = parse_frontmatter(str(doc))
        assert fm["title"] == "Auth flow"
        assert fm["description"] == "Load when modifying auth."
        assert fm["lastValidated"] == "2025-03-01"
        assert fm["maxAgeDays"] == 60
        assert fm["paths"] == ["src/auth/**"]
        assert fm["tags"] == ["auth"]

    def test_missing_optional_fields_default_to_empty_lists(self, tmp_path):
        doc = tmp_path / "test.md"
        doc.write_text(textwrap.dedent("""\
            ---
            title: "Overview"
            description: "Load when orienting."
            lastValidated: "2025-01-01"
            maxAgeDays: 90
            ---

            # Overview
        """))
        fm = parse_frontmatter(str(doc))
        assert fm["paths"] == []
        assert fm["tags"] == []

    def test_no_frontmatter_returns_empty(self, tmp_path):
        doc = tmp_path / "test.md"
        doc.write_text("# Just a heading\n\nSome content.\n")
        fm = parse_frontmatter(str(doc))
        assert fm == {}

    def test_crlf_line_endings(self, tmp_path):
        doc = tmp_path / "test.md"
        content = "---\r\ntitle: \"CRLF doc\"\r\ndescription: \"Load when testing.\"\r\nlastValidated: \"2025-06-01\"\r\nmaxAgeDays: 90\r\n---\r\n\r\n# CRLF doc\r\n"
        doc.write_bytes(content.encode("utf-8"))
        fm = parse_frontmatter(str(doc))
        assert fm["title"] == "CRLF doc"
        assert fm["description"] == "Load when testing."

    def test_utf8_bom(self, tmp_path):
        doc = tmp_path / "test.md"
        content = textwrap.dedent("""\
            ---
            title: "BOM doc"
            description: "Load when testing BOM."
            lastValidated: "2025-06-01"
            maxAgeDays: 90
            ---

            # BOM doc
        """)
        doc.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
        fm = parse_frontmatter(str(doc))
        assert fm["title"] == "BOM doc"

    def test_empty_file_returns_empty(self, tmp_path):
        doc = tmp_path / "test.md"
        doc.write_text("")
        fm = parse_frontmatter(str(doc))
        assert fm == {}

    def test_malformed_yaml_returns_empty(self, tmp_path):
        doc = tmp_path / "test.md"
        doc.write_text(textwrap.dedent("""\
            ---
            title: "Valid start
            description: [invalid yaml
            not_closed: {
            ---

            # Bad YAML
        """))
        fm = parse_frontmatter(str(doc))
        assert fm == {}

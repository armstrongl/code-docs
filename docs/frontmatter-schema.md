---
description: "Load when authoring new docs, reviewing frontmatter validation, or modifying the build-index script."
lastValidated: "2026-03-12"
maxAgeDays: 90
paths:
  - "docs/**"
  - "scripts/agents/build-index.py"
  - ".agentsrc.yaml"
tags:
  - frontmatter
  - schema
  - validation
title: "Frontmatter schema"
---

# Frontmatter schema

Every Markdown file in `docs/` must include a YAML frontmatter block. The schema serves two consumers: the `update-frontmatter.py` script, which writes and validates field values, and the `build-index.py` script, which reads them to generate the AGENTS.md index table. Humans read the schema when authoring new docs or reviewing automation PRs. Agents read the compiled index in AGENTS.md and use individual doc frontmatter to decide whether to load a file.

---

## Full schema reference

```yaml
---
title: "Authentication flow"
description: "Load when modifying auth, tokens, session handling, or debugging login failures."
lastValidated: "2025-03-01"
maxAgeDays: 60
paths:
  - "src/auth/**"
  - "src/middleware/session.ts"
tags:
  - auth
  - security
---
```

---

## Required fields

These four fields must be present in every doc. The automation will not generate an AGENTS.md entry for a doc that is missing any of them.

### `title`

A plain string in sentence case. The index builder uses this as the doc's display name in the AGENTS.md table. Keep it short enough to read in a table column without wrapping.

- **Format:** Plain string, sentence case.
- **Authored by:** LLM on creation.
- **Example:** `"Authentication flow"`

### `description`

The agent's primary signal for whether to load the doc. Because agents make a load-or-skip decision based on this field alone, it must be written as a trigger condition rather than a topic summary.

The LLM prompt enforces a strict formula: *"Load when [trigger conditions]."* Descriptions that summarize content rather than specify trigger conditions are considered malformed and will be flagged by the validation step.

- **Format:** Plain string, maximum 160 characters, beginning with "Load when".
- **Authored by:** LLM on creation, never overwritten after initial generation.
- **Example:** `"Load when modifying auth, tokens, session handling, or debugging login failures."`

A description like "This document covers the authentication system" is invalid. It gives an agent no basis for a load decision.

### `lastValidated`

The date a human last confirmed the doc's content is accurate. The staleness workflow uses this field as the baseline for both time-based and path-based staleness checks. The automation never writes to this field. It is set by a human when they review and confirm a doc.

- **Format:** ISO 8601 date string (`YYYY-MM-DD`). No timestamps, no other formats.
- **Authored by:** Human only.
- **Example:** `"2025-03-01"`

### `maxAgeDays`

The number of days after `lastValidated` at which the doc is considered time-stale. This value is per-doc and overrides the repo-level default in `.agentsrc.yaml`. Docs that change frequently or cover fast-moving parts of the codebase should use a lower value. Conceptual or architectural docs can use a higher one.

- **Format:** Positive integer.
- **Authored by:** Human only, or inherited from `.agentsrc.yaml` if absent.
- **Example:** `60`

---

## Optional fields

These fields improve staleness detection and discoverability but are not required for a doc to appear in the AGENTS.md index.

### `paths`

A list of glob patterns pointing to the code paths this doc describes. The staleness workflow checks these paths against the git log since `lastValidated`. If any commits have touched these paths since that date, the doc is flagged as path-stale regardless of whether the time threshold has been reached.

Use [minimatch](https://github.com/isaacs/node-minimatch) glob syntax. This is the standard used by GitHub Actions and most JavaScript tooling, which ensures consistency across the automation scripts and CI configuration.

- **Format:** YAML list of minimatch glob strings.
- **Authored by:** LLM on creation.
- **Example:**

```yaml
paths:
  - "src/auth/**"
  - "src/middleware/session.ts"
```

Omit this field for docs that are not tied to specific code paths, such as onboarding guides or architectural overviews. The staleness workflow will only apply time-based checks to docs without a `paths` field.

### `tags`

A freeform list of lowercase strings for categorization. Tags appear in the AGENTS.md index table and can be used to filter docs. There is no controlled vocabulary. Use whatever terms are natural for the repo.

- **Format:** YAML list of lowercase strings.
- **Authored by:** LLM on creation.
- **Example:**

```yaml
tags:
  - auth
  - security
```

Note that across multiple repos, a meta-index will accumulate tag sprawl over time. This is acceptable until the volume of docs makes it a problem. Do not pre-optimize with a controlled vocabulary unless you already feel the pain.

---

## Field ownership

The automation and humans own different fields. The `update-frontmatter.py` script never overwrites a field outside its scope.

| Field | Owned by | Notes |
| --- | --- | --- |
| `title` | LLM | Written on creation. Updated if missing or blank. |
| `description` | LLM | Written on creation. Never updated after that. |
| `lastValidated` | Human | Never written by automation. |
| `maxAgeDays` | Human / repo default | Never written by automation. Inherited from `.agentsrc.yaml` if absent. |
| `paths` | LLM | Written on creation. Updated if missing or blank. |
| `tags` | LLM | Written on creation. Updated if missing or blank. |

The reason `description` is never updated after creation is intentional. The LLM generates it once from the full document content at the moment of creation. Subsequent edits to the doc do not trigger a regeneration, because silently changing an existing description could break any agent that has already learned to use it as a loading signal. If a description needs to change, a human edits it manually and the change appears in the next automation PR diff for review.

---

## Repo-level defaults

The `.agentsrc.yaml` file at the repo root sets defaults that apply when per-doc values are absent.

```yaml
# .agentsrc.yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
defaults:
  maxAgeDays: 90
```

The only schema field with a repo-level default is `maxAgeDays`. If a doc's frontmatter includes `maxAgeDays`, that value takes precedence. If it is absent, the staleness workflow falls back to `defaults.maxAgeDays`. If `.agentsrc.yaml` is also absent or the field is not set, the workflow uses a hardcoded fallback of 90 days.

The `.agentsrc.yaml` file should be committed to the repo root. It is the right place to tune staleness sensitivity for the repo as a whole without editing every individual doc.

---

## Validation rules

The `update-frontmatter.py` script validates its LLM response before writing any fields to disk. The following rules are checked:

- `title` is a non-empty string.
- `description` is a non-empty string, is 160 characters or fewer, and begins with "Load when".
- `lastValidated` matches the pattern `YYYY-MM-DD` and is a valid calendar date.
- `maxAgeDays` is a positive integer.
- Each entry in `paths` is a non-empty string. The script does not verify that the paths exist in the repo, because a doc may describe paths that have not yet been created.
- Each entry in `tags` is a non-empty lowercase string.

If the LLM response fails validation for any field, the script writes only the fields that passed and sets a `status: llm-error` field in the frontmatter. The index builder reflects this in the AGENTS.md status column, and the automation PR body includes a warning for each affected doc.

Validation is run as a standalone check during the staleness workflow as well, so malformed frontmatter introduced by a manual edit is caught even if no doc content has changed.

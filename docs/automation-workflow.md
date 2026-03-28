---
description: "Load when modifying GitHub Actions workflows, debugging CI runs, or changing staleness detection logic."
lastValidated: "2026-03-28"
maxAgeDays: 90
paths:
  - ".github/workflows/**"
  - "scripts/agents/**"
tags:
  - automation
  - ci
  - github-actions
  - staleness
title: "Automation workflow"
---

# Automation workflow

This system uses two discrete GitHub Actions workflows. The first keeps frontmatter and the AGENTS.md index in sync whenever a doc changes. The second detects stale docs on a schedule and when relevant code paths change. Both workflows write their changes back to the repo via pull requests rather than committing directly to any branch.

## Overview

| Workflow | File | Trigger | Responsibility |
| --- | --- | --- | --- |
| Docs sync | `docs-sync.yml` | Push to any branch that modifies `docs/**` | Update frontmatter, regenerate AGENTS.md index |
| Docs staleness | `docs-staleness.yml` | Daily cron + push that modifies tracked paths | Detect and flag stale docs |

The two workflows are intentionally decoupled. `docs-sync.yml` owns content accuracy. `docs-staleness.yml` owns freshness signaling. This separation means a failing LLM call in sync never blocks a staleness check, and vice versa.

Both workflows delegate their logic to scripts in a `scripts/agents/` directory. Keeping logic out of YAML makes it testable locally and reusable across repos.

## Workflow 1: `docs-sync.yml`

This workflow runs whenever a file in `docs/` is added or modified on any branch. It calls an LLM to generate or refresh frontmatter, then regenerates the AGENTS.md index table, and opens a PR with both sets of changes.

### Triggers

```yaml
on:
  push:
    paths:
      - "docs/**"
```

### Job steps

1. Check out the branch at the triggering commit.
2. Identify which files in `docs/` were added or modified in the push (not the full directory).
3. For each changed file, call the LLM frontmatter script (`scripts/agents/update-frontmatter.py`).
4. After all files are processed, call the index regeneration script (`scripts/agents/build-index.py`), which rewrites `AGENTS.md`.
5. If any files changed, open a PR targeting the triggering branch (not `main`).

### LLM call design

The frontmatter script sends the full document content to the configured LLM endpoint with a strict system prompt (see the provider-agnostic LLM layer section below). It receives a JSON response with the frontmatter fields and writes them back to the file in place.

The script only overwrites fields that are missing or empty. It never overwrites `lastValidated` (that field is human-controlled) or `maxAgeDays` (that field is set by the human or inherited from `.agentsrc.yaml`). The fields the LLM is responsible for are `title`, `description`, `paths`, and `tags`.

### PR write-back strategy

The workflow opens a PR using the `peter-evans/create-pull-request` action. The PR:

- Targets the same branch that triggered the workflow (not `main`).
- Is titled `[agents] sync frontmatter and index`.
- Includes a body that lists which files were updated and shows a diff of the generated `description` fields so a human can verify them at a glance.
- Is labeled `agents-sync` for easy filtering.

If a PR with this label already exists for the branch, the action updates it rather than opening a duplicate.

## Workflow 2: `docs-staleness.yml`

This workflow detects docs that are stale by two independent signals: time elapsed since `lastValidated`, and code changes that touched paths listed in a doc's frontmatter. It opens a PR that updates the `status` field in AGENTS.md for any flagged docs.

### Triggers

```yaml
on:
  schedule:
    - cron: "0 9 * * 1"  # Every Monday at 09:00 UTC
  push:
    paths:
      - "src/**"
      - "lib/**"
      # Add any other tracked code paths here
```

The cron handles time-based staleness. The push trigger handles path-based staleness. Both call the same script with different flags, so the logic is not duplicated.

### Staleness logic

The staleness script (`scripts/agents/check-staleness.py`) reads all frontmatter in `docs/` and checks two conditions for each doc:

Time-based: Compare today's date against `lastValidated + maxAgeDays`. If the doc is past its threshold, flag it as stale. The `maxAgeDays` value comes from the doc's frontmatter or, if absent, from the `defaults.maxAgeDays` value in `.agentsrc.yaml`.

Path-based: Run `git log --since=<lastValidated> -- <paths>` for each doc that has a `paths` field. If any commits exist against those paths since `lastValidated`, flag the doc as path-stale regardless of whether the time threshold has been reached.

The script produces a JSON report of all flagged docs, which `build-index.py` uses to set the `status` column in AGENTS.md:

- `current`: No staleness signals.
- `stale (time)`: Past `maxAgeDays` threshold.
- `stale (paths)`: Relevant code paths changed since `lastValidated`.
- `stale (time + paths)`: Both signals triggered.

### PR write-back strategy

The staleness workflow opens a PR targeting `main` (not the triggering branch). The PR:

- Is titled `[agents] staleness report <date>`.
- Is labeled `agents-staleness`.
- Includes a body listing each flagged doc, its staleness reason, and the relevant paths or date delta.
- Does not modify doc content. It only updates AGENTS.md status flags.

The PR is a notification mechanism. A human reviews it, validates the flagged docs, updates `lastValidated` in the relevant frontmatter, and merges. The `docs-sync.yml` workflow then picks up the frontmatter change and regenerates the index.

## Provider-agnostic LLM layer

The scripts call a thin wrapper (`scripts/agents/llm.py`) that abstracts the LLM provider. The wrapper reads two environment variables:

```bash
AGENTS_LLM_PROVIDER=anthropic   # or: openai, azure, ollama
AGENTS_LLM_API_KEY=<your-key>
AGENTS_LLM_MODEL=claude-sonnet-4-20250514  # or any compatible model string
```

Internally, the wrapper maps `anthropic` to the Anthropic Messages API and all other values to an OpenAI-compatible endpoint. This means any provider with an OpenAI-compatible API (Azure, Ollama, Groq, etc.) works without code changes.

The model and provider are also configurable in `.agentsrc.yaml` as fallbacks if the environment variables are not set:

```yaml
# .agentsrc.yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
defaults:
  maxAgeDays: 90
```

Secrets are stored as GitHub Actions secrets (`AGENTS_LLM_API_KEY`) and never committed to the repo.

## Shared tooling

Both workflows call scripts in `scripts/agents/`. The scripts and their responsibilities are:

| Script | Called by | Responsibility |
| --- | --- | --- |
| `update-frontmatter.py` | `docs-sync.yml` | Call LLM, parse response, write frontmatter to doc |
| `build-index.py` | Both | Read all frontmatter, regenerate AGENTS.md table |
| `check-staleness.py` | `docs-staleness.yml` | Run time and path checks, produce JSON report |
| `llm.py` | `update-frontmatter.py` | Provider-agnostic LLM wrapper |

All scripts accept a `--dry-run` flag that prints intended changes without writing them. This makes local testing straightforward without needing to stub the LLM.

## Failure modes and guards

**LLM call fails:** The frontmatter script catches API errors and writes a `status: llm-error` field to the affected doc's frontmatter. The index regeneration step still runs and reflects the error status in AGENTS.md. The PR is still opened so a human can see which file failed.

**PR already exists:** Both workflows check for an existing open PR with their respective label before opening a new one. If one exists, the workflow updates it. This prevents accumulating duplicate PRs from rapid successive pushes.

**No changes detected:** If `docs-sync.yml` runs but the generated frontmatter and index are identical to what's already in the repo, the workflow exits without opening a PR. The `create-pull-request` action handles this check natively.

**Malformed frontmatter:** The LLM script validates its JSON response against a schema before writing. If validation fails, it falls back to writing only the fields it can confirm are valid and logs a warning. The PR body includes a warning banner for any doc with partial frontmatter.

**Rate limiting:** The frontmatter script processes changed files sequentially with a configurable delay between calls (`AGENTS_LLM_DELAY_MS`, default 500ms). For repos with many simultaneous doc changes, this prevents bursting the API.

## Reusable template strategy

To stamp this system onto a new repo:

1. Copy `.github/workflows/docs-sync.yml` and `docs-staleness.yml`.
2. Copy `.github/agents/frontmatter-prompt.md` (the task prompt used by the docs-sync workflow).
3. Copy `scripts/agents/` in its entirety.
4. Copy `requirements.txt`.
5. Add `.agentsrc.yaml` to the repo root and set `defaults.maxAgeDays`. The `llm:` block is optional and only needed if using the provider-agnostic LLM layer described above.
6. Add `ANTHROPIC_API_KEY` to the repo's GitHub Actions secrets. This is the secret name used by `docs-sync.yml` for the Claude Code implementation. If using the provider-agnostic LLM layer instead, the secret name is `AGENTS_LLM_API_KEY`.
7. Create the `docs/` directory (if it doesn't already exist) and add an initial `AGENTS.md` with boundary markers (`<!-- AGENTS-INDEX-START -->` and `<!-- AGENTS-INDEX-END -->`).

No other configuration is required. The push trigger paths in `docs-staleness.yml` should be updated to reflect the repo's actual code paths, but the workflow runs safely without them (it will only perform time-based checks until paths are configured).

For the multi-repo meta-index, a separate `meta-index.yml` workflow in the aggregating repo can call `build-index.py` with a `--repos` flag that accepts a list of repo paths (or a cloned workspace). This generates a combined AGENTS.md with a `repo` column prepended to each row.

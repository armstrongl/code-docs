---
description: "Load when editing AGENTS.md preamble, modifying the index table format, or updating build-index.py."
lastValidated: "2026-03-12"
maxAgeDays: 90
paths:
  - "AGENTS.md"
  - "scripts/agents/build-index.py"
tags:
  - agents
  - index
  - documentation
title: "AGENTS.md structure"
---

# AGENTS.md structure

AGENTS.md is the entry point for every agent that works in the repo. Agents use it to find available documentation and decide what to load for a given task. The `build-index.py` script generates and maintains the index table automatically. The preamble and repo-level context sections are human-authored and protected from regeneration.

---

## Overview

AGENTS.md has three sections in a fixed order:

1. **Preamble** — a short block of instructions that orients agents before they read anything else.
2. **Repo-level context** — instructions for how to use the index and load docs selectively.
3. **Index table** — one row per doc in `docs/`, generated entirely by `build-index.py`.

Agents are expected to read AGENTS.md first on every session. The preamble and repo-level context sections are always loaded. The index table is scanned, not fully loaded. Each row gives the agent enough signal to decide whether to fetch and read the linked doc.

---

## Preamble

The preamble is a short block at the top of the file. It orients the agent before it reads the index. It should be three to five sentences at most. Longer preambles waste tokens on every session.

A good preamble covers three things in order:

1. What this repo contains and what the agent's primary job is likely to be.
2. That the index table below lists all available documentation.
3. That the agent should read the `description` column of each row and load only docs that are relevant to the current task.

A poor preamble tries to document the schema or cover edge cases. That content belongs in individual docs, not in a file that is loaded on every session.

**Example preamble:**

```markdown
This repo contains the authentication service for the platform. You are likely
here to modify, debug, or extend auth-related code.

The index below lists all available documentation. Read the description column
for each row and load only the docs that are relevant to your current task.
Do not load docs speculatively. If you are unsure whether a doc is relevant,
read its description again before fetching it.
```

---

## Repo-level context section

The repo-level context section follows the preamble and precedes the index table. It contains instructions that apply to every session regardless of task. Keep it focused on loading behavior only. Do not include repo conventions, tech stack descriptions, or onboarding content here. Those belong in dedicated docs in `docs/` that agents load on demand.

This section should answer two questions for the agent:

- How do I decide whether to load a doc?
- What do I do if no doc seems relevant?

**Example repo-level context section:**

```markdown
## How to use this index

Load a doc if its description matches the concepts, components, or tasks
involved in your current work. The description field is written as a trigger
condition: "Load when [conditions]." If the conditions match your task, load
the doc. If they do not, skip it.

If no doc in the index is relevant to your task, proceed without loading any.
The absence of a relevant doc is useful signal — it may mean the area you are
working in is undocumented. Note this if it affects your ability to complete
the task accurately.
```

---

## Index table

The index table is generated entirely by `build-index.py`. It contains one row per Markdown file in `docs/`. Each row has four columns.

### Column definitions

| Column | Source | Notes |
| --- | --- | --- |
| Doc | `title` frontmatter field | Rendered as a relative Markdown link to the file. |
| When to load | `description` frontmatter field | The agent's primary load/skip signal. |
| Last validated | `lastValidated` frontmatter field | ISO 8601 date. Helps agents assess freshness at a glance. |
| Paths | `paths` frontmatter field | Comma-separated list of globs. Empty if the doc has no code path association. |

### Row generation rules

`build-index.py` generates one row per file found in `docs/`. The script follows these rules:

- Files missing any required frontmatter field are included in the table with a `⚠️ missing fields` note in the relevant column, rather than being silently omitted. This makes frontmatter gaps visible.
- The `Doc` column renders the `title` value as a relative Markdown link: `[title](docs/filename.md)`.
- The `Paths` column renders each glob on a single line separated by `<br>` tags so the table stays readable without horizontal scrolling.
- Rows are sorted alphabetically by `title`.
- The script never modifies any content above the index table. It identifies the table by a pair of HTML comments used as boundary markers (see the full example below).

### Boundary markers

The script uses two HTML comments to locate the index table within the file. Everything outside these markers is treated as human-authored and never modified.

```markdown
<!-- AGENTS-INDEX-START -->
<!-- AGENTS-INDEX-END -->
```

On every run, `build-index.py` replaces everything between these markers with the freshly generated table. The markers themselves are preserved. If either marker is missing from the file, the script appends them and the table at the end of the file rather than failing.

---

## Full example

The following is a complete annotated AGENTS.md with realistic sample data.

```markdown
This repo contains the authentication service for the platform. You are likely
here to modify, debug, or extend auth-related code.

The index below lists all available documentation. Read the description column
for each row and load only the docs that are relevant to your current task.
Do not load docs speculatively. If you are unsure whether a doc is relevant,
read its description again before fetching it.

## How to use this index

Load a doc if its description matches the concepts, components, or tasks
involved in your current work. The description field is written as a trigger
condition: "Load when [conditions]." If the conditions match your task, load
the doc. If they do not, skip it.

If no doc in the index is relevant to your task, proceed without loading any.
The absence of a relevant doc is useful signal — it may mean the area you are
working in is undocumented. Note this if it affects your ability to complete
the task accurately.

<!-- AGENTS-INDEX-START -->

| Doc | When to load | Last validated | Paths |
| --- | --- | --- | --- |
| [Authentication flow](docs/auth-flow.md) | Load when modifying auth, tokens, session handling, or debugging login failures. | 2025-03-01 | `src/auth/**`<br>`src/middleware/session.ts` |
| [Rate limiting](docs/rate-limiting.md) | Load when modifying rate limit rules, configuring thresholds, or debugging 429 errors. | 2025-02-14 | `src/middleware/rate-limit/**` |
| [Token refresh service](docs/token-refresh.md) | Load when modifying token refresh logic, expiry configuration, or debugging refresh failures. | 2025-01-30 | `src/auth/refresh.ts`<br>`src/auth/expiry.ts` |
| [Service architecture](docs/architecture.md) | Load when making structural changes, adding new services, or orienting to the codebase for the first time. | 2025-01-10 |  |

<!-- AGENTS-INDEX-END -->
```

---

## Generation rules

`build-index.py` enforces a strict separation between human-authored content and generated content.

- Everything above `<!-- AGENTS-INDEX-START -->` is never read or modified by the script.
- Everything between the markers is fully replaced on every run.
- Everything below `<!-- AGENTS-INDEX-END -->` is never read or modified by the script.

This means the preamble and repo-level context section are safe to edit at any time without risk of the next automation run overwriting the changes. The only content at risk of being overwritten is the table itself, which is intentional.

The script also enforces these additional rules on generation:

- The table header row and separator row are always regenerated from a fixed template. They cannot drift.
- An empty `paths` field in frontmatter produces an empty cell in the table, not a placeholder string like "N/A".
- The script does not sort by `lastValidated` or any staleness signal. Sort order is alphabetical by title only. Staleness is surfaced in a separate PR by the `docs-staleness.yml` workflow, not in this file.

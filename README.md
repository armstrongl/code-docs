# In-repo documentation for humans and agents

Most repos have a documentation problem that gets worse as the codebase grows. Knowledge about how the system works, why decisions were made, and how to navigate the code lives in wikis, READMEs, Slack threads, and people's heads. Humans rediscover it slowly. AI agents and coding assistants don't find it at all.

This is a proposal for a lightweight, in-repo documentation system designed to serve both audiences from the ground up, with minimal maintenance overhead and no proprietary tooling.

## The problem

When an AI agent starts working in a repo, it has no institutional memory. It reads what is in front of it. If the repo has a README, the agent reads that. If there are inline comments, it reads those. Everything else, the architectural decisions, the known gotchas, the conventions that aren't enforced by linting, is invisible.

Humans have the same problem, just more slowly. A new team member reads the README, asks questions, and gradually builds a mental model. That process takes weeks. An agent can't ask questions the same way, and it starts from zero every session.

Existing solutions don't bridge this gap well. Wikis are external to the repo and drift out of sync with the code. Long READMEs are loaded in full regardless of relevance, which wastes context window and buries useful signal. Inline comments are scoped to individual files, not workflows or systems. None of these are designed with agents in mind.

---

## The idea

The system proposed here is built on three components that work together:

- A `docs/` folder at the repo root containing Markdown files, each covering a specific topic, workflow, or area of the codebase.
- A frontmatter schema that gives each doc a machine-readable identity: what it covers, when an agent should load it, and which code paths it describes.
- An `AGENTS.md` file at the repo root that serves as a lazy-load index. Agents read this file first, scan the index, and load only the docs relevant to their current task.

The system is intentionally minimal. It uses standard Markdown, YAML frontmatter, GitHub Actions, and a provider-agnostic LLM API call. It has no runtime dependencies and no external services. It can be stamped onto any repo in under an hour.

## How it works

### Docs

Each file in `docs/` is a standard Markdown document with a YAML frontmatter block. A typical doc looks like this:

```markdown
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

# Authentication flow

...
```

The frontmatter is the doc's machine-readable identity. The `description` field is the most important piece. It is written as a trigger condition, not a topic summary, so an agent can make a load-or-skip decision without reading the doc itself. The `paths` field links the doc to specific areas of the codebase, which enables staleness detection when those paths change.

### AGENTS.md

`AGENTS.md` is the entry point for every agent session. It contains a short preamble that orients the agent, instructions for how to use the index, and a generated table with one row per doc.

```markdown
This repo contains the authentication service for the platform...

## How to use this index

Load a doc if its description matches the concepts, components, or tasks
involved in your current work...

| Doc | When to load | Last validated | Paths |
|---|---|---|---|
| [Authentication flow](docs/auth-flow.md) | Load when modifying auth, tokens, session handling, or debugging login failures. | 2025-03-01 | `src/auth/**` |
| [Rate limiting](docs/rate-limiting.md) | Load when modifying rate limit rules, configuring thresholds, or debugging 429 errors. | 2025-02-14 | `src/middleware/rate-limit/**` |
```

The table is generated automatically. Humans author only the preamble and the context section. The rest is maintained by automation.

### Automation

Two GitHub Actions workflows keep the system current with minimal human involvement.

The first workflow, `docs-sync.yml`, triggers whenever a file is added or modified in `docs/`. It calls an LLM to generate or validate the frontmatter fields the automation owns (`title`, `description`, `paths`, and `tags`), then regenerates the AGENTS.md index table. Changes are written back to the repo via a pull request rather than committing directly, so a human sees every automated change before it merges.

The second workflow, `docs-staleness.yml`, runs on a daily schedule and on any push that touches code paths tracked in doc frontmatter. It checks two staleness signals for each doc: whether the time since `lastValidated` has exceeded the doc's configured threshold, and whether relevant code paths have changed since the doc was last validated. Flagged docs surface in a pull request with a summary of the staleness reason. A human reviews, validates the affected docs, updates `lastValidated`, and merges. The sync workflow picks up the change and regenerates the index.

## Design principles

Several explicit decisions shaped the system.

Lazy loading over eager loading. Agents read the index first and load individual docs on demand. This keeps token usage proportional to task complexity rather than repo size. A repo with fifty docs does not cost fifty docs worth of context on every session.

Description as trigger, not summary. The `description` field is written as a load condition: "Load when [conditions]." This is a small but important distinction. A summary describes content; a trigger condition drives a load-or-skip decision. The latter is what enables reliable lazy loading.

Automation owns generation, humans own validation. The LLM generates `title`, `description`, `paths`, and `tags` on doc creation. It never overwrites them after that, and it never touches `lastValidated` or `maxAgeDays`. Those fields belong to humans. This division means the system can run without human involvement for routine changes while keeping humans in the loop for anything that affects accuracy.

Provider-agnostic by design. The LLM call is abstracted behind a thin wrapper that maps to either the Anthropic Messages API or any OpenAI-compatible endpoint. Swapping providers requires changing two environment variables, not rewriting scripts.

Co-located with code. Docs live in the repo alongside the code they describe. They appear in pull requests, code reviews, and git history. They go stale on the same timeline as the code. This is a deliberate choice against external wikis, which drift silently because they are not part of the development workflow.

## What you get

A repo with this system in place gives agents a reliable, low-cost way to orient themselves before starting work. An agent reading AGENTS.md can scan the full index in a fraction of the tokens required to read the underlying docs, then load only what is relevant to the current task.

For humans, the system surfaces documentation gaps in pull requests and keeps freshness visible in a single file.

The system is designed to be stamped onto new repos with minimal setup: copy two workflow files, copy the scripts directory, add a `.agentsrc.yaml` with a default staleness threshold, and add an `AGENTS.md` with a preamble. No configuration beyond that is required to get the automation running.

For organizations with multiple repos, the same index-building script can aggregate across repos into a meta-index with a `repo` column prepended to each row. This gives agents working across a codebase a single entry point without requiring a monorepo.

## Tradeoffs and open questions

No system is free. A few honest tradeoffs are worth naming.

Description quality depends on the LLM. A poorly generated `description` either prevents a relevant doc from being loaded or loads an irrelevant one. The prompt design and validation rules mitigate this, but they don't eliminate it. Human review of generated descriptions on first creation is the strongest safeguard, even though the system is designed to not require it.

`lastValidated` depends on human discipline. The staleness system surfaces docs that may need attention, but it cannot validate them. A human has to read the doc, confirm it is accurate, and update the date. If that habit doesn't form, the staleness signals eventually become noise.

The system doesn't scale to very large doc sets without further tooling. At a few dozen docs, scanning the AGENTS.md index is fast and cheap. At several hundred docs, agents may benefit from tag-based or semantic filtering before scanning the full table. That layer is not part of this proposal and would add complexity.

The `description` field is immutable after creation. This is intentional, but it means a doc that is substantially rewritten can have a description that no longer reflects its content. There is currently no automated signal for this. A human editing a doc significantly should review and manually update the description.

## Detailed specs

The following documents cover each component of the system in full detail:

- [Frontmatter schema](docs/frontmatter-schema.md) — field definitions, ownership rules, validation logic, and repo-level defaults.
- [AGENTS.md structure](docs/agents-md-structure.md) — preamble guidance, index table columns, generation rules, and a full annotated example.
- [Automation workflow](docs/automation-workflow.md) — both GitHub Actions workflows, the shared scripts, failure modes, and the reusable template strategy.
- [LLM prompt design for Claude Code](docs/llm-prompt-design-claude.md) — Claude Code CI invocation, task prompt structure, tool constraints, and the full prompt text.
- [LLM prompt design (provider-agnostic)](docs/llm-prompt-design-agnostic.md) — system prompt for a standalone LLM API call, JSON output schema, and few-shot examples. Use as a reference for non-Claude implementations.

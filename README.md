# In-repo documentation for humans and agents

[![CI](https://GitHub.com/armstrongl/code-docs/actions/workflows/ci.yml/badge.svg)](https://github.com/armstrongl/code-docs/actions/workflows/ci.yml) [![Docs Sync](https://GitHub.com/armstrongl/code-docs/actions/workflows/docs-sync.yml/badge.svg)](https://github.com/armstrongl/code-docs/actions/workflows/docs-sync.yml) [![Docs Staleness](https://GitHub.com/armstrongl/code-docs/actions/workflows/docs-staleness.yml/badge.svg)](https://github.com/armstrongl/code-docs/actions/workflows/docs-staleness.yml)

Most repos have a documentation problem that gets worse as the codebase grows. Knowledge about how the system works, why decisions were made, and what to watch out for ends up in Slack threads, wikis, and people's heads. Humans find it eventually. AI agents don't.

This is a proposal for a lightweight, in-repo documentation system designed to serve both audiences, with no proprietary tooling and minimal maintenance overhead.

I designed it specifically to solve a problem where engineers want to adopt AI in a token-efficient way, but they don’t want to mess around with complicated AGENT.md files, manually maintaining file frontmatter, or setting up skills. So the idea is that they have a standard pattern where they have internal docs in the repo in a `docs/` folder. Coding agents can find the docs, but they often sample all of them and waste tokens. Many teams are also reluctant to adopt new tools or add any sort of overhead.

So, my thinking was to create a very simple system that:

- Let agents use existing in-repo docs in a token-efficient way (using frontmatter that’s pulled into the AGENTS.md file to tell agents which docs to use based on the context).
- Have a CI/CD workflow that minimizes the effort required of the engineering team to keep the system running. It does this by:
   - Automatically flagging stale docs
   - Automatically generating useful descriptions for docs (using an LLM)
   - Automatically maintaining routing info for all docs in the AGENTS.md file

## How it works

The system has three parts that work together:

- A `docs/` folder at the repo root, where each file covers a specific topic, workflow, or area of the codebase.
- A frontmatter schema that gives each doc a machine-readable identity: what it covers, when an agent should load it, and which code paths it describes.
- An `AGENTS.md` file at the repo root that acts as a lazy-load index. Agents read it first, scan the table, and load only the docs relevant to their current task.

### Docs

Each file in `docs/` has a YAML frontmatter block. The `description` field is the most important part. It's written as a trigger condition, not a topic summary, so an agent can make a load-or-skip decision without reading the doc itself.

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
```

The `paths` field links the doc to specific areas of the codebase, which enables staleness detection when those paths change.

### AGENTS.md

`AGENTS.md` is the entry point for every agent session. It has a short preamble that orients the agent, instructions for using the index, and a generated table with one row per doc.

```markdown
| Doc | When to load | Last validated | Paths |
| --- | --- | --- | --- |
| [Authentication flow](docs/auth-flow.md) | Load when modifying auth, tokens, session handling, or debugging login failures. | 2025-03-01 | `src/auth/**` |
```

The table is generated automatically. You author only the preamble.

### Automation

Two GitHub Actions workflows keep the system current.

**docs-sync** triggers when a file is added or modified in `docs/`. It calls an LLM to generate or validate frontmatter, then regenerates the AGENTS.md index. Changes come back as a pull request, so a human sees every automated change before it merges.

**docs-staleness** runs on a weekly schedule and on any push that touches tracked code paths. It checks two signals per doc: whether the time since `lastValidated` has exceeded the configured threshold, and whether relevant code paths have changed. Flagged docs surface in a pull request. Review, update `lastValidated`, and merge.

## Design decisions

**Lazy loading.** Agents load only what they need for the current task. Token usage stays proportional to task complexity, not repo size.

**Description as trigger condition.** "Load when [conditions]" drives a load-or-skip decision. A topic summary doesn't.

**Automation generates, humans validate.** The LLM generates `title`, `description`, `paths`, and `tags` on doc creation. It never overwrites them after that and never touches `lastValidated` or `maxAgeDays`. Those belong to humans.

**Provider-agnostic.** Swapping LLM providers requires changing two environment variables, not rewriting scripts.

**Co-located with code.** Docs live in the repo, show up in pull requests, and go stale on the same timeline as the code.

## Getting started

Copy the following into any repo:

- `.github/workflows/docs-sync.yml` and `.github/workflows/docs-staleness.yml`, the two automation workflows.
- `scripts/`, the Python scripts for index building and staleness checking.
- `.agentsrc.yaml` with a default staleness threshold.
- `AGENTS.md` with a preamble.

No additional configuration required.

## Tradeoffs

**Description quality depends on the LLM.** A poorly generated `description` either prevents a relevant doc from loading or loads an irrelevant one. Reviewing generated descriptions on first creation is the strongest safeguard, even if the system is designed to run without it.

**`lastValidated` depends on human discipline.** The staleness system surfaces docs that may need attention, but it can't validate them. If the review habit doesn't form, staleness signals eventually become noise.

**Scale.** At a few dozen docs, scanning the index is fast and cheap. At several hundred, tag-based or semantic filtering would help. That's out of scope here.

## Documentation

### Guides

- [How it works](docs/how-it-works.md) — end-to-end walkthrough of the system lifecycle
- [Get started](docs/get-started.md) — add code-docs to an existing repo

### Detailed specs

- [Frontmatter schema](docs/frontmatter-schema.md)
- [AGENTS.md structure](docs/agents-md-structure.md)
- [Automation workflow](docs/automation-workflow.md)
- [LLM prompt design for Claude Code](docs/llm-prompt-design-claude.md)
- [LLM prompt design (provider-agnostic)](docs/llm-prompt-design-agnostic.md)

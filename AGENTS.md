This repo defines a lightweight, in-repo documentation system for both humans
and AI agents. You are likely here to modify the system spec, add automation
scripts, update workflows, or extend the frontmatter schema. The index below
lists all available documentation. Read the description column for each row
and load only the docs that are relevant to your current task.

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

| Doc | When to load | Last validated | Status | Paths |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------- | ------- | ------------------------------------------------------------------------- |
| [AGENTS.md structure](docs/agents-md-structure.md) | Load when editing AGENTS.md preamble, modifying the index table format, or updating build-index.py. | 2026-03-12 | current | `AGENTS.md`<br>`scripts/agents/build-index.py` |
| [Automation workflow](docs/automation-workflow.md) | Load when modifying GitHub Actions workflows, debugging CI runs, or changing staleness detection logic. | 2026-03-12 | current | `.github/workflows/**`<br>`scripts/agents/**` |
| [Frontmatter schema](docs/frontmatter-schema.md) | Load when authoring new docs, reviewing frontmatter validation, or modifying the build-index script. | 2026-03-12 | current | `docs/**`<br>`scripts/agents/build-index.py`<br>`.agentsrc.yaml` |
| [LLM prompt design (provider-agnostic)](docs/llm-prompt-design-agnostic.md) | Load when implementing a provider-agnostic LLM layer or porting frontmatter generation to non-Claude providers. | 2026-03-12 | current |  |
| [LLM prompt design for Claude Code](docs/llm-prompt-design-claude.md) | Load when modifying the Claude Code task prompt, adjusting CI frontmatter generation, or debugging LLM output. | 2026-03-12 | current | `.github/agents/**`<br>`.github/workflows/docs-sync.yml` |

<!-- AGENTS-INDEX-END -->

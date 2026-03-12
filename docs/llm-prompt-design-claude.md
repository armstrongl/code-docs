---
description: "Load when modifying the Claude Code task prompt, adjusting CI frontmatter generation, or debugging LLM output."
lastValidated: "2026-03-12"
maxAgeDays: 90
paths:
  - ".github/agents/**"
  - ".github/workflows/docs-sync.yml"
tags:
  - llm
  - prompt
  - claude
  - ci
title: "LLM prompt design for Claude Code"
---

# LLM prompt design

Claude Code runs in CI as the agent responsible for writing and updating LLM-owned frontmatter fields whenever a file in `docs/` is added or modified. It reads the document content, the existing frontmatter, and the repo config, then edits the file in place using its file editing tools. No separate `update-frontmatter.py` script or `llm.py` wrapper is needed. The GitHub Actions workflow invokes Claude Code directly and commits the result.

This document covers how Claude Code is invoked, what the task prompt instructs it to do, and the full ready-to-use prompt text.

---

## Overview

Claude Code is responsible for the following frontmatter fields only:

- `title`
- `description`
- `paths`
- `tags`

It never reads, writes, or reasons about `lastValidated` or `maxAgeDays`. Those fields are human-controlled and are explicitly excluded from its instructions.

Claude Code writes a field only if it is missing or blank. It never overwrites an existing value, with one exception: `description` is always regenerated on the first run (when the field is absent) and never touched again after that. This is enforced in the task prompt, not in post-processing.

---

## Invocation design

The GitHub Actions workflow calls Claude Code via the CLI after checking out the triggering branch. It passes the task prompt as a file reference rather than an inline argument to avoid shell escaping issues with long prompt text.

```yaml
- name: Run Claude Code frontmatter update
  run: |
    claude \
      --task-file .github/agents/frontmatter-prompt.md \
      --allowedTools "Edit,Read" \
      --no-interactive \
      --output-format json
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

Key invocation decisions:

- `--task-file` loads the prompt from a file in the repo, which makes the prompt versionable and reviewable like any other code.
- `--allowedTools "Edit,Read"` restricts Claude Code to reading and editing files only. It cannot run shell commands, make network requests, or use any other tools.
- `--no-interactive` ensures the run is fully unattended.
- `--output-format json` makes it straightforward to parse the result in subsequent workflow steps.

The workflow injects the list of changed files as an environment variable (`CHANGED_FILES`), which the task prompt reads to know which files to process.

---

## Task prompt

The task prompt is a Markdown file stored at `.github/agents/frontmatter-prompt.md`. It is the single source of truth for what Claude Code does. It is structured in four sections: context, rules, examples, and input.

### Context section

The context section tells Claude Code what it is, what it is doing, and what success looks like. It also states the hard ownership boundaries up front so they are the first thing the model reads.

### Rules section

The rules section specifies the exact behavior for each LLM-owned field. The most important rule is the `description` formula. A description must:

- Begin with "Load when".
- Specify trigger conditions, not topic summaries.
- Be 160 characters or fewer.
- Be written for an agent making a load-or-skip decision, not a human browsing docs.

The rules section also specifies that Claude Code must leave the file unchanged if all LLM-owned fields are already populated, and must never add, remove, or reorder any other content in the file.

### Examples section

Two `description` examples are embedded in the prompt to anchor the model's output.

**Good example:**

```
"Load when modifying auth, tokens, session handling, or debugging login failures."
```

This works because it specifies concrete trigger conditions. An agent reading this knows exactly when to load the doc.

**Bad example:**

```
"This document covers the authentication system and how tokens are managed."
```

This fails because it summarizes content rather than specifying trigger conditions. An agent cannot make a reliable load decision from a content summary.

### Input section

The input section contains the XML-tagged data blocks Claude Code reads to do its work. These are injected by the workflow at runtime using environment variable interpolation.

---

## XML-tagged input sections

Separating instructions from data using XML tags prevents the model from confusing document content with instructions, which is especially important when a doc contains imperative language or code samples.

```xml
<changed_files>
{{ CHANGED_FILES }}
</changed_files>

<document path="{{ FILE_PATH }}">
{{ DOC_CONTENT }}
</document>

<existing_frontmatter>
{{ FRONTMATTER }}
</existing_frontmatter>

<repo_config>
{{ AGENTSRC_YAML }}
</repo_config>
```

The workflow populates these blocks before passing the prompt to Claude Code. If `.agentsrc.yaml` does not exist in the repo, the `<repo_config>` block is passed as empty. Claude Code is instructed to treat an empty `<repo_config>` as a signal to use schema defaults.

---

## Tool use constraints

The `--allowedTools "Edit,Read"` flag is the primary enforcement mechanism. It is not sufficient on its own to state the constraint in the prompt. The flag ensures Claude Code cannot exceed its scope even if the task prompt is ambiguous or the model reasons its way around a soft instruction.

Within the Edit tool, Claude Code is instructed in the prompt to:

- Edit only the frontmatter block at the top of the file.
- Never modify content below the closing `---` of the frontmatter.
- Never create new files.
- Never delete files.

---

## Edge case handling

The following edge cases are addressed explicitly in the task prompt.

**Empty document:** If the document body contains no content below the frontmatter, Claude Code generates a minimal description based on the title alone and sets `tags` to an empty list. It does not fabricate content.

**Very short document:** If the document body is fewer than 50 words, Claude Code generates the description from what is available. It does not infer or expand on what is not written.

**No clear code relationship:** If the document has no apparent relationship to specific code paths (for example, an onboarding guide or architectural overview), Claude Code leaves `paths` as an empty list rather than guessing. It never populates `paths` with speculative values.

**Frontmatter already complete:** If all LLM-owned fields are populated, Claude Code makes no changes to the file and exits cleanly.

**Malformed existing frontmatter:** If the existing frontmatter cannot be parsed as valid YAML, Claude Code writes a note to stdout and skips the file rather than attempting a repair. The workflow treats a skipped file as a soft failure and includes it in the PR body as a warning.

---

## Full task prompt

The following is the complete contents of `.github/agents/frontmatter-prompt.md`.

---

```markdown
You are a documentation automation agent running in CI. Your only job is to populate
missing frontmatter fields in Markdown files in the docs/ directory of this repository.

## What you own

You are responsible for these fields only:

- title
- description
- paths
- tags

You never read, write, modify, or reason about lastValidated or maxAgeDays. Those fields
do not exist as far as you are concerned.

## What you must never do

- Modify any content below the closing --- of the frontmatter block.
- Overwrite a field that already has a value.
- Create new files.
- Delete files.
- Run shell commands.
- Make network requests.
- Add commentary, explanations, or notes anywhere in the file.

## Rules for each field

### Title

Write a short plain string in sentence case that names the document. Match the
document's own heading if one exists. If no heading exists, infer the title from
the content.

### Description

This is the most important field. An agent will read this field and decide whether
to load the document. Write it for that agent, not for a human reader.

Formula: "Load when [trigger conditions]."

Rules:

- Begin with "Load when".
- Specify concrete trigger conditions: tasks, errors, or scenarios where loading this
  doc would help an agent.
- Never summarize the document's content.
- Never use vague language like "related to" or "covers".
- Maximum 160 characters.

### Paths

Write a list of minimatch glob patterns pointing to the code paths this document
describes. Use patterns like src/auth/** or lib/tokens/session.ts. If the document
has no clear relationship to specific code paths, write an empty list.

Never guess. If you are not confident a path is relevant, leave it out.

### Tags

Write a list of lowercase strings that categorize the document. Use natural terms
that reflect the document's subject matter. If the document is very general or you
cannot identify clear tags, write an empty list.

## Good and bad description examples

Good:
"Load when modifying auth, tokens, session handling, or debugging login failures."

Why this works: it specifies concrete trigger conditions. An agent knows exactly
when to load this doc.

Bad:
"This document covers the authentication system and how tokens are managed."

Why this fails: it summarizes content. An agent cannot make a reliable load
decision from a content summary.

## Edge cases

- Empty document: generate a minimal description from the title alone. Set tags
  to an empty list. Do not fabricate content.
- Very short document (fewer than 50 words): generate from what is available.
  Do not infer or expand on what is not written.
- No clear code relationship: leave paths as an empty list. Never speculate.
- All LLM-owned fields already populated: make no changes. Exit cleanly.
- Malformed frontmatter: write a note to stdout and skip the file. Do not attempt
  a repair.

## Input

The files you need to process, the content of each file, the existing frontmatter,
and the repo config are provided below.

<changed_files>
{{ CHANGED_FILES }}
</changed_files>

<document path="{{ FILE_PATH }}">
{{ DOC_CONTENT }}
</document>

<existing_frontmatter>
{{ FRONTMATTER }}
</existing_frontmatter>

<repo_config>
{{ AGENTSRC_YAML }}
</repo_config>

Process each file listed in <changed_files>. Edit only the frontmatter block at the
top of each file. When you are done, stop. Do not summarize what you did.
```

---

## Note on the automation workflow document

Switching to Claude Code invalidates the following sections in the automation workflow document:

- The `llm.py` provider-agnostic wrapper (no longer needed).
- The `update-frontmatter.py` script (replaced by Claude Code's file editing tools).
- The provider config block in `.agentsrc.yaml` (replaced by `ANTHROPIC_API_KEY` in GitHub Actions secrets).
- The "shared tooling" table entry for `update-frontmatter.py`.

The `build-index.py` script, `check-staleness.py`, and the `.agentsrc.yaml` `defaults.maxAgeDays` config remain unchanged. Those are not LLM concerns.

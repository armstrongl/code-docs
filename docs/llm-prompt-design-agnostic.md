---
description: "Load when implementing a provider-agnostic LLM layer or porting frontmatter generation to non-Claude providers."
lastValidated: "2026-03-12"
maxAgeDays: 90
paths: []
tags:
  - llm
  - prompt
  - provider-agnostic
title: "LLM prompt design (provider-agnostic)"
---

# LLM prompt design

The `update-frontmatter.py` script calls a provider-agnostic LLM API to generate values for the fields the automation owns. The system prompt is the sole instruction source. The document content, existing frontmatter, and repo config are injected into the prompt as XML-tagged sections. The model returns strict JSON and nothing else.

---

## Overview

The prompt is responsible for generating four fields: `title`, `description`, `paths`, and `tags`. It never generates or modifies `lastValidated` or `maxAgeDays`. Those are human-controlled and the script will refuse to write them even if the model returns them.

The most important field is `description`. It is only generated once, on the first time the script processes a file. The script checks whether a valid description already exists before calling the API. If one exists, it skips the API call entirely for that field. This prevents the model from silently overwriting a description that may have been manually refined.

---

## Prompt structure

The prompt uses a system-prompt-only structure. All instructions and injected content live in the system prompt. There is no user message.

Content is injected using XML-tagged sections interpolated into the prompt text at runtime. This approach separates instructions from data clearly and works consistently across all major providers.

```
<document>
{{ doc_content }}
</document>

<existing_frontmatter>
{{ existing_frontmatter }}
</existing_frontmatter>

<repo_config>
{{ agentsrc_yaml }}
</repo_config>
```

If any section is empty (for example, a new doc has no existing frontmatter), the corresponding tags are included but left empty. This keeps the prompt structure stable across all cases.

A note on prompt size: if docs in the repo are long, a system-prompt-only design can produce very large prompts. If you encounter provider-specific size limits or parsing issues, the recommended fallback is to move the `<document>` section into a user message while keeping all instructions in the system prompt. This does not change the output behavior and is fully provider-agnostic.

---

## Instructions block

The instructions block tells the model exactly what to do, what constraints to follow, and what to ignore.

The key rules are:

- Generate values only for `title`, `description`, `paths`, and `tags`.
- Never generate or return `lastValidated` or `maxAgeDays`.
- If a valid value already exists for a field in `<existing_frontmatter>`, return it unchanged. Do not improve, rephrase, or expand it.
- If a field is missing or empty in `<existing_frontmatter>`, generate a new value following the field rules below.
- Return only a JSON object. No preamble, no explanation, no code block wrapper.

### Field rules

**`title`:** A short plain string in sentence case. Extract the most accurate descriptive title from the document content. Do not use the filename.

**`description`:** This is the most important field. Write it as a trigger condition for an AI agent making a load-or-skip decision. Follow this formula exactly: "Load when [specific trigger conditions]." Be specific. Name the actual concepts, components, or tasks an agent would be working on when this doc is relevant. Do not summarize the document. Do not describe what the document covers. Maximum 160 characters.

**`paths`:** A list of minimatch glob patterns for the code paths this document describes. Infer these from the document content. If the document references specific files, directories, or modules, include them. If the document is conceptual and not tied to specific code paths, return an empty list.

**`tags`:** A list of lowercase freeform strings that categorize the document. Use terms that reflect the domain, technology, or workflow the document covers. Return an empty list if no meaningful tags apply.

---

## Output specification

The model must return a single JSON object with exactly these four keys. No other keys are permitted. Keys for empty optional fields must still be present with empty values.

```json
{
  "title": "string",
  "description": "string",
  "paths": ["string"],
  "tags": ["string"]
}
```

The script validates the response against this schema before writing anything to disk. See the validation rules in the frontmatter schema document for the full set of checks.

---

## Few-shot examples

Two examples are embedded directly in the prompt to anchor the model's behavior for the `description` field, which is the most likely field to be generated incorrectly.

**Good example**

Input document: A guide covering how the token refresh service works, when tokens expire, and how to configure refresh intervals.

```json
{
  "description": "Load when modifying token refresh logic, expiry configuration, or debugging authentication failures."
}
```

This is correct because it names specific trigger conditions an agent would encounter. It is actionable.

**Bad example**

Same input document.

```json
{
  "description": "This document covers the token refresh service, including expiry behavior and configuration options."
}
```

This is incorrect because it summarizes the document instead of specifying when to load it. An agent reading this has no clear signal for when the doc is relevant.

Include both examples in the prompt with explicit labels: one marked `CORRECT` and one marked `INCORRECT`. This contrast is more effective than a correct example alone.

---

## Edge case handling

**Empty or near-empty document:** If the document content is fewer than 50 words, the model has insufficient signal to generate reliable paths or tags. The script detects this before calling the API and skips path and tag generation. It still generates a title and description from whatever content exists. Both fields are flagged as low-confidence in the PR body.

**No code relationship:** If the document is conceptual, architectural, or process-oriented and contains no references to specific files, directories, or modules, the model should return an empty `paths` list. The instructions block states this explicitly. The script does not penalize an empty `paths` list.

**Existing valid frontmatter:** If all four LLM-owned fields are already present and valid in the existing frontmatter, the script skips the API call entirely and returns without making any changes. This avoids unnecessary API costs on docs that only had minor content edits.

**Model returns extra keys:** The validation step strips any keys not in the expected schema before writing. This prevents the model from writing `lastValidated` or `maxAgeDays` even if it ignores the instruction not to.

**Model returns malformed JSON:** The script wraps the JSON parse step in a try-catch. On failure, it logs the raw response, sets `status: llm-error` in the frontmatter, and continues processing the next file. The PR body includes a warning for each file that errored.

---

## Prompt text

The following is the full system prompt with placeholder variables. Replace `{{ doc_content }}`, `{{ existing_frontmatter }}`, and `{{ agentsrc_yaml }}` at runtime in the script.

```
You generate frontmatter fields for documentation files in a software repository.
Your output is consumed by an automated script and by AI agents that use the
frontmatter to decide whether to load a document. Accuracy and specificity are
critical.

You are responsible for four fields only: title, description, paths, and tags.
You must never generate or return lastValidated or maxAgeDays. If you return
those keys, they will be discarded.

Rules:
- If a valid value already exists for a field in <existing_frontmatter>, return
  it unchanged. Do not rephrase, improve, or expand it.
- If a field is missing or empty, generate a new value following the field rules
  below.
- Return only a valid JSON object. No preamble. No explanation. No code block.
  No trailing text.

Field rules:

title: A short plain string in sentence case. Derive it from the document
content. Do not use the filename.

description: An AI agent load trigger. Follow this formula exactly:
"Load when [specific trigger conditions]." Be specific — name the actual
concepts, components, or tasks that make this document relevant. Do not
summarize the document. Do not describe what it covers. Maximum 160 characters.

CORRECT example:
"Load when modifying token refresh logic, expiry configuration, or debugging
authentication failures."

INCORRECT example:
"This document covers the token refresh service, including expiry behavior and
configuration options."

The incorrect example summarizes the document. The correct example names trigger
conditions. Always follow the correct pattern.

paths: A list of minimatch glob patterns for the code paths this document
describes. Infer from document content. If the document references specific
files, directories, or modules, include them. If the document is conceptual and
not tied to specific code, return an empty list.

tags: A list of lowercase freeform strings. Use terms that reflect the domain,
technology, or workflow the document covers. Return an empty list if no
meaningful tags apply.

Output schema (return exactly this structure, no other keys):
{
  "title": "string",
  "description": "string",
  "paths": ["string"],
  "tags": ["string"]
}

<document>
{{ doc_content }}
</document>

<existing_frontmatter>
{{ existing_frontmatter }}
</existing_frontmatter>

<repo_config>
{{ agentsrc_yaml }}
</repo_config>
```

---
date: 2026-04-04
topic: open-ideation
focus: open-ended
---

# Ideation: code-docs Open Improvement Ideas

## Codebase Context

**Project shape:** Python-based documentation automation system that helps AI agents efficiently discover and load in-repo documentation. ~390 LOC across 3 core scripts (`build-index.py`, `check-staleness.py`, `frontmatter.py`), with YAML frontmatter-driven docs in `docs/`, an auto-generated `AGENTS.md` index, and GitHub Actions CI/CD (`docs-sync.yml`). Minimal dependencies (PyYAML only). Currently 7 docs indexed.

**Notable patterns:** Frontmatter schema with `paths`, `tags`, `lastValidated`, `maxAgeDays`. "Load when [conditions]" description formula for agent routing decisions. Token-efficient lazy-loading model. All automation runs via GitHub Actions + Claude Code.

**Known pain points:** No semantic filtering (linear scan of full table), human discipline needed for `lastValidated`, description quality depends on LLM with no validation, limited test coverage, no frontmatter schema enforcement in CI, flat `docs/*.md` glob misses subdirectories.

**Critical finding: docs-reality gap.** The documentation describes a richer system than what exists:

- `update-frontmatter.py` and `llm.py` are referenced in automation-workflow.md but don't exist
- `frontmatter-schema.md` line 107 says "Tags appear in the AGENTS.md index table" but they don't
- Validation rules at frontmatter-schema.md lines 159-172 are documented but unenforced
- The provider-agnostic LLM layer is described in detail but doesn't exist
- `status: llm-error` is described as a failure mode but nothing generates it

**Key architectural insight: descriptions are the product.** The system's entire value proposition is one binary decision per doc: load or skip. The description field is the sole signal for that decision. Yet descriptions are generated once, never tested, never measured, and never updated even as doc content evolves. Descriptions are treated as immutable API contracts (frontmatter-schema.md line 136), which prevents silent breakage but guarantees silent rot.

**Integration blind spot: cold-start problem.** CLAUDE.md is auto-loaded at session start. AGENTS.md is not. Agents have no prompt-level signal that code-docs documentation exists unless they happen to discover the file. The doc system is invisible at the moment it matters most.

**IR theory gap:** The system has a forward index (doc -> metadata) but no inverted index (tag -> docs, path -> docs). Tags and paths exist in frontmatter but serve zero routing purpose -- they are write-only metadata. The most basic search engine data structure is missing.

**Past learnings:** Existing brainstorm/plan for onboarding docs (March 2026). Docs cover prompt design (model-agnostic and Claude-specific), automation workflow, frontmatter schema, agents-md structure. No `docs/solutions/` yet.

## Ranked Ideas

### 1. Git-Derived Staleness -- Replace Manual lastValidated

**Description:** Replace the manually-maintained `lastValidated` frontmatter field with git-derived validation signals. The most recent commit that meaningfully touches a doc's body content becomes the validation date. Merging a staleness PR is an implicit revalidation. Remove `lastValidated` from the human-managed schema entirely.

**Rationale:** `lastValidated` is the system's single biggest fragility. It depends entirely on human discipline to update a date string, but no workflow or tooling exists to prompt that action. The staleness PR tells humans to "update lastValidated" -- a manual step with no enforcement. In practice, either humans forget (producing false staleness noise) or rubber-stamp (producing false freshness). Both failure modes destroy trust in the system. Git already tracks exactly when docs were last modified. Six of six first-round ideation agents independently generated this concept. Both adversarial critics kept it as the strongest idea.

**Downsides:** Editing a doc doesn't always mean validating it (e.g., fixing a typo doesn't confirm technical accuracy). Removes a deliberate human review signal. Requires defining "meaningful edit" vs. cosmetic change.

**Confidence:** 90%

**Complexity:** Medium

**Status:** Unexplored

### 2. Description Drift Detection

**Description:** When a doc's body content is modified, automatically re-generate a shadow description from the current content and compare it against the frozen live description. If they diverge significantly, flag the doc as "description-drifted" -- a new staleness signal distinct from time or path staleness. Surface the old and proposed new descriptions side-by-side in the sync PR for human review.

**Rationale:** The system's write-once policy for descriptions (frontmatter-schema.md line 136) prevents silent breakage but guarantees silent rot. A doc can be rewritten substantially while its description still reflects the original content. The staleness system checks time drift and code drift, but never description-content drift -- the most dangerous failure mode, where the routing signal actively misleads agents. The infrastructure for detection already exists: `docs-sync.yml` already invokes Claude Code with full doc content on every change. Adding a comparison step is incremental, not architectural. Four independent ideation agents across two rounds generated this concept.

**Downsides:** Requires an LLM call to generate the shadow description, adding CI cost. The "significant divergence" threshold needs tuning. May surface false positives on docs with stable trigger conditions but reorganized internal content.

**Confidence:** 85%

**Complexity:** Medium

**Status:** Unexplored

### 3. CLAUDE.md Bridge -- Auto-Inject Doc Awareness at Session Start

**Description:** Add a build step (or section in `build-index.py`) that generates a compact doc manifest and injects it into the project's CLAUDE.md between markers. Every agent session then starts with awareness of available docs and their trigger conditions -- without the agent needing to discover or read AGENTS.md at all.

**Rationale:** CLAUDE.md is loaded automatically at session start. AGENTS.md is not. This creates a cold-start problem: agents working on a task may never realize relevant documentation exists. The current CLAUDE.md files in this repo contain vexp instructions but zero references to AGENTS.md or the docs/ directory. Bridging the two guarantees doc awareness from the first message. This is the simplest, highest-leverage integration improvement -- one build step, zero new dependencies, solves a fundamental discovery gap.

**Downsides:** Adds content to CLAUDE.md that increases base token cost for every session. Must be kept compact to avoid bloating the always-loaded context. Creates a second place to maintain the doc manifest (though it's auto-generated).

**Confidence:** 85%

**Complexity:** Low

**Status:** Unexplored

### 4. Docs-Reality Consistency Checker

**Description:** Create a `check-consistency.py` script that cross-references documentation claims against the actual filesystem and codebase. Verify: files mentioned in docs exist, scripts listed in shared-tooling tables exist, AGENTS.md column definitions match `TABLE_HEADER`, `.agentsrc.yaml` sections described in docs match the actual config. Run it in CI alongside pytest.

**Rationale:** The deep codebase scan revealed a massive docs-reality gap: `update-frontmatter.py` and `llm.py` are referenced but don't exist, `frontmatter-schema.md` says "Tags appear in the AGENTS.md index table" but they don't, validation rules are documented but unenforced. Every single one of these gaps is mechanically detectable -- file existence checks, string matching, column counting. A consistency checker turns a one-time audit into a continuous feedback loop. For a project that exists to make documentation trustworthy for AI agents, having docs that mislead about the system itself is an existential credibility gap.

**Downsides:** The checker needs to be taught what to check. Maintaining it adds overhead. Some claims are intentionally aspirational.

**Confidence:** 80%

**Complexity:** Medium

**Status:** Unexplored

### 5. Token Budget Metadata in the Index

**Description:** Add a `Size` column to the AGENTS.md index table showing approximate token count per doc (e.g., "~850 tokens"), computed by `build-index.py` at generation time. Agents can then make informed load/skip tradeoffs when multiple descriptions match.

**Rationale:** Agents make load decisions completely blind to cost. Loading 3 docs might consume 5% of context or 50%. When multiple descriptions match, the agent has no basis for prioritization. `build-index.py` already reads each doc's full content; adding a character or word count to `build_table_row()` is one line of code.

**Downsides:** Token counts are model-dependent. May encourage agents to skip valuable large docs.

**Confidence:** 80%

**Complexity:** Low

**Status:** Unexplored

### 6. Inverted Index on Tags and Paths

**Description:** Generate a second index structure -- an inverted index -- that maps each tag and each path glob to the set of docs containing it. Emit as a structured lookup section in AGENTS.md (e.g., a "Quick Lookup" block above the table). An agent editing `scripts/agents/build-index.py` can jump directly from that path to the relevant docs. An agent working on `ci` tasks can jump to docs tagged `ci`.

**Rationale:** Every search engine's core data structure is the inverted index. code-docs only has a forward index (AGENTS.md table: doc -> description). Tags are parsed by `frontmatter.py`, stored in every doc's frontmatter, promised by `frontmatter-schema.md` line 107 to appear in the index table, and then completely discarded. Paths are used for staleness detection but never for routing. The inverted index makes both fields functional for the first time. At 7 docs with 12 unique tags and 8 unique path patterns, the inverted index is compact -- it would add ~15 lines to AGENTS.md.

**Downsides:** Adds complexity to the index format. Agents need to understand two index structures. Broad globs (e.g., `docs/**`) produce noisy lookup results.

**Confidence:** 75%

**Complexity:** Medium

**Status:** Unexplored

### 7. Description Routing Test Suite (Canary + Golden Set)

**Description:** Two-tier approach. **Tier 1 (Canary):** Add a `docs/_canary.md` with a deliberate description and a CI test that verifies routing behavior. **Tier 2 (Golden Set):** Add `tests/routing-golden.yaml` mapping known tasks to expected doc sets. Test descriptions against it. Catches gross failures like indistinguishable descriptions or unreachable trigger conditions.

**Rationale:** The description field IS a testable assertion: "Load when [conditions]" predicts agent behavior. Zero tests validate this. The `llm-prompt-design-agnostic.md` description references a provider-agnostic LLM layer that doesn't exist -- its trigger condition is already dead. A routing test would catch this.

**Downsides:** Synthetic routing may not match real agent behavior. The golden set requires human curation.

**Confidence:** 70%

**Complexity:** Low (canary) / Medium (golden set)

**Status:** Unexplored

### 8. Local Description Preview CLI

**Description:** Add a local command (`python scripts/agents/preview-description.py docs/my-new-doc.md`) that calls the same LLM with the same prompt used in CI, shows the generated description/title/paths/tags in the terminal, and lets the human iterate BEFORE pushing. No git, no CI, no PR round-trip.

**Rationale:** The current workflow forces a push-to-CI-to-PR round trip just to see what description the LLM will generate. If the description is bad, the human must manually edit it in another commit. This is the longest feedback loop in the doc creation process -- and the description is the most important field. The `frontmatter-prompt.md` (the exact CI prompt) already exists locally. `get-started.md` line 146 warns: "Review generated descriptions carefully on the first PR -- this is the one chance to catch them." A local preview removes the "one chance" constraint entirely.

**Downsides:** Requires a local API key (or local LLM). Adds a development dependency. Preview may differ from CI output if LLM temperature or model version differs.

**Confidence:** 70%

**Complexity:** Medium

**Status:** Unexplored

## Honorable Mentions

Ideas that didn't make the ranked list but deserve future consideration:

- **Description Collision Detection:** Pairwise similarity check between descriptions. Subsumed by the inverted index (#6) which makes overlap visible structurally.
- **Documentation Gap Map:** "Uncovered Areas" section in AGENTS.md listing paths not covered by any doc. Speculative (65% confidence) but an elegant complement to the inverted index.
- **Section-Level Addressability:** Load H2/H3 sections instead of whole docs. The boldest architectural idea across all 3 rounds (load granularity challenge). High complexity, uncertain payoff at current scale.
- **Progressive Disclosure Index:** Three tiers (description -> abstract -> full doc) instead of binary load/skip. Resolves ambiguity without full doc commitment.
- **Relevance Feedback via JSONL Log Convention:** The IR agent reframed the rejected telemetry idea compellingly: if agents follow the "read AGENTS.md" convention, logging load decisions is the same trust model. Still speculative but the framing is sound.
- **Conversational Doc Authoring ("Interview-to-Doc"):** Extract tacit knowledge via LLM interview instead of blank-page writing. Addresses the root cause of missing docs.

## Bug Fixes (Not Ranked)

| Fix | Complexity | Evidence |
|-----|-----------|---------|
| Multi-commit push: replace `HEAD~1..HEAD` with `before..sha` in docs-sync.yml | One line | get-started.md lines 165-173 |
| Recursive docs: change `*.md` to `**/*.md` in both scripts | Two lines | build-index.py:88, check-staleness.py:72 |
| Reconcile automation-workflow.md with Claude CLI reality | Doc edit | References update-frontmatter.py and llm.py that don't exist |
| Add Tags column to AGENTS.md table | ~10 lines | frontmatter-schema.md:107 promises it; TABLE_HEADER lacks it |
| Fix example table in agents-md-structure.md (4 cols to 5 cols) | Doc edit | Example shows 4 columns; actual has 5 |
| Add index generation timestamp inside AGENTS.md markers | ~3 lines | No way to know when index was last rebuilt |

## Rejection Summary

### Round 1 Rejections

| Idea | Reason Rejected |
|------|-----------------|
| Frontmatter Schema Validation CI Gate | System fails visibly on bad input; bureaucracy at current scale |
| Tag-based Semantic Filtering | Subsumed by inverted index idea (#6) |
| Description Quality Linter | LLM prompt already enforces rules; treats symptoms not causes |
| Multi-repo Meta-Index | Different product entirely; premature with zero multi-repo users |
| Agent Telemetry and Description Effectiveness | Requires instrumenting systems outside project's control |
| Staleness-Aware Freshness Scores | False precision -- agents make binary load/skip decisions |
| Structured YAML/JSON Sidecar | LLMs parse Markdown tables trivially; second artifact to maintain |
| Agent-Proposed Description Improvements | Contradicts documented design decision (line 136) |
| Content-Hash Staleness | Redundant with git log on the doc file itself |
| Scaffold Generator CLI | Complexity-to-value ratio terrible for a 5-file copy operation |
| Atomic Frontmatter Rollback | PR review already catches LLM failures |
| Query Interface Replacing Table Scan | Building a search engine for 7 table rows |

### Round 2 Rejections

| Idea | Reason Rejected |
|------|-----------------|
| Description Versioning with Changelog | Versioning doesn't fix drift; detection does |
| Composable Micro-Descriptions (trigger facets) | Fundamental schema change for marginal gain |
| Description-as-Embedding Index | Requires embedding infrastructure; overkill |
| Description A/B Testing | No telemetry mechanism to measure outcomes |
| Build provider-agnostic LLM layer (llm.py) | Different product; Claude CLI works fine |
| Implement status: llm-error | Narrow failure mode already mitigated by PR review |
| Doc Dependency Declarations (requires field) | Docs cross-reference but are not prerequisites |
| Self-healing staleness (LLM evaluates diffs) | LLM judgment for automated writes is unreliable |
| Staleness triage dashboard (STALENESS.md) | Persistent file adds maintenance burden |
| Tag evolution via periodic re-tagging | Tags aren't consumed by anything; fix consumer first |
| Description specificity scorer | Subsumed by drift detection + routing tests |
| Dead description detection | Subsumed by routing test suite golden set |

### Round 3 Rejections

| Idea | Reason Rejected |
|------|-----------------|
| Embedded doc fragments in code (@agent-doc) | Fundamental architecture change; breaks existing workflow |
| Kill write-once descriptions (auto-regenerate) | Drift detection (#2) achieves the same goal more safely |
| Query-time dynamic index (search endpoint) | Overkill; inverted index + CLAUDE.md bridge solve the routing gap more simply |
| Agent feedback loop (telemetry) | Still speculative despite reframe; save for future |
| Semantic embedding matching | Requires embedding infrastructure; inverted index is simpler |
| Cross-repo meta-index / federated discovery | Premature; same rejection as round 1 |
| Per-subtask doc scoping (roles field) | No multi-agent consumers yet; inverted index enables this later |
| IDE extension (VS Code gutter indicators) | High effort; outside repo scope |
| Multi-field weighted ranking (BM25-lite) | Over-engineering; inverted index is sufficient |
| Faceted index (parallel retrieval dimensions) | Inverted index achieves 80% of the value at 20% complexity |
| Query expansion via tag synonyms | Premature optimization; need tag consumers first |
| Doc health dashboard (HTML) | Nice-to-have but not core; staleness PR is sufficient |
| One-command doc scaffolder | Nice quality-of-life but doesn't advance the system architecturally |
| Frontmatter linter as pre-push hook | Local preview CLI (#8) provides superset value |
| "When to write a doc" decision tree | Useful but is a documentation task, not a system feature |

## Session Log

- 2026-04-04 (round 1): Initial open-ended ideation -- 48 raw ideas across 6 sub-agents (pain/friction, unmet needs, inversion/automation, assumption-breaking, leverage/compounding, edge cases). Deduped to 20 + 5 combos. Two adversarial critics. 5 initial survivors.
- 2026-04-04 (round 2): Deep dive after user requested creative push. Deep-read all core files. Discovered docs-reality gap and "description as product" framing. 40 ideas across 5 deeper frames (description as product, implementation gaps, agent experience, description testing, maintenance loop). Combined total: 88 raw, 30 themes. 7 survivors.
- 2026-04-04 (round 3): User requested further depth. 31 ideas across 4 novel frames (challenge core model, ecosystem integration, IR theory, human workflow). Identified cold-start problem, inverted index gap, and human authoring workflow gap. Combined total: 119 raw ideas across 15 agents. Final: 8 ranked survivors + 6 honorable mentions + 6 bug fixes. 39 rejected with reasons.

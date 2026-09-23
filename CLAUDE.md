# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

### Derive tests from the requirement, not from the code

Write the test cases from the issue, spec, or acceptance criteria **before** the
implementation, and land them as their own failing commit.

A test written after the code inherits the code's assumptions. It asserts what was built
rather than what was asked, so it passes by construction and cannot fail:

- asserting a flag that was just set, instead of the property that flag was meant to produce;
- asserting what a function returns, instead of running it through the consumer that has to
  accept it;
- covering the fields that were implemented, instead of the fields the requirement lists.

Read the requirement's own acceptance conditions line by line and turn each into a named
test. A requirement that is read once and then worked from memory is how a stated field goes
missing.

For anything producing an artifact someone else reads, assert a property of the whole
artifact — "this directory contains nothing derived from X" — not of the switch that was
supposed to produce it.

**Then break the code each new test guards, and confirm the test fails.** That check
establishes only that the test detects changes to what was built. It cannot tell you whether
what was built satisfies the requirement; deriving the cases from the requirement first is
what does that.

## 5. Comments Explain Durable Constraints

Prefer clear names, small functions, and explicit types over explanatory comments.

Use comments for information the code cannot express clearly:
- Why a non-obvious approach is necessary.
- Invariants, units, coordinate systems, and compatibility constraints.
- Important failure behavior or why a simpler alternative is incorrect.
- For non-obvious formulas: the modeled quantity, units/sign convention,
  normalization or aggregation, and the provenance of empirical coefficients.

Label tuned constants and thresholds as heuristics unless they are validated. Cite the
primary paper, standard, fixture, or calibration dataset for externally derived values; do
not imply that research supports an exact coefficient when it supports only the general
relationship. If provenance cannot be established, add a targeted `TODO: add comment` that
names the missing evidence instead of inventing a rationale.

Do not use production comments to:
- Restate the code or narrate it line by line.
- Preserve debugging history, previous outputs, or a single fixture's measurements.
- Explain that a test now passes or list every rejected implementation.
- Narrate obvious arithmetic or duplicate type annotations and parameter names.

Keep inline comments short. Put concrete regressions in tests, measurement provenance in
fixture metadata, experiments and rejected alternatives in design documentation, and
historical context in commits or pull requests. Test names should describe behavior; add a
test comment only when it explains a non-obvious invariant.

Before keeping a comment, ask: "Will this still help after the current pull request is
forgotten?" Update or remove comments whenever their surrounding code changes.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

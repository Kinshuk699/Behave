# Copilot Instructions — Synthetic India

Adapted from [obra/superpowers](https://github.com/obra/superpowers). These rules are mandatory for every interaction.

---

## Iron Laws

```
1. NEVER ONE-SHOT AN APPLICATION OR LARGE FEATURE.
2. NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.
3. NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.
```

Violating the letter of these rules is violating the spirit. No exceptions without the human partner's explicit permission.

---

## Workflow: Brainstorm → Plan → Build → Verify

Every non-trivial task must follow this sequence. "Non-trivial" means anything beyond a single-line fix.

### 1. Brainstorm

Before writing any code:

- Explore the current project state (files, recent changes, context)
- Ask clarifying questions — one at a time
- Propose 2–3 approaches with trade-offs and a recommendation
- Get user approval on the approach before proceeding

**HARD GATE:** Do NOT write code, scaffold files, or take implementation action until the user has approved a design or approach. This applies to EVERY feature regardless of perceived simplicity.

### 2. Plan

After the user approves an approach:

- Map out which files will be created or modified
- Break work into bite-sized tasks (one action each, 2–5 minutes)
- Each task follows TDD: write failing test → verify it fails → write minimal code → verify it passes → commit
- Present the plan to the user for approval before starting

### 3. Build — One Task at a Time

- Work on exactly ONE task at a time
- Mark it in-progress, complete it, verify it, then move to the next
- Do not batch multiple tasks or jump ahead
- Each task should produce self-contained changes that make sense independently
- Use `manage_todo_list` to track progress visibly

### 4. Verify Before Claiming Completion

Before claiming ANY task or feature is done:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does the output confirm the claim?
5. ONLY THEN: State the claim WITH evidence

**Red flags — STOP if you catch yourself:**

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Done!")
- About to commit without running tests
- Relying on partial verification

---

## Test-Driven Development

### The Cycle

```
RED    → Write one minimal failing test
VERIFY → Run it, confirm it fails for the right reason
GREEN  → Write simplest code to pass the test
VERIFY → Run it, confirm all tests pass
REFACTOR → Clean up only, keep tests green
REPEAT → Next failing test for next behavior
```

### Rules

- Write code before the test? Delete it. Start over.
- Test passes immediately? You're testing existing behavior. Fix the test.
- Don't add features, refactor other code, or "improve" beyond the test.
- Mocks only when unavoidable. Test real code.

### When To Use TDD

**Always:** New features, bug fixes, refactoring, behavior changes.

**Exceptions (ask user first):** Throwaway prototypes, configuration files, data/persona JSON files.

---

## Anti-Patterns — Things You Must Never Do

| Anti-Pattern                                 | Why It's Wrong                                                     |
| -------------------------------------------- | ------------------------------------------------------------------ |
| One-shotting an entire app or feature        | Guarantees errors, prevents verification, breaks trust             |
| Writing code before tests                    | Can't prove tests catch anything                                   |
| Claiming "done" without running verification | Evidence before claims, always                                     |
| Adding features beyond what was asked        | Over-engineering wastes time and adds bugs                         |
| Skipping brainstorm for "simple" tasks       | "Simple" is where unexamined assumptions cause the most waste      |
| Batching multiple tasks                      | Lose traceability, verification becomes partial                    |
| Writing tests after implementation           | Tests-after answer "what does this do?" not "what should this do?" |

---

## Project-Specific Context

### Tech Stack

- Python 3.12, Pydantic v2, Anthropic SDK, OpenAI SDK
- Memory retrieval: score = α·recency + β·relevance + γ·importance
- Medallion architecture: bronze → silver → gold
- Test runner: `pytest`
- Package manager: pip with pyproject.toml

### Key Files

- `thoughts.md` — persistent working memory, keep updated
- `capstone_roadmap.md` — execution brief, the plan of record
- `src/synthetic_india/` — all application code
- `data/personas/` — persona JSON profiles
- `tests/` — all test files

### Code Review Checklist

After completing a logical chunk of work, review against:

- [ ] Every new function has a test
- [ ] All tests pass (run `pytest` and show output)
- [ ] No import errors or type issues
- [ ] Pydantic models validate correctly
- [ ] Async patterns are consistent (async def + await)
- [ ] Cost tracking is present on LLM calls
- [ ] No hardcoded API keys or secrets

---

## Communication Protocol

- One question at a time when clarifying
- Present trade-offs before recommending
- Show evidence, not assertions
- Update `thoughts.md` with decisions and learnings
- Use `manage_todo_list` for all multi-step work

# Ah-Ha Moments — Accumulated Insights

These are the key insights discovered while building Synthetic India. Each one changed how we think about the system.

## From the Generative Agents Paper

1. **Reflection = learning.** Repeated low-level events become stable beliefs. Without it, agents remember but don't learn.

2. **Plans are memory.** The system retrieves from intended future actions as well as past observations.

3. **Retrieval discipline under context limits.** The paper is really about deciding which memories to surface — not about storing them.

## From the Spec & Design

4. **Calibration data is the moat.** Not the prompt library. Real client outcomes that let you tune persona reactions.

5. **CreativeCard is the normalization boundary.** The most important design artifact — it's where messy real-world ads become structured data.

6. **"Simple" is where assumptions hide.** The superpowers principle: unexamined assumptions cause the most waste in "simple" tasks. → All components

7. **Evidence before claims.** No "should work" or "looks correct." Run the test, read the output, verify the claim. → TDD workflow

## From v2 Evolution

8. **200K context = skip retrieval.** Full memory dump mode is simpler AND eliminates retrieval errors (a top failure mode in the original paper).

9. **Vision-native > text extraction alone.** CreativeCard is no longer the SOLE input — the persona sees the raw ad too, catching cultural cues the extraction might miss.

10. **Critic Agent is the differentiator.** It prevents the system from being a "fancy wrapper around ChatGPT" by enforcing persona consistency, catching sycophancy, and validating cultural authenticity.

## From Implementation

11. **Inline critic > batch critic.** Quarantine before aggregation, no context overflow at 20+ personas, natural fit in existing loop.

12. **API keys leak in test output.** pytest error messages include dataclass repr — fixed with `repr=False`. Always check what shows up in test failures.

13. **Critic should fail-open.** If the LLM call fails, the evaluation is included anyway. Quality gate shouldn't block the whole run.



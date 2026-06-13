## Parent

#100

## What to build

Reorganize all model override select dropdowns and custom text inputs in `ModelQuotasTab` into four visual stage containers matching the pipeline flowchart:
1. **Stage 1: Pre-processing Models** (subtle indigo border & background): Contains the Relevance Filter Model and the Lightweight Fallback Model.
2. **Stage 2: AI Analysis Models** (subtle violet border & background): Contains the Summarization Task Model, Classification Task Model, Deep Analysis Task Model, and the Reasoning Fallback Model.
3. **Shared: Vector Indexing Service** (subtle emerald border & background): Contains the Primary Embedding Model and the Fallback Embedding Model.
4. **Pacing & Safety Controls** (subtle muted border & background): Contains the Daily API Spend Limit, Task Pacing Delay, Max Analysis Duration, and Analysis Batch Size.

Remove the sequential numbering (e.g. 1. Relevance Filter, 6. Lightweight Fallback, etc.) from the dropdown label titles and comments. Update Vitest unit tests to match the new label elements and ensure all tests continue to pass.

## Acceptance criteria

- [ ] Form input fields are grouped into four styled accent containers matching the flowchart stages.
- [ ] Fallback models are co-located in the same visual containers as their primary models.
- [ ] Misleading sequential numbers are completely removed from label titles.
- [ ] The PUT payload remains flat and preserves existing API compatibility.
- [ ] Vitest unit tests in `model-quotas.test.tsx` pass successfully.

## Blocked by

None - can start immediately

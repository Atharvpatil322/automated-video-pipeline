---
name: pipeline-stage
description: Use when adding or changing a pipeline stage, agent or provider in this video pipeline, so it matches the reference architecture.
---

# Adding a stage, agent or provider

1. Read the matching section of docs/ARCHITECTURE_REFERENCE.md first.
2. Contract first: add or update the Pydantic model / Protocol in app/schema/.
3. Agent = prompt file in prompts/ + schema + a thin async function returning (data, usage).
4. Provider = implements the Protocol, registered in app/providers/factory.py,
   key read from the per-job keys map, never from global state.
5. Stage = reports via callbacks (start, complete, skip, error, progress), checks
   cancel/dry-run/cost-rejected flags first, writes outputs to the run directory.
6. Failure policy: retry where the reference retries, otherwise degrade (null asset),
   do not crash the run.
7. Tests: mock the provider/LLM, cover validation rules and the failure path.
8. Update the doc-vs-reference notes if you deviate, and say why.

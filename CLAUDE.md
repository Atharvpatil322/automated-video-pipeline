# AI Video Pipeline

Python pipeline: topic -> research -> director -> TTS -> visuals -> assembly -> critic.
Architecture source of truth: docs/ARCHITECTURE_REFERENCE.md (derived from OpenReels).
Follow its architecture; do not copy its TypeScript line by line.

## Stack

FastAPI, Pydantic v2, MongoDB (motor), Redis + ARQ worker, React + Vite,
FFmpeg for assembly, Docker Compose. Python 3.11+, ruff, pytest.

## Layout

app/schema/ Pydantic contracts (DirectorScore, providers as Protocols)
app/agents/ one async function per LLM step, returns (data, usage)
app/providers/ llm, tts, image, stock, video, music + factory
app/pipeline/ orchestrator, utils, callbacks
app/config/ archetypes/\*.json, platforms, playbook
prompts/ markdown prompts + playbook.md
web/ React app

## Rules

- Fixed pipeline, not an agent framework. Agents are plain functions, one structured LLM call each.
- Pipeline code knows nothing about HTTP/Redis; it reports through a PipelineCallbacks interface.
- Every provider sits behind an interface and is created in the factory; keys are passed per job.
- Creative behaviour is data (archetype JSON, playbook.md), not code.
- Plan critique/revision happens before any paid asset generation.
- A failed scene produces a null asset and a black frame, never a crashed run.
- Cooperative cancel: check between stages only.
- Persist a job snapshot (Mongo) and send it first on every SSE connect.
- Cost estimate before spend; a gate in CLI, auto-approve in worker.

## Working agreements

- Build in phases; stop after each and summarize. Plan before coding.
- Mock all external services in tests; no API keys needed to run pytest.
- Where the reference doc and your assumptions differ, say so and ask.
- Run `ruff check` and `pytest` before declaring a phase done.
- Never commit secrets. Keys come from env or per-job input.

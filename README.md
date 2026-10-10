# AI Video Pipeline

Topic → research → director → TTS → visuals → assembly → critic. See
`CLAUDE.md` for stack/layout conventions and `docs/ARCHITECTURE_REFERENCE.md`
for the architecture this is built from.

## Setup

```
python -m venv .venv
source .venv/Scripts/activate   # or .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
```

Requires `ffmpeg`/`ffprobe` on `PATH` for anything that renders video
(assembly, visuals' image/video providers, offline mode). Everything else
only needs API keys for the vendors you actually use (see `.env.example`).

## Running the pipeline

```
python -m app.cli run --topic "the history of lighthouses" --archetype infographic
```

Useful flags: `--dry-run` (stop after the plan), `--yes`/`--max-cost 5.00`
(cost gate), `--no-tts`/`--no-visuals`/`--no-video`/`--no-music`/`--no-critic`
(skip a stage), `--from-stage {tts,visuals,assembly,critic}` on `replay`
(resume from an existing run directory's artifacts).

### Offline mode

`--offline` swaps every provider (LLM, TTS, image, stock, video) for a
deterministic local fake - no API keys, no network, cost $0. Useful for
trying the whole pipeline, or as a smoke test before wiring up real keys.

```
python -m app.cli run --topic "the history of lighthouses" --offline --yes
```

This still needs `ffmpeg`/`ffprobe` on `PATH` (the fakes use it to generate
placeholder audio/images/video, same as the real render stage). The run
directory is printed at the start (`output/<timestamp>-<topic-slug>/`); to
watch the result:

```
# Windows
start output\<run-dir>\final.mp4
# macOS
open output/<run-dir>/final.mp4
# Linux
xdg-open output/<run-dir>/final.mp4
```

## Server: API, queue, job state, live progress

`app/main.py` (FastAPI) and `app/worker.py` (ARQ, concurrency 1) wrap the
same pipeline the CLI runs - the pipeline itself knows nothing about
HTTP/Mongo/Redis. MongoDB is the source of truth for job state; Redis is
transport only (the ARQ queue, and a pub/sub channel per job for SSE).

### Start everything

```
cp .env.example .env    # fill in whichever provider keys you'll use, or leave
                         # blank and set OFFLINE=true below for a keyless run
docker compose up --build
```

Set `OFFLINE=true` (in `.env`, or `OFFLINE=true docker compose up`) to run
every job through the deterministic offline providers - no keys needed,
`$0` cost, same as `--offline` on the CLI. `api` on `:8000`, `mongo` on
`:27017`, `redis` on `:6379`, `web` (the React UI) on `:5174`.

## Running the UI

The UI lives in `web/` (React + TypeScript + Vite + Tailwind + TanStack
Query). It talks to the same API as the curl examples below.

**Dev mode** (hot reload, Vite proxies `/api` to `http://localhost:8000` -
start the API separately first, e.g. `uvicorn app.main:app --reload`):

```
cd web
npm install
npm run dev          # http://localhost:5173
```

**In docker compose**: the `web` service builds the production bundle and
serves it from nginx, which also proxies `/api/` to the `api` service (so
the browser only ever talks to one origin - no CORS, and SSE streams
through unbuffered):

```
docker compose up --build
# -> http://localhost:5174
```

Settings (API base URL, API token, BYOK provider keys) are configured from
the UI's own Settings page and kept in `sessionStorage` only - nothing is
written to disk or sent anywhere except as part of creating a job.

**Frontend checks**, from `web/`:

```
npm run typecheck    # tsc -b --noEmit
npm run lint         # eslint .
npm test             # vitest run - component tests + the SSE parser/hook
npm run test:e2e     # playwright - needs the compose stack up in OFFLINE mode
```

### Create a job (curl)

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"topic": "the history of lighthouses", "archetype": "infographic", "platform": "youtube"}'
# -> {"id": "<job-id>", "topic": "...", "archetype": "infographic", "status": "queued"}
```

Add `"keys": {"groq": "...", "elevenlabs": "..."}` to BYOK for that job
alone - never persisted (see app/server/security.py); omit it entirely in
offline mode.

### Stream progress (SSE)

```bash
curl -N http://localhost:8000/api/v1/jobs/<job-id>/events
```

Sends a `job.snapshot` event first (current Mongo state - safe to
reconnect any time), then forwards `stage.<name>`/`progress.<stage>`
events live, ending with `job.completed`/`job.failed`/`job.cancelled`.

### Cancel

```bash
curl -X POST http://localhost:8000/api/v1/jobs/<job-id>/cancel
# -> {"id": "...", "cancel_requested": true, "message": "...the current stage will finish first"}
```

Cooperative, stage-granularity - matches the reference. 409 if the job's
already finished.

### Fetch the video (with Range support, for seeking)

```bash
# whole file
curl http://localhost:8000/api/v1/jobs/<job-id>/files/final.mp4 -o final.mp4

# a byte range (what a browser <video> element does when seeking)
curl -H "Range: bytes=0-1023" http://localhost:8000/api/v1/jobs/<job-id>/files/final.mp4 -o chunk.bin
# -r is curl's shorthand for the same thing:
curl -r 0-1023 http://localhost:8000/api/v1/jobs/<job-id>/files/final.mp4 -o chunk.bin
```

Also serves `score.json`, `visuals.json`, `review.json`, `cost.json`,
`log.json` and anything else under that job's run directory, by the same
path convention, with path-traversal protection.

### List / inspect / delete

```bash
curl http://localhost:8000/api/v1/jobs                 # newest first
curl http://localhost:8000/api/v1/jobs/<job-id>         # full Mongo document
curl -X DELETE http://localhost:8000/api/v1/jobs/<job-id>   # 409 if queued/running
```

### Running the server test suite

```
pytest tests/server      # mongomock_motor + fakeredis - no real Mongo/Redis needed
```

Covered: request validation, enqueue, full job lifecycle to completed,
SSE snapshot-then-events and the subscribe-before-snapshot race,
reconnect-after-completion, cancel between stages, delete rules, path
traversal, Range requests, worker crash recovery, and a scan confirming
per-job API keys never land in Mongo, Redis, or logs.

## Testing

```
pytest              # mocked/offline only - no API keys, no network required
pytest -m live      # also runs tests that need a real key/network (none yet)
```

Tests marked `@pytest.mark.live` are skipped by default (`pytest.ini`'s
`addopts` excludes them) since this project's working agreement is that the
whole suite runs without any API keys. Add that marker to a test the
moment it needs to make a real network call against a real vendor.

A few tests (assembly/render, the offline end-to-end run) additionally
skip themselves at runtime if `ffmpeg`/`ffprobe` aren't on `PATH`, independent
of the `live` marker - they're still API-key-free, just render-dependent.

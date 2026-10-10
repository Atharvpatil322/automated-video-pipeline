# OpenReels Architecture Reference

Oct 3, 2026 · @Atharv

## Overview

OpenReels is a fixed six-stage pipeline (research, director, TTS, visuals, assembly, critic) that turns a topic string into a vertical MP4. It is plain code wrapped around a handful of LLM calls, not an autonomous multi-agent system. This reference is written from the source files (orchestrator, schemas, providers), not the README. Where the README or docs disagree with the code, this document follows the code and flags it in the last section.

**Design principles visible in the code**

- **Fixed order, typed hand-offs.** Stages run in a hardcoded chain. Every LLM call returns data validated by a Zod schema, so a bad response fails at the boundary instead of deep in rendering.
- **One contract between creative and production.** The director produces a single `DirectorScore` JSON. Everything after it (voiceover, visuals, music, render) reads only that score plus generated assets. The score is saved as `score.json` and can be replayed without repeating research or the director.
- **Providers behind small interfaces.** LLM, TTS, image, stock, video and music each have a minimal interface and a factory that wires implementations by key. Swapping a vendor never touches the pipeline.
- **Spend is gated.** After the director finishes, the pipeline estimates cost and asks for confirmation before any paid asset call. `--dry-run` stops at that point and prints the score.
- **Progress leaves through callbacks.** The engine never prints or serves anything itself. A `PipelineCallbacks` object lets the CLI, the worker and the web UI share the same engine.
- **Fail soft early, fail hard late.** A failed research search falls back to topic-only. A failed scene asset is recorded as `null` and the run continues. A failed voiceover or render stops the run.

**What matters for rebuilding**

The parts to reproduce are the stage flow, the `DirectorScore` contract, the provider interfaces and factory, the prompts, and the score-to-render mapping. The web UI, REST server, job queue and Docker setup are delivery wrappers and can come later. Mastra, the workflow library, is used only to chain six steps. Any sequence of async functions gives the same behavior.

## Pipeline architecture

&#91;embedded content: pipeline flow · 6 stages, 1 loop\]

OpenReels is a straight six-stage chain; stages pass data through four shared closure objects, and the only loop is the director's plan-critique-revise cycle that runs before any money is spent on assets.

## Data contracts

Four structures cross stage boundaries, and every LLM-produced one is validated with a Zod schema before the next stage sees it. The `DirectorScore` is the central one.

**ResearchResult** (research to director): `summary` (string), `key_facts` (string\[\]), `mood` (string), `sources` (string\[\]).

**DirectorScore** (director to everything after):

| Field           | Type      | Rule                                                                                                                                       |
| --------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `emotional_arc` | string    | Non-empty. A short journey label such as "curiosity-to-wisdom".                                                                            |
| `archetype`     | string    | Must be a registered archetype key. Drives colors, captions, pacing tier.                                                                  |
| `music_mood`    | enum      | One of 8: epic_cinematic, tense_electronic, chill_lofi, uplifting_pop, mysterious_ambient, warm_acoustic, dark_cinematic, dreamy_ethereal. |
| `scenes`        | Scene\[\] | 3 to 16 scenes.                                                                                                                            |

**Scene**:

| Field           | Type         | Rule                                                                                                                                                       |
| --------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `visual_type`   | enum         | ai_image, ai_video, stock_image, stock_video, text_card.                                                                                                   |
| `visual_prompt` | string       | Non-empty. Meaning depends on type: a scene description for AI visuals, a 3-5 word search query for stock, a headline phrase for text cards.               |
| `motion`        | enum         | zoom_in, zoom_out, pan_right, pan_left, static. Set to static for ai_video.                                                                                |
| `script_line`   | string       | Non-empty. The voiceover for this scene.                                                                                                                   |
| `transition`    | enum or null | none, crossfade, slide_left, slide_right, wipe, flip. Describes the cut into the next scene. Null falls back to the archetype default, then to a hard cut. |

One cross-field rule is enforced with a Zod refinement: no more than two consecutive scenes may share a `visual_type` (the "golden rule").

**Two schemas for one object.** The director's LLM call uses a looser `DirectorScoreRaw` with no minimum or maximum on `scenes`, because Gemini's structured-output API rejects `minItems` above 1. The result is then parsed with the strict `DirectorScore`. If parsing fails, the call is retried (up to 3 attempts) with the error message appended to the prompt. This pattern is worth copying for any provider-agnostic structured output.

**CritiqueResult** (critic to director): `score` (number, 1-10), `strengths` (string\[\]), `weaknesses` (string\[\]), `revision_needed` (boolean), `revision_instructions` (string or null), `weakest_scene_index` (number or null, 0-based).

**Provider result types** (defined in `schema/providers.ts`):

| Type             | Fields                                                                          |
| ---------------- | ------------------------------------------------------------------------------- |
| `LLMResult<T>`   | `data`, `usage` { inputTokens, outputTokens }                                   |
| `TTSResult`      | `audio` (Buffer), `words` (WordTimestamp\[\]: word, start, end in seconds)      |
| `StockCandidate` | `url`, `width`, `height`, `duration?`, `id` (provider-specific, used for dedup) |
| `StockAsset`     | `filePath`, `width`, `height`, `duration?`                                      |
| `VideoResult`    | `filePath`, `durationSeconds`                                                   |
| `MusicResult`    | `filePath`, `durationSeconds?`, `metadata?`                                     |

**Run artifacts on disk.** Each run writes to `output/<date>-<time>-<topic-slug>/` containing `assets/`, `score.json`, `final.mp4` and `log.json`. The log records the topic, stage timings and statuses, estimated and actual cost, stock and video resolution details, music resolution, and whether the run was a replay. It is written in a `finally` block, so a failed run still leaves a log.

## LLM steps and prompts

The "agents" are six plain async functions in `src/agents/`. Each takes an `LLMProvider` plus inputs, makes one structured-output call, and returns `{ data, usage }`. None keeps state, calls tools of its own, or calls another agent. The orchestrator decides when each runs.

| Step                         | Input                               | Output                  | What the code does                                                                                                                                                                                   |
| ---------------------------- | ----------------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Research                     | topic                               | ResearchResult          | Calls the LLM with `enableWebSearch: true`. Prompt: "Research this topic for a short-form video script".                                                                                             |
| Creative director (generate) | topic, research, options            | DirectorScore           | Builds one long user message (see below). Up to 3 attempts, each retry appends the previous validation error.                                                                                        |
| Critic                       | DirectorScore, topic, pacing        | CritiqueResult          | Scores the plan 1-10 against a rubric. Reviews the plan text, never rendered video.                                                                                                                  |
| Creative director (revise)   | score, critique, research           | DirectorScore           | Sends the current plan, the critic's weaknesses and its revision instructions. Up to 2 attempts. Forces `archetype` back to the original, because the LLM sometimes changes it despite instructions. |
| Image prompter               | scene prompt, narration, archetype  | optimized prompt string | Rewrites a short scene description into a full generator prompt. Same function has a `video` mode that writes a motion and camera prompt.                                                            |
| Music prompter               | mood, arc, scene timings, narration | Lyria prompt string     | Writes timestamped musical direction. Rejects an empty result.                                                                                                                                       |

**What the director's user message contains.** Topic, research summary, key facts and mood. Then either a fixed archetype or the list to choose from. Then a pacing instruction, one of three paths: an explicit override, the tier of the chosen archetype, or the full tier table when the LLM picks the archetype. Then the allowed visual types (five if video providers exist, otherwise four). Then hard rules: no visual type more than twice in a row, every scene needs a `script_line`, the first scene is a strong hook, and cut a scene rather than cram. An optional creative brief from the producer is appended when supplied.

**Pacing tiers** (scenes, words per scene, total words):

| Tier      | Scenes | Words per scene | Total words | Archetypes                                                                                                     |
| --------- | ------ | --------------- | ----------- | -------------------------------------------------------------------------------------------------------------- |
| fast      | 8-12   | 8-12            | 90-120      | infographic, bold_illustration, comic_book                                                                     |
| moderate  | 7-10   | 10-16           | 100-140     | warm_editorial, editorial_caricature, anime_illustration, vintage_snapshot, surreal_dreamscape, gothic_fantasy |
| cinematic | 5-8    | 15-22           | 90-130      | cinematic_documentary, moody_cinematic, studio_realism, warm_narrative, pastoral_watercolor                    |

**Rules baked into the director prompt** (the part that shapes video quality):

- Voiceover runs at about 150 words per minute, so word count controls video length.
- Hook scene: 8-15 words. Final scene is a required call to action, 8-15 words, not a story conclusion.
- One idea per scene.
- `visual_prompt` means different things per type: describe _what_ to show for AI images, a 3-5 word query for stock, a short headline for text cards, and no styling words (the renderer owns styling).
- `ai_video` is used for 1-3 scenes where motion is the story, costs roughly $0.30 per scene against $0.04 for an image, and its `script_line` stays under 18 words because clips max out at 8 seconds.
- No em dashes in narration or prompts.

**The critic's checks.** It counts total words, scene count and per-scene length against the tier, flags scenes with more than one idea, and flags any scene holding over 30% of the words. If any check fails, the pacing score must be 5 or lower and revision is required. The prompt says revision is needed below 7.

**Style bible injection.** The image prompter appends the archetype's `artStyle`, `visualColorPalette`, `lighting`, `compositionRules`, `culturalMarkers`, `mood` and `antiArtifactGuidance` to its system prompt. This keeps every scene visually consistent without the director repeating style words. The music prompter is told to describe sound only and never topic words.

**How prompts are organized.** Seven markdown files in `prompts/`: `creative-director`, `critic`, `researcher`, `image-prompter`, `video-prompter`, `music-prompter` and `playbook`. Each agent reads its file at call time and falls back to a short inline default if the file is missing. The director also receives the entire playbook appended to its system prompt, and the critic receives only the "Pacing Rules" and "Critic Rubric" sections. One gotcha: paths are built from `process.cwd()`, so the process must start from the repo root or the defaults silently take over.

## Provider layer

Every external capability sits behind a small interface in `schema/providers.ts`, has one class per vendor, and is wired by `createProviders(config)` in `providers/factory.ts`. The pipeline only ever sees the interfaces, so swapping a vendor is a config change.

| Capability | Interface                                                                                                  | Implementations                                                    | Notes                                                                                   |
| ---------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| LLM        | `generate({ systemPrompt, userMessage, schema, enableWebSearch })` returns `{ data, usage }`               | anthropic (default), openai, gemini, openrouter, openai-compatible | All extend `BaseLLM`, built on the Vercel AI SDK.                                       |
| TTS        | `generate(text)` returns `{ audio, words }`                                                                | elevenlabs (default), inworld, kokoro, gemini-tts, openai-tts      | First two return word timestamps natively. The other three are wrapped with an aligner. |
| Image      | `generate(prompt, style?)` returns a Buffer                                                                | gemini (default), openai                                           |                                                                                         |
| Stock      | `searchVideo`, `searchImage`, `download`                                                                   | pexels, pixabay                                                    | Held as an array, primary first.                                                        |
| Video      | `supportedDurations` and `generate({ sourceImage, prompt, durationSeconds, aspectRatio, negativePrompt })` | gemini (Veo), fal (Kling)                                          | Image-to-video. Held as an array, primary then secondary.                               |
| Music      | `generate(prompt, mood)` returns `{ filePath, ... }`                                                       | bundled, lyria                                                     |                                                                                         |

**`BaseLLM` has two generation paths.** The direct path makes one call with the schema. The web-search path is two passes: the first lets the model call search tools freely (capped at 5 steps), the second restructures the text into the schema. The second pass retries up to twice without repeating the first, so a schema failure does not burn search credits. If the model rejects tool calling (detected by matching phrases in the error message), it falls back to a single call with a note in the prompt that no web search is available.

**Search tool resolution** happens in the factory. An explicit choice wins: `tavily`, `none`, or `native`. With no choice, Anthropic, OpenAI and Gemini use their built-in search, and every other LLM uses Tavily if a key exists, otherwise it warns and runs on the model's own knowledge. Injected tools override a subclass's native ones, which is how the factory adds search to models that lack it.

**The factory's other jobs.**

- **Per-job keys.** A `keys` map lets each job bring its own API keys instead of using environment variables. For stock and video providers the factory falls back to environment variables itself. For LLM, TTS and image it passes the key or `undefined` to the vendor class, and I did not read how those classes fall back.
- **Ordered fallbacks.** It builds a stock array and a video array from whichever keys exist, primary first. The video primary defaults to Gemini if a Google key exists, else fal.
- **A shared aligner.** One `WhisperAligner` instance is shared across TTS providers so the model loads once.
- **A separate vision model.** `createVerificationModel` returns the model used to judge stock footage (defaults: gpt-4o, gemini-2.5-flash, or claude-sonnet-4-6 depending on the LLM provider).

**TTS alignment decorator.** `AlignedTTSProvider` wraps any TTS provider. If the inner provider returned words, they pass through. If not, it runs Whisper alignment over the audio and the known script. If the audio is WAV, it transcodes to MP3 with ffmpeg, because the pipeline's voiceover contract is `voiceover.mp3`.

**How `WhisperAligner` works.** It lazy-loads `whisper-small.en_timestamped` through Hugging Face Transformers (about 460 MB on first run), resamples audio to 16 kHz, and transcribes with word timestamps in 30-second chunks. It then maps the _known script_ onto the recognized words: greedy matching within a 5-word lookahead, a substring fallback, and interpolation for misses (60 ms per character, 100 ms minimum). If Whisper returns zero words it throws, because broken captions are judged worse than no video.

**Caveat for our build.** The aligner model is English-only (`.en`). OpenReels began as a Bangla pipeline, but this version's alignment path will not handle other languages without a different model.

**Smallest useful set for a first version:** one LLM, one TTS that returns word timestamps (or any TTS plus the aligner), and one image provider. Stock, video and music can be added behind the same pattern later.

## Orchestration

The whole run is `runPipeline(opts, callbacks)` in `pipeline/orchestrator.ts` (1,040 lines, the largest file in the repo). It creates a timestamped run directory, builds six Mastra steps chained with `.then()`, runs them, and writes `log.json` in a `finally` block.

**State is shared through closures, not the workflow engine.** Providers and callbacks are not serializable, so Mastra's own state cannot carry them. Instead four mutable objects (`directorResult`, `ttsResult`, `visualsResult`, `assemblyResult`) are declared at the top of the builder and every step closes over them. After the director step, step inputs and outputs are just `{ done: boolean }`. The practical meaning for our build: this is a sequence of `await`s with shared variables, and a workflow library adds no capability here.

| Stage    | What it does                                                                                                                               | Failure behavior                                                                                                      |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| research | One web-search LLM call returns ResearchResult.                                                                                            | Falls back to topic-only research (summary "Topic: X", no facts, mood "informative") and marks the stage skipped.     |
| director | Generates the DirectorScore, runs the critic-revise loop, writes `score.json`, then runs the dry-run exit and the cost gate.               | Generation throws after 3 failed attempts and fails the run. A critic or revision failure keeps the best plan so far. |
| tts      | Sends the entire script as one call (all `script_line`s joined by spaces), saves `voiceover.mp3`, splits word timestamps back into scenes. | No catch. A failure fails the run.                                                                                    |
| visuals  | Resolves every scene's asset in parallel, and resolves music in parallel with them.                                                        | A failed scene becomes a `null` asset and a progress event. The run continues.                                        |
| assembly | Maps the score to Remotion props, bundles, selects the composition and renders `final.mp4`.                                                | No catch. A failure fails the run.                                                                                    |
| critic   | Evaluates the score once more and reports strengths and weaknesses.                                                                        | Failure marks the stage skipped.                                                                                      |

**The critic-revise loop** lives inside the director stage, before any money is spent on assets:

1. Generate a plan, then evaluate it with the critic.
2. Remember the highest-scoring plan seen so far.
3. Stop if the score is 7 or higher or the critic says no revision is needed. Otherwise revise and go again.
4. At most 2 rounds. If the last revision was never scored, evaluate it once more so it can compete.
5. Use the best-scoring plan, not necessarily the latest one. The code notes that LLM refinement can get worse in later rounds.
6. Any exception in the loop stops it and proceeds with the best plan so far.

The counts of evaluations and revisions completed feed the cost estimate.

**Early exits and cancellation.** The director sets `dryRunExit` or `costRejected` on the shared state. Every later step starts with `isCancelled() || dryRunExit || costRejected` and returns immediately if true. Cancellation is therefore checked only between stages, never inside one.

**Dry run** happens after the revision loop, so it prints the revised score. It marks tts, visuals, assembly and critic as skipped.

**Replay** takes a saved `score.json`. It skips research, plan generation, revision and the final critic. It still runs the cost gate, with the research, director and critic LLM costs left out.

**Callbacks are the only output channel.** `PipelineCallbacks` has stage start, complete, skip and error hooks, a free-form `onProgress(stage, data)`, `onCostEstimate` (returns a boolean to proceed), `onActualCost`, `onLog`, `onRunDir` (called before stage 1 so a caller can persist the path), and `isCancelled`. The CLI maps these to terminal progress and a y/n prompt, and auto-confirms when not in a terminal or when `--yes` is set. The worker maps them to queue progress events.

**Run directory.** `output/<YYYY-MM-DD>-<HHMMSS>-<topic slug, 50 characters max>/`, created and announced before any stage runs.

## Visuals stage

The visuals step resolves one asset per scene by switching on `visual_type`, and every scene runs concurrently inside a single `Promise.all`. Each scene is wrapped in its own try/catch, so one failure yields a `null` asset and a progress event instead of stopping the run. Target scene duration comes from the voiceover timing: last word end minus first word start, plus 0.5 seconds (3 seconds if no timing exists).

| Visual type                  | Strategy                                                                                                                                               | File written                  | Fallback                                                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `ai_image`                   | Prompt optimizer rewrites the scene description with the archetype style bible, then the image provider generates.                                     | `scene-N-ai.png`              | On a safety rejection, retry once with a softened prompt. If prompt optimization fails, use the original prompt. |
| `stock_image`, `stock_video` | Adaptive resolver: search, download, vision-verify, reformulate, retry.                                                                                | `scene-N-stock.jpg` or `.mp4` | AI image, with rejected results passed in as negative examples.                                                  |
| `ai_video`                   | Two phases: generate an AI image as the first frame, then animate it with a video provider.                                                            | `scene-N-ai-video.mp4`        | The phase-1 image. With no video providers configured, the scene silently becomes an `ai_image`.                 |
| `text_card`                  | No asset. The renderer `shows the scene's narration line (script_line, not visual_prompt) as large text on a card in the archetype's` colors and font. | none                          | none                                                                                                             |

**Safety-rejection retry.** A rejection is detected by looking for phrases such as "safety", "content policy" or "content moderation" in the error text. The optimizer is then re-run with an instruction to remove violence, gore, weapons and similar content while keeping style and mood, and generation is attempted once more. If the rewrite call itself fails, the original error is thrown.

**Adaptive stock resolution** (`providers/stock/adaptive-resolver.ts`):

1. Start with the director's original 3-5 word query. For each stock provider in order, search. The whole scene has a budget of 4 search calls (`stockMaxAttempts`).
2. Take the top 3 candidates for images but only the top 1 for video, since video downloads are expensive. Skip any candidate id already seen. Download lazily, one at a time.
3. If verification is off, accept the first download and record it as unverified.
4. Otherwise a vision model judges the image against the requested description and narration. For video it first extracts one frame with ffmpeg (at 1 second, or 0 if that fails). The judge prompt is deliberately strict (a toy rocket is not a rocket launch) and returns `relevant`, a 0-1 `confidence` and a `reason`. A result counts only if confidence is at least 0.6 (`stockConfidence`).
5. Among verified candidates, keep the highest confidence.
6. After the original query fails on every provider, an LLM rewrites it into 2-3 alternatives: strip proper nouns, 3-5 concrete visual nouns, most specific first. This happens once per scene.
7. If nothing verifies, generate an AI image instead. Up to three rejection reasons are fed into the image prompt as things to avoid.
8. If the verifier itself errors, the candidate is accepted and marked unverified (confidence -1) rather than blocking the scene.

Every attempt is recorded (query, provider, candidate id, verified, rejected or not found, confidence, reason) and written to `log.json` with the final method: `stock_verified`, `stock_unverified` or `ai_fallback`.

**AI video resolution** (`providers/video/video-resolver.ts`):

- An LLM writes a motion and camera prompt in the image prompter's `video` mode. If that fails, the scene's `visual_prompt` is used.
- A negative prompt is built from fixed defaults (blur, flicker, warping, deformed hands, morphing faces and similar) plus the archetype's `antiArtifactGuidance`.
- Providers are tried in order. Clip length is the smallest duration the provider supports that is at least the scene length. If the scene is longer than every supported length, the longest is used and the clip is trimmed, never looped. Aspect ratio is 9:16.
- A module-level limiter allows 3 concurrent video-generation calls across all scenes. Nothing else in this stage has a concurrency cap.
- If every provider fails, the phase-1 image is used and the resolution is logged as `image_fallback`.

**Fallback detection by filename.** The render mapper identifies an AI-image fallback by checking whether the asset path ends in `-ai.png`. It then rewrites the scene to `ai_image`, and turns a `static` motion into `zoom_in` so the still is not frozen. This works but is fragile. Our build should return the actual asset type and metadata with each resolved scene.

**What a failed scene looks like.** A `null` asset reaches the renderer as no source. In the AI image and video beat components I read, that renders nothing, so the scene shows the black background with captions still running. I did not read the stock image beat.

## Voiceover, word timestamps and captions

The whole narration is generated in one TTS call, and every timing in the video is derived from that call's word timestamps. The director's `script_line`s are joined with spaces into one string, sent to the TTS provider, and saved as a single `voiceover.mp3`. There is no per-scene audio and no stitching.

**Where timestamps come from.**

- **ElevenLabs** (default) uses the `/with-timestamps` endpoint, which returns character-level start and end times. The provider groups characters into words at each whitespace. Model `eleven_multilingual_v2`, stability 0.5, similarity boost 0.75.
- **Inworld** returns word timestamps natively.
- **Kokoro, Gemini TTS and OpenAI TTS** return none, so the Whisper aligner described in the provider layer produces them.

The result is always a list of `{ word, start, end }` in seconds on the voiceover's own timeline.

**Splitting words back into scenes** (`splitWordsIntoScenes`). The script text gives an expected word count per scene. TTS often returns a different total, because numbers and abbreviations expand into several spoken words. When the totals differ, each scene's share is scaled proportionally (at least one word each), and any leftover words go to the last scene. These per-scene groups are used only to compute scene durations. Captions never use them.

**Scene duration.** The time from a scene's first word start to its last word end, plus 0.5 seconds. The orchestrator uses 3 seconds when a scene has no words. The render mapper additionally enforces a 2-second minimum.

**Captions are one layer for the whole video.** A single `CaptionWrapper` sits at the top of the composition, outside the per-scene sequences, and reads absolute timestamps from the full word list. It owns all the timing logic, and each caption style is a thin renderer that receives ready-made word states.

- **Chunking.** Words are shown in fixed-size sequential chunks. Default size is 5 words, and an archetype can override it (cinematic documentary uses 4). A chunk stays on screen while its words are spoken and for a linger time afterward (default 0.3 seconds, 0.5 for cinematic documentary). The linger is cut short if the next chunk's first word has started. After the last word plus linger, captions disappear.
- **Word states.** Each word is `unspoken`, `active` or `spoken`, decided by comparing the current time with its start and end.
- **Animation.** Each word gets a spring value (0 to 1) calculated from the frame number and the word's start frame. This is pure frame math with no stored state, so seeking anywhere in the timeline gives the right result. Each chunk also fades in over 6 frames.
- **Placement.** Bottom of the frame with 18% padding. The text card's accent bar is placed at 35% from the bottom so it clears this caption zone.
- **Seven styles**, each with its own spring physics: `bold_outline`, `color_highlight`, `clean`, `karaoke_sweep`, `gradient_rise`, `block_impact`, `box_highlight`. The archetype picks the style, the accent color, the chunk size and the linger.

**Gotcha worth copying.** The karaoke style guards against words whose start equals their end, because Remotion's `interpolate` throws on a non-increasing input range. Any aligner we write should guarantee a positive duration for every word.

**Portable pieces.** `getWordChunk`, `getWordState` and `computeWordStates` in `caption-utils.ts` are pure functions with no Remotion dependency. They can be ported to any renderer unchanged.

## Music

Each video gets one background track, resolved in parallel with the scene visuals, and the code mixes it at a fixed low volume with no ducking. `resolveMusic` in `pipeline/music-resolver.ts` returns a file path or `null`, and a `null` simply means a video without music.

| Provider            | How it picks music                                                          | Notes                                                                                                                                                                                                                                                                               |
| ------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bundled` (default) | Random track from the director's `music_mood`.                              | 25 royalty-free MP3s in `assets/music/`, described by `music-manifest.json` (id, mood, filename, duration, source, license). If a mood has no tracks, any track is chosen and flagged as a fallback. The manifest is validated at worker start and only warns if files are missing. |
| `lyria`             | An LLM writes a detailed prompt, then Google Lyria 3 Pro generates a track. | About $0.08 per track plus one LLM call.                                                                                                                                                                                                                                            |

**Lyria path.**

1. Total length is the sum of the scene durations plus 5 seconds of padding, capped at 180 seconds.
2. The music prompter receives the mood, the emotional arc, the archetype's mood, and each scene's time window and narration. It writes a prompt with genre, instruments, tempo and timestamped sections that follow the scene timing. It is told to describe sound only, and never topic words, characters or events.
3. Lyria generates the audio.
4. On any failure the resolver falls back to a bundled track marked `fallback: true`, and keeps the rejected prompt and the error in the log for debugging. If the bundled fallback also fails, the result is `null`.

**Mixing.** The renderer plays the voiceover as a normal audio track and the music through `MusicTrack`, which sets a constant volume of 0.15 and loops it. Nothing lowers the music while someone is speaking. Three places in the repo's docs describe audio ducking, but the code does not do it (see the last section).

**Housekeeping.** After copying a generated track into the render folder, the orchestrator deletes the temp file so server runs do not fill `/tmp`.

## Assembly and rendering

Rendering is a pure function of the `DirectorScore` plus a bundle of resolved files. `mapScoreToProps` turns them into one props object, and a single Remotion composition draws it. Everything creative has been decided before this point.

**Steps inside the assembly stage**

1. Read the platform config. YouTube, TikTok and Instagram are all 1080 x 1920 at 30 fps. The config also holds a maximum and a recommended duration and a codec field, but none of these are enforced: the maximum is only returned by the `/platforms` API route, and the render hardcodes `h264`.
2. Create `<run>/_remotion_public/` with a symlink named `assets` pointing at the assets folder, plus copies of `voiceover.mp3` and `music.mp3`. Remotion reads files through `staticFile()`, so everything must live under one public folder.
3. Call `mapScoreToProps(score, resolvedAssets, fps)`.
4. Compute total frames with `getTotalDurationInFrames`.
5. Bundle the Remotion entry (`src/remotion/index.ts`), select the `OpenReelsVideo` composition with the props, and call `renderMedia` with the platform's width, height and fps, writing `final.mp4`.

**What `mapScoreToProps` produces.** Per scene: the resolved visual type, asset path (relative, `assets/<file>`), motion, narration, duration in frames, the archetype's color palette, text-card font and motion intensity, the source clip duration for video, and a resolved transition. Globally: caption style, accent color, chunk size, linger time, voiceover and music paths, and the full absolute word list.

Two cascades live here:

- **Transition:** the scene's own value, else the archetype's `defaultTransition`, else a hard cut. Duration is the archetype's frame count, default 15.
- **AI-fallback correction:** a stock or video scene whose asset ends in `-ai.png` is re-labelled `ai_image`, and `static` motion becomes `zoom_in`.

**Total duration.** Scene frames are summed, then each non-`none` transition between scenes subtracts its overlap. Because the voiceover is the spine, the result is never shorter than the voiceover end, and the last scene is stretched to cover any deficit. For an `ai_video` last scene the stretch is capped at the clip's own length to avoid a visible loop seam. The function mutates the last scene, so it must be called once per render.

**The composition** stacks four layers on a black background:

| Layer     | Component          | Behavior                                                                                                                           |
| --------- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| Scenes    | `TransitionSeries` | One sequence per scene, dispatched to a beat by visual type. The transition between scene N-1 and N is scene N-1's own transition. |
| Captions  | `CaptionWrapper`   | One layer on absolute timestamps (see the voiceover section).                                                                      |
| Voiceover | `Audio`            | One continuous track from frame 0.                                                                                                 |
| Music     | `MusicTrack`       | Volume 0.15, looped.                                                                                                               |

**Beat components**

| Visual type               | Beat                            | Behavior                                                                                                                                                                  |
| ------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ai_image`, `stock_image` | `AIImageBeat`, `StockImageBeat` | Two files with identical code. Ken Burns motion: zoom changes scale by 15% times the archetype's motion intensity, pans hold 1.15x scale and shift 50 px times intensity. |
| `stock_video`             | `StockVideoBeat`                | Muted `OffthreadVideo`. Loops if the clip is shorter than the scene.                                                                                                      |
| `ai_video`                | `StockVideoBeat`                | Same component, but never loops.                                                                                                                                          |
| `text_card`               | `TextCardBeat`                  | Narration text at 72 px over a gradient built from the archetype palette, spring scale-in, and an accent bar above the caption zone.                                      |

**Transitions** come from `@remotion/transitions`: `crossfade` is `fade()`, `slide_left` is `slide` from the right, `slide_right` is `slide` from the left, `wipe` is `wipe` from the left, and `flip` is `flip()`.

**Fonts** are loaded with `@remotion/google-fonts`: Montserrat, Inter, Playfair Display and Oswald for captions, and Inter, Merriweather and Space Grotesk for text cards.

**Runtime requirements.** Remotion drives headless Chrome, and the code also shells out to ffmpeg and ffprobe. The Docker commands in the README give the container 2 GB of shared memory for this reason.

**Design note for our build (my analysis, not measured).** Scene boundaries are built by adding up per-scene durations, while captions and audio use absolute word times. Each scene gets 0.5 seconds of padding, which is close to the 0.5 to 0.6 seconds that a 15 to 18 frame transition overlap removes, and the last scene is stretched to catch up. That likely keeps drift small, but nothing in the code guarantees it. Computing each scene's start frame directly from its first word's timestamp would remove the question.

## Cost estimation and usage

Cost is estimated from the final plan before any paid asset call, and measured afterward from real token usage. The estimate is arithmetic over the scene list, so it needs nothing but the `DirectorScore` and the provider choices (`cli/cost-estimator.ts`).

**What the estimate counts**

| Line   | How it is computed                                                                                                                                                         |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LLM    | One research call, one director call and one critic call, plus one image-prompter call per `ai_image` scene and two per `ai_video` scene (image prompt and motion prompt). |
| Gate   | Critic evaluations and director revisions actually completed in the revision loop.                                                                                         |
| TTS    | Total characters in all `script_line`s times a per-character price.                                                                                                        |
| Images | `ai_image` scenes plus `ai_video` scenes (each video starts from an image) times a per-image price.                                                                        |
| Video  | `ai_video` scenes times a fixed 6 seconds times a per-second price.                                                                                                        |
| Music  | Lyria track price plus one prompter call. Bundled music is free.                                                                                                           |
| Stock  | Free. The printout adds a worst case: if every stock scene falls back to AI, add stock scenes times the image price.                                                       |

LLM calls are priced from fixed token assumptions per call type: research 2,000 in / 1,000 out, director 5,000 / 2,000, critic 3,000 / 500, image prompter 800 / 200.

**Hardcoded prices** (comments date them to March 2026): LLM per million tokens is $3 in / $15 out for Anthropic, $2 / $8 for OpenAI and $0.10 / $0.40 for Gemini. TTS per character is $0.00018 for ElevenLabs, $0.00001 for Inworld, $0.00002 for Gemini TTS, $0.00005 for OpenAI TTS and free for Kokoro. Images are $0.101 (Gemini) or $0.167 (OpenAI). Video is $0.05 per second for Veo Lite or $0.07 for Kling. A Lyria track is $0.08. OpenRouter and OpenAI-compatible LLMs have no price entry and are counted as zero, so their estimates undercount.

**Actual cost.** Every LLM call's token usage is appended to one list during the run, including prompters, the stock verifier and the music prompter. After rendering, the totals are priced at the main LLM's rate. Non-LLM quantities are derived from outputs: AI images are counted by files ending in `-ai.png` plus AI video files, TTS characters from the script, and a flag for whether Lyria generated music. Video is again priced at a flat 6 seconds per clip rather than the real length. The estimated and actual totals are both saved in `log.json`.

**The confirmation gate exists only in the CLI.** The CLI prints the breakdown and asks to proceed, and skips the question with `--yes` or when there is no terminal. The worker's `onCostEstimate` stores the estimate and returns `true` immediately, so jobs started from the web UI or REST API are never held for approval. The README describes the gate without that qualification.

## Server, worker and live progress

The web mode wraps the same `runPipeline` function with three processes: a Fastify API (`src/server.ts`), a BullMQ worker (`src/worker.ts`) and a React SPA. The pipeline itself knows nothing about HTTP or Redis; it only talks through `PipelineCallbacks`.

**Division of labour**

- **API server**: validates the request, enqueues one BullMQ job (queue name `openreels`), writes a placeholder `meta.json`, streams events, serves artifacts.
- **Worker**: concurrency 1 (one render at a time). Builds providers from the job's own `keys`, builds callbacks, calls `runPipeline`, writes `meta.json`.
- **Redis**: queue plus progress events only. It is not the source of truth.
- **`meta.json` per job directory**: the source of truth for status, stages, score, review, cost. It survives Redis restarts and is written atomically (tmp file then rename).

**Routes (all under `/api/v1`)**

| Route                                                              | Behaviour                                                                                                                    |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| `GET /health`, `/stats`, `/archetypes`, `/platforms`, `/providers` | Status and config discovery for the UI.                                                                                      |
| `POST /jobs`                                                       | Validates, enqueues, writes placeholder meta (every stage `pending`), returns 201 `{id, topic, archetype, status:"queued"}`. |
| `GET /jobs`, `GET /jobs/:id`                                       | Read from `meta.json`, so a queued job never 404s.                                                                           |
| `GET /jobs/:id/events`                                             | Server-Sent Events stream (below).                                                                                           |
| `GET /jobs/:id/*`                                                  | Artifact serving with path-traversal protection.                                                                             |
| `POST /jobs/:id/cancel`                                            | Sets `cancelRequested` in meta, tries `moveToFailed`. 409 if already completed or failed.                                    |
| `DELETE /jobs/:id`                                                 | 409 if active or waiting; otherwise removes the job and the directory.                                                       |

**Request validation on `POST /jobs`**

- `topic` required, at most 500 characters.
- `archetype`, `pacing` and `platform` must exist in their registries.
- `direction` must be a string of at most 10 KB.
- A supplied `score` (replay) must pass `DirectorScore.safeParse` and reference a known archetype.
- Defaults: llm `anthropic`, tts `elevenlabs`, image `gemini`, stock `pexels`, music `bundled`, platform `youtube`.
- Per-job `keys` map is passed through to the worker (BYOK).

**Worker responsibilities**

- Initialises `meta` with all six stages `pending`, then maps each callback to a meta write plus a `job.updateProgress(...)` event.
- Stage callbacks: `onStageStart` → running, `onStageComplete` → done with detail and duration, `onStageSkip`, `onStageError`.
- `onProgress` carries rich payloads that are also persisted for reconnection: `results` (research), `score`, `music`, `music_resolved`, `revision` (round and critique score), `review` (final critic).
- `onCostEstimate` stores the estimate and returns `true` (the worker auto-approves; the y/n gate is CLI only).
- `isCancelled` re-reads `meta.json` and checks `cancelRequested`, so cancellation works across processes without extra IPC.
- On finish the status becomes `cancelled` if the flag was set, otherwise `completed`; on error `failed` (or `cancelled` if the flag is set).
- Optional pruning: with `MAX_JOBS` set, the oldest finished jobs are deleted after each run.

**SSE protocol**

1. Client opens `/jobs/:id/events`.
2. If BullMQ no longer knows the job (Redis wiped), the server falls back to `meta.json`; for a terminal job it sends `job:snapshot` plus `job:completed` or `job:failed` and closes, otherwise 404.
3. Otherwise it sends `job:snapshot` (the current `meta.json`) first, so a reconnecting client is instantly up to date.
4. A job already finished in BullMQ gets its terminal event and closes.
5. Live: BullMQ `QueueEvents` `progress` events are forwarded as `stage:<name>` events; `completed` and `failed` become `job:completed` and `job:failed`. A guarded cleanup removes listeners on client disconnect or job end.

**Cancellation, honestly described**

Cancel is cooperative. The flag is checked only between stages (and inside the director revision loop), so a long visuals or render stage runs to completion first. The `moveToFailed` call only works on queued jobs; for an active job the token does not match the worker's lock and the error is swallowed.

**What to copy into your pipeline**

- Keep the pipeline a pure function with a callbacks interface; put transport on top.
- Persist a snapshot per job on disk and send it first on every SSE connection; this makes reconnects trivial.
- Cooperative cancel via a flag file/field is enough if you accept stage-level granularity.
- You can skip BullMQ/Redis at first: a single in-process queue with concurrency 1 gives the same behaviour.

## Configuration: archetypes, pacing, platforms, playbook, critic rubric

Almost all creative behaviour is data, not code. This is the part you can reuse most directly.

**Archetype config (`src/schema/archetype.ts`, one JSON file each in `src/config/archetypes/`)**

- `scenePacing`: `fast` | `moderate` | `cinematic`.
- `captionStyle`: one of 7 (`bold_outline`, `color_highlight`, `clean`, `karaoke_sweep`, `gradient_rise`, `block_impact`, `box_highlight`); optional `captionChunkSize` (default 5) and `captionLingerS` (default 0.3).
- `colorPalette` `{background, accent, text}`, `textCardFont`, `motionIntensity` (number multiplier).
- `defaultTransition` and `transitionDurationFrames`, applied when a scene's `transition` is null (cascade: scene value → archetype default → `none`).
- Image-prompter fields: `artStyle`, `lighting`, `compositionRules`, `culturalMarkers`, `mood`, `antiArtifactGuidance`, `visualColorPalette[]`.

**The 14 archetypes**

| Archetype             | Pacing    | Caption style   | Chunk / linger | Transition (frames) | Motion | Font          |
| --------------------- | --------- | --------------- | -------------- | ------------------- | ------ | ------------- |
| infographic           | fast      | box_highlight   | 6 / 0.15       | slide_left (10)     | 0.8    | Space Grotesk |
| bold-illustration     | fast      | color_highlight | 6 / 0.15       | slide_left (12)     | 1.0    | Space Grotesk |
| comic-book            | fast      | color_highlight | 6 / 0.15       | slide_left (12)     | 1.3    | Inter         |
| warm-editorial        | moderate  | clean           | default        | crossfade (20)      | 0.9    | Merriweather  |
| editorial-caricature  | moderate  | bold_outline    | default        | slide_left (12)     | 1.5    | Inter         |
| anime-illustration    | moderate  | bold_outline    | default        | flip (12)           | 1.4    | Inter         |
| vintage-snapshot      | moderate  | clean           | default        | flip (12)           | 0.7    | Merriweather  |
| surreal-dreamscape    | moderate  | karaoke_sweep   | default        | wipe (15)           | 1.2    | Merriweather  |
| gothic-fantasy        | moderate  | block_impact    | default        | wipe (15)           | 1.1    | Merriweather  |
| cinematic-documentary | cinematic | clean           | 4 / 0.5        | crossfade (18)      | 0.9    | Inter         |
| moody-cinematic       | cinematic | block_impact    | 4 / 0.5        | crossfade (18)      | 1.1    | Space Grotesk |
| studio-realism        | cinematic | clean           | 4 / 0.5        | slide_left (10)     | 1.0    | Inter         |
| warm-narrative        | cinematic | karaoke_sweep   | 4 / 0.5        | crossfade (20)      | 1.2    | Merriweather  |
| pastoral-watercolor   | cinematic | gradient_rise   | 4 / 0.5        | crossfade (20)      | 0.9    | Merriweather  |

Pattern: fast archetypes get bigger caption chunks and short linger; cinematic ones get small chunks, long linger and slow crossfades.

**Pacing tiers (`PACING_CONFIG` in `src/agents/creative-director.ts`)**

| Tier      | Scenes | Words per scene | Total words |
| --------- | ------ | --------------- | ----------- |
| fast      | 8–12   | 8–12            | 90–120      |
| moderate  | 7–10   | 10–16           | 100–140     |
| cinematic | 5–8    | 15–22           | 90–130      |

Precedence for the director prompt: explicit `--pacing` override, then the archetype's tier, then (no archetype given) a lookup table injected so the LLM chooses the archetype and tier itself. Note the schema allows 3–16 scenes, while the tiers are enforced only by prompt and critic, not by Zod.

**Platforms (`src/config/platforms.ts`)**

| Platform  | Size      | FPS | Max length | Recommended | Codec |
| --------- | --------- | --- | ---------- | ----------- | ----- |
| youtube   | 1080x1920 | 30  | 60 s       | 40–55 s     | h264  |
| tiktok    | 1080x1920 | 30  | 180 s      | 40–60 s     | h264  |
| instagram | 1080x1920 | 30  | 90 s       | 40–55 s     | h264  |

**Playbook (`prompts/playbook.md`)**

One markdown file split on `## ` headers. `loadPlaybookSections([...names])` returns only the sections an agent needs, so each prompt stays small and the editorial knowledge is editable without touching code. Sections: Hook Patterns, Narrative Arcs, Pacing Rules, Visual Storytelling Rules, CTA Patterns, Music Mood Tags, Audience Psychology Triggers, Critic Rubric. A missing section throws with the list of available ones.

**Prompt files (`prompts/`)**: `creative-director.md`, `critic.md`, `researcher.md`, `image-prompter.md`, `video-prompter.md`, `music-prompter.md`, `playbook.md`. Each agent = prompt file + Zod schema + a thin function.

**Critic rubric (7 dimensions, each scored 1–10)**

| Dimension             | Weight |
| --------------------- | ------ |
| Hook Strength         | 20%    |
| Narrative Arc         | 20%    |
| Pacing                | 15%    |
| Visual Variety        | 15%    |
| Visual-Narration Sync | 10%    |
| Style Adherence       | 10%    |
| CTA Effectiveness     | 10%    |

Overall = `round(Hook*0.20 + Arc*0.20 + Pacing*0.15 + Variety*0.15 + Sync*0.10 + Style*0.10 + CTA*0.10)`. Each dimension has four bands (1–3, 4–6, 7–8, 9–10) with concrete criteria in the playbook.

**Mechanical pacing checks in the critic prompt**: total words against tier budget (150 WPM estimate), scene count in range, per-scene length, hook of at most 15 words, one idea per scene, no scene above 30% of total words. If any check fails, Pacing must be 5 or lower and revision is forced with a named fix.

**Critic output**: `score`, strengths, weaknesses, `revision_needed`, `revision_instructions`, `weakest_scene_index` (nullable).

## Testing, build order and doc-vs-code discrepancies

**Testing approach**

- Vitest, 48 colocated `*.test.ts` files under `src/`, `environment: node`, `globals: true`, v8 coverage. Run with `vitest run`; also `biome check .` and `tsc --noEmit`.
- Everything external is mocked, so the suite needs no API keys and no Redis.
- Highest-value tests to copy: Zod schema tests (golden rule, scene bounds), archetype registry and playbook section parsing, pacing instruction builder, `splitWordsIntoScenes`, caption chunking and timing maths, `mapScoreToProps`, cost estimator, and the revision loop with a fake LLM.

**Recommended build order for your own pipeline**

Each step produces something you can run and judge before the next one.

1. **Contracts first**: `DirectorScore`-style schema, provider interfaces (`LLM`, `TTS`, `Image`, `Stock`, `Video`, `Music`), result types with usage. Nothing else is stable without these.
2. **LLM provider with structured output** and a retry that feeds the validation error back into the prompt.
3. **Director agent plus playbook and one archetype**, with `--dry-run` that stops after the score and saves it as JSON. Add score replay at the same time; it makes every later stage cheap to develop.
4. **TTS with word timestamps** (native, or a forced aligner), then the scene-splitting and duration maths.
5. **Visuals stage**: one asset type first (AI image), per-scene parallelism, null-asset fallback; add stock, verification and video later.
6. **Renderer**: score-to-props mapper, one beat component, then captions, transitions and music.
7. **Critic and plan-level revision loop** (before spending on assets).
8. **Cost estimate and gate, callbacks, `meta.json` snapshots.**
9. **Only then** a queue, SSE and a UI.

**Where OpenReels' docs and code disagree (trust the code)**

- The README implies the pipeline re-runs on a low critic score. In code the revision loop is plan-level, before any spend (max 2 rounds, pass at 7, best plan kept); the final critic after rendering is informational.
- The architecture page says TTS synthesises each scene's `script_line` separately. The code makes one TTS call for the whole script and splits words proportionally across scenes.
- The architecture page says `MusicTrack` has ducking. The code mixes music at a fixed 0.15 volume with no ducking.
- The architecture page says 6 caption styles. The schema defines 7 (`box_highlight` is the extra one).
- The architecture page says the critic is a VLM watching the rendered video. The critic agent evaluates the plan (`DirectorScore` plus topic) with text-only prompts; the VLM is used for stock-image verification.
- Docs describe the pipeline as agents orchestrated by Mastra. Mastra only chains six steps; the "agents" are plain functions with one structured LLM call each, and state moves through closure variables rather than step outputs.
- Tier word and scene budgets are enforced by prompt and critic only; the Zod schema accepts any 3–16 scenes.
- Cancellation is only checked between stages, so "cancel" can take as long as the current stage.

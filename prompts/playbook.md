# Playbook

## Hook Patterns

The first scene must earn the next three seconds. Open with one of:
- A direct question the viewer is already asking themselves.
- A surprising fact or number that contradicts intuition.
- A bold claim that the rest of the video will prove or unpack.

Keep the hook line to 8-15 words. Never open with "Did you know" or a slow setup.

## Narrative Arcs

Pick one arc and hold it for the whole script:
- **Curiosity-to-wisdom**: open with a question, close with the answer reframed as insight.
- **Problem-to-solution**: state a relatable problem, escalate it briefly, resolve it.
- **Myth-to-reality**: state the common belief, flip it, land on the corrected view.

Name the arc as `emotional_arc`, e.g. "curiosity-to-wisdom".

## Pacing Rules

Voiceover runs at roughly 150 words per minute, so total word count controls video length.
- Hook scene: 8-15 words.
- Final scene: a call to action, 8-15 words, not a story conclusion.
- One idea per scene. Cut a scene rather than cram two ideas into it.
- No single scene should carry more than 30% of the total script word count.
- Stay within the pacing tier's scene count and words-per-scene budget.

## Visual Storytelling Rules

- `visual_prompt` means different things per scene type: a scene description for AI
  visuals, a 3-5 word search query for stock, a short headline phrase for text cards.
- Never include styling words in `visual_prompt` - the renderer/archetype owns style.
- No more than two consecutive scenes may share the same `visual_type` (the golden rule).
- Use `ai_video` sparingly (1-3 scenes) and only where motion tells the story.
- No em dashes anywhere in narration or prompts.

## CTA Patterns

The last scene is always a direct call to action, never a story wrap-up:
- "Follow for more like this."
- "Comment [X] if you knew that."
- "Save this before you forget it."

## Music Mood Tags

Pick one `music_mood` that matches the emotional arc, not the topic:
epic_cinematic, tense_electronic, chill_lofi, uplifting_pop, mysterious_ambient,
warm_acoustic, dark_cinematic, dreamy_ethereal.

## Audience Psychology Triggers

Short-form viewers decide to keep watching within 1-2 seconds. Favor specificity
over generality, concrete numbers over vague claims, and a clear stake ("why this
matters to you") over abstract framing.

## Critic Rubric

Score the plan 1-10 on each dimension, then compute the weighted overall score.

| Dimension             | Weight |
| ---------------------- | ------ |
| Hook Strength          | 20%    |
| Narrative Arc          | 20%    |
| Pacing                 | 15%    |
| Visual Variety         | 15%    |
| Visual-Narration Sync  | 10%    |
| Style Adherence        | 10%    |
| CTA Effectiveness      | 10%    |

Mechanical checks (apply before scoring):
- Total word count against the pacing tier budget (at ~150 words/minute).
- Scene count within the tier's range.
- Per-scene word count within the tier's per-scene range.
- Hook scene at most 15 words.
- No scene holding more than 30% of total words.

If any mechanical check fails, the Pacing dimension must score 5 or lower and
`revision_needed` must be true with a concrete fix in `revision_instructions`.
Otherwise, revision is needed when the overall score is below 7.

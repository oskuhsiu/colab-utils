# Reference/audio artifacts: PR2 verification and cost boundary

This change is stacked on PR1 head `460a3e766a87291582ee9214aa71f536316f7428` (`fix/reduce-harness-coupling`), not on `main`. It adds only opt-in named references and shared recorded-audio timing. No GPU/model, paid API, TTS/ASR engine, account, or external media upload was used in verification.

## Why these two additions

Existing asset IDs already had ready-state, path, hash and character-lineage checks. The new resolver closes the narrower gap between a script's typed character/scene/prop/voice names and those **actual existing inputs**. It does not rebuild asset storage. Missing variants/views, ambiguous names and prompt references to unprovided pictures fail before paid execution. It never picks a fallback image or expands the reference-image count.

The audio artifact preserves the bytes and measured duration of an **already available PCM WAV**, alongside explicitly supplied transcript/speaker/voice identities and timing provenance. The same imported timing reaches the existing dialogue planner, local edit clock and SRT export. It does not create speech or infer alignment. The recording's declared voice identity is not acoustic proof; native H3 voice description is prompt intent only. Studio's separate audio is post-generation mux, not lip-sync conditioning.

Rejected scope: provider accounts, new TTS/ASR/forced-alignment models, mixing engine, DB, vector search, GUI, GPU arbitration, animatics, scheduler or extra approval gates. Existing no-dialogue, native H3/Pika and direct asset-ID paths remain usable without new manifests.

## Measured local overhead

Raw results: [JSON](reference-audio-artifacts-20261101.json). Python 3.12.14 on Linux x86-64, warm filesystem cache, one 15-second 48 kHz stereo 16-bit PCM WAV (2,880,044 bytes), three small synthetic image references, one synthetic utterance span. No real speech or generated video-quality comparison.

| Operation | Repetitions | Median | p95 |
| --- | ---: | ---: | ---: |
| Resolve selected references/voice only | 1,000 | 0.078 ms | 0.188 ms |
| Import and validate complete WAV | 100 | 6.339 ms | 8.219 ms |
| Load/revalidate artifact against current WAV | 100 | 6.240 ms | 7.364 ms |
| Compile job with resolver + artifact | 100 | 10.610 ms | 12.652 ms |
| Compile same assets through legacy IDs, no artifact | 100 | 3.792 ms | 5.029 ms |

Observed incremental median was about **6.8 ms per compile**, not per complete production. The manifest was **1,563 bytes**; the source WAV is referenced, not duplicated by import. Existing attempt packaging still copies selected input assets as before. `prepare`/`reserve`/submission may compile and validate more than once; existing FFmpeg decode checks and CLI process startup are not included in these micro-measurements. Cold disks, larger recordings and other machines can differ.

Revalidation intentionally rereads complete PCM data and checks file hashes around measurement; job compilation also performs its existing asset hash. A persistent mtime-only cache was not added: measured overhead was small, and accepting replaced audio would defeat the artifact's purpose.

### Costs saved versus incurred

- **Demonstrated:** wrong/missing/ambiguous references reject locally; changed recording/transcript/speaker/voice binding rejects stale reuse; subtitle-only alignment/unused aliases/views preserve generation identity. One imported artifact produced exact source and trimmed/retimed SRT through real FFmpeg integration, without another ASR/TTS call.
- **Expected, not measured:** fewer manual reference-binding mistakes, fewer repeated timing/ASR passes, and fewer expensive retakes caused by stale references or incorrect speech budgets. No production mistake rate, CU saving, dollar saving or video-quality gain is claimed.
- **Incurred:** a small catalog for reused entities, one explicit recording/transcript snapshot, local validation/I/O and maintenance of two small modules. A single-image or native-audio-only task can skip these fields. Manual boundaries are useful only when trustworthy; otherwise alignment stays unavailable.
- **Quality boundary:** generated motion/identity, actual voice consistency, emotion, natural pacing and lip sync still need the original visual/listening QA. More metadata is not better video evidence. The resolver does not increase model steps, reference count, video length or review-agent count by itself. Full imported audio is never shortened to fit a clip; when the chosen model's constraints require a longer clip, that real cost remains explicit.

## Reproducible checks

```bash
python3 scripts/install_repo_skills.py
python3 scripts/install_repo_skills.py --check
python3 -m unittest discover -s tests -v
# Runnable short end-to-end example, entirely offline:
python3 -m unittest discover -s tests -p 'test_shared_dialogue_integration.py' -v
```

The end-to-end fixture runs public `audio-import`, `prepare`, `reserve`/pack, `edit-prepare`, raw/edited `audio-srt`, and the existing `caption.py --mode mux`. Synthetic PNG/PCM media and FFmpeg stand in for a generated clip; a marked synthetic receipt tests the existing immutable-source boundary. It verifies real decode, staged WAV hash, trim/speed mapping, output stream types and extracted subtitle timestamps. It does **not** assert that a tone says its test transcript or that a model rendered anything.

An integration check caught caption.py's intentional one-second minimum cue extension. The documented handoff uses its existing `--min-duration 0` flag for precise supplied timing; the caption engine itself was not changed. Tests also retain final-release QA gates and refuse output overwrites, malformed/truncated WAV, stale dependencies, absent alignment and partial-utterance cuts. Existing PR1 generation digests are verified under their original version before canonical input comparison.

The first independent reviews led to these corrections before publication:

- Reject unsupported acting/voice controls in the recorded-audio timing branch instead of silently ignoring them; native H3 prompting remains unchanged. Put visual acting in the actual shot prompt and change recorded performance through a new recording.
- Reproject subtitle-only alignment corrections through a frozen edit recipe without rewriting/re-encoding the video, while still validating the frozen job, source, media and recipe hashes.
- Permit explicitly timed same-character overlapping voice layers; no extra permission flag or invented second character is needed.
- Preserve legacy omitted `inputs`, reject caller-injected compiler-owned timelines, and compare the validated artifact's WAV hash/path with the finally selected input snapshot. The regressions exercise the source-change race and public CLI bypass attempt.

Independent prerelease reviews and final check counts are recorded in the PR description after review; this document does not self-approve the implementation.

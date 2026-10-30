# Video workflow evidence report

Checked 2026-09-30. This is source gathering only: claims below are attributed to
the repository authors or marked as measured by them; I did not run generation.
Line ranges refer to the raw source reads; links point to recoverable source files
without GitHub page fragments, whose rendered navigation line numbers differ.

## Vault index and current repository URLs

- `Links/2026-04-18-github-waoowaoo-ai-film-studio.md` -> [waooAI/waoowaoo](https://github.com/waooAI/waoowaoo) (the note's older URL is `saturndec/waoowaoo`; the current README says preview release and Elastic License 2.0 from v0.5.0-beta.1, [README lines 10-25, 94-95](https://github.com/waooAI/waoowaoo/blob/main/README_en.md)).
- `Links/2026-08-11-github-video-autopilot-kit.md` -> [Hao0321/video-autopilot-kit](https://github.com/Hao0321/video-autopilot-kit), v0.23.0, MIT ([README lines 0-7, 198-200](https://github.com/Hao0321/video-autopilot-kit/blob/main/README.md)).
- `Links/2026-04-27-github-firered-openstoryline.md` -> [FireRedTeam/FireRed-OpenStoryline](https://github.com/FireRedTeam/FireRed-OpenStoryline), Apache-2.0, Python >=3.11 ([README lines 21-26](https://github.com/FireRedTeam/FireRed-OpenStoryline/blob/main/README.md)).
- `Links/2026-06-25-github-openmontage-agentic-video.md` -> [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage), AGPLv3 ([README lines 9-28](https://github.com/calesthio/OpenMontage/blob/main/README.md)).
- `Links/2026-05-13-github-pixelle-video-engine.md` -> [AIDC-AI/Pixelle-Video](https://github.com/AIDC-AI/Pixelle-Video), Apache-2.0 ([README_EN lines 390-392](https://github.com/AIDC-AI/Pixelle-Video/blob/main/README_EN.md)).
- `Links/2026-08-26-github-minimax-h3-integration-index.md` and `Links/2026-09-01-github-minimax-h3-cloud.md` -> official [MiniMax-AI/MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3), plus community [soren-labs/minimax-h3-colab](https://github.com/soren-labs/minimax-h3-colab). The model license is a separate MiniMax H3 Community License dated 2026-08-02, excluding the EU, UK, Korea and US ([license lines 0-10](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE)).
- `Links/2026-08-11-github-wan-animate-2.md` -> current official [Wan-Video/Wan2.2](https://github.com/Wan-Video/Wan2.2), whose README contains the Wan-Animate-14B section; the note's `Wan-Animate-2` URL is retained as the historical note target. Apache-2.0 ([README lines 244-277, 418-420](https://github.com/Wan-Video/Wan2.2/blob/main/README.md)).
- `Links/2026-09-04-github-wangp-low-vram-generative-suite.md` -> [deepbeepmeep/Wan2GP](https://github.com/deepbeepmeep/Wan2GP), community suite; current README reports v13.141 ([README lines 7-26, 52-70](https://github.com/deepbeepmeep/Wan2GP/blob/main/README.md)).
- `Links/2026-08-26-github-h3lite-local-video-generation.md` -> [Rimagination/h3lite](https://github.com/Rimagination/h3lite), MIT skill ([README lines 0-18, 298-300](https://github.com/Rimagination/h3lite/blob/main/README.md)).

## Reusable production and review contracts

**OpenMontage** documents an end-to-end contract. Its agent guide treats a
reference video as a first-class entry point: run `video_analyzer`, transcript
extraction, scene detection and frame sampling, then produce a grounded summary
of content, pacing, structure and style ([AGENT_GUIDE.md lines 13-40](https://github.com/calesthio/OpenMontage/blob/main/AGENT_GUIDE.md)).
The production loop is manifest -> stage-director skill -> tools -> self-review
-> checkpoint -> human gate ([lines 41-67](https://github.com/calesthio/OpenMontage/blob/main/AGENT_GUIDE.md));
canonical artifacts include `scene_plan`, `asset_manifest`, `edit_decisions` and
`render_report` ([ARCHITECTURE.md lines 197-214, 244-255](https://github.com/calesthio/OpenMontage/blob/main/docs/ARCHITECTURE.md)).
Concrete tool contracts are `BaseTool`, `ToolResult`, `input_schema`/`output_schema`,
`fallback_tools`, `resource_profile`, `retry_policy`, `seed` and `model`
([ARCHITECTURE.md lines 94-125](https://github.com/calesthio/OpenMontage/blob/main/docs/ARCHITECTURE.md)).
The repo's quality claims are design claims; its README says post-render checks
use ffprobe, frame sampling, audio analysis and delivery-promise checks, but this
report has no independent quality measurement ([README lines 355-391](https://github.com/calesthio/OpenMontage/blob/main/README.md)).

**FireRed-OpenStoryline** supplies a conversational editing/refinement pattern,
not a local video-generation model. It supports partial redo at any stage and
saving an editing workflow as a Skill ([guide lines 30-65](https://github.com/FireRedTeam/FireRed-OpenStoryline/blob/main/docs/source/en/guide.md));
the repository layout exposes `src/open_storyline/mcp`, `nodes`, `skills`,
`storage`, `agent.py` and `config.py` ([README lines 260-287](https://github.com/FireRedTeam/FireRed-OpenStoryline/blob/main/README.md)).
The authors warn that AI transitions call third-party generators and are costly
and unpredictable ([README lines 47-54](https://github.com/FireRedTeam/FireRed-OpenStoryline/blob/main/README.md));
its TODO still lists image/video generation and GPU rendering ([lines 296-302](https://github.com/FireRedTeam/FireRed-OpenStoryline/blob/main/README.md)).

**video-autopilot-kit** and **Pixelle-Video** document complementary mechanical
gates. Autopilot's `Editkin v4` contract is evidence -> plan -> audit -> atomic
apply -> render, with Python/FFmpeg as analysis/QA support ([README lines 17-21](https://github.com/Hao0321/video-autopilot-kit/blob/main/README.md));
its `workflow_contract.py`, `workflow_state.py`, receipts, `edit-plan/v4`,
`media_delivery_qa.py` and `delivery_media_ops.py` are concrete seams
([lines 84-99](https://github.com/Hao0321/video-autopilot-kit/blob/main/README.md)).
The author explicitly requires receipts reconciliation and human review after
technical QA ([lines 187-190](https://github.com/Hao0321/video-autopilot-kit/blob/main/README.md)).
Pixelle's pipeline is `Script Generation -> Image Planning -> Frame-by-Frame
Processing -> Video Composition` ([README_EN lines 53-59](https://github.com/AIDC-AI/Pixelle-Video/blob/main/README_EN.md));
its API-video path claims retry and neighboring-segment continuity hints, but
that is an author feature claim, not a measured continuity score ([lines 329-334](https://github.com/AIDC-AI/Pixelle-Video/blob/main/README_EN.md)).

Waoowaoo is a preview workspace for references, model-aware aspect ratio,
duration, resolution and reference roles, with versioned refinement ([README lines 18-25](https://github.com/waooAI/waoowaoo/blob/main/README_en.md)).
The README documents a persistent project/canvas UX, but the preview notice
and lack of published faithfulness measurements mean its identity/shot claims are
unverified.

## Model controls, identity and hardware evidence

**MiniMax H3.** The official README documents 4–15 s, 24 FPS, 768p base output,
2K regeneration, stereo audio, FL2VA with 0/1/2 keyframes, and Ref2VA with up to
9 images + 3 videos + 3 audio clips/12 files ([README lines 55-76](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/README.md)).
It recommends a structured Context-IR preprocessing stage, but Context-IR and the
Regenerate-2K module are hosted/not open-sourced ([lines 73-84, 126-138](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/README.md)).
The model README states complete weights support further development including
fine-tuning, but has no official trainer link ([lines 119-147](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/README.md)).
The official example shows explicit shot timing, camera movement, action and
sound fields ([lines 261-285](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/README.md)).

Community sources report additional constraints, and must remain attributed. The Colab G4
harness reports one RTX PRO 6000 Blackwell (~96 GiB), ~75 GiB free disk, and
single-run measurements: 1344x768/5.17 s Native 355.8 s, Spectrum 226.1 s,
TE-Speed 104.2 s at 864x480/8 s; it calls these directional single-machine
feasibility measurements ([README lines 0-14, 27-52, 54-76](https://github.com/soren-labs/minimax-h3-colab/blob/main/README.md)).
The independent H3 trainer demonstrates a character LoRA and IC-LoRA pose control
on synthetic/held-out tests; it reports 36 clips/rank 16/1200 steps and joint
distance 0.0177 adapter vs 0.0272 base, but explicitly says voice identity and
real-footage generalization were not measured ([README lines 89-139, 174-215](https://github.com/AviadDahan/MiniMax-H3-Trainer/blob/main/README.md)).
This is identity/structural LoRA evidence, not diffusion-speed LoRA evidence.
The community H3 index separately labels Turbo/PDD adapters as acceleration paths
and warns about motion/audio trade-offs ([README lines 37-55](https://github.com/MiniMax-AI/awesome-minimax-h3-integration/blob/main/README.md)).

**Wan2.2 / Wan-Animate.** Official docs list TI2V-5B 720p/24 FPS on >=24 GB
(e.g. 4090), while A14B T2V/I2V single-GPU examples require >=80 GB with
offload/dtype options ([README lines 184-204](https://github.com/Wan-Video/Wan2.2/blob/main/README.md)).
Wan-Animate takes a character image plus driving video for animation or replacement,
with pose/face/background/mask inputs in the Diffusers contract ([lines 244-277, 293-360](https://github.com/Wan-Video/Wan2.2/blob/main/README.md)).
Replacement has a built-in relighting LoRA, but the authors explicitly warn
against generic LoRAs trained on Wan2.2 for Wan-Animate ([line 362](https://github.com/Wan-Video/Wan2.2/blob/main/README.md)).
The official README cites DiffSynth-Studio as a community path with LoRA/full
training support ([lines 34-44](https://github.com/Wan-Video/Wan2.2/blob/main/README.md));
this does not establish identity-adapter compatibility with Animate.

**LTX-2/2.5.** Official pipelines expose text/image-to-video, video extension,
retake, ICLoRA, keyframe interpolation and Dub-It speaker/lip-motion workflows
([README lines 117-129](https://github.com/Lightricks/LTX-2/blob/main/README.md)).
The repo provides distilled and detailing IC-LoRAs, and its trainer explicitly
supports LoRA, full fine-tuning and video/audio reference conditioning
([README lines 60-80, 103-106, 159-163](https://github.com/Lightricks/LTX-2/blob/main/README.md));
standard training is recommended on >=80 GB, with a 32 GB low-VRAM config
([trainer README lines 29-40](https://github.com/Lightricks/LTX-2/blob/main/packages/ltx-trainer/README.md)).
The quick start needs roughly 66 GiB of model files and allows FP8/CPU/disk
offload; camera/action/appearance prompting is explicit ([README lines 25-55, 138-147](https://github.com/Lightricks/LTX-2/blob/main/README.md)).
No source read here establishes a person-identity guarantee.

WanGP reports a unified low-VRAM UI for Wan, H3 and LTX with LoRA/finetune,
queues, headless CLI, pose/depth/flow preparation and API ([README lines 7-35](https://github.com/deepbeepmeep/Wan2GP/blob/main/README.md));
these are integration claims, and the repository metadata says `NOASSERTION` for
license in the vault note, so check the actual license before redistribution.
H3 Lite documents a bounded skill workflow: it records anchor cards in `anchors.json`, runs
`anchor_qa` across first/middle/last frames, and reports 640x352/4-step hardware
measurements (4060 Ti 16 GB ~77 s; 4070 Laptop 8 GB ~591 s) while requiring human
identity/clothing/composition review ([README lines 27-41, 62-71](https://github.com/Rimagination/h3lite/blob/main/README.md)).

## Dense, time-indexed video analysis for QA

Anthropic's official Vision docs say Claude accepts image blocks and multiple
images, but “animations are unsupported, and only the first frame is used”
([Vision lines 81-98, 190-192, 234-256](https://platform.claude.com/docs/en/build-with-claude/vision#supported-formats)).
For this API, a workflow seeking video coverage would have to decode video locally
into timestamped stills plus audio/transcript evidence; native video understanding
is not documented by this source.

Two source implementations expose concrete analysis contracts. [dsh-video-lens](https://github.com/dundunhan/dsh-video-lens/blob/main/README.md) defines `video_probe`,
scene-change-aware `video_analyze` (`ffmpeg scdet` + optional timestamped ASR +
vision JSON), and time-anchored `video_ask`; its evidence JSON contains shot
timestamps, sampled frames, transcript segments and a visual timeline ([README
lines 4-22, 77-104](https://github.com/dundunhan/dsh-video-lens/blob/main/README.md)).
It is MIT, v0.3.2, and warns that its local-file readability check is only a UX
guard, not a security boundary ([README lines 106-124](https://github.com/dundunhan/dsh-video-lens/blob/main/README.md)). [timecode-agent](https://github.com/mupozg823/timecode-agent/blob/main/README.md)
(MIT, v0.4.0) goes further: transcript/deterministic signals first, lazy visual
verification, append-only `checkpoints.jsonl`, provenance, and evidence-gated
EDL/FCPXML/OTIO ([README lines 19-36, 79-101](https://github.com/mupozg823/timecode-agent/blob/main/README.md)).
Its `boundary-eval` checks speech cuts, breaths and loudness joins; it blocks VFR
or irregular timing before revision-bound export and reports verified versus
uncertain person-presence intervals ([lines 270-275, 318-352](https://github.com/mupozg823/timecode-agent/blob/main/README.md)).
The authors explicitly call the fixed-sampling comparison architectural rather
than a performance claim ([lines 92-101](https://github.com/mupozg823/timecode-agent/blob/main/README.md)).

## Verified VACE benchmark assets

The original VACE repository's UserGuide documents `src_video` as a condition
video (including Pose or Layout), `src_ref_images` as reference images, and
`animate_anything` / `swap_anything` as image+video composition tasks ([UserGuide
§3.1 and §3.3](https://github.com/ali-vilab/VACE/blob/main/UserGuide.md)). The
official examples table names the pose and layout paths ([UserGuide examples
table](https://github.com/ali-vilab/VACE/blob/main/UserGuide.md)), while the
pipeline script invokes `pose` with `pose/ori_video.mp4` and `layout_track` with
`layout/ori_video.mp4` ([run_vace_pipeline.sh](https://github.com/ali-vilab/VACE/blob/main/run_vace_pipeline.sh)).

I verified the following three files from the public [ali-vilab/VACE-Benchmark](https://huggingface.co/datasets/ali-vilab/VACE-Benchmark)
dataset at commit `c70300e817d21c9fdb6bccddecadf8d57e02a0f3` (dataset page shows
Apache-2.0):

- [Pose original human video](https://huggingface.co/datasets/ali-vilab/VACE-Benchmark/resolve/c70300e817d21c9fdb6bccddecadf8d57e02a0f3/assets/examples/pose/ori_video.mp4): H.264, 1280x720, 30 fps, 161 frames, 5.366667 s, 7,007,490 bytes; SHA-256 `005e850eb0fc27ccade3967e143df7155754868199290549b9e9eb4ec298a558`. A sampled frame shows a multi-person dinner scene; this is the source video passed to the official `--task pose` pipeline.
- [Pose condition video](https://huggingface.co/datasets/ali-vilab/VACE-Benchmark/resolve/c70300e817d21c9fdb6bccddecadf8d57e02a0f3/assets/examples/pose/src_video.mp4): H.264, 1280x720, 30 fps, 161 frames, 5.366667 s, 3,431,100 bytes; SHA-256 `5c6c8fe70de71f0a6768cb46cce3c22d1e9934926a07e6e3993bc4416b71bf6d`. A sampled frame visibly contains colored human skeleton keypoints on black, confirming it is a pose-control representation rather than a guessed filename.
- [Reference character image](https://huggingface.co/datasets/ali-vilab/VACE-Benchmark/resolve/c70300e817d21c9fdb6bccddecadf8d57e02a0f3/assets/examples/face/src_ref_image_1.png): PNG RGB, 670x598, 294,376 bytes; SHA-256 `d6bd58e69f1a39b7d587fb30e651d1b9121f66d72969e4ad498a2eeaa7287e94`. It is an elderly elf-like head reference used by the VACE face R2V example.

The measurements above came from direct downloads followed by `ffprobe` and
`file`/image inspection on 2026-09-30. The pose videos and face image are
separate official examples, so this verifies availability and media contracts;
it does not claim they are a pre-paired identity/pose sample.

## Evidence gaps

No source here provides a cross-model, independently measured faithfulness score
for framing/action/identity. H3's most capable preprocessing and 2K stages are
hosted; H3 LoRA identity results are community measurements on synthetic or
held-out data; Wan-Animate generic LoRA compatibility is explicitly discouraged;
LTX identity fidelity is not documented. Colab availability for H3 beyond the
specific G4 harness, and any Wan2.2/LTX Colab timings, remain unverified.

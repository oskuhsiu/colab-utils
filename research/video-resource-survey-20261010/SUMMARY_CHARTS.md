# Summary charts: requirements, quality, speed, best choice

Checked 2026-10-10. This condenses the [survey](README.md); no new GPU test was run.

Use separate L4 and A100 charts. Keep requirements, quality and speed together so each choice has its trade-offs beside it. Keep production frameworks separate because they can be combined with a generation backend.

**How to read:** “Best choice” means the primary agent's preferred starting point for the stated use case, not a measured overall winner. Quality descriptions come from supported capabilities and author/user observations; there is no common quality score. Unknown speed means no comparable measurement on the named GPU. Model-file size is not peak VRAM. High RAM means host RAM; A100 40GB and 80GB remain distinct.

## 1. Low resources — one L4, nominal 24GB VRAM

| Model / configuration | Requirements / fit | Quality and limitations | Speed on L4 | Best choice when… |
|---|---|---|---|---|
| **FastH3 v1, 4 steps** | Kijai INT8-ConvRot DiT + Qwen32B NVFP4-AWQ + matching video/audio VAEs; VSA. Existing run used **52.96GiB host RAM**, with about **42.36GB model files**; these are observed conditions, not minimums. | Generates audio/video together. Motion/detail/audio can be weaker than Base; T2VA student is not a trained Ref2VA replacement. | **156–182s for 5s**, 864×480. Two different prompts/seeds; install/download excluded; no controlled warm repeat. | **An evidenced L4 baseline for quick text-to-audio-video iteration.** |
| **H3 FL2VA Turbo, 8 steps** | Matching FL2VA quantized base + Turbo LoRA; staged loading/offload. Full-pipeline host RAM minimum unknown. | First/last-frame conditioning and native audio. Official guide notes an audio/motion trade-off relative to Base. | Comparable L4 preset **not measured**. | **H3 image-to-video or first/last-frame work where latency matters.** |
| **H3 Ref2VA Turbo, 4 steps** | Separate Ref2VA base + matching Ref2VA Turbo LoRA; reference encoding costs extra memory. | Trained reference task; identity/voice retention still needs checking. Audio/motion trade-off. | Comparable L4 preset **not measured**. | **Faster reference-conditioned previews.** |
| **H3 Base, 20–25 / 50 steps** | Quantized matching FL2VA or Ref2VA, Qwen encoder and both VAEs; CPU staging. Comfy defaults to 20; DiffSynth example uses 50. | Preferred H3 quality/conditioning baseline. Neither more steps nor Ref2VA guarantees exact identity or correct physics. | Matching end-to-end L4 timing **unknown**. | **Reference fidelity and motion/audio quality take priority over iteration speed.** |
| **FastH3 V2 / Trim, 8 steps** | Separate V2/Trim checkpoint and scheduler; quantized loading, compatible attention backend. | V2 versus v1 is not ranked on L4. Trim is smaller; its author reports less detail in busy scenes. | **No L4 benchmark found.** | **A next speed/detail experiment**, after the known v1 baseline. |
| **Wan2.2 TI2V-5B** | Official 720p path states ≥24GB with model offload, dtype conversion and T5 on CPU. | Text/image-to-video, 720p/24fps; video-only. No same-input quality ranking against A14B. | Author reports **0.15 generated frames/s** for a 49-frame, 1280×704 L4 workload; not playback FPS or a 5s total. | **The clearest documented L4 route for silent 720p T2V/I2V.** |
| **Wan2.2 A14B Lightning, 4 steps** | Matching high/low experts and LoRAs; FP8 or compatible GGUF + offload. L4 fit/time not directly qualified. | A candidate for visual detail/control; large-motion artifacts and reversed vehicle direction are reported. | **No direct L4 timing found.** | **Visual quality exploration with more loading/quantization work.** |
| **HunyuanVideo-1.5, I2V 8/12 steps** | Author states ≥14GB with offload; use the **480p I2V step-distilled** checkpoint. T2V and CFG-distilled variants have different contracts. | Lean video-only I2V alternative; 4-step sampling can lower quality. | **No direct L4 timing found.** | **An alternative image-animation test.** |
| **FramePack / F1 / P1** | Official GPU floor 6GB; progressive section generation and host offload. | Longer I2V clips; cache/quantization can change motion and detail. | Historical user report: **~80min for 20s**, 480-class output. Old, incompletely specified stack. | **Longer clips with low VRAM**, when render time is acceptable. |

LTX-2.3/2.5 remains a conditional L4 experiment: quantization/offload exists, but no complete target-GPU memory/timing qualification was found. Its official NVFP4 path requires Blackwell.

Sources: [local L4 runs](00-hardware-and-local-evidence.md), [H3 native guide](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/minimax/minimax-h3-native.mdx), [FastH3 variants](03-fasth3-variants.md), [Wan2.2 official](https://github.com/Wan-Video/Wan2.2), [Wan measurements](04-wan-core-low-mid.md), [HunyuanVideo-1.5 official](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5), [other-model evidence](05-other-video-models.md).

## 2. Mid resources — one A100 + High RAM

| Model / configuration | Requirements: 40GB versus 80GB | Quality and limitations | A100 speed evidence | Best choice when… |
|---|---|---|---|---|
| **H3 Base, 20–25 / 50 steps** | Both profiles need explicit DiT/encoder/VAE staging. Higher precision on 80GB is a candidate, not a qualified full-stack recipe. | Preferred H3 reference/motion/audio baseline. Use FL2VA for text/keyframes and Ref2VA for multimodal references. | One **A10080** author reports **110s**, INT8-ConvRot/Triton, 864×480, 124f, 20 steps; host RAM and cold/warm status unreported. | **Quality-focused H3 production and reference work.** |
| **H3 Turbo: FL2VA 8 / Ref2VA 4** | Matching base/adapter, dimensions and shifts; both 40/80GB still require measured peak memory. | More economical sampling with reported audio/motion trade-offs. | A10080 author has a **38.31s Turbo4+Sol** example, but clip length/frames are unspecified; it cannot be ranked against the 110s row. | **A speed/quality compromise**, checked against Base. |
| **FastH3 v1 / V2 / Trim** | Quantized formats plus the correct scheduler/backend. A100's SM80 is below FastVideo's native FP8 compute gate, so that path dequantizes to BF16. | Speed-oriented students; Trim can lose busy-scene detail. Reference-task limitations remain. | **No matched single-A100 benchmark found.** | **Speed experiments**, rather than a proven A100 winner. |
| **Wan2.2 A14B Base / Lightning** | Official stock 720p command states **≥80GB**. At 40GB, quantization/offload is a separate conditional path. Always pair high/low experts and adapters. | Preferred video-only visual-quality candidate; Base versus Lightning trades cost against motion/detail. Not a cross-model quality winner. | **No qualified single-A100 + High RAM timing** for the compared presets. The ~21.7s serving result uses four GPUs. | **Silent T2V/I2V visual work**, especially on A10080. |
| **Wan2.2 TI2V-5B** | 40GB is a plausible capacity candidate; actual host usage still unknown. The single-A10080 qualification used BF16 and **1TiB installed host RAM**. | A smaller 720p T2V/I2V alternative; video-only. | A10080: **288s T2V / 299s I2V**, 1280×704, 121f, 50 steps. **The 1TiB host makes this a reference outside the verified High RAM budget.** | **A simpler silent-video baseline** before A14B. |
| **LTX-2.5 distilled, 8+4 steps** | Matching Gemma4 encoder, video/audio VAEs and upscaler. 40GB needs quant/offload evaluation; 80GB peak/decode cost also unqualified. Official NVFP4 is Blackwell-only. | Native audio/video, IC-LoRA, keyframes and refinement; diffusion versus convolutional VAE trades resources against detail. | **No direct single-A100 timing found.** | **The next native-audio alternative to compare with H3.** |
| **HunyuanVideo-1.5 I2V, 8/12 steps** | 480p step-distilled checkpoint + offload; SR stages cost extra. The ≥14GB author floor is not a complete A100 benchmark. | Video-only image animation; keep its task-specific distilled contract. | **No direct A100 timing found.** | **Lean I2V generation without soundtrack requirements.** |
| **VACE / Animate / Fun Camera / SVI / TalkVerse** | Different checkpoints/LoRAs, control inputs and preprocessors; measure these separately from denoising. | Better suited to explicit motion/editing/camera/audio controls; no general identity or long-clip consistency guarantee. | **No complete target-profile comparison.** | **Specific controls are more important than generic prompt-only generation.** |

Sources: [H3/A100 reports](01-h3-original-steps.md), [A10080 optimization report](https://note.com/howrass_note/n/nb6adf1bce83e), [single-A10080 Wan qualification](https://github.com/wiseyak-core/wiseyak-vllm-omni/blob/main/recipes/Wan-AI/Wan2.2-TI2V-5B-A100.md), [LTX-2.5 official](https://github.com/Lightricks/LTX-2), [control/long-video contracts](06-wan-control-variants.md).

## 3. Best choice by requirement — short decision chart

These are recommendations from the primary agent's synthesis, with the qualifications above.

| Your requirement | L4 starting choice | A100 High RAM starting choice |
|---|---|---|
| Quick **text → video + audio** | **FastH3 v1 4-step**, the existing L4 baseline | **H3 FL2VA Turbo8**, compared with Base20/25; A100 speed still needs measurement |
| **Reference character / outfit / voice** matters | **H3 Ref2VA Base20**, matching quant/offload; Turbo4 for previews | **H3 Ref2VA Base20/25**, matching inputs and measured memory |
| **Silent 720p T2V/I2V** | **Wan2.2 TI2V-5B** offload path | **Wan2.2 A14B** on 80GB; quant/offload must be qualified on 40GB |
| Explore another **native audio/video** model | LTX only after a memory test | **LTX-2.5 distilled 8+4**, as a comparison candidate |
| **Pose / camera / editing / acting** control | A smaller matching VACE/Fun/Hunyuan path, then measure | Matching **VACE / Fun Camera / Animate** according to the actual input |
| **Audio-driven speaking / longer clips** | **TalkVerse-5B** is a smaller candidate; no L4 qualification | Compare **TalkVerse / MultiTalk / SVI**; external audio and drift checks required |
| **Whole edited film**, subtitles and soundtrack | **ComfyUI + OpenMontage** | **ComfyUI + OpenMontage**; GPU choice remains in the generator |

There is no universal quality winner in the current evidence. For a final decision, compare successful accepted clips per total GPU minute, including retries, decoding, preprocessing and postproduction.

## 4. Quantization — keep this as a separate small chart

| Format / weight family | Resource implication | Quality / speed evidence | Starting decision |
|---|---|---|---|
| H3 **pruned INT8-ConvRot / scaled FP8** | About 21GB DiT files; encoder and VAEs additional. Need matching kernels and offload. | Most directly documented Comfy stack; no complete L4/A100 same-seed quality matrix. | **Default comparison pair** for the matching H3 task. |
| H3 **W4A8** | Roughly 12GB DiT files, depending on author/variant. | Experimental or author-qualified; lower size does not prove faster or equal quality. | **Memory-saving candidate**, compare against INT8. |
| **GGUF Q4 / Q5 / Q6 / Q8** | Size varies with full/pruned, prior FP8 conversion and mixed precision; loader matters. | No cross-author target-GPU quality ranking. | Compare higher/lower quant on the **same source checkpoint**, not filename alone. |
| **NF4 + CPU/disk offload** | Very low claimed GPU floor; host RAM/I/O can dominate. | Some extremely small Colab outputs were reported unusable; no target-tier speed winner. | **Fallback feasibility route**, not a speed recommendation. |
| **NVFP4 DiT / sealed merged formats** | Kernel- and format-specific; Blackwell native versus emulation/fallback differs. | Fusion/pruning/distillation and quantization can all change output. | Choose only with an explicit matching loader and profile. L4/A100 should not inherit Blackwell timing. |

Sources: [quant authors and evidence](02-h3-quant-community.md), [backend gates](09-inference-frameworks.md).

## 5. Frameworks and finishing — separate from model rankings

| Requirement | Preferred starting tool | Why / limit |
|---|---|---|
| Exact model/control/quant workflow | **ComfyUI native or model-author sample** | Clear graph, inputs and weights; UI JSON must be exported before API submission. |
| Story, assets, editing, subtitles, QA | **OpenMontage + local ComfyUI** | Documented local Comfy API integration. Cloud/stock demos have different generation costs and quality. |
| Alternative low-memory runtime | **Wan2GP / DiffSynth** as comparison candidates | Profiles/offload and model coverage; no universal L4/A100 speed win. |
| Sparse/distilled speed experiments | **FastVideo / LightX2V** | Exact checkpoint/scheduler/backend matching; hardware gates matter. |
| Modest low-resource upscale | **Tiled Real-ESRGAN** as a conservative comparison | Copies audio in its official video path; framewise processing can flicker. |
| Temporal upscale on A100 | **FlashVSR**, compared with **SeedVR2** if detail restoration is needed | A100 author data exists for FlashVSR; check crop/frame count/audio. SeedVR2 can over-sharpen or alter details and lacks target-profile timings. |

Sources: [OpenMontage local interface](https://github.com/calesthio/OpenMontage/blob/main/docs/PROVIDERS.md), [workflow inventory](08-comfy-workflows.md), [framework survey](09-inference-frameworks.md), [postproduction contracts](10-postproduction-workflows.md).

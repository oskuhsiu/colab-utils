# Open-Source Scouting Report: Qwen Image 2.1 acceleration and webtoon upscaling

> Decision Verdict: **Option B — Extension / Sidecar**
> Estimated MVP Delivery: **1 day for a controlled accelerator comparison; the T4 2× notebook and measured baseline are implemented**
> Primary Recommendation: **Keep Qwen Image 2.1 Diffusers as the generation baseline; test LightX2V as an optional backend after storyboard angle diversity is repaired. Upscale approved drafts with Swin2SR x2 on a temporary T4.**

Repository and model information checked on 2026-09-24. The report distinguishes vendor benchmarks from this project's own run measurements.

## 1. Requirement Scope and Boundaries

- **Core Business Loop:** Codex adapts a novel into a vertical-scroll storyboard and panel prompts; one persistent Qwen Image 2.1 pipeline generates referenced draft panels; after review, a separate 2× upscaler outputs final-size panels and the HTML reader.
- **Target Delivery Type:** Local CLI plus two Colab notebooks, single creator, panel PNGs and a phone-width HTML reader.
- **Licensing Constraint:** Private non-commercial evaluation. Qwen Image 2.1 usage remains under its Research License. Open-source code, model code and weights have separate license terms.
- **Remote constraint:** Do not reload Qwen between chapter submissions. Upscaling gets its own temporary standard-memory T4, which exits after the job.
- **Visual constraint:** The latest 39-panel draft repeats frontal/half-body hamster views. The user identified this as an upstream novel-to-storyboard/prompt coverage problem. Acceleration and model reloads cannot create shot variety absent shot-specific prompts.

## 2. Shortlisted Candidates

| Repository | URL | Stars | Last pushed | Tech stack | License | Risk level | Rating |
| :--- | :--- | --: | :--- | :--- | :--- | :--- | --: |
| LightX2V | [ModelTC/LightX2V](https://github.com/ModelTC/LightX2V) | 2,854 | 2026-09-24 | PyTorch/CUDA image/video inference framework | Apache-2.0 | Warning | 4/5 |
| SGLang Diffusion | [sgl-project/sglang](https://github.com/sgl-project/sglang) | 36,392 | 2026-09-24 | Python/CUDA serving runtime | Apache-2.0 | Warning | 3.5/5 |
| vLLM-Omni | [vllm-project/vllm-omni](https://github.com/vllm-project/vllm-omni) | 7,047 | 2026-09-24 | Python/CUDA multimodal serving | Apache-2.0 | Warning | 2.5/5 |
| Real-ESRGAN | [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | 36,891 | 2024-08-06 | PyTorch/BasicSR, plus separate NCNN port | BSD-3-Clause | Warning | 3/5 |

GitHub repository counts and push dates were checked from GitHub's live pages/API on the report date. The selected Swin2SR is an official Hugging Face model card, not a GitHub application repository, so it is assessed below separately.

## 3. Five-Pillar Due Diligence

### LightX2V

- **Maintenance & Governance:** Active; over 1,500 commits and a push on the report date. Its repository announced Day-0 Qwen Image 2.1 support.
- **Community Health:** 2.9k stars, 274 forks, visible community contributions.
- **Setup Friction:** It has its own configs, runners, optional GPU kernels and model layout. It does not re-use the current `QwenImage21Pipeline` object; the model must be loaded in the alternate engine. Qwen 2.1 text-to-image and editing are listed, but I found no specific official 8-step Qwen 2.1 distillation checkpoint. The current official 8-step image checkpoints I found target Qwen Image 2512 / Edit 2511 instead.
- **Modularity & Reusability:** Clear pipeline boundary; our existing `webtoon_tasks.json` is a suitable adapter input. It supports image-conditioned editing, which the character/reference workflow needs.
- **Supply Chain & Licensing:** Apache-2.0 repository; separately verify the precise Qwen weights and any compiled-kernel terms. Hardware-specific optimized kernels require a supported GPU/software pair.
- **Summary:** Best first alternate backend to try on one panel. Vendor performance measurements in LightX2V's README are for other workloads and must not be quoted as a measured speedup for our 768px, three-reference Qwen panels.

### SGLang Diffusion

- **Maintenance & Governance:** Highly active with more than 36k stars and 9k forks; current repository activity is dated 2026-09-24.
- **Community Health:** Large open serving community, frequent releases and diffusion documentation.
- **Setup Friction:** The official Qwen 2.1 cookbook asks for `sglang[diffusion]` prerelease dependencies and a source checkout. Its installation and backend versions are more involved than the existing notebook. It documents hardware-specific placement choices.
- **Modularity & Reusability:** Independent API/server supports Qwen 2.1 text-to-image and multi-image editing, component offload, CUDA execution choices and VAE tiling. It can be wrapped behind the existing task package without changing the storyboard.
- **Supply Chain & Licensing:** Apache-2.0 repository; model weights retain their own terms.
- **Summary:** Strong sidecar candidate. Its official cookbook measured a 22.7 GiB peak on RTX 4090 at 1024×1024 and 40 steps; that is not the current A100/T4 hardware nor our 768px three-reference panel case.

### vLLM-Omni

- **Maintenance & Governance:** Active multi-modal serving project, around 7k stars and 1.8k forks; pushed 2026-09-24.
- **Community Health:** Broad vLLM community and integration work.
- **Setup Friction:** The Qwen 2.1 recipe currently says support is in an unmerged branch and not yet part of a tagged release; its tested run uses a GB300. Installing this stack in standard Colab for serial panel generation is not a small drop-in.
- **Modularity & Reusability:** API service supports image-conditioned inputs with prefix KV cache, CUDA graphs, FP8 and optional parallelism. Continuous batching is mainly useful at higher request throughput; our pilot submits one panel at a time.
- **Supply Chain & Licensing:** Apache-2.0 repo; Qwen weights remain independently licensed.
- **Summary:** Revisit after Qwen 2.1 is in a stable vLLM-Omni release or when several authors share an inference service. Not the current Colab MVP.

### Real-ESRGAN

- **Maintenance & Governance:** Not archived, but last push was 2024-08-06, outside the last-12-month activity target.
- **Community Health:** Very strong, about 36.9k stars and 4.5k forks.
- **Setup Friction:** The official `RealESRGAN_x4plus_anime_6B` model is specifically optimized for anime imagery, and supports tiled inference/arbitrary output scale. On the current Colab Python 3.13 image, the Python package install failed while generating BasicSR package metadata. Its separate NCNN Vulkan binary expects a working Vulkan ICD; the T4 test image exposed the Vulkan loader but no ICD manifest.
- **Modularity & Reusability:** Good CLI and Python entry points; tile processing gives control over GPU memory. Its x4 anime model can produce arbitrary output scale, but it still internally infers at x4 then resizes to x2.
- **Supply Chain & Licensing:** Code repo is BSD-3-Clause. Check the exact weight asset's license before redistributing model files.
- **Summary:** Strong anime-oriented comparison candidate, but not reliable enough for the default Colab T4 notebook without rebuilding its dependency environment or bringing a usable Vulkan driver.

### Screened alternative: `waifu2x-ncnn-vulkan`

[`nihui/waifu2x-ncnn-vulkan`](https://github.com/nihui/waifu2x-ncnn-vulkan) has about 3,476 stars, MIT license and a 2026-04-13 push. Its portable binary supports exact x2 and configurable smaller tiles for lower VRAM. It is anime-oriented, but also depends on Vulkan at runtime; the current Colab VM did not expose a Vulkan ICD. A local desktop with Vulkan is a better target than this Colab image.

## 4. Architectural Decision Verdict

- **Recommended Path:** Option B — Extension / Sidecar for generation acceleration; separate T4 notebook for upscaling.
- **Key Justification:** Keep the known-good Diffusers/Qwen generation route until an alternate backend wins a same-prompt, same-seed, same-reference test. The official Diffusers Qwen 2.1 pipeline already has exact cross-step prefix KV caching enabled by default for the text and reference-image condition. It is not the cause of repeated camera poses. A panel-level LightX2V or SGLang adapter can be tested without changing novel adaptation or the webtoon schema.
- **Current upscaler:** `caidas/swin2SR-classical-sr-x2-64`, Apache-2.0. Its official model card says it scales exactly 2× and carries a 48.5 MB safetensors checkpoint; the Transformers API exposes `Swin2SRForImageSuperResolution`. On a standard-memory Tesla T4, a 768×1152 sample reached 10.11 GiB allocated / 10.67 GiB reserved, producing the x2 result in 22.66 seconds. The model pads to attention-window boundaries; the worker crops the result to exactly 1536×2304.
- **Generation default hardware:** The user requested V100 without high-RAM. The installed Colab CLI supports T4/L4/G4/H100/A100, not V100; it silently maps unknown names to A100. The project CLI now rejects unsupported GPU names. It requests A100 with standard system RAM, which provides safe GPU headroom without the high-RAM machine shape. This exact A100 standard-memory Qwen configuration has not yet been rerun. L4 is not a safe drop-in at the current three-reference settings: the recorded 22.52 GiB allocated peak approaches or exceeds an L4's 24 GB physical limit once driver/headroom is included.

## 5. Model Alternatives for This Comic

| Model | Official facts | Fit for a scrolling hamster story | Verdict |
| :--- | :--- | :--- | :--- |
| [Qwen Image 2.1](https://github.com/QwenLM/Qwen-Image-2.1) | 7.1B DiT, unified T2I/I2I, multi-image editing and up to 10 references; exact prefix KV cache | Best proven path for applying fixed character/style/habitat references to every panel | Keep as the image baseline |
| [Qwen-Image-2512](https://huggingface.co/Qwen/Qwen-Image-2512) | Qwen reports better natural fur details and text; Apache-2.0, about 57.7 GB bundle | Older T2I model card and larger bundle; it does not replace the current 2.1 multi-image edit task by itself | Test only if fur/detail is the remaining concern |
| [Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) | 6B, 8 NFEs, Apache-2.0, official statement says it fits 16 GB GPU memory | Fast T2I, but official model zoo marks Turbo diversity low and lists image editing on a different checkpoint | Not a stronger series-continuity candidate yet |
| [FLUX.2 [dev]](https://huggingface.co/black-forest-labs/FLUX.2-dev) | 32B, multi-reference editing and reference-based identity/style without fine-tuning are stated features | Larger model and non-commercial model license; not suitable for an easier/lower-memory Colab pipeline | Hold as a future quality comparison |
| [HunyuanImage-3.0-Instruct-Distil](https://huggingface.co/tencent/HunyuanImage-3.0-Instruct-Distil) | 8-step image-conditioned editing and reasoning; vendor recommends 8×80 GB GPUs for the instruct-distill variant | Far beyond current A100/T4 deployment | Exclude from this Colab project |

There is no single “better” model across quality, speed, consistency and hardware. For this series, panel angle diversity must be fixed in the storyboard before a model comparison can be meaningful.

## 6. Minimalist MVP Plan (1-1-1-1 Rule)

- **Core User Story:** As a solo webtoon author, I can approve a novel-adapted vertical storyboard, generate referenced review-size panels, and upscale only the panels I accept.
- **Starter Architecture:** Keep the one-kernel Qwen Diffusers run for generation; introduce LightX2V behind an alternate adapter for a controlled single-panel comparison. Keep the independent T4 Swin2SR notebook for x2 post-production.
- **Minimal Schema Draft:**

  ```text
  Entity: WebtoonPanel
  - panel_id: stable chapter/panel key
  - source_spans: novel evidence and adaptation decision
  - camera: shot distance, angle, body orientation, action and gaze
  - generation: model/backend, refs, width/height, seed and steps
  - output: draft PNG, optional 2x PNG, manifest status
  ```

- **Milestones:**
  - Phase 1: Revise both storyboards to vary camera distance, azimuth, pitch, hamster orientation, gaze and silhouette in neighboring panels. Keep the narrative/source spans.
  - Phase 2: Generate a few revised panels with baseline Diffusers and LightX2V, holding panel content, three references, dimensions and seeds constant; compare time, VRAM and visual quality.
  - Phase 3: Keep the baseline unless an accelerator passes the matched comparison. After author approval, run the x2 T4 notebook; retain original draft files and seeds.
- **Scope Blacklist:**
  - [ ] No new model, LoRA training or automatic prompt-rewriter until panel composition is revised.
  - [ ] No default high-RAM or unsupported `--gpu V100` requests.
  - [ ] No model reload between Qwen chapters.
  - [ ] No upscaling before the story/panel is approved.
  - [ ] No commercial licensing assumption for restricted model weights.

## 7. Next Actions

- [ ] Revise camera and pose coverage across the two chapter storyboards; the author identified repeated front-facing compositions as a prompt/adaptation-stage defect.
- [ ] Run a small matched Diffusers vs. LightX2V comparison once revised prompts are approved.
- [x] Measure 2× Swin2SR VRAM on a max-size draft panel with a standard-memory T4; stop the temporary runtime.
- [x] Create a separate Swin2SR upscaler notebook and point the CLI `upscale` command to a temporary T4 session.
- [x] Stop the prior A100 high-RAM session. Set future Qwen defaults to a supported standard-memory A100; explicitly reject `V100` through this CLI.

### Primary source references

- [Qwen Image 2.1 repository: architecture, native prefix cache, multi-reference editing and supported backends](https://github.com/QwenLM/Qwen-Image-2.1)
- [LightX2V repository and Qwen Image 2.1 support](https://github.com/ModelTC/LightX2V)
- [SGLang-Diffusion Qwen Image 2.1 cookbook and hardware/VRAM measurements](https://docs.sglang.io/cookbook/diffusion/Qwen-Image/Qwen-Image-2.1)
- [vLLM-Omni Qwen Image 2.1 recipe and current branch/tag requirement](https://recipes.vllm.ai/Qwen/Qwen-Image-2.1)
- [CAIDAS Swin2SR x2 model card](https://huggingface.co/caidas/swin2SR-classical-sr-x2-64) · [Transformers Swin2SR API](https://huggingface.co/docs/transformers/model_doc/swin2sr)
- [Real-ESRGAN anime model notes](https://github.com/xinntao/Real-ESRGAN/blob/master/docs/anime_model.md) · [ncnn Vulkan alternative](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan)
- [waifu2x-ncnn-vulkan repository and x2/tile controls](https://github.com/nihui/waifu2x-ncnn-vulkan)
- [NVIDIA L4 specifications](https://www.nvidia.com/en-au/data-center/l4/) · [NVIDIA V100 configurations](https://www.nvidia.com/en-gb/data-center/tesla-v100/)

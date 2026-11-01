Pika H3 Flex：指定 `pika` 預選 H3 INT8 底模＋對應 Pika adapter，使用 repo 維護的 [Ref2VA API starter](workflows/comfyui_h3/pika-h3-ref2va-int8.api.json) 與[操作說明](skills/minimax-h3-colab/references/pika-h3-flex.md)。明確選用官方 BF16 CLI 時使用[獨立 Colab notebook](notebooks/Pika_H3_Flex_Colab.ipynb)或 [CLI](scripts/pika_h3.py)；`omni` 沿用下方 FastH3 Omni。預設不配置資源、不安裝、不下載權重、不生成；實際容量與內容依當次產物驗證。

FastH3 Omni 新增：[ComfyUI notebook](notebooks/ComfyUI_Colab.ipynb) 的 `h3-omni-int8` 選項（原生 Ref2VA、8步、INT8模型與含視覺塔的INT8 encoder），並可切換 `REF_IMAGE_SIZE=max/match`，表單預設 `max`。[使用方式](doc/COMFYUI_WORKSPACE.md)、[模型與 hybrid 研究](research/h3_omni_20261028.md)。此新增路徑完成離線檢查，未做 GPU 生成／人物相似度對照。

參考方案查核：[YZ 金魚 workflow 與 HyperFlow-Infinity](research/h3_workflow_hyperflow_20261028.md)。前者是 hybrid／12步／SelfLift 配方；後者已使用本地H3，包含固定身份圖、原始latent交接與場景記憶，目前沒有勝過Continuum的同條件比較，也尚未移植至單卡notebook。

ComfyUI 新入口：[獨立 Colab notebook](notebooks/ComfyUI_Colab.ipynb)、[操作說明](doc/COMFYUI_WORKSPACE.md)。整合 H3 Continuum 與實驗性原生 Ref2VA-VSA；預設不下載模型、不生成。新增 A100 40GB／Continuum 三組 one-shot 實測（歷史證據未隨此 source-only repo 發佈：`projects/ninja-continuum-a10040-20261019/RESULTS.md`）與同步比較頁（歷史證據未隨此 source-only repo 發佈：`projects/ninja-continuum-a10040-20261019/comparison.html`）：Ref Turbo4、Ref Turbo8、Ref Turbo4＋VSA，各36秒、6段、三張人物參照。Notebook UI 尚未實測。Veda 暫緩，保留[來源研究](research/comfy_h3_extensions_20261019.md)。

L4 後續：Continuum＋Ref Turbo4＋VSA 真人 one-shot（歷史證據未隨此 source-only repo 發佈：`projects/ninja-continuum-live-l4-20261019/RESULTS.md`）、兩支原片與檢查頁（歷史證據未隨此 source-only repo 發佈：`projects/ninja-continuum-live-l4-20261019/review.html`）。各20秒、4×5秒；同款INT8母模配動態分層卸載與INT8 video VAE，在L4完成，顯存觀測峰值15.39／15.77GiB。分路跳躍與枝條回彈仍有內容限制，依要求保留原生一次生成結果。

Spark-H3：[加速、VRAM 與相容性評估](research/spark_h3_20261019.md)。目前正式套件支援 ComfyUI 0.38–0.40／CUDA 13.0，未納入這份 0.42 工作台；缺少與 Veda 同條件的峰值 VRAM 比較。

FastH3 L4 新流程：[操作說明](doc/FAST_H3_L4.md)、[可匯入工作流](workflows/fast_h3_l4.json)、[獨立 Colab notebook](notebooks/FastH3_ComfyUI_L4.ipynb)。原 H3 notebook 已新增可選 FastH3 引擎，保留既有 H3 模式。

FastH3 T4：[研究與實測結果](doc/FAST_H3_T4.md)，包含相容性、影片、速度與 2 CU 內的用量證據。

AI 圖片／影片放大：[操作與研究](doc/AI_UPSCALER.md)、[圖片 2× 工作流](workflows/ai_upscale_image_2x.json)、[影片 2× 工作流](workflows/ai_upscale_video_2x.json)、[FastH3 + 2× 工作流](workflows/fast_h3_l4_upscale_2x.json)、[Colab notebook](notebooks/AI_Media_Upscaler_Colab.ipynb)。預設 Real-ESRGAN 原生 2×，另有 4×／anime 模型及逐幀低記憶體 CLI。

影片模型性價比：[A100 實測、CU 與畫面證據](doc/VIDEO_MODEL_CP_BENCHMARK.md)、[原始研究](doc/VIDEO_MODEL_TRIALS_RESEARCH_20261011.md)、可播放比較頁（歷史證據未隨此 source-only repo 發佈：`projects/video-model-cp-20261011/comparison.html`）。包含 H3 加速變種、Kandinsky 6 與生成後 2× 放大的成本比較。

研究總結：[三組效益推薦與畫質優先方案](doc/VIDEO_MODEL_RECOMMENDATIONS.md)：整合A100／INT8 Larry＋2×、A100／W6A8 Larry、L4／FastH3，以及原生768p畫質組與原始量測證據。

影片模型移植：[L4、T4 與 Kaggle 適用性評估](doc/VIDEO_MODEL_L4_T4_KAGGLE.md)。區分已有 FastH3 實測、H3／Kandinsky／LTX 待驗候選，以及 Kaggle T4×2 的 RAM、精度與後製限制。

C01 標準 T4：[Kandinsky 6 Lite 實測](doc/KANDINSKY6_LITE_T4.md)，已完成288p含音訊5秒影片，記錄分階段低RAM流程、品質問題及CU歸零後的存活結果。

Colab 影片製作的新入口：[`colab-video-studio`](skills/colab-video-studio/SKILL.md) 以人物基準、分鏡／控制素材、逐段 Colab 推論、時間證據驗收與合成取代臨時批次腳本。支援 H3、Wan2.2 5B、VACE 與 Wan-Animate adapter；[研究依據](research/video-workflow-sources.md)與實際短測／限制（歷史證據未隨此 source-only repo 發佈：`projects/video-studio-benchmark-20260930/README.md`）另行保存。新任務從這個 skill 開始，下方保留原 H3 notebook 的使用與歷史證據。

## 專案 skills

Fresh clone 後先執行 `python3 scripts/install_repo_skills.py` 建立本 repo 的發現連結；此指令不安裝套件、不改全域設定、不覆蓋既有不同目標。可用 `--check` 唯讀核對。

原始內容統一放在 `skills/`，以 `.agents/skills/<name> -> ../../skills/<name>` 的相對符號連結供此 repo 使用。新增 Colab／影片 skill 時沿用此方式，保留 repo 作用域；不連到 `~/.codex/skills/` 或 `~/.agents/skills/`。Codex 支援 repo 內的符號連結，見[官方說明](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。

| Skill | 用途 |
| --- | --- |
| [video-production](skills/video-production/SKILL.md) | 內容、分鏡、素材、剪輯與成片交付；含[短劇前製模板](skills/video-production/references/drama-preproduction.md) |
| [colab-video-studio](skills/colab-video-studio/SKILL.md) | Colab 製作計畫、逐段執行與驗收 |
| [minimax-h3-colab](skills/minimax-h3-colab/SKILL.md) | H3／FastH3／Pika H3 Flex 提示、模型契約與工具 |
| [ffmpeg-skill](skills/ffmpeg-skill/SKILL.md) | 本機音畫剪輯、字幕與轉檔 |
| [strata-colab-start](skills/strata-colab-start/SKILL.md) | Strata Colab runtime 啟動、恢復與釋放 |
| [strata-colab-client](skills/strata-colab-client/SKILL.md) | 呼叫已運作的 Strata API |

MiniMax-H3 on Colab A100
========================

The completed clip is gorilla_rocket_bf16_15s_480p.mp4（歷史證據未隨此 source-only repo 發佈：`artifacts/minimax-h3/gorilla_rocket_bf16_15s_480p.mp4`）.
The gorilla lifts the rocket, throws it overhead, and the camera follows it into space.

The reusable notebook is [notebooks/MiniMax_H3_A100.ipynb](notebooks/MiniMax_H3_A100.ipynb).
The executed notebook（歷史證據未隨此 source-only repo 發佈：`notebooks/MiniMax_H3_A100_output.ipynb`） includes the video
and the successful run's outputs.
The reusable notebook now has Colab dropdowns for **LightX2V Turbo 8-step,
4-step v1.2, 4-step v1.0, and original 50-step**, plus **BF16, pruned INT8
ConvRot, pruned NF4, and unpruned NF4** weights. Turbo 8-step
with BF16 is marked as an **80GB recommendation**. Quantized choices are marked
as **40GB candidates**, with explicit untested status for that workload.
Ref2VA supports native BF16 and both NF4 variants with Original 50-step or
the dedicated Ref2VA Turbo 8-step adapter; Ref2VA INT8 is not integrated.
Native BF16 Ref2VA Turbo8 has generated media-verified 7-second, 1312×736 clips
on an A100 80GB. This verifies the workload, not story-quality acceptance.
The revised Mid-Autumn preview（歷史證據未隨此 source-only repo 發佈：`projects/midautumn-h3/revision-02/README.md`） uses
native FL2VA BF16 Turbo4 v1.2 with first/last-frame guidance.
Offline tests separately verify component and processor routing.
See [MODEL_OPTIONS.md](plan/MODEL_OPTIONS.md) for sources, community feedback,
recommendations, hardware labels, and candidates requiring another backend.

Start with [USAGE.md](USAGE.md) for launch commands, prompt examples, image
references, and continuing one clip into the next. **Run setup cells 1–5 once;
for each clip, edit and run cells 6–7 at the bottom.** The existing pipeline is
reused. `CONTINUE_PREVIOUS` uses the preceding verified MP4's decoded final
frame. Timestamped output folders keep every take, including repeated names.

The reusable notebook lets you select **5–15 seconds** in one-second steps
and choose resolution in the clip settings, at 24 FPS with stereo audio. At 15 seconds,
H3 generates 362 frames and keeps 360 video frames, with 480,000 audio samples
per channel. It uses the selected model's prescribed steps/shifts and chooses a fresh random
seed for each generation by default; the actual seed is recorded in `metrics.json`.
Enter a number in **本片內容** to fix the seed for a repeatable setup. The historical
A100 clip used 50 steps.

The allocated runtime was measured as an A100-SXM4-80GB with 79.25 GiB usable
VRAM, 167.05 GiB system RAM, and approximately 188 GiB free disk. Full BF16
weights total about 134.14 GiB on disk, so the notebook loads components in
stages instead of keeping the entire pipeline in GPU memory. That run used a
70 GiB weight budget. The revised notebook reserves at least 10 GiB for other
allocations and caps the weight budget at 70 GiB. Actual successful
generation, rather than file sizes alone, determines whether these settings fit.

For an already authenticated Colab CLI, create the runtime only if it is not
already active. Edit the notebook's model dropdowns first:

```bash
colab --auth oauth2 usage
colab --auth oauth2 new -s minimax-h3-a100 --gpu A100 --high-mem
python3 scripts/export_cells.py setup --output /tmp/h3-setup.py
colab --auth oauth2 exec -s minimax-h3-a100 -f /tmp/h3-setup.py --timeout 7200

# After editing the notebook's clip settings; repeat only these two commands:
python3 scripts/export_cells.py clip --output /tmp/h3-clip.py
colab --auth oauth2 exec -s minimax-h3-a100 -f /tmp/h3-clip.py --timeout 7200
```

Section exports are Python scripts; they do not overwrite the historical
executed notebook. Inspect `PASS` and the run's `metrics.json`: CLI 0.7.2 can
return exit code zero even when remote Python has failed.

Download `video.mp4` and `metrics.json` from the printed
`/content/minimax-h3-runs/<RUN_NAME>_<timestamp>/`, then release
the runtime with `colab --auth oauth2 stop -s minimax-h3-a100`. Remote files
are ephemeral. `colab usage` showed 6.77 CU/hour for this allocation; check
the current rate each time rather than assuming that rate is fixed.
The historical executed notebook used the earlier `/content/minimax-h3-run/`
location; the usage guide describes the current reusable notebook.

**Colab CLI 0.7.2 dependency repair.** The PyPI installation pulled a Jupyter
client without `JupyterSubprotocol`, preventing notebook execution. This
session repaired it using Google's fork at the revision pinned in the
[CLI lockfile](https://github.com/googlecolab/google-colab-cli/blob/e25c2655c7ff2fffb7e6c493c51a910d5c461a0b/uv.lock):

```bash
uv tool install --force 'google-colab-cli==0.7.2' \
  --with 'jupyter-kernel-client @ git+https://github.com/googlecolab/jupyter-kernel-client.git@f18e982c3265df5e923aa9def101ab3fd737e139'
```

The reusable notebook pins DiffSynth, model revisions, and the key inference
dependencies while preserving the runtime's installed PyTorch/CUDA stack.
INT8 additionally installs pinned `comfy-kitchen`. The executed copy records the
original text-only run, before the new model menus and persistent workflow. Model files are public
and do not require a Hugging Face token. Model use remains subject to the
[MiniMax H3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE).

**Verified result — 2026-09-23:**

| Measurement | Result |
| :--- | :--- |
| Model | Original BF16 FL2VA; disk-backed staged offloading; no quantization |
| Device | One NVIDIA A100-SXM4-80GB; 79.25 GiB usable VRAM |
| Clip | Exactly 15.000 seconds; 360 frames; 832×480; 24 FPS |
| Audio | AAC, 32 kHz, stereo; decoded and non-silent |
| Sampled peak total GPU memory | 72.277 GiB |
| Peak PyTorch allocated / reserved | 67.911 / 71.762 GiB |
| Peak process RSS | 9.059 GiB on the tested 167.05 GiB host |
| Inference including lazy weight loading and decoding | 1,414.73 seconds (23 min 35 sec) |
| Total session CU debit | 4.94 CU, including setup, downloads, and the interrupted earlier demo prompt |
| Final account balance / rate | 195.06 CU / 0.00 CU per hour; no active assignments |

The notebook decoded all 360 video frames and checked both streams. Local
`ffprobe` independently confirmed the downloaded file's dimensions, frame count,
audio format, and exact 15-second stream/container durations. Sampled frames
show the gorilla's overhead throw and the rocket reaching space. The result ZIP
passed its CRC integrity check, and the executed notebook validates without
error outputs. The A100 runtime was released after downloads.

This verifies the listed original-model workload on an **80 GB A100**. New
Turbo/quantized combinations, first/last-image generation, and continuation have
source and offline workflow checks, but no new GPU generation or quality test.
The result does not establish performance on a 40 GB A100, with Turbo, or at
higher resolutions. The historical executed notebook is not included in this source-only checkout; the workload claims above are historical, not independently reproducible from the published artifacts.

Offline checks: `python3 -m unittest discover -s tests -v`. These exercise local workflow, cache, dialogue and evidence contracts using synthetic inputs; they do not establish real GPU memory use or generated content quality. CI runs the same offline suite. No test allocates a runtime or contacts a model API.

Evidence: metrics（歷史證據未隨此 source-only repo 發佈：`artifacts/minimax-h3/metrics_bf16.json`）,
resource samples（歷史證據未隨此 source-only repo 發佈：`artifacts/minimax-h3/resources_bf16.json`）,
local media check（歷史證據未隨此 source-only repo 發佈：`artifacts/minimax-h3/local_ffprobe.json`）,
environment versions（歷史證據未隨此 source-only repo 發佈：`artifacts/minimax-h3/environment_versions.json`）,
CU and setup record（歷史證據未隨此 source-only repo 發佈：`artifacts/minimax-h3/local_setup.json`）, and
scene preview（歷史證據未隨此 source-only repo 發佈：`artifacts/minimax-h3/contact_sheet.png`）.

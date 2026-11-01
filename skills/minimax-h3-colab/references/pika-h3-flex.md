# Pika H3 Flex 工具

指定 `pika` 時讀此頁。依使用者偏好，往後未另指定實作或精度的 `pika`，預選 **ComfyUI 的原 H3 INT8 底模＋對應 Pika H3 Flex BF16 LoRA**。明確要求官方獨立 CLI、BF16 或精度對照時，才使用下方的獨立工具分支。`omni` 仍指 FastH3 Omni／`h3-omni-int8`；兩者的模型與採樣設定分開。

## 預設：ComfyUI H3 INT8＋Pika

沿用 [ComfyUI workspace](../../../doc/COMFYUI_WORKSPACE.md)，依輸入選原 H3 `ref2va` 或 `fl2va` INT8 checkpoint，再接同家族的 Pika LoRA。Ref2VA 使用 repo 維護的 [Pika INT8 API starter](../../../workflows/comfyui_h3/pika-h3-ref2va-int8.api.json)，將 `reference.png`、提示與尺寸換成當次輸入，再由 `scripts/comfyui_workspace.py` 的 API 提交／等待／取回介面執行。接線依 [Comfy 官方 Ref2VA 範本](https://github.com/Comfy-Org/workflow_templates/blob/c067929d7e9cc0f3fd15be348fa1a1d85da15946/templates/video_pika_h3_flex_ref2va.json)核對；當次預算、批次排程與保存依共用製作流程處理。

- 量化範圍：starter 使用 INT8 H3 Ref2VA、NVFP4/AWQ Qwen3-VL encoder、INT8 video VAE、FP32 audio VAE、BF16 Pika Ref2VA LoRA；「預選 INT8」指 H3 底模，並非所有元件都用 INT8。首尾幀控制使用 [FL2VA INT8 API starter](../../../workflows/comfyui_h3/pika-h3-fl2va-int8.api.json)及對應的原 H3 FL2VA INT8／Pika FL2VA LoRA，依其實際範本核對端點輸入。
- 採樣沿用 [Comfy 官方 Pika adapter 設定](https://huggingface.co/Comfy-Org/MiniMax-H3/discussions/70)：`lcm`、`ManualSigmas = 1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0`、六次模型評估、CFG 1、LoRA strength 1。只接對應 Pika adapter；普通 Euler 六步或額外 Turbo／Omni adapter 不等價。
- 尺寸、幀數與 reference resize 依實際 ComfyUI 節點及 job 核對，不能直接套獨立 CLI 的 aspect buckets；starter 使用 `ref_image_size="match"`。Prompt 仍依 [Pika 官方指南](https://github.com/Pika-Labs/Pika-H3-Flex/blob/64d81b2e98aa8aa1cf078b07a6ef3aaeae1033da/docs/prompt-guidance.md) 綁定有序素材，Ref2VA 使用六欄及 `<Picture N>`／`<Subject N>`。
- 容量、速度及內容品質依當次配置與產物驗證。量化 ComfyUI 與官方 BF16 CLI 不是逐位等價實作；當次實測資料保存在 project／research，不作 skill 的工具入口。

此路徑使用 ComfyUI 的 queue／history／workflow 與當次保存收據；共用[資源生命週期](../../colab-video-studio/references/runtime-monitoring.md)。目前沒有名為 `pika-int8` 的 repo 通用 preset，以 API starter 編譯當次 job；`h3-omni-int8` 是另一模型的入口。

新對白、心聲或旁白 job 在提交前必走 [對白估時與語速](../../video-production/references/dialogue-pacing.md) 的原生 ComfyUI 入口：先換好當次視覺／動作 base，再以 `dialogue_timing.py compile-api` 產生帶逐句發聲目標和正確 frames 的 API graph，將其輸出交給上述既有提交介面。保留 timing report，核對沒有把模型5秒下限或長鏡頭當成說話時長；native cadence 仍須由實際輸出聆聽驗證。

## 明確選用：官方 BF16 獨立 CLI

以下設定與量測只適用此分支。

### 入口與版本

- Repo CLI：`scripts/pika_h3.py`，本機 Python 3.10+／標準函式庫；`plan`、`prepare()`、`status` 不安裝、不下載、不啟動 GPU。
- [獨立 notebook](../../../notebooks/Pika_H3_Flex_Colab.ipynb)：內嵌工具；預設 `INSTALL_PIKA=False`、`RUN_GENERATION=False`。依當次授權在目標 runtime 明確執行；不配置 GPU 或呼叫付費 API。
- [版本 lock](../../../scripts/pika_h3_lock.json)：官方 code `64d81b2e98aa8aa1cf078b07a6ef3aaeae1033da`、模型 `0ddf55ad7067ca1e76812253bd7b4600df87f759`。安裝遵循官方 requirements／Diffusers patches／`pika-h3-pro` package，使用獨立 Python 3.12 venv，沿用 HF cache／`HF_TOKEN` 環境。

此接入只做離線契約及模擬程序檢查；GPU 推論／性能／畫質為 `not_run`。官方測試單張 H100 80GB，本工具尚未驗證 A100／L4／T4。官方 480p／5s sampling 約 66–69 GiB；offload 長片 sampling 約 29–32 GiB GPU，host memory 曾接近 94 GiB，encoder／VAEs 另有峰值，不能當整體最低需求。兩種 task 家族合計約 210 GB base＋5.5 GB adapters，另留依賴與暫存。配置前核實 GPU／host RAM／磁碟。來源：[官方硬體測試](https://github.com/Pika-Labs/Pika-H3-Flex/blob/64d81b2e98aa8aa1cf078b07a6ef3aaeae1033da/docs/hardware.md)。

### 模式與輸入

| task | 實際條件 |
| --- | --- |
| `t2va` | 純文字，不帶圖片或 references |
| `i2va` | `--first-image` |
| `l2va` | `--last-image` |
| `fl2va` | `--first-image` 與 `--last-image` |
| `ref2va` | 有序 `--ref image:path`／`video:path`／`audio:path`；至少一張圖或一段影片，與首尾圖互斥 |

Ref2VA 上限：9 圖、3 影片、3 獨立音訊、合計 12 檔。每段影音須 2–15 秒；影片合計及獨立音訊合計各不超過 15 秒。影片自帶音軌隨影片送入，不另算獨立音訊。Wrapper 先核模式與數量，官方 CLI 再驗格式／影音長度並記輸入 hash；最大組合的 GPU 容量另驗。

Prompt 依 [Pika 官方指南](https://github.com/Pika-Labs/Pika-H3-Flex/blob/64d81b2e98aa8aa1cf078b07a6ef3aaeae1033da/docs/prompt-guidance.md)核 reference 編號、順序與保留／改動要求。UTF-8 文字 1–8000 字元，原樣寫入 prompt file，不套原 H3 wrapper 的六欄 validator。

原生 480p／768p、11 種 aspect buckets、24fps、32kHz stereo、5–15 整數秒。工具起始設定是 480p／16:9／5s，實際 832×480／124 幀（約 5.17s）；768p／16:9 是 1344×768。完整尺寸從 lock 讀取；15s 為 362 幀，不自動裁成精確片長。

官方採樣使用 `1000/750/500/250/100/40/0` knots、video/audio shift 12/3 與中間 fresh noise，由官方套件處理。普通 Euler 六步不等價；不另疊 Turbo／Omni LoRA。4K、分離 audio stems 與 prompt enhancement 是 hosted 服務，本工具未接入。來源：[固定版 README](https://github.com/Pika-Labs/Pika-H3-Flex/tree/64d81b2e98aa8aa1cf078b07a6ef3aaeae1033da)。

### 操作與產物

安裝／生成在已授權的 NVIDIA runtime 執行。本機可先做離線計畫；同 runtime 的安裝與生成依序執行。

```bash
python3 scripts/pika_h3.py plan --root /content/pika-h3
python3 scripts/pika_h3.py install --root /content/pika-h3 --python /usr/bin/python3.12
python3 scripts/pika_h3.py generate --root /content/pika-h3 \
  --task ref2va --prompt-file /content/prompt.txt \
  --ref image:/content/actor.png --ref video:/content/motion.mp4 \
  --resolution 480p --aspect 16:9 --duration 5 --seed 42 --cpu-offload
python3 scripts/pika_h3.py status --root /content/pika-h3
```

`PikaWorkspace(root).prepare(prompt=..., task=..., refs=[...])` 預覽 job、尺寸及命令，無檔案或網路副作用。`install` 只安裝依賴，`generate` 才下載所選 task 的權重；CLI 每次重新載入 pipeline。Pika venv 與 Omni 的 ComfyUI 環境分開。

每次生成建立新 `runs/<id>/`，保存 `request.json`、原文 `prompt.txt`、`generation.log`、官方 `video.mp4`／`video.json` 及 `receipt.json`。完整影音解碼、尺寸／幀數與 stereo 檢查通過才記 `technically_valid`，內容仍為 `not_reviewed`。`wall_seconds` 包含該次 CLI 與輸出核驗，不含先前安裝及事後下載；不把 sampling timing 當完整耗時。

斷線後依[共用生命週期](../../colab-video-studio/references/runtime-monitoring.md)查原 run／PID／日誌再決定新 take；`status` 只讀已記錄 receipt，不聲稱程序仍存活、不重送。保存並核對本機產物後另行釋放 Colab runtime；此工具不提供常駐 server、資源管理或 Studio reserve／fetch 身分。

修改 wrapper／lock 後執行 `python3 scripts/build_pika_h3_notebook.py` 重封裝。`scripts/export_cells.py setup|clip --notebook notebooks/Pika_H3_Flex_Colab.ipynb --output <path>` 可匯出至 persistent Colab kernel。

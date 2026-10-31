# Pika H3 Flex 工具

指定 `pika` 時讀此頁；`omni` 指既有 [ComfyUI workspace](../../../doc/COMFYUI_WORKSPACE.md) 的 FastH3 Omni／`h3-omni-int8`。Pika 使用獨立官方 CLI，不是 Studio 的 `settings.backend`，也不是把 Omni 步數改成六步。

## 入口與版本

- Repo CLI：`scripts/pika_h3.py`，本機 Python 3.10+／標準函式庫；`plan`、`prepare()`、`status` 不安裝、不下載、不啟動 GPU。
- [獨立 notebook](../../../notebooks/Pika_H3_Flex_Colab.ipynb)：內嵌工具；預設 `INSTALL_PIKA=False`、`RUN_GENERATION=False`。依當次授權在目標 runtime 明確執行；不配置 GPU 或呼叫付費 API。
- [版本 lock](../../../scripts/pika_h3_lock.json)：官方 code `64d81b2e98aa8aa1cf078b07a6ef3aaeae1033da`、模型 `0ddf55ad7067ca1e76812253bd7b4600df87f759`。安裝遵循官方 requirements／Diffusers patches／`pika-h3-pro` package，使用獨立 Python 3.12 venv，沿用 HF cache／`HF_TOKEN` 環境。

此接入只做離線契約及模擬程序檢查；GPU 推論／性能／畫質為 `not_run`。官方測試單張 H100 80GB，本工具尚未驗證 A100／L4／T4。官方 480p／5s sampling 約 66–69 GiB；offload 長片 sampling 約 29–32 GiB GPU，host memory 曾接近 94 GiB，encoder／VAEs 另有峰值，不能當整體最低需求。兩種 task 家族合計約 210 GB base＋5.5 GB adapters，另留依賴與暫存。配置前核實 GPU／host RAM／磁碟。來源：[官方硬體測試](https://github.com/Pika-Labs/Pika-H3-Flex/blob/64d81b2e98aa8aa1cf078b07a6ef3aaeae1033da/docs/hardware.md)。

## 模式與輸入

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

## 操作與產物

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

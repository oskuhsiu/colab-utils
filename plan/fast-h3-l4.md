# FastH3：Notebook 與 Colab ComfyUI L4 流程

## 使用者要求

依本機保存的 closerAI FastVideo-Minimax-FastH3 知乎文章，準備兩套生成流程：

1. 從現有 H3 notebook 擴充 FastH3 與 LoRA 掛載功能。
2. Colab 安裝 ComfyUI、下載所需模型，agent 修改節點設定並輸出影片。

兩者使用 **L4**；本次 GPU 測試只允許 **FastH3**。不執行原版 H3／Turbo 基座的高記憶體生成，不配置 A100 或 high-memory runtime。

## 已讀取的文章設定

- FastH3：`minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors`。
- 文字編碼器：`qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`。
- Video VAE：`minimax_h3_video_vae_int8_convrot.safetensors`。
- Audio VAE：`minimax_h3_audio_vae_fp32.safetensors`。
- VSA：keep 10%，start/end 0/1、minimum tokens 8192、strict native backend。
- 原始模型時間步：`[999, 749, 500, 250]`，需要由模型採樣器轉成 sigmas，包含終點。
- 專用 Euler；CFG 1；24 fps；5 秒；864×480；截圖的 length=124。
- 目前預览使用文字條件；截圖節點明示首尾幀暫未接入。

以上是文章與截圖資料，不代表已驗證上游目前實作或 L4 相容性。原作者 workflow JSON／私有節點若無法取得，交付自行重建的等效工作流並明示差異。

## 實作邊界

- 保留既有 DiffSynth 模式與 notebook cell ID、setup/clip 匯出契約。
- FastH3 在安裝、下載及載入前分流；不能只降低原版模型步數。
- 以目前可查證的 FastH3 loader、VSA 與 scheduler 實作固定版本。
- FastH3 student 已經蒸餾；預設不再加 LightX2V Turbo LoRA。
- 另提供使用者可選的相容 LoRA 清單、strength 與實際載入紀錄。
- 匯出 ComfyUI 可讀的 UI workflow 與 agent 可修改的 API graph。
- Colab 控制流程包含設定檢查、提交、查詢、下載驗證及釋放；斷線不自動重送生成。

## 本次短測與完成證據

- 先完成本機程式、graph、依賴及 model manifest 檢查，再配置獨立 L4。
- 正常 RAM；確認 GPU 型號與實際資源。VSA 的 L4 小型 kernel 檢查在大模型下載前執行。
- 文生測試使用自訂簡單單主體動作／聲景，5 秒、864×480、固定 seed；無真人素材。
- 每條路徑先執行一片，只有具體程式／環境錯誤修正才做技術重試；不做品質抽卡或原版 H3 對照。
- 預備上限：本輪最多 90 分鐘 L4 runtime；若相容性仍需研究，先保存證據並釋放 GPU再修改。
- 安裝／下載／載入／推論期間持續保存 phase、資源與日誌；片段完成立即取回本機。
- 成功需有實際 FastH3 模型、VSA 狀態、steps/sigmas、LoRA 清單、prompt/seed 的紀錄，以及可完整解碼且具有音訊的 MP4。
- 分開報告本機檢查、GPU 執行、媒體驗證與內容觀察；未實測的能力保持未實測。
- 結束核對遠端 assignments 與計費，保留全部本機產物。

## 即時資源基準

2026-10-09 讀取 Colab CLI：24.35 CU、0.00 CU/hr、active assignments 0、server sessions 空。這是測試前快照，後续須重新確認。

## 完成證據

兩條入口均在同一台 L4 完成 864×480、5 秒／120 frames、32 kHz stereo：原 notebook FastH3 分支 176.80 秒，agent ComfyUI graph 161.43 秒；各 200 次 VSA／零 fallback。第二段使用合成 rank-2 adapter、strength 0.7，1 個實際模型 target，僅驗證掛載與推論。

量化四模型共 39.45 GiB，逐檔 SHA256 通過。原 H3 功能保留；本輪沒有原模式 GPU 對照。過程發現 Comfy compiler 的 allocation graph CUDA 中止，單一旗標 `--disable-comfy-compiler` 對照解除；相關原始失敗證據保留。

兩支 MP4、UI/API graph、metrics、模型／LoRA hash、硬體／版本／資源與本機完整解碼證據在 `artifacts/fast-h3-l4/`。58 個 FastH3 與 16 個既有 H3 檢查通過；完整 114 個測試有 113 通過、1 個原本已失敗的 Qwen notebook cell 數量測試，沒有改該部分。

L4 已釋放：sessions 空、assignments 0、0.00 CU/hr；24.35 → 23.02 CU，本輪共 1.33 CU。操作與限制見 `doc/FAST_H3_L4.md`。

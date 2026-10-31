# FastH3：兩套 L4 生成流程

依使用者提供的 closerAI 知乎文章／節點截圖重建，使用 ComfyUI 原生節點、公開 VSA 套件與本專案節點；不使用作者私人節點。

## 目標一：原 H3 notebook 新增 FastH3 選項

[MiniMax_H3_A100.ipynb](../notebooks/MiniMax_H3_A100.ipynb) 第一格新增 `BACKEND`：

- `DiffSynth | Original H3 (FL2VA / Ref2VA)`：保留既有 FL2VA、Ref2VA、Turbo 4/8-step、Original 50-step、BF16/INT8/NF4 選單，以及原提示詞與參照設定。
- `FastH3 | ComfyUI L4 (T2VA)`：新增的 FastH3 路徑，共用下方工作流。安裝、下載、載入與推論前分流，不下載原版 H3。

FastH3 預設選取以便本輪測試；原 H3 功能仍保留。切換底層引擎請重新啟動 runtime，避免兩套大型模型共存。**本輪只在 L4 測 FastH3，原模式沒有重新做 GPU 測試。**

新 runtime 執行 A 區一次；每片只改 B 區中的 `FAST_H3_PROMPT`、尺寸、秒數、seed 與 run name，再執行生成格。原 H3 的 `PROMPT`、首尾圖、references 獨立保留。FastH3 preview 這條路徑只走 T2VA。

`FAST_H3_LORAS_JSON` 預設 `[]`。文章 baseline 使用已蒸餾 student，不需要再加 Turbo LoRA。可選相容的內容／風格 adapter，例如：

```json
[{"path":"/content/my_fast_h3_style.safetensors","strength":1.0}]
```

或固定版本下載：

```json
[{"repo":"owner/repository","file":"adapter.safetensors","revision":"完整40字元commit","strength":1.0}]
```

以上是格式例，需換成實際相容 adapter。LoRA 節點記錄 hash、strength 與模型 targets；無匹配或只套用部分 patch 就停止。ComfyUI 處理 adapter 的 alpha/rank，strength 為額外倍率，不沿用 DiffSynth 的 `0.0625`。本次沒有指定內容 LoRA，GPU baseline 不會任意加入 adapter；未產片驗證的 adapter 不宣稱相容或品質有效。

## 目標二：Colab 安裝 ComfyUI，由 agent 操作 nodes

[FastH3_ComfyUI_L4.ipynb](../notebooks/FastH3_ComfyUI_L4.ipynb) 是獨立 FastH3 notebook，包含 setup 與每片生成區。

可匯入工作流：[fast_h3_l4.json](../workflows/fast_h3_l4.json)。Agent 使用 API graph：[fast_h3_l4.api.json](../workflows/fast_h3_l4.api.json)。

```text
FastH3 INT8 -> optional LoRA -> video/audio shift 12/3 -> learned VSA
                                                            |
Qwen3-VL + video VAE -> text conditioning + AV latent         |
                               |                            |
                          BasicGuider <----------------------+
                               |
noise + trained sigmas + Euler -> SamplerCustomAdvanced
                               |
                     video/audio VAE decode
                               |
                    VSA receipt + duration trim
                               |
                       CreateVideo -> SaveVideo
```

| 文章接線 | 本流程替代 |
| --- | --- |
| FastH3 專用載入器 | 原生 `UNETLoader`，固定 student checkpoint |
| closerAI Native VSA | 公開 `FastH3VSAPatch`，keep 10%、64-token tile、min_tokens 8192，錯誤即停止 |
| 精確時間步 | 本專案 `FastH3ExactSigmas`，由模型把 `[999,749,500,250]` 轉為 sigmas，再加終點 0 |
| FastH3 Euler | 原生 `KSamplerSelect(euler)`，搭配 H3 影音雙時鐘 12/3 |
| FastH3 T2VA | 原生 `MiniMaxH3ImageToVideo`，只送文字，無首尾圖 |
| 影音解碼／儲存 | 原生 VAE、`CreateVideo`、`SaveVideo`，本專案節點保存 VSA 執行證據並裁切 |

5 秒的 H3 模型格點為 124 frames（約 5.167 秒）；照文章格點生成後，裁成 **120 frames／5.000 秒**，音訊也裁成 5 秒。成功證據要求 **50 blocks × 4 forwards = 200 次 VSA 呼叫**，零 dense fallback。開啟選項不等於 VSA 實際執行。

## 模型與環境

[fast_h3_lock.json](../scripts/fast_h3_lock.json) 固定 Git/HF revision、檔案大小及 SHA256。四個初始模型共 **39.45 GiB**：

| 模組 | 檔案 |
| --- | --- |
| FastH3 student | `minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors` |
| 文字 encoder | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` |
| Video VAE | `minimax_h3_video_vae_int8_convrot.safetensors` |
| Audio VAE | `minimax_h3_audio_vae_fp32.safetensors` |

這是文章的 **1300-step student 量化版**；FastVideo v0.2 是另一個 2900-step checkpoint。四步降低推論次數，L4 的容量仍依賴量化與 offload。

安裝使用隔離 venv、固定 ComfyUI／公開 VSA pack commit、Comfy Kitchen 0.2.37。先確認單張 NVIDIA L4，跑小型原生 Sol-Attn CUDA 檢查，再下載大模型。服務只監聽 Colab 的 `127.0.0.1:8188`；notebook 可選本機連接埠預覽。這套 L4 設定使用 `--disable-comfy-compiler`：預設 compiler 的 allocation graph 曾在第一個 forward 後触發 CUDA 釋放錯誤；同條件停用後完成生成。仍保留動態 VRAM 與 offload。

## CLI／agent 操作

先複製 tracked [每片設定模板](../templates/fast-h3/clip.json)，修改本次 prompt、seed 與 run name。模板為 864×480、5 秒 T2VA，無參考圖與 LoRA；兩條入口共用相同設定契約。以下從 repo 根目錄執行，只有 `prepare` 是純離線，其餘命令需要已認證的 Colab CLI 與本次執行授權：

```bash
# 複製成自己的每片設定；不配置 GPU 的離線準備
cp templates/fast-h3/clip.json /tmp/fast-h3-clip.json
python3 scripts/fast_h3_colab.py prepare --backend comfy \
  --config /tmp/fast-h3-clip.json

# 建立或沿用指定 L4；沒有 A100 / high-mem 參數
python3 scripts/fast_h3_colab.py start --session fast-h3-l4

# 目標一：實際執行修改後的原 H3 notebook cells
python3 scripts/fast_h3_colab.py setup --backend notebook --session fast-h3-l4
python3 scripts/fast_h3_colab.py generate --backend notebook --session fast-h3-l4 \
  --config /tmp/fast-h3-clip.json

# 目標二：由 agent 設定 graph 並提交
python3 scripts/fast_h3_colab.py setup --backend comfy --session fast-h3-l4
python3 scripts/fast_h3_colab.py generate --backend comfy --session fast-h3-l4 \
  --config /tmp/fast-h3-clip.json

python3 scripts/fast_h3_colab.py status --session fast-h3-l4
python3 scripts/fast_h3_colab.py fetch --session fast-h3-l4
# 若 CLI 連線失效，核對原工作後只刷新同一 VM 的 proxy
python3 scripts/fast_h3_colab.py refresh --session fast-h3-l4
python3 scripts/fast_h3_colab.py stop --session fast-h3-l4
```

同一台 L4 可依序使用兩條入口。Config 只接受模板中的九個欄位；`width`／`height` 必須是正的 32 倍數，總面積不超過 1344×768；`duration_seconds` 為 5–15 的整數，`run_name` 不含路徑分隔符。正式生成前替換範例 prompt；T2VA 保持 `generation_mode="t2va"` 與 `reference_paths=[]`。`prepare` 會驗證設定並將 config、toolkit 與 API graph 寫至 `--output`（預設 `artifacts/fast-h3-l4/`），不建立 Colab session。Config 的 prompt、seed、尺寸與 LoRA 清單會更新對應 node inputs。提交前由 `/object_info` 檢查 node／input／link，再只提交一次。要直接編輯 API graph，可用 [fast_h3_client.py](../scripts/fast_h3_client.py) 的 `validate_graph`、`queue_prompt`、`wait_prompt`，保存自己的 prompt ID 與 receipt。

每輪有獨立 action ID，進度／資源持續抓回 `artifacts/fast-h3-l4/state/`。CLI exit code 0 不算成功，須讀到对应 action PASS 和 FastH3 receipt；斷線先查 status/fetch 原工作，不自動重送。

每片保留 MP4、UI/API workflow、prompt/seed/LoRA/VSA metrics、model manifest、硬體、套件版本、資源取樣。下載後比對 SHA256，完整解碼並驗尺寸、fps、影格數、音訊及時間；技術通過和內容驗收分開記錄。MP4 也附本工作流 metadata，JSON 同時獨立交付。

## 驗證紀錄

需要放大成片時，使用 [AI 圖片／影片放大流程](AI_UPSCALER.md)。現有 CLI 產出的 MP4 可交給逐幀 tiled upscaler；[FastH3 + 2× ComfyUI 工作流](../workflows/fast_h3_l4_upscale_2x.json) 則保留原生 MP4，從裁切後的影格與音訊另存 2× 成片。生成 receipt 與放大結果的驗證分開保存。

FastH3 本機 client／workflow／notebook 合約測試通過；原 H3 的 16 個既有合約測試通過。完整套件在改動前已存在一個無關 Qwen notebook cell 數量測試失敗（期待 2，實際 3），沒有修改該部分。

目標一已實測：L4、864×480、5.000 秒／120 frames、32 kHz stereo，4-step Euler／200 次原生 VSA／零 fallback；首次完整工作含權重初始化與解碼為 176.80 秒，取樣的整張 GPU 用量峰值 20.18 GiB。原尺寸首／中／尾影格可見紅色玩具火車從左向右移動。聲音已完整解碼且非靜音，未另做內容聽審。目標二也通過：agent graph 產出相同規格影音，161.43 秒，200 次 VSA、零 fallback，取樣 GPU 峰值 19.97 GiB。以合成低幅度 rank-2 LoRA、strength 0.7 掛上 1 個實際模型 target 並完成推論；這證明載入／接線，不代表真實訓練的風格或人物 LoRA 品質。首／中／尾影格可見藍色玩具帆船由左向右移動。這些是歷史測試範圍，原始產物不作為此操作流程的輸入依賴。

本輪已釋放 L4：server sessions 空、active assignments 0、計費 0.00 CU/hr。餘額 24.35 → 23.02，本輪共 1.33 CU，包含安裝／下载／診斷與兩條入口的成功生成。

來源／版本：[primary-source report](../research/fast_h3_primary_sources.md)、[本輪計畫](../plan/fast-h3-l4.md)。使用者保存的 PNG/JPG 和兩段 MP4 已檢查，沒有可直接提取的 workflow/prompt metadata，因此依截圖與公開原始碼重建。

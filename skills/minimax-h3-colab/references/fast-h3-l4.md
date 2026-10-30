# FastH3：pinned ComfyUI 路徑

此頁適用 repo 的 FastH3 T2VA student 路徑；現有 recipe／runtime 限 L4，其他硬體需另建立契約，不能把此限制推廣成 FastH3 理論能力。本路徑與原 H3 DiffSynth 獨立；照片條件看 [fast-h3-reference.md](fast-h3-reference.md)。

## 入口與離線準備

工具定位見 [repo-tools.md](repo-tools.md)，詳細操作在 `<repo>/doc/FAST_H3_L4.md`。`fast_h3_colab.py prepare` 只產生 config／toolkit／graph；`start` 配置或重用 session，`setup` 安裝／下載，`generate` 推論，副作用不同。離線任務止於準備。明確指定 `--output <run-dir>`，workflow exporter 也指定 `--output-dir`，避免重建 canonical workflows。

CLI 可選 `--backend notebook`（原 H3 notebook 的 FastH3 分流）或 `comfy`（直接 runtime）；兩者使用同一引擎。Notebook 的 `BACKEND` 選擇要核對實際設定，檔名不代表硬體需求。只看 cell IDs／tags／settings；具體錯誤才讀相關實作，勿輸出 `FAST_H3_SOURCES` 巨型嵌入字串。

## Checkpoint 與採樣契約

`scripts/fast_h3_lock.json` 是 repo pin 的來源：Kijai INT8 ConvRot `1300step`、4-step T2VA student，NVFP4-AWQ Qwen encoder、INT8 video VAE、FP32 audio VAE。它與 FastVideo v0.2 的 2900-step checkpoint 分開處理。Git/HF revision、bytes 與 SHA 直接查 lock，不手抄成第二份清單。

Graph 使用 video/audio shift 12/3、Euler、精確 timesteps `[999,749,500,250]` 經模型轉為 sigmas 再加零 endpoint、learned VSA keep 10%／64-token tile／min_tokens 8192／failure_mode=error。此 pinned 50-block graph 必須有四 forwards、200 VSA calls、零 fallback；打開選項或 kernel 小測通過不代表全圖已執行。

本地 builder 接整數 5–15 秒、正的 32 倍數寬高且像素面積不超過 1344×768。模型長度用原生 `17k+5` 格點，5 秒為 124 格，交付裁為 120 格／24 fps、音訊同步裁為 5 秒。其他長度按實際 receipt 與 decoded output 核對。

Student 已蒸餾，預設不再疊 base H3 Turbo adapter。內容／風格 LoRA 必須相容：remote 用精確 revision 或 local safetensors，記 hash、strength 及實際 mapped targets；非零 strength 必須識別到 patches，且已識別 patches 能完整套用；strength=0 只記錄停用。此檢查不證明原權重的所有 keys 都已解析，完整相容性另核對。ComfyUI 處理 alpha/rank，strength 為額外倍率，不能照抄 DiffSynth 的 0.0625。合成 adapter 只證明 loader 接線，真實風格／身份效果另驗。

## 執行與完成證據

固定 session、config、獨立輸出目錄，按授權執行 setup／generate。成功需對應 action ID 的 PASS、Comfy prompt ID／history、FastH3 receipt、下載 MP4 的 hash／完整解碼與實際尺寸、fps、片長及音軌；CLI exit 0 不能代替這些證據。斷線恢復看 [runtime.md](runtime.md#proxy-與原作業恢復)。技術完成與內容 verdict 分開記錄，通用內容檢查見 [Studio 驗收](../../colab-video-studio/references/video-review.md#通用驗收)。

## 計時口徑

分開 setup／下載、端到端單片、sampler 及 forward timing。`metrics.total_seconds` 在準備／下載後由送出 graph 到儲存／驗證計時，包含 queue、編碼、首次模型載入、採樣、VAE 與驗證。`vsa.elapsed_seconds`／首個 forward 仍可能含載入成本。

`metrics.total_seconds` 不含提交前的素材上傳、驗證後的封存打包、生成後 CLI 狀態拉取、封存下載與本機核驗；預算准入用實測或保守估算的完整保存耗時，見[提交前的預算判斷](../../colab-video-studio/references/runtime-monitoring.md#提交前的預算判斷)。比較端到端耗時時，明記本機取回的起末時間及這些額外階段。

ComfyUI 進度列可能把首步列 initialization 並重設起點，顯示的速率不是獨立四步計時；直接扣首步會連首次推論一起扣掉。Warm benchmark 需新 request、receipt 與媒體，見 [參照分支快取](fast-h3-reference.md#暖機與條件快取)。純採樣、原生生成與含後製交付時間各自標範圍，不以估算充作實測。

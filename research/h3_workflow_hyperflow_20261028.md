# 使用者 workflow 與 HyperFlow-Infinity 接線研究

查核日期：2026-10-28。作為目前 [Omni 整合](h3_omni_20261028.md) 的參考；沒有執行第三方 workflow、安裝 HyperFlow 或生成影片。原始下載檔未修改。

## YZ 金魚 workflow：實際存的是 hybrid／match 配方

本地來源：`/Users/apple/Downloads/YZ金鱼-MiniMax+H3+终极篇-文武双全.json`。117,562 bytes；SHA-256 `8bd5b87acac68685c48dcde0be5dff7e1d87f9ee9b827e8c1b80ce1cf65dc3b4`。這是 ComfyUI UI graph（100 nodes、75 links），不是可直接交給 `run_api()` 的 API JSON。

以下依 node IDs／widgets／links 的靜態讀取，不代表實際 UI group 開關後的執行狀態：

| Node ID | 接線／設定 | 意義 |
| --- | --- | --- |
| 192 | `minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors` | 與前述社群 hybrid 的 b25–49 變種相符；不是 FastH3 Omni |
| 265 | `MiniMaxH3ReferenceToVideo`；`ref_image_size="match"` | 這份檔案尚未改成 `max`；有九圖、三影片、三音訊的接點 |
| 255／261／333 | Euler、simple、12 steps、denoise 1、shift 12/3 | 與已蒸餾 Omni 的固定八步配方不同 |
| 53 | DMAD/DareTies LoRA，strength 約 0.8 | 啟用的額外蒸餾配件；不能視為 Omni 的必要配件 |
| 400 | 另一個 LoRA，strength 約 0.35 | 啟用的額外風格配件；沒有針對本次人物的驗證 |
| 342／343／344／345 | 四個動作／速度 LoRA，`mode=4` | 檔案保存時為 bypass，不是全部都啟用 |
| 331／332 | `comfy kitchen attention` → `sol-attn`，tau 1.3，start 0.2，sink `exact_kv_and_rows` | 需另核對平台／版本；不能直接當作目前 Colab 可執行的證據 |
| 401 | `MiniMaxChunkFeedForward`：chunks 2、threshold 4096 | 這是 feed-forward 記憶體分塊，不是跨片段延續或人物記憶 |
| 397 | `SelfLiftH3Sampler`：CFG 1、transition step 6、lowres scale 0.6，另帶 latent upscaler | 是另一種採樣／放大流程，不能直接移植成 Omni 八步驗證結果 |
| 252 | ResolutionSelector：16:9、1.5 MP、32 倍數 | 超過目前 starter 的約 1 MP 上限，增加記憶體需求 |
| 38 | 另一個修改版 INT8 Qwen3-VL encoder | 不是本次 catalog 固定的發布者 encoder |
| 36／37 | INT8 video VAE、FP32 audio VAE | 與目前低記憶體元件方向相同 |

檔內仍有圖片／音訊的 `None` 與空影片路徑，seed 控制為 randomize，且使用 Set/Get、群組忽略、VHS、SelfLift 等節點。它是可參考的配置範本，無法只憑這份 JSON 證明穩定度或比較人物相似度。

[ComfyUI 官方指南](https://docs.comfy.org/tutorials/video/minimax/minimax-h3#choosing-the-checkpoint-precision) 目前明列 Comfy Kitchen attention 不支援 INT8 ConvRot diffusion checkpoint。這份平台 workflow 同時選擇兩者，可能涉及平台修改或不同版本，原因尚未確認；因此未把該 attention 鏈直接搬入本 repo。Omni 的現有 native starter 採 dense attention，保留發布者八步契約。`max` 已作為可選參考圖設定接入，而不是連同這份 workflow 的所有 LoRA／SelfLift 配件一起複製。

## HyperFlow-Infinity 本身已使用本地 H3

固定來源：[Video-Rebirth/hyperflow-infinity](https://github.com/Video-Rebirth/hyperflow-infinity/tree/6c3291f319de9a81f63538af9b48da7cbc0b6a3f)，HEAD `6c3291f319de9a81f63538af9b48da7cbc0b6a3f`，2026-10-24 初始 commit，版本 0.1.0，程式 Apache-2.0。[README](https://github.com/Video-Rebirth/hyperflow-infinity/blob/6c3291f319de9a81f63538af9b48da7cbc0b6a3f/README.md) 已明確使用本地 MiniMax H3 + HyperFlow。選用 OpenRouter 時，付費服務負責 Director／Memory 的視覺語言模型，並非影片生成器。

上游要求 Linux、Python 3.10+、ffmpeg／ffprobe，至少四張 NVIDIA GPU（OpenRouter 可減為三張），只驗證 H200 141 GB；依賴固定 PyTorch 2.11／Diffusers 0.40 等版本。因此現有 A100／L4 notebook 不能把它當作直接可跑的單卡工具。HyperFlow 模型權重另受 MiniMax H3 模型授權規範，並不因 harness 程式是 Apache-2.0 而改變。

### 一致性機制與實際邊界

| 層次 | 原始碼實際做法 | 與目前工具的關係 |
| --- | --- | --- |
| 身份錨點 | 固定一張 identity image，後續每段都重新帶入；未提供時，從第一段 12 個候選畫面挑一張 | 可借用策略；若目標是像使用者原照，應保留原照作錨點，避免把第一段偏差固定下來 |
| 畫面交接 | 從前段保存檔取最後 7 個 normalized video latents，不經 RGB 重編碼，並對齊到新片段目標時間位置 | 這是移植的主要難點；一般影片 reference 不是等價替代 |
| 時間與接點 | 首段 345 幀；續段生成 141 幀，裁掉 22 幀重畫交接區，新增 119 幀；24 fps | 原始策略可重現，但不能直接把其中數字套給任意片長或 sampler |
| 劇情與場景記憶 | VLM 觀看前段，更新文字 scene graph／事件／章節，Director 決定下一段；另有重複觀察偵測 | 主要改善長片規劃及故事延續，並非臉部像素鎖定 |
| 素材記憶 | 一個固定身份圖；新人物只記文字外觀，沒有依場景／角色檢索圖片的資產庫 | 不宜把 scene graph 宣稱為完整的多角色視覺記憶系統 |
| 收據與恢復 | 保存 request、hash、latent、conditioning audit、state 與 memory，通過契約後才 commit 片段 | 可沿用目前工作收據／人工檢查原則；需要額外跨段狀態 |

來源：[engine.py 的 frame/request 契約、身份圖及 observe/plan/commit](https://github.com/Video-Rebirth/hyperflow-infinity/blob/6c3291f319de9a81f63538af9b48da7cbc0b6a3f/src/hyperflow_infinity/engine.py)、[handoff.py 的最後七個 latent 與位置對齊](https://github.com/Video-Rebirth/hyperflow-infinity/blob/6c3291f319de9a81f63538af9b48da7cbc0b6a3f/src/hyperflow_infinity/handoff.py)、[文字 scene graph](https://github.com/Video-Rebirth/hyperflow-infinity/blob/6c3291f319de9a81f63538af9b48da7cbc0b6a3f/src/hyperflow_infinity/memory.py)。上述原照錨點取捨是本次移植判斷，不是上游比較實驗的結論。

另一個值得區分的細節：上游 `generator.py:71–85` 主動把 reference image 短邊設為 480，而不是 2048。它的一致性設計重心是固定身份圖、latent 交接與故事記憶，不能把其長片示範歸因於 `max`。

### 接到現有 ComfyUI／Omni 的具體界面

生成替換點是 [generator.py](https://github.com/Video-Rebirth/hyperflow-infinity/blob/6c3291f319de9a81f63538af9b48da7cbc0b6a3f/src/hyperflow_infinity/generator.py) 的 `_build()`／`_execute()`；外層 Engine 已以 `generator.generate(request)` 呼叫它。但回傳不只有 MP4，還包括音訊、normalized video/audio latents、媒體資訊與 conditioning audit。`handoff.install()` 會 patch 五個 Diffusers 內部步驟；改成 ComfyUI HTTP 需要實作相應條件，不能保留假 audit 來繞過驗證。

最小可驗證的完整移植應分三個整合邊界：

1. **ComfyUI latent 介面**：保存 sampler 輸出的 H3 AV latent；定義與 normalized latent 的轉換、尺寸／時間格／模型版本契約。新增可在 reference 條件之外注入原始 tail latent 的 guide 節點，驗證身份圖與 tail 均實際到達 sampler。
2. **Generator adapter**：將 Hyperflow request 轉為 native Ref2VA graph，回傳影片、音訊、latent 路徑、hash 與真實 audit；沿用單一 prompt ID，逾時先查原工作。先做「一段開場＋一段續接」，核對 141→119 幀與無重編碼的 tail 交接，再驗內容。
3. **外層導演與記憶**：保留 scene graph、計畫、恢復與 commit 流程；將 VLM 與影片模型分時執行或拆為服務，處理單卡資源。固定使用者原照，對新人物另建立資產對照；把停止條件改為有限段數／時長，再逐步驗長片。

這是可執行的後續移植設計，尚未實作。保留相同 harness、改用 Omni 也需要重新驗證；HyperFlow 的八步 LoRA 與 FastH3 Omni 是不同的蒸餾路徑，不應疊加。只用前段 MP4 作 reference 可做較簡單的實驗，但會經 VAE 重編碼，不能宣稱保留了原始七個 latent 的交接方式。

### 「比 Continuum 一致」目前證據不足

README 的比較對象是 **Echo-Infinity**，重點是開放式故事及場景變化；一小時 Alice 影片是發布者示範。此次讀到的測試涵蓋 request／latent 幾何、fake Diffusers hook、memory 與解析，沒有同條件的 Continuum 人物身份對照。[HyperFlow 模型本身](https://github.com/Video-Rebirth/hyperflow/tree/1dd2f342aba5ab51da02b62885939655e8e268da) 的 base-H3 比較也不能當成 Infinity 對 Continuum 的證據。

若日後比較，至少固定身份原照、分鏡／動作、模型精度、輸出尺寸、片長及預算，分開觀察身份、跨段場景／道具、接點與故事重複率。目前只足以確認它有明確的一致性機制，不足以判定普遍勝過 Continuum。

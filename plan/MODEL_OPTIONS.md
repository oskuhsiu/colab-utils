# H3 模型選項與評價整理

查核日期：**2026-09-23**。這份選擇同時考慮作者規格、Hugging Face 討論、使用者比較，以及能否接入目前的 Colab notebook。**80GB 選項保留；40GB 是量化配置的評估目標，不是所有選項的上限。**

我的建議是：日常先用 **LightX2V 8-step**；試動作與構圖用 **4-step v1.2**；對畫面與音訊要求高的成片，保留原版作比較。這是依目前證據作的選擇，並非我們已完成同場景畫質評測。

## 已接入 notebook 的兩個選單

模型和量化分開選。所有模型選項都是 **FL2VA/T2VA**：文字產片、首圖、尾圖、首尾圖，以及以前片最後一格續接。

| 模型選項 | 固定設定 | 適合用途／取捨 |
| :--- | :--- | :--- |
| **Turbo 8-step v1.0 768p**，預設 | 8 steps、video shift 6、audio shift 3、CFG 1、LoRA strength 1 | 品質與速度平衡的首選；作者 Studio 採用此版本，但不等於每個場景都勝過原版 |
| **Turbo 4-step v1.2 768p** | 4 steps、shift 6/3、CFG 1、strength 1 | 快速預覽；作者主打比 v1.1 改善音訊，視覺細節評價有分歧 |
| **Turbo 4-step v1.0 768p** | 4 steps、shift 6/3、CFG 1、strength 1 | 與 DiffSynth 固定版本的 Turbo 範例一致，保留作對照 |
| **Original 50-step** | 50 steps、shift 12/3、CFG 1、無 LoRA | 已完成大猩猩火箭影片所用的原版基準；最慢 |

設定依據：[ModelTC 規格與 Studio 設定](https://github.com/ModelTC/Minimax-H3-Turbo/blob/02e26d591f7a04d5d1a074c9566d5dd4f22f6225/README.md)、[v1.2 作者公告](https://huggingface.co/lightx2v/Minimax-h3-Turbo/discussions/52)、[DiffSynth Turbo 範例](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/examples/minimax_h3/model_inference_low_vram/MiniMax-H3-FL2VA-Turbo.py)。768p 是訓練版本名稱，下方產片區仍可輸出 480p。

| 權重選項 | 建議 GPU 容量 | 所選元件的磁碟總量 | 選用理由與限制 |
| :--- | :--- | ---: | :--- |
| **BF16 original**，預設 | **80GB 建議** | 134.14 GiB | 保留原始權重。既有 15s/480p 原版實測峰值 72.28 GiB；新增 LoRA 的峰值尚未量測 |
| **INT8 ConvRot pruned** | **40GB 候選；80GB 更有餘裕** | 55.08 GiB | 剪枝 DiT + INT8 文字編碼器；影片／音訊 VAE 保留原版。作為 40GB 的第一個比較選項 |
| **NF4 pruned** | **40GB 候選** | 25.81 GiB | 剪枝 DiT、文字編碼器及 VAE 使用 NF4；下載最小，量化／剪枝的畫質影響仍須實際比較 |
| **NF4 original** | **40GB 候選** | 32.03 GiB | 未剪枝 DiT 的 NF4 版本，提供與剪枝版對照的選擇 |

上述總量包含 processor；Turbo 另加 **1.29 GiB** 原生 LoRA。INT8 的 55.08 GiB **不是必須有 55GB VRAM**：本流程分階段 offload。反過來，NF4 檔案小於 40GB，也不表示 15s/768p 的峰值一定小於 40GB。40GB/80GB 是規劃標示，並非硬性最低容量或成功保證。

量化配方直接對應固定版本的 [INT8 ConvRot 範例](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/examples/minimax_h3/model_inference_low_vram/MiniMax-H3-Int8-ConvRot-Pruned-FL2VA.py)、[NF4 pruned 範例](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/examples/minimax_h3/model_inference_low_vram/MiniMax-H3-NF4-Pruned-FL2VA.py)、[NF4 original 範例](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/examples/minimax_h3/model_inference_low_vram/MiniMax-H3-NF4-FL2VA.py)。

**驗證層級必須分清楚：** 上游分別提供 Turbo 與各量化配方，loader 也支援量化層的 LoRA hot-loading；本 notebook 將它們組合成選單。這些新增組合尚未經本專案 GPU 產片驗證，不能把「上游有各別配方」當成「16 種組合都已測過」。載入時會檢查 LoRA 是否套用到預期的 208 層。來源：[LoRA loader](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/diffsynth/diffusion/base_pipeline.py)、[量化層與 LoRA](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/diffsynth/core/vram/layers.py)。

### 已處理的載入差異

選單不是只替換檔名。原生 LoRA 的訓練比例也必須保留：4-step v1.0 是 `128/128 = 1`，8-step v1.0 與 4-step v1.2 是 `8/128 = 0.0625`，對應使用者 strength 1。notebook 將正確比例傳給 DiffSynth；否則新版 adapter 會被放大 16 倍。依據是實際 header、官方轉換版的 `training_scale`，以及 [LightX2V 原生 loader 的 alpha/rank 公式](https://github.com/ModelTC/LightX2V/blob/4ff8267e7ca09a30dace323f3c024529de7d4a30/lightx2v/models/networks/minimax_h3/lora.py#L152-L160)。記錄：[h3_lora_headers.json](research/h3_lora_headers.json)。

剪枝 Comfy 底模使用 `[QKV, head, channel]` 排列，原生轉換器則產生 `[head, QKV, channel]`。notebook 只對剪枝底模的原生 adapter 重排 QKV 的 B 矩陣輸出列，A 矩陣、MLP 與其他權重不變；已轉換的 adapter 不重複重排。這個轉換已用獨立數值例子檢查，仍需 GPU 產片驗證。[兩種 attention 排列](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/diffsynth/models/minimax_h3_dit_comfy.py)、[原生 LoRA 轉換器](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/diffsynth/utils/lora/minimax_h3.py)。

另外，7 個所選量化權重的 header 已按固定 DiffSynth loader 的 key/shape 演算法核對，全部能對應正確 model class。這不是權重內容 checksum，也不是 GPU 測試。[結構核對紀錄](research/h3_quant_structure_checks.json)。

## 社群評價如何影響選擇

- **LightX2V 8-step vs 4-step：** LegacyV1 的 RTX 6000／480p／15s 比較回報 4-step 56 秒、8-step 107 秒、原版 20-step 191 秒；作者認為 8-step 更接近原版，但 Turbo 仍偏高對比、文字較差，4-step 適合先確認動作。該文 8-step 使用的是較早的非 768p adapter，不能視為我們預設 768p adapter 的直接評測；使用者的 reference 用法也和本 notebook 端點流程不同。[原始貼文與作者回覆](https://www.reddit.com/r/StableDiffusion/comments/1vlo9se/comparing_lightx2vminimaxh3turbo/)。
- **v1.2 音訊更新不是全面勝出：** 2026-09-04 左右的作者公告主打音訊較乾淨；同串有人滿意 0.4MP 的效果，也有人認為頭髮與細節變差。因此保留 v1.0 選項，v1.2 定位為快速預覽。[作者公告與原始回覆](https://huggingface.co/lightx2v/Minimax-h3-Turbo/discussions/52)。
- **4-step 的音訊風險：** 另一個 RTX 4090／15s／1MP 使用者測試，回報 4 次影像和 4 次音訊採樣效果不足，改用較多音訊步數。這是個別 workflow 的觀察，不能直接把設定搬到目前共同步數的 DiffSynth pipeline。[原始測試貼文](https://www.reddit.com/r/comfyui/comments/1vjrlif/minimax_h3_lightx2v_4step_lora_quality_speed/)。
- **有速度數字不代表品質排行：** hffordata 的 2026-09-20 benchmark 有多 prompt／seed、H200 時間與重現資料，但明確沒有視覺品質評分，因此不能據此宣稱某版最好。[原始測試資料](https://huggingface.co/datasets/hffordata/h3-fewstep-benchmark-20260920)。

這些測試使用不同 GPU、解析度、基礎量化、adapter 和框架，**不換算成 A100 Colab 的預期秒數或 CU**。先前原版的 23 分 35 秒也不能直接除以 50、再乘 4，因為下載、文字編碼、offload、VAE 解碼不會等比例縮短。

## 有找到，但未接入這份 notebook 的候選

| 候選 | 值得注意的地方 | 本次未列入可執行選單的原因 |
| :--- | :--- | :--- |
| **Larry v4-600 EMA，6–8 steps** | 作者主打靜態、小動作和細節；推薦 6–8 steps | 需專用雙時間表 sampler，剪枝底模還有時間條件補回邏輯；不能只掛 LoRA。4-step 大幅快速動作可能拖影，對丟火箭場景尤其需比較 |
| **LightX2V Turbo-SLA，4 steps** | 作者回報 RTX 5090 上稀疏注意力可再加速 | 需 SLA/Sage2 的特定設定；本 notebook 沒有該注意力後端，不能把一般 Turbo 載入方式當成 SLA |
| **FastVideo FastH3 VSA preview** | 4-step、VSA 稀疏注意力的完整權重 | 作者驗證預設是 4×B200，且只蒸餾 T2VA；不符合這裡必須保留首尾圖的介面 |
| **FastVideo 社群 ComfyUI port** | 作者在 3090 Ti 24GB 有速度實測 | 明確為實驗性 FL2VA 路線，還需 gate、LoRA、Triton/VSA；其 task 範圍與官方 preview 也不同，不能混作同一套選項 |
| **FP8／NVFP4／GGUF Q6 類版本** | 可以在適合的框架或硬體有用途 | 本次先整合有現成 DiffSynth 配方的 INT8／NF4。沒有把 GGUF 檔塞進 safetensors loader，也沒有將特定 GPU 的低位元加速宣稱套用到 A100 |

候選來源：[Larry 模型卡](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora)、[Larry 專用節點](https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo)、[Turbo-SLA 模型卡](https://huggingface.co/lightx2v/Minimax-h3-Turbo-SLA)、[FastVideo 官方 preview](https://huggingface.co/FastVideo/FastVideo-FastH3-4-step-Preview-v1-VSA-DataFree)、[FastVideo 社群 port 實測](https://github.com/barelymining/ComfyUI-MiniMax-H3-FastVideo)、[Comfy 權重庫](https://huggingface.co/Comfy-Org/MiniMax-H3)。這些仍是可考慮的後續整合，未將它們包裝成已可用的 notebook 模式。

## 硬體與重現資料

**V100 沒有 40GB 版本**；NVIDIA 列出 16/32GB，A100 則有 40/80GB。本 notebook 使用 BF16 計算，檢查 GPU compute capability 與 BF16 支援；量化儲存不會使 V100 自動獲得 BF16 運算能力。[V100 規格](https://images.nvidia.com/content/tesla/pdf/Tesla-V100-PCIe-Product-Brief.pdf)、[A100 40/80GB 與 BF16](https://nvidianews.nvidia.com/news/nvidia-doubles-down-announces-a100-80gb-gpu-supercharging-worlds-most-powerful-gpu-for-ai-supercomputing)、[NVIDIA 支援表](https://docs.nvidia.com/deeplearning/tensorrt/archives/tensorrt-1001/pdf/TensorRT-Support-Matrix-Guide.pdf)。

| 元件 | 固定 revision |
| :--- | :--- |
| DiffSynth-Studio | `7686e54d41d25c0e8ed5f1318acc23b6bb832654` |
| MiniMaxAI/MiniMax-H3 | `42ed227ee7df40d41602854ae760620d6eb651fe` |
| lightx2v/Minimax-h3-Turbo | `3ec17a324ced54151364f24f8b5fb6bf7e26414f` |
| Comfy-Org/MiniMax-H3 | `1c41cfca8ebba91d0af792a05c5761fb2c3a7975` |
| DiffSynth-Studio/MiniMax-H3-NF4 | `363fdc8fbd7ae55f5b9e7fb87cf3d508df28ee0d` |

選中的 46 個公開檔案與大小記錄在 [h3_selected_files.json](research/h3_selected_files.json)；不是權重本身。已查核 16 種選單組合的檔案存在、revision、檔案大小，並讀取三個 LoRA 的 safetensors header：624 個 tensor 的名稱、dtype、shape 相同，符合現有 native LightX2V 轉換器。**結構相符不是畫質或 GPU 成功的證明。**

本次不啟動付費 GPU，不下載整套模型庫。新 runtime 只下載選中的底模、processor 和所選 LoRA；後續同模型產片沿用 pipeline。

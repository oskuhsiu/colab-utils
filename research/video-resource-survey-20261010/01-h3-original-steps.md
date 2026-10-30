# MiniMax-H3 原模型、Turbo 與 4/8 步來源證據

查閱截止：2026-10-10（Asia/Taipei）。本葉只查找 MiniMax-H3 Base、Turbo／其他非 FastH3 的 4/8 步 adapter、原生 ComfyUI、DiffSynth、以及 L4 24GB／A100+High RAM 的公開明示資料。沒有登入、安裝、下載大模型、啟動 GPU 或重建本地環境；沒有把 FastH3 student 當作本報告候選。

## Answer

官方 H3 Base 分成 FL2VA 與 Ref2VA：FL2VA 支援 T2VA 與首／尾幀條件，Ref2VA 支援多模態 reference；兩者是不同 checkpoint。官方模型卡把 Base 稱為 CFG-distilled，沒有把它稱為 step-distilled。Hugging Face Diffusers 的 H3 pipeline 明示每個 denoise step 僅一次 transformer forward、沒有 `negative_prompt` 或 `guidance_scale`；DiffSynth 的同一模型介面則把預設 `num_inference_steps` 寫成 50、`cfg_scale=1.0`、video/audio shift `12.0/3.0`。DiffSynth 原始 pipeline loop 會逐一遍歷 scheduler timesteps；`cfg_scale=1` 只呼叫 positive branch，非 1 才再呼叫 negative branch。

官方 ComfyUI native 文件的 Base workflow 預設 20 steps；T2V/I2V 的 Lightning Turbo 範例是 FL2VA 8-step，R2V 的範例是 Ref2VA 4-step。Comfy 文件把 Ref2VA 的 `match` 與 `max` reference resize、9 images／3 videos／3 audio 上限，以及 Ref2VA／FL2VA 權重分離寫清楚；它只把 `max` 描述為較強 identity fidelity、較慢，未給身份成功率。

ModelTC/LightX2V 的 Turbo 表列多個獨立合約：544p FL2VA 4-step（shift 12/3）、544p FL2VA 8-step（12/3）、768p FL2VA 4/8-step（6/3）、544p Ref2VA 4-step（12/3）。其 ComfyUI workflow 預設 FL2VA 8-step 與 Ref2VA 4-step，並將 4-step 的 4 個 sigma interval 與 video/audio shift 寫出。vLLM-Omni 的表進一步顯示部分 artifact 的 request `num_inference_steps` 是 5 或 9，而 denoiser forward 是 4 或 8；因此 steps 欄位要和實際 forward 次數分開記錄。

HyperFlow 是 Video Rebirth 的另一條明示「data-free flow self-distillation」8-step 路徑，使用官方 Base／VAE／conditioner／三種 workflow；它固定 sigma grid、video/audio shift 12/3，並明示官方 Diffusers 50-point schedule 為 49 model forwards、HyperFlow 為 8。drbaph 的 ComfyUI repository 同時保留 HyperFlow、LightX2V Dynamic-SVD resize、v4 step-600 EMA、checkpoint-500/850 等不同 provenance；其 v4 pruned conversion 明示移除不相容的 51 組 AdaLN pairs，不能假定與原始 full-model LoRA 等同。

## 證據表

| ID | 來源與明示事實 | 資源／任務口徑 | 限制與反向結果 |
|---|---|---|---|
| H3O01 | MiniMax 官方 HF model card：H3-Base-FL2VA 與 H3-Base-Ref2VA 是兩個 task-specific BF16 checkpoint；Base 是 CFG-distilled。FL2VA 是 T2VA／first-last-frame，Ref2VA 是 reference image/video/audio。Ref2VA 上限為 ≤9 images、≤3 videos（各 2–15s、總 ≤15s）、≤3 audio（各 2–15s、總 ≤15s）、混合 ≤12 files。 | 768p Base；4–15s、24 FPS、32kHz stereo；原始 HF repo 同時含 `FL2VA/`、`Ref2VA/`。 | 官方未在此 model card 報單卡 L4、A100 RAM 或端到端耗時；H3-Regenerate-2K 為未開源 API 模組。 | 
| H3O02 | Hugging Face Diffusers 官方 H3 pipeline：video/audio 兩個 scheduler 在單一 packed transformer call 內步進，video shift 12、audio shift 3；guidance 已 baked in，沒有 guider、negative prompt 或 guidance scale；每步恰一次 forward。Ref2VA workflow 的 audio reference 不能是唯一 reference。 | 原始 Base／Diffusers workflow；steps 由呼叫端提供，forward 數按 pipeline 每步一回。 | 官方 Diffusers code page 沒有列 Base 的預設 steps 數；不同 wrapper 的 sigma point／forward 計數要單獨核對。 |
| H3O03 | DiffSynth 官方 H3 文件與 pipeline：NF4 quick start 啟用 VRAM management，文件寫最低 7GB VRAM；範例 480×832、124 frames、50 steps、BF16 compute。介面預設 768×1344、124 frames、50 steps、`cfg_scale=1.0`、video/audio shift 12/3、tiled VAE true、tile 256/64；negative prompt 預設空白但 CFG-distilled 下預設無效。 | GPU 未指定；VRAM 下限 7GB 是文件宣告，不是 L4 成片 benchmark；124 frames @24 FPS 約 5.17s；NF4 weights + CPU offload。 | 文件未報 host RAM、L4/A100 wall time 或品質；7GB 只表示其 VRAM-management path 的最低宣告。 |
| H3O04 | Comfy-Org 官方 native docs：T2V/I2V Base workflow 預設 20 steps；`turbo_mode` 使用 FL2VA 8-step Lightning LoRA，`turbo_steps` 預設 8、LoRA strength 預設 1.0。R2V 使用不同的 Ref2VA weights，預設 20 steps，Lightning LoRA 為 Ref2VA 4-step；文件將其描述為較快但 audio/motion quality 稍低。R2V 最多 9 images、3 videos、3 audio；`match` 依生成面積縮放，`max` 保留至 2048px short edge 並標為較強 identity fidelity、較慢。 | Native ComfyUI；官方 storage example 使用 pruned INT8 ConvRot DiT、NVFP4-AWQ text encoder、INT8 ConvRot video VAE、FP32 audio VAE。 | `quality` 描述是官方 workflow note，不是受控 benchmark；未給 L4/A100 RAM、forward trace 或 identity pass rate。 |
| H3O05 | ModelTC/LightX2V Turbo author repo：FL2VA 4-step v0.1 = 544p、shift 12/3、4 NFE；FL2VA 8-step v1.0 = 544p、12/3、8 NFE（推薦 8/4）；FL2VA 4/8-step v1.0 768p = 1344×768、shift 6/3；Ref2VA 4-step v0.1 = 544p、12/3。作者給出 4 NFE 的 video/audio sigma 例。其 Comfy graphs 預設 T2VA/I2VA 8-step、Ref2VA 4-step；Ref2VA resize 預設 `match`，訓練也使用 `match`。 | Turbo adapter；T2VA/FL2VA 與 Ref2VA 分開任務。Studio 當時使用 FL2VA 8-step 768p、8 NFE、shift 6/3。 | 這是 adapter 作者的 contract／workflow facts；沒有 L4/A100 RAM 或同 seed perceptual benchmark。 |
| H3O06 | vLLM-Omni 官方 H3 recipe 的 artifact table：FL2VA 4-step artifacts 標示 4 forwards、request `num_inference_steps=5`；8-step artifacts 標示 8 forwards、request `num_inference_steps=9`；544p rows 用 video shift 12、768p rows 用 6，audio shift 全為 3。Recipe 會驗證 LoRA artifact 的 steps/shift，不匹配時拒絕 request。 | BF16 LightX2V artifact；FL2VA 與 Ref2VA server／task 分開。 | 這個 wrapper 將 terminal sigma point 算入 request steps；不能直接拿 request 數當 transformer forward 數。Recipe 未給 L4/A100 host RAM。 |
| H3O07 | Video Rebirth HyperFlow：8-step LoRA 以 data-free flow self-distillation 得到，官方 Base weights、VAEs、conditioner 與 `t2va`/`fl2va`/`ref2va` workflow 保留；adapter rank 256/alpha 256、316 modules、約 2.8GB；固定 sigma grid、video/audio shift 12/3。作者寫官方 Diffusers 50-point schedule 為 49 model forwards、HyperFlow 為 8；不得傳 `num_inference_steps`，步數與 grid 由 weights file 決定。HyperFlow 使用專用 `load_hyperflow_lora` 與 TwoTimeEmbedder，不是 generic LoRA，不能直接用 `diffusers.load_lora_adapter`。 | 可用單 GPU auto CPU offload；作者另寫 24GB reserve margin 是在 H200 上驗證的 recipe 條件。 | H200 的 margin 不是 L4 benchmark；49-vs-50 的 wording 是 HyperFlow 對 Diffusers sigma-point wrapper 的計數，與 DiffSynth loop 的 50 timesteps 應保留為 implementation/version boundary；generic loader 不相容是明示限制。 |
| H3O08 | drbaph HF ComfyUI model-author card：HyperFlow 8-step files 來自 Video Rebirth；LightX2V files 是 official LightX2V 4/8-step 的 Dynamic-SVD resize（平均 projection rank 21.724359）；v4 step-600 EMA、checkpoint-500/850 等是另一條 pruned/curve-form conversion。現行 v4 workflow 6–8 steps、Euler、Beta、strength 1.0、video shift 12、audio shift 4–6；8 steps 被該作者標為 motion/audio stability path。其 pruned conversion 從 518 tensors 留 416、移除 102 AdaLN tensors（51 pairs），作者明示不可假定與 intended full-model LoRA 等同。 | ComfyUI pruned base；LightX2V resize files為 BF16。artifact `v4_step600_ema_pruned_comfyui` 約 620MB。 | 這些是 repository 作者的 tested workflow／weight reconstruction facts；數值相似度是 weight reconstruction，不是感知品質分數。4-step 使用 matching LightX2V FL2V/Ref2V workflow，TaoMate 4-step sigma 另列為 experimental。 |
| H3O09 | Alibaba PAI 官方 HF model card：PDD (`MiniMax-H3-FL2VA-Acc-8Step`、`MiniMax-H3-Ref2VA-Acc-8Step`) 是對應 FL2VA／Ref2VA 的 official 8-step Acc LoRA，rank 64、network alpha 64、BF16；同頁 demo 對照 Base 與 Turbo 4-step，權重 1.0。PDD inference 由其 config 推導 NFE，依 VideoX-Fun/ Diffusers ModularPipeline 使用，並要求 `apply_pdd_lora` 與 Diffusers ≥0.40.0。 | FL2VA／Ref2VA 各自 matching base；8-step、joint audio-video。 | model card 未列 L4/A100 RAM、端到端時間或普通 Comfy generic loader compatibility；不能與普通單一 LoRA loader 的結果混為一談，必須保留 PDD head-bank loader boundary。 |
| H3O10 | smhfacct HF model-author card：hybrid 以官方 FL2VA 作 base，從 Ref2VA 擷取後段 `adaln_proj`，提供 b15–49、b20–49、b25–49、b30–49 INT8 variants；作者說這是 tensor-level weight-selection merge，無 additional training/fine-tuning。作者的主張是 b30–49 較接近 FL2VA、b20–49 較偏 reference capability，並明示這是 subjective empirical、可能隨 prompt/reference/settings 改變。 | Pruned INT8-ConvRot base；可作 text/image/video/audio-to-video reference workflow。文件列出的檔案約 21GB 級。 | 沒有獨立 reproduction 或定量 identity/audio benchmark；其 quality/reference tradeoff 只能保留為作者聲明。 |
| H3O11 | Kijai HF experimental card：`ref lora` 是 FL2VA 與 Ref2VA 的 difference，作者明示完全 experimental、尚不知道 use case；PDMD LoRAs 是從 pdmd2026 2NFE/4NFE 轉換並 rank-reduced，DMAD 來自 ZhengmingYu/DMAD；另列 W4A8/W6A8 與 int8-convrot VAE。 | ComfyUI 0.31.0；int8-convrot VAE 需 0.36.0 才有作者所述速度路徑；W4A8/W6A8 precision／work-in-progress。 | 作者沒有給 reference fidelity、audio fidelity、L4/A100 RAM 或 reproducible timing；`ref lora` 的任務能力明確未確認。 |
| H3O12 | NVIDIA SANA official H3 DataCenter page：4× A100 SM80 使用 original BF16 checkpoint、1344×768、124 frames、50 steps、Ulysses-4、no offload、warm batch 1；dense 217.32s、full-opt 61.28s；full-opt peak 49,126 MiB per A100。官方頁未註明 A100 是 40GB 還是 80GB，亦未報 host RAM。 | 多卡 A100；約 5.2s clip、native audio-video；SM80 Triton Sol-Attn。 | 這是高資源 4-GPU benchmark，不能外推單卡 L4 或單卡 A100；memory 是 full-opt peak per GPU，不等於 host RAM。 |
| H3O13 | zenryokukikai first-hand repo：A100 80GB、INT8 ConvRot、Triton、864×480、20 steps、124 frames（5.17s），4.25s/it、總 110s；同頁另列 1344×768 時 16.9s/it。 | 單張 A100 80GB；host RAM 未報；量化／backend 已指定。 | 沒有 text-encode/decode/mux 分項、沒有 host RAM、沒有同條件 BF16／Turbo 4/8 A/B；作者數據只適用該 repo stack。 |
| H3O14 | Marwanto606 first-hand blog（2026-08-10）：Modal A100-80GB + 1TB RAM，ComfyUI 10s、960×544、T2V；作者記錄 VRAM 50.62GB、RAM 100.8GB、生成 307.08s，並列出 INT8 ConvRot DiT、NVFP4 text encoder、FP16/FP32 VAE 與 Turbo LoRA 檔。 | A100 80GB；host RAM 1024GB；10s／960×544；耗時口徑為整次生成，未拆分。這是 Modal 機器規格，不是 Colab High RAM 的驗證。 | 作者明示不同 prompt 時時間上下波動；steps、seed、warm/cold、完整 workflow 未固定報出，作為單一第一手案例保留。 |
| H3O15 | revolverocelot1 first-hand L4 workflow repo：預配置 NVIDIA L4 24GB VRAM／32GB RAM；作者表列 native 15–20 steps T2V/I2V 約 3.5–4.5min、R2V 約 4–5min；Turbo 6 steps T2V/I2V 約 2.5–3min、R2V 約 3–4min；未加速 20 steps 約 12–15min。 | 單張 L4 24GB；host RAM 32GB；INT8 quantization、NVFP4 text encoder、SpeedStack／Turbo。 | 表格沒有解析度、frame count、seed、warm/cold、I/O 分項或影片驗收；repo 也含 NSFW-specific workflow，故只引用硬體／步數／時間欄，不把「100% native quality」當已驗證結論。 |
| H3O16 | MiniMax-AI first-party integration index：24GB first-run stack 列 pruned INT8 ConvRot DiT 19.53GiB + NVFP4-AWQ TE 14.61GiB；原始官方 repo 每個 transformer partition 61.73GiB，整個 original repository 464.2GiB；DiffSynth NF4 path 標 8GB VRAM floor。該頁另寫 FL2VA 通常 raw output 較高、Ref2VA reference inputs 較多但 base quality 較低，Ref Patch 只能「partially bridge」。 | 24GB path 的檔案／component size facts；host RAM 未給。 | 這是 first-party curated index 的明示整理，不是其自身 benchmark；19.53+14.61GiB 是檔案大小，不能直接當 peak VRAM；FL2VA/Ref2VA quality 描述未附受控分數。 |

## 未確認與 search boundary

- 沒有找到官方 MiniMax 在單張 L4 24GB 上、同一 prompt/seed/解析度/片長下，比較 Base 20/50 steps、Turbo 4/8、Ref2VA identity/audio 的端到端 benchmark；L4 數字來自一個社群 workflow repository，解析度／frame count／warm-cold 未報。
- 找到 A100 80GB 的社群實測與 4×A100 官方 NVIDIA benchmark，但沒有找到單張 A100 40GB、且同時報 host RAM／峰值 VRAM／完整輸出時間的官方 H3 原模型 benchmark。A100-80GB blog 的 1TB RAM 是機器規格，實際 RAM use 只有 100.8GB；兩者分列。
- 官方 Base 的「CFG-distilled」不等於「step-distilled」；這裡只保留來源對 Base defaults、forward loop、Turbo/HyperFlow/PDD provenance 的明示，沒有把少步時品質差異寫成因果結論。
- Ref2VA 對 identity、style、motion、camera、voice 的 reference role 在 Comfy docs 中是輸入分工描述；沒有 primary source 量化 identity retention，也沒有證明 `max` 必然優於 `match`。Diffusers code 另外明示 audio reference 不能是唯一 reference。
- 社群 merged／converted／rank-reduced weights（drbaph、smhfacct、Kijai）均保留作者自己的限制；沒有把作者主觀 quality tradeoff 當成跨硬體或跨 workflow 的結論。
- 未查 FastH3 student、未查需要登入的社群貼文全文、未下載任何大模型或影片；4090/5090/H100/GB200 等資料若在來源中出現，只保留為來源邊界，不作 L4/A100 外推。

## Sources

每筆完整 machine-readable source record 在同目錄的 `01-h3-original-steps.json`；以下只列本報告實際讀取的 primary／author pages。

- H3O01 — https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/README.md
- H3O02 — https://github.com/huggingface/diffusers/blob/main/src/diffusers/modular_pipelines/minimax_h3/modular_pipeline.py
- H3O03 — https://diffsynth-studio-doc.readthedocs.io/en/latest/Model_Details/MiniMax-H3.html
- H3O04 — https://github.com/Comfy-Org/docs/blob/main/tutorials/video/minimax/minimax-h3-native.mdx
- H3O05 — https://github.com/ModelTC/Minimax-H3-Turbo
- H3O06 — https://github.com/vllm-project/vllm-omni/blob/main/recipes/MiniMaxAI/MiniMax-H3.md
- H3O07 — https://github.com/Video-Rebirth/hyperflow
- H3O08 — https://huggingface.co/drbaph/MiniMax-H3-Turbo-Lora-ComfyUI
- H3O09 — https://huggingface.co/alibaba-pai/MiniMax-H3-Acc-LoRAs
- H3O10 — https://huggingface.co/smhfacct/Minimax-H3-fl2va-ref2va-hybrid-models
- H3O11 — https://huggingface.co/Kijai/MiniMax-H3-experimental
- H3O12 — https://nvlabs.github.io/Sana/Sol-Engine/H3-DataCenter/
- H3O13 — https://github.com/zenryokukikai/minimax-h3-webui/blob/main/README.md
- H3O14 — https://www.marwanto606.com/2026/08/cara-menjalankan-minimax-h3-di-comfyui-menggunakan-gpu-modal-dot-com.html
- H3O15 — https://github.com/revolverocelot1/ComfyUI-MiniMax-H3-L4-Workflows/blob/main/README.md
- H3O16 — https://github.com/MiniMax-AI/awesome-minimax-h3-integration


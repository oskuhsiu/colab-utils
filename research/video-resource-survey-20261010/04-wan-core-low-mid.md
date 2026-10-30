# Wan 核心模型：低／中資源與加速證據

查核日：2026-10-10（公開 web/HTTP，只讀；未登入、未安裝、未下載權重、未啟動 GPU）。本檔只覆蓋 Wan2.1／Wan2.2 核心 T2V、I2V、TI2V（1.3B、5B、A14B）以及與這些核心權重直接配套的 LightX2V、CausVid、TurboDiffusion、GGUF／FP8／NF4 證據；Wan VACE、Animate、S2V、MultiTalk、SVI、其它模型與框架的完整調查留給其它檔案。L4 24GB、A100 40GB、A100 80GB 分開記錄；RTX 4090/5090 等數據只作原始來源條件，沒有直接外推。

## Answer

官方 Wan2.1 的最低資源核心是 T2V-1.3B：官方卡宣稱 8.19GB VRAM，5 秒 480P 在 RTX 4090 約 4 分鐘，並警告 1.3B 雖可試 720P，但訓練不足使 480P 更穩定（WAN01）。Wan2.1 14B 的 T2V 支援 480P／720P，I2V 分成 480P／720P 權重；官方 Diffusers 範例為 81 frames、16fps，720P flow shift 5、480P flow shift 3，CFG 5（WAN01）。

Wan2.2 A14B T2V／I2V 是兩個約 14B expert：高噪聲 expert 早期負責 layout，低噪聲 expert 後期負責細節；整體約 27B，但每個 denoise step 只啟用約 14B。官方 single-GPU 指令把 T2V／I2V 的 720P 路徑標成至少 80GB，並以 `--offload_model True --convert_model_dtype`（OOM 時再加 `--t5_cpu`）降低記憶體；這不是 4-bit 量化（WAN02）。官方 ComfyUI 14B 原生模板給出實際可重現的雙模型 workflow：FP8-scaled 高／低噪聲檔各 13.31GB，LoRA 各 1.14GB，基礎 20 steps、10+10 split、CFG 3.5；Lightning turbo 開啟時改為 4 steps、2+2 split、CFG 1、Euler/simple、shift 5（WAN03）。

Wan2.2 TI2V-5B 是 dense unified T2V+I2V，官方固定 720P 約 1280×704、24fps，24GB 級 GPU 加 offload／dtype conversion／T5 CPU 可跑（WAN02）。單 A100-SXM4-80GB 的公开 qualification（BF16、121 frames、1280×704、24fps、50 steps、flow shift 5、1TiB host RAM）報 warm server T2V 288.267s、I2V 299.439s，觀測 device peak 分別 27,533MiB／30,333MiB（WAN12）。Wan2.2 TI2V-5B-Turbo 另是一個作者針對 5B 做的 4-step + CFG-distilled checkpoint：121 frames、1280×704、24fps、無 CFG trick，官方 config 的 denoising list 是 `[1000,750,500,250]`（WAN10）。

### 低資源：單張 L4 24GB

目前找到的 L4 直接單卡資料是 GPU Battle 的 Wan2.2 TI2V-5B benchmark：49-frame、1280×704、single stream／batch 1，L4 為 0.15 frames/s，作者明示該卡為 measured；同一測試頁對完整工作路徑宣稱約 18GB VRAM minimum、約 34GB full path、約 38GB system RAM，但未把每張卡的 host-RAM 峰值拆出（WAN14）。這是實際 L4 證據，不能把它改寫成 4090 或 A100 的時間。

一份 Colab notebook wrapper 只作硬體路由說明：T4/L4 對應 TI2V-5B，A100 對應 A14B；它沒有報 L4 的 warm/cold time、peak VRAM、host RAM 或成片品質測試（WAN20）。因此本次在 L4 上沒有找到 A14B 的直接公開成片／時間紀錄，也沒有找到 Wan2.1 1.3B 在 L4 的同條件測量。ComfyUI 官方模板中的 RTX4090D 640×640 測試（FP8-scaled 84% VRAM、首／二次約 536/513s；加 4-step LoRA 89%、約 108/71s）保留作原始條件，不能外推 L4（WAN03）。

### 中資源：單 A100（40GB 與 80GB 分列）

| GPU | 來源明示結果 | 條件 | 證據性質 |
|---|---|---|---|
| A100 80GB SXM4 | Wan2.2 TI2V-5B T2V/I2V：1280×704、121 frames、24fps、50 steps、CFG 5、flow shift 5；T2V 288.267s／27,533MiB，I2V 299.439s／30,333MiB；host 1TiB，warm server，未使用 CPU offload。| 單 GPU、BF16、native FlashAttention、VAE tiling。| 社群 vLLM-Omni qualification，附 MP4 ffprobe 與完整解碼檢查（WAN12）。 |
| A100 40GB | Wan2.2_Accelerate 文件給的 expected profile：`--offload_model True --compile --compile_mode reduce-overhead --use_batched_cfg --tf32`，81 frames、1280×720 約 120s，預期 2.5–3× speedup。| 文件未提供實測 log、steps／scheduler／host RAM，且目前只優化 T2V。| 明示 expected，不當作測得的 A100 40 結果（WAN13）。 |
| A100 40GB／80GB | GPU Battle 的 TI2V-5B 49-frame、1280×704、batch 1 表：A100 40GB SXM4 0.66 frames/s、A100 80GB SXM4 0.66；A100 40GB PCIe 0.61、A100 80GB PCIe 0.61。作者把 SXM4/PCIe A100 40GB rows 標成 estimated，把 80GB rows 標成 measured。| 該站自述 BF16、warm-up + 2 timed runs、single-stream；host RAM 只在 workload 層面寫約 38GB。| 保留 measured／estimated 標籤；A100 40GB 不能寫成實測（WAN14）。 |

**主代理核查後另列的高資源資料：** WAN11 的 A100-SXM4-80GB serving table 使用 CFG parallel 2、Ulysses 2、TP 1、HSDP on；480P 3 steps 為 21.6810–24.6766s，720P 6 steps 為 117.44–124.6639s。官方 [parallel configuration constraints](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/feature_compatibility/)（WAN22）要求 GPU 數為 Ulysses×Ring×CFG×TP；按該表參數、其餘 degree=1 推得 **4張 GPU**。benchmark 頁面只列 GPU 型號、未直寫卡數，但其設定不支持將數字稱為單 A100 跑分。這是主代理依官方公式作的資源判讀，列高資源旁證；3／6步的 throughput test 亦未附成片品質驗收。

### 雙 expert 邊界與少步契約

- Wan2.2 官方的 expert switch 是 SNR-based：初始高噪聲時用 high-noise，當 `t < t_moe`（對應半個 `SNR_min`）切至 low-noise；它不是 token router（WAN02）。
- ComfyUI 官方 14B template 的 base path 預設 20 steps，split 10/10；base CFG 3.5；template 的工作尺寸預設 640×640×81、5 秒、16fps。啟用 Wan2.2 Lightning LoRA 後預設 4 steps、split 2/2、CFG 1、Euler／simple、shift 5，且 high／low LoRA strength 各 1（WAN03）。
- LightX2V 的 Wan2.1 4-step CFG-distill config 明示 `infer_steps=4`、`denoising_step_list=[1000,750,500,250]`、`sample_shift=5`、`sample_guide_scale=6`、`enable_cfg=false`、LoRA strength 1；它另說 CFG 開啟會做正／負 prompt 兩次而增加時間（WAN05）。
- LightX2V Wan2.2-Lightning 作者宣稱 4 steps、無 CFG trick、約 20× speed-up，並提供 T2V/I2V high／low pair；V1.1 的原生 Comfy JSON、Kijai JSON、MP4 demo 都公開。作者同時保留反例：極大動作可能出 artifact，車輛方向有時反轉（WAN04）。
- TurboDiffusion 的 Wan2.2 I2V A14B runner 是另一套 checkpoint／attention／rCM contract：1–4 steps，default 4；high/low model boundary default 0.9；sigma_max default 200；SageSLA top-k default 0.1、作者建議 0.15；`--ode` 較 sharp 但較不 robust；量化 checkpoint 要 `--quant_linear`，>40GB GPU 建議 unquantized、移除該 flag（WAN09）。
- CausVid 官方 Wan2.1 1.3B repo 是 autoregressive／bidirectional 3-step 5-second workflow；訓練 config 的 timestep shift 8、real guidance 3.5、denoising list `[1000,757,522,0]`，但這是訓練／model config，不等同 Comfy LoRA strength 或 inference CFG。LightX2V 的 Wan2.1 14B CausVid card 寫 9-step distillation、每 segment 約 5 秒，沒有 L4/A100 inference timing（WAN07、WAN08）。

### LoRA、量化與品質聲明

Wan2.1 與 Wan2.2 LoRA 不能因為架構同家族就視為普遍相容。LightX2V 文件把 `Wan2.1-Distill-Loras` 與 `Wan2.2-Distill-Loras` 分成兩個來源，且 Wan2.2 需要 high／low 各自的 LoRA、每個 expert 單獨配置（WAN05）。Kijai 的 wrapper issue 回覆說，他快速嘗試把 Wan2.2 LoRA 從 Wan2.1 直接抽取／套用沒有成功，推測沒有直接從 2.1 訓練；同一討論中其它作者說 LightX2V LoRA 能工作的原因是延續訓練。這是相反的實作者證據，不能合併成「所有 2.1 LoRA 都能套 2.2」（WAN18）。官方 Comfy template 使用 Wan2.2 專用 high／low LoRA；這是已核對的配套路徑。

量化格式也不能混稱：官方 `--convert_model_dtype` 只是把參數轉成 config dtype；LightX2V 的 BF16／FP8／INT8 4-step files 分別約 28.6GB／15GB／15GB，FP8/INT8 需對應 quantized loader／scheme；Comfy repack 的 FP8-scaled high／low expert 各 13.31GB（WAN02、WAN03、WAN05）。city96 的 Wan2.1 T2V GGUF 是直接轉換，提供 Q3_K_S 6.99GB 至 Q8_0 15.9GB、BF16/F16 29.1GB，但 card 沒有其自身的質量測量或比較（WAN15）。bullerwins 的 Wan2.2 I2V GGUF 明示一定要同時下載 high／low，Q2_K 5.3GB 至 Q8_0 15.4GB 每個 expert，同樣沒有 controlled quality claim（WAN16）。第三方 lopho NF4 card 只標示 bitsandbytes／NF4／4-bit 與 base model，沒有 L4/A100、VRAM、速度或 quality acceptance test（WAN19）。

### 有明確 output／workflow 的來源

- 官方 ComfyUI T2V workflow JSON：[video_wan2_2_14B_t2v.json](https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_wan2_2_14B_t2v.json)；I2V：[video_wan2_2_14B_i2v.json](https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_wan2_2_14B_i2v.json)。前者保存了 640×640×81、16fps、5 秒、20-step base 與 4-step Lightning toggle、模型／LoRA URLs 及 RTX4090D test note（WAN03）。
- LightX2V Wan2.2 Lightning 的 T2V/I2V 原生 Comfy JSON 與 demos 在 [model-author repo](https://github.com/ModelTC/LightX2V-Wan2.2-Lightning)；README 另列 [v1.1-v250928 對比 MP4](https://huggingface.co/lightx2v/Wan2.2-Lightning/blob/main/Wan2.2-T2V-A14B-4steps-lora-250928/v1.1-vs-250928.mp4)、I2V/T2V demo MP4 和極大動作 badcase MP4（WAN04）。
- CausVid 官方 repo 的 3-step autoregressive／bidirectional commands 在 [tianweiy/CausVid](https://github.com/tianweiy/CausVid)，WAN2.1 14B CausVid card 的 model／script 在 [HF card](https://huggingface.co/lightx2v/Wan2.1-T2V-14B-CausVid)（WAN07、WAN08）。
- TurboDiffusion repo 提供 Wan2.1 1.3B/14B 與 Wan2.2 I2V high/low checkpoint links、runner、4-step sample command與 output demos；其性能圖是單 RTX5090，不能視為 L4/A100 測量（WAN09）。
- Wan2.2 TI2V-5B-Turbo 作者 repo 有 `i2v_fewstep.sh`、121-frame 24fps demo prompts 與 `wan22.yaml` step list；沒有公布單 L4/A100 wall-time（WAN10）。

## Unknown / Search boundary

- 沒有找到同一 prompt／seed／resolution／frames／precision／VAE 下，Wan2.1 1.3B、Wan2.1 14B、Wan2.2 A14B、TI2V-5B 在單 L4 24GB 與單 A100 40/80GB 的完整 cold+warm paired quality／time／VRAM／host-RAM benchmark。L4 目前只有 TI2V-5B 的 GPU Battle 49-frame throughput；A10080 有單 GPU／1TiB host 的 TI2V qualification，A10040 多為 expected 或 estimated。WAN11 A14B serving 數字按 parallel degrees 屬多 GPU，不是本次單卡中資源證據。
- 官方 Wan2.2 computational-efficiency table以圖片嵌入 README；本檔不把未直接讀取的圖片表格值當作一手數字，另以可讀的 vLLM、TI2V qualification、GPU Battle、LightX2V benchmark 記錄。二手頁面轉述的官方 A14B 41.3GB／59.8GB peak 與 785.7/2735.7s 不當作主要證據。
- 沒有找到 Wan2.2 A14B 的官方／作者 L4 native run；「24GB with offload」多是 Comfy／GGUF／第三方路徑，不能與官方 80GB command 等同。
- 沒有找到 Wan2.2 TI2V-5B-Turbo 在 L4 或 A100 上的作者 wall-time、peak VRAM、host RAM 或 controlled visual comparison；作者只明示 4-step／121f／24fps／1280×704／無 CFG trick。
- 沒有找到 NF4 Wan 核心模型的第一手 L4/A100 video quality comparison；NF4 card 多只提供量化檔案與 loader tags。GGUF Q2–Q8、FP8-scaled、INT8、NF4 的 bit 數不能直接當成畫質排序。
- 不能由參數量、模型版本號、少步數或量化 bit-width 單獨推出畫質更好／更差；本檔保留作者「on par／sometimes better」與「extreme motion artifacts／vehicle direction reversal」、Kijai 2.1→2.2 相容性失敗等相反或限制證據。

## Sources

WAN01 — [Wan-Video/Wan2.1 README](https://raw.githubusercontent.com/Wan-Video/Wan2.1/main/README.md)（官方；8.19GB、1.3B 480P、1.3B 720P instability、14B task/resolution、Diffusers flow shift/CFG；checked 2026-10-10）。

WAN02 — [Wan-Video/Wan2.2 README](https://raw.githubusercontent.com/Wan-Video/Wan2.2/main/README.md)（官方；A14B MoE/SNR boundary、80GB command、TI2V-5B 24GB/720P/24fps、5s under 9min、`convert_model_dtype`/offload flags；checked 2026-10-10）。

WAN03 — [Comfy-Org native Wan2.2 T2V workflow](https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_wan2_2_14B_t2v.json) 及 [I2V workflow](https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_wan2_2_14B_i2v.json)（官方 Comfy workflow；model/LoRA sizes、640×640×81、16fps、20→4 steps、CFG 3.5→1、RTX4090D note；checked 2026-10-10）。

WAN04 — [ModelTC/LightX2V-Wan2.2-Lightning README](https://raw.githubusercontent.com/ModelTC/LightX2V-Wan2.2-Lightning/main/README.md)（模型作者；4-step/no-CFG/x20 claim、V1/V1.1/0928 dates、workflow JSONs、demos、extreme-motion limitation；checked 2026-10-10）。

WAN05 — [LightX2V model structure and loading guide](https://raw.githubusercontent.com/ModelTC/LightX2V/main/docs/EN/source/getting_started/model_structure.md) 及 [Wan21-14B guide](https://raw.githubusercontent.com/ModelTC/LightX2V/main/examples/BeginnerGuide/EN/Wan21-14B.md)（模型作者；Wan2.1/2.2 LoRA separation, 4-step schedules, CFG/offload, BF16/FP8/INT8 files and H100 reference; checked 2026-10-10）。

WAN06 — [LightX2V benchmark source](https://github.com/ModelTC/LightX2V/blob/main/docs/EN/source/getting_started/benchmark_source.md)（模型作者；H200/RTX4090 Wan2.1 I2V 480/720 benchmarks, 40-step and distilled 4-step times/VRAM, 81f; not L4/A100; checked 2026-10-10）。

WAN07 — [tianweiy/CausVid repo](https://github.com/tianweiy/CausVid) 及 [causal config](https://raw.githubusercontent.com/tianweiy/CausVid/master/configs/wan_causal_dmd.yaml)（原作者；Wan2.1 1.3B, 3-step commands, 480×832×81/16fps dataset contract, shift 8/config denoising list, no low/mid GPU timing; checked 2026-10-10）。

WAN08 — [lightx2v/Wan2.1-T2V-14B-CausVid card](https://huggingface.co/lightx2v/Wan2.1-T2V-14B-CausVid)（模型作者；9-step distillation, 81-frame ~5s segments, inference via LightX2V; no GPU timing; checked 2026-10-10）。

WAN09 — [thu-ml/TurboDiffusion README](https://raw.githubusercontent.com/thu-ml/TurboDiffusion/main/README.md)（原作者；Wan2.1/2.2 checkpoint families, 1–4 steps, Wan2.2 boundary .9, sigma_max 200, SageSLA top-k, ODE quality caveat, 5090-only evaluation; checked 2026-10-10）。

WAN10 — [quanhaol/Wan2.2-TI2V-5B-Turbo](https://huggingface.co/quanhaol/Wan2.2-TI2V-5B-Turbo), [few-step script](https://raw.githubusercontent.com/quanhaol/Wan2.2-TI2V-5B-Turbo/main/running_scripts/inference/Wan2.2/i2v_fewstep.sh), [config](https://raw.githubusercontent.com/quanhaol/Wan2.2-TI2V-5B-Turbo/main/configs/inference/wan22.yaml)（模型作者；4-step CFG-distilled TI2V-5B, 121f/24fps/1280×704/no CFG trick, `[1000,750,500,250]`, no L4/A100 inference timing; checked 2026-10-10）。

WAN11 — [vLLM-Omni Wan2.2 T2V A14B serving performance](https://github.com/vllm-project/vllm-omni/blob/main/benchmarks/diffusion/performance_dashboard/wan_2_2_serving_performance.md)（作者 benchmark；A100-SXM4-80GB, 480/720 workload rows, measured serving latency and parallel settings; checked 2026-10-10）。

WAN12 — [vLLM-Omni Wan2.2 TI2V-5B A100 qualification](https://github.com/wiseyak-core/wiseyak-vllm-omni/blob/main/recipes/Wan-AI/Wan2.2-TI2V-5B-A100.md)（作者 qualification；A100-SXM4-80GB, host 1TiB, BF16 121f 720P/24fps 50 steps, warm HTTP times, peak VRAM, MP4 ffprobe; checked 2026-10-10）。

WAN13 — [Wan2.2_Accelerate optimization guide](https://github.com/msiraga/Wan2.2_Accelerate/blob/main/OPTIMIZATION_GUIDE.md)（作者 guide；A100 80/40 expected flags and times, explicit expected/unmeasured status, T2V only; checked 2026-10-10）。

WAN14 — [GPU Battle Wan2.2 TI2V-5B benchmark](https://gpubattle.com/guides/wan-2-2-5b-gpu-benchmarks)（作者 first-party benchmark；49f/1280×704/batch1, L4 and A100 rows with measured vs estimated labels, workload RAM statement; checked 2026-10-10）。

WAN15 — [city96 Wan2.1 T2V GGUF](https://huggingface.co/city96/Wan2.1-T2V-14B-gguf)（量化作者；direct conversion, Q3_K_S–Q8_0/BF16/F16 file sizes, no quality benchmark; checked 2026-10-10）。

WAN16 — [bullerwins Wan2.2 I2V A14B GGUF](https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF)（量化作者；paired high/low requirement, Q2_K–Q8_0 file sizes, ComfyUI-GGUF workflow, no controlled quality benchmark; checked 2026-10-10）。

WAN17 — [Kijai WanVideo_comfy card](https://huggingface.co/Kijai/WanVideo_comfy)（實作者；CausVid LoRA extraction caveats: v1 motion/adverse flashing, v1.5 first-block change, v2 attention-only and more steps/CFG; checked 2026-10-10）。

WAN18 — [Kijai wrapper issue #894](https://github.com/kijai/ComfyUI-WanVideoWrapper/issues/894)（實作者討論；direct 2.1↔2.2 LoRA extraction attempt failed／LightX2V works after extended training claim；conflicting evidence retained；checked 2026-10-10）。

WAN19 — [lopho Wan2.2 T2V NF4 card](https://huggingface.co/lopho/Wan2.2-T2V-A14B-Diffusers_nf4)（第三方 model author；NF4/bitsandbytes/4-bit labels and base link only; no low/mid hardware or quality result; checked 2026-10-10）。

WAN20 — [epg900 Wan2.2 Colab wrapper](https://github.com/epg900/wan2.2)（社群 notebook；A100 recommended for A14B, T4/L4 for TI2V-5B, ~10GB download; no direct timing/VRAM/quality measurements; checked 2026-10-10）。

WAN21 — [Wan2Lab TI2V-5B hardware record](https://github.com/soomrenald/wan2lab/blob/main/docs/wan2.2-ti2v-5b-hardware.md)（社群 first-hand AMD gfx1200 record, 17GB reported VRAM; 5f/121f timing and VAE tile OOM/retry, out of requested NVIDIA L4/A100 scope; checked 2026-10-10）。

WAN22 — [vLLM-Omni feature compatibility：GPU count constraints](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/feature_compatibility/)（官方；GPU count 為 enabled parallel degrees 的乘積，VAE parallel group 不增加獨立卡數；主代理查核 WAN11 使用）。

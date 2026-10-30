# 替代 Comfy 的影片推論框架／優化工具

查核日：2026-10-10。只讀公開網頁、原始 repo、官方文件與少量可讀的第一手社群報告；未登入、未安裝、未下載權重、未啟動 GPU。低資源口徑是單 L4（24GB）；中資源口徑是單 A100 + High RAM，A100 40GB／80GB 分列；主機 RAM、磁碟和 offload 分開記錄。多卡、Blackwell-only、H100/5090 或 1TiB RAM 的數據只作旁證，不外推成 L4/A100 Colab 結果。

## 直接答案與候選邊界

| 框架／工具 | 已讀 exact model／task | L4 24GB | 單 A100 40GB | 單 A100 80GB | host RAM／disk／offload | backend／quant／fallback | 已讀實測或失敗 |
|---|---|---|---|---|---|---|---|
| **Wan2GP** | Wan 2.1/2.2、MiniMax H3 FL2VA／Ref2VA、LTX-2、Hunyuan 1/1.5、LTXV；T2V/I2V/Ref/audio 路線依模型 | H3 文件只有泛化低 VRAM 聲稱；未見 L4 實測 | 未見 | 未見 | Profile 1–5；Profile 4／4+ 逐 block 搬移，reserved/pinned RAM；預設 MMGP VRAM spill 可溢出到 system RAM；無明示 disk benchmark | INT8／FP8／GGUF／NVFP4；Sage/Sage2/Flash/SDPA；compile 需 Triton；H3 Sol-Attn 只列 RTX40/50、H100/H200、B100/B200 | H3 5–6GB VRAM／5s 124f、8–9GB／15s 832×480 是作者聲稱，不是指定 GPU timing；H3 VAE allocator 省約 5.4GB（1920×1088/241f）／1.5GB（1280×720/241f） |
| **DiffSynth-Studio** | MiniMax-H3 FL2VA／Ref2VA／Retake、LTX-2.3／2.5 的 T2AV/I2AV/A2V/Retake、Wan 系列 | 未見 L4；官方 H3 NF4 最低 7GB VRAM 是 runtime 聲稱，不是 L4 qualification | 未見 | 未見 | H3/LTX 範例用 CPU parameter offload 與 dynamic `vram_limit`；NF4＋disk offload 的 Colab 是社群 notebook；ModelScope/HF cache 需磁碟 | bitsandbytes NF4、Comfy-Kitchen INT8（需 `diffsynth[quant]`）；tiled VAE；H3 FL2VA/Ref2VA 權重與 encoder/VAE 檔案需 matching | Colab G4：480×832/124f/50 steps 成功；free T4：448×256/56f/12 OOM、320×192/39f/8 OOM、320×192/22f/6 在 50% OOM，288×160/22f/6＋VRAM limit 9GB＋disk 完成但作者稱不可用；沒有 wall time |
| **FastVideo** | Wan 1.3B/14B、Wan2.2 TI2V-5B/A14B/S2V、LTX-2/2.3/2.5、Hunyuan、MiniMax H3 T2VA/FL2VA/Ref2VA、FastH3 V1/V2 | 支援矩陣列模型／optimization，但沒有 L4 實測；FP8 在 sm<89 自動 BF16 dequant fallback | 未見 H3／FastH3 單 A100 timing | 未見 | `dit_cpu_offload`、`dit_layerwise_offload`、text encoder／VAE offload、pinned CPU；H3 `lazy_module_load`／`h3_sequential_load`；disk reload 證據只在 lazy path 說明 | VSA、Sage、Flash、SLA/SLA；FastH3 V1 是 VSA 90% sparse tile64、4 forwards，V2 是 8-forward 80% VSA；STA full path archived 且 Hopper-only；FP8 hardware path 要 sm89+，舊卡 BF16 fallback；torch.compile 只編 DiT，不編 text encoder/VAE | FastH3 V1 官方速度只給單 Blackwell「up to 14×」及 8×B200 15s 768p<13s；H3 recipe 明示 CUDA full examples 預設 4 GPU且未聲稱 memory minimum；無 L4/A100 timing |
| **LightX2V** | Wan2.1 T2V/I2V、Wan2.2；MiniMax-H3 T2AV/I2AV/L2AV/FL2AV/Ref2AV | 未見 L4 | 未見 | 未見 H3；Wan 只有 H100 | H3 一卡 BF16 model CPU offload、text encoder/VAE offload、AdaLN cache；`offload_granularity=model`；124f/544×960、29 steps；Sol config 362f/768×1344 是單卡但 GPU 未指定 | SageAttention2、SGL kernels；FP8/INT8 quant；LoRA dynamic apply 對 quantized DiT required；compile configs `warmup:true`；FP8 VAE encoder mode 要 SM120 | Wan2.1 H100 single-GPU author timing：T2V BF16 278.9s/43,768MiB，4-step FP8 22.0s/31,032MiB；offload T2V 319.0s/34,932MiB，FP8 58.9s/21,290MiB。這是 H100，不外推 L4/A100 |
| **SANA Sol Engine／Sol-Attn** | MiniMax-H3 T2VA/I2VA/Ref2VA；H3 full-stack inference | 未見 | **超出單卡** | **超出單卡** | 官方 H3 4×A100 無 offload；49,126MiB/GPU | A100 SM80 用 portable Triton；H100 SM90 用 CuTe；shared policy first 10 steps/first 2 layers dense、Sol-Attn route density 18.04%、FirstBlockCache reuse 67.35% | 4×A100、1344×768/124f/50 steps、warm batch1：dense 217.32s，full-opt 61.28s，3.55×；同 prompt/seed/topology；不得當單 A100 結果 |
| **SGLang Diffusion** | MiniMax-H3 T2VA/FL2VA/Ref2VA、Wan、Hunyuan；OpenAI-compatible `sglang serve/generate` | 文件有 4090／12GB emulation，不是 L4；單卡 24GB recipe 是 4090 | 未見 | 未見 H3 單 A100 | H3 layerwise offload；consumer recipe 需 host RAM；docs 以 12GB VRAM＋32GB host 與 16GB＋116.7GB pinned host 作測量；VAE layerwise 會重播 9GiB×167 tiles，故 recipe 排除 VAE | ConvRot INT8 在 CC8.9 走 Comfy-Kitchen、CC9/10/12 用 SGLang JIT；W4A8/W4A4 需 Comfy-Kitchen；NVFP4 要 compute capability 10+；Cache-DiT/TaylorSeer/SCM；H3 compile 會改 numerical output，lossless preset 不啟用 | 12GB hard-cap、864×480/124f/20 NFE、warm：Recipe A 235s（32GB host）、218s（48GB）、180s（64GB）；Recipe B 120.92s，需 16GB VRAM cap＋116.7GB pinned host；非 L4/A100，且 host cap 是 emulation |
| **vLLM-Omni** | Wan2.1/2.2 T2V/TI2V/I2V、LTX-2/2.3/2.5、SANA-Video 2B、MiniMax H3（FL2VA row） | 未見 | 未見 | Wan2.2 TI2V-5B 有單 A100-SXM4-80GB qualification | vLLM feature matrix 列 layerwise/module CPU offload、FP8/INT8/GGUF、VAE tile；A100 recipe 無 CPU offload、host 1TiB（超出 High RAM典型未知） | Cache-DiT/TeaCache、Ulysses／CFG／TP/HSDP；OpenAI-compatible Videos API；LTX H800 benchmark compile/cache 需分開看 | 單 A100 80GB Wan2.2 TI2V-5B、1280×704/121f/24fps/50 steps BF16：T2V 288.267s、27,533MiB；I2V 299.439s、30,333MiB；host 1TiB，warm steady-state，非 Colab High RAM qualification |

## 模型／任務與可重現入口

- **Wan2GP**：README 的 video matrix 明列 Wan 2.1/2.2、H3、LTX-2、Hunyuan 1/1.5、LTXV。CLI 可 `python wgp.py --process queue.zip`，server/API 可 Gradio／MCP；`--profile 4 --attention sdpa` 是低 VRAM fallback，`--compile --attention sage2 --profile 3 --preload 2000` 是作者的 high-performance example。H3 FL2VA／Ref2VA 的 audio/reference 能力和 33B/full、20B/pruned 需按 matching variant 使用。
- **DiffSynth-Studio**：H3 official example 固定 480×832、124f、50 steps、24fps，四個 NF4 component 分開載入；`vram_limit=torch.cuda.mem_get_info(...)-2`。H3 model table 明列 FL2VA／Ref2VA／Retake、pruned／INT8 ConvRot／FP8／NF4 與 LightX2V 4-step entries。LTX-2.3 example 是 1024×1536、121f、two-stage，並列 one/two/distilled T2AV、I2AV、A2V、Retake、IC-LoRA。
- **FastVideo**：support matrix 的 canonical registration 是 commit `8d89f30d`；Wan2.2 TI2V-5B 720p，LTX-2.3/2.5 T2V/I2V，H3 T2VA/FL2VA/Ref2VA。注意 Wan-VACE 在 `main` 明示未支持，LTX-2.5 gated split files 需先轉成 FastVideo component layout。
- **LightX2V**：H3 five scripts 是 one-GPU BF16＋model CPU offload＋124f/544×960；`run_minimax_h3_{t2av,i2av,l2av,fl2av,ref2av}.sh` 是完整入口。量化 INT8/FP8 DiT 與 LoRA contract 不能混用：quantized DiT 必須 dynamic LoRA apply，merge unsupported。H3 CPU offload 要先生成 matching AdaLN cache，cache 不匹配會拒絕。
- **SGLang／vLLM-Omni**：兩者都提供 server/API 路徑。SGLang H3 docs 明列 H3 weight formats、attention backend、layerwise offload 與 Cache-DiT；vLLM-Omni docs 的 model/feature tables 明列 Wan、LTX、SANA、H3 與 offload/quant/cache/parallel support。API 可保存 MP4、返回 timing/header，適合後續做同條件測試。

## Backend、精度、SM eligibility 與 fallback

1. FastVideo 的 FP8 文件是最清楚的 target-band eligibility 證據：硬體 FP8 compute 要 `sm89+`；低於 sm89 自動走 BF16 dequant path。L4 是 sm89，A100 是 sm80；按文件 eligibility，A100 應記為低於 native FP8 gate 的 fallback 情形，實際 loader／kernel 仍需 runtime 檢查。
2. FastVideo H3 VSA / FA4 gate 比較嚴：MiniMax-H3 VSA 的 inference-only `sm_100a` tile-64 route 不支援舊 GPU時會保持 transformer eager；FA4 在 sm90 以下部分 attention 退回 FA2，但設 `FASTVIDEO_FA4=1` 且不可用時會 loud failure。這些是 fallback／failure contract，不是速度推算。
3. LightX2V ordinary H3 config 是 BF16＋SageAttention2＋SGL；FP8 VAE encoder mode 要 converted weights 和 SM120。SGLang H3 quant table 明列 NVFP4 需 compute capability 10.0+，W4A8/W4A4 需 Comfy-Kitchen；因此不能把 Blackwell NVFP4 文件當 L4/A100 native path。
4. Wan2GP H3 Sol-Attn 文件只列 BF16、Triton 3.6+ 與 RTX 40/50/H100/H200/B100/B200；未列 L4/A100，SDPA 是兼容 fallback。Sage2 需 Triton＋SageAttention 2.x＋RTX 30XX 或更新，涵蓋 Ampere，但作者的「40% faster」沒有 target-band benchmark。
5. vLLM-Omni 的 feature matrix 顯示 H3 有 TeaCache（FL2VA）、Cache-DiT、SP、DiT/TE quant、layerwise offload、VAE tile；LTX-2/2.3/2.5 的支持欄位不同，LTX-2.5 Cache-DiT 是 one-stage 受限／部分未驗證，不能把 LTX-2.3 旗標移植成 LTX-2.5 保證。

## 實測、cold/warm、cache/compile 與失敗紀錄

| 證據 | 條件 | 明示結果 | 不能推出 |
|---|---|---|---|
| DiffSynth Colab | G4、480×832、124f、50 steps；T4 約14.56GiB，disk offload | G4 完成；T4 448×256/56f/12 OOM、320×192/39f/8 OOM、320×192/22f/6 在 bitsandbytes dequant OOM、288×160/22f/6＋VRAM limit 9GB 完成 | 未給 G4/T4 wall time、host RAM、disk throughput；T4 結果不是 L4 |
| LightX2V Wan21 | single H100；官方 beginner guide、`watch nvidia-smi` | T2V BF16 278.902s/43,768MiB；4-step FP8 22.000s/31,032MiB；model-offload BF16 319.020s/34,932MiB；offload FP8 58.922s/21,290MiB | H100-only；prompt/resolution/frames metadata未在同頁完整重述，不能對照 A100/L4 |
| Sol Engine | 4×A100、1344×768、124f、50 steps、warm batch1、Ulysses4、無 offload | dense 217.32s→full-opt 61.28s；peak 49,126MiB/GPU；A100 kernel 是 Triton SM80 | 多卡高資源；不能除以4外推單卡，也沒有 A100 40GB |
| vLLM-Omni community qualification | 1×A100-SXM4-80GB、1TiB host、BF16、native FlashAttention/eager、VAE tiling、warm | 720p TI2V-5B T2V 288.267s/27,533MiB；I2V 299.439s/30,333MiB；MP4 121f/24fps 5.041667s | host 1TiB 超出本調查 High RAM 未知；不代表 A100 40GB 或 L4 |
| SGLang H3 consumer emulation | 12GB hard cap＋32/48/64GB host vs 16GB cap＋116.7GB pinned；864×480/124f/20 NFE | warm request A=235/218/180s；B=120.92s；docs稱 output verified | 不是實體 L4/A100，psutil/allocator 是測量 emulation；不是 50 steps/720p |
| vLLM LTX-2 H800 | 480×768/41f/20 steps | baseline 10.3s；compile warm 約10.3s但 first request +6s；Cache-DiT 7.4s avg、lossy；4-GPU Ulysses＋Cache-DiT 4.7s avg | H800、多卡和短片；不能外推單 L4/A100 |
| LightX2V V100 TP4 | 4×V100 32GB、256GiB RAM、precomputed text conditioning、hot DiT | 864×480/124f：load 25.11s、hot DiT 49.73s、VAE 43.93s、fresh two-phase 119.10s；1344×768/362f OOM | 高資源多卡、排除了 live text encoder；不是 target-band |

## 版本／維護與依賴

- 初始INF01讀到的是 `extreme2k/Wan2GP` fork，API顯示其parent是`deepbeepmeep/Wan2GP`、最後push為2026-08-07，故v12.434（2026-08-06）是該fork的snapshot；主代理另讀canonical `deepbeepmeep/Wan2GP`，其README最新列v13.141（2026-09-29）、API最後push2026-10-07（INF18），兩者不合併成同一版本。最新條目含 First Block Cache、Sol-Attn、H3 W4A8 與 lower-RAM Video VAE。CLI 文件則標示 PyTorch 2.3+（VRAM allocator）和 PyTorch 2.6–2.15（RAM allocator）支援範圍；實際 wheel/CUDA 仍需鎖定。
- DiffSynth README 的更新條目有 LTX-2.5（2026-09-10）、MiniMax-H3（2026-08-03）、quantization backend（2026-08-19）、CPU offload training（2026-05-18）；H3 Colab 實測額外需要 `av` 與 `bitsandbytes`。這些是 source/firsthand environment facts，不是本報告的安裝建議。
- FastVideo README 的更新條目有 FastH3 V2（2026-09-15）、FastH3 V1（2026-08-27）、FastWan-QAD（2026-06-23）；CUDA 安裝文件列 CUDA 12.6/13.0，DGX Spark 用 CUDA 13。FastH3 CUDA profile 的官方 recipe 以 4 GPU 為預設，performance profile 實測是 4×GB200。
- LightX2V README 建議 Docker；H3 Git install 是 `pip install -v git+https://github.com/ModelTC/LightX2V.git`。Sage/SGL/quant kernels 依 JSON／device matching，H3 AdaLN cache 會另佔 disk。
- SGLang Diffusion 安裝文件提供 `uv pip install "sglang[diffusion]" --prerelease=allow`、source 與 Docker；vLLM-Omni recipe 使用 vLLM 0.28.0 CUDA 12.9 wheel（A100 qualification），需 `--omni`。

## Unknown / Search boundary

- 沒有找到同一 prompt／seed／resolution／frames／precision、同時記錄 cold load、warm/cache hit、text encoder、DiT、VAE decode、peak VRAM、peak host RAM、disk I/O 的單 L4 24GB 對照；因此本檔不能為任何替代框架排出通用速度或畫質名次。
- 單 A100 40GB 的公開 exact qualification 仍缺；A100 80GB 只有 Wan2.2 TI2V-5B 的 1TiB-host qualification和 Sol Engine 的 4×A100 高資源資料，二者不可互換。
- FastVideo 的 L4/A100 兼容性可由 support/SM gate 文件確認，但沒有指定 GPU 實跑；FastH3 V1/V2 的公開 timing 是 Blackwell／GB200 等高資源。H3 VSA、FA4、NVFP4、Sol-Attn、SANA/Blackwell compilation 不能外推至 L4/A100。
- Wan2GP 的 H3 5–6GB／8–9GB 與 LTX-2 8GB／12GB／16GB／24GB 是作者 runtime claims，沒有拆 host RAM、磁碟 cache、cold/warm 或完整 MP4 timing；需與 actual success/failed 分開。
- 社群頁面如 Reddit/X/FB 多為 snippet、登入邊界或未完整 read；本檔只採可讀的 Reddit benchmark 一條作旁證，沒有把 snippet-only 資料寫成 qualification。

## Sources

- **INF01** — [Wan2GP README](https://github.com/extreme2k/Wan2GP)（v12.434 changelog、models、H3 claims、Sol-Attn/W4A8；作者 repo）。
- **INF02** — [Wan2GP CLI/reference](https://raw.githubusercontent.com/DeepBeepMeep/Wan2GP/main/docs/CLI.md)（profiles、preload、pinned RAM、MMGP allocator、compile/attention/TeaCache；作者 docs）。
- **INF03** — [DiffSynth MiniMax-H3 docs](https://github.com/modelscope/DiffSynth-Studio/blob/main/docs/en/Model_Details/MiniMax-H3.md)（NF4、7GB claim、480×832/124f/50-step example、tasks、quant/offload）。
- **INF04** — [DiffSynth LTX-2 docs](https://github.com/modelscope/DiffSynth-Studio/blob/main/docs/en/Model_Details/LTX-2.md)（LTX-2.3/2.5 tasks、8GB claim、two-stage、audio/control）。
- **INF05** — [DiffSynth Colab firsthand report](https://zenn.dev/nakanishitf/articles/bec3dc44dd1b65?locale=en)（2026-08-18；G4/T4 results、OOM logs、disk offload、dependency fixes）。
- **INF06** — [FastVideo support matrix](https://github.com/hao-ai-lab/FastVideo/blob/main/docs/inference/support_matrix.md)（registered IDs、Wan/LTX/H3 tasks、VSA/Sage/STA constraints、unsupported Wan-VACE）。
- **INF07** — [FastVideo optimizations](https://github.com/hao-ai-lab/FastVideo/blob/main/docs/inference/optimizations.md) and [offloading](https://github.com/hao-ai-lab/FastVideo/blob/main/docs/inference/offloading.md)（FP8 sm89 gate/fallback、compile、H3 VSA/FA4、offload/lazy/sequential）。
- **INF08** — [FastH3 official blog](https://haoailab.com/blogs/fasth3-preview/) and [FastVideo H3 recipes](https://haoailab.com/FastVideo/cookbook/minimax-h3/)（V1/V2 task contracts、4/8 forwards、Blackwell-only timing boundary）。
- **INF09** — [LightX2V H3 README](https://github.com/ModelTC/LightX2V/blob/main/scripts/minimax_h3/README.md) and [config](https://raw.githubusercontent.com/ModelTC/LightX2V/main/configs/minimax_h3/minimax_h3.json)（one-GPU offload/AdaLN/Sage/SGL/124f contract、quantized LoRA/compile restrictions）。
- **INF10** — [LightX2V Wan21 beginner guide](https://github.com/ModelTC/LightX2V/blob/main/examples/BeginnerGuide/EN/Wan21-14B.md)（single H100 and offload timing/VRAM）。
- **INF11** — [NVIDIA SANA Sol Engine H3 DataCenter](https://nvlabs.github.io/Sana/Sol-Engine/H3-DataCenter/)（2026-08-09；4×A100 SM80/Triton, 3.55×, 61.28s full-opt）。
- **INF12** — [SGLang MiniMax-H3 cookbook](https://github.com/sgl-project/sglang/blob/main/docs/cookbook/diffusion/MiniMax/MiniMax-H3.mdx)（H3 formats, offload, 4090/host emulation, compile/cache limits）。
- **INF13** — [SGLang Cache-DiT docs](https://github.com/sgl-project/sglang/blob/main/docs/docs/sglang-diffusion/cache_dit.mdx)（DBCache/TaylorSeer/SCM, up to 1.69× claim, per-request cache）。
- **INF14** — [vLLM-Omni diffusion features](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/diffusion_features/) and [supported models](https://docs.vllm.ai/projects/vllm-omni/en/latest/models/supported_models/)（Wan/LTX/SANA/H3 matrix、offload/quant/cache/parallel support）。
- **INF15** — [Wan2.2 TI2V-5B A100 qualification](https://github.com/wiseyak-core/wiseyak-vllm-omni/blob/main/recipes/Wan-AI/Wan2.2-TI2V-5B-A100.md)（1×A100 80GB、1TiB host、T2V/I2V timing/peak/MP4 verification）。
- **INF16** — [vLLM-Omni text-to-video examples](https://docs.vllm.ai/projects/vllm-omni/en/stable/user_guide/examples/online_serving/text_to_video/)（OpenAI-compatible API、sync timing header、LTX H800 compile/cache benchmark、Wan/SANA commands）。
- **INF17** — [LightX2V V100 TP4 benchmark](https://github.com/Leonccaa/LightX2V-V100/blob/main/docs/minimax_h3_v100_tp4_benchmark.md)（2026-08-10；4×V100 high-resource H3 timing、cold/warm/DiT/VAE split、OOM boundary）。


- **INF18** — [Canonical deepbeepmeep/Wan2GP](https://github.com/deepbeepmeep/Wan2GP) 與 [canonical API metadata](https://api.github.com/repos/deepbeepmeep/Wan2GP)、[extreme2k fork API](https://api.github.com/repos/extreme2k/Wan2GP)（主代理核查fork provenance與更新範圍；canonical本身歷史上是Wan2.1的fork，不以fork旗標判定無效）。

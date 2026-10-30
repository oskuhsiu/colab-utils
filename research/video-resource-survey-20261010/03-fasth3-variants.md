# FastH3 / FastVideo variants 與資源證據

查核日：2026-10-10（公開 web/HTTP，只讀；未登入、未安裝、未下載權重、未啟動 GPU）。本檔只整理 FastVideo student variants、OmniRef/PDD、量化／kernel 契約與可核對的作者／社群測試；不把步數直接當畫質排序。

## Answer

FastVideo 的公開 student 路線目前是分開的契約：4-step v0.2/v1 是 T2VA；8-Step V2 是另一個 T2VA DMD2 student；Trim 是 V2 的 42-block 實驗剪枝版；OmniRef PDD-8 是獨立的 Ref2VA `transformer_ref` student。ComfyUI 官方 FastH3 template 對 V2 明示支援 T2VA 與首／尾幀 FL2VA；Ref2VA 尚未由該 student 蒸餾。FastVideo 原生 `basic_fasth3_omniref_pdd.py` 才是 PDD Ref2VA 路徑。

4-step v0.2 的明示契約是 DMD2、`[999,749,500,250]`、video/audio shift 12/3、64-token tile、90% video sparsity、四次 DiT forward；v0.2 是 4000-step run 的 step 2900，訓練解析度為 1344×768、124 frames、約 5 秒同步音訊。模型卡仍寫高動作細節與部分音訊低於 50-step base。v1 另有 VSA/Data-Free（推薦）、VSA/Synthetic/Step1300、VSA/Synthetic/Step1900、Dense/Data-Free 四個 4-call checkpoint／LoRA ablation：差別是 prompt-only 或 Base-H3 synthetic source、training step，以及 VSA 90%/tile64 或 Dense FA4；不能把 synthetic／dense 版當同一權重。

8-Step V2 是 step-1300、data-free DMD2、VSA 80%/tile64、video/audio shift 10/3、八 forward 的獨立 checkpoint；精確梯子 `[999,874,749,624,500,375,250,125]`，九個 sigma points 才是八次 forward。官方預設測試為 4×B200；其他多 GPU CUDA path 明示改用 Triton、`--no-fa4`。模型卡只承諾 T2VA，並保留困難動作、細節、部分音訊低於 base 的限制。

Trim 是 V2 的實驗縮小版：50 個 transformer blocks 移除 8 個，AdaLN timestep projection 改為共享 rank-16 basis，checkpoint 300、8-step DMD2、VSA 保留 20% tiles；作者稱它比 V2 快且較小，但 busy scenes 可能少細節。公開 BF16、FP8、NVFP4 與 Comfy repack；FP8 card 寫 transformer 19.9 GiB，NVFP4 card 寫 11.1 GiB。這些是模型／作者明示的尺寸與限制，不是 L4/A100 實測。

OmniRef PDD-8 是另一條 Ref2VA student：`transformer_ref` 32 個 PDD heads，8 個 block、每 block 4 heads；shift 12/3、`pdd_steps=32`、`vsa_sparsity=0.9`、tile 128、`p2_multi_region`，每個 reference video 自成 sparse region。FastVideo 文件明確限定 tile 128 只走 sm100a/sm103a（B200/B300/GB200/GB300）block-sparse kernel，沒有 Triton fallback；GB200 480×832×124 的八 forwards 約 54 s、device memory 約 103 GiB。768×1344×345、4 GPU 的八 forwards 約 36 s，文檔另報約 66 GiB allocated／約 95 GiB in-use per GPU。這不是 24-GB L4 或 A100 路徑。

### Variant / execution evidence

| 路線 | 來源明示的模型／採樣／任務 | 資源與時間證據 | 品質／音訊界線 |
|---|---|---|---|
| v0.2 | 4-step DMD2；`[999,749,500,250]`；shift 12/3；VSA 90%、tile64；T2VA only；BF16 student transformer，其餘 base components unchanged。| 訓練 32×GB200；1344×768、124f、約5s；沒有 L4/A100 E2E。| v0.2 比 v0.1 多 1500 distillation steps；卡片稱 still maturing，尤其高動作細節；其它梯子／步數 off-distribution。[FH301] |
| v1 ablations | VSA/Data-Free（prompt-only、step1300）、VSA/Synthetic/Step1300、VSA/Synthetic/Step1900（Base-H3 synthetic video）、Dense/Data-Free（Dense FA4、step1000）；四者都 4 DiT calls。| 官方 B200 benchmark 只重複報推薦 VSA/Data-Free；ablation latency 未獨立報。| 官方仍寫 FL2VA/Ref2VA 未蒸餾；困難動作、細節、部分音訊可能低於 base。[FH302][FH303] |
| 8-Step V2 | step1300、data-free DMD2、VSA 80%、tile64；shift 10/3；8 forwards；T2VA only。| 預設 4×B200；非 Blackwell 文件要求 Triton、`--no-fa4`；未報 L4/A100。[FH304][FH305] |
| Trim 8-step | 42/50 blocks、shared rank-16 AdaLN、checkpoint300、VSA keep20%；BF16/FP8/NVFP4/Comfy files。| 作者 benchmark 是 5s、832×480與1344×768 warm E2E；FP8 transformer 19.9 GiB，NVFP4 11.1 GiB。| 作者稱比 V2 快但 busy scenes 少細節；作者建議 quality matters 時看 V2（此為作者明示，不作泛化）。[FH308][FH309][FH310] |
| V2 FP8 / NVFP4 | FP8 是 50-block V2，attention/MLP E4M3、per-channel weight scale + per-token activation；NVFP4 deployment 是 calibrated W4A4，部分 DiT/VAE layers quantized，attention／text encoder等保留 BF16/FP32。| FP8 card targeting RTX4090/3090、及 16/12GB tiers；NVFP4 Comfy 13.6GB file targeting Blackwell；NVFP4 deployment target 4×B200。| NVFP4 deployment 5 pairs、1344×768×5s、同 prompt/seed，mean PSNR 11.92 dB、SSIM .3647、LPIPS .5184、audio log-mel cosine .9346；作者明示是 calibration-source trajectory drift，非 held-out quality acceptance。[FH311][FH312][FH324] |
| V2 NVFP4 Consumer | 單一 Blackwell GPU／DGX Spark variant；8 steps；AdaLN table 155MB 可跳過 26GB BF16 AdaLN；text encoder layerwise、LynnReal video VAE + INT8、H3 audio VAE。| 官方寫 single RTX5090／RTX PRO6000／DGX Spark；低於64GB system RAM 要用 AdaLN table；未報 L4/A100。[FH313] |
| OmniRef PDD-8 | Ref2VA `transformer_ref`；32 heads → 8 blocks×4；PDD contract、tile128、VSA90%、ref keep10%；reference images/videos/audio 有序傳入；原生 stereo audio。| GB200：480×832×124 8 forwards約54s、device peak約103GiB；768×1344×345、4 GPU 約36s，約66GiB allocated／95GiB in-use per GPU；model load/decode另計。[FH305][FH306] |

### Author / community timing and completed artifacts

| 實測者與路徑 | 條件／數據 | 可回溯 artifact | 限制 |
|---|---|---|---|
| FastVideo v1 作者 | Warm E2E、1344×768、24fps、audio；1×B200 VSA/Data-Free：5s 16.2s、10s 31.1s、15s 47.2s；4×B200：6.1/12.0/15.5s；8×B200：6.84/11.66/12.88s。Base dense FA4 同條件 1×B200：132.5/377.4/678.7s。| [v1 blog](https://haoailab.com/blogs/fasth3-preview/)、[FastH3 collection](https://huggingface.co/collections/FastVideo/fastvideo-fasth3) | B200 only；warm E2E includes encode/denoise/decode/audio/mux；不可外推 L4/A100。[FH302] |
| FastVideo consumer author | 5s、832×480與1344×768、audio；每 machine 兩 prompts×兩 runs median、warm server。V2/Trim：4090 24GB 54.6/43.9s（480p）、154.6/132.8s（768p）；5090 32GB 14.8/13.4s、38.6/35.4s；PRO6000 96GB 13.5/12.0s、36.5/32.5s。4090 memory cap rows：16GB 79.9/72.1s、12GB 91.2/74.1s、8GB Trim 82.0s。| [FastH3 on Consumer Hardware](https://haoailab.com/blogs/fasth3-rtx/) | 16/12/8GB 是同一 4090 cap，不代表真實卡；host RAM 未按 machine 報完整。Pinned allocator 2.87GiB FP4 weights→5.06GiB host allocation，可在 60GB cloud container 被 kill，exact-size buffer 2.90GiB。[FH308] |
| FastVideo local author | 四步、full VAE、832×480、124f：M4 Max 504/465s；DGX Spark first/repeat 264/243s；4×GB200 first/warm 10.2/5.1s。Spark 128GB unified；同 box 768×1344×124 one Spark 374s、two Sparks 292s；345f two Sparks 581s。| [FastH3 Goes Local](https://haoailab.com/blogs/fasth3-local/) | cold/repeat 標籤與 server state 要照正文；GB200 VRAM/host RAM未報；Spark 是 unified memory，不可化約成離散 GPU。[FH318] |
| ComfyUI community FastH3 T2VA | RTX4060Ti 16GB、64GB RAM；0.4MP 約1分鐘／5s video，0.5MP 約2分鐘；另有 31GB usable report：host RAM 29.8→7.5GB with `--disable-pinned-memory`，VRAM peak 11.5–15.4GB。| [Reddit post](https://www.reddit.com/r/comfyui/comments/1w4cjcb/testing_t2va_fast_h3_only_1_minute_generating/)、[Civitai workflow](https://civitai.com/models/2906467/fast-minimax-h3-t2va?modelVersionId=3286956) | 社群非同一 seed／解析度／冷暖 benchmark；quality discussion 混有近景與寬景，不能作模型排名。[FH320] |
| ComfyUI experimental VSA | RTX PRO4500 Blackwell SM120、34GB VRAM、約64GB RAM；608×352×124f、stereo AAC。Hero 3-step `res_2s` 約5.17s、300 calls、0 fallbacks；另 4-step `simple/res_multistep` 約7.8s denoise vs dense 8.6s，200 calls。| [repo](https://github.com/exportAnything/ComfyUI-FastH3-VSA)、[T2VA workflow](https://github.com/exportAnything/ComfyUI-FastH3-VSA/blob/main/examples/fast_h3_vsa_t2va_workflow.json)、[hero workflow](https://github.com/exportAnything/ComfyUI-FastH3-VSA/blob/main/examples/fast_h3_vsa_hero_res2s_workflow.json)、[hero MP4](https://github.com/exportAnything/ComfyUI-FastH3-VSA/blob/main/assets/fast_h3_vsa_hero.mp4) | 明示是 independent experimental integration；只驗 Windows／one GPU／SM120，Linux、其它 architecture、FL2VA/Ref2VA、MultiGPU 未驗。3-step hero 不可直接與 4-step time 比。[FH319] |
| ComfyUI community Kijai path | RTX4060Ti 16GB、64GB DDR4；Kijai FastH3 VSA 4-step checkpoint卻用 8 steps，約10分鐘／15s；作者稱不加 LoRA，音訊在4步較差、6/8步較好。| [Reddit](https://www.reddit.com/r/comfyui/comments/1w3iotu/testing_kijai_fast_h3_model_with_8_steps/)、[checkpoint link](https://huggingface.co/Kijai/MiniMax-H3-experimental/blob/main/minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors)、[workflow](https://civitai.red/models/2906467/fast-minimax-h3-t2va?modelVersionId=3286956) | 8 steps 是 4-step student 的 off-contract 社群試驗；同頁另有 RTX3090 使用者稱比 int8+Turbo LoRA 慢約2×且較糊，保留相反結果。[FH321] |
| 社群 FastH3 vs base | 12GB VRAM／32GB RAM；作者下載 FastH3 官方 blog clips，Comfy default workflow 25 steps、SLA+Spectrum、Ref2VA int8_convrot，每 clip平均7m30s；附5個完整 Streamable clips。| [Reddit comparison](https://www.reddit.com/r/StableDiffusion/comments/1w1333e/minimax_h3_a_quick_comparison_between_the_fasth3/)、[ship](https://streamable.com/liv2tn)、[window](https://streamable.com/6qu4y3)、[ogre](https://streamable.com/d9bi45)、[moon](https://streamable.com/t9uwwp)、[woman](https://streamable.com/19zewa) | FastH3 clip不是同機重跑，未報解析度／FastH3 steps；只能算品質／artifact觀察，不能算 FastVideo-vs-Comfy speed A/B。[FH322] |

### A100 / L4 / kernel boundary

NVIDIA 的 compute-capability table 將 L4 列為 CC/SM 8.9、A100 列為 8.0；Google Cloud 的 GPU table 列 L4 24GB、A100 40GB／80GB，並列 L4 FP8 121 TFLOPS、A100 FP8 N/A。FastVideo 的 FP8 docs 明示硬體 FP8 需 sm89+，sm89 以下自動走 BF16 dequant。因此：L4 的「FP8 hardware eligibility」是由官方 threshold + 官方 GPU mapping 合成的適用性判讀；A100 的 FP8 model 不應宣稱走 native FP8，官方文件只支持它走 BF16 dequant fallback。這仍不是 FastH3 L4/A100 端到端測試。[FH315][FH316][FH317]

FastVideo 的 4-step/V2 public recipe 對非 `sm100a` 路徑提供 Triton／`--no-fa4` 方向；但 regional H3 compile 的官方說明只支持 sm100a tile64，tile128 OmniRef PDD 更明示沒有 Triton fallback。故「VSA 能否在特定 L4/A100 build native 跑」與「FP8 linear 是否能跑」是兩個不同問題；本 leaf 的外部 public evidence 沒有找到官方 FastH3 L4/A100 cold/warm、peak VRAM/host RAM、kernel fallback log 或完整成片。[FH315][FH305]

工作區另有主代理於 2026-10-09 取得的 L4 本地試驗（23034 MiB VRAM、52.96 GiB RAM、864×480×124f、4 steps、VSA 200 calls/0 dense fallback、total 181.62s 與 156.19s），詳見 [00-hardware-and-local-evidence.md](./00-hardware-and-local-evidence.md)。那是既有 workspace evidence，不是本 leaf 今日外部查核，也不是受控的 FastVideo-vs-Comfy head-to-head。

## Unknown / Search boundary

- 沒有找到同一 prompt／seed／resolution／frames／VAE／precision 下 FastVideo CLI 與 ComfyUI 的同 GPU cold+warm paired benchmark；官方 FastVideo 數字多為 B200／4090／5090／Spark，社群 Comfy 數字多為不同 workflow。
- 沒有找到 A100 40GB 或 A100 80GB 的 FastH3 student 端到端實測；A100 只在 FastVideo generic Wan compile example 出現，不能轉成 H3 benchmark。
- 沒有找到 L4 的 FastH3 VSA native/fallback 實測或完整 workflow video；4-step/V2 的 Triton fallback availability 仍需按實際 fastvideo-kernel/Triton build 驗證。
- 不能由 4 vs 8 forward、VSA 90% vs 80%、或量化 bit-width 單獨推出畫質優劣；官方 cards 明示各自 trained ladder／attention policy，且 quality claims 均有 motion/detail/audio 限制。
- 社群「接 Ref2VA 節點」不等於 FastH3 student 已蒸餾 Ref2VA；官方 V1/v0.2/V2 cards 都寫 FL2VA/Ref2VA 未蒸餾，只有 OmniRef PDD 是原生 Ref2VA student。

## Sources

FH301 [FastVideo FastH3 Preview v0.2 model card](https://huggingface.co/FastVideo/FastVideo-Minimax-FastH3-Preview-v0.2)（2026-08-28 revision / current card）

FH302 [FastVideo FastH3 Preview v1 author blog](https://haoailab.com/blogs/fasth3-preview/)（2026-08-27）

FH303 [FastH3 v1 VSA/DataFree card](https://huggingface.co/FastVideo/FastVideo-FastH3-4-step-Preview-v1-VSA-DataFree)

FH304 [FastH3 8-Step V2 card](https://huggingface.co/FastVideo/FastVideo-FastH3-8-Step-V2)

FH305 [FastVideo distilled schedules + OmniRef PDD contract](https://github.com/hao-ai-lab/FastVideo/blob/main/docs/inference/fasth3-distilled.md)

FH306 [OmniRef PDD runner and hardware measurements](https://github.com/hao-ai-lab/FastVideo/blob/main/examples/inference/basic/basic_fasth3_omniref_pdd.py)

FH307 [FastVideo support matrix](https://github.com/hao-ai-lab/FastVideo/blob/main/docs/inference/support_matrix.md)

FH308 [FastH3 on Consumer Hardware / Trim author blog](https://haoailab.com/blogs/fasth3-rtx/)（2026-10-06）

FH309 [Trim FP8 card](https://huggingface.co/FastVideo/FastVideo-FastH3-Trim-8-Step-FP8)

FH310 [Trim NVFP4 card](https://huggingface.co/FastVideo/FastVideo-FastH3-Trim-8-Step-NVFP4)

FH311 [V2 FP8 card](https://huggingface.co/FastVideo/FastVideo-FastH3-8-Step-V2-FP8)

FH312 [V2 NVFP4 deployment card](https://huggingface.co/FastVideo/FastVideo-FastH3-8-Step-V2-NVFP4)

FH313 [V2 NVFP4 Consumer card](https://huggingface.co/FastVideo/FastVideo-FastH3-8-Step-V2-NVFP4-Consumer)

FH324 [V2 NVFP4 Comfy repack](https://huggingface.co/FastVideo/FastVideo-FastH3-8-Step-V2-NVFP4-Comfy)

FH314 [ComfyUI official FastH3 docs](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/minimax/minimax-h3-fastvideo.mdx)；[official T2V workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_fastvideo_fasth3_t2v.json)；[official I2V workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_fastvideo_fasth3_i2v.json)

FH315 [FastVideo optimizations / FP8 / compile docs](https://github.com/hao-ai-lab/FastVideo/blob/main/docs/inference/optimizations.md)

FH316 [NVIDIA CUDA GPU compute capability](https://developer.nvidia.com/cuda/gpus?trk=article-ssr-frontend-pulse-little-text-block)

FH317 [Google Cloud GPU memory / Tensor Core table](https://docs.cloud.google.com/compute/docs/gpus/)

FH318 [FastH3 Goes Local author benchmark](https://haoailab.com/blogs/fasth3-local/)（2026-09-02）

FH319 [ComfyUI experimental VSA integration](https://github.com/exportAnything/ComfyUI-FastH3-VSA)（captured test 2026-08-31）

FH320 [Reddit: FastH3 T2VA 4060Ti workflow test](https://www.reddit.com/r/comfyui/comments/1w4cjcb/testing_t2va_fast_h3_only_1_minute_generating/)

FH321 [Reddit: Kijai FastH3 8-step test](https://www.reddit.com/r/comfyui/comments/1w3iotu/testing_kijai_fast_h3_model_with_8_steps/)

FH322 [Reddit: FastH3 vs default 25-step workflow](https://www.reddit.com/r/StableDiffusion/comments/1w1333e/minimax_h3_a_quick_comparison_between_the_fasth3/)

FH323 [Reddit: FastVideo v1 announcement and 3090 Comfy test](https://www.reddit.com/r/StableDiffusion/comments/1w0xtrg/fastvideo_fasth3_v1_open_source_4step_sparse/)


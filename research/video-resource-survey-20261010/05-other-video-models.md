# 其他 Open-Weights 影片模型：低／中資源與成品證據

查核日：2026-10-10。只做公開 web/HTTP 讀取，未登入、未安裝、未下載權重、未啟動 GPU。本檔範圍是 LTX-Video/LTX-2、HunyuanVideo/1.5、FramePack、CogVideoX/CogVideoX-Fun、Mochi、Pyramid Flow、EasyAnimate，以及 StepVideo（只作 A10080 容量上限／多卡旁證）。Wan 核心與 Wan 專門控制不在本檔。低資源欄以「單張 L4 名義 24GB」為路由參考；中資源只把單 A100 40GB 與單 A100 80GB 分開列出。來源若是 RTX 3060、4090、A10、RTX PRO 6000 等，只保留原始條件，不能外推成 L4 或 A100 結果。

## Answer

以下是來源明示的資源／功能資訊；VRAM floor、相容性和指定 GPU 實測分開記錄：

- **有低 VRAM 路徑的來源：FramePack、Pyramid Flow、CogVideoX 2B／5B Diffusers、HunyuanVideo-1.5、EasyAnimate V5.1 7B／12B、LTXV 0.9.x。** FramePack 官方寫 6GB GPU 即可產生 13B、60 秒、30fps（1800 frames），但其 4090 速度是 1.5–2.5s/frame，並沒有 L4 實測。Pyramid Flow 官方以 sequential CPU offload 宣稱低於 8GB 可跑，768p 24fps 最長 10 秒。CogVideoX 官方 Diffusers 記錄 1.5-5B 約 10GB BF16／7GB INT8、2B 約 5GB BF16／4.4GB INT8，但測試記憶體只在 A100/H100，不能把數字當作 L4 實測。HunyuanVideo-1.5 官方最低 14GB（模型 offload），EasyAnimate 則給出 24GB A10、qfloat8/offload 的可跑矩陣與秒數。
- **EasyAnimate／CogVideoX-Fun 提供多種控制工作流與24GB級旁證。** 它們的官方作者 repo 都列 image-to-video、video-to-video、start/end image、Canny/Pose/Depth/MLSD；EasyAnimate V5.1 另列 trajectory／camera control。這是控制輸入契約，不等於角色身份長期一致保證。
- **音訊只有 LTX-2 家族是原生 joint audio-video。** LTX-2/2.3/2.5 的官方 pipeline 有 audio VAE、T2A、A2Vid、Dub-It、audio in/out；LTXV 0.9.x、HunyuanVideo/1.5、FramePack、CogVideoX、Mochi、Pyramid Flow、EasyAnimate 的本檔第一手 repo 未找到原生同步音訊，任何後配音或外部音訊節點都應標成外掛流程。
- **LTX-2.5 提供較多音畫／兩段式功能，但沒有指定 L4 完整測試。** 官方建議 distilled 22B，8 steps stage 1 + 4 steps stage 2；DFR 以 detailing IC-LoRA 做第二段空間細節，支援 2×／4× 空間及可選 2×／4× fps。官方只給量化／offload 旗標，沒有單 L4 或 A100 inference wall-time；trainer 的 80GB+／32GB low-VRAM 是訓練需求，不能偷換成生成需求。
- **Mochi 不屬於官方低資源路線。** Genmo repo 明示單 GPU 約 60GB VRAM、建議 H100；ComfyUI 可低於 20GB，但沒有官方 peak/time。第三方 GGUF 有 Q3_K_M 4.31GB、T5 Q4 2.9GB、FP8 VAE 460MB 並附 workflow，卻沒有可重現的 L4/A100 成片時間。

## Evidence table

| 模型／版本 | 官方／作者模型與少步契約 | 低／中資源硬體證據 | 成品規格與控制 | 音訊、量化與限制 |
|---|---|---|---|---|
| LTXV 0.9.8／0.9.7 | `ltxv-13b-0.9.8-dev`, `-distilled`, `-mix`；另有 2B distilled、13B FP8。0.9.7 distilled 是 8 steps（或更少），不需要 CFG/STG；0.9.6 distilled 官方稱比非 distilled 快 15×。| 沒有官方 L4/A100 peak。來源只給 H100 0.9.7 distilled HD 低解析預覽約 3s、HD 約 10s，且不是 0.9.8 的同條件 benchmark。| 官方預設 1216×704、30fps；解析度需可被 32 整除，frames 為 `8k+1`，最佳通常低於 1280×720 與 257 frames；0.9.8 宣稱可延長到 60s。多 keyframe、video extension、V2V、IC-LoRA；depth／pose／canny control 與 detailer 皆有官方 workflow。| Video-only，未見原生音訊。FP8 官方權重；city96 2B GGUF 有 Q3_K_S–Q8_0、BF16/F16，檔案約 0.99–3.94GB（OTH22）。 |
| LTX-2／2.3／2.5 | LTX-2.5 recommended：22B dev 與 distilled transformer；distilled pipeline 8 + 4 steps。LTX-2.3 是 legacy 單檔，Gemma 3；2.5 是 split transformer/Gemma4/video/audio VAE。| 無 direct L4/A100 inference measurement。官方 trainer 80GB+ standard、32GB low-VRAM INT8 是 training config；不能當 generation qualification。官方支持 `fp8-cast`, `fp8-scaled-mm`, 2.5 `nvfp4-cast/prequant`。| 2.5 distilled default 1024×1536、24fps、121f 約 5.04s；DFR final size 必須可被 64 整除（spatial-upscalings=2 時 128），4K 合法尺寸 3840×2176；temporal rounds 0/1/2 對應 24/48/96fps，時長約不變。IC-LoRA、keyframe interpolation、A2Vid、retake、HDR、Dub-It（speaker identity/lip match）。| 原生 joint audio-video、audio-only、audio in/out。DFR 第二段只細化 video，audio 來自 stage 1。官方沒有 L4/A100 time；2.3 Comfy quant 實測只在 RTX PRO 6000 Blackwell（OTH21）。 |
| HunyuanVideo-1.5 | 8.3B T2V/I2V；480p/720p base、CFG-distill、480p I2V step-distill（8/12 steps，4 steps 更快但略降質）；FP8 GEMM 另需 SGL kernel。| 官方最低 14GB（model offload）；官方以 RTX4090 宣稱 step-distilled 約 75s，但不是 L4/A100。CPU memory 不足可關閉 overlapped group offloading。LightX2V 4-step base 16.7GB、FP8 8.85GB，作者稱約 25× 相對 50 steps，但無秒數。| CLI default 121f、50 steps，480p／720p；官方 SR step-distill 480→720 用 6 steps、720→1080 用 8 steps。Comfy 官方有 720p T2V/I2V templates。原 repo 只直接保證 T2V/I2V；未提供身份一致或通用 ControlNet 保證。| 官方 repo 未見原生音訊。LightX2V FP8 `hy1.5_t2v_480p_scaled_fp8_e4m3_lightx2v_4step.safetensors`；未找到官方 HunyuanVideo-1.5 GGUF/NF4 成品 benchmark。 |
| HunyuanVideo 1.0 | 13B base／FP8 weights；single-GPU official sizes 544×960×129f（45GB）及 720×1280×129f（60GB），50 steps，CPU offload。| 官方測試單 80GB；45–60GB peak，超過 L4/A100 40。| 540p/720p 合法尺寸與 129f；未見原生音訊。| FP8 官方宣稱省約 10GB；city96 GGUF 是直接轉換，Q3_K_S 6.09GB 到 Q8_0 14GB、BF16 25.6GB，沒有量化畫質測試。 |
| FramePack／F1／P1 | 官方 repo：原始 FramePack、F1（2025-05-03）、P1 anti-drifting/history discretization（2025-06/07）。FramePack 是 next-frame-section progressive model。| 官方最低 6GB，13B 可作 60s/30fps；官方 4090 2.5s/frame unoptimized、1.5s/frame TeaCache。沒有 L4/A100 直接 benchmark。| I2V，長度靠 section 逐步增加；官方 README 未固定合法 spatial resolution，GUI 依 input bucket。官方示例 5s／1min；可看到中間 latent preview。| 無原生音訊。官方的特定 sanity-check 示範稱约30%使用者得到所附較差結果、其餘70%結果依硬體不同，量化／sage／bnb／GGUF 可能影響畫質；FramePack Studio NF4 社群測試在 RTX3060 12GB、約 7GB free VRAM 可載入，快速動作有 ghosting，8-bit 失敗。 |
| CogVideoX 1.5／5B、2B | 1.5-5B (latest) BF16/FP16/FP8/INT8，INT4 不支援；2B FP16；官方另有 5B、5B-I2V。| 官方 Diffusers memory：1.5-5B 10GB BF16／7GB INT8；2B 5GB BF16／4.4GB INT8。官方明示這些 memory test 只在 A100/H100，未在其它 GPU 實測。A100 5s benchmark：1.5-5B 約 1000s、2B 約 180s；H100 約 550s／90s。| 1.5 1360×768、`16N+1`（default 81）、5/10s、16fps；1.5-I2V 可變 resolution。舊 2B/5B 720×480、`8N+1`（default 49）、6s、8fps。I2V、V2V continuation；官方列 CogVideoX-ControlNet、Interpolation、ConsisID 為配套。| 官方 repo 沒有 audio branch；INT8/TorchAO、Optimum-Quanto；INT4 unsupported。官方 INT8 會明顯變慢且只保留 minimal quality loss 的作者描述，未提供控制的 video quality table。 |
| CogVideoX-Fun V1.5／V1.1 | PAI/AIGC 作者 repo；V1.5-5B-InP、Reward LoRAs；V1.1 2B/5B InP、Pose、Control、Reward。| Repo 驗證 Nvidia 3060 12G、3090 24G、V100 16G、A10 24G、A100 40/80G；約 60GB disk。提供 `model_cpu_offload`, `model_cpu_offload_and_qfloat8`, `sequential_cpu_offload`。| V1.5 512/768/1024、85f、8fps；V1.1 512/768/1024/1280、49f、8fps。start/end image、I2V/V2V、Canny/Pose/Depth/MLSD control。| 無原生音訊證據。qfloat8 可略降性能；沒有 L4/A100 wall-time或peak VRAM，不能由已驗證 A10/3090 外推。 |
| Mochi 1 | Genmo official 10B、64-step sample；LoRA fine-tune single H100/A100 80GB，最多 85f training。| 官方單 GPU約 60GB，建議 H100；ComfyUI 宣稱可低於 20GB但未給測量。| Official code example 480×848×31f、64 steps；初版 480p。T2V、LoRA；官方未提供 I2V／control／identity contract。| 無原生音訊。Comfy official FP8 files 可在 memory issue 時用，但質量較 16-bit 低；calcuis GGUF workflow 有 Mochi Q3_K_M 4.31GB、T5 Q4 2.9GB、FP8 VAE 460MB，作者稱新版 FP8 VAE workflow 約 50% faster，無 hardware/time qualification。 |
| Pyramid Flow miniFLUX／SD3 | 官方 miniFLUX 768p checkpoint、384p checkpoint；SD3 variant 仍可用。single DiT；提供 DiT fine-tuning code。| CPU offload 可低於 12GB，sequential offload 可低於 8GB；單 A100 5s/768p/24fps 約 5.5min，4×A100 2.5min。| miniFLUX 384p 5s、768p 最長 10s、24fps；I2V。官方無 ControlNet／identity／audio claim。| 沒找到 FP8/GGUF/NF4/NVFP4 model card；低記憶體靠 CPU offload。 |
| EasyAnimate V5.1 7B／12B | 7B／12B，Qwen2-VL text encoder、Flow sampling；LoRA、reward、control/camera weights。| 官方 matrix：12B 在 24GB 可跑 384×672×25/49、576×1008×25/49、768×1344×25，但 768×1344×49 不行；A10 24GB 25-step times 約 120/240/320/750s；A100 80GB 約 45/90/120/300/265/710s。24GB 是 A10，不是 L4。| 512/768/1024，49f、8fps，約 6s；I2V、T2V、V2V、Canny/Pose/Depth/MLSD、trajectory、camera control。| 無原生音訊證據。`model_cpu_offload_and_qfloat8` 節省 VRAM 但可略降性能；約 60GB disk。 |
| StepVideo-T2V／TI2V（高資源邊界） | 30B；T2V-Turbo 是 inference-step distillation（10–15 steps），base 30–50 steps；TI2V 可 102f、motion score。| T2V 官方 768²×204f peak 78.55GB、50 steps 860s with flash-attn；推薦 80GB，測試 4 GPU。TI2V 允許 single GPU 但較慢，要求 CPU offload for high-res。| T2V 最多 204f；TI2V 102f、camera／motion control；無本檔可接受的 24GB qualification。| 只作容量上限／多卡旁證，未在指定單卡High RAM完成驗證；原 repo 將單 GPU quantization 交給 DiffSynth-Studio，未給 quantized L4/A100 benchmark。 |

## 音訊、控制與兩段式／放大整理

| 能力 | 有第一手證據的模型 | 具體契約 | 未證明的部分 |
|---|---|---|---|
| 原生同步音訊 | LTX-2/2.3/2.5 | audio VAE、audio-only T2A、A2Vid、Dub-It；2.3 Comfy quant source 仍產出 49 frames + FLAC。| LTXV 0.9.x 的 video-only 權重不能當成 LTX-2 audio model；其它模型若加 MMAudio／聲音 remux 是外掛。 |
| 參考／控制 | LTXV、LTX-2、CogVideoX-Fun、EasyAnimate、StepVideo | LTX IC-LoRA depth/pose/canny、multi-keyframe、video conditioning；Cog/EA 的 start/end／control video；StepVideo motion score/camera。| 「角色一致」只有 LTX Dub-It speaker identity、StepVideo VBench subject consistency 報告或第三方 LoRA context；不能推導出通用 identity guarantee。 |
| 兩段式／空間放大 | LTX-2.5 DFR、LTX-2.3 Comfy workflows、Hunyuan 1.5 SR | DFR stage 1 half-res + detailing IC-LoRA stage 2、2×/4× spatial、optional temporal 2×/4×；Hunyuan 480→720／720→1080 SR step-distilled。| 任何第三方 latent upscaler 不代表原始模型原生支援；放大會增加 VRAM/time，且 LTX DFR decode 可能是 VRAM cliff。 |

## 量化與精度證據

- **LTX-2.3／Comfy 官方量化工具：** LTX-2.3 22B dense BF16 source 46.1GB；在 RTX PRO 6000 Blackwell、512²×49 + audio、20 steps 的 fresh server 測試，BF16 peak 53.7GB／2.37 it/s，FP8 E4M3 29.1GB artifact／36.7GB peak／2.27 it/s，NVFP4 21.7GB／29.6GB／1.56 it/s，INT8 tensorwise 29.2GB／38.6GB／2.73 it/s。這是可追溯的 quant comparison，但 GPU 高於本檔 L4/A100 邊界，不能把 peak/time 外推成 L4（OTH21）。官方 2.5 code 同時提供 `fp8-cast`, `fp8-scaled-mm`, `nvfp4-cast`, `nvfp4-prequant`；NVFP4 要 Blackwell（OTH03/04）。
- **LTX GGUF／IQ：** city96 的 LTXV 2B direct conversion 提供 Q3_K_S 0.99GB、Q4_K_M 1.42GB、Q8_0 2.17GB、BF16 3.94GB，沒有 video quality/time benchmark（OTH22）。gguf-org 的 LTX-2.3 22B `IQ4_XS` 14.8GB、`IQ4_NL` 15.4GB，另附 FP8 E4M3 checkpoint與 Comfy setup；同樣沒有 target-GPU measurement（OTH20）。
- **Hunyuan quant：** HunyuanVideo 官方 FP8 weights 說可省約 10GB；city96 original Hunyuan GGUF 13B 提供 Q3_K_S 6.09GB 至 Q8_0 14GB、BF16 25.6GB，只有檔案大小與 loader contract（OTH08/09）。HunyuanVideo-1.5 LightX2V 4-step FP8 artifact 8.85GB、base 16.7GB；作者宣稱約 50% memory reduction，但沒有 L4/A100 timing（OTH06）。
- **NF4：** FramePack Studio fork 的 first-hand issue 以 RTX3060 12GB、約 7GB free VRAM 比較 BF16 與 NF4；在 704×544，magcache on 的第二 section 是 BF16 10.62s/it、NF4 9.82s/it，在 832×640 是 15.03 vs 15.16s/it；作者記錄低解析 speedup、快速動作 ghosting，且 8-bit integer 方案不工作。這不是官方 FramePack repo，也不是 L4/A100，僅作 NF4 implementation evidence（OTH11）。
- **Mochi GGUF／FP8：** calcuis 的 Mochi 10B Q3_K_M 4.31GB、Q4_0 2.9GB、Q8_0 5.06GB、F16 9.53GB，T5 Q4 2.9GB、VAE FP8 460MB；Comfy 官方另外明示 FP8 files 較 16-bit 低質量但可能較快（OTH16/17）。
- **CogVideoX／EasyAnimate：** CogVideoX 官方只列 FP16/BF16/FP8/INT8，INT4 unsupported，TorchAO／Optimum-Quanto 可量化但 INT8 會顯著變慢；EasyAnimate qfloat8 是其自身 offload path。未找到這兩個 family 的第一手 NF4 或 NVFP4 video card，不能填補成品 quality claim。

## 失敗、限制與 Unknown / Search boundary

- **L4 缺 direct paired benchmark：** 本次沒有找到同一 prompt／seed／resolution／frames／precision／VAE 下，以上模型在單 L4 24GB 的 cold+warm wall-time、peak VRAM、host RAM 與可下載 MP4 成品成對測量。最接近的官方硬體是 Hunyuan 1.5 的最低 14GB（無 L4）、CogVideoX 的 A100/H100-only optimization table、EasyAnimate 的 A10 24GB table，三者都不能互換。
- **A100 40GB direct data 稀少：** EasyAnimate 只有 A100 80GB time；CogVideoX 有 A100 time但未拆 40/80；Pyramid Flow 有 single A100 time；Hunyuan original 45–60GB 直接排除 A100 40。LTX-2/2.5 沒有 official single-A100 generation timing。
- **FramePack 的理論低 VRAM 不等於實用速度：** 官方 6GB floor 與 community issue 的 RTX3090 24GB + 64GB RAM 約 16min／5s、RTX3060 12GB 5s 每秒約 7min 互相顯示速度高度受 attention kernels、TeaCache、section 數和精度影響；官方示範稱约30%使用者得到所附較差結果，其餘70%為其他隨硬體而異的結果；這不是通用品質成功率，快速運動會 ghosting。
- **HunyuanVideo-1.5 的少步配置易被錯用：** 官方 CFG-distill 仍要求 50 steps；step-distill 只對 480p I2V，8/12 steps（4 steps 可能略降質）。社群一篇 5080 report 用 720p FP16 50 steps 產生 5s 影片約 1.5h，並非模型必然速度；另一評論給 4/8-step LoRA 建議，但沒有完整 hardware/VRAM/MP4 package，因此不採當作 qualification。
- **LTX-2.5 的 32GB low-VRAM 說法是 trainer：** trainer README 的 80GB standard / 32GB low-VRAM INT8 是 fine-tuning，不能外推 generation。LTX-2.5 inference docs只提供 quant/offload flags和定性「slower/more VRAM」描述，沒有 L4/A100 measurement。
- **Mochi 的 ComfyUI <20GB 是未拆條件的 integration claim：** Genmo 原生 implementation 明示 60GB single GPU，Comfy official只說 FP8 files可降低 memory、品質低於16-bit；没有同一 prompt的 quantized output/time table。
- **控制／音訊未知：** 除 LTX-2 明示 joint audio，其他 repo 沒有 first-party native audio；第三方 audio node、RIFE、Topaz、MMAudio 或 remux 不能算模型原生功能。CogVideoX 的 ControlNet、ConsisID、VideoX-Fun／EasyAnimate 的控制權重是外掛／衍生模型契約，不能回寫成 base model自帶 identity consistency。
- **搜尋邊界：** 未實機、未下載 workflow／weights，沒有驗證本地 ComfyUI 版本、Python/CUDA 相容性、RAM 需求、磁碟寫入或實際成片畫面。也沒有把 4090/5090/B200 benchmark 外推至 L4/A100；StepVideo只留A10080容量上限／多卡旁證，沒有指定單卡High RAM成片qualification。未找到可信的 Mochi NF4/NVFP4、CogVideoX NF4/NVFP4、Pyramid Flow quantized card或它們的 L4/A100 controlled video quality test。

## Sources

詳細 claims、resources、measurements 與 artifact URLs 請見同目錄 `05-other-video-models.json`；以下列出本檔使用的 source label 與實際讀取 URL。

- **OTH01** — [LTX-Video official README](https://github.com/Lightricks/LTX-Video)（0.9.8/0.9.7 models、FP8、resolution/frame grid、IC-LoRA、control models、60s；官方）。
- **OTH02** — [LTX-2 official README](https://github.com/Lightricks/LTX-2)（2.5 model list、distilled/DFR、audio pipelines、quant/offload flags；官方）。
- **OTH03** — [LTX-2 pipeline docs](https://github.com/Lightricks/LTX-2/blob/main/packages/ltx-pipelines/docs/pipelines.md)（pipeline、兩段式、合法 grid、audio、DFR）與 [optimization docs](https://github.com/Lightricks/LTX-2/blob/main/packages/ltx-pipelines/docs/optimization.md)（FP8/NVFP4/offload；官方）。
- **OTH04** — [LTX trainer README](https://github.com/Lightricks/LTX-2/blob/main/packages/ltx-trainer/README.md)（80GB/32GB 是 training config；官方）。
- **OTH05** — [HunyuanVideo-1.5 official README](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)（8.3B、14GB offload、step distill、resolution/steps/SR、FP8 GEMM；官方）。
- **OTH06** — [LightX2V Hy1.5-Distill-Models](https://huggingface.co/lightx2v/Hy1.5-Distill-Models)（4-step base/FP8 file sizes、offload、81f/16fps、~25× claim；model author）。
- **OTH07** — [HunyuanVideo original official README](https://github.com/Tencent-Hunyuan/HunyuanVideo)（45/60GB peak、129f legal sizes、FP8 saves 10GB；官方）。
- **OTH08** — [city96 HunyuanVideo GGUF](https://huggingface.co/city96/HunyuanVideo-gguf)（Q3–Q8/BF16 file sizes、native Comfy loader；quant author）。
- **OTH09** — [FramePack official README](https://raw.githubusercontent.com/lllyasviel/FramePack/main/README.md)（F1/P1 releases、6GB floor、60s/30fps、4090 speed、TeaCache/quant failure caveats；官方）。
- **OTH10** — [FramePack issue #117](https://github.com/lllyasviel/FramePack/issues/117)（3090+64GB RAM slow run、per-section log、attention missing；firsthand community）。
- **OTH11** — [FramePack Studio NF4 issue #349](https://github.com/FP-Studio/framepack-studio/issues/349)（RTX3060 12GB NF4/BF16 s/it、約 7GB free VRAM、ghosting、INT8 failure；firsthand community fork）。
- **OTH12** — [CogVideo official README](https://raw.githubusercontent.com/zai-org/CogVideo/main/README.md)（model variants、memory/time、resolution/frame/fps、INT8/quantization/ControlNet/ConsisID；官方）。
- **OTH13** — [VideoX-Fun official README](https://raw.githubusercontent.com/aigc-apps/VideoX-Fun/main/README.md)（CogVideoX-Fun model names、tested GPUs、offload/qfloat8、49/85 frames、controls；model author）。
- **OTH14** — [Genmo Mochi official repo](https://github.com/genmoai/mochi)（60GB single GPU、Comfy <20GB claim、480p、31f/64 steps、LoRA；官方）。
- **OTH15** — [ComfyUI official Mochi example](https://comfyanonymous.github.io/ComfyUI_examples/mochi/)（FP8/BF16 placement、FP8 lower quality/faster；官方 ComfyUI）。
- **OTH16** — [calcuis Mochi GGUF card](https://huggingface.co/calcuis/mochi)（Q3/Q4/Q8/F16 sizes、T5 Q4、VAE FP8、~50% faster claim；quant author）。
- **OTH17** — [Pyramid Flow official README](https://github.com/jy0205/Pyramid-Flow)（miniFLUX/SD3、384/768p、5/10s、24fps、CPU offload <8/12GB、single A100 5.5min；官方）。
- **OTH18** — [EasyAnimate official README](https://github.com/aigc-apps/EasyAnimate)（V5.1 7B/12B、24GB matrix、A10/A100 times、qfloat8/offload、control/camera/trajectory；model author）。
- **OTH19** — [StepVideo-T2V official README](https://github.com/stepfun-ai/Step-Video-T2V)（30B、78.55GB peak、204f、50/10–15 steps、80GB recommendation；高資源 boundary）。
- **OTH21** — [Comfy-Org LTX-2.3 quant docs](https://github.com/Comfy-Org/comfy-quants/blob/main/docs/quantization/ltx2.md)（FP8/MXFP8/NVFP4/INT8 formats、RTX PRO 6000 measurements、audio+49f；官方 Comfy quant）。
- **OTH20** — [gguf-org LTX-2.3 IQ4 card](https://huggingface.co/gguf-org/ltx2.3-gguf)（IQ4_XS/NL 14.8/15.4GB、FP8 checkpoint、Comfy setup；quant author）。
- **OTH22** — [city96 LTX-Video GGUF](https://huggingface.co/city96/LTX-Video-gguf)（LTXV 2B Q3–Q8/BF16 file sizes；quant author）。
- **OTH23** — [HunyuanVideo-1.5 ComfyUI community timing report](https://www.reddit.com/r/comfyui/comments/1p6p5zz/hynuyanvideo_15_i2v_takes_forever_1.5h_on_5080/)（RTX5080 720p FP16 50-step 5s 約 1.5h；firsthand community，slow/failure evidence）。

# H3 / FastH3 最快影片生成：L4 來源證據

查閱截止：**2026-10-09T04:44:00Z**。本報告只整理來源明示的參數、平台、數據與限制；沒有啟動 GPU、沒有下載模型，也沒有把外部數據當成 L4 實測。

## Answer

對單張 24-GB L4，公開資料可直接支持的速度候選是：FastH3 student 的訓練步數契約（4 次 DiT forward）+ 64-token、90% VSA，並選用能在 SM89 路徑運行的 Triton/INT8-QK attention。FastVideo 官方目前最快的 `sm100a` VSA、FA4 與 regional compile 是 Blackwell 路線；PR #1919 雖加入 SM89，公開時間是 RTX 4090，不是 L4。固定 864×480、124 frames（再裁 120 frames/5 秒）才能把目前本機數據和來源數據分開比較。

人物 reference 要維持 H3 **Ref2VA** 語義。MiniMax 官方把 FL2VA（T2VA／首尾幀）和 Ref2VA（多圖／影片／音訊 reference）分成不同 checkpoint；FastH3 4-step v0.2 是 T2VA student，8-step V2 的模型卡仍寫 T2VA-only，FL2VA/Ref2VA 都未蒸餾；ComfyUI 另提供首尾幀 I2V 接口，接口可接不等於 student 已蒸餾此任務。因此不要把 base+Turbo 的步數資料改稱 FastH3。

## 來源明示

| 候選／旋鈕 | 來源明示 | 平台／品質或記憶體限制 | 尚未 L4 驗 |
|---|---|---|---|
| 4-step FastH3 v0.2 | HF model card S1：base 50 steps；student 用 `[999,749,500,250]`、guidance 1.0，4 次 forward；VSA 64-token、90% video-tile sparsity。768×1344、124 frames、同步音訊；其他 grid／step 數是 off-distribution。 | 2900-step student；品質仍低於 base，尤其高動態細節。32×GB200 是訓練平台。 | L4 端到端時間、VRAM、品質未由來源提供。 |
| 8-step FastH3 V2（獨立 checkpoint） | HF README S2：8 次 forward、VSA 80%、video shift 10 / audio 3；FastVideo repo NEWS 於 2026-09-15 公開。 | 只支援 T2VA；README 明示 FL2VA/Ref2VA 未蒸餾，困難動作／細節／部分音訊低於 base；測試命令預設 4×B200，其他 CUDA 建議 Triton、`--no-fa4`。 | 不可套到目前 Kijai 1300-step 4-step 檔；L4 未驗。 |
| FastVideo SM89 VSA | PR #1919 S3：SM89 INT8-QK sparse attention、fused-scale FP8 GEMM、INT8 VAE epilogue；RTX 4090 warm server、5 秒含音訊：832×480 V2/Trim 54.6/43.9 s，1344×768 154.6/132.8 s。sm89 API S4 是 BF16 `[B,H,S,128]`、64-token tile、INT8 QK 可選、FP32 accumulation；FP8 PV 因真實 H3 誤差過大而保留 BF16。 | 4090≠L4；INT8-QK／FP8 weight scale 會改數值，來源沒有 L4 品質 gate。 | 需要在 L4 實測 kernel 是否走 native SM89、step wall time、fallback、峰值 VRAM。 |
| Comfy Kitchen Sol-Attn / VSA mode | PR #117 S5：`tail=False`、`block_len`、`coarse_gate`、`topk_ratio` 可重現 VSA fine/coarse；chunked QKV 直接產生 INT8 carriers，T=113k 約省 5 GB peak。H3 T=80k/56 heads：23.4→13.0 s/it（1.80×）對 dense INT8，cos≈0.97 vs dense、≥0.998 vs full precision。 | generic guard SM80+，但調校／數據是 SM120；官方說 `<12k tokens` dense 通常更快。這是公開 kernel 參考，不證明 private FastH3 VSA 等同。 | L4 端到端、品質、是否比目前 public FastH3VSAPatch 快，均未驗。 |
| W4A8／ConvRot 與 VAE | comfy-kitchen PR #90 S6：W4A8 INT4 weight + INT8 GEMM，約 0.56 B/elem、約 1.09× INT8 speed、無 calibration；範例機是 5090。Kijai README（commit `d8023be`）稱 int8-convrot VAE 在 ComfyUI 0.36.0 可讓 VAE decode 約 2×；light VAE 約 1.3×。 | 這些是權重／decoder 轉換的作者數據，非 FastH3 4-step L4 數據；精度與畫面品質需同 seed 驗。 | L4 kernel、VAE decode wall time、品質未驗。 |
| resident、offload、pin、初始化 | FastVideo basic CLI S7 預設 `--offload-text-encoder`/`--offload-vae`、`--pin-cpu-memory`、`--compile-vae`、regional `--inference-torch-compile`；`--no-lazy-module-load` 保持元件常駐，`--warmup --repeats` 把初始化／compile 排除。官方 offloading docs：CPU offload 有 PCIe 成本；lazy 以最大重疊元件取代總和，但下一次 request 需重讀，文字 encoder 可多十幾秒。 | `h3_sequential_load` 先 encode Qwen 再釋放，主要為 unified-memory；離散 GPU 強制開會阻塞同 worker 的下一次 generate。Comfy issue #14250 顯示 `--disable-pinned-memory` 可解 HostBuffer OOM 且速度未變，但那是 WAN/5070Ti，不可當 H3 L4 benchmark。 | 本機目前是 dynamic offload／compiler disabled；resident vs offload、pin vs unpin、冷／warm 5 秒總時間需後續同一 L4 量測。 |
| compile／decoder／tiling | FastVideo optimizations S8：第一個 compile generation 要付 graph-build，須 warmup；GB200 H3 50-point 示範 185.08→157.01 s E2E、174.90→147.12 s denoise，但 compiled 與 eager 的 SSIM/MAE 不相同。其 H3 regional compile 只支援 sm100a tile-64。Comfy H3 VAE source S9 固定 spatial tile 256、temporal clip 17；`decode_tiled()` 只是呼叫內部 tiled `decode()`。 | TAEH3 是官方 CLI 的 fast approximate preview decoder；完整 VAE 才是品質路徑。DiffSynth docs 的 tile 256/overlap 64 明示省 VRAM、增加少量時間並帶小數值誤差。 | L4 compiler、TAEH3／完整 VAE 品質與 decode time 未驗；目前 L4 設定停 compiler 是已知可成功條件。 |
| text encoder output cache | ComfyUI core/FastVideo 官方來源未找到可重複 prompt 的 H3 conditioning cache。第三方 `linjian-ufo` S10 宣稱完全相同 prompt、reference、encoding options 才命中 CPU cache；首次仍完整 32B encode。`Comfy-H3-MultiStream` S11 的 Blackwell 測量：NVFP4/AWQ encoder uncached 67 s、weight-cache warm 12.5 s、output-cache hit 0.2 s；output cache 約 12 MB/768×1344 scene，並警告非 Blackwell 未驗。 | cache 命中改變的是重複 scene 的 conditioning／staging，不是 DiT 4-step sampling；第三方沒有 L4 證據。 | 只可作獨立 A/B 實驗候選，需記錄 hit/miss、RAM、conditioning equality；不要把作者數據當本機速度。 |

## 本機可比基準（來源是工作區實測，不是外部來源）

`research/fast_h3_l4_speed.md` 已記錄 864×480、124→120 frames、5 秒、4 Euler steps、200 native VSA calls：Notebook total 181.62 s（VSA 98.6004 s；首 forward 69.55 s；尾三步 29.0504 s），Comfy total 156.19 s（VSA 86.8137 s；首 forward 57.65 s；尾三步 29.1637 s）。由尾三步外推的 4-step sampling 約 38.73/38.88 s 只是估算；尚沒有真正 warm 5 秒總時間。此數據包含目前 dynamic VRAM/offload 條件，不能用 FP32 TFLOPS 比例外推。

## 平台／限制與量測口徑

FastVideo headline protocol S3 是固定 prompt、一次 warmup、每 prompt 兩次 timed `generate_video` wall time；Comfy／本機應另記 text encode、DiT/VSA、VAE decode、save/mux，並固定 864×480、124 frames、4 forwards、seed、kernel、fallback、peak VRAM/RAM。H3 合法 frame count 是 `17n+5`，24 fps；5 秒會對齊 124 frames。來源 benchmark 的 4090、5090、GB200、SM120、Blackwell 結果只作條件化參考。

## 尚未 L4 驗

尚未有公開 primary source 在單張 L4 上同時報 FastH3 4-step 真正 5 秒 cold/warm total、SM89 INT8-QK vs public VSA、pin/offload、text cache hit、int8-convrot VAE、compiler/TAEH3 品質 gate。OmniRef PDD-8 的 Blackwell-only／103-GiB 峰值資料不列為 L4 候選。 

## Sources

- S1 [FastVideo-Minimax-FastH3-Preview-v0.2 model card, README commit `d0b052d`](https://huggingface.co/FastVideo/FastVideo-Minimax-FastH3-Preview-v0.2/blob/d0b052d148db3d24fb39b702087f206484c30269/README.md)
- S2 [FastH3 8-Step V2 README](https://huggingface.co/FastVideo/FastVideo-FastH3-8-Step-V2/blob/main/README.md)；[FastVideo basic_fasth3.py](https://github.com/hao-ai-lab/FastVideo/blob/2b164405c3d15ed2d222d0582d6db09ffc5ee6b2/examples/inference/basic/basic_fasth3.py)
- S3 [FastVideo PR #1919](https://github.com/hao-ai-lab/FastVideo/pull/1919)
- S4 [FastVideo SM89 sparse INT8 source](https://github.com/hao-ai-lab/FastVideo/blob/2b164405c3d15ed2d222d0582d6db09ffc5ee6b2/fastvideo/attention/backends/minimax_h3_sparse_int8.py)
- S5 [comfy-kitchen PR #117](https://github.com/Comfy-Org/comfy-kitchen/pull/117)
- S6 [comfy-kitchen PR #90](https://github.com/Comfy-Org/comfy-kitchen/pull/90)；[Kijai MiniMax-H3-experimental README](https://huggingface.co/Kijai/MiniMax-H3-experimental/blob/d8023be02fefbb3633b0cd335c3879f91177299d/README.md)
- S7 [FastVideo offloading](https://github.com/hao-ai-lab/FastVideo/blob/2b164405c3d15ed2d222d0582d6db09ffc5ee6b2/docs/inference/offloading.md)；[Comfy pinned-memory issue #14250](https://github.com/Comfy-Org/ComfyUI/issues/14250)
- S8 [FastVideo optimizations / compile](https://github.com/hao-ai-lab/FastVideo/blob/2b164405c3d15ed2d222d0582d6db09ffc5ee6b2/docs/inference/optimizations.md)；[DiffSynth H3 tiled VAE](https://github.com/modelscope/DiffSynth-Studio/blob/main/docs/en/Model_Details/MiniMax-H3.md)
- S9 [ComfyUI H3 VAE source](https://github.com/Comfy-Org/ComfyUI/blob/a4b5a045e56fc334903db8457b728b64e006119c/comfy/ldm/minimax/vae.py)；[H3 VAE tiling issue #15453](https://github.com/Comfy-Org/ComfyUI/issues/15453)
- S10 [ComfyUI speed/cache node](https://github.com/linjian-ufo/comfyui-speed-minimaxH3)；S11 [Comfy-H3-MultiStream measurements](https://github.com/martonsagi/Comfy-H3-MultiStream)
- [MiniMax official H3 README](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/README.md)；[Comfy official FastH3 docs](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/minimax/minimax-h3-fastvideo.mdx)；[Comfy native Ref2VA docs](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/minimax/minimax-h3-native.mdx)

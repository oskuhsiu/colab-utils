# 後製工作流：VSR、插幀與補音訊證據

查核日：2026-10-10。只讀公開 web/HTTP；未登入、未安裝、未下載權重、未啟動 GPU。本檔只補「低／中資源生成後，是否可用獨立後製提升」的可執行契約：FlashVSR／v1.1、SeedVR2 3B／7B、Real-ESRGAN、RIFE，以及 MMAudio 影片補音訊。L4 24GB、A100 40GB、A100 80GB 與高 RAM／CPU offload 分開記錄；來源若是 RTX4090、H100、2080Ti 等，只保留原始條件。

## Answer

第一手資料顯示，後製主要分成三種不同工作：空間／時序影片修復、插幀、以及獨立補音訊。它們的輸入輸出與失敗模式不能混為同一個「升級」步驟。

- FlashVSR 官方 v1.1 是 one-step、主要針對 4× 的影片 VSR；官方單 A100 報 768×1408 約 17 FPS，Block-Sparse Attention 在 A100/A800 有理想加速，L4 fallback／性能沒有官方確認。官方 full script 目前會 scale=4、把目標尺寸向下取 128 倍數並中心裁切，且依 `8n+1` frame contract 加尾幀後可能截斷原片尾；這是可改變 framing／時長的實際風險。FlashVSR-Pro 是獨立重寫版，作者宣稱支援 tiled low-VRAM、保留音軌、反射 padding 以維持精確 duration/resolution，但它不是官方實作，沒有本檔 target GPU 實測。
- SeedVR2 官方 3B／7B 是單步 diffusion video restoration。官方只給 1×H100-80G 可處理約 100×720×1280、4×H100 可到 1080p/2K，並明示大動作／重劣化、輕劣化 AIGC 720p／480p 會失敗或過度銳化。官方 Comfy wrapper 的 batch_size=1 是低 VRAM 路徑，batch_size≥5 才開 temporal consistency；BlockSwap 以 CPU 記憶體換 VRAM。wrapper 的 4090 24GB 與 H100 93GB 表是作者測量，沒有 L4/A100 表。
- SeedVR2-lite 是獨立社群工具，不是 ByteDance 官方 wrapper。其 README 給出 3B FP8 最低 8GB、7B FP8 12GB、3B FP16 16GB、7B FP16 24GB，並列出約 RAM、BlockSwap 與解析度成本；這是作者的真機／工具聲明，不等於官方模型 card 的 L4 qualification。它的 FP8 主要是權重儲存格式，README 聲明 FP8/FP16 推理速度近似，BlockSwap 與解析度／帧數才主導成本。
- Real-ESRGAN 官方 Python／video script 是低資源、逐幀型路徑：x4plus、realesr-animevideov3 等模型，支援 tile、arbitrary `outscale`、FP16 default 與 CPU／NCNN executable。官方 video script 會讀 input FPS、frame count、audio stream，輸出以 `width*scale`／`height*scale` 寫出並 `acodec=copy`，所以可保留原音軌；它沒有 temporal restoration，frame-to-frame consistency、臉部細節漂移與閃爍需要自行驗證。
- RIFE 官方支援 `--exp=1` 2×、`--exp=2` 4×，作者以 2080Ti 報 720p 2× 30+ FPS；4K 可把 flow processing `--scale=0.5`，產生錯亂 pattern 時可試 `scale=2.0`。官方 `--fps=60` 路徑明示會移除 audio。RIFE issue 有 dissimilar frames 導致大批中間幀重複的實例；不能把插幀當動作／身份修復。
- MMAudio 是獨立影片補音訊模型，不會改畫面。官方 large_44k_v2 16-bit inference 約 6GB GPU、預設 8 秒、25 steps；輸入 video+prompt，輸出 FLAC，demo 另用 `make_video` 合成 MP4。輸入會被 CLIP resize 到 384×384、Synchformer resize/crop 到 224 shorter edge、低於 25 FPS 時複製幀，故要記錄輸入 FPS／duration；官方列出人聲不可辨、背景音樂誤生成與陌生概念失敗。程式 MIT、checkpoint CC-BY-NC 4.0。

## Source evidence table

| ID／工具與版本 | 輸入→輸出／scale／frames | L4 24GB | A100 40/80／H100 | Host RAM／offload／tiling | 時間證據 | 音軌與失敗 |
|---|---|---|---|---|---|---|
| POST01 FlashVSR v1.1 official | 主要 4×；官方 full script 128-pixel target grid、center crop、`F=largest_8n1_leq(N+4)`，fps 取 input | 未知；Block-Sparse L4 compatibility/performance 未確認 | A100 768×1408 約 17 FPS；A100/A800 backend ideal，H200 limited | Full script `tiled=False` higher VRAM；`tiled=True` lower VRAM/slower；RAM 未列 | 17 FPS 是作者 A100 claim，非 Colab/Wan 端到端 | Official script only writes frames/video，未做 audio copy；官方 quality note 指 no-LCSA third-party 會有 alias/artifact |
| POST03 FlashVSR-Pro community fork | `--scale` default 2、官方原作建議 4；reflective padding 宣稱 exact scale/res；frames/duration exact claim | 作者寫 8GB low-res tiled、16GB+ high quality、24GB+ 4K；無 L4 run | A100/H100/H200 optimizations claimed；無 40/80 table | host RAM 16GB+；tile-DiT default 256 overlap24、tile-VAE；NVENC | 無公開 target GPU wall-time | `--keep-audio`；exact duration/res 是作者 claim；fork 非官方，需防 tile seam／quality drift |
| POST04 SeedVR2 official 3B/7B | arbitrary output `res_h/res_w`；area resize（可 upscale）、DivisibleCrop(16,16)；按 `4*sp_size` padding，output trim 回 original length | 未知 | 1×H100-80G 可 100×720×1280；4×H100-80G 到 1080p/2K | `dit_offload=True`；VAE/DiT CPU swapping；host RAM 未列 | 無 FPS；one-step model | 官方 script writes via mediapy，未保留 input audio；heavy degradation/large motion failure、720p/480p light degradation oversharpen |
| POST06 ComfyUI SeedVR2 wrapper | 3B/7B FP16/FP8；`new_resolution` short edge；batch_size 1/5/9…；輸入／輸出 resolution 皆影響 VRAM | 作者說 <24GB 用 batch 1、preserve_vram；未給 L4 | H100 93GB：3B FP8 149f 854×480→1920×1080 361.22s/0.41 FPS；7B表同卡；4090 24GB 有 3B/7B 5-frame rows | BlockSwap 0–32（3B）/0–36（7B），CPU swap；batch≥5 temporal consistency，較高 batch 增加 VRAM | 4090/H100 author benchmark；無 A100 40/80 | README 無 audio handling；7B FP8 曾有 quality issue，3B/7B output all VRAM/OOM risk |
| POST07 SeedVR2-lite v1.5.8 community | video/image SR；3B/7B/7B-Sharp；FP16/FP8/INT8-convrot/MXFP8/NVFP4；resolution cost | 3B FP8 ≥8GB，7B FP8 ≥12GB，3B FP16 ≥16GB，7B FP16 ≥24GB（author table） | 未給 A100/H100 timing | 約 RAM 8/12/12/20GB；BlockSwap；2048² 約比1024²慢3–4×；FP8 storage，不代表更快 | 無同條件 video wall-time | FFmpeg 需另裝；無 audio preservation claim；第三方工具，不是 ByteDance 官方 |
| POST08/09 Real-ESRGAN official | x4plus／anime-v3／x2plus；Python `outscale` 任意終尺，NCNN `-s` 2/3/4；逐幀 video script | 低資源路徑，無 L4 peak | 無 A100 table | tile 可拆畫面；FP16 default；NCNN 無 CUDA/PyTorch | 無官方 video wall-time；Colab/demo available | video script probes fps/audio/frame count、輸出 audio `copy`；NCNN tile stitching 可能 block inconsistency；逐幀無 temporal consistency |
| POST10 RIFE | `exp=1` 2×、`exp=2` 4×；`--scale=0.5` 4K；`--fps=60` | 未列 VRAM | 無 A100 table；作者 2080Ti 720p 2× 30+ FPS | scale 控制 flow processing resolution | 30+ FPS 是 2080Ti author claim | `--fps=60` audio removed；高解析 disordered pattern；issue #185 報 63 identical intermediate frames |
| POST11/12/13 MMAudio | video+prompt→audio；default 8s、25 steps；CLIP 384² crop、Sync 224 crop、低於25fps複製幀 | 約6GB GPU 16-bit（官方） | 無 A100/L4 split | Host RAM 未列；higher-res decode/encode 可佔 >95% processing；duration大幅偏離8s quality↓ | 無 GPU wall-time；官方 paper摘要曾報 H100 8s約1.23s，非本地 demo measured | demo saves FLAC + composites MP4；known unintelligible speech/music/unfamiliar concepts；audio checkpoint CC-BY-NC |

## Input/output and failure details

### FlashVSR v1.1 exact script behaviour

The pinned official script sets `scale=4`, computes `sW=w0*scale`, `sH=h0*scale`, floors target dimensions independently to 128 multiples, bicubic-resizes and center-crops. Thus 320×176 becomes 1280×640 (1280×704 intermediate), while 640×352 becomes 2560×1408. It appends four copies of the last frame, sets `F=largest_8n1_leq(N+4)`, truncates the index list to `F`, and writes `fps` from the input video. The print label `Target Frames (8n-3): F-4` is a label, not a proof that the saved tensor has `F-4` frames. No post-inference trim is present in the full script. This can drop original tail frames for some `N`; exact output PTS/frames require a separate probe.

FlashVSR-Pro documents a different contract: reflective padding rather than crop, exact output frame count and resolution scale, `--keep-audio`, `--tile-dit`, `--tile-vae`, `--scale`, `--fps`, and `--color-fix`. Those are fork-author claims and should not be assigned to official v1.1. The official README also warns that third-party implementations without LCSA can have noticeable high-resolution quality degradation.

### SeedVR2 temporal and spatial contracts

The official script area-resizes to `res_h*res_w` (including upsample because the model is trained at high resolution), crops to 16-pixel divisibility, pads temporal length to `(t-1) % (4*sp_size)==0`, and later trims samples back to `ori_length`. The Comfy wrapper uses `batch_size=1` without temporal consistency and recommends at least 5 for temporal consistency; larger batches use more VRAM. The wrapper writes video/PNG but does not document carrying an input audio stream.

### Audio preservation / replacement

- Real-ESRGAN official video code copies the input audio stream (`acodec='copy'`) while writing upscaled frames and input FPS; this preserves an existing audio track but does not synthesize a missing one.
- FlashVSR-Pro adds an explicit `--keep-audio` mux path. Official FlashVSR v1.1 does not.
- RIFE 的 explicit `--fps=60` 路徑跳過原音軌合併；主代理讀到官方 `inference_video.py` 的預設 `--exp` 路徑（未指定 `--fps`、video輸入且非PNG）會在插幀後嘗試 `transferAudio`，先copy、不成功再AAC。不能把「所有2×／4×都掉音」或「沒有內建mux」當成結論；container／ffmpeg失敗時仍可能掉音。
- MMAudio generates a new synchronized audio track from video and/or prompt; `demo.py` saves `.flac` and calls `make_video` for a composited `.mp4`. It is semantic audio synthesis, not preservation of original audio.

## Failure / unknown / search boundary

- No source in this lookup provides a paired L4 24GB, A100 40GB and A100 80GB benchmark using the same 320×176 or 640×352 source, same frames/fps, same crop, same output quality checks, and same audio mux.
- FlashVSR official block-sparse attention is confirmed by its authors on A100/A800 and limited on H200; L4 behavior is unknown. FlashVSR-Pro says Ampere+ and 8GB tiled minimum, but this is a community implementation claim without L4 run logs.
- SeedVR2 official resources are H100-heavy. The Comfy wrapper has H100 and RTX4090 tables but no A100/L4 table; `batch_size=5` temporal consistency may exceed a 24GB path even when batch 1 runs.
- SeedVR2 and RIFE can change motion appearance rather than repair identity: SeedVR2 may invent/oversharpen details or fail under large motion; RIFE can produce repeated/interpolation failures on dissimilar frames. “Sharper” is not evidence of identity or motion consistency.
- Real-ESRGAN is framewise; no official temporal consistency or low/mid wall-time evidence was found. Its audio copy path preserves audio but does not correct timing if upstream PTS are already wrong.
- RIFE explicit FPS／PNG 路徑不會自動合併原音；預設exp/video路徑自帶audio-transfer但可能失敗。High-resolution flow scaling can create disordered patterns. Ghosting/repeated frames and crop/time drift require post-run probe and visual QA.
- MMAudio is limited to a default 8s training regime, central crops input conditioning, duplicates low-FPS frames, and may output unintelligible speech or background music. Its weights are CC-BY-NC 4.0; this is separate from source video/model licenses.
- Search did not find a primary, downloadable standalone Real-ESRGAN or RIFE workflow that reports L4/A100 host RAM and wall-time for the exact target clips. Search did not find a first-party SeedVR2 audio mux contract.

## Sources

Detailed claims are mirrored in `10-postproduction-workflows.json`.

- **POST01** — [OpenImagingLab/FlashVSR README](https://github.com/OpenImagingLab/FlashVSR/blob/main/README.md), official v1/v1.1 release, 4× recommendation, A100 17 FPS, A100/A800 sparse backend and third-party LCSA quality warning.
- **POST02** — [FlashVSR v1.1 full script](https://github.com/OpenImagingLab/FlashVSR/blob/main/examples/WanVSR/infer_flashvsr_v1.1_full.py), official resize/crop/frame-padding/fps/output contract.
- **POST03** — [FlashVSR-Pro](https://github.com/LujiaJin/FlashVSR-Pro), independent Apache-2.0 fork with tiling, exact duration/resolution and audio-preservation claims.
- **POST04** — [ByteDance-Seed/SeedVR README](https://github.com/ByteDance-Seed/SeedVR/blob/main/readme.md), official SeedVR2 3B route, H100 resources and prototype limitations.
- **POST05** — [SeedVR2 3B inference script](https://github.com/ByteDance-Seed/SeedVR/blob/main/projects/inference_seedvr2_3b.py), official area-resize, 16-grid crop, 4n+1 padding, length trim and FPS/output behavior.
- **POST06** — [ComfyUI SeedVR2](https://github.com/comfyorg/comfyui_seedvr2), official Comfy integration, model list, BlockSwap, batch/temporal contract and H100/RTX4090 benchmarks.
- **POST07** — [SeedVR2-lite v1.5.8](https://github.com/ReSerendipity/SeedVR2-lite), independent third-party tool with 3B/7B precision, RAM/VRAM, BlockSwap and resolution cost claims.
- **POST08** — [Real-ESRGAN README](https://github.com/xinntao/Real-ESRGAN), official models, arbitrary outscale, tile, FP16 and video/Colab entry points.
- **POST09** — [Real-ESRGAN video script](https://github.com/xinntao/Real-ESRGAN/blob/master/inference_realesrgan_video.py), official input FPS/audio probe and `acodec=copy` output mux.
- **POST10** — [ECCV2022-RIFE README](https://github.com/hzwer/ECCV2022-RIFE), official 2×/4× CLI, 2080Ti 30+ FPS claim, high-resolution scale controls and audio-removal note.
- **POST11** — [RIFE issue #185](https://github.com/hzwer/ECCV2022-RIFE/issues/185), firsthand report of repeated identical intermediate frames for dissimilar endpoints.
- **POST12** — [MMAudio official README](https://github.com/hkchengrex/MMAudio), MIT code/CC-BY-NC weights, 6GB 16-bit memory, 8s duration, crop/FPS/failure limitations and video-to-audio contract.
- **POST13** — [MMAudio official demo script](https://raw.githubusercontent.com/hkchengrex/MMAudio/main/demo.py), 25-step CLI, audio FLAC save and MP4 composition.
- **POST14** — [ComfyUI-MMAudio](https://github.com/kijai/ComfyUI-MMAudio), downloadable custom-node path and model/workflow location.

- **POST15** — [RIFE inference_video.py](https://github.com/hzwer/ECCV2022-RIFE/blob/main/inference_video.py)（主代理核查：`fpsNotAssigned`與`transferAudio`條件、預設exp路徑的copy/AAC fallback；不概括成全部插幀流程掉音）。

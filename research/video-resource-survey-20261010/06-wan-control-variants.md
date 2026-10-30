# Wan 控制變體與長片衍生：VACE／Animate／Fun／Audio／SVI

查核日：2026-10-10。這份分題只收 Wan 控制與長片衍生：VACE 1.3B/14B、Wan-Animate、Wan2.2-Fun Control/Camera/VACE-Fun、InfiniteTalk、MultiTalk、SVI 與 ComfyUI 延續節點。只讀公開 web/HTTP；未登入、未安裝、未下載權重、未啟動 GPU，也沒有把其它 GPU 的結果換算成 L4 或 A100。

## Answer

目前沒有找到一組在相同 prompt、seed、解析度、frames、precision、VAE、steps、offload 與 workflow 下，直接比較單張 L4 24GB、A100 40GB、A100 80GB 的控制／長片成片品質與時間。可用的直接邊界證據如下：

- **低資源（單 L4 24GB）**：沒有找到 Wan 控制或長片變體在單 L4 的完整一手成片 benchmark。最接近的 VACE-1.3B 實測是 A10G 24GB：480p、81 frames、5 秒，19GB VRAM，作者後來確認至少約 21GB 主機 RAM，完成時間約 15 分鐘（CTRL05）；這不能改寫成 L4 結果。Wan2.2-Fun-5B-Control 的作者只列約 23GB 權重磁碟大小與 121 frames／24fps 訓練契約，沒有單 L4 wall time/peak VRAM（CTRL09、CTRL13）。MultiTalk 官方只明示「低 VRAM」480p 單 RTX4090 路徑，沒有 L4 數字（CTRL21）。
- **中資源（單 A100 + High RAM）**：MultiTalk 官方寫多人物效率結果是在 A100 評估，但數值藏在圖片，README 沒提供可核對的單卡時間／峰值；它只明示單 GPU 當前程式支援 480p、720p 需多 GPU（CTRL21）。SVI 官方 Wan2.1 分支環境以 A100 80G 測試，但沒有把 wall time、host RAM 或 peak VRAM 拆出（CTRL25）；Wan2.2 分支明示單 `CUDA_VISIBLE_DEVICES=0` 的 50 clips／250 秒流程，但同樣沒有 GPU 型號或記憶體數字（CTRL26）。InfiniteTalk 的 A100 40GB／50GB RAM 社群 issue 報 10 秒影片需 17 小時（量化路徑，CTRL19），說明可以啟動不代表可接受吞吐。
- **14B 控制 checkpoint provenance 是硬條件**：VACE-14B 不是把任意 Wan I2V／T2V 權重名稱換掉即可；Kijai 的一手 issue 明確指出 VACE module 應與 T2V 配對。作者使用 I2V base 時雖以 block swap 壓到 24GB、約 89% VRAM，結果是綠噪聲／像素化；改成配對 T2V 後才表示修正（CTRL07）。Wan-Animate 官方也明確不建議把一般 Wan2.2 LoRA 套到 Animate，可能出現未預期行為（CTRL14）。

以下硬體欄位以 `A100-40`、`A100-80` 分列；host RAM、磁碟、offload 只有來源明示才填。RTX4090／A10G／其它卡保留為原始條件旁證，不外推。

## Evidence matrix

| 候選與來源 | 精確輸入／控制契約 | 權重修改與 preprocessing | 來源明示資源／設定 | 明示失敗或品質限制 | 音訊狀態 |
|---|---|---|---|---|---|
| **VACE-1.3B / VACE-14B**（CTRL01–08） | VACE 將 `src_video`、`src_mask`、`src_ref_images`、prompt 組成可編輯條件；支援 depth/flow/gray/pose/scribble、bbox/layout track、first/last/first-last frame、first/last/first-last clip、inpaint/outpaint。白 mask 代表生成、黑代表保留；reference image 可用於 R2V。 | 官方 `vace_preprocess` 用 DepthVideoAnnotator、Flow、PoseBodyFace、Scribble、Layout、FrameRef 等 annotator；`vace_wan_inference.py` 有 `--size`、`--frame_num`（預設 81，要求 4n+1）、`--offload_model`、`--t5_cpu`、`--sample_steps`、shift、CFG。14B/1.3B 是不同 VACE checkpoint，不能與 stock I2V 任意互換。 | 1.3B 約 480P；14B 支援 480P/720P。A10G 24GB 480P/81f/5s 的一手作者記錄約 19GB VRAM、RAM 至少 21GB、約 15 分鐘；未提供 L4/A100。VACE 14B 的 24GB block-swap issue 是社群修正流程，不是官方 benchmark。 | 官方 UserGuide 說超長影片會 trim/uniform sample 到約 5 秒，建議逐段 5 秒並用 `firstclip` extension 維持時間一致；1.3B issue 有物件嚴重變形；14B 錯配 I2V 時一手報綠噪聲／像素化。 | 無原生音訊生成契約；VACE 輸入／輸出是視覺 video editing。 |
| **Wan-Animate-14B**（CTRL09、CTRL14–16） | 兩種模式：animation（character image 模仿 driving video 的人體動作）與 replacement（以 character image 替換 driving video 中人物）。輸入是 driving video + reference character image；replacement 另需 background/mask。 | preprocessing 需要 YOLOv10m、ViTPose wholebody；replacement 可加 SAM2；animation 可加 pose retargeting 與 FLUX.1-Kontext-dev。產生 `src_face.mp4`、`src_pose.mp4`，replacement 另產 `src_bg.mp4`、`src_mask.mp4`。官方 single-GPU command 有 `--refert_num 1`，replacement 可 `--use_relighting_lora`。 | 官方未給單 L4/A100 數字或 VRAM floor；只公開 single-GPU command 及 8-GPU FSDP/Ulysses command。解析度以 `resolution_area` 控制；fps 可降以提高效率但可能卡頓。 | 官方 preprocess guide 明示 retargeting 不保證完美；body proportion 不匹配會 artifact/deformation；replacement mask extraction 僅設計給 single-person，multi-person 可能錯；mask 太小會 shape leakage，太大會破壞背景一致性。一般 Wan2.2 LoRA 不建議套 Animate。 | 無原生音訊；輸入／輸出以視覺 driving video 為主。 |
| **Wan2.2-Fun-A14B-Control**（CTRL09–13） | 14B Control checkpoint 支援 Canny、Depth、Pose、MLSD、trajectory；Comfy workflow 使用 reference/start image + 預處理 control video。官方 Python control script 的 `control_video` 是 video-to-video condition。 | VideoX-Fun 提供 high-noise/low-noise Control 權重；Comfy 對應 high/low FP8-scaled diffusion files。Lightning 4-step LoRA 也必須 high/low 成對；官方 Comfy docs 明示 pair 不可混。其它 depth/pose 等通常先由 controlnet_aux 或外部 annotator 預處理。 | 作者描述 A14B 為 512/768/1024 多解析度、81 frames、16fps。Comfy 官方 4090D 24GB 640×640/81f：FP8 83% VRAM，首/二次約 524/520s；加 4-step LoRA 89%，約 138/79s。這是 4090D 旁證，不是 L4/A100。 | 官方 docs 明示 4-step LoRA 可能減少 dynamics；預設 640×640 是為了避免低 VRAM 使用者處理時間過長；control video 範例是已預處理素材。沒有 identity/服裝保持率、fixed-seed paired score。 | 無原生音訊。 |
| **Wan2.2-Fun-A14B-Control-Camera**（CTRL09–13） | Camera checkpoint 讀 `control_camera_txt`，每幀相機內參與 3×4 pose 轉成 Plücker embedding；官方工具列出 static、pan、zoom、ACW/CW 等鏡頭路徑。輸入可含 start image。 | 與 A14B Control 分開的 camera checkpoint，不是 generic Control LoRA。官方 script 預設 480×832、81f、16fps、bf16、50 steps、CFG 6；480p 建議 shift 3，720p shift 5。 | 作者列 512/768/1024、多 81f/16fps；沒有單 L4/A100 timing。Comfy 4090D 控制 workflow 的 640×640 metrics 可作同家族 camera/control 的外部旁證，但不可改寫成 camera 專項結果。 | 沒有 camera trajectory fixed-seed quality table；未找到相機控制的 identity/cloth/long-drift 受控評估。 | 無原生音訊。 |
| **Wan2.2-VACE-Fun-A14B**（CTRL09、CTRL12） | VACE scheme 的 Wan2.2 control weights，支援 Canny、Depth、Pose、MLSD、trajectory，並支援以 subject/reference image 指定生成；HF card 另列 generic control video + reference image demos。 | HF front matter 的 base model 是 `Wan-AI/Wan2.2-T2V-A14B`；模型是 VACE-Fun control weights，與普通 Fun Control／stock A14B checkpoint 分開。 | 作者列約 64GB 權重存儲、512/768/1024、81f/16fps、多語；沒有低／中 GPU wall time、peak VRAM、host RAM。 | 沒有 identity preservation score 或與 A14B-Control 的同 seed comparison；不能以檔案大小推導品質。 | 無原生音訊。 |
| **InfiniteTalk**（CTRL17–20） | audio-driven video-to-video 與 image-to-video；`mode=streaming` 長片，`mode=clip` 單 chunk；motion frame 預設 9，`max_frame_num` 預設 1000（約 40 秒上限參數）。V2V 可模仿原片 camera movement；I2V 單圖約 1 分鐘內較好。 | 必須配 `Wan2.1-I2V-14B-480P` base + `chinese-wav2vec2-base` + `MeiGen-InfiniteTalk` single/multi condition weights。可用 FP8 quant，或 FusionX 8-step／LightX2V 4-step；`num_persistent_param_in_dit=0` 為 very-low-VRAM mode。 | 官方支援 480/720p、single GPU；沒有官方單 L4/A100 timing。24GB RTX4090 5s/720p/40 steps 路徑跑 1:50:58 後在 VAE decode OOM（21.61GiB used、23.52GiB total、267GB RAM）；另一 4090 24GB 480p 10s、8 steps、no LoRA 需 40 分鐘；A100-40 + 50GB RAM issue 報 10s 需 17h。 | 官方明示 FusionX 會使 1 分鐘後 color shift 加劇並降低 ID preservation；V2V 長片 camera 不完全複製，SDEdit 可改善但引入 color shift；I2V 超過 1 分鐘 color shift 變明顯。 | **外部音訊驅動／mux**：Wav2Vec2 只產 audio embeddings，最後用 `save_video_ffmpeg(..., [input_data['video_audio']])` 將輸入/產生的 wav 寫入影片；不是模型原生產生音軌。 |
| **MultiTalk**（CTRL21–24） | reference image + prompt + single/multi-stream audio；支援 single/multi-person、singing、cartoon、480/720p。官方提示最佳 81 frames @25fps，可到 201f 但 prompt following 可能下降；streaming 可接長片。 | 必須把 `MeiGen-MultiTalk` condition weights link/copy 到 `Wan2.1-I2V-14B-480P` directory；另需 Wav2Vec2、可選 Kokoro TTS。支援 INT8 quant、`num_persistent_param_in_dit=0`、TeaCache、FusionX 8-step／LightX2V 4-step。 | 官方明示 current code 單 GPU 僅 480p；720p 需多 GPU。低 VRAM 480p 單 RTX4090；A100 用於 multi-person efficiency 圖，沒有文字版數值。提供 A100 Colab link，但 notebook 需登入才可讀。 | 官方提示較多 steps 提高 motion/visual quality，低至 10 steps 可能保 lip-sync 但降低 motion/visual quality；20+ 秒社群 issue 回報 face distortion + color drift；兩 A100 與單 A100 的速度問題有未量化 issue。 | **外部音訊驅動／mux**：localfile 或 Kokoro TTS 先存 wav、產 embeddings，最後把 `input_data['video_audio']` 傳給 ffmpeg 保存；非原生音軌生成。 |
| **TalkVerse-5B**（CTRL30–31） | image + audio + prompt；官方 inference task 為 `s2v-5B`，batch script 可設 `INFER_FRAMES=120`、CFG 6.5。論文評估 40 秒、25fps、1000 frames；支援 zero-shot dubbing 與音訊/視覺 prompt director。 | 不是通用 LoRA：TalkVerse-5B 是在 Wan2.2-TI2V-5B 上訓練的 audio-driven LoRA，另需 Wav2Vec2-large-xlsr-53-english；paper 描述 (t,h,w)=(4,16,16) VAE、FramePack motion-context 與 reference-image positional embedding 的 sliding-window 長片契約。 | 官方只說 `--offload_model True --t5_cpu` 可替 consumer GPU（例如 RTX4090），沒有 L4/A100 runtime/peak RAM；paper 作者主張約 10× lower inference cost than 14B Wan-S2V，並用 40s/1000f 評估。 | Paper 明示 5B 對 complex/extreme hand articulation/full-body motion 可能較弱；5B full fine-tuning 更易產 artifact，LoRA 優於 full tuning。沒有同 seed 與 Wan-S2V/MultiTalk 的硬體 paired table。 | **外部音訊輸入／mux**：generate.py 讀 audio，完成後 `merge_video_audio`；模型用 Wav2Vec2 作 condition，不是獨立 native soundtrack generator。 |
| **SVI 2.0／SVI 2.0 Pro（Wan2.1 / Wan2.2）**（CTRL25–29） | SVI 是 LoRA-based long-video continuation：image + prompt stream → multiple clips。Wan2.2 branch 的官方命令是 `height=832,width=480,fps=15,num_clips=50`（250 秒）、`cfg_scale=4`、`num_overlap_frame=5`、`num_motion_latent=1`；SVI-Shot/Film/Talk/Dance 另有 audio/skeleton 路徑。 | Wan2.2 branch 明列 high-noise/low-noise SVI LoRA pair，base 是 Wan2.2-I2V-A14B；另有 SVI 2.0 Pro pair。官方特別說不同 PyTorch 版本即使同 seed 也會出不同結果，Comfy workflow 不可直接沿用原 Wan2.1 workflow；SVI LoRA 與 LightX2V LoRA 有 conflict 註記。 | Wan2.1 repo 的 reproduction environment 用 A100 80G，但無 timing/peak RAM；Wan2.2 branch 使用單 `CUDA_VISIBLE_DEVICES=0`，無 GPU 型號、VRAM、RAM 或 wall time。 | SVI 官方宣稱 long video temporal consistency／cross-clip consistency，保留為作者 claim；社群 SVI-Pro-FLF node 回報 VAE seam 可能 ghost/double，需要 overlap slider，短 clip 可能來不及觸發動作而 drop action。WanExtended 社群 demo 是 403f、24fps、720p（三段 161+161+81），但無硬體與時間。 | SVI base path 本身可接 SVI-Talk audio 或 SVI-Dance skeleton；純 SVI 2.0/Pro image+prompt 路徑無原生音訊。 |

## Hardware and measurement rows

| 資源欄位 | 可直接引用的數字 | 可支持的範圍 |
|---|---|---|
| L4 24GB | 本分題沒有單 L4 控制／長片完整實測。VACE A10G 24GB 480p/81f/5s：19GB VRAM、RAM 約 21GB、約 15 分鐘；Fun 5B 只有 23GB 權重磁碟契約；MultiTalk 只有 RTX4090 low-VRAM 宣告。 | 只能說 L4 direct evidence gap 仍在；不能把 A10G/4090 time 換算 L4。 |
| A100-40 | InfiniteTalk issue：A100 40GB + 50GB RAM、量化模型，10 秒影片約 17 小時。 | 來源作者自報且未給完整 steps/precision/log；是吞吐警示，不是合格 benchmark。 |
| A100-80 | SVI Wan2.1 repo 的環境已以 A100 80G 測試；MultiTalk README 明示 A100 efficiency evaluation；兩者沒有可讀的單卡 peak/time 表。 | 可標記「A100-80 相容性／作者環境」，不能聲稱速度或品質。 |
| RTX4090/A10G 旁證 | Fun Control 4090D 640×640/81f：約 524/520s FP8，138/79s 4-step LoRA；InfiniteTalk 4090 24GB 480p/10s/8 steps/no LoRA 約 40min；VACE A10G 24GB 480p/81f 約 15min。 | 只作近似 VRAM 路徑與 failure boundary 的原始條件，不能推論 L4 或 A100。 |

## Explicit provenance / quality notes

- VACE 1.3B/14B 是 VACE-specific checkpoints；官方支持的 conditions 是 `src_video`、mask、reference image 與 preprocess annotators。VACE UserGuide 的長片指引是 5 秒 clip + `firstclip` extension，不是一次丟任意長片。
- Wan2.2-Fun Control、Camera、VACE-Fun 各自是不同 weight family。Control/Camera 使用 high-noise/low-noise model pair；Comfy 4-step LoRA 也要求 high/low 對應。不要把普通 Wan I2V LoRA、Wan-Animate LoRA、SVI LoRA、VACE module 互相視為通用 adapter。
- InfiniteTalk/MultiTalk 的 audio embedding model、audio condition weights、base Wan checkpoint 都是分離資產；audio 是外部輸入，最後由 ffmpeg mux。這些模型的「native audio」應記成 false，避免與能直接生成音訊的其它 Wan family 混淆。
- SVI 2.0 Pro 的 Wan2.2 branch 是 high/low SVI LoRA 對；其官方 250 秒命令可核查 overlap/motion latent，但沒有 GPU/RAM/time。這是長片方法與 weight contract 證據，不是低／中資源 benchmark。

## Unknown / Search boundary

- 未找到同一固定 seed／prompt／input control／resolution／frames／steps 的 Wan VACE、Fun Control、Camera、Animate、InfiniteTalk、MultiTalk、SVI 在單 L4、A100-40、A100-80 的 paired quality/time/VRAM/RAM 表。尤其缺人物 identity、服裝、動作因果、顫動、long drift、lip-sync 的受控分數。
- 未找到 Wan-Animate 在單 L4 或單 A100 的可讀 peak VRAM／wall time；官方只給 single-GPU command與 preprocessing contract，HF 的 efficiency table是圖片嵌入，本文沒有把未直接讀取的圖片數字當證據。
- 未找到 Fun Control/Camera 5B 在 L4/A100 的 wall time、host RAM、peak VRAM、fixed-seed quality；23GB 是作者的權重存儲表述，不等於 VRAM requirement。
- TalkVerse-5B 有 Wan2.2-TI2V-5B + audio LoRA + Wav2Vec2 的完整 weight contract，以及 40s/1000f 論文評估，但沒有 L4/A100 wall time、peak VRAM 或 host-RAM row；「10× lower inference cost」是作者相對 Wan-S2V-14B 的論文 claim，不是本次指定硬體測量。
- A100-40/80 的 High RAM 定義需與來源 host RAM 分開；沒有來源明示的 host RAM 一律留 null。A100-40 issue 的 50GB RAM 是作者機器條件，不能移植到 Colab High RAM 的實際可用容量。
- 外部社群的 RTX4090、A10G、3090、5070、H100/H200、L40S、5090 只保留原始條件；不做硬體比例推算。SVI/WanExtended 的 MP4/demo links 是 artifact availability，不是品質驗收。
- 搜索範圍未包含已由 04 報告覆蓋的 Wan 核心少步／量化、其它非 Wan 模型、訓練成本、商用 API 及需要登入才能下載的 Colab cell 內容；A100 Colab link 的可見性被登入牆阻斷。

## Sources

CTRL01 — [ali-vilab/VACE README](https://github.com/ali-vilab/VACE/blob/main/README.md)（官方；VACE 1.3B/14B、480/720P、release dates、模型與流程；checked 2026-10-10）。

CTRL02 — [VACE UserGuide](https://github.com/ali-vilab/VACE/blob/main/UserGuide.md)（官方；src_video/src_mask/src_ref_images、annotators、task contracts、長片約 5 秒與 firstclip 指引；checked 2026-10-10）。

CTRL03 — [VACE Wan inference script](https://github.com/ali-vilab/VACE/blob/main/vace/vace_wan_inference.py)（官方；size/frame_num/offload/T5 CPU/steps/CFG/inputs；checked 2026-10-10）。

CTRL04 — [Wan-AI/Wan2.1-VACE-1.3B model card](https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B)（官方 model card；VACE 480P recommendation與720P stability warning；checked 2026-10-10）。

CTRL05 — [VACE issue #75](https://github.com/ali-vilab/VACE/issues/75)（一手使用者＋maintainer回覆；A10G 24GB、16→32GB RAM、19GB VRAM、480p/81f、約15分鐘；checked 2026-10-10）。

CTRL06 — [VACE issue #101](https://github.com/ali-vilab/VACE/issues/101)（一手使用者；VACE 1.3B default i2v object distortion；checked 2026-10-10）。

CTRL07 — [ComfyUI-WanVideoWrapper issue #562](https://github.com/kijai/ComfyUI-WanVideoWrapper/issues/562)（wrapper maintainer與使用者；VACE14B blockswap、24GB/89%、錯配 I2V 綠噪聲、T2V pairing、350f 4.5h；checked 2026-10-10）。

CTRL08 — [ComfyUI VACE tutorial](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/wan/vace.mdx)（官方 Comfy docs；640×640 first-run recommendation、preprocessed depth/control/reference input、JSON/MP4 artifacts；checked 2026-10-10）。

CTRL09 — [VideoX-Fun README](https://raw.githubusercontent.com/aigc-apps/VideoX-Fun/main/README.md)（模型作者；Fun Control/Camera/VACE-Fun weights、23/64GB storage rows、controls、GPU classes、offload modes；checked 2026-10-10）。

CTRL10 — [VideoX-Fun Wan2.2 control script](https://raw.githubusercontent.com/aigc-apps/VideoX-Fun/main/examples/wan2.2_fun/predict_v2v_control.py)（模型作者；control_video/camera txt inputs、81f/16fps、50 steps、CFG、shift、TeaCache；checked 2026-10-10）。

CTRL11 — [ComfyUI Wan2.2 Fun Control tutorial](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/wan/wan2-2-fun-control.mdx)（官方 Comfy docs；4090D 24GB 640×640/81f FP8 and 4-step timings、matching high/low LoRAs、preprocessed pose video、dynamics caveat；checked 2026-10-10）。

CTRL12 — [Wan2.2-VACE-Fun-A14B model card](https://huggingface.co/alibaba-pai/Wan2.2-VACE-Fun-A14B)（模型作者；base_model、VACE-Fun control/reference demos、64GB storage、81f/16fps；checked 2026-10-10）。

CTRL13 — [VideoX-Fun Comfy Wan2.2 setup](https://github.com/aigc-apps/VideoX-Fun/blob/main/comfyui/wan2_2_fun/README.md)（模型作者；A14B/5B control/camera weight rows、23/64GB storage、JSON workflows；checked 2026-10-10）。

CTRL14 — [Wan2.2 official README](https://raw.githubusercontent.com/Wan-Video/Wan2.2/main/README.md)（官方；Wan-Animate release, animation/replacement commands, no generic Wan2.2 LoRA warning；checked 2026-10-10）。

CTRL15 — [Wan-Animate preprocessing UserGuider](https://raw.githubusercontent.com/Wan-Video/Wan2.2/main/wan/modules/animate/preprocess/UserGuider.md)（官方；pose/mask/Flux preprocess models、retargeting/mask limitations、fps/resolution outputs；checked 2026-10-10）。

CTRL16 — [Wan-Animate preprocess script](https://raw.githubusercontent.com/Wan-Video/Wan2.2/main/wan/modules/animate/preprocess/preprocess_data.py)（官方；YOLO/ViTPose/SAM2/Flux checkpoint paths、resolution/fps/mask params；checked 2026-10-10）。

CTRL17 — [InfiniteTalk README](https://github.com/MeiGen-AI/InfiniteTalk)（模型作者；base/audio/condition weights、480/720p, streaming/clip, low-VRAM/FP8/LoRA settings, long drift limitations；checked 2026-10-10）。

CTRL18 — [InfiniteTalk issue #187](https://github.com/MeiGen-AI/InfiniteTalk/issues/187)（一手使用者；RTX4090 24GB/267GB RAM 720p 5s 40 steps, 1:50:58 to VAE OOM, 23.52GiB total；checked 2026-10-10）。

CTRL19 — [InfiniteTalk issue #169](https://github.com/MeiGen-AI/InfiniteTalk/issues/169)（一手使用者；A100-40 + 50GB RAM, quantized path, 10s≈17h；checked 2026-10-10）。

CTRL20 — [InfiniteTalk issue #210](https://github.com/MeiGen-AI/InfiniteTalk/issues/210)（一手使用者；RTX4090 24GB, 480p/10s/8 steps/81f chunk, 40min no LoRA; later comment 15min/10s FusionX+TeaCache；checked 2026-10-10）。

CTRL21 — [MultiTalk README](https://raw.githubusercontent.com/MeiGen-AI/MultiTalk/main/README.md)（模型作者；81/201f contract、480p single-GPU boundary、A100 evaluation statement、INT8/LoRA/TeaCache/Colab link；checked 2026-10-10）。

CTRL22 — [MultiTalk generation script](https://raw.githubusercontent.com/MeiGen-AI/MultiTalk/main/generate_multitalk.py)（模型作者；audio embedding/TTS prep、external audio mux、offload/quant/LoRA/vram-management flags；checked 2026-10-10）。

CTRL23 — [MultiTalk issue #93](https://github.com/MeiGen-AI/MultiTalk/issues/93)（一手使用者；20+ sec face distortion/color drift report；checked 2026-10-10）。

CTRL24 — [MultiTalk issue #126](https://github.com/MeiGen-AI/MultiTalk/issues/126)（一手使用者；two A100 vs one A100 speed question under 640×640/5s/4-step TeaCache/LightX2V settings；no numeric result；checked 2026-10-10）。

CTRL30 — [Snap TalkVerse README](https://github.com/snap-research/TalkVerse)（模型作者；Wan2.2-TI2V-5B base + TalkVerse-5B audio LoRA + Wav2Vec2, image/audio/prompt, offload/T5 CPU, INFER_FRAMES=120, external audio merge, non-commercial license；checked 2026-10-10）。

CTRL31 — [TalkVerse paper](https://arxiv.org/abs/2512.14938)（原作者論文；(4,16,16) VAE, sliding window + motion frame, FramePack/reference embedding, 40s/1000f evaluation, 10× lower inference-cost claim, hand/full-body limitations；checked 2026-10-10）。

CTRL25 — [Stable-Video-Infinity main README](https://github.com/vita-epfl/Stable-Video-Infinity/blob/main/README.md)（研究作者；A100-80G reproduction environment、SVI family/14-minute and 20-minute claims、Wan2.1 LoRA contracts、official workflow boundary；checked 2026-10-10）。

CTRL26 — [Stable-Video-Infinity Wan2.2 branch README](https://raw.githubusercontent.com/vita-epfl/Stable-Video-Infinity/svi_wan22/README.md)（研究作者；Wan2.2 high/low SVI LoRAs、single-GPU CLI、250s/50 clips、832×480、15fps、overlap5、motion latent1、CFG4、PyTorch version sensitivity；checked 2026-10-10）。

CTRL27 — [ComfyUI-Wan-SVI2Pro-FLF](https://github.com/Well-Made/ComfyUI-Wan-SVI2Pro-FLF)（一手社群作者；video continuation with target last frame/prompt, overlap seam issue, 81–101f action timing notes, motion/FLF latent contract；checked 2026-10-10）。

CTRL28 — [ComfyUI-WanExtended](https://github.com/ethanfel/ComfyUI-WanExtended)（一手社群作者；403-frame/24fps/720p demo, 161+161+81 segments, SVI Pro + First-Middle-Last + InfiniTalk artifact；no hardware timing；checked 2026-10-10）。

## Main attention

1. 低資源直接缺口最大的不是「哪個模型最好」，而是缺少同條件 L4 control/long-video measurements；VACE A10G 與 Fun 4090D 只能當鄰近 VRAM 路徑的原始條件。
2. 若主代理要判斷可行性，先保留 checkpoint pairing：VACE-14B + matching T2V；Fun high/low + matching LoRA；Animate 不套一般 Wan2.2 LoRA；SVI Wan2.2 high/low SVI LoRA；InfiniteTalk/MultiTalk 需各自 audio condition weights。
3. 對長片，VACE 官方是 5 秒分段 + firstclip；InfiniteTalk 是 streaming 但其作者明示 color/ID drift；MultiTalk 81f/201f 與 20+秒 drift issue；SVI Wan2.2 有明示 overlap/motion latent 的 250 秒命令，但沒有 hardware/time acceptance。
4. TalkVerse-5B 是本分題新增的 Wan2.2-TI2V-5B 長片音訊候選：它有 explicit audio-LoRA/base/Wav2Vec2 contract 與 40 秒／1000f 紙上評估，但目前仍缺指定 L4/A100 的直接運行證據。

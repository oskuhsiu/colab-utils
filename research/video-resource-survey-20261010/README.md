# 影片生成：L4／A100 High RAM 資料蒐集與初步統整

查閱日：2026-10-10。由9位 `luna_worker` 完成11輪有界分題查找，主代理整合並複讀決策相關原始來源。此次只做公開資料查找與工作區舊證據整理，未啟動GPU或新增影片跑分。來源統計與機器可讀索引見本文末。

快速比較見 [Summary charts：L4／A100需求、畫質、速度與用途選擇](SUMMARY_CHARTS.md)。

## 初步判斷：按資源與成片目標選對照

以下是**主代理的下一輪優先對照清單**；參數取自作者契約，實際吞吐與成品通過率仍需在指定runtime量測。L4有一條本地舊run技術基線；A100須先核40／80GB與High RAM實際容量。

| 目標 | L4優先保留 | A100＋High RAM優先保留 | 判斷依據／完成條件 |
|---|---|---|---|
| 快速有音訊T2VA | 已跑通的FastH3 v1 Kijai INT8-ConvRot：864×480、124→120f、Euler4、shift12/3、VSA keep10%；再對照V2 8步 | matching H3 Base20／25步與Turbo FL2VA 8步；FastH3 V2／Trim另列速度對照 | 先確認台詞／動作／音畫，不能從sampling秒數或單張截圖定最好 |
| 人物／服裝／多素材reference | native H3 Ref2VA INT8-ConvRot＋Qwen32B量化；Base20 vs matching Ref2VA Turbo4 | same-task Ref2VA Base20／25，必要時比DiffSynth50；較高精度是否能fit另測 | checkpoint／實際reference接線優先；FastH3 T2VA student接reference仍是未蒸餾任務的實驗 |
| 無音訊、I2V／畫面可控 | Wan2.2 TI2V-5B官方offload720p路線；Wan A14B Lightning成對FP8/GGUF作條件候選；Hunyuan1.5 480p I2V8／12步 | A10080可保留A14B720p原始／較高精度；A10040需量化／offload；同時比較5B、Hunyuan1.5 | 原生720p、24GB門檻／nearby-GPU成功各自標清。LoRA、scheduler、expert切換不可跨family硬套 |
| joint audio-video替代 | LTX-2.3／2.5量化offload流程列待測，不因模型檔小就判已fit | LTX-2.5 distilled8+4步、配套Gemma4／VAEs／upscaler；conv與diffusion decoder分別量decode成本 | 作者功能契約明確；目前缺指定GPU端到端表。NVFP4官方路徑是Blackwell；不能套到A100／L4 |
| 動作、攝影機、說話長片 | VACE-1.3B／專用Fun Control、TalkVerse5B列較小的控制候選；SVI等列待測 | matching VACE14B／Animate／Fun Camera／SVI high-low pair按需求選；MultiTalk單GPU先看480p契約 | 預處理、external audio、長片drift与後製計入總成本；沒有本次指定GPU完整paired benchmark |
| 完整成片與細節 | 已有local Comfy graph＋OpenMontage/Pixelle控制層；Real-ESRGAN/tiled VSR列後製對照 | 同一製作層，另保留FlashVSR與SeedVR2 temporal路徑 | 本地/API/stock路線分開；裁切、幀數、原音軌、identity與動作需重驗，不能只看更銳利 |

這份清單保留了速度、任務能力、畫質與資源的取捨。暫時最有把握的結論是：**先選matching任務与workflow，再選量化與加速；「best」要按成功成片所需總時間計算**。來源基礎與限制展開如下。

## 資源範圍與讀法

- 低資源：單張 L4，名義 24GB VRAM。工作區舊 Colab 實測為 23034MiB VRAM／52.96GiB 主機 RAM，這是既有一次 runtime 規格。
- 中資源：單張 A100 + High RAM。A100 40GB／80GB 分列；主機 RAM、offload、磁碟另列。High RAM 指 system RAM，不視作增加 GPU 顯存。[Colab FAQ](https://research.google.com/colaboratory/faq.html#resource-limits)
- 超過單張 A100 High RAM 的配置列高資源參考；4090／5090 等非指定 GPU 保留原測試條件。多卡、Blackwell-only 或 1TB 主機 RAM 的結果不當成指定 Colab 配置已驗。
- 以下「初步候選」是主代理依來源作的判斷，並非新跑分或畫質冠軍。各模型使用不同 prompt、解析度、片長、precision、scheduler，公開數據不足以排出通用最佳。

## H3 的模型與權重不能只按步數分類

```text
MiniMax-H3 Base
  +-- FL2VA  (文字 / 首幀 / 尾幀 -> video + audio)
  +-- Ref2VA (多圖 / video / audio reference -> video + audio)
       |
       +-- matching Turbo / HyperFlow / PDD acceleration

FastH3 student
  +-- v0.2 / v1 : 4 forwards, T2VA training contract
  +-- V2       : 8 forwards, another checkpoint / schedule
  +-- Trim     : 42-block V2 derivative
  +-- OmniRef  : separate Ref2VA PDD student; high-resource kernel path

每條路線再另選：pruned/full -> quant format -> loader/kernel -> workflow
```

原 H3 Base 已 CFG-distilled；「原步數」依框架不同：DiffSynth 範例為 50 steps，Comfy 原生模板為 20 steps；有些 wrapper 計算 sigma points，另一些計算 transformer forwards。檔名 `1300step`／`2900step` 則是 student 訓練進度。這些數字須分欄，不能直接相除當加速比。[MiniMax 模型卡](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/README.md)、[Comfy 原生指南](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/minimax/minimax-h3-native.mdx)、[步數查核](01-h3-original-steps.md)

| 路線 | 配套契約 | 在本次範圍的證據／定位 | 仍缺的證據 |
|---|---|---|---|
| Base FL2VA／Ref2VA | 不同 task checkpoint；Comfy 20-step／DiffSynth 50-step 基線 | 有 L4 作者 workflow 與單 A100 作者報告；保留作有參考條件的品質基線 | 同條件 20／25／50步、量化與音畫對照；單 A100 High RAM 完整 RAM／VRAM 記錄 |
| LightX2V Turbo FL2VA | 544p 4／8 NFE shift 12/3；768p 4／8 NFE shift 6/3 | 原 H3 上的專門 adapter，非 FastH3；可在 matching workflow 評估 | L4／A100 同 seed、完整耗時與 motion/audio 對照 |
| LightX2V Turbo Ref2VA | 544p 4 NFE、shift 12/3；reference resize `match` 為作者訓練條件 | 有原生 reference 任務契約，適合加入 Ref2VA 基線對照 | 不能宣稱保臉成功率或所有 reference 都提升 |
| HyperFlow／Alibaba PDD | HyperFlow 8步需要 two-time embedder＋專用 loader；PDD matching LoRA＋`apply_pdd_lora` | 補充的少步候選；不能把其檔案直接當一般 LoRA | 指定 GPU 的 E2E、量化／pruned compatibility、同條件成片驗證 |
| FastH3 v1／v0.2 4步 | Euler trained ladder `[999,749,500,250]`；VSA 90%、tile64、shift 12/3 | 工作區已有 Kijai v1 INT8-ConvRot 在 L4 跑通的技術證據 | v0.2 step2900 不是該舊 run 權重；warm、品質與不同任務尚無受控比較 |
| FastH3 V2／Trim 8步 | V2 shift 10/3、VSA 80%；Trim 另有剪枝 | 列入速度／細節候選；公開作者跑分多為其他 GPU | 尚無公開 L4／單 A100 完整 benchmark；Comfy FL2VA 接口與 student 訓練任務要分開 |
| FastVideo OmniRef PDD-8 | 独立 `transformer_ref`；tile128、sm100a／sm103a、沒有 Triton fallback | 高資源參考 | GB200 約103GiB 的例子不能當 L4／A100 recipe |

表中契約見 [LightX2V 原作者](https://github.com/ModelTC/Minimax-H3-Turbo)、[HyperFlow](https://github.com/Video-Rebirth/hyperflow)、[Alibaba PDD](https://huggingface.co/alibaba-pai/MiniMax-H3-Acc-LoRAs)、[FastH3 分題](03-fasth3-variants.md)。

## 量化作者與改權重的初步整理

| 類型 | 本次找到的來源 | 如何比較 |
|---|---|---|
| Comfy 原生量化與 pruned repack | Comfy-Org、Kijai、Winnougan、DmitryDB | INT8-ConvRot、scaled FP8、W4A8／W6A8 的 loader、保留 BF16 layers 與 CUDA 路徑各異；按 exact file／revision 比較 |
| NF4／GGUF | DiffSynth、Unsloth、molbal、realrebelai、Abiray | 同 Q4 標籤可能對應 full/pruned、先 FP8 再 GGUF、mixed precision 或特別 fork；不得只按 bit-width／檔案大小推論畫質 |
| NVFP4／特殊部署格式 | lilcheaty、FastVideo consumer、QuantFunc | Blackwell native 與 L4／A100 emulation／BF16 fallback 分開；QuantFunc 含 fused acceleration 並需專用 loader |
| Merge／adapter conversion／單 tensor 修改 | smhfacct hybrid、drbaph conversion、Kijai ref-difference、t8star HF1.02 | 與純量化分開；權重重建相似度或少量 seed diagnostic 不等於 reference／動作／聲音提升 |

詳細檔名、GB／GiB、text encoder、video/audio VAE 與作者限制見 [量化與社群表](02-h3-quant-community.md)。H3 的 DiT、Qwen3-VL encoder、video VAE、audio VAE 四者要合計並分開看載入峰值。替換成 Qwen 4B／projection adapter 是改 conditioning 路徑，不能視作只是同一 32B encoder 的量化。

L4 是 SM89、A100 是 SM80；FastVideo FP8 文件明示低於 SM89 走 BF16 dequant fallback。這不表示 A100 不能載 FP8，也不表示它在某 Comfy stack 一定較慢；它表示要核實實際 backend。[NVIDIA GPU 架構表](https://developer.nvidia.com/cuda/gpus)、[FastVideo optimization docs](https://github.com/hao-ai-lab/FastVideo/blob/main/docs/inference/optimizations.md)

## 已找到的少數指定 GPU 案例

| 來源 | 條件與結果 | 能支持的結論／限制 |
|---|---|---|
| 工作區既有 L4 | Kijai v1 4-step INT8-ConvRot＋Qwen NVFP4-AWQ＋INT8 VAE；864×480、124→120f、5秒；181.62／156.19秒 | 這條路徑曾技術跑通，200 VSA calls／0 fallback；不同 prompt／seed／fixture LoRA，沒有受控品質排名或 warm 重複 |
| AI Lab A10040／L4 | 20-step H3、864×480、124f；A10040 572.9秒；作者記 A100/L4 24.6/77.2秒每步 | A10040 刻意 `--reserve-vram 28` 以觸發 offload；precision 未報。不能當標準 A10040 vs L4 硬體勝負 |
| howrass Colab A10080 | 作者用 CUDA12.8、第二次以後 timing；0.5MP INT8 348.25秒、FP8 211.36秒、FP8+Sol+Spectrum 97.12秒；Turbo+Sol 38.31秒 | 作者選較慢的方案，主觀認為 Turbo 的聲音／畫面／prompt fidelity 下降；缺 exact seed、frames、revision、peak RAM/VRAM，不能移植成保證 |
| zenryokukikai A10080 | INT8-ConvRot、Triton、864×480、124f、20步；作者報110秒 | 可保留 single-A100 候選；host RAM、cold/warm、各階段 timing 未報 |
| Marwanto A10080＋1TB RAM | 960×544、10秒；作者報307.08秒、50.62GB VRAM、100.8GB RAM use | 機器規格超出本次主線；實際 RAM use 與 provisioned 1TB 分開。steps/seed/peak 定義不足 |

來源：[舊 L4 evidence](00-hardware-and-local-evidence.md)、[AI Lab 原測試](https://ai-lab.aidly-ai.jp/posts/video-ai-4models/)、[howrass 原帖](https://note.com/howrass_note/n/nb6adf1bce83e)、[A10080 repo](https://github.com/zenryokukikai/minimax-h3-webui/blob/main/README.md)、[完整來源表](01-h3-original-steps.md)。耗時行之間沒有共同的完整控制條件，不能彼此直接排名。

## 其他模型、控制變體與框架

### Wan 核心：可先保留的對照路線

| 模型／配置 | L4／A100 的現有依據 | 初步定位與必要界線 |
|---|---|---|
| Wan2.1 T2V-1.3B 480p | 官方聲稱8.19GB VRAM；480p為較充分訓練的解析度 | 低負擔、無原生音訊的基線候選；官方4090耗時不能當L4結果 |
| Wan2.2 TI2V-5B 720p／24fps | 官方有≥24GB＋offload／dtype conversion／T5 CPU 路線；GPU Battle 報L4單卡49f的0.15frames/s | L4可行性證據比A14B直接；該throughput不是121f或5秒完整成片時間，亦未量化品質 |
| Wan2.2 TI2V-5B-Turbo | 作者獨立4步CFG-distilled權重；121f、1280×704、24fps、trained list `[1000,750,500,250]` | 少步候選，不能由同為5B就宣稱L4/A100端到端已驗 |
| Wan2.2 A14B Base／Lightning | Comfy原生FP8-scaled high/low pair，各13.31GB；base20步、CFG3.5；Lightning4步、CFG1、2+2 split、Euler/simple、shift5、LoRA strength1 | 可作中資源影像品質／低資源量化offload候選；20/4步要用matching高低噪權重與LoRA。檔案總和不等於同時resident VRAM |
| Wan2.2 A14B GGUF | bullerwins提供high/low pair、Q2–Q8；model card未有受控quality測試 | L4顯存不足時的待測候選；保留較高bit與較低bit對照，不宣稱Q4一定最佳 |
| TurboDiffusion／CausVid | 各有不同checkpoint、scheduler、attention與segment契約；TurboDiffusion作者測試主要5090 | 獨立加速分支，不能把其少步權重／switch boundary套成原生Lightning recipe |

契約與作者限制見 [Wan核心分題](04-wan-core-low-mid.md)、[Wan2.2官方](https://github.com/Wan-Video/Wan2.2)、[LightX2V Lightning](https://github.com/ModelTC/LightX2V-Wan2.2-Lightning)、[TI2V-5B-Turbo](https://huggingface.co/quanhaol/Wan2.2-TI2V-5B-Turbo)。LightX2V也公開极大動作artifact／車向反轉的badcases，少步提速與成品通過率須一起看。

Wan2.2 A14B有兩個expert，而每步只啟用其中一個；換expert可能涉及CPU↔GPU搬移。不同loader的offload、block swap、text encoder常駐與VAE decode會影響總時間。本次不以「active14B」就認定它只需單個14B檔案的資源。

**指定硬體的數據缺口：** 單A10080 TI2V-5B BF16 qualification有121f／1280×704／50步的288.267秒T2V、299.439秒I2V，device peaks為27,533／30,333 **MiB**，但host是1TiB、未報實際system RAM峰值，因此仍不是Colab High RAM整套已驗。GPU Battle的A10080行標measured、A10040行標estimated。另有A14B的21.68秒等vLLM數字，依CFG2×Ulysses2須四張GPU，已移到高資源參考。[單GPU qualification](https://github.com/wiseyak-core/wiseyak-vllm-omni/blob/main/recipes/Wan-AI/Wan2.2-TI2V-5B-A100.md)、[GPU Battle](https://gpubattle.com/guides/wan-2-2-5b-gpu-benchmarks)、[官方平行卡數公式](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/feature_compatibility/)

### 其他模型：可行性與用途分開

| 路線 | 來源提供的低／中資源依據 | 在初步候選中的位置 |
|---|---|---|
| HunyuanVideo-1.5 | 官方8.3B、14GB model-offload門檻；480p I2V step-distill推薦8／12步；另有LightX2V 4步模型 | L4／A100的無原生音訊I2V候選；CFG-distill不是step-distill，T2V/I2V及4步衍生不能混用 |
| LTXV 0.9.x | 2B／13B、distilled／FP8／GGUF、keyframe/control/extension | 可作無音訊的輕量與控制候選；舊LTXV與LTX-2音畫模型分開 |
| LTX-2.3／2.5 | 原生音畫、兩段式、IC-LoRA／Dub-It／A2Vid；2.5支持FP8 cast＋CPU/disk offload，8+4-step distilled | 值得在A100 High RAM列入音畫／細節對照；目前沒有指定GPU完整時間／memory表，不能宣布L4成片已驗；NVFP4官方路徑要求Blackwell |
| FramePack／F1／P1 | 官方6GB floor、逐section長片；工作區另收錄歷史L4 20秒約80分鐘社群案例 | 適合列長片／I2V比較，但低顯存不能視作低耗時。官方TeaCache示範有不同／較差結果，沒有通用保真保證 |
| CogVideoX／CogVideoX-Fun、EasyAnimate | CogVideoX A100/H100 memory表；Fun／EasyAnimate提供offload、控制權重；EasyAnimate有A10080／A10 timing矩陣 | 有明確pose/depth/start-end等條件的候選；小VRAM、控制能力、速度與最終質量分項，不因版本較舊就刪除 |
| Pyramid Flow | 官方CPU/sequential offload<12／8GB；單A100 5s/768p作者例約5.5分鐘 | 保留另一種長片／I2V候選；A100型號、host RAM、其他quant未完整報告 |
| Mochi／原HunyuanVideo／StepVideo | 原生實作約60GB、45–60GB，或四GPU／近80GB上限；社群另有量化流程 | A10080或第三方量化的條件候選；不是現成L4 qualification，不能拿train memory當inference floor |

模型檔名、frame grid、音訊狀態、控制／量化與失敗案例見 [其他模型分題](05-other-video-models.md)。特別是 LTX-2.3 的 Gemma3／單檔與2.5的Gemma4／split components不互換；2.5 diffusion video decoder與conv decoder有不同資源／細節取捨。[LTX-2官方](https://github.com/Lightricks/LTX-2)、[HunyuanVideo-1.5官方](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)、[FramePack官方](https://github.com/lllyasviel/FramePack)

### 控制和長片：解決成品要求的另一條軸

| 成品需求 | 有明確契約的路線 | 本次範圍需要注意 |
|---|---|---|
| 指定動作、位置、局部保留 | VACE-1.3B／14B、Wan2.2-Fun Control | 需要matching control checkpoint、預處理video/mask/reference；VACE14B錯配I2V base曾報綠噪聲。沒有單L4完整control benchmark |
| 指定攝影機軌跡 | Wan2.2-Fun Control-Camera | 是專用camera權重＋每幀相機pose，不只prompt文字；不能假定generic Wan I2V加普通LoRA等價 |
| 跟隨人物表演／服裝角色替换 | Wan-Animate-14B | pose／face／mask／background preprocessing是額外成本；一般Wan2.2 LoRA不建議直接套；單人mask／身材比例有作者限制 |
| 音訊驅動說話／多人物 | InfiniteTalk／MultiTalk；TalkVerse-5B | 外部WAV＋Wav2Vec2＋condition weights，最後mux原音訊；不是原生生成soundtrack。MultiTalk原程式單GPU路徑為480p；TalkVerse較小但尚缺指定GPU timing |
| 長片接續／跨鏡 | SVI／SVI2 Pro、VACE firstclip、Comfy延續節點 | SVI Wan2.2需要high/low LoRA pair、overlap／motion latent；長度demo不等於時間穩定或身份通過。社群有seam ghost、color/ID drift和motion drop |

上述是**主代理依輸入契約整理用途**，不是模型效果排名。完整來源與badcases見 [控制／長片分題](06-wan-control-variants.md)、[VACE](https://github.com/ali-vilab/VACE)、[Wan-Animate](https://github.com/Wan-Video/Wan2.2)、[TalkVerse](https://github.com/snap-research/TalkVerse)、[SVI Wan2.2分支](https://github.com/vita-epfl/Stable-Video-Infinity/tree/svi_wan22)。目前單L4的控制／長片實測缺口大；A10040 InfiniteTalk issue報10秒17小時是失敗／低吞吐案例，不能當標準性能。

### 成片框架：可與生成端組合

```text
分鏡 / 素材 / 台詞 / anchor
           |
  OpenMontage / Pixelle / 製作控制器
           |
   ComfyUI / 推論backend (L4 或 A100)
           |
  逐鏡內容QA -> 選片 -> 放大 / 插幀 / audio
           |
        剪輯 / 字幕 / 最終影片
```

這是主代理的初步層次整理；各框架的實際連接仍須按來源adapter與API契約驗證。

| 框架 | 已讀功能與可下載流程 | 對本次限制的意義 |
|---|---|---|
| OpenMontage（`calesthio/OpenMontage`） | 12類production pipelines、manifest/checkpoint／cost／QA；文件明确支援local ComfyUI URL與自訂API workflow，含H3 local stack | 可作完整製作的控制層候選；預算／成片demo有cloud、stock、local不同路線，不能把Veo等demo質量算成本地L4效果 |
| Pixelle-Video | script→鏡頭image/video→TTS/BGM→composition；可接local ComfyUI／RunningHub／API | 可作多鏡短片流程候選；本次未找到指定L4/A100 full-pipeline benchmark |
| FireRed-OpenStoryline | existing footage／Pexels搜尋與agent剪輯、ASR／TTS／timeline；部分AI transitions是第三方API | 比較適合把已有素材編成成片；README仍把某些generation／GPU rendering能力列TODO |
| waoowaoo | self-hosted canvas＋OpenRouter provider calls；Docker/Temporal/DB等 | preview生成靠API；本地workspace不是本地model，不能納為L4離線生成已驗 |
| video-autopilot-kit | Editkin execution／receipts／QA與合成demo | 屬剪輯執行契約，需Editkin環境；不是另一個本地生成模型 |
| h3lite | ComfyUI路由＋anchors/manifest/anchorQA；Windows/NVIDIA作者實測 | 有內容驗收與硬體路由參考，但Linux experimental、沒有L4/A100直接測量 |

來源：[製作框架分題](07-production-frameworks.md)、[OpenMontage provider文檔](https://github.com/calesthio/OpenMontage/blob/main/docs/PROVIDERS.md)。同名 `Open-Montage-app/OpenMontage` 是另一個owner的包裝repo，本報告以canonical源碼repo為主，不當作另一份獨立成片benchmark。OpenMontage列出的12GB／8GB等provider資源分類，與模型作者完整pipeline門檻不一定相同，未作本研究實測保證。

### ComfyUI 現成workflow：先保留可追溯的最小圖

已整理14組workflow/node來源，含H3 T2V/I2V/R2V、FastH3 V2、Wan VACE/Animate、Kijai WanVideo/FramePack、VideoX-Fun、LTX官方nodepack、GGUF低VRAM與upscale/framegen社群圖。下載連結、node依賴、model/LoRA/TE/VAE與輸入素材契約見 [workflow inventory](08-comfy-workflows.md)。

主代理優先保留的**研究基線**是官方native與模型作者最小sample，便於查清checkpoint、step、kernel與輸入；完整社群圖仍保留，尤其是已有原始run ledger者。這是可追溯性的選擇，不是官方圖品質一定勝過社群圖。

- UI JSON（`nodes/links`）與API prompt JSON不是同一格式。接OpenMontage或自動提交前，要在對應nodepack版本載入並另export API格式。[OpenMontage ComfyUI接口](https://github.com/calesthio/OpenMontage/blob/main/docs/PROVIDERS.md)
- H3 FL2VA／Ref2VA、FastH3 v1／V2、Wan native／WanVideoWrapper／VideoX-Fun的物件與權重不同；圖可以載入不代表任務或數值契約正確。
- 「GGUF Q4」也不足以識別流程。Cordux的低VRAM圖包含rapid-AIO第三方merge、many custom nodes與CPU offload，其3050實測不是L4結果；保留作完整流程線索。
- 模型、encoder、VAE、preprocessor、postprocessor的常駐與釋放順序影響峰值。Tiny VAE／preview的成功不能代替完整decode／成片內容驗收。

### 替代推論框架：目前沒有指定GPU的通用勝負

| 框架 | 可用資料／入口 | 關鍵資源與品質邊界 |
|---|---|---|
| Wan2GP／MMGP | canonical `deepbeepmeep/Wan2GP`目前README列v13.141；模型profiles、preload、block offload、GUI／CLI／API | H3/LTX小VRAM數值為作者runtime claims；host/pinned RAM要另測。讀到的extreme2k與lucazin forks分列，未當成canonical當前版本 |
| DiffSynth-Studio | H3/Wan/LTX的examples、NF4／INT8／FP8、parameter／disk offload、tiled VAE | 7／8GB floor有不同來源；T4社群多次OOM或極小輸出不可用，是反向證據；沒有同條件L4/A100完整成片表 |
| FastVideo | exact student schedules、support matrix、VSA／Sage／FA、CLI／server | A100 FP8 BF16 fallback、H3 regional compile與OmniRef的Blackwell gate；cold/compile/warm与text encode/VAE分開 |
| LightX2V | H3 one-GPU task scripts、matching AdaLN cache；Wan少步／量化configs | quantized DiT的LoRA需dynamic apply、不能generic merge；單H100跑分保留原GPU |
| SGLang Diffusion | H3 formats/offload/cache的consumer recipes、server/API | 4090 VRAM/host hard-cap emulation有詳細資料，但不是實體L4/A100；116.7GB pinned host與lossy cache有不同成本 |
| vLLM-Omni | model/feature matrix、OpenAI-compatible video API、Wan5B A100 qualification | single-A10080例host1TiB未報RAM峰值；CFG/Ulysses/HSDP benchmark要核卡數 |
| SANA Sol Engine | H3 full-stack／Sol-Attn與4×A100同prompt/seed比較 | 多卡性能與約49,126MiB/GPU不在單卡主線；不能把3.55×套到本機L4 |

來源與版本、kernel支援／fallback、cache/compile失敗見 [推論框架分題](09-inference-frameworks.md)。主代理的初步決定是**先保留現有已跑通Comfy路徑與一條matching替代backend的對照**；尚沒有證據值得現在就把全部製作流程搬到另一套框架。

### 後製：資源與內容改變都算進成片成本

| 流程 | 來源能支持的用途 | 指定資源內的待測項 |
|---|---|---|
| FlashVSR v1.1 | 官方one-step、4×、單A100作者17FPS例；temporal VSR | L4 kernel未確認；官方script128-grid中心裁切與frame alignment可能改構圖／片尾，原音軌未copy |
| FlashVSR-Pro | 社群tiled／padding／keep-audio流程 | exact duration/resolution與低VRAM是fork作者claims，非官方或L4qualification |
| SeedVR2 3B／7B／Comfy／lite | restoration、BlockSwap；batch≥5 temporal consistency，batch1省VRAM | 官方多H100，wrapper多4090/H100；L4/A100仍缺實測。較清晰可能over-sharpen／改細節，不等於身份修好 |
| Real-ESRGAN | 較小模型逐幀、tiling、可copy原音軌 | 缺時間一致機制，可能flicker；沒有本次target paired表 |
| RIFE | 2×／4×插幀；flow resolution可調 | explicit FPS／PNG路徑不auto-mux原音；預設exp/video則有copy/AAC transfer。重複幀／ghosting、PTS與時長需驗 |
| MMAudio | 約6GB、video→new audio、8秒訓練時長條件；MP4合成 | 新音訊不能視作保留原台詞；有不可辨人聲／誤音樂限制。模型權重CC-BY-NC与程式MIT分開 |

詳細scale/crop/frame-grid/audio契約、sample links與badcases見 [後製分題](10-postproduction-workflows.md)。H3→LTX2.3→RTX VSR的社群pipeline也有完整graph與影片線索，但其4080S timing與未固定seed不構成本次資源比較。[社群補查](11-social-primary-scout.md)

## 社群證據與尚未解決的缺口

本次查了X／Twitter、Facebook公開groups/posts、Reddit、GitHub/HF discussions/issues、日文note/Zenn、作者blog，並嘗試YouTube/Bilibili/Civitai定位。可讀原始測試主要來自Reddit、作者repo/blog和issue。X多為Grok trending摘要；Facebook多是無關結果／登入牆。未登入或繞過权限，沒有把摘要當原帖測試。

值得回讀的社群紀錄：A10080的howrass 18條件比較、AI Lab reserve/offload測試、GenVidKit固定seed兩次run ledger、Kasei-san cache/Turbo比較、ai-muninn兩seed的FastH3 V2與H3比較、VACE／InfiniteTalk／MultiTalk的失敗issues。它們仍有各自的GPU、版本、輸入或指標限制。[量化社群](02-h3-quant-community.md)、[控制變體](06-wan-control-variants.md)、[社群補查](11-social-primary-scout.md)

主代理已對重要矛盾作窄修正並留下原始來源：

1. vLLM A14B的CFG2×Ulysses2屬四GPU，不是單A100。
2. FramePack的30%是作者某個TeaCache較差示範，不是30%品質成功率；由秒／幀換算的時間另標計算值。
3. RIFE的explicit FPS與預設exp/video有不同audio-transfer行為。
4. Wan2GP舊fork的版本不代替canonical當前README。
5. SOC06宣稱單24GB4090卻列41–48GB Peak VRAM，內部不一致；保留線索、排除資源／速度結論。

仍缺：同一L4與A100 High RAM下，matching任務／素材／提示、配套sampling、cold＋warm、各階段時間、完整峰值與成片通過率的共同測試。官方benchmark、profile宣告、nearby-GPU案例和本地舊run都不足以補齊。

## 後續實測用的最小記錄表（本次未執行）

| 固定／記錄 | 目的 |
|---|---|
| GPU型號／卡數／VRAM MiB／system RAM GiB、driver／CUDA／Torch／nodepack revision | 確认真的在資源範圍、kernel與loader可追溯 |
| exact weights＋hash、full/pruned/merge/quant／LoRA、actual task／inputs／crop／order | 檢查同名格式與任務錯配 |
| 同素材／prompt、至少兩個seeds；每模型合法size/frame grid，統一最終交付時長／比例 | 給每模型符合契約的測試，不能為了同數字強迫OOD |
| download／cold load／encode／sampling（actual forwards）／decode／mux／post；warm repeat和cache hit分開 | 找出總成本，不能把kernel或denoise當E2E |
| ID／服裝／動作因果／細節／flicker／聲音／台詞／lip-sync／clip joins的PASS/FAIL＋原尺寸frames/完整片 | 能播放與成品內容合格分開 |
| 重抽次數、失敗／OOM、post成本、成功成片數 | 用「成功成片／總GPU分鐘」比較本次所說的最佳成品 |

## 分題與來源索引

| 檔案 | 內容 |
|---|---|
| [00 資源與本地舊證據](00-hardware-and-local-evidence.md) | 範圍、硬體規格、L4旧run、統整方法 |
| [01 H3原模型與步數](01-h3-original-steps.md) | Base／Turbo／HyperFlow／PDD／merge／forward count |
| [02 H3量化與社群](02-h3-quant-community.md) | 作者、精度、TE/VAE、資源與品質反例 |
| [03 FastH3](03-fasth3-variants.md) | v0.2／v1／V2／Trim／OmniRef與kernel |
| [04 Wan核心](04-wan-core-low-mid.md) | 1.3B／5B／A14B、少步／量化／實測与估計 |
| [05 其他模型](05-other-video-models.md) | LTX／Hunyuan／FramePack／CogVideo／Mochi等 |
| [06 控制與長片](06-wan-control-variants.md) | VACE／Fun／Animate／MultiTalk／TalkVerse／SVI |
| [07 製作框架](07-production-frameworks.md) | OpenMontage／Pixelle／FireRed等 |
| [08 ComfyUI圖](08-comfy-workflows.md) | 原始JSON、nodepack、model／輸入契約 |
| [09 推論框架](09-inference-frameworks.md) | Wan2GP／DiffSynth／FastVideo／LightX2V／SGLang等 |
| [10 後製](10-postproduction-workflows.md) | VSR／插幀／補音訊／尺寸与時長 |
| [11 社群補查](11-social-primary-scout.md) | 原始ledger、兩seed比較與blocked/discovery |

完整保留claims／resources／artifact links的 [sources.json](sources.json)，可篩選比較的 [sources.csv](sources.csv)，去重入口 [SOURCE_INDEX.md](SOURCE_INDEX.md)，檢查與覆蓋統計 [verification.json](verification.json)。`full-text`表示該worker／主代理讀到正文，不表示本研究在GPU重現；主代理複讀範圍另標。多筆紀錄可指向同頁，去重頁數也不是獨立實驗數。

### 覆蓋統計

- 228筆來源紀錄、228個唯一source IDs；213個按URL去重的主來源入口（不是213個獨立實驗）。
- 210個URL至少有一筆正文讀取紀錄；207個URL至少一筆為primary／作者／第一手正文，已排除二手、blocked/snippet與SOC06內部矛盾。
- 紀錄分類：110 official、52 model-author、58 firsthand-community、4 secondary、2 search-boundary、2 local-evidence；其中SOC06另被隔離為不可用資源benchmark。
- 主代理重新打開／抽核37個對應索引URL，涉及44筆紀錄；並非每頁由主代理全文重讀，其餘正文讀取為worker回報。查核範圍保存在verification.json。
- JSON／CSV筆數與source IDs、local links已作格式檢查。未驗證每個外部artifact可下載或可在指定runtime執行；未啟動GPU、下載模型或登入社群。

# 成片製作／Agent Orchestration 框架證據

查核日：2026-10-10（公開 web/HTTP，只讀；未登入、未安裝、未下載權重、未啟動 GPU）。本檔只整理框架本身的 orchestration、成片流程、provider／API／local 邊界、依賴與驗收證據；不比較 ComfyUI workflow 或推論 backend 的畫質、速度，也不作最佳推薦。L4 24GB 與 A100 High RAM 只在來源明示的資源欄記錄，沒有從框架宣稱外推成可行性。

## Answer

OpenMontage 的可核實 canonical source 是 `calesthio/OpenMontage`：GitHub API 顯示 owner `calesthio`、`fork:false`、AGPL-3.0；它把 coding assistant 當控制平面，透過 YAML pipeline manifest、Markdown stage skills、Python tools、JSON checkpoint 走 `research → proposal → script → scene_plan → assets → edit → compose`。架構文件沒有指定唯一 LLM；checked `config.yaml` 列出 anthropic、openai、gemini、openrouter、ollama、mistral、minimax 等 provider 欄位。框架本身不是影片生成模型；它可選 cloud API、local GPU／ComfyUI、stock footage、Remotion／HyperFrames／FFmpeg，並記錄 provider、成本、fallback、review 與人類 gate（PROD01–PROD05）。

`Open-Montage-app/OpenMontage` 不是 canonical repo 的轉址或獨立 benchmark：本次讀到的是另一個 owner 的 public repo，頁面列 `2 Commits`、MIT、`assets/`、`lib/`、README；其 release 頁列出一個 `OpenMontage` release，頁面日期顯示為 23 Sep（未顯示年份）。它重複產品描述，但沒有 canonical repo 的完整 pipeline source，故只作 provenance／包裝來源記錄（PROD06）。

FireRed-OpenStoryline 是對既有媒體做自然語言剪輯與 agent tool orchestration 的框架。它有 MCP server、nodes、skills、storage、LangChain agent；LLM／VLM、Pexels、TTS 和 AI transition 需要 API 或外部服務。README 的 TODO 仍把「image/video generation」和「GPU-accelerated rendering」列為待辦；作者明示 AI transitions 會呼叫第三方生成服務、成本較高且結果不可預測（PROD07–PROD09、PROD20）。

Pixelle-Video 是 Streamlit／FastAPI 的短片自動化引擎，流程是 `script generation → image planning → frame-by-frame processing → video composition`。它可以接本地 ComfyUI、RunningHub 或明示的 DashScope/Wan、ARK/Seedance、Kling、OpenAI API；LLM 可配置 Qwen、GPT、DeepSeek、Ollama。API video 路徑有下載重試、審核失敗後 prompt neutralization retry，並嘗試用旁白長度與相鄰片段資訊改善連續性（PROD10–PROD12）。官方 source 沒有 L4／A100 的 VRAM 或 host-RAM benchmark；一篇二手指南另報其 local/API 路徑與資源數字，須按二手證據使用（PROD18）。

waoowaoo 是 self-hosted preview workspace，不是本地影片模型。README 明示透過 OpenRouter 呼叫 GPT Image 2、Nano Banana、Seedance、MiniMax H3/H3 Max；H3 Max 在此 preview 只收單一 first frame，且 preview 不含 music／voiceover controls。Docker Compose 封裝 Next.js、MySQL、Temporal、Redis、MinIO、Caddy；provider calls 由使用者 OpenRouter 帳戶付費（PROD13–PROD14）。v0.5.0-beta.1 起 license 是 Elastic License 2.0，且 repo 自己標成 source-available、不是 OSI-approved open source。

video-autopilot-kit 的公開核心是 Editkin v4 execution contract，不是生成模型。Python／FFmpeg 只做素材分析、正規化和 QA；實際 timeline 需 Editkin 支援環境回傳 receipts。合約含 source-byte binding、evidence、plan、audit、atomic apply、render、真人審片與 outcome，可續跑；自包含 examples 可產生 1080×1920 synthetic Short，但不等同真素材的成片 benchmark（PROD15–PROD16）。

h3lite 是 hardware-aware Codex skill，將 MiniMax H3 local generation 路由到 ComfyUI。官方支持路線是 Windows + NVIDIA；Linux + NVIDIA 為 experimental。它保存 `anchors.json`、在 `manifest.json` 記錄路徑，以首／中／尾幀 `anchor_qa` 驗收，但身份、服飾與構圖仍需人工複核。官方同一 Set B、640×352、4 steps、原生音訊條件報 RTX 4060 Ti 16GB／32GB 約 77.08s、RTX 4070 Laptop 8GB／32GB 約 591.22s；沒有 L4 或 A100 直接測量（PROD17）。

## Evidence

| 框架／來源 | 生成與 orchestration 邊界 | 依賴／部署證據 | 產物、驗收、重試或成本紀錄 |
|---|---|---|---|
| OpenMontage canonical | Agent 是控制平面；Python 是 tools/persistence；可用 cloud、local GPU、ComfyUI、stock；config.yaml 列 LLM provider 欄位，但架構文件稱 agent 是控制平面 | Python ≥3.10、FFmpeg；Node.js optional；Remotion Node 18+、HyperFrames Node ≥22；GPU/CUDA 只在 local generation 需要 | YAML manifests、JSON schemas/checkpoints、scene_plan／asset_manifest／edit_decisions／render_report；pre-compose gate；ffprobe、4-frame extraction、audio silence/clipping、subtitle與delivery promise 檢查；budget estimate→reserve→reconcile，預設 total cap $10、單 action $0.50（作者文件） |
| OpenMontage local/provider docs | `wan_video`、`hunyuan_video`、`cogvideo_video`、`ltx_video_local`；ComfyUI tool 明列 MiniMax H3 local graph 與 partner nodes；沒有把「OpenAI-compatible」當 H3/Wan 支持證據 | local video 需 CUDA；文件列 Wan2.2 TI2V-5B 12GB、Wan2.1 1.3B 6GB、Wan2.1 14B 24GB、LTX-2 8GB 等作者 VRAM 類別；ComfyUI URL 可 override；Partner Node 需網路、登入 Comfy、prepaid credits | H3 local no API charge；Partner Node 文件列 Gemini ~$0.146/s、Seedance ~$0.148/s 480p／$0.333/s 720p、MiniMax H3 ~$0.129/s 768P／$0.186/s 2K；Wan 長片以約 5s segment chain，文件明示 chaining drift；12GB path 有 1.97GB peak 的作者測量，但無 L4/A100 wall time |
| FireRed-OpenStoryline | 自有 footage 或 Pexels；MCP nodes 做搜尋、切鏡、理解、script、voiceover、timeline、render；沒有本地 video generation model 的明示完成路徑 | Python ≥3.11；requirements 含 MoviePy、FFmpeg Python、TransNetV2、librosa、torchaudio、FAISS CPU、LangChain/MCP；Docker 是 python:3.11-slim + ffmpeg/wget/unzip/git-lfs/curl | LLM/VLM config 各 `max_retries=2`；TransNet device 預設 CPU、視覺理解 2 fps／clip 上限 64 frames；TTS 可 MiniMax／Bytedance／302；AI transition 可 DashScope Wan／MiniMax Hailuo，作者警告高成本與不確定性；partial redo 與 Skill archive 已有文件 |
| Pixelle-Video | LLM script→每鏡 image/video→TTS→BGM→template／FFmpeg；本地 ComfyUI、RunningHub、直連 API 可替換 | source `pyproject.toml` 要 Python ≥3.11；依賴 Streamlit、FastAPI、ffmpeg-python、ComfyKit、MoviePy、Playwright；Docker python:3.11-slim，系統裝 FFmpeg、CJK fonts，ports 8000/8501 | 官方 README 有 dynamic video API 的 network retry、content-review neutralization retry、旁白時長／鄰鏡 continuity hint；release page 有 Windows packages；官方沒有 GPU/host RAM benchmark |
| waoowaoo | Assistant 在 canvas 建 brief／asset／版本；OpenRouter model list 含 MiniMax H3/H3 Max、Seedance 等；preview 的 H3 Max 只有 single first frame | release Compose 需 Docker Engine/Desktop、Compose ≥2.24.4、Git、POSIX shell、flock；host 可不裝 Node/MySQL/Redis/Temporal/FFmpeg；source build 才需 Node 22+／npm | local MySQL、Temporal、Redis、private MinIO、Caddy；API calls paid through own OpenRouter account；preview 不含 music／voiceover，沒有本地 GPU/VRAM 數字 |
| video-autopilot-kit | Editkin v4：evidence→plan→audit→atomic apply→render；Python/FFmpeg 是支援層，非另一 editor runtime | Python 3.9+；FFmpeg/ffprobe；Pillow、numpy、opencv-contrib runtime；無生成 backend／model／GPU requirement | receipts、reconcile、fail-closed gates、technical QA 後真人審片；examples/01 可合成 1080×1920 Short，02 是 contract self-test；release page 顯示 v0.23.0，頁面日期只顯示 27 Aug |
| h3lite | Codex/WorkBuddy skill 路由 T2VA/I2VA/FL2VA/Ref2VA 到 ComfyUI；不是獨立 inference backend | Windows + NVIDIA 主支持；Set A W4A8 + 4B INT4 text encoder，Set B 4B FP8 encoder；官方 8GB／16GB GPU rows 都配 32GB RAM | `anchors.json` + `manifest.json`；`anchor_qa` first/middle/last；fast=4 steps 640×352 native audio，balanced=6、quality=8；4060Ti 16GB 77.08s、4070 Laptop 8GB 591.22s；Linux experimental、無 L4/A100 measurement |

## 成片／pipeline／artifact evidence

- OpenMontage README 的 pipeline 表列 Animated Explainer、Animation、Avatar Spokesperson、Cinematic、Documentary Montage、Hybrid、Localization & Dub、Podcast Repurpose、Screen Demo、Talking Head 等；每條共用 `research → proposal → script → scene_plan → assets → edit → compose`。README 範例宣稱 The Last Banana 為 60s、6 個 Kling v3 clips、Google Chirp3-HD、字幕與 Remotion，總成本 $1.33；Void 為 4 張 GPT Image、TTS、音樂、WhisperX word-level subtitles，$0.69。這些是作者展示／成本宣稱，不是本次獨立重跑。
- OpenMontage Prompt Gallery 列 zero-key `make demo` 三個 40–50s composition demo；zero-key agent pipeline 45–90s 的 estimated 5–15min、$0；FAL_KEY image paths 約 10–20min／$0.15–$1.00；premium cinematic 30s 約 25–40min／$2.50。Prompt Gallery 自稱 community-maintained 且 tested，但沒有外部 quality score。
- FireRed README 提供八類 demo（Zhongcao、Humorous、Product Picks、Artistic、Unboxing、Talking Pet、Travel Vlog、Year-in-Review）；作者警告 README demo heavily compressed，且第一列 open-source assets 與第二列 Xiaohongshu asset library 是不同效果來源。
- Pixelle README 提供 AI Avatar、Image-to-Video、Motion Transfer、portrait／landscape templates；output 在 `output/`，UI 顯示 script→images→voice→composition 的進度與片長／檔案大小／分鏡數。v0.1.8 release 明示 custom media、video understanding、Index-TTS、Wan2.2 workflows 與音頻合併邏輯；v0.1.14 明示 motion transfer 與 local workflows。
- video-autopilot examples 是 synthetic／disposable fixture；其 contract 要求 receipts、audit、reconcile，且技術 QA 後仍要真人審片，不能用機器代填 certified。
- h3lite 第一次驗收 prompt 是 5 秒、簡單動作與明確聲音的紅球影片；複雜多鏡頭要先低解析度跑完整分鏡，再升畫布，長任務保留每鏡 log。

## 實際硬體／部署數字（只保存原始條件）

| 來源 | 原文條件 | 可記錄數字 | 限制 |
|---|---|---|---|
| OpenMontage provider docs | 作者 local model table／12GB sequential offload example | Wan2.2 TI2V-5B 12GB 類別；704×480 sequential path peak 1.97GB；每 denoise step 約 4s PCIe traffic | 不是 L4/A100 benchmark；沒有完整成片 wall time／host RAM |
| h3lite | Set B、640×352、4 steps、原生音訊、同 prompt／seed | RTX4060Ti 16GB + 32GB RAM 77.08s；RTX4070 Laptop 8GB + 32GB RAM 591.22s | 官方 skill 作者測量；無 L4/A100 |
| Pixelle 二手指南 | API／local paths；作者整理而非上游 benchmark | API 3–8min image、10–30min video；local ComfyUI 5–15min；WAN 2.1 local 16GB min／24GB recommended；models 建議至少 50GB disk | 二手、未核對 seed／resolution／peak VRAM；不能當本項主 benchmark |

## Unknown / Search boundary

- 沒有找到任何上述 framework 在單 L4 24GB 或單 A100 + High RAM 上，對同一 prompt／seed／解析度／frames／precision 的完整成片 benchmark（生成、TTS、合成、QA、peak VRAM、host RAM、wall time）。
- OpenMontage 的 local provider VRAM 表是文件中的 model class／routing metadata，不代表在 L4 或 A100 已驗證；OpenMontage 明示 MiniMax H3 local graph，但本次沒有看到該 graph 在指定 GPU 的完整成片 log。
- FireRed、waoowaoo、video-autopilot-kit 沒有公開本地影片模型的 L4/A100 成片測量；FireRed 的 transitions 是第三方 API，waoowaoo preview 是 OpenRouter paid calls，video-autopilot 的 Editkin runtime 是外部契約。
- Pixelle 的 main source 已從 `AIDC-AI/Pixelle-Video` 轉到頁面顯示的 `ATH-MaaS/Pixelle-Video`；release page 最新列 `v0.1.15`，current `pyproject.toml` version 是 `0.2.0`，兩者版本語境未在本次合併為同一 release。
- `Open-Montage-app/OpenMontage` 與 `calesthio/OpenMontage` 在本次讀到的是兩個 owner／兩個 repo；沒有把前者 README 或 release 當成 canonical repo 的另一個 benchmark。YouTube/X 對 OpenMontage 的直接頁面在本工具不可讀，社群索引只作連結定位，沒有將其內容當主要證據。
- 角色身份、跨鏡服裝／構圖、聲音身份、lip-sync 或音畫對齊的獨立質量分數均未找到；框架的 QA／continuity 描述仍是作者功能／流程宣稱，不能替代受控驗收。

## Sources

- PROD01 — [GitHub API: calesthio/OpenMontage](https://api.github.com/repos/calesthio/OpenMontage)（owner、`fork:false`、license、created/updated/pushed metadata；checked 2026-10-10）。
- PROD02 — [OpenMontage ARCHITECTURE.md](https://raw.githubusercontent.com/calesthio/OpenMontage/main/docs/ARCHITECTURE.md) 與 [config.yaml](https://raw.githubusercontent.com/calesthio/OpenMontage/main/config.yaml)（agent-first control plane、Python/manifest/schema/checkpoint、dependencies、LLM provider fields；last-updated in architecture file 2026-03-28；checked 2026-10-10）。
- PROD03 — [OpenMontage README](https://github.com/calesthio/OpenMontage)（pipeline、providers、demo claims、quality gates、output profile；checked 2026-10-10）。
- PROD04 — [OpenMontage PROVIDERS.md](https://raw.githubusercontent.com/calesthio/OpenMontage/main/docs/PROVIDERS.md)（ComfyUI/H3 local、Partner Node costs、local model VRAM classes、Remotion/HyperFrames/FFmpeg、long-clip chaining；checked 2026-10-10）。
- PROD05 — [OpenMontage PROMPT_GALLERY.md](https://raw.githubusercontent.com/calesthio/OpenMontage/main/PROMPT_GALLERY.md)（zero-key demos、estimated time/cost、animation/HyperFrames/premium examples；checked 2026-10-10）。
- PROD06 — [Open-Montage-app/OpenMontage](https://github.com/Open-Montage-app/OpenMontage) 與 [release page](https://github.com/Open-Montage-app/OpenMontage/releases)（另一 owner、2 commits、MIT、release page 顯示 23 Sep 但未顯示年份；checked 2026-10-10）。
- PROD07 — [FireRed-OpenStoryline README](https://raw.githubusercontent.com/FireRedTeam/FireRed-OpenStoryline/main/README.md)（features、news dates、demo、TODO、Docker/Quick Start；checked 2026-10-10）。
- PROD08 — [FireRed config.toml](https://raw.githubusercontent.com/FireRedTeam/FireRed-OpenStoryline/main/config.toml)、[requirements.txt](https://raw.githubusercontent.com/FireRedTeam/FireRed-OpenStoryline/main/requirements.txt)、[API key guide](https://github.com/FireRedTeam/FireRed-OpenStoryline/blob/main/docs/source/en/api-key.md)（LLM/VLM/TTS/transition providers、retry、CPU ASR/FFmpeg/Python deps；checked 2026-10-10）。
- PROD09 — [FireRed user guide](https://github.com/FireRedTeam/FireRed-OpenStoryline/blob/main/docs/source/en/guide.md)（Pexels, partial redo, interrupt, Skill archive；checked 2026-10-10）。
- PROD10 — [Pixelle-Video README_EN](https://github.com/ATH-MaaS/Pixelle-Video/blob/main/README_EN.md)（AIDC-AI URL redirects to ATH-MaaS page; pipeline, providers, retry, local/cloud paths, releases noted in README；checked 2026-10-10）。
- PROD11 — [Pixelle pyproject.toml](https://github.com/ATH-MaaS/Pixelle-Video/blob/main/pyproject.toml) and [Dockerfile](https://github.com/ATH-MaaS/Pixelle-Video/blob/main/Dockerfile)（Python ≥3.11, version 0.2.0, deps, FFmpeg/fonts, ports 8000/8501, Playwright；checked 2026-10-10）。
- PROD12 — [Pixelle releases](https://github.com/AIDC-AI/Pixelle-Video/releases)（page redirects ATH-MaaS; v0.1.15 latest displayed, v0.1.14/v0.1.12/v0.1.8 feature notes and dates without year; checked 2026-10-10）。
- PROD13 — [waoowaoo README](https://github.com/waooAI/waoowaoo)（preview scope, OpenRouter models, H3 Max first-frame limit, tech stack, paid calls, license note；checked 2026-10-10）。
- PROD14 — [waoowaoo INSTALL.md](https://github.com/waooAI/waoowaoo/blob/main/docs/INSTALL.md) and [releases](https://github.com/waooAI/waoowaoo/releases)（self-hosted v0.5.0-beta.1, Docker/Compose/flock, local services, Node 22 source path, release page 05 Sep date without year；checked 2026-10-10）。
- PROD15 — [video-autopilot-kit README](https://github.com/Hao0321/video-autopilot-kit)（Editkin v4, receipts, examples, Python/FFmpeg dependencies, human review；checked 2026-10-10）。
- PROD16 — [video-autopilot-kit releases](https://github.com/Hao0321/video-autopilot-kit/releases)（v0.23.0 latest displayed, v0.19/v0.13.1 architecture and release QA claims, dates displayed without year；checked 2026-10-10）。
- PROD17 — [h3lite README](https://github.com/Rimagination/h3lite)（ComfyUI routing, anchor card/QA, Windows/NVIDIA matrix, 4/6/8 steps, 4060Ti/4070 timings, sample artifacts；checked 2026-10-10）。
- PROD18 — [Pixelle secondary guide](https://blog.mushroom.cv/blog/pixelle-video-ai-short-video-engine-guide/)（2026-07-08; API/local paths, 16/24GB Wan2.1 guidance, 50GB disk, estimated times/costs; secondary, not upstream benchmark）。
- PROD19 — [Repo Dispatch OpenMontage field note](https://repodispatch.online/en/dispatches/118-calesthio-openmontage/)（secondary source read for official YouTube/X/README demo links and broad discovery; direct YouTube/X pages blocked here; checked 2026-10-10）。
- PROD20 — [FireRed official demo page](https://fireredteam.github.io/demos/firered_openstoryline/)（LLM/VLM intent routing, MCP primitives, middleware/memory, demos；checked 2026-10-10）。

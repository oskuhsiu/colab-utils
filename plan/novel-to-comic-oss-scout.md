# Open-Source Scouting Report: Codex + ComfyUI/Qwen 漫畫流程

> Decision Verdict: Option B — 組合既有工作流與本機生圖工具
> Estimated MVP Delivery: 原頁面型 PoC 的估算為 4–7 個工作日；改成網漫 scroll-first 分鏡與長條組版後尚待重估
> Primary Recommendation: 借用 [Codex Novel-to-Comic Studio](https://github.com/lhfer/codex-novel-to-comic-studio) 的故事改編與審核階段，改成網漫 episode／縱向格序資料契約，搭配版本化角色與畫風記憶及 ComfyUI/Qwen 分格生成

調查日期：2026-09-24。GitHub stars、license、commit 以當日 REST API/repository 資料核對；分數是相對於這個使用情境的粗略適配度。這份計畫更新了先前「找一套小說轉漫畫成品」的範圍，改以可組合的階段和資料交接格式為主。

## 1. Requirement Scope and Boundaries

- Core Business Loop: Codex 將小說改編為有因果與情緒節奏的網漫 episode／縱向格序；作者先審核故事取捨與滑動節奏，再由 Qwen 產生分格圖、後製排字並組成手機下滑長條。
- Target Delivery Type: 單人、本機 Codex 工作流加 ComfyUI；以檔案與 JSON 交接，不先做新的多使用者網站。
- Licensing Constraint: 自建程式優先採 MIT／Apache-2.0；小說必須是自有、公共領域或已獲授權可改編的內容。
- 作者指定的設計方向：Codex 負責小說理解與改編，不逐段照搬原文；成品以手機縱向下滑的網漫 episode 為原生格式，不採固定翻頁頁數；以跨章固定的角色/畫風 bible 與參照控制視覺延續。生圖工具可以替換。
- 不把影片／漫劇功能當作 MVP 必需。劇本或戲劇化場景拆解可作為可選前處理。

### Qwen Image 2.1 的核對事項

- 官方模型頁標示支援最多 10 張參考圖、圖像編輯和局部編輯，且 ComfyUI 在 2026-09-20 起原生支援。這些能力適合拿來測角色、服裝和風格參考能否延續，不代表跨頁一致性已經得到保證。[官方模型卡](https://github.com/QwenLM/Qwen-Image-2.1) · [ComfyUI 官方工作流文件](https://github.com/Comfy-Org/docs/blob/main/tutorials/image/qwen/qwen-image.mdx)
- 授權需要特別處理：官方 repo 使用 **Qwen Research License Agreement**，授權範圍限制為非商業用途；商用需另外取得授權。因此可稱為公開權重／研究授權模型，但不能當成 MIT/Apache 這類可自由商用的開源授權。[官方授權條款](https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE)
- 官方模型卡將架構描述為 7B 單流 DiT，使用 Flow Matching scheduler。為避免技術描述過度簡化，本計畫不以「完全非 diffusion」作為可控性的保證；把「比既有工作流更容易控制」列成待測假設，重點測試多參考圖、編輯和逐頁審核的實際效果。[官方架構說明](https://github.com/QwenLM/Qwen-Image-2.1#architecture)
- Qwen Image 2.1 剛發布數日，尚無足夠證據證明它能在長篇多頁漫畫中維持臉、服裝、道具和畫風。先用短篇多頁試作量化，不要一開始批次生成整本。

## 2. Shortlisted Components

這四個專案分別覆蓋漫畫頁企劃、小說轉劇本、角色視覺記憶和 ComfyUI 生圖管理；沒有一個單獨負責整條流程。

| Repository | URL | Stars | Last Commit | Tech Stack | License | Risk Level | Rating |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Codex Novel-to-Comic Studio | [Repo](https://github.com/lhfer/codex-novel-to-comic-studio) · [metadata](https://api.github.com/repos/lhfer/codex-novel-to-comic-studio) | 17 | [2026-05-19](https://github.com/lhfer/codex-novel-to-comic-studio/commit/7c64ef96b0ccb28a55ae514e185e92cb2364daac) | Python、Codex skills | MIT | Warning | 4/5 |
| AI novel2script | [Repo](https://github.com/Axelxrd/ai-novel2script) · [metadata](https://api.github.com/repos/Axelxrd/ai-novel2script) | 4 | [2026-06-06](https://github.com/Axelxrd/ai-novel2script/commit/d17522da1809d41c1419afb0c693db58da08ca5f) | Python CLI/Web | MIT | Warning | 3/5 |
| Agent Mangaka Forge | [Repo](https://github.com/RemiPelloux/agent-mangaka-forge) · [metadata](https://api.github.com/repos/RemiPelloux/agent-mangaka-forge) | 13 | [2026-04-29](https://github.com/RemiPelloux/agent-mangaka-forge/commit/1168ba358e539a94a3a1743ecbf98dbdf9720d65) | Codex skill、Python stdlib helper | MIT | Warning | 4/5 |
| ComfyUI Storyboard | [Repo](https://github.com/colorAi/comfyui-storyboard) · [metadata](https://api.github.com/repos/colorAi/comfyui-storyboard) | 72 | [2026-01-19](https://github.com/colorAi/comfyui-storyboard/commit/42b45db94106a466909bf6a55e37f020f89fa47a) | ComfyUI custom node、JavaScript/Python | Apache-2.0* | Warning | 4/5 |

\* ComfyUI Storyboard 的 `LICENSE` 是 Apache-2.0，但 README 兩個語言版本寫 MIT。使用前以 LICENSE 檔案為準，並可向作者確認文件差異。[LICENSE](https://github.com/colorAi/comfyui-storyboard/blob/main/LICENSE) · [README](https://github.com/colorAi/comfyui-storyboard#license)

## 3. Five-Pillar Due Diligence

### Codex Novel-to-Comic Studio

- Maintenance & Governance: 2026-05-19 更新；17 stars、3 forks、1 位可見貢獻者，GitHub API 顯示目前只有 1 個 commit。已有範例、驗證工具與測試，但維護者與更新歷史仍少。
- Community Health: 社群小，適合先試用並固定一個自己的副本，不應假設有成熟支援。
- Setup Friction: 克隆後放入 TXT/EPUB，再執行來源解析與檢查工具；Codex 依 skill 的階段產出改編資料。使用者已計畫用 Codex，接入阻力低。
- Modularity & Reusability: 以故事優先的順序產生 story bible、visual bible、page story plan、page script、storyboard 和每頁 director brief。`make_image_tasks.py` 將頁面 prompt、參考圖和目標 PNG 路徑輸出成 JSON，適合作為 Qwen runner 的輸入。預設圖片階段是 Codex Image2，並非 Qwen，但可以把圖片生成留在外部工作流。[README](https://github.com/lhfer/codex-novel-to-comic-studio#readme) · [image task builder](https://github.com/lhfer/codex-novel-to-comic-studio/blob/main/TOOLS/novel_to_comic/image_tasks.py)
- Supply Chain & Licensing: 專案程式碼採 MIT。Image2 是預設生成路徑，但本計畫可改由本機 ComfyUI 生成；小說與模型素材仍要各自確認權利。未做套件 CVE 掃描。
- Summary: 最合適當作 Codex 的頁面企劃和任務格式參考；保留它的中間產物與驗證器，把圖片生成換成本機 Qwen adapter。

### AI novel2script

- Maintenance & Governance: 最新 commit 2026-06-06，GitHub REST 顯示最近 push 為 2026-07-24；4 stars、3 個 open issues，可見貢獻者是作者與 Dependabot。
- Community Health: 使用者和外部貢獻者少，適合取用輸出概念，不宜把它當成熟改編引擎。
- Setup Friction: `pip install -e ".[dev]"` 後可跑 CLI；不設定 API 時使用啟發式改編，設定 OpenAI-compatible API 才會用 LLM 增強。它要求至少 3 個章節，短篇試作未必合用。
- Modularity & Reusability: 把小說拆成幕、場景、動作、對白和轉場，並產生 `structure_map`、`story_bible`、coverage/adaptation reports 及 Fountain。這是你提到的 novel-to-drama 類中間層；Codex 可以借用其資料欄位與檢查概念，沒有必要再跑一個重複的 LLM 階段。[README](https://github.com/Axelxrd/ai-novel2script#readme)
- Supply Chain & Licensing: MIT；依賴未作 CVE 掃描。
- Summary: 可以在 Codex 難以保留場景因果或戲劇目標時作為參考；不是漫畫分鏡器，也不會生成圖片。

### Agent Mangaka Forge

- Maintenance & Governance: 2026-04-29 更新，13 stars、0 forks、2 個 commits、1 位作者；專案很新且維護面窄。
- Community Health: 小型個人 skill，還沒有可觀察的外部維護社群。
- Setup Friction: 將 skill 複製到 Codex skills 路徑並重啟；本機 Python helper 僅用標準函式庫。
- Modularity & Reusability: `img-memory` 將人物、地點、道具、角色版本及參考圖片分開保存；缺少必要角色參考時先補圖，再生成漫畫頁。Helper 只管理 metadata/目錄，不負責生成圖片。可以重用它的 identity markers、base/variant/evolution 版本與 `record-page` 概念，並把可見圖片交給 Qwen workflow。[README](https://github.com/RemiPelloux/agent-mangaka-forge#readme)
- Supply Chain & Licensing: MIT；helper 無外部 Python 套件。Skill 本身仍假設 Codex 可看見並生成參考圖，Qwen/ComfyUI 接口需要自行定義。
- Summary: 對整本漫畫的角色版本與視覺記憶很對題；建議先取用資料結構和 pre-generation gate，不必把整份生成指令當作固定產品流程。

### ComfyUI Storyboard

- Maintenance & Governance: 2026-01-19 最新 commit；72 stars、10 forks、24 commits，但只有 1 位可見貢獻者，2026 年 1 月後沒有新 commit。安裝前先在目前 ComfyUI 版本做一次相容性試跑。
- Community Health: 四個元件中 stars/forks 相對較高，但近期維護訊號弱。
- Setup Friction: 可從 ComfyUI Manager 安裝，也可複製到 `custom_nodes` 後重啟。需要在介面上對應 prompt、save image 和可選 reference-image 節點。
- Modularity & Reusability: 提供 shot grid、相機角度 prompt、順序批次執行、SQLite 保存和回寫 workflow。可以把一張完整漫畫頁當作一個生成 task。它是 shot/workflow 管理器，不會分析小說或保證角色連續；README 只描述一個可選參考圖節點，多參考圖 Qwen 編輯可能要改 workflow/節點映射。[README](https://github.com/colorAi/comfyui-storyboard#readme)
- Supply Chain & Licensing: 實際 LICENSE 是 Apache-2.0；README 宣稱 MIT，需釐清此文件不一致後再散佈修改版。未做依賴 CVE 掃描。
- Summary: 可快速試出 ComfyUI 端的逐頁工作台，但不是整個漫畫製作系統，也不應依賴它實作角色記憶。

### 其他可拆用的候選

- [ScriptBreak](https://github.com/wassermanproductions/scriptbreak)（Apache-2.0；54 stars；2026-08-05 commit）從既有 screenplay 拆出 scenes、characters/locations/props bibles、shot lists、timeline 和可交給任意 LLM/image generator 的 prompt packs。它是劇本輸入，不是小說解析器；若 Codex/Novel2Script 已產出劇本，可作為 shot breakdown 的替代來源。
- [mok-tua](https://github.com/the1truedan/mok-tua)（MIT；2026-09-24 commit）是本機 script-to-shot conductor，可編排 ComfyUI storyboard stills 和可選影片工具；0 stars、單一維護者且範圍較廣，先參考其 shot ledger/privacy gates，不作 MVP 依賴。
- [Inkstone](https://github.com/phaethix/inkstone)（MIT；約 6–7 stars；2026-09-14 commit）提供 TXT→人物/場景→漫畫頁→PDF/PNG 的完整流程，但以 Agnes cloud API 為預設；其 openai-compatible image adapter 仍期待特定 Agnes image payload，不是已確認的 ComfyUI/Qwen 即插即用方案。保留作整體流程參考。
- [Rsaga-skill](https://github.com/rsagacom/Rsaga-skill) 中文流程包含逐句改編、分鏡、視覺審核與 B5 排版，但 GitHub 沒有偵測到 license，故僅作功能參考，不複製或 fork。

## 4. Architectural Decision Verdict

- Recommended Path: Option B — file-contract sidecar。
- Key Justification: 由 Codex 負責理解小說、做取捨並核准 episode 級改編；將故事 beat 和縱向 scroll layout 分開存成可審核資料，再由 Qwen 產生 panel art、後製文字並組成連續長條。Character/style memory 獨立保存並由每格共用。這樣可替換圖像後端，不需 fork 整套小說改編 app。

### 運作方式：是否需要操作 ComfyUI？

- 這是**流水線式，但有人工審核閘門**：小說理解 → episode 故事改編 → 核准縱向分鏡 → 逐格生圖 → 後製排字與連續長條組版 → 手機預覽/返修；不是把原文逐段貼進頁格，也不是固定頁數的一頁頁翻閱。
- 若以 ComfyUI 為生圖後端，ComfyUI server 需要啟動並載入已設定好的 Qwen workflow；Python runner 可透過 ComfyUI 的 `/prompt`、WebSocket/`/history` 提交和等待任務、取回圖片。官方範例就是程式送入 workflow，不要求每張圖都在 UI 手動按 Queue。[ComfyUI API example](https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/websockets_api_example.py) · [API routes](https://docs.comfy.org/development/comfyui-server/comms_routes)
- **日常不必操作 ComfyUI UI**：用 Codex 啟動 episode/panel 任務與 runner，ComfyUI 在背景負責推論。需要手動開 UI 的時機是第一次配置/除錯 workflow，或日後要調整節點與參數。MVP 審核看縱向長條及手機視窗預覽；ComfyUI Storyboard extension 是可選介面，不是必需依賴。
- 若希望**連 ComfyUI 都不運行**，Qwen 官方也提供 Diffusers `QwenImage21Pipeline` 和 vLLM image-generation API；將 runner 改接其中一種即可，但要另寫 provider/圖片參考輸入 adapter。[Qwen Image 2.1 inference examples](https://github.com/QwenLM/Qwen-Image-2.1)

### 遠端 runtime 生命週期決策

- Colab 使用一個固定命名的 session/kernel 處理整個系列；Codex 每次產生新 episode 時，把 episode bundle（故事改編、scroll board、story/style bible、圖片參照及已有 panel）上傳到同一個 session。
- 模型由持續存在的 Colab Jupyter kernel 持有；`start` 時載入一次，後續只呼叫 panel worker 並沿用相同 pipeline instance。不要在每章的 subprocess 裡重新執行 `from_pretrained`，也不要用每工作一個 VM 的 `colab run`。
- 每章 run manifest 記錄固定的 `session_name` 與 `model_instance_id`，以便驗證跨章確實重用模型。只有明確 `stop` 或 kernel 被重啟才釋放/重載模型。
- Colab CLI 說明同一 session 的 kernel 狀態可跨 `colab exec` 保留；這是本實作選擇的狀態邊界。Colab 的 keep-alive/服務限制仍可能讓 session 失效；發生 kernel restart 後才需要重新載入模型。

### 建議組合

```text
TXT / EPUB
   ↓
Codex：story bible + series visual bible + 原文因果/情緒脈絡
   ↓
Codex：episode story spine → scroll beat map → webtoon storyboard
   ↓                         ↘ canonical character/style refs + approved prior panel
Qwen：逐格生成無字 panel art（沿用同一常駐模型與核准參照）
   ↓
排入可變格距的縱向 episode canvas + 後製台詞/旁白
   ↓
手機視窗通讀 → 修訂故事、節奏或單格 → 核准並固定版本
```

- novel2script 可作為 Codex 提示與 JSON schema 的參考：每場保存戲劇目標、衝突、轉折與原文來源跨度；不要求必須先把小說改成電影劇本。
- ScriptBreak 適合已經有 screenplay 時，補做場景元素 bible 和 shot breakdown。短篇漫畫可由 Codex 直接輸出頁面計畫，避免把相同小說再送進另一套 LLM。
- 每格輸入固定 canonical refs（角色臉/全身/服裝、畫風參考、必要場景/道具），需要時再加一張已核准的相鄰格作場景連接。不要只用上一格作唯一參考，以免早期偏差逐格累積。這是建議的可測設計，不是已驗證的 Qwen 特性。
- Qwen 2.1 支援最多 10 張參考圖與圖像編輯；ComfyUI Storyboard 的 README 只確認一個可選參考圖節點。第一個原型應直接用官方 Qwen 2.1 ComfyUI image-edit workflow 測 multi-reference；若工具不支援，再擴充 node mapping。[Qwen-Image-2.1](https://github.com/QwenLM/Qwen-Image-2.1) · [ComfyUI Qwen workflows](https://github.com/Comfy-Org/docs/blob/main/tutorials/image/qwen/qwen-image.mdx)
- ComfyUI 官方也有 Qwen Image Union Control workflow，列出 lineart、pose、depth、canny 等結構控制；該頁沒有證明所有 control LoRA 都與 Image 2.1 相容，先驗證權重版本再加入 MVP。[官方 control workflow](https://github.com/Comfy-Org/docs/blob/main/tutorials/image/qwen/qwen-image.mdx#qwen-image-union-control-lora-workflow)

## 5. Minimalist MVP Plan (1-1-1-1 Rule)

- Core User Story: 作為單人漫畫作者，我可以把一段小說改編成可審核、適合手機下滑觀看的網漫 episode，逐格生成與返修 Qwen 圖像，最後輸出連續長條。
- Starter Architecture: Codex Studio 的檔案化故事改編與審核階段作為參考；一個本機 Python CLI 從 `episode-board.json` 讀取故事 beat、scroll 節奏、panel art prompt、reference/output path，提交到已運作的 Qwen workflow；Agent Mangaka 的 image-memory 命名與版本化供 Codex 檢查。
- Minimal Schema Draft:

  ```text
  Entity: ComicProject (one JSON manifest + files)
  - id: project slug
  - source_path: rights-cleared TXT/EPUB path
  - canon: story/style bible paths
  - assets: character/location/prop reference manifests
  - episodes: narrative goal/hook, source spans, adaptation decisions, continuity-in/out state
  - panels: ordered visual beat, reader inference, camera/composition, text overlay, scroll gap/reveal, reference roles, prompt, status, output path
  - render: model/runtime/template/workflow versions, reference hashes, per-panel seed/settings, assembled strip/phone-preview paths
  ```

- Milestones:
  - Phase 1: 以布丁倉鼠第 1、2 章作改編試材，Codex 先產出 story/style bible、episode story spine 與 scroll-first storyboard；人工審核保留/刪併/改寫/視覺化的理由和讀者情緒節奏，再畫低保真縱向縮圖。
  - Phase 2: 接 Qwen 2.1 逐格生成無字 panel art；固定同一常駐模型、版本化 prompt/參照和參數，後製排字後組成連續長條。比較同一 episode 的手機視窗預覽和通讀效果，再逐格審核。
- Scope Blacklist:
  - [ ] No authentication or multi-user accounts
  - [ ] No microservice decomposition or distributed queue
  - [ ] No video/animation, full novel batch run, analytics, or extra export formats beyond the core vertical episode strip and platform-sized slices
  - [ ] No automatic whole-book generation before human approval gates pass

### MVP 驗收條件

用一段連續網漫 episode 測同一角色、畫風與滑動節奏：

1. 每個故事 beat 能追溯來源段落；清楚標記內容如何保留、合併、改寫、轉為視覺、略去或新增。
2. 故事按 episode 和縱向格序設計；panel gap、留白時間、揭露時機、轉場和尾段 hook 都有明確閱讀目的，不以固定 2:3 頁數切故事。
3. 在手機視窗預覽時能順著下滑讀懂動作、情緒和文字；格間留白能呈現停頓/時間/期待，而非只是頁面空白。
4. 全段引用同一核准角色/畫風 bible 和參照規格；manifest 可重現模型、workflow、提示模板、參照 hash 與 panel seed。Seed 只供重現，不視為畫風鎖。
5. 台詞/旁白後製排版；修改一格不重生其他核准格，保留每格版本和可重組的 episode strip。

## 6. Next Actions

- [x] 以完整原文重做兩章 story spine 和 scroll-first storyboard；第一章 10 段／16 格，第二章 13 段／23 格，改編決策與來源跨度附在每段。
- [x] 定義並實作 `webtoon-storyboard.v1`、panel task、手機視窗與語義 gap、後製文字、reference roles、seed 和 runtime manifest。
- [x] 在一個固定 Colab session/kernel 依序生成兩章 768px 小圖；兩個 manifest 的 `model_instance_id` 同為 `945b1aef-9c7d-4088-b36c-b4b5670bafe7`，參照 hash 相同，39 格 seed 唯一且尺寸依構圖類別變化。
- [ ] 作者以兩章 HTML reader 作手機視窗通讀，確認節奏、畫風、角色狀態和中文排字，再依審稿結果修訂 panel；已記錄「倉鼠鏡頭角度重複」這個 novel-to-storyboard/prompt 問題，下一版要明確輪換 camera/pose。
- [x] 實作 panel art + 後製文字 + 縱向 HTML reader 流程；日常不要求手動操作 ComfyUI Storyboard。
- [x] Notebook 可選 512–1536px 寬，預設 768px；每格依 composition class 自動計算高度。另建核准後使用的獨立 2× Swin2SR T4 notebook，不與 Qwen 分享或重載 model。
- [x] Seed 基準固定為 42，按章／格穩定推導不同值；manifest 保存實際 panel seed，重跑同格不變。
- [x] 固定一個 Colab session/kernel 跨章處理任務，持有單一 Qwen pipeline instance 並保存 instance ID。

### 網漫分鏡與跨章畫風：首輪生成完成，待作者審稿及 angle-diversity 修訂

- 現有第 1、2 章 `page_plan.json` 是六張固定 2:3 圖、每張 4–5 格、逐頁重述大量原句的頁面型試作；它不具備網漫的可變縱向格序、scroll gap、手機視窗節奏與揭露時機。它只驗證過任務交接/生圖，不視為已核准的網漫分鏡。
- 網漫不是把傳統頁格垂直堆起來。以持續下滑與手機可視範圍為構圖單位；在縮圖階段就安排格與格的距離、留白時間、單格長高比例、轉場、讀者先看到/後看到什麼，利用滑動控制停頓和揭露。
- 故事改編先抽出因果鏈、角色目標/情緒轉折和每段讀者需要知道的內容；再選擇保留、合併、改寫、用動作/表情/環境代替內心旁白、刪除重複訊息或新增必要視覺橋接。每項改編可回查原文，但不要求一段原文配一格。
- 目前 run 記錄中章一六張圖片都是沿用舊圖，章二才用固定 runtime 新生成；雖然提交時看到相同 `model_instance_id`，這不是同樣內容在同一 instance 重跑的受控比較。因此不能把風格差異歸因於單純 reload，也不能據此排除 reload/環境版本差異。下一次對照需兩章各選同類型畫格，同一 session/model revision、提示模板、參照角色與生圖參數一起生成。
- 固定常駐 runtime 是避免每章載入不同模型環境的必要工程約束，不是畫風保證。畫風還需有可視規格（調色盤、線條、陰影/顆粒、材質細節密度、角色比例）、固定且有角色說明的 canonical refs、版本化 prompt/設定；生成前後以相鄰格 strip 和手機尺寸做人工 continuity gate。Seed 用來重現單次結果，不會自己鎖住不同畫面風格。
- 生圖先輸出 panel art，不讓模型同時做精準中文排版；依 panel/scene 組成連續 episode strip，再用字體疊加旁白和對白。這也讓改字不必重生畫面。
- 2026-09-24 已建立 [chapter 1 webtoon storyboard](../projects/pudding-hamster/chapter-01/webtoon_storyboard.json) 與 [chapter 2 storyboard](../projects/pudding-hamster/chapter-02/webtoon_storyboard.json)；生成 adapter、source-span validator、persistent Colab worker、可調 panel 寬度 notebook、HTML reader 和 optional post-review upscaler 已就緒。原有 `page_plan.json` 和整頁圖片保留作歷史樣本。
- 初次觀看 39 格後，作者指出布丁倉鼠常重複正面／半身角度。依目前觀察，這是 **novel-to-storyboard/prompt** 的鏡頭與姿勢變化約束不足：文本沒有在相鄰 panel 間強制遠近景、俯仰、側背面、動作方向和視線改變；記錄為後續 storyboard 修訂項，不據此判定 Qwen 模型載入或顯存出錯。本輪只保存觀察，不重生圖。
- 另在第 2 章 p12 視覺抽查到疑似多出第二隻布丁倉鼠；這是獨立單格連續性問題，先列待審，未重生。該 panel 帶入整頁風格與棲地參照；重跑時可比較保留／移除場景參照，但目前不推論為唯一原因。
- 原 session 當前已停止時，按系列固定名稱重新配置 A100 high-memory；本次兩章共用 instance `945b1aef-9c7d-4088-b36c-b4b5670bafe7`，都記錄 `model_reused: true`。作者之後要求中斷，Colab 確認 0 assignments。往後預設改為 A100 標準系統記憶體，不加 high-RAM；實際只有先前 high-RAM A100 configuration 完整生圖驗證過。
- 本機安裝的 Colab CLI 支援 T4/L4/G4/H100/A100，**不支援 V100**，且未知 GPU 名會 fallback 到 A100；CLI runner 現在只接受已知型號，避免聲稱已設定 V100。
- T4 放大基準與獨立 notebook smoke test：Swin2SR `caidas/swin2SR-classical-sr-x2-64` 對 768×1152 格峰值 10.11 GiB allocated／10.67 GiB reserved；最終 notebook 輸出精確 1536×2304，一格約 26.94s。T4 共 14.56 GiB，符合目前放大尺寸。樣本測試存在 tmp，不屬於兩章成品。
- 同一 T4 runtime 的 `realesrgan==0.3.0`/BasicSR 安裝 metadata 失敗；NCNN Vulkan 探查只找到 Vulkan loader，沒有 ICD manifest。根據目前 Colab 執行環境，先採用有實測的 Swin2SR，而非宣稱動漫專用 Real-ESRGAN 可直接使用。
- Qwen Image 2.1 加速器與圖片模型／放大器比較列於 [Qwen acceleration and upscaler OSS Scout report](qwen-image-acceleration-and-upscaler-oss-scout.md)。
- 遠端兩章生成已完成，但原 A100 high-RAM session 已照要求停止。後續 CLI 預設為 A100 標準系統 RAM；V100 不在該 CLI 的支援清單。
- 網漫創作與開源專案的依據、限制和本作縱向縮圖例子記在 [網漫分鏡研究](novel-to-webtoon-storyboard-research.md)。

## Sources

- [Qwen Image 2.1 官方 repository](https://github.com/QwenLM/Qwen-Image-2.1) · [Qwen Research License](https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE)
- [ComfyUI 官方 Qwen Image workflows](https://github.com/Comfy-Org/docs/blob/main/tutorials/image/qwen/qwen-image.mdx)
- [Codex Novel-to-Comic Studio](https://github.com/lhfer/codex-novel-to-comic-studio) · [image task contract](https://github.com/lhfer/codex-novel-to-comic-studio/blob/main/TOOLS/novel_to_comic/image_tasks.py)
- [AI novel2script](https://github.com/Axelxrd/ai-novel2script)
- [Agent Mangaka Forge](https://github.com/RemiPelloux/agent-mangaka-forge)
- [ComfyUI Storyboard](https://github.com/colorAi/comfyui-storyboard) · [actual Apache-2.0 LICENSE](https://github.com/colorAi/comfyui-storyboard/blob/main/LICENSE)
- [ScriptBreak](https://github.com/wassermanproductions/scriptbreak) · [mok-tua](https://github.com/the1truedan/mok-tua) · [Inkstone](https://github.com/phaethix/inkstone) · [Rsaga-skill](https://github.com/rsagacom/Rsaga-skill)
- [manhwa-forge](https://github.com/JesseRWeigel/manhwa-forge) · [MangstoonAI](https://github.com/jays0606/mangstoon_ai) · [BoredComic](https://github.com/youvandra/bored-comic)
- [網漫縱向分鏡研究與本作 thumbnail/schema](novel-to-webtoon-storyboard-research.md)

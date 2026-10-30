# Open-Source Scouting Report: Colab Video Upscaling and Camera Control

> Decision Verdict: Option B
> Estimated MVP Delivery: 2–3 days for one measured VSR loop; camera integration is a later, separately verified change.
> Primary Recommendation: FlashVSR as an isolated post-processing candidate; VideoX-Fun Wan2.2-Fun camera as the explicit-camera candidate.

本次完成的是研究與 skill 修訂，沒有啟動 GPU、安裝這些模型或宣稱上述 MVP 已實作。估時是規劃假設，依 Colab CUDA／attention 安裝與品質實測調整。

## 1. Requirement Scope and Boundaries

- Core Business Loop: 要求與人物／分鏡素材 → Colab 逐鏡生成及動作驗收 → 選用鏡頭影片超解析／剪輯 → 身份、動作、構圖與接點再驗收 → 交付。
- Target Delivery Type: CLI，延伸現有 `colab-video-studio`，不另建 UI 或服務平臺。
- Licensing Constraint: Internal Tool；優先 Apache-2.0／MIT 程式與權重，保留未來使用選擇。程式、權重、底模、依賴的授權分開確認。環境隔離不豁免任何授權要求。
- Technical neutrality: 依時序品質、實際 camera 接口、A100／Colab 摩擦、速度與身份風險選擇；不因既有 ComfyUI 或 Diffusers 而預設搬入整套平臺。
- Search boundary: 2026-10-01 的兩種 GitHub 搜尋模式及原始查詢、API／commit／license 細節見 [evidence report](video-speed-camera-evidence-20261001.md)。Luna 負責查找；主代理另讀決策關鍵的 FlashVSR 尺寸函式、SeedVR2 notice／transform、VideoX-Fun camera call。沒有 GPU benchmark 或依賴 CVE 審計。

## 2. Shortlisted Candidates

Stars／commit／license 是 2026-10-01 GitHub API 快照，並以權重 model card 交叉檢查。Rating 是本任務的粗略適配判斷，不是模型品質測量；全部保持 Warning，尚未通過 Colab／人物驗收。

| Repository | URL | Stars | Last Commit | Tech Stack | License | Risk Level | Rating |
| :--- | :--- | ---: | :--- | :--- | :--- | :--- | :--- |
| FlashVSR | [OpenImagingLab/FlashVSR](https://github.com/OpenImagingLab/FlashVSR) | 1,880 | [2026-09-01, cf910c61](https://github.com/OpenImagingLab/FlashVSR/commit/cf910c61a60733e610e9c6e8b607f80c3a6c202b) | PyTorch、DiffSynth、block-sparse attention | Code／v1.1 weights: Apache-2.0 | Warning | 3.5/5 |
| SeedVR2 | [ByteDance-Seed/SeedVR](https://github.com/ByteDance-Seed/SeedVR) | 1,380 | [2026-01-27, e4de8c24](https://github.com/ByteDance-Seed/SeedVR/commit/e4de8c24441a67e1b7df56abea10645059bb1185) | PyTorch、torchrun、FlashAttention／Apex | Code／3B weights: Apache-2.0 | Warning | 3/5 |
| Wan2.2-Fun camera | [aigc-apps/VideoX-Fun](https://github.com/aigc-apps/VideoX-Fun) | 2,275 | [2026-09-29, 4b7b6402](https://github.com/aigc-apps/VideoX-Fun/commit/4b7b6402a1e0f0406bd6801fb66c0a00bd922621) | PyTorch、Wan、camera pose／Plücker conditioning | Code／camera weights: Apache-2.0 | Warning | 3.5/5 |

[CamI2V](https://github.com/ZGCTroy/CamI2V) 為歷史相機控制參考：API 快照 171 stars、MIT、最後 commit 2025-09-29，已超過 12 個月篩選界線；DynamiCrafter 底模與本地 Wan2.2 不相容，排除部署 shortlist。[CameraCtrl II 原論文](https://openaccess.thecvf.com/content/ICCV2025/html/He_CameraCtrl_II_Dynamic_Scene_Exploration_via_Camera-controlled_Video_Diffusion_Models_ICCV_2025_paper.html) 的 bounded 查找未找到可 audit 的官方 repo；不當成可安裝方案。

## 3. Five-Pillar Due Diligence

### FlashVSR

- Maintenance & Governance: 最近一個月內有 commit；無 GitHub release，最近可見 PR 為 2026-07-16；contributors snapshot 只顯示一個主要帳號。活動存在，但 bus factor ≥3 未證實。
- Community Health: 有 stars／PR，但單次數據不能證明自然成長、獨立貢獻者持續參與或沒有 bot stars。
- Setup Friction: 官方需 block-sparse attention；A100 是作者優先路線，Colab 的 CUDA／Torch 組合仍須驗。README 的約 17fps 是單 A100、768×1408 的作者條件，不是本案實測，也不能推出零載入成本。[README](https://github.com/OpenImagingLab/FlashVSR/blob/cf910c61a60733e610e9c6e8b607f80c3a6c202b/README.md)
- Modularity & Reusability: 可將 video file 當獨立後製輸入，時序 LQ tensor 與串流路線吻合子流程；不涵蓋人物、分鏡與動作生成。官方推薦 **4x**；當前 script 對輸出向下取 128 格點並中心裁切，不能直接當任意 2x／原長影片接口。[full inference](https://github.com/OpenImagingLab/FlashVSR/blob/cf910c61a60733e610e9c6e8b607f80c3a6c202b/examples/WanVSR/infer_flashvsr_v1.1_full.py)
- Supply Chain & Licensing: repo 與 [v1.1 weights](https://huggingface.co/JunhaoZhuang/FlashVSR-v1.1/blob/main/README.md) 為 Apache-2.0；依賴／CVE status 未審計，沒有足夠證據稱為 clean。沒有身份保真承諾。
- Summary: 最適合先測速度，但直接複用 demo 的中心裁切／時序取整會威脅頭腳與片尾；wrapper 要先保住原畫面和時間再比較品質。

### SeedVR2

- Maintenance & Governance: 最後 commit 距查找約 8 個月；仍在 12 個月篩選內，但不滿足 1–3 個月強維護條件。沒有 latest release，最新可見 PR 為 2025-09-10；兩個 contributors 不證明治理／bus factor。
- Community Health: stars 與社群整合存在；持續成長／維護承諾未驗。
- Setup Friction: 官方列 FlashAttention／Apex 與單 H100-80G 的 100×720×1280 能力，1080p／2K 範例是四 H100；不是保證 A100 或單 Colab 可直接完成。官方示範涉及安裝／下載／腳本設定，不能把「3 段 quick start」誤算為 ≤3 個命令即可啟動。[README](https://github.com/ByteDance-Seed/SeedVR/blob/e4de8c24441a67e1b7df56abea10645059bb1185/readme.md)
- Modularity & Reusability: 影片序列後處理、以目標面積 resize 並裁到 16 格點；適合比較目標尺寸較彈性的 2x／4x，但實際比例／尺寸要 probe。不涵蓋 camera path。作者 notice 說大動作／重劣化可能失敗，輕劣化 AIGC 可能過度生成／過銳，故不能預設保臉。[transform](https://github.com/ByteDance-Seed/SeedVR/blob/e4de8c24441a67e1b7df56abea10645059bb1185/projects/inference_seedvr2_3b.py#L229-L266)
- Supply Chain & Licensing: code 與 [SeedVR2-3B weights](https://huggingface.co/ByteDance-Seed/SeedVR2-3B/blob/main/README.md) 分別確認 Apache-2.0；依賴／CVE status 未審計。
- Summary: 作為 2x 目標尺寸與品質對照候選；容量、安裝與生成細節風險較高，未測前不列為快片預設。

### Wan2.2-Fun camera / VideoX-Fun

- Maintenance & Governance: 2026-09-29 有 commit、近期 PR；contributors snapshot 有三個帳號，但對 camera 核心的維護集中度、bus factor ≥3 未證實；未有 latest release。
- Community Health: stars、PR 與 Comfy 文件可見，不能由快照斷言自然成長與品質。
- Setup Friction: 新模型與 runtime；官方有 offload／float8 等選項，較省記憶體的 sequential offload 也較慢。Comfy 的 24GB GPU／4step 範例涉及量化與 speed LoRA，不能套成本地 BF16／40steps A14B。
- Modularity & Reusability: [camera script](https://github.com/aigc-apps/VideoX-Fun/blob/4b7b6402a1e0f0406bd6801fb66c0a00bd922621/examples/wan2.2_fun/predict_v2v_control_camera.py#L302-L332) 真正把 camera file 轉成 `control_camera_video` 傳入專用 pipeline；相機內參／pose 與 Plücker 條件可提供可重現的運鏡輸入。匹配的是 **Wan2.2-Fun-A14B-Control-Camera checkpoint**，不能往目前 stock A14B 多塞一個參數就生效。小至 640×352／320×176 的正式支援未找到。
- Supply Chain & Licensing: code 與 [camera model card](https://huggingface.co/alibaba-pai/Wan2.2-Fun-A14B-Control-Camera/blob/main/README.md) 為 Apache-2.0；底模、speed LoRA 與依賴仍按實際版本各自核對，CVE status 未審計。
- Summary: 指定鏡頭路徑的最佳本次候選；固定取景的裁頭應先修 anchor，不為每個動作鏡新增專用 camera 模型。相機控制不能替代身份與扣具／穿帶控制。

## 4. Architectural Decision Verdict

- Recommended Path: **Option B — Extension / Sidecar**。
- Key Justification: 沿用本地人物／分鏡、immutable attempt、內容 review、selection、hash 與 join 流程；以明確檔案接口接外部 VSR，camera 則另設 backend。候選各自只覆蓋一個子流程，不達整個工作流 85% direct-adoption 適配；不需維護 hard fork 或搬入全部 UI／資料庫。
- Isolation: inference 在獨立環境／kernel，依賴與模型配置 pin；input／output files 和小 receipt 為邊界。隔離是相容性選擇，所有實際程式／權重授權義務仍要履行。此研究沒有複製第三方實現。
- Priority: 先驗 640×352 的核心動作是否足夠，再選 2x 目標 SR；FlashVSR 可沿官方 **4x→再降至2x交付** 作對照，但會處理較大畫面，不能先宣稱省 CU。320×176+4x 是另一路實驗；官方 A14B只列480P／720P，低尺寸不因本地格點合法而成為官方品質保證。[Wan2.2 README/config](https://github.com/Wan-Video/Wan2.2)
- Camera: 先用按完整動作取景的固定鏡；有硬路徑需求再接 VideoX-Fun 的實際 camera tensors。VSR 不能修復裁頭、未解扣、未背包或停車未知。

## 5. Minimalist MVP Plan (1-1-1-1 Rule)

- Core User Story: As a 影片製作者, I can 對已通過 native 動作驗收的選用鏡頭產生有來源的放大版本, so that 我能比較同等內容品質下的總時間與 CU。
- Starter Architecture: 1 個使用者；1 個尚未實作的 CLI 入口 `upscale`；1 個 `UpscaleJob` JSON 物件；1 個「選用原片 → 保存 job → 外部 SR → probe/hash/新 QA → 保存衍生結果」完整 loop。先只接 FlashVSR 一個 backend，camera 不擠入同一 MVP。
- Minimal Schema Draft:

  ```text
  Entity: UpscaleJob
  - id: primary key
  - source: path + SHA-256 + source-review SHA-256 + selected interval
  - recipe: tool/model revisions + target + clock/padding mapping + settings
  - result: path + SHA-256 + probe + timing/CU + content-review state
  ```

- Milestones:
  - Phase 1: 固定環境與實際授權、用已存 native clip 驗證畫面完整性／時鐘的 SR 子 loop；生成模型保持原基準。
  - Phase 2: 最小 CLI／驗證，加入 640×352 與 320×176 的配對生成比較；保住動作／身份與 SR 後品質，才選預設。
- Scope Blacklist:
  - [ ] No authentication or multi-user accounts
  - [ ] No microservice decomposition
  - [ ] No non-core exports or styling features
  - [ ] No Redis/Kafka、dashboard、i18n/theme、完整 CI/CD

## 6. Next Actions

- [x] Action 1: 按實際失敗修訂 skill，補 [製作復盤](../skills/colab-video-studio/references/production-lessons.md)、[運鏡](../skills/colab-video-studio/references/camera.md)、[低解析度／SR測試契約](../skills/colab-video-studio/references/resolution-upscaling.md)。
- [x] Validation: `quick_validate.py` 回傳 `Skill is valid!`；26個本地文件連結存在；獨立代理以320×176保臉／解扣和完整下車追拍兩個情境，能指出SR／hard camera尚未接入、裁切與時鐘風險及可操作的準備／驗收條件。這是文件行為檢查，不是SR或運鏡實跑。
- [ ] Action 2: 未來 VSR benchmark 先檢官方 full-script 的 **128 像素取整／中心裁切與 `8n+1` 時序選取**；明確 pad／映射／trim，保留原尺寸與全部必要時段；不直接把 demo 檔當同長、同取景結果。
- [ ] Action 3: 將 generation／SR／載入／下載／QA、warm/cold、通過率與 CU 分開記，依取得一個合格輸出的總成本選路線；2x／4x性能尚未測量。
- [ ] Action 4: 有精確運鏡要求時另測 camera checkpoint 的固定／單一運動配對，不把 camera sidecar 說成已接入。

# H3 執行與原作業恢復

本頁只處理 H3 backend 狀態與工具邊界。授權、停止、保留／釋放及計費證據使用 [Studio 資源與作業生命週期](../../colab-video-studio/references/runtime-monitoring.md#資源與作業生命週期)；讀文件與唯讀檢查不恢復已停止的生成。

## Pinned FastH3 runtime

Repo lock 固定 ComfyUI `a4b5a045e56fc334903db8457b728b64e006119c`、VSA pack `c1798183d89f7143d021c16507e4bb7ac0b3decc`、Comfy Kitchen 0.2.37。對應診斷環境為 L4、Python 3.13.15／Torch 2.11.0+cu130；現有 runtime 以 `--disable-comfy-compiler` 啟動，保留 dynamic VRAM／offload；它針對此環境的 allocation-graph／CUDA invalid argument 故障，不是所有 GPU 的通用規則。小型 sol_attn preflight 不代替完整 chunked VSA；CUDA error 也不直接證明 OOM。

若碰到安裝／schema 問題，核對實際版本和 pinned實作。Runtime 的 venv 使用 system-site-packages／without-pip；需確認其 pip 可用。Comfy 新 COMBO schema 的選項可能在 `options.options`，舊版可能是 list；以 node schema 判斷。

## 首次使用與啟動診斷

首次使用 runtime，或改變本機 CLI／proxy／kernel 執行鏈時，核對檔案往返與 kernel 能開始並返回帶本次身分的小型執行結果。`Session READY` 或上傳成功只證明相應通道；setup 已有等價的執行 marker／硬體檢查時沿用它，不在每段重做探測。

啟動診斷的外層時限須涵蓋連線及 CLI prelude，按當次成本界線設定。停在第一個 setup marker 之前時，先區分 assignment、檔案通道、kernel 和本機 CLI 的狀態；取得能支持處理方案的新證據，再決定是否重配資源。版本比較、工具安裝或較長診斷依共用資源規則移到釋放後。

## Proxy 與原作業恢復

1. 固定邏輯 session 與既有 assignment endpoint，讀 action-result／progress、Comfy queue／history 和 receipt，區分未上傳、未開始、已入隊、執行中、完成、失敗。CLI stdout、IDLE 或 connection lost 各自只是一項訊號。
2. Proxy／檔案存取失效時，用 `scripts/fast_h3_colab.py refresh --session <目標> --output <run-dir>` 更新**該 endpoint**；helper 比對 assignment 並要求既有 FastH3 runtime 目錄，refresh 不建立 VM。尚未進入 setup 的情況先用基礎檔案／kernel 檢查定位，不把缺少 runtime 目錄當成失去 assignment。以小型讀取／ping 驗連線，避免輸出含 token URL。Endpoint 已變或無 assignment 時先釐清資源狀態。
3. 已入隊的 prompt 用 queue／history 追蹤並 fetch 原結果；不能用重新 generate 來恢復通訊。未開始的工作只有在確認狀態及原授權允許時才送出。`fetch` 取 latest 技術完成產物，仍須比對目標 prompt ID，不能把上一工作的 latest 當本次結果。

FastH3 CLI 每個 action 有獨立 ID，PASS 必須匹配該 ID。輸出目錄的 `state` 保留拉回的 progress／telemetry／action-result；遠端 runtime 的 `runs` 保存 prompt ID、graph、history、receipt、媒體，`latest.json` 是最近技術完成結果定位。恢復前先找本次身分，不猜預設 session 或路徑。

## 完成結果的取回順序

匹配本次身分的完成訊號出現後，優先取回必要媒體及 receipt／hash 核對資訊，再補非必要診斷與完整日誌。遠端 PASS 與本機保存是不同事實；stdout 已有匹配 PASS、本機 action-result 仍是 running 時，先以最新的小型 marker、history 或 receipt reconcile 原工作，不直接判成推論失敗或重送。

現有 CLI 在 action 返回後會先批次拉狀態，再檢查 action-result 並 fetch。文字規則不會改變工具順序：把這段耗時計入[提交預算](../../colab-video-studio/references/runtime-monitoring.md#提交前的預算判斷)；需要及時保存時，用可用的小型讀取／fetch 路徑取得原結果，仍核對目標 prompt ID。已釋放後取不到檔案則記錄「遠端完成、本機未保存」與恢復限制，保留原 attempt，不將它納入 selection。

## 原 H3 notebook 的載入與續跑

Notebook `_LOADED_CONFIG`、preset、模式與實際生成 metrics 必須一致。同 kernel 的 setup、卸載、生成與全域設定依序進行；切换 backend 按 notebook 指引重新啟動 runtime，避免兩套大型模型共存。僅清 allocator cache 不會釋放仍被物件引用的權重。

CLI exit 0 仍可能含遠端 Traceback；完成需對應 PASS、model/config 與可讀媒體。Stdout 失去更新時以遠端 checkpoint／progress 判當前片段；單次 0% 或 utilization=0 不能證明卡死，比較時間、phase、log 與多次觀測。進度不能推算 completed。

若專案有每段一次限制，推論前持久記 attempt identity，已啟動但中斷的片段不自動重送。恢復讀取／下載與新推論分開；同參數技術重啟是否允許依原要求處理，不另套固定批准關卡。

## 模型快取與產物核對

按 pinned revision inventory 缺少與共用元件，實際 bytes／hash 查 lock 或同 revision metadata。檔案大小相同不能證明內容相同；hash mismatch 先查來源與字串完整性，不能換成 main 或跳過檢查。FL／Ref 共用 encoder／VAE／processor 需逐檔 hash 相同，transformer 分開。

容量不足時整理精確候選與可回收空間，刪除依授權及共用元件依賴決定；allocator/offload 預算不等於實際峰值。停掉已有 pipeline 引用後才能回收其權重。

FastH3 fetch 驗 ZIP CRC、basename-only entries、不覆蓋不同 bytes，核對 receipt prompt ID／video SHA，重新解碼本機影片。原 H3 自訂分段 controller 另依其 manifest 契約：完成狀態須有匹配輸入設定與完整媒體；輸入、crop、prompt 或模型變更用新版本／命名空間。工具入口见 [repo-tools.md](repo-tools.md)，通用交付與合成驗收用 Studio。

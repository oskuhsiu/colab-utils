# Colab 原生 Omni：預備包與部署到首鏡

適用 `h3-omni-int8`、A100 STANDARD、`high_mem=false`。工具只操作已配置的 VM，不配置／釋放 Colab，也不更換模型、尺寸或採樣設定。沿用當次預算；正式影片與既有收據不因部署測試而重寫。

## 開 GPU 前完成

`scripts/colab_video_bootstrap.py prepare` 使用專案既有 `common.py`、`run_shot.py`、`status.py` adapter，將固定 toolkit、第一鏡 JSON、實際圖檔及最終 API graph 封成一包。它在獨立本機 interpreter 呼叫原 `graph_for_job`，檢查參考圖名稱完整對應，再記錄全部檔案 SHA-256。此步不安裝套件、不下載模型、不提交推論。

```bash
python3 scripts/colab_video_bootstrap.py prepare \
  --runtime projects/forum-story-ch2-20261030/runtime \
  --job projects/colab-startup-pilot-20261031/first-job.json \
  --input forum-story-yang-school.png=projects/forum-story-ch2-20261030/assets/yang-school.png \
  --input forum-story-zhang.png=projects/forum-story-ch2-20261030/assets/zhang.png \
  --input forum-story-classroom.png=projects/forum-story-ch2-20261030/assets/classroom.png \
  --output /tmp/omni-prepared --id startup-pilot-20261031
python3 scripts/colab_video_bootstrap.py inspect --package /tmp/omni-prepared/deployment.zip
```

輸出 `deployment.zip`、獨立的 `bootstrap.py` 與 `plan.json`。輸出目錄、部署 ID 及首鏡 ID 按本次任務選定；既有封包不覆寫。專案 adapter 是受信任的本機程式；此工具不是任意第三方 adapter 的 sandbox。

### 可選的離線環境包

在**與目標 GPU VM 相同 Linux 基底**的 CPU 環境建包；需要相同 Python／ABI／套件與 CUDA PyTorch distributions，不需要可用 GPU。Mac venv、不同基底的 CPU 環境不可直接替代。

```bash
python3 scripts/comfyui_environment.py build /tmp/omni-environment --extensions ''
python3 scripts/comfyui_environment.py inspect /tmp/omni-environment
```

建包取得固定 Git revision 的乾淨來源，保留 `.git`；pip 僅 dry-run 解依賴並下載 wheels，不安裝至建包機。manifest 包含來源／wheel／lock 的 hash、完整基底套件指紋、Python ABI、架構／glibc 及 GPU stack。下載 SDK 版本與 `comfyui_workspace.DOWNLOAD_REQUIREMENTS` 共用，沿用成功 Omni 環境的 Hub 1.33.0／Xet 1.7.0，不另加 Hub <1 的限制而迫使 Transformers 5 降版。

在 `prepare` 加 `--environment /tmp/omni-environment` 會封入完整環境包，`plan.json` 標 `environment_mode=offline`。GPU VM 先驗包與基底，重建 venv，以 `--no-index --no-deps --only-binary --require-hashes` 安裝；不相容就明確停止，不暗中轉為線上安裝。缺省是 `environment_mode=online`，沿用原安裝流程。wheelhouse 是安裝來源，仍有傳輸／解壓／安裝成本。

## 已配置 VM：單次背景啟動

先由外部控制器以官方 API 核對精確 endpoint、A100、STANDARD、當次累計剩餘預算及費率，啟動獨立 budget／release guard，再將兩個檔案上傳至**同一 endpoint**。不要呼叫有 auto-create 行為的 session 選擇器來尋找舊 VM。

控制器寫 `admission.json`，以下是欄位示意，不能拿舊時間戳直接使用：

```json
{
  "endpoint": "exact-owned-endpoint",
  "accelerator": "A100",
  "machine_shape": "STANDARD",
  "high_mem": false,
  "observed_epoch": 0,
  "allocation_started_epoch": 0,
  "deadline_utc": "由本次剩餘預算換算的帶時區截止時間",
  "completion_reserve_seconds": 360
}
```

`observed_epoch` 是啟動前的官方分配／預算觀測時間，啟動時最多 90 秒；不是本機推測的 GPU 規格。`deadline_utc` 須涵蓋累計已用成本、當前費率上界與停止餘量，不能重設原任務 cap。`completion_reserve_seconds` 是提交前所需的完整生成／驗證／保存時間；以當次完整循環實測設定。遠端 admission 是外部准入結果，不會自行查帳戶或證明獨立 guard 正在工作。

```bash
python3 /content/bootstrap.py launch \
  --package /content/deployment.zip \
  --root /content/video-startup-pilot-20261031 \
  --admission /content/admission.json
```

`launch` 立即回 PID／log，不等待 GPU 工作；worker 使用獨立 session 與部署 lock，stdin 關閉。遠端流程：

```text
驗封包／第一鏡 → 若已有 shot，先對帳
              → 確認 A100 → 還原／安裝環境 → 放入素材
              → 官方 HF 下載並驗權重 → 啟動服務 → 立即跑原 run_shot
              → 下載輸出至 VM 的 production → ffprobe＋完整音畫解碼 → 保存結果 ZIP
```

官方下載器只取 catalog 固定 revision 的所需檔案，最多兩檔並行；Xet 使用官方預設，無 high-performance／high-RAM 開關。HF cache 位於 workspace 本機磁碟，驗 bytes／SHA 後 hardlink 至 models，不再複製一份權重。工具不清除 cache，完整且校驗成功的檔案可重用；partial 的建立／清除由 SDK 管理。**固定 Hub 1.33.0／Xet 1.7.0 不會跨程序接續舊 partial**，終止下載程序可能導致該檔重新全量傳輸；控制通道斷線時保留背景下載，切換通道觀測，不重開下載程序。首個失敗後尚未開始的檔案取消，進行中的傳輸可完成。`download-progress.json` 的 bytes 是**已驗證量**，不是即時網路速率；heartbeat 也只表示程序存活。

原生 workspace 的 `download` 預設 `--download-backend hf --download-workers 2`；原串流路徑保留為明確指定的 `--download-backend http`，不在 HF 失敗後自動換路線。

## 首鏡後的批次接續

此 bootstrap 只負責冷啟與原首鏡，不是逐鏡下載／驗收的批次迴圈。啟動前把後續 ready jobs 與 [批次控制器](COMFYUI_WORKSPACE.md#批次生成取回與審查並行) 接好；首鏡後端完成後，控制器接續下一個已授權且准入通過的工作，首鏡 ZIP 取回、完整解碼與內容審查並行。真正依賴首鏡生成結果的分支才等該結果，不讓主代理閱讀日誌、審查或回覆訊息成為所有下一鏡的排程關卡。完整政策見 [共用批次排程](../skills/colab-video-studio/references/runtime-monitoring.md#批次排程生成保存與驗收並行)。

## 狀態、恢復與保存

```bash
python3 /content/bootstrap.py status --root /content/video-startup-pilot-20261031
python3 /content/bootstrap.py fetch --root /content/video-startup-pilot-20261031
```

- `status` 只讀小型本機檔案：phase、worker identity／heartbeat、下載進度與原首鏡收據，不提交工作。控制通道斷線時用既有的官方 SSH bridge 在同 VM 執行；代理刷新與最長恢復窗口見 [連線故障分流](../skills/colab-video-studio/references/connection-recovery.md)。此工具本身不是帳戶 watcher 或自動 SSH failover 服務。
- 同封包再 `launch`：健康 worker 回傳 `already_running`。worker 已結束而首鏡目錄存在時，只查原 receipt／queue／history；完成就 fetch，執行中就 wait。原 server 或 prompt 消失、缺收據、回應遺失且查無作業，均停為需對帳，不重裝 server、不重新 POST，也不把 prompt ID 當 server 已支援去重的保證。
- `fetch` 可補抓原已完成作業；worker lock 尚在時先用 `status`。內容判斷仍是 `not_run`，媒體完整性通過不等於劇情／表演通過。
- `production/results/<shot>.zip` 及 `progress.json`／`events.jsonl`／`worker.log` 要即時抓回本機，核 hash、收據與解碼。VM 上的 `complete_media_verified` **不代表本機已保存**。
- 成功或失敗都不會自行釋放 Colab；外部控制器依既有預算 guard 保存產物、停止精確 endpoint，並以官方 assignment 查詢確認釋放。不得從 worker 結束、心跳停止或零利用率推定停止計費。

## 實測口徑與目前範圍

`progress.json` 記各階段耗時、`ready_to_submission_seconds`；admission 有配置時間時另記 `allocation_to_submission_seconds`。提交計時使用 `first-post.json`，在最後一次 schema validation 後、單次 POST 即將發出時寫入；完整循環保留時間也在此重新檢查，入隊仍以原 submission／history 為準。`results/<shot>.package.json` 另記 ZIP 的 bytes／hash；媒體已驗而 ZIP 尚未發布時，可從本機已驗檔案補包，無須重新生成。首鏡仍負責實際模型載入及輸出，沒有額外空跑暖機。以「配置至首鏡提交／完成、本機保存、釋放」整段計費比較，不只比較服務 READY。

2026-10-31 完成三輪各 45 項離線故障測試，以及兩台 T4 STANDARD 的無生成實測：線上安裝約 39 秒，Linux wheelhouse 實建約 30–39 秒，四次全新目錄離線還原約 24–25 秒；兩個固定 VAE 共 3,416,319,992 bytes 下載與校驗、完整檔／cache hardlink 重用通過。強制中斷 SSH／notebook、失效 token 和本機 handle 遺失後，仍可找回同一 endpoint／worker。詳細證據、限制及資源紀錄見 [無生成演練](../research/colab-preflight-rehearsal-20261031.md)。未執行模型載入或影片推論，未驗證 A100 的生成速度／RAM 峰值。

環境包約 764 MB，包含官方 requirements 的大量範本媒體；VM 內還原比線上安裝少約 15 秒，但本機與 Colab 的包傳輸另需數分鐘。**目前保留 `online` 作為缺省，離線包僅供相容基底與已備妥傳輸的明確使用情境。** 不把還原秒數單獨當成端到端節省。原 0.42.0 首鏡基準包仍標為 `online`，不因本次 0.43.0 無生成測試改寫。

## 無生成前置演練

先由既有控制器配置測試 VM、保存精確 endpoint／當次費率並啟動獨立停止監控，將 `scripts/colab_preflight_probe.py` 與共用 toolkit 上傳同一 VM，再執行：

```bash
python3 /content/toolkit/colab_preflight_probe.py launch \
  --root /content/colab-preflight-test --toolkit /content/toolkit --environment-rounds
python3 /content/toolkit/colab_preflight_probe.py snapshot --root /content/colab-preflight-test
```

工具不配置／釋放 VM、不載入權重、不 POST prompt。它以無 custom node 的當前 Core 安裝、重用 server 並檢查空 queue／history，測試兩個 VAE 的中斷重開、完整檔重用及 cache hardlink；`--environment-rounds` 額外建包並還原到兩個全新 workspace。下載每次最多 180 秒，worker 最多 900 秒；外部控制器另負責傳輸、恢復期限、累計成本與釋放。`completed_files_reuse=verified` 與 `cross_process_partial_reuse=not_established` 分開記錄；RX 含控制流量，不能當精確 HF 位元組數。

帳戶另有 allocation 時，先記配置前後精確清單；只有其餘 endpoint 保持一致時才用費率差隔離本次成本。帳戶總費率／總扣費不能直接歸給這個測試，也不能因此停止其他任務的 VM。

待測 `projects/colab-startup-pilot-20261031/ready/` 已封存原 Core 0.42.0／`8f04fd6ecf4a548937971e840af2a985529fab76`，只比較啟動／下載／首鏡銜接。後續 [Context Windows 整合](H3_CONTEXT_WINDOWS.md) 已把 canonical catalog 升為 0.43.0；重新 `prepare` 會使用當前來源，應另存新包，不覆寫或混用這份部署基準。

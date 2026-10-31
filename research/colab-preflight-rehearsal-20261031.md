# Colab 無生成前置／重連／下載演練 — 2026-10-31

本輪只測前置流程與故障恢復，未載入 H3 模型、未送出生成 prompt、未產生影片。兩輪實機均為 **Tesla T4 15 GB／STANDARD／high_mem=false**，每台配置時隔離出的費率均為 **1.15 CU/h**。本輪自行設累計 1 CU 與 30 分鐘 VM 時間上限，不重設先前影片製作預算。

## 執行版本與證據

- ComfyUI 0.43.0，`6651247a8b50cefd1436c834f704bdf7767722e9`，不載入 custom nodes。
- VM Python 3.13.16，Torch 2.11.0+cu130，Hub 1.33.0，hf_xet 1.7.0；GPU stack 未被安裝／離線還原替換。
- 原 0.42.0 首鏡部署基準包保持封存；本次不是該包的生成速度比較。
- [三輪離線紀錄](../projects/colab-preflight-rehearsal-20261031/offline/summary.json)：每輪 45 項，合計 135 次全部通過；三個獨立 interpreter、fake/temp、封鎖 socket。覆蓋身分／重入、解包中斷、遺失 POST 回應不重送、缺 server 不重裝、下載失敗／校驗和基底不符。
- [實機 R1 觀測](../projects/colab-preflight-rehearsal-20261031/live/observed-result.json)：遠端結果已從 SSH 讀到，但 guard 釋放前未取回整個目錄；只保留實際觀測，不聲稱完整原始檔已恢復。
- [實機 R2 完整證據](../projects/colab-preflight-rehearsal-20261031/artifacts/evidence-r2/evidence/result.json)：result、events、phase／download 收據、server marker、versions、環境 manifest 已保存至本機。[封存檔](../projects/colab-preflight-rehearsal-20261031/artifacts/evidence-r2.tar.gz) SHA-256 `5a283505eaba674d94fb79c56250813043826e3fe8d6d89c7921a80afa95b43c`。
- [R1 封包 inventory](../projects/colab-preflight-rehearsal-20261031/payload.json)、[R2 封包 inventory](../projects/colab-preflight-rehearsal-20261031/payload-r2.json) 保存當時程式 SHA。R2 已將誤導的 `download_resume` 名稱改成 `download_restart`，結果明列 `cross_process_partial_reuse=not_established`。

## 量到的時間

以下是完整 phase 的 wall time，單位秒。服務 phase 含兩次 schema GET、核對同 PID、空 queue／history 與停止；不是模型 READY／已載入權重時間。

| Phase | R1 | R2 |
| --- | ---: | ---: |
| 線上安裝 | 39.038 | 39.038 |
| 既有安裝重入 | 1.015 | 1.012 |
| 服務啟動／同 PID 重用／停止 | 27.100 | 26.030 |
| 刻意中斷下載 | 3.600 | 2.643 |
| 同 cache 重新開始未完成檔 | 39.074 | 41.086 |
| 完整模型檔重用／校驗 | 11.034 | 11.029 |
| cache hardlink 發布至另一目錄 | 11.033 | 11.039 |
| Linux 環境包建置 | 30.051 | 39.048 |
| 離線還原新目錄 1 | 25.038 | 24.045 |
| 離線還原新目錄 2 | 24.043 | 24.042 |

安裝與全部前置 probe 在單一 detached worker 中依序執行，整段約 211／218 秒。完整檔重用的約 11 秒主要包含兩個大檔 SHA-256 校驗，不能稱作瞬間完成。

環境建包使用線上安裝已填入的 pip cache，並非空 cache 建包基準；建包階段 RX 約 13.8 MB。四次離線還原都在同 VM 的新 workspace 執行，安裝使用 `--no-index --no-deps --only-binary --require-hashes`。尚未證明另一台 A100 的基底可直接接受此包，仍需實際 fingerprint 核對。

## 四種控制故障

R2 原 worker PID `5316`、start ticks `134972`；完整 argv 一併核對。

| 注入／症狀 | 實際結果 |
| --- | --- |
| 安裝中強制 kill 本機 SSH client process group | SSH 重新接到同 endpoint；讀到原 worker，安裝繼續進入服務 phase。 |
| notebook 已讀到原 worker 後，故意令客戶端 `os._exit(23)` | 原背景 worker 不受影響，後續下載與環境包步驟仍完成。 |
| 本機代理 token 改為刻意失效值 | Contents SDK 在約 0.77 秒回 `FileNotFoundError`；該版 SDK 把 HTTP 404 映成檔案不存在。官方 assignment／proxy 刷新後，SSH 讀到原 worker，未重開工作。這不是自然到期時鐘的量測。 |
| 刪除本機 session handle | 先備份 kernel/session ID；從官方同 endpoint assignment 還原，回傳 `local_handle_restored=true` 且 kernel 身分保留；讀到同一 worker。沒有使用可 auto-create 的 session 選擇器。 |

[斷線前身分](../projects/colab-preflight-rehearsal-20261031/live-r2/before-forced-ssh-close.json)、[失效 token 後](../projects/colab-preflight-rehearsal-20261031/live-r2/recovery-after-invalid-token.json)、[handle 遺失後](../projects/colab-preflight-rehearsal-20261031/live-r2/recovery-after-lost-handle.json) 均已比對原身分。

R1 的第一次 notebook marker 讀取有測試輔助程式格式誤讀，修正為 SDK 實際輸出的 notebook output object 後才進行 R2；該次缺 marker 不計為 Colab 故障。R1 另有真實 Contents 讀取 25 秒逾時；同 endpoint SSH 可讀原 worker。SDK 在例外後可能仍等 websocket thread，外層要限制整個 process group 的生命週期，不能只設 kernel timeout。

## 模型下載：完整檔可重用，舊 partial 不會接續

只下載固定 catalog 的 audio VAE `605,254,808` bytes 與 INT8 video VAE `2,811,065,184` bytes，合計 **3,416,319,992 bytes**，非整套約 52.8 GB Omni 權重。

兩輪都在寫入中以 SIGTERM 終止下載子程序，留下約 `224,243,712` allocated bytes 的 partial。以相同 spec／cache 重新執行仍接近全量傳輸：R1 RX `3,406,849,009`、R2 RX `3,403,686,432` bytes；RX 包含控制流量，不能作精確網路量或推算壓縮比。

這與版本實作一致：[Hub 1.33.0](https://github.com/huggingface/huggingface_hub/blob/v1.33.0/src/huggingface_hub/file_download.py#L1828-L1898) 每次建立 UUID temporary 並以 `wb` 開啟；[Xet 1.7.0 download group](https://github.com/huggingface/xet-core/blob/v1.7.0/xet_pkg/src/xet_session/file_download_group.rs#L150-L155) 建立 session 時傳入 `chunk_cache=None`。因此不能用保留 `.incomplete` 或設定舊 chunk-cache 變數承諾跨程序續傳。[官方環境變數說明](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables#hf_xet_chunk_cache_size_bytes) 亦記載下載 chunk cache 已停用。改用 top-level HTTP download 仍有新 temporary，沒有因此取得舊 partial 接續能力。

完整下載後的兩個檔均通過 bytes／SHA-256；再次執行只核驗既存檔，發布到另一個 models 目錄時，兩個目標與 cache 共用 inode，沒有第二份權重。**控制斷線時保留背景下載程序，換通道觀測；只有程序實際死亡才重新下載缺檔。**

## 環境包的端到端代價

本次 pack 約 **764 MB**，24 個 wheels；其中 workflow templates 的多個 media wheels 各約 54–104 MB。封存約 **725.7 MB**。VM 內離線還原只比線上安裝少約 15 秒，搬運完整包另需數分鐘；本次未支持「從本機上傳完整環境包一定更省 CU」的說法，工具繼續預設 `online`。

完整包的一次串流下載超過先設的 150 秒上限，一度保留約 291 MB 未完成檔，完整封存校驗成功後才清除；失敗的大小／處理紀錄留在 `artifacts/failed-transfer-observations.json`。之後改為**固定封存檔＋每 32 MiB SHA-256 檢查點**：刻意在首 chunk `33,554,432` bytes 後退出，再由新程序從該 offset 繼續；各 chunk 校驗後才落入已驗前綴。這是自有封存檔的取回方式，與 HF 未完成模型檔的能力分開記錄。[下載事件](../projects/colab-preflight-rehearsal-20261031/live-r2/events.jsonl) 保存重新啟動 offset；完成封存與還原檢查另見下列交付紀錄。

## 已套用的改動

- 新增 [無生成 probe](../scripts/colab_preflight_probe.py)，獨立 worker／鎖與 PID 身分、各階段時限、小型 snapshot、完整檔／cache 重用及可選建包／兩次還原；不配置 VM、不送 prompt。
- 修正 HF cache／partial 的說明，不再把重新開始下載叫做已證實的續傳；同步 notebook。
- Studio 恢復規則加入已驗版本的 partial 邊界、保留原下載程序，以及多 allocation 帳戶的費率隔離。
- R1 guard 使用帳戶總費率，看到另一台 A100 後提早停止自己的 T4；R2 已改用配置前後相同其他 endpoint 的費率差，仍只停止自己記錄的 T4。其他 VM 的帳戶扣費不歸本輪。
- 最後聚焦檢查：新 probe、notebook 嵌入與 assets 共 36 項通過；Studio skill 格式與 diff whitespace 通過。既有 135 次故障測試紀錄另存，不以它們代替實機結果。

## 交付與釋放紀錄

- [累計收據](../projects/colab-preflight-rehearsal-20261031/summary.json)：兩台 T4 合計 **25.33 VM 分鐘／估計 0.486 CU**，均在本輪 30 分鐘／1 CU 上限內。費用為配置時間乘隔離出的費率，非帳戶已入帳扣費。
- [R1 release](../projects/colab-preflight-rehearsal-20261031/live/release.json)、[R2 release](../projects/colab-preflight-rehearsal-20261031/live-r2/release.json) 均由官方 server assignment 精確 endpoint 消失確認；R2 後續觀測仍不含兩台自有 T4。
- [完整環境封存](../projects/colab-preflight-rehearsal-20261031/artifacts/environment-checkpoint-r2.tar.gz)：`725,730,559` bytes，SHA-256 `e5245c2a5ba784dcbd640c8fe9d27be2933d637ed364fadd5103b825c4982faa`。第二程序從 `33,554,432` bytes 接續，耗時約 413.8 秒；首 chunk 另約 16.6 秒，並含每段官方 SSH 握手／hash／落盤時間。這說明整包經目前控制通道傳輸的成本不可忽略。
- [已解包環境](../projects/colab-preflight-rehearsal-20261031/artifacts/verified-pack/environment/manifest.json) 的 **1,381 個檔案**已在本機逐項核對 bytes／SHA-256／mode；[驗證收據](../projects/colab-preflight-rehearsal-20261031/artifacts/environment-local-validation.json) 通過。解包與驗證花約 5 秒，於 T4 釋放後執行。764 MB 是包大小，並非 GPU 記憶體用量；不能把 Mac 當 Linux 安裝驗證。
- [實際 server schema 檢查](../projects/colab-preflight-rehearsal-20261031/live-r2/node-preflight.json)：原生 Omni 的 15 種必要節點全在，共 1,024 節點；`MiniMaxH3ContextWindows` 亦已匯入。這只驗 import/schema，不代表模型載入或 context-window 品質通過。
- 帳戶另有一台非本輪建立的 A100 HIGH_RAM，最後觀測費率 8.88 CU/h；本輪沒有停止它，已另詢使用者用途。因此帳戶總餘額差不能歸給本次 T4 測試。

模型載入、A100 容量／速度、影片生成與內容均為 `not_run`。

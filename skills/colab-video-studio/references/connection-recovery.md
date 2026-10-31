# Colab 連線故障快速分流

用於付費長批次的恢復準備，以及 `exec`／上傳／下載逾時、401／404、`Session … lost`、路徑或 session 消失。先分清控制通道、原作業和伺服器分配，讓已完成結果及時保存，避免 GPU 在反覆排查中閒置。

適用證據包含 Colab CLI 0.7.2、原生 ComfyUI／h3-omni；其他版本先核實相應介面。兩次約一小時後的失敗與一次 3600 秒代理租約是線索，**不是 Colab 固定每小時踢線的證明**。時間線及證據限制見 [事故整理](../../../research/colab-disconnect-recovery-20261031.md)。

## 付費批次啟動前

- 持久保存已授權帳號／config、邏輯 session、**實際 endpoint**、配置開始時間、GPU／machine shape、累計預算與獨立停止入口。每次新配置另記一個區間，即使沿用 session 名稱也不能覆蓋前次費用或放行狀態。
- 帳戶 usage 的費率與扣費包含其他 allocation。多人／多任務共用帳戶時，保存配置前後的 endpoint 清單並隔離本次費率；無法隔離就記估算限制，不能把其他 VM 的費率當成本次實際成本。停止仍只作用於本次已記錄的 endpoint。
- 取得 proxy 時記錄取得時間及服務回傳的有效秒數，token／URL 留在私有狀態檔。若下一個控制操作會跨過已知期限，先刷新同一 endpoint；缺少期限時按實際錯誤分流，不猜固定斷線週期。
- 長 setup／下載／生成使用可脫離 notebook websocket 的既有背景 worker，先回傳身分和啟動 marker，持續寫小型 phase／progress／receipt。準備對應工具的替代讀取入口；有已驗證的同環境 SSH 控制器就沿用，不在 GPU 閒置時重新研究或撰寫整套 harness。
- 控制通道失效時，帳戶／預算 watcher 仍須能獨立查分配及停止精確 endpoint。控制器異常退出或失聯要留下故障起點與恢復截止，讓獨立 watcher 執行到點處理，避免主代理忙於分析而延後；現有僅計 CU 的 watcher 不可當作已有這項能力，配置 GPU 前先接好。控制程式的失敗不能結束費用監控。
- 故障事件用追加紀錄保存時間、endpoint、作業 ID、錯誤種類、各通道結果及下一步；`batch-latest` 只作最新快照。日誌排除 token、含 token URL 與認證標頭。

已就緒且獲准的下一個 job，由 [批次控制器](runtime-monitoring.md#批次排程生成保存與驗收並行) 在原作業確定完成後立即接續，每次仍做預算准入；只有真正依賴試片判斷的工作才等待該結果。下載或審查通道故障與 GPU 提交通道分開處理：能可靠監看、取回且保存積壓仍安全時，繼續其他 ready jobs。改善靠排程、保存、租約和官方控制通道，不新增保活或防踢循環。

## 首個故障後的分流

先記本輪 `recovery_started` 與截止時間，以控制器首次故障記錄起算，跨回合、換工具或換代理不重設。**預設整輪控制恢復最多 5 分鐘**，剩餘費用／時間更少時縮短；CLI／SDK 的小型控制讀取通常給 20–30 秒、外層硬限不超過 45 秒。用可終止的子程序設外層 timeout；工具的 yield／CLI 的 kernel execution timeout 不保證涵蓋登入、握手與傳輸。必要媒體下載另按檔案大小和保存預算給時限。

已確定是發出遠端請求前的本機權限／輸入校驗錯誤時，先依既有授權修正本機入口；其餘依下列分流。不要把 Contents API 的 404 `FileNotFoundError` 誤判成本機錯誤。

1. **查伺服器分配，先於 kernel／檔案。** 以相同認證來源查官方 `list_assignments()`，精確匹配已保存 endpoint；同時取 usage。CLI 本機 session 已清除時仍查伺服器，不能從 `lost`、404 或本機空清單判定已停止。
   - endpoint 尚在：保留原 VM，進第 2 步。
   - endpoint 確認不在：記首次確認時間並結束該配置的費用估算；原未保存結果記恢復限制。只有仍有生成授權、必要工作與重載／保存餘量時才建立新配置，累計預算不重設，GPU／RAM 沿用原限制。
   - 帳戶 API 自身也失敗：分配／計費仍未知，走截止處理；不要建立第二台來試。
2. **刷新同一 endpoint 的 proxy 一次。** 用官方 assignment 回傳的最新 proxy 更新私有 cache 與本次 lease 取得／到期記錄，再做一次小型檔案或狀態讀取。保存既有 kernel／session ID；若 CLI 已 prune，先找回原身分／原 worker，勿把新空 kernel 當模型已卸載。刷新成功只代表取得新租約，完成條件是該通道讀到原 worker／session 的身分與對應 phase；job 已啟動時還要核其 marker／prompt。
3. **通道仍壞就換入口，停止重試同一路徑。** Contents HTTP、notebook websocket、官方 SSH 分別判斷；一個失敗不證明其餘失敗。普通執行已具體失效時，做一輪有界的官方 SSH 連線與原 worker snapshot；保持 exact-endpoint 核對，停用任何 session 缺失時的自動配置路徑。能讀 phase／原作業且可取回檔案後，記 `active_transport`，後續批次沿用該可靠通道，不每鏡回到已壞 websocket。HTTP 取檔仍可用時可繼續取檔，無須重建全部傳輸。
4. **對帳原作業後才續跑。** 用原 attempt／shot、submission marker、prompt ID、queue／history、receipt 和檔案核對：

   | 已確認狀態 | 下一步與完成條件 |
   | --- | --- |
   | 上傳失敗且尚未進入提交階段 | 修傳輸後，依原授權提交待執行 job；若啟動可能發生過，仍先查原 marker |
   | 已入隊／執行中 | 監看同一 prompt，不重送；有進度則回正常資源監看 |
   | 原結果完成 | 將原結果交保存工作線 fetch／核驗；同時按准入接續已就緒的獨立 job，再補非必要日誌 |
   | 收據／marker 不足以判斷 | 維持 `needs_reconcile`，不以新 take 掩蓋未知作業 |

已能可靠讀取原進度／保存結果即結束本輪恢復；模型仍在下載或運算可繼續，不因控制恢復的 5 分鐘時限殺掉健康 worker。仍須遵守原付費上限。

## 到點與釋放

到截止仍無可靠作業／進度入口時，停止新的付費工作，保存本機證據和 partial，透過獨立官方帳戶 API 停止**已記錄的 endpoint**並確認其從分配清單消失，再決定用已存素材收尾或在剩餘預算內重配。不要延長同一排查窗口去研究新工具／升級 CLI；需例外時由主代理根據新證據和成本作明確決定，停止餘量仍保留。

停止尚未確認時，該資源仍按可能計費處理，維持獨立停止監控並回報未確認狀態；不疊加新配置。沒有新的觀測、可行修正或狀態改變，就不再重試同一請求。

## CLI 0.7.2 的已知介面陷阱

以下是版本限定的恢復資料，不代表已提供自動 failover 服務。讀實際安裝來源／help，再使用所選 adapter 的狀態契約。

| 症狀／陷阱 | 已核對的行為與處理 |
| --- | --- |
| `Upload failed: File or directory not found: /content/…` | Contents API 將 HTTP 404 映成此訊息；它不單獨證明本機檔案缺少、遠端目錄被刪或 VM 已消失。先查分配，再查 lease／其他通道。 |
| `Session … lost (404/401). Cleaning up.` | CLI 可能 prune 本機 handle；這不等於官方 `unassign` 成功。先用保存的 endpoint 查 server。 |
| 刷新後仍讀不到資料 | 新 token 不代表 notebook websocket 健康，也不證明 worker 失敗；轉官方 SSH 查同一原作業，不重裝模型。 |
| 重建 `SessionState` 報 variant 型別錯誤 | 此版 assignment 的 `variant.value` 是整數，cache schema 要字串；用核實過的 enum 名稱，避免在付費期間重踩序列化錯誤。 |
| `colab ssh -s NAME` 找不到本機 session | 此版可自動建立 VM。恢復必須先驗精確 endpoint，使用已驗證的 existing-session bridge，不能靠名字直接呼叫並假定是原 VM。 |
| 保留 HF cache 後，重開下載仍接近全量傳輸 | Hub 1.33.0／Xet 1.7.0 每次建立新 partial，不能跨程序接續舊檔。只承諾校驗成功的完整檔重用；控制斷線保留背景下載程序。實機證據與版本來源見 [無生成演練](../../../research/colab-preflight-rehearsal-20261031.md)。 |

同一 endpoint 的 cache 更新在此版可使用官方回傳資料，保留私有 kernel 身分；下列片段本身不配置 VM、不提交推論。`saved_private` 是配置時保存的身分備份；需 notebook globals 的 route 若已失去 kernel ID，先找回原 kernel，再執行生成。獨立 ComfyUI worker 的 SSH／檔案恢復則不依賴 notebook globals。

```python
# 在已安裝 colab_cli 的 interpreter 中執行；外層子程序設 timeout。
# state 使用已授權的 auth provider 和本次私有 config，owned_endpoint/name 已持久保存。
from colab_cli.state import SessionState
from colab_cli.common import state

matches = [a for a in state.client.list_assignments() if a.endpoint == owned_endpoint]
if len(matches) != 1:
    raise RuntimeError("Original endpoint not uniquely present; reconcile allocation")
a = matches[0]
old = state.store.get(name)
restored = SessionState(
    name=name, endpoint=a.endpoint,
    token=a.runtime_proxy_info.token, url=a.runtime_proxy_info.url,
    variant=a.variant.name, accelerator=a.accelerator.value,
    machine_shape=a.machine_shape.name,
    kernel_id=(old.kernel_id if old else None) or saved_private.get("kernel_id"),
    session_id=(old.session_id if old else None) or saved_private.get("session_id"),
    keep_alive_pid=old.keep_alive_pid if old else None,
)
state.store.add(restored)  # 私有 cache；不要列印 restored/token/url。
```

此版官方 SSH 的既有連線入口是 `colab_cli.commands.ssh._run_proxy_bridge(restored, key_path, False)`，繞開 CLI 的 auto-create 選擇器；它是私有介面，升版先核實。作為 OpenSSH ProxyCommand 時，stdout 只承載 SSH bytes，避免 CLI 更新橫幅混入。key、known_hosts 和 ControlPath 按 allocation 隔離，保留主機金鑰核對；只使用有限的工作連線，不加自動重連／保活迴圈。

FastH3 獨立 CLI 的既有 `refresh/status/fetch`，以及 Studio 的 `status/fetch`，仍用各自 job 身分與資料契約；不要把 FastH3 runtime 目錄檢查套給原生 Omni，或在缺目錄時判定 VM 已消失。

# Colab 斷線與恢復整理

範圍：本工作區的 2026-10-28、2026-10-30 影片製作及本次對話工具回報。只讀既有紀錄，未啟動 runtime、查詢 live 帳號或提交生成。下列時刻為 UTC；台灣時間為 UTC+8。CLI 觀測版本為 0.7.2，ComfyUI／Omni 案例為 0.42.0／`h3-omni-int8`。

## 事件與實際結果

| 事件 | 已觀察的現象 | 處理與結果 | 證據與限制 |
| --- | --- | --- | --- |
| 10-28 pudding ch1 | 13:42:40 的 snapshot 尚有 1 assignment，數秒後 server assignments 為空 | `server_already_absent`；account snapshot 顯示 0 assignments、0 rate，沒有把本機 cache 清除當作停止證據 | [budget-latest](../projects/pudding-captive-ch1-omni-20261028/runtime/budget-latest.json)、[heartbeat](../projects/pudding-captive-ch1-omni-20261028/runtime/watchdog-heartbeat.json)、[release](../projects/pudding-captive-ch1-omni-20261028/runtime/release.json)。不知消失原因，也不是 SDK unassign 成功的證明。 |
| 10-30 forum ch1 安裝後 | 控制程式註記 notebook websocket 反覆失聯 | 沿同一 runtime 改 authenticated SSH；後續影片 receipt 與本機 hash 保存成功 | [local_control.py](../projects/forum-story-ch1-20261030/runtime/local_control.py)、[成功 receipt](../projects/forum-story-ch1-20261030/clips/s16-take02/receipt.json)、[本機 receipt](../projects/forum-story-ch1-20261030/clips/s16-take02/local-receipt.json)。websocket 原始例外與首次失敗時刻未留存；此項前半是程式註記，不能補成根因結論。 |
| 10-30 forum ch1 11:17:05 | 上傳新 job 回 `File or directory not found: /content/…json`，同次 usage 還列 1 assignment | 失敗發生在提交 inference 前，沒有自動重送；用已保存素材收尾，之後 stop／server／usage 確認釋放 | [batch-latest](../projects/forum-story-ch1-20261030/evidence/batch-latest.json)、[release](../projects/forum-story-ch1-20261030/evidence/release.json)、[delivery report](../projects/forum-story-ch1-20261030/delivery/delivery-report.json)。10:08:11 配置，失敗在約 68 分 54 秒後；沒有當時 proxy expiry 資料。 |
| 10-30 forum ch2 第 1 台 | 本次對話 16:22:55 上傳失敗；之後 `exec` 回 lost 401/404 並清本機 handle。server 起初仍列原 endpoint | 16:34:30 從官方清單取新 lease，回傳 3600 秒；刷新沒有恢復原通道。16:45:30 首次明確確認原 endpoint 不在清單，才記釋放與規劃重配 | [proxy-refresh](../projects/ch2試片/forum-story-ch2-20261030/evidence/proxy-refresh.json)、[sanitized SSH diagnostic](../projects/ch2試片/forum-story-ch2-20261030/evidence/ssh-diagnostic.log)、[release-r1](../projects/ch2試片/forum-story-ch2-20261030/evidence/release-r1.json)。首次上傳錯誤與 CLI 90 秒 timeout 來自本次對話；`batch-latest` 後被成功批次覆寫，不再是該次失敗的原始 log。 |
| 10-30 forum ch2 第 2 台 | 背景 setup 實際已於 16:58:09 READY，但 notebook 執行／監看通道逾時 | 官方 SSH 對精確新 endpoint 讀到既有模型／READY；保留安裝、切 SSH 控制，HTTP 取檔仍可用。17:06:44 起提交七支已審 job，全部本機 hash 保存後釋放 | [setup snapshot](../projects/ch2試片/forum-story-ch2-20261030/clips/s10-take02/setup-evidence/setup-status.json)、[SSH bridge](../projects/ch2試片/forum-story-ch2-20261030/runtime/ssh_bridge.py)、[transport flag](../projects/ch2試片/forum-story-ch2-20261030/evidence/use-ssh)、[首支 marker](../projects/ch2試片/forum-story-ch2-20261030/evidence/submission-s10-take02.json)、[batch](../projects/ch2試片/forum-story-ch2-20261030/evidence/batch-latest.json)、[release-r2](../projects/ch2試片/forum-story-ch2-20261030/evidence/release-r2.json)。原始 Jupyter timeout 與 SSH probe 在對話中；成功媒體／setup snapshot 是持久證據。 |

## 能推論到哪裡

- forum ch2 第 1 台 15:16:06 配置，首次上傳失敗在約 66 分 48 秒後；與 ch1 的約 69 分鐘接近，另有一次 3600 秒新 lease。足以把 lease 期限納入前置保存與控制操作檢查；不足以證明固定每小時踢線、token 到期就是兩次根因，或刷新一定能救回。
- 第 1 台首次失敗至確認 endpoint 不在約隔 22 分 36 秒。這是觀測跨度，不表示全程仍在計費或全程持續排查。第 2 台 READY 至首個提交 marker 約隔 8 分 35 秒，也包含本機處理，不能全歸為網路故障。兩者都顯示需要短時限分流、可靠通道驅動已授權批次，而不是靠主代理反覆長等待。
- 安裝後 websocket 失效而 SSH 可讀原 worker，與 endpoint 真消失是不同分支；`lost`／404／本機 prune 都不能代替 server 分配證據。
- 安裝錯誤不是斷線：ch1 曾因預先建立非空 ComfyUI 目錄導致 setup 被拒，修正輸入 staging 後才 READY，見 [setup snapshot](../projects/forum-story-ch1-20261030/evidence/probe-setup-latest.json)。模型 OOM／CUDA failure 也需各自的程序／資源證據，不由 transport 失聯推斷。

## 流程修改及版本依據

可操作規則集中在 [connection-recovery.md](../skills/colab-video-studio/references/connection-recovery.md)，資源與計價共用規則仍在 [runtime-monitoring.md](../skills/colab-video-studio/references/runtime-monitoring.md)。加入：

1. 配置時保存 endpoint、私有 kernel/cache 身分和回傳 lease 有效時間；控制操作跨期限前刷新。
2. 故障先查 server，之後至多一輪 lease 刷新及一輪替代通道；預設 5 分鐘恢復窗口，控制讀取另設短外層 timeout。
3. SSH 只連既有精確 endpoint，成功後整批沿用；從已知原 marker／prompt 繼續，完成結果優先取回。
4. 無可靠控制入口到點後保存 partial、精確停止並確認；重配只用原累計預算剩餘額度。無法確認停止時仍按可能計費處理。
5. 故障事件追加保存，避免最新狀態覆寫掉首次失敗；較長本機整理／QA 移到釋放後。

本機已安裝的 CLI 0.7.2 原始碼已唯讀核對：

- `colab_cli/contents.py`：Contents HTTP 404 映成 `FileNotFoundError`，不能據此判 VM 或檔案被刪。
- `colab_cli/commands/execution.py`、`common.py`：部分 401／404 分支 prune 本機 session。
- `colab_cli/client.py`、`state.py`：server 清單含新 proxy；assignment variant 為 enum，`SessionState.variant` 要字串。ch2 初次 cache 恢復曾用整數 `.value` 失敗，改 enum 名稱後通過序列化。
- `colab_cli/commands/ssh.py`：CLI selector 可在 session 缺失時 auto-create；既有 `_run_proxy_bridge` 可直接接已核對的 session，避免意外配置。私有 API 升版需重核。

對應成功範例是 ch2 的 [refresh_proxy.py](../projects/ch2試片/forum-story-ch2-20261030/runtime/refresh_proxy.py) 與 [ssh_bridge.py](../projects/ch2試片/forum-story-ch2-20261030/runtime/ssh_bridge.py)，含專案硬編碼，只作案例，不應原樣拿去操作下一個專案。Skill 內提供去除專案身分的 cache 範例，沒有宣稱新增自動 failover 服務。

## 費用與停止口徑

ch2 兩次配置共用原 20 CU 上限，A100 STANDARD、high-RAM 關閉；新配置未重設預算。完成 30 支原生 take，帳戶釋放後觀測扣除 10.99 CU，按首次 server 確認不在計算的配置時間保守估算 13.60 CU，見 [resource summary](../projects/ch2試片/forum-story-ch2-20261030/evidence/resource-summary.json)。兩值不可混作同一實際扣費；後續本機 QA 不再延長已結束區間。

這次文件更新只做離線核對與流程驗證，未重新連線、生成或重演付費故障。下次應以實際 recovery 事件耗時及是否重複提交／配置校準，不預先宣稱已實測能在 5 分鐘內恢復所有故障。

## 更新驗證

獨立 leaf agent 使用本 skill，對五個 synthetic 情境作離線前向決策：本機 handle 消失但原 prompt 仍在 SSH sampling、原 endpoint 消失但有不相干 VM、各控制通道失效且超過恢復期限、下一個操作會跨 lease 到期、GPU 0% 但下載 bytes 增加。結果皆選對分支，沒有重送原 prompt、停止他人 VM、重設累計預算或因六分鐘健康下載而重開；未發現阻塞性文件矛盾。這是文件行為驗證，不是連線恢復效能實測。

Skill validator、45 個相對檔案連結、Python 範例語法與 `git diff --check` 通過。驗證器使用現有含 PyYAML 的本機環境，未安裝套件。前向驗證原始案例／回答留在本機暫存 `colab-recovery-forward-20261031/`，未寫入正式 skill。

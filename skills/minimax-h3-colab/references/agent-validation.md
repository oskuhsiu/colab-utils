# 限時 agent 試驗與 session 審核

只在明確要求有界 agent 試驗／session audit 時使用，不是一般 H3 生成門檻。主代理負責指派、監看、整合與最終判斷；此頁不授權葉代理額外派工或 GPU。

## 試題與截止

固定題目、skill 版本 hash、模型／effort、可讀資料、可寫範圍、GPU 權限、UTC 截止及本輪驗收層級。等價多輪用乾淨上下文，保留相同題目與條件，避免透露上一輪解法。指定模型以 host session 記錄核對，角色名稱／自述不代替證據。

主代理以實際 clock 獨立監看，到期 interrupt；資源清理由授權且只針對本輪目標的安排執行。葉代理記錄起止，重試沿用同一截止，到期停止新工作並保存 partial 與 job 身分。停止證據使用 [共用生命週期](../../colab-video-studio/references/runtime-monitoring.md#資源與作業生命週期)。

Follow-up 各 turn 的 `task_started/task_complete` 分別與其截止配對。Session 跨度包含輪間等待，`host_active_seconds` 是 turn active 時長之和；兩者不是單片生成時間。Audit 的單一 `--deadline` 只比較最後完成時間。實際 `turn_aborted` timestamp 是中止邊界，中止 turn 不算完成，下一 follow-up 前的等待不算 active；interrupt 意圖或較早 clock 不能取代 host 中止事件。

## 捕捉與封存

Config、graph、export、debug 都在指定可寫目錄。重要準備、生成、媒體檢查與最終驗證命令可用：

```bash
python3 scripts/record_fast_h3_trial.py --root <run-dir> --label <唯一名稱> -- <命令與參數>
```

Recorder 保存實際 subprocess 起止、exit code、stdout／stderr 和 commands.jsonl。摘要另標 derived，不能手寫內容冒充捕捉輸出。Bytes、尺寸、SHA 與 receipt 欄位由檔案解析；prompt 建一次再供 prompt.txt／config 使用。Wrapper 正規化／忽略設定時，completed job 的實際 args 與 import versions 才是執行值，草稿意圖另列。

Readiness／manifest 建立時間是 phase 時間，不等於 host turn 完成。`phase_elapsed_seconds` 明示區間，總 active 時間由主代理核對。完整驗證還在進行時，不提前記整輪結束。

Append-only journal 最後一次寫入後，在另一份 manifest 算 journal／report／結果 hash；把自身最終 hash 寫回 journal 會立即使其失效。工具：

```bash
python3 scripts/seal_fast_h3_trial.py seal --root <run-dir> --files events.jsonl report.md result.json
python3 scripts/seal_fast_h3_trial.py verify --root <run-dir>
```

以工具 help 核對參數；重封存使用新的 `--manifest` 保留前版。只選明確證據文件，不含憑證。Report 重寫為本輪最後狀態，journal 保留事件順序。Reviewed timestamp 在相關實際檢查後產生。

## 結果與審核

Offline 分支只要指定 prepare／export／checks 通過就按範圍報 `offline_pass`，GPU／內容 `not_run`。GPU 分支驗新 receipt／MP4；歷史成功或合成 LoRA 接線不能充當本輪真實品質證據。使用 `verify_media`；自訂 ffprobe checker 先確認 JSON 型別並正規化，checker 故障不等於生成失敗。

主代理用 `scripts/audit_fast_h3_trial.py`（先讀 help）核對 observable tool timeline、host model／effort／active turns、產物、退出碼與資源行為。只審相關 session 的可觀察證據，排除隱含推理、秘密與無關資料。修訂依具體事件區分路由、工具、環境、執行問題；等價題目再驗時保留前後版本與變更條件，不把單次通過推廣為所有任務規則。

# Luna 實跑／session 審核／skill 修訂

使用者指定 `gpt-5.6-luna/max` subagent，多次測試，每輪設時限，按真實 session 修正 skill。

## 固定條件

- 原訂四輪：8 分鐘離線基準；修訂後 8 分鐘離線回歸；20 分鐘 L4 notebook 實跑；12 分鐘 L4 agent graph + LoRA 實跑。第四輪发现手抄 SHA 錯誤後，增加 6 分鐘離線封存回歸。
- 每輪 fork none，避免繼承主代理已知的解法。提示只交代要求、技能入口、責任／時限及交付證據，不把操作答案塞進測試提示。
- 主代理控制時限、GPU 配置與釋放。葉代理只寫該輪資料；不編輯生產碼或 skill、不派生代理、不改原 H3 模式、不生成原版大模型。
- 只有後兩輪可使用 GPU，限主代理提供的同一台 L4。主代理設定總 GPU 35 分鐘截止與每輪截止；超時保留紀錄並停止工作／已授權的本輪資源。
- 保存 skill 版本 hash、試題、wall time、host session metadata、工具呼叫／錯誤／輸出摘要及證据。敏感 token／proxy URL query 先清理。
- 審核實際找到的入口、執行命令、配置、驗證範圍、停止／資源行為、卡點及自述與證據差異。技能改動要能指回 session 的具體事件。
- 58 個既有 FastH3 檢查與 16 個原 H3 檢查是基準；倉庫既有 Qwen cell 數量失敗分開記錄。

## 預定驗收

離線輪應選正確 FastH3 路徑，保留原 notebook 的兩個 backend，產生可執行的 CLI／graph 準備資料並實際跑聚焦驗證。實跑輪應下載 MP4／metrics，核對 5 秒、864×480、24fps、native stereo、4-step／200 VSA／零 fallback；LoRA 輪區分合成載入檢查與真實風格品質。

完整原尺寸解碼与 session 工具證據由主代理獨立確認。前後比較使用同樣或等價試題；因提示補答案而成功的輪次不算 skill 改善證據。

## 完成紀錄

五輪 host session 都確認為 `gpt-5.6-luna/max`，並於固定截止前完成。離線基準找出 workflow help 寫入副作用、漏跑原 H3 regression、錯誤結束時間和自雜湊 ledger；修訂後第二輪離線驗證通過。第三、四輪生成新 L4 影片並由主代理獨立驗證。第四輪合成 LoRA 載入通過，但原 manifest 有一個手抄 SHA 錯字；保留原證據，新增自動封存工具，第五輪驗證全部 35 份封存檔案。

最後聚焦驗證為 62 個 FastH3 tests 加 16 個原 H3 tests，兩個 skill schema 與相關連結檢查通過。沒有執行原 H3 高記憶體模型。GPU 已釋放，零活躍 assignments、零當前 CU/hr；本次 campaign 使用 0.83 CU。

完整結果與範圍限制見 [試驗報告](../artifacts/fast-h3-skill-trials/20261009/REPORT.md)。

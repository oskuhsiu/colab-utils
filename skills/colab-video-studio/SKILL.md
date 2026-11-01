---
name: colab-video-studio
description: 規劃並在 Colab 製作影片，從素材與控制輸入、逐段生成到驗收和交付；也適用既有影片的角色替換、剪輯或生成問題診斷。
---

# Colab Video Studio

此 skill 管製作計畫與產物生命週期。模型的輸入契約、推論完成與作品符合要求分開核對；實測結果只適用其模型版本、素材和條件。主代理保留成片放行責任，製作與驗收可委派；依共用驗收處理證據與例外，不預設使用者逐支親審。

## 從當前任務開始

讀使用者要求與現有 plan／ledger，確定這次要規劃、試片、正式製作、剪輯或審查，以及交付規格、重要內容、限制與已接受的取捨。沿用已有授權；停止製作後的審查或文件工作不恢復生成。例行創作與實作選擇依現有資訊完成，缺項會改變要求或可行性時才詢問。

先沿用使用者指定的模型：`omni` 指 FastH3 Omni 的 `h3-omni-int8` ComfyUI 路徑；`pika` 依 [Pika H3 Flex 的預設路由與既有工作流](../minimax-h3-colab/references/pika-h3-flex.md)選擇；其他模型依[模型介面](references/controls.md)選路。指定路徑缺能力或資源時先說明缺口，取得變更方向後再換模型。

只讀當次需要的分支：

| 當次工作 | 參考 |
| --- | --- |
| 寫稿、重編內容或多鏡安排 | [內容與分鏡](references/story-planning.md) |
| 指定人物、外觀基準或 LoRA | [人物與適配器](references/people.md) |
| 跨片段狀態、一致性或長片 harness | [連續性與記憶](references/continuity.md) |
| 動作取景或運鏡 | [相機與構圖](references/camera.md) |
| 來源影片的角色／身體替換 | [控制與角色替換](references/character-replacement.md) |
| 選擇模型實際接受的條件 | [模型介面](references/controls.md) |
| 本地 CLI、plan／attempt／剪輯資料契約 | [執行工具](references/workflow.md) |
| 付費 runtime、連線逾時／401／404、恢復或停止 | [資源與作業](references/runtime-monitoring.md) |
| 訂判準、委派審查、看影片或放行 | [驗收與放行](references/video-review.md) |
| 調整原生尺寸、放大或比較速度 | [解析度與後製](references/resolution-upscaling.md) |

H3／FastH3／Pika H3 Flex 的提示與模型契約使用相鄰的 [minimax-h3-colab](../minimax-h3-colab/SKILL.md)。兩個 skill 在此 repo 成對提供。執行前由 [模型介面](references/controls.md) 區分 Studio adapter 與獨立工具，沿用所選工具的 job／receipt 介面。

## 製作流程

1. **準備可審計畫。** 把重要事件、人物／素材用途、鏡頭初末態、實際輸入、聲音與交付條件對應到每鏡。依驗收規則記明判準、可接受取捨與放行範圍，分開使用者必需內容與創作選擇。按作品目的選內容結構，單鏡或單純剪輯可直接處理。
2. **編譯可執行 job。** 用所選 adapter 的支援輸入和時鐘準備素材；確認實際 resize／crop、引用順序、版本、prompt 與輸出位置。角色敘事依 [內容與分鏡](references/story-planning.md) 將劇本判定的情緒強度轉成可見／可聽表演；使用語音 compiler 時，逐句語氣放入 `utterances[].delivery`。核對逐句發聲方式、嘴型與強度錨點已落入編譯後最終 `shot.prompt` 或實際後製設定，並寫入可觀察的 `criteria`。完成條件是 job 和全部輸入可追溯，`ready` 只代表準備完成。
3. **按不確定性試做與生成。** 先確認當次預算／嘗試限制和資料保存方式。多段工作按 [批次排程](references/runtime-monitoring.md#批次排程生成保存與驗收並行) 讓 GPU 自動接續已就緒工作，下載、驗證與內容審查獨立並行；修正 take 優先於尚未提交的一般工作。需要驗證核心能力時，用能看清該問題的短片與必要接點，只阻擋真正依賴試片結果的工作。使用者指定單輪、保留已知缺陷或僅交付試片時，照該範圍執行並如實標狀態。
4. **驗收與選材。** 核 receipt、hash、完整解碼，再依當次重要內容判斷。尚未確認的核心要求不以技術成功或預計日後可修替代。修正只涉及必要鏡頭及其依賴；相同條件重抽是新 take，不是原因診斷。
5. **剪接與交付。** selection 指向實際來源和評審；剪輯／後製改變內容或時鐘時重驗受影響內容與接點。匯出後檢查最終媒體、字幕／聲音和必要的即時播放，依驗收規則記錄實際成片的放行決定。報告結果、未達項及資源狀態，將測試／已知缺陷版與合格成品分開。

命令與不可重送的 attempt 契約在 workflow；付費作業、恢復與停止規則集中在 runtime-monitoring；判準、證據、委派放行與校準集中在 video-review。使用相應分支，不把所有專門流程加到每一支影片。

## 維護

案例、量測、錯誤時間線及驗證範圍留在 project／research。只有會改變未來操作、適用條件已清楚且不易從單一設定讀出的規則才進入 skill；更新現有對應段落並移除重複。來源索引見 [sources.md](references/sources.md)。

---
name: minimax-h3-colab
description: 準備、執行或診斷 MiniMax-H3／FastH3／Pika H3 Flex 的提示、模型接線、推論參數及 Colab 工具；支援離線準備與唯讀檢查。
---

# MiniMax-H3 on Colab

本 skill 處理 H3 模型契約與 repo 工具。通用製作、素材與驗收依賴同層安裝的 `colab-video-studio`；其 [驗收、委派與放行](../colab-video-studio/references/video-review.md) 和 [資源與作業生命週期](../colab-video-studio/references/runtime-monitoring.md#資源與作業生命週期) 是共用來源。模型工具與 Studio 的 reserve／submit 流程分開使用，不能把兩套 job 身分或狀態混在一起。

## 依任務選路

1. 確認本次是離線準備、唯讀診斷、已授權生成或停止。讀文件、修改 skill、檢查舊產物保持停止狀態；本次任務包含生成授權且未被後續停止取代時，才進入執行分支。使用者指定單輪／每段一次時，沿用該限制，不額外強制試片或品質重抽。
2. 依使用者指定模型與實際輸入選 backend／模式。`pika` 依 [Pika H3 Flex 的預設路由與既有工作流](references/pika-h3-flex.md)選擇；`omni` 走 [ComfyUI workspace](../../doc/COMFYUI_WORKSPACE.md) 的 `h3-omni-int8`。原 H3 的 checkpoint／processor／LoRA、FL／Ref 限制與步數看 [models.md](references/models.md)；舊 FastH3 的 pinned ComfyUI 路徑看 [fast-h3-l4.md](references/fast-h3-l4.md)，照片條件另看 [fast-h3-reference.md](references/fast-h3-reference.md)。模式名稱不構成條件已送入模型的證據。
3. 原 H3／FastH3 寫或改 prompt 時讀 [official-prompting.md](references/official-prompting.md)；Pika 使用其獨立 reference 的官方 prompt 指南。核對最終文字、實際素材順序及片長。定位 repo 工具／匯出 notebook 看 [repo-tools.md](references/repo-tools.md)；原 H3／FastH3 操作與斷線恢復看 [runtime.md](references/runtime.md)。只讀當前需要的 cell、函式或 lock，避免載入巨型嵌入 toolkit。
4. 生成結果分開報輸入準備、技術完成與內容 verdict。H3 特有輸入／人物／時序問題看 [visual-quality.md](references/visual-quality.md)，影片內容判斷與成片放行用共用驗收；只做離線準備則 GPU／媒體／內容為 `not_run`。限時 agent 試驗或 session 審核明確被要求時，才讀 [agent-validation.md](references/agent-validation.md)。

## 持續補充新坑

先在當次專案記錄版本、模式、症狀、原始證據、處理與仍未知的部分。使用者要求更新 skill 時，才把證據支持、會改變後續決策的窄規則整理到對應 reference；單次成功、待驗因果與製作流水帳留在專案。規則被新證據推翻時更新其範圍與結論。重要路由修改後驗 frontmatter 與引用；工具修改另做對應檢查。

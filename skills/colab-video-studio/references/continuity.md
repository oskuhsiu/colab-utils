# 跨片段連續性與記憶

用於多段影片的身份、場景狀態、接點，或選擇／移植長片 harness。先辨認要維持哪一層，再選實際支援的條件；模型名稱或長片示範不構成一致性保證。

## 分開管理四種資料

| 資料 | 用途與界線 |
| --- | --- |
| 身份素材 | 人物的固定外觀基準與實際 reference；選取及防止逐代漂移依 [people.md](people.md)。 |
| 故事／場景記憶 | 記角色、物件、位置、關係與事件的當前狀態，供下一段規劃。文字 scene graph 不等於多角色圖片資產庫；角色 ID 到視覺素材的對應需另行保存。 |
| 短期視覺交接 | 關鍵幀、前段影片或原始 latent 各有不同輸入契約；依 backend 核對真正送入的條件。前段解碼成 RGB 再經 VAE 編碼，不等同直接移交 sampler latent。 |
| 重疊區與剪接 | 記明重畫區、保留區間及聲畫時間映射，避免把交接內容重播或裁掉必要動作。時鐘處理見 [resolution-upscaling.md](resolution-upscaling.md)。 |

## 以實際選材更新狀態

觀察已選定片段 → 記錄可見結果 → 更新狀態 → 規劃下一段 → 準備條件與生成 → 驗收、選材後再提交新狀態。分開可見事實、推測與未完成計畫；prompt 描述過的事件不能直接記成已發生。被淘汰的 take 不覆寫正式記憶，換選材時重算受影響的後續依賴。

只保存下一段會用到的狀態與來源片段／時間，必要時保留不確定項。有限篇幅的改編仍以已定故事、時長與結局為約束；開放式 Director 不自行增加支線或延長作品。作業恢復與停止沿用 [runtime-monitoring.md](runtime-monitoring.md)，內容提交與接點判準沿用 [video-review.md](video-review.md)。

## 借用或移植 harness

- **ComfyUI H3 Continuum** 提供分塊延續、接點與 Take／session 管理。身份 reference、交接條件與保存位置仍以所選版本及 graph 為準；可恢復選材時保留其狀態資料，不能只留下 MP4。
- **HyperFlow-Infinity** 將固定身份圖、前段原始 latent 尾段、VLM 觀察與文字場景記憶分工。它已使用本地 H3；可選付費 VLM 負責觀察／規劃，並非影片生成器。這些是設計參照，尚未成為本 skill 的 Studio 功能。

替換生成器前核對 request／return 契約：影片與音訊、latent 的 shape／正規化與空間時間對齊、模型／VAE 相容性、實際 conditioning 及其審計紀錄。若原 harness 需要 latent 交接，只回傳 MP4 的 API 尚缺這一層；接口欄位有值也不證明條件已到達 sampler。實作細節以 [H3 skill](../../minimax-h3-colab/SKILL.md) 與 [ComfyUI workspace](../../../doc/COMFYUI_WORKSPACE.md) 的所選路徑為準。

驗證延續機制需包含真實續接；只成功生成開場尚未覆蓋跨段能力。以當次授權範圍選必要接點，分開看人物外觀、場景／道具狀態、聲畫接點與故事進展。比較 harness 時固定可控制的素材、模型、分鏡及成本條件；不同示範不足以宣稱誰普遍更一致。

## 一手設計來源

以下為閱讀時的固定版本，數字與內部實作不作通用預設：

- [H3 Continuum README](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/blob/7e14fde33f8e8fa5804fa409777d33afee2427f4/README.md)：分塊延續與 Take／session 設計。
- HyperFlow-Infinity 的 [engine](https://github.com/Video-Rebirth/hyperflow-infinity/blob/6c3291f319de9a81f63538af9b48da7cbc0b6a3f/src/hyperflow_infinity/engine.py)、[memory](https://github.com/Video-Rebirth/hyperflow-infinity/blob/6c3291f319de9a81f63538af9b48da7cbc0b6a3f/src/hyperflow_infinity/memory.py)、[handoff](https://github.com/Video-Rebirth/hyperflow-infinity/blob/6c3291f319de9a81f63538af9b48da7cbc0b6a3f/src/hyperflow_infinity/handoff.py) 與 [generator](https://github.com/Video-Rebirth/hyperflow-infinity/blob/6c3291f319de9a81f63538af9b48da7cbc0b6a3f/src/hyperflow_infinity/generator.py)：觀察／規劃／提交、文字記憶、latent 交接與生成器契約。

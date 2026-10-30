# 官方提示格式與本地適配

寫或修改 H3 prompt 時讀本頁，核對最終送入 processor 的文字與資料。格式符合不代表身份、動作或畫面已通過。

## 來源與版本

本頁依 MiniMax-AI/MiniMax-H3 commit `d21241f0a4b3acbb34c97dae47fa417b7065e438`（2026-08-15）。升級時比較相應文件，既有 run 保留原契約。

| 固定來源 | 用途 |
| --- | --- |
| [h3-prompt-writing/SKILL.md](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/SKILL.md) | 模式、欄位順序、英文改寫與原語言台詞 |
| [base-en.txt](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/base-en.txt) | Base 模式、keyframe 對齊首行、鏡頭與聲音 |
| [ref-en.txt](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt) | Ref 六欄、來源與主體、保留關係 |
| [README](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/README.md) | H3-Context-IR、H3-Base、H3-Regenerate-2K 的系統界線 |

本地 Base 加自寫 prompt 未執行託管 Context-IR／2K regeneration。官方 `h3-prompt-writing` 可攜；其餘 Hub skills 依賴 canvas、choice cards 和 `hub_generate_*`。例如 [3d-animation-short-generator](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/3d-animation-short-generator/SKILL.md) 的 [shot table](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/3d-animation-short-generator/references/shot-table-spec.md)、[fallback](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/3d-animation-short-generator/references/fallback-policy.md) 與 [QC](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/3d-animation-short-generator/references/qc-checklist.md) 屬 Hub 工作流，其 toon 比例、卡片、重試梯與 backend 切換不自動適用本地 Colab。

## 先選輸入模式

| 實際輸入用途 | 模式與描述方向 |
| --- | --- |
| 文字 | T2VA：可見、可聽的過程 |
| 首幀 | I2VA：首幀現狀→起動→發展 |
| 首尾幀 | FL2VA：中間連續動作與狀態變化 |
| 尾幀 | L2VA：合理開場→接近末態 |
| 人物／服裝／場景／動作來源 | Ref2VA：來源用途→生成過程 |

官方單次範圍為 4–15 秒；本地 wrapper 可能更窄，見模式文件。`[Shot N]` 代表切鏡，單鏡中的人物動作／攝影移動仍屬同一 shot。

## Ref2VA 六欄與來源對應

英文欄位按此順序；台詞、歌詞與畫面文字保留原語言：

```text
subject_definitions:
summary:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:
```

實際輸入順序決定 `<Picture N>`；影片與音訊各自編號。保存 path／hash／crop→label→用途對照。`<Subject N>` 可代表人物、臉髮、服裝、環境或動作，多來源可提供同一 Subject，同一來源也可提供不同 Subject。

只提供身份的照片在 Subject 中引用 Picture；圖片本身作首尾幀／構圖錨點時才獨立定義 Picture 及保留關係。文字中的「首幀」不會建立 loader 沒有接入的硬控制。影片來源用 `<Video N>`；只對實際提供／啟用的音訊定義 `<Audio N>`。

本人外貌、扮演角色與新服裝分開定義。同人原照與定裝照一起輸入時，綁定同一身份並區分各來源用途。`retention_analysis` 對已定義內容列出 shots、理由及 `fully_preserved`／`partially_preserved`／`attribute_transfer`／`weak_reference`；關係相對於定義用途判斷。只定義臉髮時，新服裝不改變臉髮的保留範圍；定義整人含原衣服時，換裝須列部分保留。這些標記是輸入意圖。

`summary` 以實際任務標籤開始，如 `[reference generation]`。`video editing`／`video continuation` 只用於實際來源影片；另有 `keyframe completion`、`audio reuse`、`audio reference`，按資料用途選。

`detailed_description` 建立風格後以 `[Shot 1]` 起頭，首鏡不帶 cut timestamp；後鏡如 `[Shot 2] At 00:03.500, ...`，時間遞增且在片長內。首次清楚出現人物時用 Subject 及具體可見特徵，後鏡沿用。Ref 指南通常建議 350–500 英文詞，依內容分配，不用重複限制湊詞。攝影 `pull out` 指退後，`zoom out` 指焦距變化；描述可見過程，區分人物移動與鏡頭移動。

說話在主時間軸用 `<Subject N> (S1) ... <d>[語言] 原台詞</d>`。S 編號依本段實際發聲順序並跨鏡沿用，不等於 Subject 編號；未發聲者不加 S。跨片段需要聲線一致時另保存角色→聲音描述。旁白依指南用 `says in an off-screen voiceover` 並交代畫面人物嘴唇閉合；跨鏡台詞用 `<scenetrans>`，片尾截斷用 `<cutoff>`。

`overall_soundscape` 描述環境、物理動作與非語言聲音；`<d>` 台詞留在主時間軸。`non_diegetic_music` 描述觀眾聽到的配樂，無配樂寫 `N/A`。

## Base：三欄與 keyframe 首行

T2VA 用 `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music` 三欄。I2VA／FL2VA／L2VA 前加圖片時間對齊首行及空行；產出前讀固定 `base-en.txt` §2.1 的對應完整模板，填真實 final shot 與兩位小數片長。缺來源時保留待補，不猜首行。

`[Shot 1]` 建立風格與構圖後描述過程。FL 通常建議單一連續鏡頭，明確切鏡需求才增 shot；只各述首尾圖不足以描述中間轉變。畫面文字用英文雙引號包原字，其餘對白／聲音依 Base 指南。

## 最終輸入檢查

保存經核對的序列化 prompt 與來源對照，檢查：模式／欄序／keyframe 首行符合實際接線；所有 label 有來源且 Subject、retention、畫面用途一致；`[Shot 1]`、遞增切鏡時間與對白時間有效；S 編號依發聲順序；初末服裝、道具、地標、位置與當段時序無矛盾。空鏡使用自己的場景描述，角色／聲線共用文字僅帶入需要的鏡頭。

此檢查證明輸入符合所選規格；`fully_preserved`、exact face 或否定句不構成像素硬鎖。輸入故障診斷看 [visual-quality.md](visual-quality.md)，模型／loader 看 [models.md](models.md)。

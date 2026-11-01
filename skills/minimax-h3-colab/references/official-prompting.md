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

規劃或補製人物圖時讀本地 [人物參照](../../video-production/references/character-references.md)。同人全身、臉部及角度圖只引用實際送入的 Picture，合併到同一 Subject 並說明各自用途；身分圖的背景或正面姿勢不自動成為當鏡場景與演出朝向。

`summary` 以實際任務標籤開始，如 `[reference generation]`。`video editing`／`video continuation` 只用於實際來源影片；另有 `keyframe completion`、`audio reuse`、`audio reference`，按資料用途選。

`detailed_description` 建立風格後以 `[Shot 1]` 起頭，首鏡不帶 cut timestamp；後鏡如 `[Shot 2] At 00:03.500, ...`，時間遞增且在片長內。首次清楚出現人物時用 Subject 及具體可見特徵，後鏡沿用。Ref 指南通常建議 350–500 英文詞，依內容分配，不用重複限制湊詞。攝影 `pull out` 指退後，`zoom out` 指焦距變化；描述可見過程，區分人物移動與鏡頭移動。

本地分鏡依 [段內時間線與具體表演](../../video-production/references/intrashot-staging.md) 細化動作、注意力與對話輪替，並寫入 `detailed_description`（Base 則為 `integrated_multimodal_description`）。同一連續鏡頭的時間窗保留在同一 `[Shot N]` 內；只有實際切鏡才新增 Shot。把人物在對誰說、看向誰／物件及聽者如何反應寫進描述，不以參考圖的正面姿勢替代當場互動。這是本地提示寫法，不新增 backend 欄位或時間硬控制。

說話在主時間軸用 `<Subject N> (S1) ... <d>[語言] 原台詞</d>`。S 編號依本段實際發聲順序並跨鏡沿用，不等於 Subject 編號；未發聲者不加 S。跨片段需要聲線一致時另保存角色→聲音描述。旁白可用 `says in an off-screen voiceover` 描述；畫面人物的發音動作須另依下述本地發聲方式指定。跨鏡台詞用 `<scenetrans>`，片尾截斷用 `<cutoff>`。

`overall_soundscape` 描述環境、物理動作與非語言聲音；`<d>` 台詞留在主時間軸。`non_diegetic_music` 描述觀眾聽到的配樂，無配樂寫 `N/A`。

## 本地表演與發聲方式交接

含角色表演或內心話時，生成前依 [情緒與表演](../../video-production/references/emotion-and-performance.md) 判定劇本所需的 E0–E4 強度，分開 felt／shown 的進程，決定具體表演錨點、逐句 `delivery`、`voice_mode`、嘴型及聲音聽感／可聽對象。這是本地製作標註，不是新增 H3 欄位、特殊 tag 或 guidance 對照表；在既有畫面與語音描述中表達，實際能力另驗。

把逐句的語速、重音、停頓、氣息與情緒變化寫進當句發聲描述，與動作、表情和時點接上；Ref2VA 放在 `detailed_description`，Base 放在 `integrated_multimodal_description`，維持各自原有欄位。共用角色文字保留聲線身份，當句表演照分鏡轉入；核最終序列化文字，而非只檢查 metadata 有 `delivery`。表演、模式、音效及聲音處理寫在台詞 tag 外，`<d>[語言] ...</d>` 只放實際要聽到的文本。

新語音 job 走 [對白估時與語速](../../video-production/references/dialogue-pacing.md) 的 compiler：base 保留視覺／動作與既有欄位，逐句語氣放 `utterances[].delivery`，台詞只放 `text`，由 compiler 插入 `<d>` 與發聲目標。不要將包含 `<d>` 的完成稿再當 base 編譯，也不要把 felt／shown 塞進 timing schema。檢查的是編譯後 prompt；情緒強度不自動改變語速或要求台詞填滿片長。

例如劇本要求認出門外威脅後，恐懼由 E1 升至 E3，但為免被發現而壓低聲音。下列為 base 的視覺／動作局部內容；完整 Ref2VA base 仍使用既有六欄與實際來源綁定，這段放在 `detailed_description` 的同一 `[Shot 1]` 內：

```text
On recognizing the figure at the doorway, <Subject 1> abruptly stops typing, fixes her gaze on the door and tightens her grip on the phone already in her hand. She recoils one step. She keeps watching the doorway with her hand clenched around the phone through the end of the shot.
```

對應的 timing 輸入如下；Studio 放入 `shot.dialogue_timing`，原生 ComfyUI 放入 `timing.json`。示例的最早起點與末段反應是當鏡工作假設，依實際表演調整，不作通用定值：

```json
{
  "utterances": [
    {
      "speaker": "<Subject 1> (S1)",
      "text": "是他！他就在我家門口！",
      "language": "Chinese",
      "voice_mode": "spoken",
      "delivery": "The first phrase catches in her throat; after a brief break, the second is urgent and breathless, kept to a whisper so she is not heard outside. Preserve strong fear without a calm or uniformly slow delivery.",
      "not_before_seconds": 1.5
    }
  ],
  "reaction_seconds": 1.0
}
```

`delivery` 不會自動調整估算秒數；句內中斷若明顯影響時間，依試讀提供含停頓的實測或修正估計，不因情緒級別任意填數字。低音量仍須保留強烈表演的語流與動作，不翻譯回 `slightly worried` 或套固定 `calm delivery`。若劇本改為心聲，另改 compiler 支援的模式、嘴型及當句聲音描述。對只提供身分的 reference，保留臉髮等身分特徵，不將中性表情列入必須保留的內容；首尾幀的實際表情須與該時點相容。

口說描述對應角色的同步發音動作。心聲／旁白可用畫外 voiceover 形式承載，但須另外說明其敘事層、聲音與嘴型；實際人在畫外出聲則描述其位置與遮擋，不將它混作在鏡角色心聲。非發音限制僅作用於相關角色與時窗，同鏡其他口說角色仍正常發音。

以下為最終 prompt 的當句局部寫法示例，完整 prompt 仍需原有六欄及正確來源綁定；同一句台詞只寫一次。採 timing compiler 時，不直接把這些含 `<d>` 的片段貼入 base，先核對其支援模式：一般心聲用 `inner`，畫外口說的本地 `offscreen_spoken` 對應 `offscreen`；目前 `silent_mouthed_inner` 不在其模式清單內，不能靜默降成嘴型相反的 `inner`。無聲說話示例只說明目標表演，不代表現有 compiler 已能編譯該模式：

心聲（觀眾有聲，角色無該句發音嘴型）：

```text
<Subject 1> (S1) is heard in her private inner voice, retaining her recognizable voice but with a slightly hollow resonance and a short, soft tail. Her urgency tightens the breath and quickens the words. On screen her jaw stays tense and she holds her breath without articulating the following words: <d>[Chinese] 別出聲。</d>.
```

無聲的說話（嘴型對應心聲，現場沒有另一次口說）：

```text
<Subject 1> silently mouths the following words toward her companion. In that same interval, her own private inner voice (S1) is heard with slightly hollow resonance, suppressed urgency and a breath caught before the last word: <d>[Chinese] 別出聲。</d>. Her lips articulate this sentence in sync with the inner voice; no separate in-world spoken voice is produced.
```

提交前確認模式沒有互相衝突：普通心聲保留無發音動作，無聲說話明確保留嘴型加同一句心聲；情緒仍存在於聲音處理之下。原生輸出未能區分時，按已允許工具採適用控制或獨立配音／後製，再驗實際聲畫，不能因語法正確就宣稱表演、空洞聽感或嘴型已成功。

## Base：三欄與 keyframe 首行

T2VA 用 `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music` 三欄。I2VA／FL2VA／L2VA 前加圖片時間對齊首行及空行；產出前讀固定 `base-en.txt` §2.1 的對應完整模板，填真實 final shot 與兩位小數片長。缺來源時保留待補，不猜首行。

`[Shot 1]` 建立風格與構圖後描述過程。FL 通常建議單一連續鏡頭，明確切鏡需求才增 shot；只各述首尾圖不足以描述中間轉變。畫面文字用英文雙引號包原字，其餘對白／聲音依 Base 指南。

## 最終輸入檢查

保存經核對的序列化 prompt 與來源對照，檢查：模式／欄序／keyframe 首行符合實際接線；所有 label 有來源且 Subject、retention、畫面用途一致；`[Shot 1]`、遞增切鏡時間與對白時間有效；S 編號依發聲順序；初末服裝、道具、地標、位置與當段時序無矛盾；情緒、逐句表演、發聲方式、嘴型與聲音處理符合分鏡且已進入實際提示。空鏡使用自己的場景描述，角色／聲線共用文字僅帶入需要的鏡頭。

此檢查證明輸入符合所選規格；`fully_preserved`、exact face 或否定句不構成像素硬鎖。輸入故障診斷看 [visual-quality.md](visual-quality.md)，模型／loader 看 [models.md](models.md)。

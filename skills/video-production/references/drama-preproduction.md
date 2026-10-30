# 短劇前製：劇本、資產與鏡頭交接

用於小說改編、短劇、多集故事或需要共用角色／場景／道具的敘事影片。依本次工作採用需要的部分；已有合用劇本或只改一鏡時，直接沿用既有內容。此頁含整理改寫的上游內容與可複用模板，來源、修改說明與授權見文末。

## 先定劇情，再定鏡頭

保留指定情節、人物關係和必留台詞，把敘述轉成觀眾可見的行為、環境及必要聲音。劇本先記場次、內外景、地點、時段、動作與對白；景別和運鏡留到分鏡，避免修改取景時連帶改掉故事。

按事件、揭露、選擇與反應整理節拍。移動場地或時段時明示交接；同一事件的起因、動作、結果與反應要有足夠畫面承載。段落長度以實際表演、台詞試讀和剪輯需要估算，再配合所選模型支援的片長安排生成。

## 以當集需求整理共用資產

先看現有資產，再補當集實際出現的項目。給人物、場景及關鍵道具穩定 ID，另記名稱與別名；別名可協助查找，遇到同名人物或不同外觀狀態時人工確認，避免誤合併。

| 類別 | 要保存的基準 | 何時另建變體 |
| --- | --- | --- |
| 人物 | 身分與關係、可辨識五官／體態、髮型、服裝、原始參考圖 | 劇情需要的換裝、年齡或受傷狀態；保留與同一人物的關聯 |
| 場景 | 地點、時段、出入口、主要陳設相對位置、光源及背景圖 | 晝夜或布置改變會影響接戲時；沿用原場地的空間基準 |
| 關鍵道具 | 材質、形狀、比例、顏色、辨識細節與基準圖 | 劇情造成破損、開合、內容或持有人改變時，記下狀態 |

優先為推動情節、需要特寫或反覆辨認的物件建立獨立道具資產。普通陳設留在場景描述，常規穿戴留在人物造型；沒有關鍵道具就留空。資產投入生成的數量按用途與預算決定。

基準圖按用途寫提示：人物圖清楚呈現身分與造型，必要時補正面／側面／背面；場景圖以無人物的空間建立圖交代出入口、前中後景與固定布局；道具圖以乾淨背景完整呈現物件、比例和邊緣。多視角人物表供設定核對，實際送入影片模型的圖則按支援條件選單張或裁切，避免把整張設定表當成該鏡構圖。使用者提供的照片優先保留為原始基準。

## 分開故事段落、剪輯鏡頭與生成工作

故事段落可以包含多個鏡頭；一個生成工作能否完成這些切鏡，取決於實際模型與已驗證能力。需要可靠切鏡時，拆成可生成的鏡頭後剪接。把每鏡的敘事目的、場景／角色／道具 ID、聲音、可見動作、初末態及接點寫清楚，讓生成與剪輯使用同一份內容依據。

台詞以自然試讀或已有音軌估時，再留動作、停頓及反應時間。容納不下時調整剪輯或拆鏡；旁白和對白保留原文及說話者，避免提示詞轉寫時新增情節。

## 從分鏡轉成模型提示

- **靜態起幀**：描述起始構圖、人物位置、外觀、場景和光線，選能支持後續動作的狀態。
- **動態內容**：按本鏡時間順序描述可見動作及結果；需標時間窗時，涵蓋預定片長且前後相接。每段集中在可辨認的動作，情緒落成表情、姿勢或行為。
- **聲音**：分清台詞、旁白、環境音與配樂，標出說話者及對應動作。依模型是否支援原生語音，決定送入生成或留給後製。
- **參考綁定**：從資產 ID 追到實際檔案、用途和輸入順序，再轉成所選 backend 的語法。H3 使用 [H3 提示契約](../../minimax-h3-colab/references/official-prompting.md)；Studio 使用 [資料與執行契約](../../colab-video-studio/references/workflow.md)。

上游的 `@名稱` 由其應用程式替換成圖片參照，其 `read_*`／`save_*`／`update_storyboard` 也是該後端工具。此 repo 不提供這些呼叫或自動替換；在本地編譯 job 時完成實際綁定。專案風格也須送入最終提示或已驗證的模型設定，不能假設有上游的自動注入。

## 可複用的前製模板

將下面需要的欄位複製到當次 project 的前製文件。這是內容交接表；提交前另轉成實際工具接受的 job。

```markdown
# 作品／集次
目的、受眾、來源與改編範圍：
交付時長、比例、語言、聲音、工具與預算：
必留事件／台詞與來源位置：

## 場次與劇本
場次 ID／地點／內外景／時段：
動作、台詞、說話者與必要聲音：
本場的新資訊、結果與下一場交接：

## 當集資產
資產 ID／類別／名稱與別名／來源檔案：
外觀或空間基準／當集狀態與變體／出現場次：
參考圖用途／需新增或可沿用的素材：

## 鏡頭（按需要重複）
鏡頭 ID／所屬節拍與場次／敘事目的：
場景 ID／人物 IDs／關鍵道具 IDs：
景別與運鏡／預計剪輯長度／生成長度：
初態 → 可見動作與結果 → 末態／下一鏡接點：
台詞原文與說話者／音效、旁白、配樂時點：
起幀提示／動態提示／實際參考檔案與輸入順序：
必須看見或聽見的證據／尚待試片的能力：
```

交接前，確認重要情節都有鏡頭或聲音承載、資產引用可解析、台詞放得下、相鄰初末態可銜接，以及每個工作能送入所選模型。局部修改時更新受影響的鏡頭與資產關聯，保留其他已成立內容。前製完成只代表可進入製作；成片依 [video-production](../SKILL.md) 的剪輯與驗收流程檢查。

## 來源、修改與授權

來源專案為 [chatfire-AI/huobao-drama](https://github.com/chatfire-AI/huobao-drama)，以下連結固定於 commit `3c6fdd68a6c21d4fbfae2689344d88063217abef`：

- [劇本改寫](https://github.com/chatfire-AI/huobao-drama/blob/3c6fdd68a6c21d4fbfae2689344d88063217abef/backend/workspace/skills/script-rewriter/SKILL.md)與[分鏡拆解](https://github.com/chatfire-AI/huobao-drama/blob/3c6fdd68a6c21d4fbfae2689344d88063217abef/backend/workspace/skills/storyboard-breaker/SKILL.md)。
- [資產提取](https://github.com/chatfire-AI/huobao-drama/blob/3c6fdd68a6c21d4fbfae2689344d88063217abef/backend/workspace/skills/extractor/SKILL.md)。
- [人物](https://github.com/chatfire-AI/huobao-drama/blob/3c6fdd68a6c21d4fbfae2689344d88063217abef/backend/workspace/skills/prompt-generator/character-prompt/SKILL.md)、[場景](https://github.com/chatfire-AI/huobao-drama/blob/3c6fdd68a6c21d4fbfae2689344d88063217abef/backend/workspace/skills/prompt-generator/scene-prompt/SKILL.md)、[道具](https://github.com/chatfire-AI/huobao-drama/blob/3c6fdd68a6c21d4fbfae2689344d88063217abef/backend/workspace/skills/prompt-generator/prop-prompt/SKILL.md)與[影片提示](https://github.com/chatfire-AI/huobao-drama/blob/3c6fdd68a6c21d4fbfae2689344d88063217abef/backend/workspace/skills/prompt-generator/video-prompt/SKILL.md)。

2026-10-30 修改：以繁體中文整併前製流程與模板；將上游固定段長、三秒分段、字數估時、道具數量及多視圖版式改為依作品和模型決定；改用本 repo 的資產／job 交接，保留既有生成與驗收流程。

本文件（含上方模板）的整理改寫內容採 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)，沿用[上游授權](https://github.com/chatfire-AI/huobao-drama/blob/3c6fdd68a6c21d4fbfae2689344d88063217abef/LICENSE)的姓名標示、非商業性與相同方式分享條件及免責條款。此標示適用於本文件；repo 其他既有檔案依各自授權處理。

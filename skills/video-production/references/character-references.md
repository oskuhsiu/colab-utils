# 人物參照：身分、視角與實際輸入

用 imagegen 新建或補製跨鏡人物資產時讀本頁。先沿用已選定人物及作品畫風；只補當次分鏡缺少的資訊。這是本地素材設計方法，並非模型保真保證。

## 分清素材用途

| 素材 | 要提供的資訊 | 畫面安排 |
| --- | --- | --- |
| 人物身分／定裝基準 | 五官、髮型、體態、服裝及固定配件 | 單人、乾淨中性背景、可辨識的臉與輪廓 |
| 場景基準 | 出入口、陳設、空間與光線 | 以空間為主，按劇情保留需要的地理資訊 |
| 當鏡起幀／構圖圖 | 當場人物位置、姿態、場景及光線 | 配合該鏡演出；可有人物與完整環境 |

新製人物基準預設使用素色淺灰或其他能分離髮絲、衣物輪廓的中性背景，柔和均勻照明，姿態放鬆、表情平靜；情節道具與場景陳設另做資產。保留眼鏡等身分配件。電影感的場景光、強陰影與動作姿勢留給當鏡圖，避免把它們綁入共用人物提示。

乾淨背景不等於必須透明。合成或使用者要求透明底時，依 imagegen 產出真正 alpha；影片 loader 不支援或會丟棄 alpha 時，另備中性實色底衍生圖，核對它真正收到的畫面。既有人物照可保留原背景作原始基準；需要清背景時另做衍生版，核對臉髮及邊緣，保留原檔。

## 主要角色的基本覆蓋

跨片段反覆出現、需要對話或轉身的主要人物，預設準備以下可獨立使用的圖；已有合格素材就沿用：

- **正面全身定裝圖**：完整頭頂、雙手、腳與鞋，交代體態、比例、衣物長度和固定配件。
- **正面臉部近景**：臉在圖中有足夠細節，保留髮際、耳側與下顎，清楚呈現眼、鼻、嘴和膚質；從遠景放大小臉不會增加原本沒有的細節。
- **分鏡需要的斜側面／側面**：對話、轉頭或側拍使用的三分之四面或側面；左右側依實際走位選，背拍需要時補背面及服裝背部。

單次遠景或不需辨認的次要人物可以少圖；不為每人固定生成六面。先確認全片需要的角度與景別，避免到付費生成時才發現只有一張正臉。多視圖表可供設定核對，但各視圖須能獨立取得且細節足夠；一般優先保存單人、單視角圖，避免縮小成拼圖後失去臉部資訊。

## 從同一基準補圖

先選定身分基準，再將該圖作為 imagegen 的實際參考輸入補近景、角度或定裝；沿用 imagegen 的本地圖片查看與引用流程。每次寫清保留同一人的五官、髮型、年齡感、體態及不變的服裝配件，只改指定視角、景別或背景。不要只重複文字描述而各自重新選角。

劇情換裝時，將服裝列為明確變更並保存造型變體，臉髮與體態仍對照原身分基準；不將「保留原服裝」帶入換裝提示。

逐張並排核對基準：眼距、鼻樑／鼻尖、唇形、下顎、髮際、髮型、眼鏡、膚色、體態及衣物細節是否一致。側面是生成推測，不能只因標成「同一人」就接納；漂移的圖修正或淘汰。髮分、痣、傷痕等左右特徵保留正確側別，水平翻轉不當作新視角。真人未提供的視角亦不得標成實拍身分證據。

保留最初選定的身分基準，各衍生圖回到它比對；避免用上一代生成臉逐代改寫人物。沿用專案既有資產欄位，能追查角色 ID、用途、視角／景別、來源與衍生關係、檔案及 hash、實際查看結果即可，無須新增 backend 欄位。

imagegen 提示可按下面的用途填寫；首張省略 Input images，補圖時填入真正引用的已選基準：

```text
Asset type: reusable character identity / wardrobe reference, one person in one view.
Input images: [selected character ID and image], the identity anchor for this derivative.
Subject: [stable face, hair, build, wardrobe and identity accessories].
Composition/framing: [front full body / front head-and-shoulders / required three-quarter or profile]; keep the relevant features fully visible and detailed.
Scene/backdrop: plain neutral light-grey studio background, clear separation around hair and clothing.
Style/medium: [the project's chosen visual style].
Lighting/mood: soft even light, natural skin and proportions, relaxed neutral expression.
Constraints: preserve the selected person's identity and all attributes outside the requested [view, framing, background or wardrobe change]; one single view, no collage, labels or watermark.
```

## 送入影片模型前

資產庫可以有多角度，每個 job 只選當鏡需要且實際介面支援的圖。身分／服裝圖、場景圖和起幀各自綁定用途；只支援首幀的模式，先準備該鏡真正的單一構圖，不能以中性背景人物圖冒充場景起幀。參考分支只收單圖時，按當鏡主要需求選角度與景別，記明未送入的資訊；不把整張人物多視圖表當作通用解法。

支援多張 reference 時，同人全身、臉部與不同角度綁到同一角色，分別說明提供什麼；按實際預算及圖片上限選最有用的圖。H3 的 Subject／Picture 與來源順序依 [提示契約](../../minimax-h3-colab/references/official-prompting.md)，Pika 依其[獨立契約](../../minimax-h3-colab/references/pika-h3-flex.md)，不因資產齊全就假定全部已接入。

查看最終 resize／crop 和序列化 prompt，確認人物仍有足夠臉部資訊、無拼圖／旁人誤入，背景與姿勢由當鏡決定。裁切設定表時只取相關單一視圖；圖面不足就補圖或記明限制，不用「保持一致」替代缺失資訊。影片驗收再按實際出現的角度、轉頭與遮擋前後比對人物，也檢查中性背景或設定表構圖是否誤入成片；素材檢查通過不代表影片保真已通過。

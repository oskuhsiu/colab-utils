# 小說改編成手機縱向網漫：分鏡與連續性研究

調查日期：2026-09-24  
範圍：把小說改編成手機下滑閱讀的 webtoon，而不是把小說段落逐句配圖，也不是把傳統翻頁漫畫頁面上下堆疊。本文只新增研究與工作契約，沒有修改目前的程式、既有 plan 或圖像。

## 結論先行

目前專案的第 1、2 章仍是「一張完整漫畫頁」思維：`portrait 2:3`、每頁四到五格、六頁、右到左閱讀；page task 也要求模型產生 `ONE finished full-color manga page`。這套格式可以輸出 PDF，但它沒有把手機視窗、下滑節奏、面板間距、滾動揭露和場景留白當成一級資料，因此不適合直接稱為網漫分鏡。[第 1 章 story bible](../projects/pudding-hamster/chapter-01/story_bible.json) · [第 1 章 page plan](../projects/pudding-hamster/chapter-01/page_plan.json) · [第 2 章 page plan](../projects/pudding-hamster/chapter-02/page_plan.json)

建議把下一版資料模型的最小單位改成：

```text
小說來源跨度
  → 故事節拍與讀者狀態
  → vertical-scroll segment
  → panel / gap / reveal / text
  → 參照圖 bundle + generation manifest
  → 手機視窗 QC + 長條拼接
```

分鏡先決定「讀者在這一段下滑前知道什麼、下滑後發現什麼」，再決定畫面；不要先按小說段落數量切成固定六頁。圖像生成仍可在 Qwen Image 2.1 上逐格或逐個 segment 進行，但畫風與角色連貫需要由版本化的 visual bible、固定參照 bundle、可重現的 generation manifest 共同維護。固定遠端 model instance 是必要的運行條件，單獨保證不了視覺連續性。

## 1. 來源證據與可用程度

### 1.1 官方網漫平台與創作教材

**WEBTOON Creator's Resource Handbook** 是本次關於縱向閱讀的主要一手來源。WEBTOON 的 [CANVAS 資源說明](https://webtooncanvas.zendesk.com/hc/en-us/articles/18771041280916-What-resources-are-there-for-new-creators) 明確把 handbook 描述為包含 vertical scroll、character sheets 和 pre-production 的官方教材；[handbook PDF](https://webtoons-static.pstatic.net/creator101/en/pdf/Creators-Resource-Handbook-Updated.pdf) 的「The Vertical Format」段落提供以下編排指引：

- 作品是手機優先的縱向媒介，讀者通常一次看到一個或少量面板，製作者可以用下滑安排節奏。
- 官方編輯經驗建議同一手機視窗最多約兩個面板，讓讀者有空間欣賞畫面。
- 面板寬度、形狀與高度應有變化，以表現重要性和衝擊力；關鍵揭露可用 impact panel。
- 同一場景的面板之間可用約 200px 作為起點；地點或場景切換可留約 600–1000px 的空間來表示時間／空間經過。
- 對話框宜少而短，教材給出的經驗值是每格三個以下；標準文字常見約 12–30px，但實際值取決於畫布與字型，必須在手機上驗證。
- WEBTOON 也提醒縱向媒介應保持全篇畫風一致，並選擇自己能長期維持的畫風。

這些數字是官方的編排經驗，不是所有平台、裝置或作品的硬性規格。它們應被存成可調的 baseline，例如 `gap_class: beat` 對應一個初始值，再以目標手機視窗檢查；不能只把 200px 當作任何解析度都正確的常數。

WEBTOON 的 [Creator Academy 下載資源頁](https://www.webtoons.com/en/creators101/webtoon-academy/resource-list?resourceType=DOWNLOAD_RESOURCE) 也把 handbook、character sheet、character design 和 publish checklist 放在同一套官方前置流程裡。這支持把角色表與畫風表放在分鏡之前，而不是生圖之後才補救。

### 1.2 官方繪圖工具教材的敘事與分鏡規則

[Clip Studio Paint：Effective Storytelling and Design Tips for Comics, Manga, Webtoons](https://www.clipstudio.net/en/comics-manga/design-tips/) 是官方教學，雖然是工具廠商教材，內容對分鏡設計很直接：

- 在畫 storyboard 前先回答：本段／episode 的起點和終點是什麼、途中要顯示哪些事件、讀者如何從一格移到下一格、最後一格如何引向下一段。
- 靜態漫畫要表現動作時，使用 anticipation → action → reaction；這個方法不只適用打鬥，也可用於一般情緒和喜劇節拍。
- 背景可以交代角色所在位置和場景改變；常駐地點要先畫 room layout 或建立參照，維持門、家具和空間關係一致。
- 手機 webtoon 的背景不必每格同樣精細，角色和文字重要時可簡化背景，讓焦點清楚。
- 對話框應在 storyboard 階段先放粗略位置，避免完稿後蓋住臉或動作；官方也建議用 webtoon preview／手機預覽檢查閱讀節奏。

這些內容的可借用部分是「用讀者路徑與動作因果組織分鏡」。它沒有證明任何 AI 模型能自動完成這些判斷，因此本專案要把它們變成 Codex 的顯式欄位與人工審核閘門。

[Tapas 的 Dialogue 101 官方創作者教學](https://tapas.io/newsfeed/183) 針對 scrolling、digital-only、panel-by-panel 閱讀，提醒字要在小螢幕上可讀，並讓氣泡樣式全篇一致；它也建議氣泡路徑清楚，文字要和畫面共同帶領讀者。這可作為文字 QC 的補充來源，不能把 Tapas 的 18pt 建議直接當成 WEBTOON 或 Qwen 圖像中的固定像素值。

### 1.3 既有 OSS 專案：可借用的資料中間層

以下讀的是專案自己的 README／source，因此它們證明的是「這些專案實際設計了什麼」，不代表其生成品質已被本專案驗證。

| 專案 | 一手來源觀察 | 可借用 | 明確限制 |
| --- | --- | --- | --- |
| [Codex Novel-to-Comic Studio](https://github.com/lhfer/codex-novel-to-comic-studio) · [image task builder](https://github.com/lhfer/codex-novel-to-comic-studio/blob/main/TOOLS/novel_to_comic/image_tasks.py) | 把小說流程拆成 narrative/visual bible、story-first plan、page script、storyboard、director brief、image task、QC；README 要求保存讀者已知／新知／未解問題、不可省略的因果、source span 和 references。 | `source_spans`、reader-state ledger、visual bible、director brief 和 image task 的交接方式。它的「story first, page count second」特別適合改成「episode/segment first」。 | 原本以 manga/page 與 PDF/CBZ 為目標，預設 task 有 A4/頁面尺寸，沒有手機視窗、scroll gap 或 reveal 欄位；不能直接當作 webtoon schema。 |
| [AI novel2script](https://github.com/Axelxrd/ai-novel2script) | 將小說拆成幕、場景、動作、對白、轉場；每場有戲劇目標、衝突、轉折，並生成 story bible、coverage 與修訂清單。 | 在小說與視覺分鏡之間加入 `objective / conflict / turn / adaptation_report`，避免把段落摘要誤當成可拍攝的畫面。 | 工具產生的是 screenplay YAML 初稿，不是網漫分鏡，也不處理面板高度、空白距離、視窗揭露或圖像參照。 |
| [Agent Mangaka Forge](https://github.com/RemiPelloux/agent-mangaka-forge) · [img-memory contract](https://github.com/RemiPelloux/agent-mangaka-forge/tree/main/img-memory) | README 的規則是 recurring character version 沒有必要參照圖就不能做 final page；每個版本建議 portrait、full-body、turnaround、expression、pose 等 reference，並把 base/variant/evolution 分開、不得覆寫 base。 | 版本化角色、identity markers、角色／地點／道具資產群組、缺參照就停的 pre-generation gate。 | 這是 Codex skill 和 metadata helper；helper 管理資料夾與 metadata，不負責證明圖像模型能保持一致，也不是 Qwen adapter。 |
| [ComfyUI Storyboard](https://github.com/colorAi/comfyui-storyboard) | 提供 shots grid、camera angle/zoom、prompt node、save node、可選 reference image node、順序批次執行和 SQLite 保存。 | 當 ComfyUI 端的 shot ledger 或預覽工具；把本研究的 panel camera／reference 欄位映射到 workflow。 | 它是 shot/workflow 管理介面，不分析小說，也不理解 webtoon scroll rhythm、scene gap 或角色 canon；README 的 reference node 是可選單張節點，不能假設它已支援 Qwen 多參照。 |
| [manhwa-forge](https://github.com/JesseRWeigel/manhwa-forge) | Alpha 原型以 4-beat arc（setup、inciting incident、rising action、climax + hook）產生 `script.json`，每個 panel 有 scene、description、characters、dialogue、caption、framing、mood，最後把 panel 垂直堆成長條；角色視覺描述會注入每個出場 panel，seed 與設定寫入 manifest。 | episode beat sheet、`what the reader sees` 的 panel description、frame/mood 欄位、每 panel 可重跑、長條組合與 manifest。 | 明確是 alpha proof-of-concept，綁 ERNIE-Image-Turbo／本地服務，沒有 Qwen 參照圖條件，也沒有證明 4-beat 或文字嵌圖品質適合長篇作品。 |
| [MangstoonAI](https://github.com/jays0606/mangstoon_ai) | `decompose_story()` 把故事轉成含人物、場景、對白、camera angle、mood 的 22-panel JSON；各 panel image 以 9:16 生成並輸出 scroll 格式，另支援單格自然語言修改。README 把全批 panel 生成設計成平行呼叫。 | panel schema、逐格編輯、固定身份描述與可變 outfit 欄位的分離。 | 固定 22 格並行生成，不足以證明小說改編品質或跨格連貫；使用 Gemini 圖像服務，不是 Qwen adapter。平行生成也可能讓需要前後狀態的分鏡缺少序列控制，需本案自行保留順序與 continuity state。 |
| [BoredComic](https://github.com/youvandra/bored-comic) | README 定義 `layoutMode: webtoon` 為 full-width panels stacked vertically，保存 character、series、seed 和可修訂單頁；其 pipeline 會另行合成 panel frame、balloon、SFX、narration。 | 把 panel 圖、lettering、SFX、strip 組合成可驗證的後置層；`series`、`character` 和 `revise one page` 的資料概念。 | 服務透過付費 MCP 使用，預設 Cloudflare Flux；README 自己承認 Flux 沒有 reference-image conditioning、角色一致性只是 heuristic，不能作本專案依賴。 |

共同結論：沒有一個候選專案同時解決「小說改編判斷、webtoon 垂直節奏、Qwen 多參照、跨章連續性」。可組合的是資料契約，不是整套自動化產品。

## 2. 網漫分鏡和傳統翻頁分鏡的核心差異

| 設計單位 | 翻頁漫畫 | 手機縱向網漫 |
| --- | --- | --- |
| 閱讀單位 | 一頁或跨頁；讀者一次看到較大版面 | viewport 逐步曝光的 segment；下一個畫面在下滑後才出現 |
| 讀者路徑 | 頁內格線、左右／右左閱讀和翻頁 | 固定向下，靠 panel order、氣泡路徑、面板寬高和空白控制速度 |
| 空白 | 主要是 gutter 和頁邊 | 空白是時間、停頓、心理距離、場景切換和 reveal 的主動敘事元素 |
| 面板 | 可用密集網格同時交代多個事件 | 通常讓一至兩個重要畫面佔據視窗；窄格是快速反應，寬格／hero panel 是重點 |
| 揭露 | 翻頁後的驚訝常是頁尾到下一頁 | 把物件、臉、空間或答案放到下滑後才完整出現；前一格可只給局部或輪廓 |
| 交付 | 頁面、PDF、CBZ | 一條長 scroll，或依平台切成固定寬度片段；切片不是分鏡本身 |

因此「六張 2:3 圖加大一點間距」只能是初步排版。真正的 webtoon storyboard 必須保存一個 panel 對應哪個手機視窗、哪個資訊在下滑前被隱藏、gap 要表達什麼，以及這個 segment 對下一個 segment 產生什麼期待。

## 3. 小說應如何改寫成可視的網漫節拍

### 3.1 先寫 episode promise，再切畫面

每一章先形成一個可驗收的句子：

```text
讀者在本集開始時相信 X；下滑過程看到角色因 Y 做出 Z；結尾必須留下問題 Q。
```

接著只保留能改變讀者狀態的事件。每一段小說要進入下面的 adaptation ledger，而不是直接變成 panel：

| 欄位 | 問題 |
| --- | --- |
| `source_spans` | 這個 beat 由原文哪一段支持？ |
| `narrative_function` | 建立角色、因果、笑點、情緒轉折、空間規則還是 cliffhanger？ |
| `reader_knows_before` | 進入 segment 前讀者已知什麼？ |
| `new_reveal` | 下滑後才揭露什麼？ |
| `reader_question_after` | 這一段留下的下一個問題是什麼？ |
| `visual_action` | 讀者可以看見的行為、物件變化、構圖或環境反應是什麼？ |
| `caption/dialogue/sfx` | 哪一小句文字真的增加資訊或喜劇效果？ |
| `omit/combine_reason` | 省略或合併了哪些敘述，為什麼不傷害因果？ |

這個 ledger 保留小說來源的可追溯性，也允許改編，而不是把「每句原文都有一個 caption」誤當作完整性。

### 3.2 把內心敘述轉成可視證據

本專案的主角是用誇張日記語氣描述自己，因此很適合使用「旁白自稱」和「身體證據」之間的反差。下表是第 1、2 章的具體轉換方向：

| 小說敘述 | 網漫可視化 | 文字只保留的功能 |
| --- | --- | --- |
| 「世界是黑的」 | 幾乎全黑的窄視窗；鬍鬚先碰到左、右、前、後的紙板；讓下一格在下滑後才確認是盒子 | 一句短 caption 或完全留白，建立感官限制 |
| 「空氣裡是陌生味道」 | 鼻尖、鬍鬚與透氣孔的 close-up；用氣流和色彩暗示來源，之後以紙板材質補足空間 | 只留會改變讀者判斷的氣味線索 |
| 「精神狀態：極其冷靜」 | 文字保持莊嚴，耳朵壓平、身體貼牆、後腳打滑；反差本身就是笑點 | caption 不重複解釋身體已經說出的恐懼 |
| 「正在戰略分析」 | 用四面牆、圓孔、爪子測距、頰囊物資等畫面讓分析可被看見 | 保存角色的自大命名或一次性 punchline |
| 「外面的世界更大」 | 先是盒角細縫的一條橘光，再是模糊色塊，再在較大間距後揭露透明堡壘 | 留下「外面世界」與「新牢獄／王座」的對照 |
| 「本鼠很好奇」 | 耳朵轉向牆、停住、貼耳；下一格用敲擊節奏，最後才給讀者問題 | 只保留最後的內心承認，避免旁白搶走懸念 |

可重用的轉化規則如下：

1. **感覺 → 身體和環境反應**：氣味用鼻子、鬍鬚、視線、氣流和來源物件；聲音用耳朵方向、停頓、震動和 SFX；恐懼用姿勢、距離與遮蔽物。
2. **抽象判斷 → 可觀察操作**：把「分析」改成觸摸、量距、試咬、回頭確認、儲藏、遮門；把「孤獨」改成空間中只有一個小身影與遠處聲音。
3. **情緒 → anticipation / action / reaction**：先給準備或誤判，再給動作，最後給身體或環境反應。笑點通常落在 reaction，而不是把笑點完整解說在 caption 中。
4. **世界觀 → 物件與尺度**：用透明牆、供品碗、飲水球、木屋和滾輪的穩定布局來建立天空之城，不要每格重寫設定。
5. **旁白 → 讀者狀態轉換器**：只保留角色觀點、反差、必要因果、時間跳躍或不能由圖像推斷的資訊。來源原句可列在 `source_spans`，不必全部印到圖中。

### 3.3 建議性 thumbnail 示例：第 1 章「黑暗盒中醒來」

以下只示範「把小說改成下滑節奏」的思路，是**建議性 thumbnail，非定稿分鏡，也不是可直接送給 Qwen 的 prompt**。它把開頭的感官敘述壓成六個有變化的 scroll beats；原文其餘氣味、材質和自我辯解先放進 source ledger，等 Codex 審核後再取捨。

| 下滑順序 | thumbnail 中讀者看到什麼 | 文字處理 | 空間與揭露 |
| --- | --- | --- | --- |
| 1 | 幾乎全黑的窄長格；只有一點鼻尖、鬍鬚和微弱呼吸，讀者還不知道在哪裡 | 留一句短 caption：`本鼠醒來的時候，世界是黑的。` | `episode_open`；黑色不是裝飾，而是限制視線 |
| 2 | 鬍鬚向左碰壁；下一小格向右碰壁；倉鼠身體被迫轉向 | 把 `左邊。牆。右邊。牆。` 分成兩個短 caption，前後不重複解釋 | `beat` gap 較窄，讓讀者感到連續碰撞 |
| 3 | 低角度顯示前後也都是紙板，頭頂只有幾個圓孔；倉鼠伸爪摸地 | `前面。牆。後面。還是牆。` 可縮成一個 caption：`六面封閉。` | 讓圓孔只先露局部；下滑後才看清盒頂，形成小 reveal |
| 4 | 爪子壓過平滑、冰冷、微粗糙的底板；材質特寫佔一個 viewport 的中段 | `紙盒。` 單獨保留，作為第一個判斷落點 | `hold` gap 比前面長一點；讓讀者和主角同時完成推理 |
| 5 | 倉鼠挺直身體、假裝記錄，右頰囊的葵花子微微鼓起；背景仍是盒內黑 | 把長段「稍微冷靜分析」壓成：`隨身物資：葵花子一枚。精神狀態：極其冷靜。` | 不再畫一格格說明收容所歷史；用物資和姿勢建立角色喜劇 |
| 6 | 最底部才出現盒外的模糊亮色縫隙，但不揭露人或店；倉鼠的鬍鬚朝向光 | `本鼠決定把這段經歷記錄下來。` 可留作結尾 caption；其餘日記格式延後 | `reveal_delay` 大於普通 beat，下一個 segment 才揭露綁架者；讀者帶著「外面是什麼」繼續下滑 |

這個示例的重點是：`黑暗 → 觸碰 → 推理 → 角色自我包裝 → 光的局部揭露`，而不是把原文六段各配一張圖。若手機預覽發現第 2、3 格同時可見、碰撞不夠快，可以縮小 gap；若第 6 格一出現就能看見完整寵物店，則應裁掉或延後，因為它破壞了下一段的揭露問題。

### 3.4 段落到 panel 的切法

每個 panel 應至少造成一個可驗收的變化：新資訊出現、角色姿勢改變、物件狀態改變、空間位置改變、讀者問題被改寫，或笑點／情緒落地。若兩個 panel 之間沒有變化，應合併；若一個 panel 同時塞入五個事件，應拆成 scroll beat。

panel 描述應寫「讀者看到什麼」而不是「模型要畫好看的圖」：

```text
錯誤方向：畫一張可愛、電影感、細節豐富的倉鼠漫畫。

可驗收方向：
  - 低角度；紙盒內只見倉鼠的鼻尖和鬍鬚；左壁、右壁和盒頂形成封閉感。
  - 下方只露一條透氣孔的光；不顯示盒外完整場景。
  - 耳朵先平貼，右頰囊仍有條紋葵花子；不加入衣服、字牌或其他倉鼠。
  - caption 只放核准的一句；文字位置留在圖像安全區。
```

## 4. 垂直下滑 storyboard 的實作規則

### 4.1 以手機視窗而不是頁面為主

- 每個 episode 有 `target_width`、`preview_viewports` 和 `scroll_length_estimate`；不要用 `page: 1..6` 代表敘事節拍。
- 以 360×800、390×844 等實際手機比例做預覽。WEBTOON handbook 的「最多約兩格同時可見」是節奏起點，不是每段都必須只放一格。
- 同一場景的 `gap_class: beat` 可以從 200px 左右開始；`gap_class: hold` 或笑點／恐懼停頓可加大；`gap_class: scene_transition` 以 600–1000px 的官方基線試排，再用手機閱讀修正。
- gap 必須有語義：`beat`、`reaction_hold`、`reveal_delay`、`time_passage`、`scene_transition` 或 `cliffhanger`。沒有語義的巨大空白是版面事故。
- 面板高度／寬度要變化：`peek`、`narrow`、`half_view`、`full_view`、`hero`；重要揭露可用 full-width hero，快速反應可用窄格。不要將五個固定 2:3 頁面改名成五格。
- 用角色視線、動作方向、氣泡順序和由上到下的物件連線引導閱讀；在同一 segment 內可以用重疊或無框邊界，但過多會使順序不清。

### 4.2 cut / reveal / composition 欄位

每一格至少指定：

- `cut`：establishing、insert、action、reaction、match_cut、hold、reveal 或 impact。
- `camera`：距離、角度、焦點、主體在畫面哪個區域；不要只寫 close-up。
- `composition`：前景遮擋、視線方向、可見與不可見區域、safe zone、是否貼滿寬度。
- `reveal`：下滑前可見的部分、下滑後新出現的部分、讀者應先猜什麼。
- `panel_height` / `width_class`：用邏輯類別加可選像素值，避免硬綁某一平台。
- `text_safe_area`：文字和氣泡不能遮住眼睛、關鍵物件、動作落點或下一格的揭露。

### 4.3 文字與後置排版

Qwen Image 2.1 具有文字生成能力，但目前專案實際輸出的章節備註已記錄繁中嵌字錯誤。對一部要連載的網漫，建議把 `exact_text` 和畫面分成兩層：模型生成無字／留氣泡安全區的圖，之後由 compositor/letterer 用已核准字型放置文字；若仍讓模型嵌字，就必須保存 exact text、逐字 QC，並準備該格的後置排版 fallback。這是本專案的實作建議，不是 Qwen 官方保證。

文字欄位要控制：speaker、kind（dialogue/caption/thought/sfx）、exact text、最大行數、位置、氣泡形狀、閱讀順序。旁白不是小說全文的容器；每格一至兩句短文字通常比大段 prose 更適合手機。

## 5. 角色與畫風跨章連續性

### 5.1 證據：參照圖、版本和 model API 能做什麼

[Qwen Image 2.1 官方 README](https://github.com/QwenLM/Qwen-Image-2.1#introduction) 說明模型是 text-to-image 與 image editing 的 unified model，支援最多 10 張 reference images，並聲稱可做 identity preservation；它也提供多張 `image=[...]` 的官方範例和固定 `torch.Generator(...).manual_seed(42)` 的範例。[Qwen 官方 multiple-reference 範例](https://github.com/QwenLM/Qwen-Image-2.1#image-editing-multiple-reference-images)

這證明本專案可以把 canonical character、style master、location、上一個核准 panel 等參照圖交給同一次推論。它沒有證明「多張圖一定保證角色臉、毛色、線稿或跨章畫風一致」。因此應把 reference conditioning 當成可測的控制手段，而不是無條件的品質保證。

[Diffusers 的 QwenImage21Pipeline source](https://github.com/huggingface/diffusers/blob/main/src/diffusers/pipelines/qwenimage21/pipeline_qwenimage21.py) 說明 condition images 會與 prompt 一起進入 vision context，`generator` 用來使生成具有 deterministic 可能；同一份文件也指出 `use_kv_cache` 的切換會在 reduced precision 產生可見不同的樣本，若要重現必須固定該設定。這表示可重現性至少需要固定 model weights、backend、dtype/offload、steps、seed、reference pixels、prompt、cache 設定和尺寸。

### 5.2 建議的 continuity bible

```text
series_visual_bible/
  style-manifest.json
  style-master-v001.png
  palette-and-linework.md
  characters/hamster-pudding/
    manifest.json
    versions/base/
      identity-front.png
      full-body.png
      turnaround.png
      expression-sheet.png
      pose-sheet.png
  locations/new-habitat/
    layout-topology.png
    day-light.png
    night-light.png
  props/
    sunflower-seed.json
    transport-box.json
    running-wheel.json
  accepted-panels/
    ch01-seg04-panel03-v001.png
```

每個 recurring asset 要有 stable ID、version、identity markers、禁止變動項、可變項和 hash。布丁倉鼠的禁止變動項至少包括：金棕／奶油毛色、眉間小月牙、深色圓眼、圓耳、粉鼻、鬍鬚、自然倉鼠比例、無衣服。可變項包括耳朵角度、頰囊狀態、姿勢、光線和表情，不能把「表情改變」誤登記成新角色版本。

每個 panel 的 reference bundle 建議按角色使用情境選擇，而不是把上一格無限制累積：

```text
identity_ref       固定角色身份；每次必帶
style_master       固定線稿、色盤、陰影；每個 segment 必帶
location_ref       常駐空間布局；場景內固定或按狀態切換
prop_state_ref     葵花子、紙盒、木屋等需要連續的物件狀態
previous_approved  前一格／前一章最後格；只作轉場與姿勢連續補充
```

上一章的整頁不能成為唯一 style reference，否則它的構圖、物件和偶然錯誤會被複製。每一章開始要引用同一份 style master 和角色 base，再加章節狀態；若角色真的換衣服、受傷或變形，新增 variant，不能覆寫 base。

### 5.3 固定 runtime 與畫風漂移的關係

固定 Colab session/kernel、只在啟動時載入一次 model，能消除「每章重新下載／重新初始化的權重與環境」這個變因，也使 `model_instance_id` 可追蹤。它不能取代 seed、參照圖、prompt、steps、尺寸與後置 compositing 的固定。相同 model instance 也可以因為新 seed 或不同 ref bundle 而產生不同構圖與畫風。

目前本專案的 [persistent run record](../projects/pudding-hamster/runs/2026-09-24-persistent-colab-run.md) 和兩份 manifest 都記錄同一個 `model_instance_id`，Chapter 1/2 的 manifest 都是 `model_reused: true`。但 Chapter 1 在該次驗證時是 `skipped_existing`，它的像素不是本次 instance 重新生成；Chapter 2 才是本次 instance 生成。因此目前資料可以證明 runtime 重用已工作，不能用來做「只因 model reload 才造成差異」的因果實驗。現有備註觀察到 Chapter 2 首頁紋理較粗、繁中嵌字錯誤；較合理的下一步是假設並測試 reference roles、prompt、seed、page/segment layout 和 text layer，而不是只再重載一次 model。

每次 generation manifest 最少保存：

```text
model_id / model_revision
session_name / kernel_id / model_instance_id / model_reused
backend / torch / diffusers / transformers / dtype / offload
width / height / num_inference_steps / true_cfg_scale / use_kv_cache
seed / prompt_sha256 / reference_manifest_sha256
input panel ids / output path / accepted revision
```

## 6. 可落地的 webtoon storyboard schema

下面是本專案下一版可以先由 Codex 產出、再由生圖 runner 消費的 contract 草案。它是研究建議，不修改目前的 `page_plan.json`。

```yaml
webtoon_episode:
  schema_version: "webtoon-storyboard.v1"
  series_id: pudding-hamster
  episode_id: ch01
  format:
    mode: vertical_scroll
    reading_direction: top_to_bottom
    target_platform_profile: configurable
    logical_width_px: platform_profile_value
    render_width_px: 1696
    preview_viewports:
      - {width_css_px: 360, height_css_px: 800}
      - {width_css_px: 390, height_css_px: 844}
    upload_slice_height_px: platform_profile_value
  story:
    episode_promise: "..."
    opening_hook: "..."
    ending_question: "..."
    source_spans: ["chapter-01:paragraph-001", "..."]
    adaptation_ledger:
      - source_spans: ["..."]
        narrative_function: setup|causality|comedy|reveal|hook
        reader_knows_before: "..."
        new_reveal: "..."
        reader_question_after: "..."
        visual_action: "..."
        text_kept: ["..."]
        omitted_or_combined: "..."
  continuity_in:
    style_master: "series_visual_bible/style-master-v001.png"
    character_versions: ["hamster-pudding/base"]
    location_state: "transport-box/closed"
    prop_states: {sunflower-seed: "right-cheek-pouch"}
    previous_accepted_panel: "..."
  segments:
    - segment_id: s01
      purpose: "..."
      source_spans: ["..."]
      location: "transport-box"
      reader_state_before: "..."
      reader_state_after: "..."
      next_reader_question: "..."
      gap_before_class: episode_open|beat|hold|scene_transition
      gap_after_px: 200
      transition_to_next: match_cut|time_passage|reveal|hard_cut|cliffhanger
      panels:
        - panel_id: s01-p01
          order: 1
          cut: establishing|insert|action|reaction|match_cut|hold|reveal|impact
          width_class: narrow|medium|full|bleed
          height_class: peek|short|half_view|full_view|hero
          height_px: 520
          viewport_visibility: partial|one_panel|two_panels|scroll_reveal
          camera:
            angle: low|eye_level|high|overhead|dutch
            distance: extreme_close|close|medium|wide
            focal_subject: "..."
          composition:
            visible: "..."
            hidden_until_scroll: "..."
            movement_direction: "..."
            foreground_occlusion: "..."
            text_safe_area: "..."
          action: "只寫讀者看得到的動作和物件變化"
          expression_and_body: "..."
          environment: "..."
          visual_continuity: ["identity marker", "prop state", "lighting state"]
          text:
            - kind: caption|dialogue|thought|sfx
              speaker: narrator|human-owner|null
              exact: "核准文字"
              placement: upper_left|upper_right|center|lower_safe_area
              max_lines: 2
          references:
            - role: identity_ref|style_master|location_ref|prop_state_ref|previous_approved
              path: "..."
              sha256: "..."
              revision: "..."
          generation:
            model_id: "Qwen/Qwen-Image-2.1"
            session_name: "..."
            model_instance_id: "..."
            model_reused: true
            seed: 2392402
            steps: 40
            use_kv_cache: true
          output: {path: "...", status: draft|approved|rejected}
          qc: {story: pending, continuity: pending, mobile: pending, text: pending}
```

實作時可將 `render_width_px` 保留在 Qwen 的原生 2K portrait 範圍，再由 compositor 依 `logical_width_px` 和 upload slicing 輸出；不要把 `height_px` 的 storyboard 值硬塞成每格都相同的模型畫布。若模型仍以整頁輸出，至少讓 segment 有明確的 scroll composition 和 text safe zones；若要精確控制 reveal 與 gap，逐 panel 或短 segment 生成再組合會更可控。

## 7. 驗收 checklist

### A. 故事改編

- [ ] 每個 episode 有 `episode_promise`、opening hook、ending question。
- [ ] 每個 segment 都有 source spans、reader state before/after 和 next question。
- [ ] 原文被保留、合併或省略的原因可追溯；沒有把段落逐句印成旁白。
- [ ] 每個 panel 都有一個可見變化：行為、表情、物件狀態、空間、資訊或情緒。
- [ ] 內心敘述至少有一個可視證據；caption 只補視覺無法提供的觀點、反差或因果。
- [ ] 動作／喜劇場面檢查 anticipation、action、reaction，不只列靜態姿勢。

### B. 縱向手機節奏

- [ ] 用 top-to-bottom panel order；沒有依賴翻頁或右到左的頁內格線。
- [ ] 以目標手機預覽，檢查一次看到多少 panel、文字是否需要放大、視線是否自然向下。
- [ ] `gap_class` 有語義；同場景的 gap 從 200px 基線試排，scene transition 從 600–1000px 基線試排，再以預覽調整。
- [ ] 寬度、高度和 panel type 有變化；重要揭露有 hero/impact panel，快速動作有短 gap 和 reaction sequence。
- [ ] 每個 reveal 的隱藏部分只在下滑後出現；沒有提前在上格或縮圖中洩漏答案。
- [ ] 不把六個固定 2:3 頁面直接上下堆疊當作完成；切片只在最後的交付階段做。
- [ ] 同一場景沒有無意義的巨大空白；真正的留白對應停頓、恐懼、時間或場景切換。

### C. 文字與圖像

- [ ] 只送 exact text；對話、旁白、thought、SFX 有 speaker/kind/順序。
- [ ] 氣泡不遮住眼睛、關鍵物件、動作落點或下一個 reveal；每格的字量能在手機上讀完。
- [ ] 優先使用後置 lettering；若模型嵌字，逐字比對並保留可重新排字的版本。
- [ ] 所有模型 prompt 都寫 `what the reader sees`、camera、composition、action、expression、environment，沒有只寫抽象風格形容詞。

### D. 連續性與生圖

- [ ] 角色、地點、道具都指向 canonical ID 和 version；base 不被覆寫。
- [ ] 每個 panel 帶 identity_ref、style_master，按需要帶 location／prop／previous approved；參照圖有 hash 和 revision。
- [ ] 章節內外記錄角色衣著、毛色／標記、頰囊物資、時間、光線、場景布局、道具狀態。
- [ ] `model_instance_id` 和 `session_name` 相同才可標為 model reused；kernel 重啟後視為新 session，需重新作 continuity check。
- [ ] 固定 model/backend/dtype/offload/steps/size/cache；每 panel seed、prompt hash 和 reference hash 可追溯。
- [ ] 重新生成一格不會覆蓋其他 approved panel；輸出有 `draft / approved / rejected` 版本。

### E. 最終 QC

- [ ] 從 episode 開始一路下滑，讀者不需要看原文也能理解因果和角色目標。
- [ ] 用 contact sheet 檢查整體色盤，也用手機 viewport 檢查實際節奏；兩者都通過才算通過。
- [ ] 檢查角色身份、服裝／狀態、場景拓撲、光線、道具數量和前後格動作方向。
- [ ] 檢查文字、SFX、氣泡、空白和 upload slicing；沒有亂碼、重複格、空白格、浮水印或意外新增角色。
- [ ] manifest 記錄模型、參照、seed、設定、runtime instance、輸出 hash 和人工決策。

## 8. 第 1、2 章的網漫化流程建議

這不是把既有六頁 page plan 改名，而是回到來源重新做兩集 scroll storyboard。以下節拍是建議的故事功能與揭露順序，實際 panel 數量應由手機預覽和每集節奏決定。

### 第 1 章：黑暗中的日記

1. **黑幕 hook**：先讓讀者進入主角受限的視線。黑色、鬍鬚碰牆、四面方向的短節拍逐步建立「封閉」，不要一開始就用外部 wide shot 解釋紙盒。
2. **從觸覺推理出容器**：由腳下材質、透氣孔和狹窄尺度讓讀者和倉鼠一起猜出紙盒。把「分析」畫成觸摸、嗅聞、站不直和碰壁；旁白只留角色語氣。
3. **記憶與綁架**：用明亮寵物店的短 flashback 對比黑盒；巨人臉和手以倉鼠尺度分次揭露。抓起、失去尊嚴、葵花子保住是 anticipation/action/reaction 的喜劇組。
4. **運輸中的節奏**：步行顛簸、交通工具嗡鳴、急煞車和 45 度傾斜用較密的 action/reaction panels；種子狀態每次保持可查，避免用長 caption 交代所有味道。
5. **第一道光的長留白**：急煞車後先讓紙盒穩定，給一段有意義的 `reveal_delay`；細縫的暖橘光只先露一線，再用下滑顯示外界色塊、食物氣味和天空之城。這是 webtoon 的 vertical reveal，不是翻頁 splash。
6. **結尾問題**：以透明堡壘的尺度 hero panel、半掩盒蓋的光帶和「新牢獄／新王座」的自我辯解收尾，留下「明天要進入什麼地方」的問題。第一章的最後 panel 要成為第二章第一個手部動作的 match cut 入口。

### 第 2 章：天空之城初見

1. **無縫接續**：從第一章最後的暖光帶接到盒蓋完全打開和十根柱狀物；固定 hamster base、暖光方向、盒子位置和右頰葵花子，不重新設計一個主角。
2. **捧起與落地**：手掌托起、耳朵壓平、後腿發軟是短節拍；放入透明堡壘後用「挖」作快速喜劇落點。動作場面不需要五段一樣大的格。
3. **把領地畫成可讀地圖**：先用一個 wide establishing 交代透明牆、木屑和主要設施，再按供品祭壇、生命之泉、指揮部、未鑑定設施做 inserts；同一座城的拓撲固定，讓後面的逃進木屑和夜間敲牆有空間依據。
4. **巨臉 reveal**：滾輪觀察後留一個 `hold` gap，再讓巨大的眼睛貼到牆外；倉鼠跳入木屑的 reaction 應在下一個 viewport 才完整落地，笑點由畫面和人類反應共同完成。
5. **物資喜劇**：葵花子 inventory、咬開、埋藏、頰囊超載、被看見、堵門，是一段由窄格加快到 punchline 再留白的 sequence；只保留「分散式倉儲管理」作 punchline，不把整段軍事比喻印出。
6. **夜間降速與 cliffhanger**：亮燈轉暖燈是 scene transition；用較長、乾淨的 vertical breathing space 表示第一次真正安靜。敲擊先以 SFX 節奏出現，再到耳朵定位和貼牆；最底部只回答「敲擊有意圖」，不揭露牆後生命體。

兩章共同固定的 bridge data：`hamster-pudding/base`、金棕／奶油毛色和眉間月牙、右頰葵花子狀態、透明堡壘的布局、暖色與深藍黑影、倉鼠低角度視線、第一人稱誇張冷靜旁白。這些應從 continuity bible 和 ref bundle 讀取，而不是在每個新章節 prompt 中重新自由描述。

## 9. 目前專案的下一步（只作建議）

1. 保留目前第 1、2 章圖片作為比較樣本，不把它們當成已通過的 webtoon storyboard。
2. Codex 先輸出兩章的 `webtoon-storyboard.v1` 草案，完成 adaptation ledger 和人工審核；這一步暫不呼叫 Qwen。
3. 為兩章建立一份 style master、角色 base sheet、天空之城 layout、道具 state；將 existing approved page 設為 supplementary reference，而非唯一 style source。
4. 先做一個短 segment 的 panel／gap／lettering proof，通過手機 viewport QC 後再擴成整集。
5. 將 Qwen runner 的單頁 task 逐步改成 segment task 或 panel task；每次仍沿用同一個 persistent model session，並在 manifest 驗證 `model_instance_id`。
6. 先比較「Qwen 生成無字圖 + 本地後置 lettering」和「Qwen 直接嵌繁中」兩條路徑；目前章節已有文字錯誤，不能把生成圖片直接當作可發布文字層。

## 10. 2026-09-24 實作更新

使用者開始把此 plan 落地後，原先第 9 節建議已轉為目前實作與首輪產出：

- [第 1 章 storyboard](../projects/pudding-hamster/chapter-01/webtoon_storyboard.json)：10 個 scroll segments、16 格；由暗盒醒來、寵物店回憶、綁架與顛簸旅程推到暖光和透明棲地揭露。
- [第 2 章 storyboard](../projects/pudding-hamster/chapter-02/webtoon_storyboard.json)：13 個 segments、23 格；探索食水與設施、躲巨臉、藏葵花子、夜間敲擊 cliffhanger。
- 每段保存 source spans、改編決策、reader state、reveal、semantic gap；panel 使用 Qwen art-only prompt，繁體文字由 HTML reader 排入；task builder 和 validator 已核對所有 source spans、參照與 seed 規則。
- [Colab notebook](../notebooks/Qwen_Image_2_1_Comic_Colab.ipynb) 可選 panel 寬度，預設 768 px；高度由 composition class 算出。草稿尺寸較快，通過內容審稿後才可選擇 2× Swin2SR，不重新載入或使用 Qwen 重生圖片。
- [獨立 2× 放大 notebook](../notebooks/Qwen_Webtoon_2x_Upscaler_Colab.ipynb) 已在標準記憶體 T4 smoke test。768×1152 測試格輸出 1536×2304，peak 10.11 GiB allocated／10.67 GiB reserved；放大是另一個短暫 T4 runtime，未更動兩章草稿。
- Seed 使用系列基準 `42`，有效 seed 按章號和格號固定推導；同一格重跑相同值，不同章和格不重複，manifest 留存實際 seed。
- 作者指出 39 格中倉鼠鏡頭／姿勢重複；已記錄為 novel-to-storyboard/prompt 的 camera coverage 缺陷，後續需在相鄰格明確輪換 shot size、azimuth、pitch、身體方向和動作，不把此問題歸因於 model reload。
- 現有 page-based 2:3 PNG 和原 PDF 仍是歷史 pilot 樣本。新格式兩章小圖已生成且共用同一 Qwen instance；作者尚未做最終視覺審稿。原 A100 high-RAM session 已停止。此 Colab CLI 不支援 V100，因此 Qwen CLI 的未來預設為 A100 標準系統記憶體（尚待完整生圖驗證）。
- 加速器／替代模型比較記在 [Qwen acceleration and upscaler OSS Scout report](qwen-image-acceleration-and-upscaler-oss-scout.md)。

## 來源清單（第一手）

- [WEBTOON CANVAS：新創作者資源](https://webtooncanvas.zendesk.com/hc/en-us/articles/18771041280916-What-resources-are-there-for-new-creators)
- [WEBTOON Creator's Resource Handbook PDF](https://webtoons-static.pstatic.net/creator101/en/pdf/Creators-Resource-Handbook-Updated.pdf)
- [WEBTOON Academy downloadable resources](https://www.webtoons.com/en/creators101/webtoon-academy/resource-list?resourceType=DOWNLOAD_RESOURCE)
- [Clip Studio Paint：Effective Storytelling and Design Tips](https://www.clipstudio.net/en/comics-manga/design-tips/)
- [Tapas：Dialogue 101 for Comic Artists](https://tapas.io/newsfeed/183)
- [Codex Novel-to-Comic Studio README](https://github.com/lhfer/codex-novel-to-comic-studio)
- [Codex Novel-to-Comic Studio image task source](https://github.com/lhfer/codex-novel-to-comic-studio/blob/main/TOOLS/novel_to_comic/image_tasks.py)
- [AI novel2script README](https://github.com/Axelxrd/ai-novel2script)
- [Agent Mangaka Forge README](https://github.com/RemiPelloux/agent-mangaka-forge)
- [Agent Mangaka Forge img-memory](https://github.com/RemiPelloux/agent-mangaka-forge/tree/main/img-memory)
- [ComfyUI Storyboard README](https://github.com/colorAi/comfyui-storyboard)
- [manhwa-forge README](https://github.com/JesseRWeigel/manhwa-forge)
- [MangstoonAI README](https://github.com/jays0606/mangstoon_ai)
- [BoredComic README](https://github.com/youvandra/bored-comic)
- [Qwen Image 2.1 official README](https://github.com/QwenLM/Qwen-Image-2.1)
- [Qwen Image 2.1 multiple-reference example](https://github.com/QwenLM/Qwen-Image-2.1#image-editing-multiple-reference-images)
- [Hugging Face Diffusers QwenImage21Pipeline source](https://github.com/huggingface/diffusers/blob/main/src/diffusers/pipelines/qwenimage21/pipeline_qwenimage21.py)

## 本專案的本地證據

- [現有 OSS Scout 與 deferred note](./novel-to-comic-oss-scout.md)
- [系列 README](../projects/pudding-hamster/README.md)
- [持久 Colab run record](../projects/pudding-hamster/runs/2026-09-24-persistent-colab-run.md)
- [Chapter 1 storyboard/page plan](../projects/pudding-hamster/chapter-01/page_plan.json)
- [Chapter 2 storyboard/page plan](../projects/pudding-hamster/chapter-02/page_plan.json)

# H3 / FastH3 內容對齊研究

查閱截止：2026-10-09（UTC+8）。只讀 primary source、repo 內指定參考與 `projects/midautumn-h3/final-03/README.md`；沒有下載模型、啟動 GPU、上傳或複製私人照片。以下是可操作的證據與對照邊界，不是最終架構判斷。

## Answer

要讓成片盡可能符合要求，先把「提示格式、實際模式、條件接線、驗收」固定成同一個可重現契約，再比較模型／步數。官方 H3 skill 把 T2VA、I2VA、FL2VA、L2VA 和 Ref2VA 分開；Base 的 FL2VA 是首／尾幀條件，Ref2VA 是另一個 reference transformer。FastH3 Preview v1 4-step 和 FastH3 8-Step V2 的公開 model card 都明確寫成 T2AV-only；FL2VA、Ref2VA 沒有被這些 student 蒸餾。把 shared ComfyUI 原生 Ref2VA 節點接到 FastH3 T2VA 權重，只能標成 `experimental_ref2va_ood`，不能當成參照品質保證。

原生 Ref2VA 的提示應保持六段順序：`subject_definitions`、`summary`、`retention_analysis`、`detailed_description`、`overall_soundscape`、`non_diegetic_music`。每張圖先定義用途：人物身份、服裝、場景、動作、鏡頭或具體首／尾幀；同一人原照和定裝照要明說是同一 Subject、各自提供身份或服裝。`retention_analysis` 是給模型的保留意圖，不是生成成功證據。Base prompt 對台詞使用穩定 `(S1)`、`(S2)`，依實際發聲順序跨鏡沿用，原字放在 `detailed_description` 的 `<d>` 內；`overall_soundscape` 只寫環境、物理聲和非語言聲。每個後續 shot 的 cut time 必須嚴格遞增並落在片長內。

ComfyUI native node 對 reference 的實際呈現順序是 images，再 videos（配對 soundtrack 的 `<Audio j>` 緊接在其 `<Video k>` 前），最後 standalone audio；標籤是各類別獨立的一基編號。H3 官方限制是最多 9 images、3 videos、3 audio，混合最多 12 個檔案；Comfy 還把圖片限制在不放大、最多 2048px short edge，`match` 以生成面積縮小，`max` 保留較大的 reference token 但較慢。這些是輸入／速度規格，不是「多圖一定更好」或「max 一定保臉」。

動作與道具提示要用可見的因果鏈，並把人物鏡頭、空鏡、道具鏡頭拆成能驗收的 shot：例如弓箭是「手持弓 → 單支箭搭弦 → 拉弦並朝明確方位瞄準 → 放弦 → 箭桿與羽毛沿同一方向離弦 → 命中可見位置」，同時寫初始道具數量、站位和鏡頭方向。這是基於官方要求的具體時序和本地失敗觀察形成的測試假說，不是某個詞能鎖定幾何。月面／地球空鏡則用獨立 prompt 明定可見天體、地表和攝影方向，檢查中途是否冒出人物或額外天空物件；不要用負面詞當硬遮罩。

FastVideo 4-step card 將 student 定義為 step-1300、DMD2、VSA 90% sparse、64-token tile、四次 transformer forward，並提醒困難動作、細節和部分音訊可能低於 Base；8-Step V2 則是另一個 step-1300、DMD2、VSA 80% student，使用自己的 10/3 scheduler shift 和八 forward。這支持「用配套 schedule 做對照」，不支持「4-step 必差」或「8-step 必修好」。FastVideo 現行 OmniRef PDD 文件另列 Ref2VA `transformer_ref` student，PDD-8 為 32 heads 分八塊，reference video tile 128 只走 sm100a/sm103a block-sparse kernel、沒有 Triton fallback，文件的 GB200 480×832 124-frame 例子記錄約 103 GiB device memory；因此不把它當 L4 路徑。

## Source → 操作 → 界線 → 驗收

| Source（已讀正文、revision） | 可操作控制 | 適用界線 | 成片驗收證據 |
|---|---|---|---|
| [MiniMax H3 h3-prompt-writing SKILL](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/SKILL.md)、[base-en](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/base-en.txt)、[ref-en](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt)（commit `d21241f`, 2026-08-15） | 先選模式；欄位、labels、shot timing、speaker IDs、`<d>` 和三類 sound 欄位照原格式；用具體可見／可聽細節。 | 是 prompt contract；不保證臉、衣服、物理或字幕結果。FL2VA 的 single-shot continuous path 是指南建議，不是硬控制。 | 保存最終序列化 prompt、mode、片長、shot timestamps；逐欄檢查 labels 未漂移、台詞在主時間軸。 |
| [MiniMax H3 model card](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/README.md)（revision `42ed227`, last modified 2026-08-13） | FL2VA 用 0/1/2 image；Ref2VA 以實際 references 走 separate checkpoint。記錄每張圖／片／音的 role、順序、hash、crop。 | 官方上限：≤9 images、≤3 clips（每個 2–15s、總 15s）、≤3 audio（同樣 2–15s、總 15s）、混合 ≤12 files。 | 先驗 reference manifest 和實際 loader order；輸出逐段核對身份、服裝、地標、道具初末態。 |
| [ComfyUI native H3 node](https://github.com/Comfy-Org/ComfyUI/blob/a4b5a045e56fc334903db8457b728b64e006119c/comfy_extras/nodes_minimax_h3.py)（commit `a4b5a04`, 2026-10-09）與 [官方 R2V guide](https://github.com/Comfy-Org/docs/blob/2c665405b557f2d8a36d75dfc41018ec31b18e56/tutorials/video/minimax/minimax-h3-native.mdx) | 按 node 的 images→videos→audio 順序接線；`<Picture i>/<Video k>/<Audio j>` 跟實際順序；`match`／`max` 作明確對照；有 image/audio latent 時接對應 VAE。 | 此 code path 服務原生 H3 Ref2VA；FastH3 T2VA student 接上它是 OOD。reference conditioning 每步重注入仍不是像素鎖定。 | 檢查 workflow JSON、node inputs、VAE 是否真的接上；抽取原尺寸首／中／末幀，看臉、髮型、衣領、道具幾何和空間接點。 |
| [FastH3 4-step card](https://huggingface.co/FastVideo/FastVideo-FastH3-4-step-Preview-v1-VSA-DataFree/blob/5ea076f35b84da4c3c82217112fa733d8eea2ae1/README.md)（revision `5ea076f`, 2026-09-04）與 [8-Step V2 card](https://huggingface.co/FastVideo/FastVideo-FastH3-8-Step-V2/blob/3da2ddfe1954d9cda4c05b643dc0f26007a655c5/README.md)（revision `3da2ddf`, 2026-09-15） | 各自使用其 trained ladder／scheduler／attention backend；同 prompt、references、seed、解析度、片長做有限 A/B。 | 兩 card 都說 T2AV-only；不能宣稱 FL2VA／Ref2VA 已蒸餾，也不能由 card 推導 4 必差或 8 必修。 | 同事件同影格比較 identity、action causality、prop count/direction、audio、跨段接點；記錄是否只改善某一項。 |
| [FastVideo distilled schedules](https://github.com/hao-ai-lab/FastVideo/blob/2b164405c3d15ed2d222d0582d6db09ffc5ee6b2/docs/inference/fasth3-distilled.md)（commit `2b16440`, 2026-10-07） | OmniRef PDD 只用 `MiniMaxH3Ref2VAModularPipeline` 與其 contract；保留 `transformer_ref`、PDD indices、VSA ref policy。 | PDD Ref2VA 是另一 student；tile 128 僅 sm100a/sm103a，沒有 Triton fallback，例證為 GB200 高顯存，不能視作 L4。 | 若研究 OOD，標 `experimental_ref2va_ood`；不把 native ref node 成功 decode 當 reference fidelity pass。 |
| [final-03 README](../projects/midautumn-h3/final-03/README.md)（repo evidence, 2026-09-27） | 以 original-size frame、原照、prompt／seed／model／crop manifest 驗收，不用縮圖或可解碼代替內容通過；字幕再做 ASR timing，能聽驗時補人工聽驗。 | 既有 Original50 Ref2VA 仍只有近似臉；跨段臉／髮型／衣領／腰帶／裙襬、弓箭羽毛／箭桿／來向、月面天空物件與場景有差異；不是步數因果證據。 | 逐段記 identity／garment／geometry／causality／scene／audio 六項 PASS/FAIL；格式檢查另記 fps、decoded frames、duration、32kHz stereo 和完整解碼。 |

## 建議的最小對照（留給主代理決策）

1. 先做相同 prompt／seed／片長／尺寸的 FastH3 T2VA baseline，確認 4-step 或 8-step contract、shift 和輸出格式都正確。
2. 若要測人物 reference，保留一張身份照作基線，再單獨加入定裝照；每次只改一個因素，記錄實際 order、crop、short-edge、VAE 接線。結果只支持該 seed／片段。
3. 人物與弓箭各做單人近景／道具因果短鏡；另做月面空鏡，避免把 identity、道具幾何、地球位置、背景連續性混成一個判斷。
4. 對白用穩定 S ID 和 exact `<d>`，產出後以 ASR 時間、音軌長度／解碼和可用時人工聽驗三者交叉；ASR 空白或誤詞都不能單獨證明「沒有／有」台詞。

## Uncertainty / 禁止過度宣稱

目前沒有 primary source 證明某個詞能保證原臉、裁臉必然有效、多圖必然較好、4-step 必定品質差或換 8-step 必定修好。`final-03` 的 Original50 輸出仍有上述內容缺陷；它只證明內容 QA 必須逐項做，不能反推原因。FastH3 shared Comfy Ref2VA 接線的實際畫面品質仍是 OOD 實驗，需在 report 中保留 mode／checkpoint mismatch 與未驗假說。


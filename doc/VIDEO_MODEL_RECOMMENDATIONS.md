# 影片模型搭配建議：三組效益方案與畫質優先方案

統整日期：2026-10-12。本文件整合三組效益推薦、畫質優先組合與原始量測證據。依本repo截至2026-10-11的實測，我會把 **A100／H02 Larry＋原生2×放大作為主力**，保留 **A100／H07 W6A8 Larry** 作較小權重替代，再保留 **L4／FastH3原生VSA** 作24GB GPU上的文字生片入口。

這份選擇按可用畫面、處理時間、CU、資源需求與現有workflow相容性作判斷，並非要求每種GPU各占一席，也不是全球模型品質排行榜。原始研究和2026-10-10的外部資料提供候選；後續本機實測決定本次排序。

| 選擇 | 完整搭配 | 已測規格與時間 | 保留理由 |
| --- | --- | --- | --- |
| **1．主力** | **A100 80GB＋H3 Pruned INT8＋Larry v4 step600 EMA 6步；通過原片驗收後接RealESRGAN_x2plus／CUDA FP16／tile1024** | T2V原片832×480、約5.17秒，後續中位28.45秒／名目0.0535 CU。單支I2V＋2×例子為31.63＋15.77＝47.40秒／名目0.0891 CU，交付1664×960 | 已完成T2V、首圖I2V及實際放大；本輪人物核心動作影格支持較好，速度與成本最有說服力 |
| **2．較小權重替代** | **A100 80GB＋H3 Pruned W6A8＋同款Larry EMA 6步；沿用原A100 INT8文字編碼器與影音VAEs** | 832×480、約5.17秒；後續T2V中位29.09秒／名目0.0547 CU。DiT14.89 GiB，INT8版19.53 GiB | 速度接近主力，DiT少約4.64 GiB／23.8%；有五支實際影片，可減少下載與儲存負擔 |
| **3．L4現成入口** | **L4＋FastH3 step1300 INT8 student＋NVFP4-AWQ Qwen3-VL32B＋原生VSA、4次forward** | 864×480、5秒、含音訊；兩個入口176.80／161.43秒，各200次VSA、零dense fallback | 已有可重用notebook、ComfyUI／API graph及原生kernel證據；適合手上只有L4時做T2VA |
| **畫質優先（已測流程）** | **A100 80GB＋H3 Pruned INT8＋Larry v4 EMA 6步＋原生1344×768** | 首圖I2V約5.17秒，123.31秒／名目0.2319 CU | 畫質優先的實用起點；已檢查影格支持人物動作與粗略外貌延續，尚非嚴格畫質冠軍 |

第一、二項的名目每片CU依當輪A100費率6.77 CU/h計算。第一項47.40秒只來自一支I2V＋放大案例，不是所有prompt的平均；28.45秒是後續T2V中位，兩者不混用。第三項是兩個不同入口／題目的完整工作，沒有把它們當嚴格cold/warm A/B，也沒有單片實收CU拆分。[A100測量與範圍](VIDEO_MODEL_CP_BENCHMARK.md)、[L4實測](FAST_H3_L4.md)、[原始receipt核對](#原始量測證據)

## 畫質優先時的選擇
如果要現在沿用已有實測流程，我會選 **A100 80GB＋H3 Pruned INT8＋Larry v4 EMA 6步＋原生1344×768** 作畫質優先的實用起點。首圖I2V已有約5.17秒原生768p成片，耗時123.31秒／名目0.2319 CU；已檢查影格支持轉頭、回看、微笑及粗略外貌／服裝／背景延續。LightX8原生768p也有相近的影格支持，尚無證據證明其中一組是嚴格畫質冠軍。[原生768p與成本](VIDEO_MODEL_CP_BENCHMARK.md)、[逐項影格評審](../projects/video-model-cp-20261011/quality-review.json)

選原生768p是優先產生較高解析度原片的操作建議，不是由像素數推定全面畫質勝出。Larry原生768p喝水T01曾裁掉臉／嘴；H06無Turbo的20步在手錶運鏡T03沒有實現要求，沒有全面勝過Larry的實測證據。細節、構圖、物件形狀、動作與身份仍分開驗收，不能靠增加步數或放大修正所有缺陷。

若要探索更高的畫質上限，下一個對照候選是 **A100 80GB＋原始H3 Base BF16＋原生768p＋不加少步數加速LoRA**，分階段卸載TE／DiT／VAE並核實資源。Comfy原生Base流程預設20步，官方建議可提高到25步改善motion；這是官方工作流建議，BF16／Base相對本輪Larry的優勢尚未以相同prompt、seed、解析度的本機A/B證明。[官方原生指南](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/minimax/minimax-h3-native.mdx)

目前沒有共同條件的全片播放、時間一致性、細小身份／物件幾何與畫質盲評，因此不宣稱已找出絕對最佳畫質組合。SeedVR2／FlashVSR、本輪未完成的LTX／Pro，也不直接加進「已驗最佳」組合。

## 第一項怎麼用

先生成並保存832×480原片，檢查動作、角色和道具，再用現有[streaming放大CLI](../scripts/media_upscale.py)輸出2×版本；原始音訊、fps和幀數保留。實測這一例較原生1344×768 I2V少約62%生成／後製CU，但1664×960放大與原生768p的畫質並未證明等價。[放大receipt](../projects/video-model-cp-20261011/postprocess/H02-I01-2x-t1024.mp4.upscale.json)、[本機音訊與媒體核驗](../projects/video-model-cp-20261011/postprocess/local-verification.json)

tile1024是A100／832×480來源已測設定，不能直接套到T4或更大原片。這次完成的是CLI CUDA路徑；現有Comfy放大graph／notebook只完成離線契約檢查。[放大workflow與限制](AI_UPSCALER.md) RealESRGAN_x2plus是官方原生2×的一般影像模型；影片CLI逐幀使用它，沒有時間狀態，放大後仍需檢查閃爍與新增細節。[官方model zoo](https://github.com/xinntao/Real-ESRGAN/blob/master/docs/model_zoo.md)

如果只需要480p原片，直接停在Larry生成後，約0.0535 CU的暖機T2V已是本輪最划算的通用起點。需要精確運鏡、計數、身份或聲音時，另按那些需求驗收，不能由較快推論或較大像素數推定通過。

## 第二、三項的適用界線

H07 W6A8省的是DiT檔案容量；尚未證明VRAM峰值必少4.64 GiB，整套資產也不是少23.8%。A100只測80GB／167.05 GiB主機，A100 40GB尚未驗。**H07＋較小NVFP4-AWQ TE移植L4、H07再接2×放大，都仍是新組合**，不把A100資料改稱L4成功。[模型manifest](../projects/video-model-cp-20261011/assets.json)、[平台移植評估](VIDEO_MODEL_L4_T4_KAGGLE.md)

FastH3 L4已測主機為52.96 GiB RAM，GPU取樣峰值約20 GiB；這是成功環境而非RAM最低需求。它是T2VA student。照片reference分支屬OOD實驗，65.92秒同條件cache結果不代表換prompt／照片的通用速度，也不能當正式身份保真I2V。[reference實驗](FAST_H3_REFERENCE_L4.md) L4上的FastH3＋2×組合尚未live測試，第三項先保留已驗原生480p輸出。

## 其餘研究如何處理

- **C01／標準T4：保留免費資源可用時試做。** 12.67 GiB RAM成功產出288p約5秒，三階段處理約14分鐘；抽幀有杯狀物重複／變形。按當輪1.07 CU/h估算phase supervisor約0.249 CU、安裝下載另計，未顯示付費優勢。CU歸零後仍工作約41分鐘是本輪觀察，不是免費SKU或固定時數保證。[T4實測](KANDINSKY6_LITE_T4.md) 官方免費資源與用量限制採動態政策。[Colab FAQ](https://research.google.com/colaboratory/faq.html)
- **FastH3／T4 dense：作高RAM可行性備案。** 已測約337秒／288p，但使用50.99 GiB主機；不等於免費標準RAM成功。[T4 FastH3](FAST_H3_T4.md)
- **LightX8、HyperFlow、PDD、20步原H3：按特定鏡頭需求保留。** 有些全身取景較完整，卻未提供足以取代Larry通用起點的成本／品質證據。PDD是獨立冷CLI，不與resident Larry暖機時間直接比較。[39片實測](VIDEO_MODEL_CP_BENCHMARK.md)
- **LTX、Kandinsky Pro、Bernini、Wan控制、FlashVSR／SeedVR2等：作後續比較。** 存取受阻、生成未完成或只有外部作者資料的方案，沒有足夠本機成片證據進前三。這不代表模型能力差。[原模型試用清單](VIDEO_MODEL_TRIALS_RESEARCH_20261011.md)、[較廣資源／模型調查](../research/video-resource-survey-20261010/SUMMARY_CHARTS.md)、[VSR與camera來源](../research/video-speed-camera-evidence-20261001.md)

Kaggle目前仍沒有本輪執行證據；可優先移植已測C01分階段低RAM流程或Real-ESRGAN後製，但不新增一個「Kaggle已成功」組合。圖片放大則直接沿用RealESRGAN_x2plus；anime／4×模型有各自CPU驗證，未做共同品質排名。[圖片／影片放大研究](AI_UPSCALER.md)

本次是離線統整，沒有配置GPU或消耗CU。品質判斷來自既有影格檢查，尚無完整實速播放／聽驗；前三是實用起點，成片仍需逐支驗收。

## 原始量測證據

本節整理 2026-10-09～11 的本機原始證據，不排序，也不把不同 GPU／解析度／冷暖機制合成單一分數。模型檔、版本與 reference provenance 見 [assets.json](../projects/video-model-cp-20261011/assets.json)、[source-preflight.md](../projects/video-model-cp-20261011/source-preflight.md)、[reference-lineage.json](../projects/video-model-cp-20261011/reference-lineage.json)；A100 帳務見 [cost-summary.json](../projects/video-model-cp-20261011/cost-summary.json)。

下表保留初始候選的量測證據，與前面的最終推薦用途分開解讀。

### 初始候選的原始對照

| 配置 | 實測範圍與數值 | 品質覆蓋與限制 |
| --- | --- | --- |
| **A100 H02 INT8 + Larry 6-step → RealESRGAN x2 FP16 tile1024** | 實機 A100-SXM4-80GB，79.25 GiB VRAM／167.05 GiB RAM。[hardware-probe.log](../projects/video-model-cp-20261011/hardware-probe.log) H02 T2V 為 832×480、124f、24fps、5.1667s；首個 seed42 T01 **46.81s**，同一 resident Comfy 流程的後續表定 scope（含第二 seed T01、T02–T05）中位 **28.45s**、每支 **0.0535 nominal CU**。I2V 原片 **31.63s／0.0595 nominal CU**；放大 receipt 為 124 frames、124 tiles、**15.77s**，輸出 1664×960，與原片 124f/24fps/音訊保持，故此一例合計 **47.40s／0.0891 nominal CU**。[technical-results.json](../projects/video-model-cp-20261011/technical-results.json) · [upscale receipt](../projects/video-model-cp-20261011/postprocess/H02-I01-2x-t1024.mp4.upscale.json) | H02 覆蓋 T01(seed42/3407)、T02–T05、I01；只看抽樣原生影格，T01 兩支 pass、T04 fail、其餘有 unknown，未播放／聽驗。[quality-review.json](../projects/video-model-cp-20261011/quality-review.json) 本輪只在 A100-80GB；40GB、T4 未測。 |
| **L4 FastH3 1300-step INT8 + NVFP4/AWQ TE + VSA 4-step，864×480** | Notebook receipt：864×480、模型 124f 裁輸出 120f、24fps、5.000s、32kHz stereo，**176.80s**；這是含權重初始化／解碼的首次完整入口。Comfy receipt：同規格 **161.43s**，是另一入口實跑，非同條件 warm A/B。兩支各 **200 VSA calls／0 dense fallback**；硬體為 NVIDIA L4、23,034 MiB VRAM、52.96 GiB RAM（hardware snapshot 可用 46.68–50.55 GiB），resource 最大 process-tree RSS 6.87 GiB。[notebook metrics](../artifacts/fast-h3-l4/notebook_l4_smoke_20261009T021350_9bcd99b7/metrics.json) · [notebook hardware](../artifacts/fast-h3-l4/notebook_l4_smoke_20261009T021350_9bcd99b7/hardware.json) · [Comfy metrics](../artifacts/fast-h3-l4/comfy_agent_l4_smoke_20261009T023123_4ff9db7b/metrics.json) · [Comfy hardware](../artifacts/fast-h3-l4/comfy_agent_l4_smoke_20261009T023123_4ff9db7b/hardware.json) · [resource samples](../artifacts/fast-h3-l4/comfy_agent_l4_smoke_20261009T023123_4ff9db7b/resources.jsonl) | 只取兩個玩具 prompt 各 3 個影格；粗略運動可見，音訊未聽審。Comfy 的 strength0.7 synthetic rank-2 LoRA 只證 loader/inference。整輪實際帳務 **1.33 CU**（安裝、下載、診斷及兩條成功入口合計），沒有每片 actual CU 拆分；不可與 H02 nominal per-clip CU 直接等同。[delivery/account](../artifacts/fast-h3-l4/delivery.json) 未跑 A100／T4，也未跑原 H3 GPU、L4 放大或與 T4 SR 串接。另案 Ref2VA 的同 prompt/photo/seed cache **65.92s** 不代表一般 warm L4。[benchmark](../projects/fast-h3-ref-l4/20261009/benchmark.json) |
| **標準 T4 C01 Kandinsky 6 Lite PiFlow10 FP32，3-stage／tiled VAE，512×288** | 實機 Tesla T4 SM75，14.563 GiB VRAM、12.671 GiB RAM、無 swap。[hardware-probe.log](../projects/kandinsky6-lite-t4-20261011/results/logs/hardware-probe.log) 121f／24fps／5.041667s；三個分開 stage（非單一 resident-warm 端到端）為 encode **57.54s** + sample **548.42s** + decode **176.57s** = **782.52s**，sampled GPU peak **13.741 GiB**、Comfy tree RSS **4.321 GiB**。[result-summary.json](../projects/kandinsky6-lite-t4-20261011/result-summary.json) · [288p verification](../projects/kandinsky6-lite-t4-20261011/qa/288p-verification.json) | 抽樣 frames 0,15,…,120 可見抬杯／回桌，但額外杯狀物變形，cup consistency fail；臉上緣裁切，未播放／聽驗。[288p-review.json](../projects/kandinsky6-lite-t4-20261011/qa/288p-review.json) nominal rate 1.07 CU/h 下，三階段 **0.23258 nominal CU**、supervisor **0.24903**；觀測 account debit **0.181419565 CU** 含初始 probe，生成在餘額歸零後仍繼續，不能宣稱每支 0 CU。[release.json](../projects/kandinsky6-lite-t4-20261011/runtime01/release.json) 於 **15:26:57.451306Z** 標記 released；其即時 usage 欄仍為 balance 0、名目 1.07 CU/h、1 assignment，稍後 [account-latest.json](../projects/kandinsky6-lite-t4-20261011/runtime01/account-latest.json) **15:36:27.871847Z** 確認 balance 0、0 CU/h、0 assignments。未跑 864×480、L4、Kaggle 或 T4 RealESRGAN。 |

A100 本輪整個 allocation 的 observed debit 是 **12.309842 CU**、保守 allocation estimate **12.373684 CU**（含安裝、下載、修復、推論、匯出），因此 H02 的每片數字仍是 nominal estimate，不是 account-level per-clip actual。[cost-summary.json](../projects/video-model-cp-20261011/cost-summary.json)

### 其他成功 A100 配置的可比事實

[technical-results.json](../projects/video-model-cp-20261011/technical-results.json) 的同表 A100-80GB rows：H07 6-step 832×480 中位 **29.09s／0.0547 CU**（H-W6 DiT **14.89 GiB** vs H-D INT8 DiT **19.53 GiB**，但未較快；[assets.json](../projects/video-model-cp-20261011/assets.json)）；H07 QA 覆蓋 T01×2、T02、T03、I01，T01 pass、其餘為 unknown（仍是抽樣影格）。H04 8-step **31.92s／0.0600**，production I2V **144.17s**；H05 8-step **32.38s／0.0609**，T03 影格 verdict fail；H06 20-step **71.05s／0.1336**，只覆蓋 T01–T03；A100 C01 PiFlow10 **64.41s／0.1211**（864×480），T02/T03 方向／運鏡有偏差；H01 PDD 是獨立 cold CLI，四次中位 **78.19s／0.1470**，GPU 約 4 GiB、CPU tree 約 55 GiB，不能當 resident H02 warm。對 H04/H05/H06/C01/H01 而言，這些差異、有限任務覆蓋與 frame-only QA 均不足以形成相對 H02 的明確勝勢；H01 的 cold scope 也不能與 Comfy resident time 直接比較。[quality-review.json](../projects/video-model-cp-20261011/quality-review.json) 全部 39 支仍未做連續播放／聽驗。

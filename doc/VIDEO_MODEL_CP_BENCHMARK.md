# Colab 影片模型性價比實測（2026-10-11）

**目前這批實測最划算的通用起點：H3 Comfy Pruned INT8 + Larry Turbo v4 EMA，6 步，832×480。** 後續 T2V 中位數 **28.45 秒／0.0535 CU**；人物喝水、單圖人物轉頭的已檢查影格較符合要求。需要更大交付尺寸時，採用 **480p 原片 → RealESRGAN x2plus，CUDA FP16、tile1024**；同一支 I2V 的兩段處理合計 **47.40 秒／0.0891 CU**，輸出1664×960。

這是本次 **A100 80GB**、固定題目與已查看影格範圍的操作建議。LTX 未能下載、Pro 未完成成片，不能宣稱是所有候選的總冠軍；也沒有即時播放或聽驗的流暢度／音訊品質排名。

## 可直接查看的成果

- [原始研究與完整候選清單](VIDEO_MODEL_TRIALS_RESEARCH_20261011.md)：使用者提供的文件原樣封存，當時尚無 GPU 生成。
- [可播放比較頁](../projects/video-model-cp-20261011/comparison.html)：39支原始影片與兩支2×版本，保留實際規格與耗時。
- [41支影片打包與獨立播放頁](../projects/video-model-cp-20261011/videos-and-results.zip)。
- [完整測量 CSV](../projects/video-model-cp-20261011/technical-results.csv)、[測量 JSON](../projects/video-model-cp-20261011/technical-results.json)。
- [逐片影格評審](../projects/video-model-cp-20261011/quality-review.md)、[結構化評審與證據](../projects/video-model-cp-20261011/quality-review.json)。
- [推薦 I2V 原片](../projects/video-model-cp-20261011/results/records/H02-I01-s42-sd/outputs/output/H02-I01-s42-sd/video_00001_.mp4)、[推薦2×版本](../projects/video-model-cp-20261011/postprocess/H02-I01-2x-t1024.mp4)。
- [可重送的 Larry T2V API job](../projects/video-model-cp-20261011/jobs/H02-T01-s42-sd.json)、[I2V API job](../projects/video-model-cp-20261011/jobs/H02-I01-s42-sd.json)。配套模型下載與執行修復留在[本次專案](../projects/video-model-cp-20261011/)，與既有 FastH3／H3 notebook 分開。

## 實際環境與用量

已配置一台 **NVIDIA A100-SXM4-80GB**，可用VRAM79.25GiB、RAM167.05GiB；初始可用磁碟186.85GiB。沒有取得40GB或T4的本次比較結果。Comfy固定commit `7f7fd918ed0815c5d5ef2ccfe44bfc8e72cfd217`，Python3.12、Torch2.10.0+cu130、comfy-kitchen0.2.37、SDPA，關閉dynamic VRAM與近似推論cache；保留普通節點快取。WanGP固定commit `6479db36bdc2619a904a852bba9c2d78e1a83f82`，Python3.11.14、同版Torch、comfy-kitchen0.2.35，profile4、SDPA。

使用者授權使用現有全部CU，沒有購買新額度。起始帳戶無runtime，餘額 **12.491262 CU**；配置期間費率 **6.77 CU/h**。帳戶觀測扣除 **12.309842 CU**，餘額 **0.181420 CU**；配置起點至首次伺服器確認釋放的保守估算 **12.373684 CU**，涵蓋安裝、下載、checksum、修復、生成、驗證與保存。實際扣費可能延後結算，兩種口徑分列。

**2026-10-11 10:10:51 UTC／18:10:51台北，已確認所屬allocation釋放。** 後續帳戶查核為0 assignments、0CU/h；本機QA和寫文件不延長計費區間。[成本明細](../projects/video-model-cp-20261011/cost-summary.json)、[釋放證據](../projects/video-model-cp-20261011/release.json)、[最終帳戶觀測](../projects/video-model-cp-20261011/account-latest.json)。

## 生成速度：成功的39支原片

H3：832×480，124f，24fps，5.1667s；Kandinsky Lite：864×480，121f，24fps，5.0417s。各自使用合法尺寸與時鐘，影片意圖相同，**計算量並不完全相等**。沒有prompt enhancer、插幀、face refiner或外部放大參與這張表。

| 配置 | 步數 | 首次T01秒 | 後續T2V中位秒 | 估算後續CU／支 | 成功片數含I2V/768p | 解讀 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| H02 Larry v4 EMA + pruned INT8 | 6 | 46.81 | **28.45** | **0.0535** | 9 | 通用優先；T01兩個seed皆支持核心動作 |
| H07 Larry + pruned W6A8 | 6 | 49.10 | 29.09 | 0.0547 | 5 | 權重14.89GiB，比INT8的19.53GiB小；本次未顯著加快 |
| H04 LightX2V 8step v1.0 + pruned INT8 | 8 | 48.30 | 31.92 | 0.0600 | 7 | 速度差距小；部分杯底接觸被裁切而不可驗 |
| H05 HyperFlow pruned Comfy轉檔 + INT8 | 8 | 51.70 | 32.38 | 0.0609 | 4 | T02全身取景較完整；T03運鏡弱，不等同原HyperFlow pipeline |
| H06 pruned INT8、不加加速LoRA | 20 | 75.62 | 71.05 | 0.1336 | 3 | 部分人物取景有益，成本較高；是20步對照，非官方49NFE完整基線 |
| C01 Kandinsky 6 Lite Distill BF16 | PiFlow10 | 80.48 | 64.41 | 0.1211 | 7 | 小模型不代表較省CU；T02方向／遮擋與T03運鏡偏差較明顯 |
| H01 H3 rank8 INT8 + PDD | 8 | 82.19 | 不適用 | CLI中位0.1470 | 4 | 四次獨立冷CLI流程中位78.19s；不可當成resident-model暖機速度 |

Comfy的「首次」是配置首次T01，會受到已有runtime與模型駐留狀態影響；不是每列都重建VM。後續中位數排除首次T01、I2V與production尺寸，包含T02/T03以及可用的第二seed／T04/T05。相同prompt換seed，並核對sampler實際執行，避免舊影片cache命中。時間從接受工作到server完成，含queue、lazy load、decode、save；下載和安裝不算單支生成速度，已包含在整次CU。

PDD每支啟動獨立WanGP程序，含Python、權重載入與CLIcleanup；其stdout的8步去噪約31s。profile4實測GPU峰值約4GiB、CPU process-tree約55GiB，屬大量CPU駐留／串流配置。這組結果不能證明PDD模型本身必然比Larry慢。Comfy的GPU峰值可能包含之前駐留的其他模型，不能把不同列的全GPU採樣峰值當成單模型VRAM需求。

## 原生768p與生成後放大

| 同一I01意圖／seed42 | 實際輸出 | 處理秒 | CU估算 | 範圍 |
| --- | --- | ---: | ---: | --- |
| Larry原生SD | 832×480，124f24fps | 31.63 | 0.0595 | 一張共同起始圖 |
| SD + x2，tile192 | 1664×960，同時鐘 | 31.63+84.27=115.90 | 0.2180 | 保守小tile，啟動開銷高 |
| **SD + x2，tile1024** | **1664×960，同時鐘** | **31.63+15.77=47.40** | **0.0891** | A100上每frame整張處理 |
| Larry原生768p | 1344×768，124f24fps | 123.31 | 0.2319 | 新解析度會改變latent／構圖 |
| LightX2V原生768p | 1344×768，124f24fps | 144.17 | 0.2711 | 同caption／reference |

放大模型是官方RealESRGAN_x2plus，原生2×，CUDA FP16，tile-pad16。tile192有1860個tiles，inference79.23s；tile1024只有124個tiles，inference10.84s。15.77s包括CLI載入、推論、encode及驗證，未包括首次安裝／下載。兩支本機放大檔的hash、完整解碼、frame count/fps/duration/source unchanged均通過；**解碼後音訊PCM逐byte相同**。[原始receipt](../projects/video-model-cp-20261011/postprocess/H02-I01-2x-t1024.mp4.upscale.json)、[本機核驗](../projects/video-model-cp-20261011/postprocess/local-verification.json)。

本例放大流程比原生768p I2V少約**62%**生成／後製CU，交付尺寸也不同。這是成本比較，不是等質量證明。原生與放大都可能生成不同細節，不能用更大尺寸代替動作、取景與身份驗收。原生768p T01的Larry版本反而裁切了嘴／臉，不能宣稱多花CU自動改善構圖。

```text
H3 FL2VA pruned INT8 + Larry EMA 6 steps
    -> source.mp4  (832x480; keep original)
    -> RealESRGAN_x2plus / CUDA FP16 / tile1024
    -> delivery.mp4 (1664x960; same124frames/24fps/audio)
```

既有放大CLI可直接處理原H3、FastH3及其他SDR/CFR輸出：

```bash
python scripts/media_upscale.py video source.mp4 --output delivery.mp4 \
  --model realesrgan-x2plus --device cuda --precision fp16 --tile 1024
```

模型檔已就位後才比較速度；首次另用CLI `download`。Colab notebook亦可把tile表單設1024。本次只驗了這個A100/832×480案例，不把1024固定成所有GPU、模型或大影片的通用安全值。現有native Comfy upscale graph／notebook本身仍未live執行；streaming CLI的實際CUDA路徑已驗。

## 品質證據與用途選擇

以T01拿杯→杯至嘴→放回、T02方向與遮擋、T03運鏡與物件、I01轉頭→回看→微笑為可觀察判準，記pass/fail/unknown與native frame證據。沒有把未校準主觀分數平均成單一排行榜。

- **人物／一般480p試片**：Larry兩個T01seed的核心動作較穩定，後續生成較便宜；W6A8有相近的已見外觀，可作較小權重選項。
- **人物I2V與大尺寸交付**：Larry I01的粗略臉、髮、衣服、背景與轉頭／微笑序列有影格支持；先保留SD原片，再用整frame2×放大，另驗後製版本。
- **需要全身騎車取景**：本輪PDD、HyperFlow／20步對照的T02取景較完整，值得作特定用途候選；PDD的T01取杯／喝水／同位放回也有影格支持。這些是單個seed的觀測，不能宣稱所有運動片都勝出。
- **商品、精確計數、原生聲音／對話**：未建立勝者。T03常有弱／不可量測的45°運鏡，精確dial glyph未驗；T04三次敲擊未通過；I02商品I2V及對話題未跑。

39支原片已分別作影格評審；PDD四支的粗略動作／外觀有支持，精確兩次遮擋、45°幅度及細小身份／dial細節仍保留unknown。放大版frame60靜態對照的髮絲／睫毛較銳利、臉頰更平滑，粗略幾何保留，沒有據此宣稱時間一致性改善。

I01的「left」未指定畫面與人物座標，評審只記實際方向，左右遵從unknown，保留手勢／外觀的獨立判斷。全片播放與聽驗未執行；frame-based pass不代表流暢度、between-frame flicker或音畫同步合格。可播放頁供查看原片，不把技術成功改稱正式成片放行。

## 未完成、修復與可覆核限制

**C02 Kandinsky 6 Pro Distill INT8**：31.4476GB權重實際下載及SHA驗證完成；native loader辨識mixed precision/Kandinsky6，PiFlow辨識10-step配置，已有實際取樣進度。剩餘時間給的221.9s上限設得太緊，sample節點約211.1s後被budget timeout中止，無MP4，未納入品質／成功排名。曾嘗試恢復同prompt的collector以延長保存窗口；當時queue已空、server已記interrupted，所以沒有重送生成。這是本輪時間限制，不能推定模型質量差或GPU不能執行。[metrics](../projects/video-model-cp-20261011/C02-first-metrics.json)、[history](../projects/video-model-cp-20261011/C02-first-history.json)。

LTX-2.5 L01與共享官方TE/VAE的變種：實際HEAD401、本機無HFtoken，未跑。[官方模型頁](https://huggingface.co/Lightricks/LTX-2.5)有存取／資料分享條件，本次未代接受。C03 BF16 Pro、H03 WanGP四步、其他LTX變種、Bernini編輯功能未跑，不排進榜單。

實作過的修復另記，不把原研究的靜態核對當成runtime保證：

1. Kandinsky I2V graph加入官方`Kandinsky6RemoveReferenceLatent`，再接video/audio decode；完成121f的實際I2V。
2. DeepBeepMeep/MiniMax-H3今早consolidate歷史，原`adc81...`revision失效。改固定`98b5288b174fe08f6d54f9af0dc46ee8bb58b225`；其他H01大權重SHA相同，VideoVAE改為新hash，差異保留於[revision修復](../projects/video-model-cp-20261011/H01-asset-revision-repair.json)。原研究原樣留存。
3. WanGP的decord0.6.0官方Linux wheel檔名宣告py3-none，內部WHEEL卻cp36。先核官方checksum、完整程式／native library hash、實際ctypes解碼及CPU torch bridge；只修所屬venv的WHEEL與RECORD，兩種依賴檢查再通過，程式與二進位不變。[PyPI](https://pypi.org/project/decord/0.6.0/)、[wheel格式](https://peps.python.org/pep-0427/)。
4. WanGP child使用`MPLBACKEND=Agg`；重設首次boot後出現的Deepy/enhancer預設，dry-run與實際生成時保持disabled，不修改使用者kernel的繪圖設定。

[來源核對](../projects/video-model-cp-20261011/source-preflight.md)、[實際下載manifest](../projects/video-model-cp-20261011/assets.json)、[未修改研究manifest](../projects/video-model-cp-20261011/assets-original-research.json)、下載／版本／歷史／resource證據皆在專案中。新trial runner10個focused contract tests通過，含unknown POST防重送、同key恢復、owned timeout及real-media驗證；WanGP runner另有7個CPU契約檢查與4支實際GPU影片。所有39支本機原片hash與完整解碼、兩支SR的音訊與技術檢查已核。

Production部分有背景H01下載，H07 I01有背景CPU環境安裝，因此不是嚴格隔離A/B；主要匹配SD T01/T02/T03比較在此前完成。[重疊紀錄](../projects/video-model-cp-20261011/background-work.json)。小樣本只能報本輪成功與缺陷，不建立一般失敗率；40GB、T4、長片、中文、多人物及不同kernel的速度／品質仍需自己的測試。

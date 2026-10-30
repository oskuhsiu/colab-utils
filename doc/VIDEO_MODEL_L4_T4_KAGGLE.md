# 影片模型配置：L4、T4 與 Kaggle 適用性評估

查證日期：2026-10-11。依據[原始研究](VIDEO_MODEL_TRIALS_RESEARCH_20261011.md)、[A100 的39支原片實測](VIDEO_MODEL_CP_BENCHMARK.md)、既有 FastH3 L4／T4 證據及本次官方來源核對。原離線評估階段沒有配置 GPU、生成新片或消耗 Colab CU；其後追加的C01標準T4實測見[Kandinsky6 Lite T4報告](KANDINSKY6_LITE_T4.md)。

**L4 最值得移植的原清單配置是 H07：H3 Pruned W6A8 + Larry v4 EMA 6步，搭配較小的 NVFP4-AWQ 文字編碼器；已實際成功的 L4 選項則是 FastH3 INT8 + 同款編碼器 + 原生 VSA。T4的C01 Kandinsky 6 Lite FP32分階段路徑已在標準RAM完成288p、約5秒生成；Kaggle維持移植候選，Real-ESRGAN逐幀放大仍是優先後製方向。**

H07 換編碼器、C01 改精度／卸載策略，都是新配置。A100 上的速度與品質不能直接移作這些平台的結果。

## 後續工作狀態

2026-10-11，使用者先指示「先記錄下來」，當時只完成離線記錄；其後授權在T4測C01並觀察CU耗盡。本輪新增256×256／17f、512×288／121f兩支含音訊試片，模型／解碼與本機媒體核驗完成，T4已釋放。[完整實測與品質限制](KANDINSKY6_LITE_T4.md)

後續保留：L4驗H07 W6A8＋Larry6＋NVFP4-AWQ TE；T4另驗C01原864×480／121f與其他seed；Kaggle驗Real-ESRGAN後製與C01分階段生成。這些新增規格／平台仍待實測。

## 平台條件與證據範圍

| 平台 | 顯存與精度 | 主機記憶體條件 | 對這批工作流的影響 |
| --- | --- | --- | --- |
| Colab L4 | 標示24 GB；既有實機23034 MiB，約22.49 GiB；Ada／SM89，原生BF16、FP16、FP8、INT8 | 既有實機52.96 GiB RAM；新配置須重新讀取 | H3／K6 的BF16計算方向適合；大型DiT、TE、VAE仍須分階段載入與卸載 |
| Colab T4 | 標示16 GB；既有實機14.56 GiB；Turing／SM75，沒有原生BF16／FP8 Tensor Core路徑 | 成功FastH3用的是50.99 GiB高RAM；C01新試驗使用12.67 GiB標準RAM | 本repo的H3計算契約會選FP32；不能只以「INT8權重」推定整條流程省顯存或快速 |
| 一般 Kaggle Notebook | 目前官方提供T4×2；各16 GB，兩張獨立GPU | 官方技術表列29 GB RAM、4 CPU cores；實際帳戶／session為準 | 既有單GPU graph不會自動合併顯存；RAM少於既有FastH3 Colab主機；C01另有12.67 GiB標準RAM證據 |

硬體規格見[NVIDIA L4](https://www.nvidia.com/en-us/data-center/l4/)、[NVIDIA T4](https://www.nvidia.com/en-us/data-center/tesla-t4/)。實機值來自[L4 hardware](../artifacts/fast-h3-l4/notebook_l4_smoke_20261009T021350_9bcd99b7/hardware.json)與[T4 hardware](../projects/fast-h3-t4-20261011/attempt02-result/hardware.json)，不是所有Colab session的保證。

**Kaggle P100 已於2026-09-15退役。** 官方人員表示一般Notebook目前只提供T4×2，L4限少數競賽。舊Notebook技術表仍列P100，硬體可用性以較新的[退役公告及官方回覆](https://www.kaggle.com/discussions/product-announcements/735239)為依據。若競賽真的配到L4，套用L4的模型評估，再另核對該競賽RAM及Internet條件。這次沒有登入Kaggle或觀測使用者的實際配置。

Kaggle官方頁的直接開啟回傳JS空頁；上述公告與[Notebook技術規格](https://www.kaggle.com/docs/notebooks)內容由搜尋索引取得的官方全文核對，並非本次帳戶實測。技術表列GPU session最長12小時、`/kaggle/working`最多20 GB可保存輸出，另有不保存的scratch空間；20 GB不是整台機器全部臨時磁碟的上限。GPU週額度文件寫30小時或依供需增加，應讀帳戶實際quota，不把T4×2當成自動多一倍時數。[GPU使用說明](https://www.kaggle.com/docs/efficient-gpu-usage)

## 原研究清單的配置矩陣

「候選」指有值得驗證的容量／工具條件，尚未在該平台產片。「延後」是依資源、現有證據與用途排序，不代表硬體永遠無法執行。Kaggle欄按一般T4×2、約29 GB RAM評估。

| 組合 | L4 | T4（RAM見條件） | Kaggle T4×2 | 判斷依據／必要變更 |
| --- | --- | --- | --- | --- |
| **H07 W6A8 + Larry EMA 6步** | **優先移植候選** | 高風險候選，延後 | 延後，需另設RAM策略 | L4先換H-TE4、分階段卸載；T4另驗W6A8 kernel與實際FP32計算。沒有本組合的L4／T4成片 |
| **H02 INT8 + Larry EMA 6步** | 第二H3候選 | 高風險候選，延後 | 延後 | A100通用起點最有證據，但DiT比H07大；換H-TE4仍是新配置 |
| **C01 K6 Lite 3B，PiFlow10** | **容量優先候選** | **已驗標準RAM、288p約5秒** | **優先移植候選** | T4三程序＋disk-backed dynamic loading＋FP32 block＋tiled VAE完成；處理約14分鐘，杯狀物重複／變形。Kaggle未實測 |
| H04 INT8 + LightX2V 8step v1.0 | 次選候選 | 延後 | 延後 | 可用H-TE4降低TE負擔；只有用途上的取景理由才值得加測，沒有已知容量優勢 |
| H05 INT8 + HyperFlow Comfy轉檔8步 | 特定取景候選 | 延後 | 延後 | LoRA檔較大；保留原manual sigmas／轉檔身分，不疊加Larry或PDD |
| H06 INT8，無加速LoRA，20步 | 品質對照，延後 | 延後 | 延後 | 沒有新容量優勢，步數較多；不適合作低成本移植首測 |
| H01 WanGP rank8 INT8 + PDD8 | RAM充分時再測 | RAM充分且精度另驗時再測 | **原profile4不建議原樣搬移** | 四支獨立CLI量測約55–56.4 GiB process-tree RSS；不能用約4 GiB GPU峰值宣稱適合29 GB RAM |
| H03 WanGP INT8 + LightX4 v1.2 768p | 條件候選，延後 | 延後 | 延後 | A100未跑本組合；與H01同大型TE／底模，四步不會減少權重容量需求 |
| L01 LTX-2.5 INT8 + Conv VAE，8+3 | 取得權限後，低顯存實驗 | 延後 | 延後 | 官方最低條件高於本平台；有offload工具不等於本配置保證可跑 |
| L02 L01 + Diffusion Video VAE | 排在L01之後 | 延後 | 延後 | 另有decoder成本，沒有本次成片或低顯存證據 |
| L03 LTX GGUF Q6_K；另列Q4_K_M | LTX分支的優先低容量候選 | 延後 | 延後 | Q4較小，但TE仍14.32 GiB；loader、卸載與成片須另驗，不能宣稱Q4保證16 GB可用 |
| L04 LTX mix4x8-17GB | 實驗候選，延後 | 延後 | 延後 | 檔案15.84 GiB，不是整條VRAM；混合量化kernel待驗 |
| L05 LTX單階段8步 | L01成功後再比較 | 延後 | 延後 | 仍是同大型底模／TE；在全解析度去噪，不能預先認定更快 |
| C02 K6 Pro INT8，PiFlow10 | 不列首批 | 不列首批 | 不建議起步 | DiT檔29.29 GiB，另有TE；A100試驗因時間上限中止，不是相容性失敗證明 |
| C03 K6 Pro BF16 | 不建議起步 | 不建議起步 | 不建議起步 | DiT檔56.20 GiB，完整資產約73.93 GiB；本次未產片 |
| B01 Bernini-R，WanGP高／低噪INT8 | 有影片編輯需求再評估 | 延後 | 延後 | 兩個DiT共27.07 GiB，且這不是完整TE／VAE預算；40步、沒有原生音訊，本次未產片 |

LTX官方列最低32 GB VRAM、32 GB RAM、100 GB可用磁碟。[官方系統要求](https://docs.ltx.io/open-source-model/getting-started/system-requirements) 低顯存載入器與量化可作另一條實驗路線；這些最低條件不應被解讀成「所有量化配置都不可能在24 GB跑」。本次全部LTX配置因官方TE／VAE存取權限未取得而沒有生成結果。[原次來源核對](../projects/video-model-cp-20261011/source-preflight.md)

## L4：保留成功入口，再移植Larry

**要現在沿用本repo已成功的T2V流程，選FastH3 INT8 student + NVFP4-AWQ Qwen3-VL32B + 原生VSA，4步、864×480、5秒。** 兩個入口完成時間176.80／161.43秒，200次VSA、零dense fallback，sampled整張GPU峰值約20 GiB；主機是52.96 GiB高RAM。[完整L4結果與工作流](FAST_H3_L4.md)

FastH3只蒸餾T2VA。已做的照片reference入口屬`experimental_ref2va_ood`，不能當成身份保真或原生訓練I2V的正式解法；65.92秒的同條件warm結果也不能當作換prompt／換圖的通用速度。[reference實驗](FAST_H3_REFERENCE_L4.md)

**要移植A100上Larry的T2V／首圖I2V行為，先試H07，再比較H02。** 建議新配置名稱明列`H07-L4-TE4`，包含：

- Pruned W6A8 DiT、Larry v4 step600 EMA、專用LoRA／sampler節點、6步、strength1、video/audio shift12/3。
- TE改為`qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`；不混稱原A100 H07使用的INT8 TE。
- 起步832×480／124f／24fps；BF16實際block計算；先保留Larry `low_vram=false`。
- TE編碼→DiT採樣→VAE解碼分階段卸載；必要時tiled video decode。另記VRAM、主機可用RAM與實際量化kernel。

H07 DiT檔14.89 GiB，H02為19.53 GiB；較小DiT有利於L4預留activation空間，**這是容量推論，不是已測成功或速度保證**。A100 H07沒有比H02顯著快，因此選它移植是基於容量，不是宣稱它的演算法更快。

Comfy模型作者說這款NVFP4-AWQ TE不需要Blackwell GPU；本repo的FastH3也已有L4／T4實際使用證據。[固定模型說明](https://huggingface.co/Comfy-Org/MiniMax-H3/blob/e5eb578a89295337b8ff433a035929ce0279e0b6/README.md) 這不等於NVFP4 DiT的一般硬體支援，也不證明換TE後的Larry品質不變。

先調整卸載策略；若必須開Larry `low_vram=true`，另外建立配置。該選項會從bypass改成LoRA merge，作者明示量化底模的細小更新可能因rounding變弱，不能把它當成完全相同輸出的記憶體開關。[固定節點原始碼](https://github.com/larryvrh/ComfyUI-MiniMax-H3-Turbo/blob/4274783a23afcfdbea3b4876cb79effd6c510785/__init__.py#L338)

## T4：FastH3已有288p；C01已通過標準RAM短片生成

**已驗證：FastH3同款student + TE4 + dense attention，實際DiT計算FP32，512×288、5秒。** 完整單片336.80秒、sampled GPU峰值12.47 GiB，使用50.99 GiB高RAM。這是低解析度可行性結果；沒有480p／768p或標準RAM成功證據。[T4實測](FAST_H3_T4.md)

原生Sol/VSA在實際T4回報需要SM80+；T4是SM75。固定H3 loader只列BF16／FP32，因此`--fp16-unet`不會把block計算變成FP16。直接修改模型dtype還須處理數值範圍；上游issue作者的FP16prototype曾觀測overflow／NaN，不能僅因T4支援FP16便宣布這條路徑完成。[固定H3契約](https://github.com/Comfy-Org/ComfyUI/blob/7f7fd918ed0815c5d5ef2ccfe44bfc8e72cfd217/comfy/supported_models.py#L964)、[上游實驗回報](https://github.com/Comfy-Org/ComfyUI/issues/16507)

**原清單的C01 Lite已在12.67 GiB標準RAM完成512×288／121f T2VA。** 理由是DiT只有3B，檔案5.94 GiB；但它不是5.94 GiB的完整工作流：Qwen2.5-VL7B TE檔15.45 GiB，另有影音VAE／vocoder。

K6固定Comfy實作明列BF16／FP32，不列FP16。[K6精度契約](https://github.com/kandinskylab/kandinsky-6/blob/f19c9b8ec2fcea5d391f5391983a540fc5e004da/comfyui/kandinsky6/supported_model.py#L22) 因此T4候選使用FP32 DiT，另核對VAE精度、有限數值及SDPA；FP32會增加去噪與解碼記憶體。官方上游安裝表從SM80列起，這不證明獨立的Comfy FP32／SDPA路徑一定被硬體阻擋，後續本輪已用Comfy FP32／SDPA取得T4成片；這個證據限定於已測版本與尺寸。[C01實測](KANDINSKY6_LITE_T4.md)

本輪已完成256×256／17f功能探測及512×288／121f約5秒輸出；原C01的864×480／121f仍未執行。保留PiFlow10，不改成普通Euler十步。每次降尺寸、改精度或改TE都另命名配置；先卸載並在需要時釋放TE模型，再做採樣與tiled decode。原A100 loader日誌標記FP16 TE、BF16 DiT與video VAE；本輪另用hook確認Qwen第一block及DiT觀測block輸入／輸出為FP32，權重儲存dtype混合。不能以loader旗標代替計算取證。

H07 W6A8＋Larry也可排後續研究，但其SM75量化路徑、FP32 activation與LoRA開銷都未驗，不列T4現成推薦。PDD／LightX4的WanGP版本也須先核對實際dtype和RAM，而不是只改profile。

## Kaggle：優先後製，再測小模型的低RAM配置

**目前最合理的分工是：在已驗證的A100／L4生成，將原片交給Kaggle T4做Real-ESRGAN逐幀放大。** 這是依已實測CLI和模型結構提出的移植建議，Kaggle本身尚未執行。

現有[放大CLI](../scripts/media_upscale.py)逐幀讀取，CPU保留單frame及輸出，GPU處理單個padded tile；x2plus權重約64 MiB，FP16可用，主機RAM較易控制。[流程與已做的A100 CUDA測試](AI_UPSCALER.md) 建議先用tile192，確認餘裕後再增大；不把A100的tile1024或15.77秒套到T4。生成模型退出／卸載後才開始後製。

```text
已驗證的 A100/L4 生成 -> 保留 source.mp4
                      -> Kaggle T4: RealESRGAN_x2plus / FP16 / tiled
                      -> 放大 MP4 + 原 fps/audio + 新 receipt
```

兩張T4適合分配兩支獨立影片做後製；每個程序用`CUDA_VISIBLE_DEVICES=0`或`1`、各自輸出路徑。現有CLI本身只使用一張可見GPU，沒有自動雙卡功能；雙程序安排仍需Kaggle驗證。不要同時啟動兩套大型H3流程，使有限的主機RAM更加吃緊。

若一定要在Kaggle直接生成，**原清單第一個候選是C01 Lite的分階段／FP32版本**，已有Colab標準12.67 GiB RAM完成288p的容量證據，但Kaggle尚未實測；先確認單T4、實際RAM與cgroup上限，TE階段完成後釋放大型模型物件再採樣。只把TE offload到CPU仍可能保留大量主機RAM，`--lowvram`並不保證29 GB主機能承受。另一條驗證方向是重現已成功的288p dense FastH3，但它此前是在51 GiB主機上跑，尚未證實29 GB版本。

**原H01 PDD profile4先排除原樣移植。** 四支A100冷CLI的sampled GPU約3.90–3.96 GiB，process-tree RSS卻約54.96–56.42 GiB。[取樣整理](../research/gpu-placement-20261011/local-evidence.json) RSS可能重複計共享頁，不是實體RAM最低需求測試；即使如此，它也不能支持29 GB Kaggle可行的結論。WanGP通用profile4的32 GB RAM標籤不是本H3配置成功保證；換更小TE／不同offload策略必須另驗。[WanGP profile說明](https://github.com/deepbeepmeep/Wan2GP/blob/main/run-docker-cuda-deb.sh)

模型不宜全部複製到20 GB的可保存輸出區。以已獲存取權限的input／模型資料來源或實際可用scratch放權重，`/kaggle/working`保存影片、receipt和小型設定；使用前核對磁碟與Internet狀態。本repo的Colab啟動器、`/content`路徑、下載／runtime API不會直接變成Kaggle執行器，移植的是模型graph或CLI。

## 磁碟容量：較小TE能減少多少負擔

以下由本次實際[asset manifest](../projects/video-model-cp-20261011/assets.json)的bytes加總。**是模型檔案容量，不是峰值VRAM或RAM**；另需Python／Torch、暫存下載、編譯cache及影片空間。若下載cache與目的地各保留副本，磁碟還會增加。

| 配置 | 原列資產總GiB | 改用H-TE4後GiB | 本次狀態 |
| --- | ---: | ---: | --- |
| H02 INT8＋Larry | 48.72 | 38.05 | 原列A100已產片；TE4組合未產片 |
| H07 W6A8＋Larry | 44.07 | **33.40** | 原列A100已產片；TE4組合未產片 |
| H04 INT8＋LightX8 | 49.81 | 39.14 | 同上 |
| H05 INT8＋HyperFlow | 51.63 | 40.97 | 同上 |
| H01 WanGP PDD | 49.61 | 不直接替換Comfy TE | 原列A100已產片 |
| C01 Lite完整影音資產 | **23.67** | 不適用 | 原列A100已產片；新T4分階段288p已產片 |
| L01 INT8＋Conv VAE兩階段 | 36.96 | 不適用 | 未取得共享TE／VAE存取權限 |
| L03 Q6；Q4 | 34.31；30.99 | 不適用 | 未產片 |
| C02 Pro INT8；C03 Pro BF16 | 47.02；73.93 | 不適用 | C02時間上限中止；C03未跑 |

H3原INT8 TE25.28 GiB，H-TE4為14.61 GiB，單一TE少約10.67 GiB；W6A8 DiT又比INT8少約4.65 GiB。這就是H07＋TE4優先移植L4的容量理由。**不可直接拿Comfy TE4檔替換WanGP的Quanto TE**，兩者有各自的loader、processor與權重格式。

## 性價比判斷與下一輪最小驗證

A100 H02約5秒SD原片的後續T2V中位28.45秒，費率6.77 CU/h，對應約0.0535 CU／支。先前L4 reference session觀測1.54 CU/h、T4試驗1.27 CU/h；都是歷史session讀數，新的費率要重新讀。[L4觀測](../projects/fast-h3-ref-l4/20261009/gpu-budget.json)、[T4觀測](../projects/fast-h3-t4-20261011/result.json)

```text
生成 CU = 完整單片秒數 × 實際 CU/h ÷ 3600
```

只比單片生成CU、按上述歷史費率，L4需約125秒內、T4需約152秒內，才低於A100 H02的0.0535 CU。還必須比較相當規格／品質、冷暖啟動及安裝下載攤銷。較便宜的每小時GPU不必然更划算；不能用T4的288p或FastH3 reference cache結果當成同品質480p的勝者。

本輪標準T4實際名目費率1.07 CU/h；C01的288p三階段Comfy執行782.52秒，對應名目0.2326 CU，phase supervisor含啟動／驗證約0.2490 CU，安裝下載另計。實際只扣完原有0.18142 CU，歸零後runtime仍工作，不能把名目估算當成追加實收。這支持付費生成先保留A100 H02；T4免費資源可用時適合試做，畫質需另驗。[完整用量與品質結果](KANDINSKY6_LITE_T4.md)

原驗證序列與目前狀態如下；只有C01標準T4的probe及288p約5秒已追加完成：

1. **准入**：讀GPU、SM、可用VRAM、主機／cgroup RAM、磁碟、driver／CUDA／Torch；先跑小型實際linear／attention／dtype／finite probe，再下載大模型。Kaggle單獨核對Internet、quota與scratch。
2. **L4**：新程序H07＋TE4、Larry6、832×480／124f，記實際BF16、W6A8 kernel、分階段記憶體與完整MP4；再同設定換seed跑一次，區分cold／warm。成功後才比較H02＋TE4與首圖I2V。
3. **T4**：已完成C01 FP32／SDPA的小型probe及288p約5秒影片、分程序釋放與VAE峰值；下一輪才驗864×480及其他seed。另重現已驗證的dense FastH3288p作backend參考，不混成相同模型的品質A/B。
4. **Kaggle**：先驗一支原片的tile192 FP16放大／fps／音訊／完整解碼，再測C01是否能在實際主機RAM完成。若只做移植准入，一支成功後換seed確認新採樣即可，不立即跑完整39片矩陣。
5. **驗收**：實際產片、full decode、峰值RAM／VRAM、cold／warm時間、費率或quota、動作／人物／運鏡與音訊分列。影格觀察不代替完整播放或聽驗。

本評估完成的是配置排序、條件核對與可驗證的移植方向。新H07＋TE4及Kaggle後製仍需runtime證據。後續C01 T4新增兩支試片單獨記錄，原A10039片及排名保持原樣；未把這次T4結果宣稱為嚴格跨GPU同品質排名。

完整外部來源、日期與讀取限制見[平台／kernel來源報告](../research/gpu-placement-20261011/platform-and-kernel-sources.md)；本機容量計算與資源來源見[結構化證據](../research/gpu-placement-20261011/local-evidence.json)。固定原始碼快照留於`research/gpu-placement-20261011/sources/`；原始研究與A100成片報告保持原樣。

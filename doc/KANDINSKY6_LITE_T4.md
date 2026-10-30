# C01 Kandinsky 6 Lite：Colab 標準 T4 實測

測試日期：2026-10-11。使用者要求在 T4 測試 C01，並授權使用剩餘 CU，觀察額度用完是否會斷線。這是模型可行性試驗，結果與原 [A100 比較](VIDEO_MODEL_CP_BENCHMARK.md)分開記錄。

**C01 已在標準 T4／12.67 GiB RAM 產出512×288、121幀、約5秒的含音訊影片。需要分階段載入，處理較慢，且抽幀有杯狀物重複／變形；適合低成本試做，不列為付費主力生成路線。** 本輪完成兩支試片，GPU已主動釋放；864×480、I2V、Kaggle及T4放大仍未驗。

## 配置與版本

| 項目 | 本次配置 |
| --- | --- |
| Runtime | T4／STANDARD；沒有選用 High-RAM |
| 實際硬體 | Tesla T4，SM75；Torch 可見 VRAM 14.563 GiB；主機 RAM 12.671 GiB；無 swap |
| Torch | 2.10.0+cu128，CUDA 12.8；實際支援清單含 sm_75 |
| ComfyUI | `7f7fd918ed0815c5d5ef2ccfe44bfc8e72cfd217` |
| K6 節點 | `f19c9b8ec2fcea5d391f5391983a540fc5e004da` |
| 底模 | 原 C01 Lite distill-5s，固定 HF revision 與 SHA；未替換權重 |
| 文字條件 | 原 T01 喝水提示、seed42；使用 canonical Kandinsky6TextEncode |
| 採樣 | 官方 Kandinsky6Sampler 的 PiFlow10，CFG1、denoise1 |
| Attention／載入 | PyTorch SDPA、dynamic VRAM、fast-disk、mmap、停用 pinned memory／compiler／Triton |
| 解碼 | FP32 Hunyuan video VAE，tile256、overlap64、temporal16／overlap4；原 MMAudio／BigVGAN，scaling0.417 |

完整 7 個模型資產共23.671 GiB；全部通過大小及 SHA 驗證。[資產 receipt](../projects/kandinsky6-lite-t4-20261011/results/logs/assets-C01.json) 安裝及下載805.21秒，其中下載／校驗700.59秒；這些是本輪的冷啟動耗時，不能套成一般 Colab 下載速率。

## 標準 RAM 的執行方式

```text
程序1：Qwen/CLIP -> canonical conditioning -> 存檔、有限值檢查 -> 終止
程序2：conditioning + Lite/PiFlow10 -> 影音 latent -> 存檔、有限值檢查 -> 終止
程序3：影音 latent -> tiled video VAE + audio VAE -> MP4 -> 終止
```

三個 Comfy server 分別啟動，完成後等待程序確實退出；不讓大型 TE 與 DiT 在 CPU 上同時保留。Sampler 的 positive／negative 連到同一份 conditioning，因 distilled PiFlow／CFG1 只使用 positive；沒有修改上游 sampler。模型權重使用磁碟支援的 dynamic loading，沒有把整個 TE 強制常駐 GPU。

程式、分階段 API graph、固定來源及本輪 ledger 位於 [專案目錄](../projects/kandinsky6-lite-t4-20261011/plan.json)。這是專案內獨立試驗，未修改原 A100 runner、正式 notebook 或原模型研究。

## 精度取證

啟動旗標與權重 dtype 不足以證明實際 block 計算：

- TE 啟動參數為 `--fp16-text-enc`，loader 日誌顯示 FP16；實際儲存參數包含 BF16／FP16／FP32。後續 hook 觀測 Qwen 第一個 decoder block 的輸入、mask 與輸出為 **FP32**，conditioning 為 FP32，全部有限。
- DiT 使用 `--fp32-unet`。磁碟支援載入保留 BF16／FP32 混合參數；觀測第一個 visual block 及 diffusion model 的輸入／輸出均為 **FP32**，最終 video/audio latent 全部有限。
- 原生 video VAE 日誌明示 FP32。沒有將這條路線稱為原生 BF16 或整條 FP16 計算。

Hook 覆蓋特定 block；不是每個 CUDA 算子的精度 profiler。[文字取證 metadata](../projects/kandinsky6-lite-t4-20261011/results/records/C01-T4-FP32-512x288-121-encode/outputs/output/t4-staged/C01-T4-FP32-512x288-121.conditioning.pt.json)、[最小試片 latent 取證](../projects/kandinsky6-lite-t4-20261011/results/records/C01-T4-FP32-probe17-sample/outputs/output/t4-staged/C01-T4-FP32-probe17.latent.pt.json)。

## 已完成結果

| 試片 | TE 秒 | 取樣／存 latent 秒 | 解碼／存 MP4 秒 | 狀態 |
| --- | ---: | ---: | ---: | --- |
| 256×256、17f、24fps | 58.09 | 40.68 | 21.45 | 含音訊 MP4，remote/local full decode、SHA 通過 |
| 512×288、121f、24fps | 57.54 | 548.42 | 176.57 | 含音訊 MP4，remote/local full decode、SHA 通過 |

表中時間是各階段 Comfy 提交至完成，包括該階段的 lazy load／計算／存檔；加總不是完整端到端時間，另有 server 啟動、階段驗證、下載及代理等待。最小試片三階段合計120.22秒，phase supervisor 合計200.39秒；不與原 A100 resident warm 時間直接相除。

512×288試片三階段Comfy執行合計 **782.52秒／13.04分鐘**；phase supervisor合計 **837.87秒／13.96分鐘**，另有代理調度與保存等待。單支影片是121幀、24fps、5.041667秒，音訊44.1kHz；沒有把約5秒影片生成時間寫成5秒。

其sampled GPU峰值：TE13.647／取樣13.741／解碼5.493 GiB。Comfy process-tree RSS峰值分別1.797／1.754／4.321 GiB。本次在標準RAM完成，沒有申請高RAM。

最小試片 sampled GPU 峰值：TE13.679 GiB、取樣12.272 GiB、解碼5.181 GiB。Comfy process-tree RSS 峰值分別1.785／1.763／4.371 GiB；是2秒取樣，並非 allocator 最大值或主機實體 RAM 最低需求。Kernel 讀取的 cgroup 範圍未證明涵蓋全部子程序，不以其 OOM counter 單獨判斷全機 OOM。

[最小試片 MP4](../projects/kandinsky6-lite-t4-20261011/results/records/C01-T4-FP32-probe17-decode/outputs/output/C01-T4-FP32-probe17/video_00001_.mp4) 是0.708秒功能探測，不能判定五秒喝水動作是否達成。抽幀可見藍衣、手、白杯及木桌，臉在畫面外；未做實速播放／聽驗。[本機媒體驗證](../projects/kandinsky6-lite-t4-20261011/qa/probe17-verification.json)、[影格自檢](../projects/kandinsky6-lite-t4-20261011/qa/probe17-review.json)。

## 5秒試片品質與用途

[512×288試片 MP4](../projects/kandinsky6-lite-t4-20261011/results/records/C01-T4-FP32-512x288-121-decode/outputs/output/C01-T4-FP32-512x288-121/video_00001_.mp4)、[媒體驗證](../projects/kandinsky6-lite-t4-20261011/qa/288p-verification.json)、[抽幀自檢](../projects/kandinsky6-lite-t4-20261011/qa/288p-review.json)。技術成功與成片品質分開：

- 原生影格0、15、30、45、60、75、90、105、120可見抬杯、杯靠近嘴部與放回桌面。
- 影格30／45／60，另一隻手出現額外杯狀白色物體，後續變形／消失或合併；杯子外觀一致性未通過。
- 首幀已持杯，初始桌面位置不明；同一位置放回無法確認。部分影格臉部上緣裁切。
- 未做實速播放／聽驗，不能宣稱流暢度、音效或語音內容通過。沒有做精度、解析度或tiling消融，未判定變形原因。

這支保留為試驗影片，不標為合格成品。單一提示／seed的結果也不代表模型的一般失敗率。

## CU 歸零觀察

起始帳戶餘額0.181419565 CU，無其他 assignment。先做約7.96秒的標準 T4 配置探測，回報1.07 CU/h 後釋放；再依使用者新授權重新配置同規格並繼續本次試驗，沒有購買 CU。

**首次觀測0 CU：2026-10-11 14:45:44.199 UTC／22:45:44.199 台北。當時 assignment 仍在。** 歸零後 Python 執行、模型下載、兩次 TE 編碼、最小試片的採樣與影音解碼仍成功；沒有在歸零當下立即切斷本輪 T4。API 仍回報名目1.07 CU/h，不能只據餘額0或 assignment 存在宣稱已正式轉換為某個免費 SKU。

本輪帳戶實際觀測扣除 **0.181419565 CU**，結束餘額0。2026-10-11 **15:26:57.451 UTC／23:26:57.451台北**，主代理在結果已完整保存後主動unassign；伺服器確認目標assignment不存在，沒有等待到平台強制中斷。首次讀到0至主動釋放約 **41.22分鐘**，期間完成新提交的5秒影片；這只證明本輪沒有立即因額度歸零斷線。[釋放證據](../projects/kandinsky6-lite-t4-20261011/runtime01/release.json)

名目rate×allocation elapsed在歸零後仍會增長，不當作實際追加扣費。本輪沒有購買CU。CCU帳戶彙總的rate／assignment count可能落後伺服器assignment列表，釋放以目標endpoint不存在的確認為準；後續帳戶快照另保存。[結果與用量摘要](../projects/kandinsky6-lite-t4-20261011/result-summary.json)

最終帳戶彙總在 **15:36:27.872 UTC／23:36:27.872台北** 確認 **0個assignment、0 CU/h、0 CU餘額**。這次核對在主動釋放之後，沒有延長已結束的allocation用量區間。[最終帳戶快照](../projects/kandinsky6-lite-t4-20261011/runtime01/account-latest.json)

[未快取帳戶觀測 ledger](../projects/kandinsky6-lite-t4-20261011/runtime01/fresh-budget.jsonl)、[首次歸零觀測](../projects/kandinsky6-lite-t4-20261011/runtime01/fresh-balance-zero.json)、[已執行 Python／phase 狀態](../projects/kandinsky6-lite-t4-20261011/runtime01/remote-observations.jsonl)。帳戶餘額更新有間隔，因此這是首次讀到0的時間，並非精確內部扣費時間。

本次設2小時內停止作為試驗界線。Colab 官方說免費用量與 VM 壽命採動態限制，沒有承諾固定每日2小時；也說耗盡 CU 的付費使用者回到免費政策，backend 可能因額度耗盡終止。本輪實際存活時間只適用本帳戶／allocation。[官方 FAQ](https://research.google.com/colaboratory/faq.html)


## 建議

1. **免費／低成本T4試做：** 用本次已驗的512×288、121f、PiFlow10；維持TE→DiT→VAE三程序、dynamic VRAM／fast-disk、FP32計算及tiled decode。先驗動作與物件一致性，再考慮接現有2×放大workflow；本輪未執行T4放大，放大也未證明可修正物件變形。
2. **付費生成：** 優先保留已驗的A100 H02／Larry6。按本輪1.07 CU/h名目率，C01 T4僅三階段Comfy工作就約 **0.2326 CU**，連phase supervisor約 **0.2490 CU**，還沒算安裝下載；原A100 H02暖啟動約0.0535 CU，且原生解析度較高。不同模型、解析度、冷暖啟動與品質使這不是嚴格硬體A/B，但本輪不支持「T4時租較低便更省CU」。本次生成發生在餘額0之後，這些是付費情境估算，不是額外實收。
3. **Kaggle直接生成：** C01分階段方案成為更有容量證據的優先候選。Colab標準RAM完成不等於Kaggle已驗；仍要確認driver、Torch、磁碟、Internet及實際quota。L4 H07＋TE4仍維持未實測候選。
4. **後續驗證：** 864×480／121f、不同seed、I2V及T4 Real-ESRGAN留待新一輪；本輪在使用者要求總結後保存已提交結果並收尾。

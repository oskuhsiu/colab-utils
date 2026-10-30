# Colab T4 / FastH3 實測（2026-10-11）

**結論：T4 高 RAM 配置可以用 FastH3 student 製作短片；本次成功的是 dense attention + FP32 實驗路徑。現有 pinned 原生 VSA 在 T4 上不相容。全程保守估算 0.48 CU，低於 2 CU，GPU 已釋放。**

交付：[5 秒試片](../projects/fast-h3-t4-20261011/t4-fast-h3-5s.mp4)、[抽幀](../projects/fast-h3-t4-20261011/contact-sheet.png)、[機器可讀結果](../projects/fast-h3-t4-20261011/result.json)、[本機核驗](../projects/fast-h3-t4-20261011/local-verification.json)、[成功原始封存](../projects/fast-h3-t4-20261011/attempt02-result.zip)。

## 實際條件與結果

| 項目 | 實測 |
| --- | --- |
| Colab GPU | Tesla T4、SM75、14.56 GiB 可用 VRAM |
| 主機 | High-RAM、50.99 GiB RAM、初始約193 GiB 可用磁碟；cgroup memory.max=max |
| 模型 | Kijai FastVideo FastH3 DataFree step1300、4-step INT8 ConvRot student；assets/revisions/SHA 依封存 lock 與 model-manifest |
| Encoder / VAE | NVFP4-AWQ Qwen3-VL32B、INT8 video VAE、FP32 audio VAE |
| 模型下載 | 39.45 GiB；四個檔案皆 SHA256 校驗通過 |
| 計算與 attention | DiT/block 實際 FP32；INT8 native、NVFP4 emulated；PyTorch dense，native VSA=False |
| 採樣 | Euler、timesteps `[999,749,500,250]`、video/audio shifts12/3、seed123456662 |
| 完成證據 | 四個實際 forwards、50 blocks ×4=200 block calls、finite latents/media；matching ComfyUI prompt/history |
| 成片 | 512×288、5.000秒、24fps、120幀；AAC、32kHz、stereo |
| 安裝／下載 | 300.79秒（setup）；不包含配置後的本機準備、探測與連線恢复 |
| 成功單片 | 336.80秒（約5分37秒；提交到遠端保存與完整媒體驗證，含首次載入與解碼） |
| 本機准入記錄至本機完整保存／核驗 | 376.37秒；涵蓋CLI啟動、遠端生成、封存下載與本機核驗 |
| 四次forward | 55.09, 31.94, 31.56, 31.38秒；合計 149.98秒；不把 ComfyUI 進度列重設後的速率當作完整計時 |
| Sampled 全 GPU 峰值 | 12.47 GiB；10秒取樣，可能漏掉短暫峰值 |
| Sampled process tree RSS峰值 | 10.81 GiB；不可据此聲稱標準RAM配置可用 |

成功 prompt ID：`6926cfb2-7b51-4e86-952c-48e2d5d37739`。MP4 SHA256：`160ddc0b171ea2646785ddf1566ea65acd1564524fc56799eec1609487b38f94`。

## 為何原配方不能直接跑

在真實 T4 上，FP16與BF16兩種直接 native Sol-Attn 小測皆回報 `requires sm_80+ ... cuda:0 is sm_75`。固定 [Comfy Kitchen0.2.37 source](https://github.com/Comfy-Org/comfy-kitchen/blob/v0.2.37/comfy_kitchen/backends/cuda/__init__.py#L2693) 同樣有此限制。這是該算子與 pinned 路徑的結論，不推廣到所有 FastH3 implementations。

另外，固定 [ComfyUI MiniMaxH3 dtype契約](https://github.com/Comfy-Org/ComfyUI/blob/a4b5a045e56fc334903db8457b728b64e006119c/comfy/supported_models.py#L964) 只列 BF16／FP32；量化載入會以這個契約選擇 manual cast。T4 無原生 BF16，實際選用 FP32。指定 `--fp16-unet` 僅改權重儲存精度，這次沒有把模型 block 改為 FP16。

## 嘗試與驗收

先在T4實測 FP16 SDPA、INT8 ConvRot與NVFP4 dequant/linear，小測通過後才下載大模型。初始測試腳本的 INT8 argument／NVFP4 layout API 用法曾修正，原始失敗與修正後成功資料都保留；這些 API 呼叫錯誤不計作硬體不支援證據。

第一輪 `12cc23bd-1892-47f6-8fea-5ac510af2838` 由主代理中止：預期 FP16 的實驗 receipt 與觀察到的 FP32 不符。該輪已完成三次 forward，保存在 [attempt01-interrupted](../projects/fast-h3-t4-20261011/attempt01-interrupted.zip)。修正獨立 receipt、重啟同一VM的 ComfyUI後，第二輪完整成功；沒有重新配置GPU或重下載模型。

本機核驗成功ZIP CRC、basename-only entries、prompt identity、receipt、MP4 SHA256、ffprobe frame count／尺寸／時間／音軌，以及 ffmpeg `-xerror` 全流解碼。音訊數值非靜音；未做聽驗。

主代理自行檢查 native frame0、12、24、36、48、60、72、84、96、108與119，可見紅色玩具火車沿環形木軌向右前進。尾段車頭移出右邊界，未完整維持 prompt 的全車可見意圖。本次按可行性試片放行；未做即時播放流暢度評審或聲音內容聽審。

## CU 與資源終態

- 使用者上限：2 CU；獨立 watchdog 停止門檻1.75 CU。
- 起始顯示餘額12.88 CU；終態顯示12.49 CU，觀測扣額0.39 CU。帳戶扣費更新可能有延遲，兩端顯示亦有0.01CU四捨五入。
- 實測費率1.27 CU/hr；從配置前記錄時間到伺服器unassign成功後的CLI termination event，共 1361.51秒，保守估算 **0.4803 CU**。涵蓋探測、準備、安裝／下載、連線恢复、中止與成功嘗試、產物取回及停止。
- 計費估算截止於 **2026-10-11T04:44:48.684822+00:00**；後續本機QA、報告與帳戶核對不延長此區間。
- 伺服器確認原 endpoint 不存在、assignments0、rate0 CU/hr；watchdog已退出。見 [release](../projects/fast-h3-t4-20261011/release-confirmed.json)、[final account](../projects/fast-h3-t4-20261011/final-account.json)、[budget ledger](../projects/fast-h3-t4-20261011/budget.jsonl)。

## 結論適用範圍

可重現的證據限本次4-step student、T4 high-RAM、512×288／5秒／T2VA。標準RAM、更高解析度、較長影片、照片條件與其他student未驗。Dense改變VSA蒸餾student的運算條件，這次不證明畫質與原VSA配方等同，也不構成T4／L4同條件速度比較。

原有L4 runtime guard、canonical workflows、notebooks和已安裝skills未修改；獨立實驗檔案保存在 [projects/fast-h3-t4-20261011](../projects/fast-h3-t4-20261011/)。`fast-h3-t4-toolkit.zip`保留第一輪版本，`fast-h3-t4-toolkit-final.zip`包含修正後FP32 receipt。

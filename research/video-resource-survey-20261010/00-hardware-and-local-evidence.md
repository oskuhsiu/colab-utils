# 資源口徑與工作區既有證據

查閱：2026-10-10。此檔由主代理整理；沒有配置 Colab、啟動 GPU 或重新生成影片。

## 本次範圍

使用者明定低資源為單張 **L4**，中資源為單張 **A100 + High RAM**，超出此範圍為高資源。本報告將 A100 40GB 與 80GB 分列，主機 RAM 另列；尚未取得本次實際 A100 runtime 的硬體清單，因此不假定 High RAM 一定對應特定顯存或 RAM 容量。

| ID | 已讀原始來源 | 明示事實 | 適用限制 |
|---|---|---|---|
| HW01 | [NVIDIA L4 規格](https://www.nvidia.com/en-us/data-center/l4/) | L4 名義顯存 24GB、頻寬 300GB/s；規格列出 FP8、INT8 Tensor Core。 | 名義 GB、實際可用 MiB、PyTorch allocated/reserved 各有不同口徑。規格不能直接換算影片端到端耗時。 |
| HW02 | [NVIDIA A100 規格](https://www.nvidia.com/en-us/data-center/a100/) | A100 有 40GB 與 80GB 產品；頁面列 80GB PCIe／SXM 規格。 | 產品型號不是 Colab 分配保證；多卡 A100 不屬本次單卡中資源。 |
| HW03 | [NVIDIA CUDA compute capability](https://developer.nvidia.com/cuda/gpus) | L4 為 compute capability 8.9；A100 為 8.0。 | 要另外讀各 kernel 的支援清單；相同量化檔案不代表在兩卡執行相同 kernel。 |
| HW04 | [Google Cloud GPU 比較](https://docs.cloud.google.com/compute/docs/gpus/#general_comparison_chart) | 表列 A100 40／80GB、L4 24GB；Tensor Core 表中 A100 FP8 為 N/A，L4 有 FP8。 | A100 的 FP8 權重若可載入，是否轉回 BF16／FP16、是否節省顯存，仍取決於 loader。不能套用 L4／Blackwell FP8 的速度。 |
| HW05 | [Colab FAQ：記憶體](https://research.google.com/colaboratory/faq.html#resource-limits) | High memory 指 system memory；GPU 與資源供應會變動。 | 不把 High RAM 當額外 GPU VRAM，也不填入未由實測提供的 RAM 數字。 |
| HW06 | [Google Colab CLI session management](https://github.com/googlecolab/google-colab-cli/blob/main/docs/01_session_management.md) | `--gpu A100 --high-mem` 要求 A100、`shape=hm`；L4 只有一種 shape，忽略 `--high-mem`。 | 這是請求參數與作者文件；實際分配仍需 runtime hardware evidence。 |
| HW07 | [Reddit：We finally got 80GB A100](https://www.reddit.com/r/GoogleColab/comments/1ngjhgq) | 原帖作者稱在 Colab 取得 A100 80GB，並在留言稱選了 High RAM。 | 第一手社群聲明，沒有本研究可核驗的完整 runtime 清單；不能用來保證每次分配。搜尋時間標籤與頁面相對時間不一致，精確發帖日未知。 |
| HW08 | [Reddit：FramePack 的 Colab／4090／4060 測試](https://www.reddit.com/r/StableDiffusion/comments/1lb2bbb) | `redbook2000` 報 20秒、480級 I2V：Colab L4 約80分鐘；4090 約25分鐘；4060 laptop 約90分鐘。L4 主機 RAM 約50GB，作者稱使用約6GB RAM／12GB VRAM；使用 sagiodev notebook。 | 歷史單一用戶報告，未固定 seed／steps／revision；作者將 L4 顯存寫為20GB，與 NVIDIA 名義24GB不同，統計口徑未釐清。作者對 shared machine 的因果猜測未採用。不能推論今日 FramePack 或其他模型的速度。 |
| HW09 | [sagiodev FramePack_Colab](https://github.com/sagiodev/FramePack_Colab) | 上述第一手測試直接連到此 repo，現有 `FramePack_colab_SDA.ipynb` 可作重現入口。 | 有 notebook 不等於在現行 Colab／模型 revision 通過驗證；本次未執行。 |

## 工作區 2026-10-09 既有 L4 試驗

此處是**舊的本地試驗**，不是今天重跑，也不是外部社群測試。主代理讀到兩份原始 metrics 與 hardware：

- [round03 metrics](../../artifacts/fast-h3-skill-trials/20261009/round03/round03_notebook_toycar_20261009T033057_76817ce5/metrics.json)、[hardware](../../artifacts/fast-h3-skill-trials/20261009/round03/round03_notebook_toycar_20261009T033057_76817ce5/hardware.json)
- [round04 metrics](../../artifacts/fast-h3-skill-trials/20261009/round04/generate/round04_orange_ball_lora_20261009T034455_5e82c3dc/metrics.json)、[hardware](../../artifacts/fast-h3-skill-trials/20261009/round04/generate/round04_orange_ball_lora_20261009T034455_5e82c3dc/hardware.json)

| 條件 | round03 | round04 |
|---|---|---|
| GPU／主機 RAM | NVIDIA L4，23034 MiB total VRAM；52.96 GiB system RAM | 同型 GPU、同總顯存與 RAM |
| diffusion 權重 | Kijai `minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors` | 相同 |
| text encoder／VAE | Qwen3VL-32B NVFP4-AWQ；video VAE INT8-ConvRot；audio VAE FP32 | 相同 |
| 片長／尺寸 | 864×480；124 model frames 裁 120 frames；24fps／5秒 | 相同 |
| sampling | Euler 4 steps；video/audio shift 12/3；VSA keep 10%，tile 64 | 相同 |
| 每片 total | 181.62秒 | 156.19秒 |
| VSA 記錄 | 200 kernel calls，0 dense fallback；98.6004秒 | 200 kernel calls，0 dense fallback；86.8137秒 |
| 内容／附加條件 | 紅色玩具車；無 LoRA | 橙色球；synthetic rank-2 fixture LoRA、只映射一個 target |

限制：兩片不同 prompt、seed、LoRA，不能當受控的 Notebook vs ComfyUI、LoRA、品質或 GPU 比較。`technically_valid` 僅是技術狀態。每片 total 不含安裝／模型下載；沒有同條件的 warm 重複測量。低於 2GiB 的 `peak_torch_allocated_gib` 欄位**不是完整模型顯存需求**；本研究不以它宣稱 H3 只需 2GB。動態記憶體／offload 與 CUDA allocator 的統計範圍需另測。

四個模型資產的檔案大小合計約 **42.36GB（十進位）／39.45GiB**，由 metrics 的四個 `size` 相加得出；這只是模型下載大小，不含套件、cache、暫存、輸出，也不是 VRAM 或 RAM 峰值。後續主表將「檔案大小」「載入／生成峰值」「成片品質」分開記錄。

## 統整方法

以下是本次研究的整理規則，不是來源宣称或新實驗結果。

- 每項候選保留「模型／任務 → 權重作者與 revision → 量化 → 蒸餾／LoRA → scheduler → attention backend → workflow」；來源缺哪一項就保留缺口。
- `1300step`／`2900step` 這類 checkpoint 命名中的訓練進度，與每片執行的 4／8／50 sampling steps 分欄。CFG 或模型切換可能讓 sampling steps 與實際 forward 次數不同。
- 「有 node／可以接線」「技術完成」「符合作者訓練任務」「人物／動作／聲音達標」各自記錄，不能互相替代。
- 作者只給 4090／5090／H100／B200 等結果時，保留原硬體；不按顯存容量、TFLOPS 或同 compute capability 推算 L4／A100 耗時。
- 每個耗時區分 download／load／text encode／denoise／decode／mux，來源沒有拆分則寫「口徑未說明」。區分 cold、warm、cache hit、compile 後結果。
- 成品品質關注提示遵循、人物／服裝一致、動作因果、細節、時間穩定、音畫／對白以及完整影片。漂亮的一張截圖不足以支持整片品質。
- 官方說明、權重／工具作者主張、第一手社群報告、只有搜尋摘要的線索分開。主表的「下一輪候選」是主代理初步判斷；只有可比測試能支持較強的勝負結論。

## 主代理的社群搜尋邊界

主代理另試 `site:facebook.com "L4" "Wan" video workflow`、`site:facebook.com "Wan2.2" "workflow"`、`site:x.com "L4" "Wan"`、`site:x.com "A100" "LTX" video`、`site:reddit.com "A100" "Wan" "High RAM" video generation` 等定位查詢；此範圍未得到可支持配置的 Facebook 原帖。這不表示 Facebook 沒有資料。

`site:x.com "MiniMax-H3" "ComfyUI"` 主要回傳 `/i/trending/` 多語摘要。頁面自行標示這是 Grok 彙整，因此本研究只用來定位原作者，不把其「免費無限」「12GB 可跑」「某價格／耗時」當第一手測試。已把摘要提到的作者線索交給 H3 社群 worker 追查；可讀取程度與原帖資料留在各分題報告。沒有登入、繞過群組权限或發送訊息。

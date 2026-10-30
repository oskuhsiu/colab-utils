# H3 模式、LoRA 與推理參數

選模式、換權重、映射 LoRA strength 或比較 scheduler 時讀本頁。以下原 H3 契約以 DiffSynth `7686e54d41d25c0e8ed5f1318acc23b6bb832654` 及指定權重為界；FastH3 使用另一套 [ComfyUI 契約](fast-h3-l4.md)。

## FL2VA 與 Ref2VA 的實際條件

- FL2VA 接首尾 keyframes；Ref2VA 接 references。原照只用來製作端點圖時，影片模型收到的是端點，不是原照身分 reference。
- 本地 pinned DiffSynth／notebook wrapper 的 keyframe indices 限 `0`／`-1`。pipeline 的 references 分支優先，notebook 拒絕混用，不能承諾此 wrapper 同時硬鎖 FL 首尾與原照身份。這是本 wrapper 限制：[SGLang 部署文件](https://docs.sglang.io/cookbook/diffusion/MiniMax/MiniMax-H3) 描述混合 reference 與 first/last keyframes 的另一介面；採用前另核對該框架契約。
- 原生公開 Ref 規格最多 9 圖、3 影片、混合共 12 項；實際 wrapper 可更窄。影片按 pipeline 約定取樣為 24 fps。現有 notebook 接 silent video references；影片含音軌不代表音訊已送入。
- BF16 Ref2VA 可用。Ref transformer、processor、encoder、影音 VAE 與 Ref 專用 adapter 必須相符，不能只把 FL 改標籤。量化版本另核對 loader、結構與配套元件。
- FL／Ref 共用元件以 pinned metadata 的 hash／blob id 逐檔證明；兩個 transformer 分開 inventory。

來源：[固定 H3 pipeline](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/diffsynth/pipelines/minimax_h3_audio_video.py)、[官方輸入規格](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/README.md)、[固定 Ref2VA 權重樹](https://huggingface.co/MiniMaxAI/MiniMax-H3/tree/42ed227ee7df40d41602854ae760620d6eb651fe/Ref2VA)。資產逐檔核對可用 [固定 H3 metadata](https://huggingface.co/api/models/MiniMaxAI/MiniMax-H3/revision/42ed227ee7df40d41602854ae760620d6eb651fe?blobs=true)；本地選擇函式定位見 [repo-tools.md](repo-tools.md)。

## Native Turbo 與 loader 比例

LoRA repo revision：`3ec17a324ced54151364f24f8b5fb6bf7e26414f`。表中的明確乘數只適用此 pinned DiffSynth loader：

| Native adapter | DiffSynth steps | header alpha / rank | loader 乘數 |
| --- | ---: | ---: | ---: |
| Ref2VA `minimax_h3_ref2v_turbo_4step_v0.1_bf16.safetensors` | 4 | 8 / 128 | 0.0625 |
| Ref2VA `minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16.safetensors` | 8 | 8 / 128 | 0.0625 |
| FL2VA Turbo 4-step v1.2 / 8-step v1.0 | 4 / 8 | 8 / 128 | 0.0625 |
| FL2VA Turbo 4-step v1.0 | 4 | 128 / 128 | 1.0 |

所列 Ref4／Ref8 header 有 metadata alpha=8、rank=128，沒有 per-layer tensor-alpha。MiniMax loader 轉 key 後交給 GeneralLoRALoader，此路徑 hotload 使用傳入乘數，不自動套 metadata alpha/rank，因此 0.0625 套一次。其他 loader 可能先套 alpha/rank，UI strength 再作額外倍率；映射前追蹤 native／converted keys、tensor／metadata alpha 與實際公式。

DiffSynth 這裡傳 4／8 steps；其他 scheduler 可能把零終點算入列表。比較 recipe 時以實際模型 forward 數及 endpoint 分開核對。

來源：[固定 DiffSynth LoRA loaders](https://github.com/modelscope/DiffSynth-Studio/tree/7686e54d41d25c0e8ed5f1318acc23b6bb832654/diffsynth/utils/lora)、[LightX2V 的另一 loader 介面](https://github.com/ModelTC/LightX2V/blob/4ff8267e7ca09a30dace323f3c024529de7d4a30/lightx2v/models/networks/minimax_h3/lora.py)。

## Shift 與時間格點

Ref8 發布者建議 8 steps、Euler、video/audio shift 12/3；本地 Ref4／Ref8 配置也採 12/3，但 Ref8 公告不是 Ref4 的獨立來源。[發布者原文](https://huggingface.co/lightx2v/Minimax-h3-Turbo/discussions/51) 與 [vLLM recipe](https://github.com/vllm-project/vllm-omni/blob/main/recipes/MiniMaxAI/MiniMax-H3.md#turbo-lora-artifacts) 的設定有分歧；先核對版本、scheduler、forwards 並記錄選用來源，不能從 FL 的 shift 推論 Ref。

Pinned 本地實作使用寬高 32 倍數、24 fps、32 kHz stereo。令交付影格數 `F = seconds * 24`，模型長度為 `5 + 17 * ceil((F - 5) / 17)`，輸出裁為 F 格，音訊裁為 `seconds * 32000` 樣本。模型格點與交付格數分開記錄；驗實際 decoded media，不從內部 length 推定片長。

Reference short-edge 是獨立條件編碼參數，記錄實際值與 crop；提高它可保留輸入細節，不是身份保證。Weight VRAM budget 是 offload 權重預算，不能當整卡峰值上限；activation、VAE、workspace 等另占容量。資源觀測用 [共用生命週期](../../colab-video-studio/references/runtime-monitoring.md#資源與作業生命週期)。

## 8-step 與 Original50 的有限對照

只在步數是具體疑問且試驗已授權時比較。官方 prompting 定義語法；[SGLang 指南](https://docs.sglang.io/cookbook/diffusion/MiniMax/MiniMax-H3) 的標準 Ref 請求列 50、12/3 並區分 few-step Turbo。本地 `original50` preset 是 50、12/3、LoRA=None、cfg_scale=1.0，仍須核對 kernel 實際載入設定。

先修正已知輸入／接線錯誤，再選能顯示該缺陷的支援片長或相鄰片段。A 用相符模式 Turbo8；B 用同模式乾淨 base 的 Original50，不帶 Turbo LoRA。已 merge 的 adapter 須重建乾淨 base。固定 prompt、素材 hash／順序／crop、seed、精度、尺寸與片長，記錄必要 scheduler 差異；結果僅支持此次配置與內容。多項同時變更不能隔離步數因果，相同 seed 也不保證不同 scheduler 同軌跡。此分支不是離線診斷或單輪製作的必做門檻。

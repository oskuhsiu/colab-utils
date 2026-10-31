# H3 Omni Context Windows：實驗 preset 與比較計畫

`h3-omni-context-windows` 使用原四個 Omni 權重、8-step Euler/simple、native dense attention、shift 12/3，再接 Core 的 `MiniMaxH3ContextWindows` MODEL patch。固定 ComfyUI **0.43.0／6651247a8b50cefd1436c834f704bdf7767722e9**，來源為已合併 [PR #17425](https://github.com/Comfy-Org/ComfyUI/pull/17425)。不加 Turbo LoRA／VSA gate；既有 Omni、Continuum、Ref2VA starter graph 的內容保持相同，Pika 使用其獨立路徑。

此 preset 仍是實驗功能。2026-10-31 已完成 A100 STANDARD 的 720p 直式實測：相同提示／seed 的 6.58 秒 OFF／ON 對照中，共用完整提示的 CW 版本在機器語音核對出現重複；12.25 秒、三個規則間距視窗各一句的版本，轉錄依序各一次，但第三句辨識不穩、局部疊影與實際聽驗仍有限制。詳見[歷史驗證摘要](../research/h3-context-windows-validation-20261031.md)。這不是單一因素證明或正式品質通過；下述 20／30 秒與 Continuum 比較仍未執行。Context Windows 限制每次去噪看到的時間範圍，再融合多窗；多窗也增加計算次數，不能先推定它一定更快或更連續。

## 使用入口

在 `notebooks/ComfyUI_Colab.ipynb` 將 `MODEL_BUNDLE` 與 `PRESET` 都選 `h3-omni-context-windows`。只用原生節點可停用兩個 custom-node 勾選。`RUN_API=False` 維持不生成；20／30 秒屬此實驗路徑，既有短段 Omni 仍保留 5–15 秒範圍。

Python 可先離線產生 graph 與計畫：

```python
from comfyui_workflows import build_graph, context_window_plan

graph = build_graph(
    "h3-omni-context-windows", duration_seconds=20,
    width=640, height=384, reference_image="reference.png",
    ref_image_size="match", seed=202610310074,
    context_length=124, context_overlap=39, fuse_method="pyramid",
    freenoise=True, split_conds_to_windows=False,
)
plan = context_window_plan(20, prompt_count=3, split_conds_to_windows=True)
```

未提供 prompt 時仍是範例火車提示；正式提交前須替換提示與實際 input 圖片。canonical [API starter](../workflows/comfyui_h3/h3-omni-context-windows.api.json) 是接線範例，需自行設定片長以啟用多窗；單段 latent 長度不超過 context 時，官方 handler 不啟動多窗。

## 視窗數與提示的實際對應

`context_length=124`、`context_overlap=39` 都是 **real frames**，需符合 `17*n+5`，length 最小 22、overlap 最小 5。上游轉成 latent 時間格：`L(F)=2`（F≤5），其餘 `((F-5)//17)*5+2`；有效 overlap 為 `min(L(overlap), L(length)-5)`。預設 latent length=37、overlap=12、stride=25。最後一窗會向前移到片尾，實際 overlap 可能增加。[官方 node](https://github.com/Comfy-Org/ComfyUI/blob/6651247a8b50cefd1436c834f704bdf7767722e9/comfy_extras/nodes_context_windows.py#L139-L164)、[static scheduler](https://github.com/Comfy-Org/ComfyUI/blob/6651247a8b50cefd1436c834f704bdf7767722e9/comfy/context_windows.py#L888-L904)

以下由函式與固定版 scheduler 推導，索引皆為 half-open，沒有沿用社群貼文的視窗表：

| 請求片長 | 原生幀數／實際秒數 | latent 數 | 預設窗數 | 最後兩窗 latent 範圍 | 尾窗實際重疊 |
| --- | --- | --- | --- | --- | --- |
| 20 秒 | 481／20.0417 秒 | 142 | 6 | [100,137)、[105,142) | 32 latent／107 幀 |
| 30 秒 | 736／30.6667 秒 | 217 | 9 | [175,212)、[180,217) | 32 latent／107 幀 |

其餘相鄰窗在這兩個預設案例重疊 12 latent／39 幀。修改 length／overlap 後重新呼叫 `context_window_plan`，不以此表外推。官方 model 另對影音 window 與 reference payload 做映射／裁切；這是同步機制的來源，不等於成片的口型、聲線或接點已通過驗收。[H3 modality mapping](https://github.com/Comfy-Org/ComfyUI/blob/6651247a8b50cefd1436c834f704bdf7767722e9/comfy/model_base.py)

`window_prompts`／notebook `WINDOW_PROMPTS_JSON` 是完整六欄 prompt 的有序 list，非空時取代 `PROMPT`。每份分別建立原生 reference conditioning，再以 `ConditioningCombine` 做 list concatenation；第一份的 latent 作 sampler 輸入。[官方 combine](https://github.com/Comfy-Org/ComfyUI/blob/6651247a8b50cefd1436c834f704bdf7767722e9/nodes.py#L82-L94)

`split_conds_to_windows=False` 時，每窗保留全部 conditioning。設 True、且實際啟用多窗、condition 數大於 1 時，才按下式選 region：

```text
center_ratio = (latent_start + latent_end_inclusive) / (2 * total_latents)
region_index = clamp(int(center_ratio * prompt_count), 0, prompt_count - 1)
```

三份 prompt 的預設對應：20 秒為 `[0,0,1,1,2,2]`，30 秒為 `[0,0,0,1,1,1,2,2,2]`。這不是「每份提示一窗」或精準逐秒排程，窗重疊處也會融合。單一 prompt 或沒有多窗時，計畫的 `split_active=False`、`region_index=None`。[官方 region 計算](https://github.com/Comfy-Org/ComfyUI/blob/6651247a8b50cefd1436c834f704bdf7767722e9/comfy/context_windows.py#L92-L94)、[選 condition 的條件](https://github.com/Comfy-Org/ComfyUI/blob/6651247a8b50cefd1436c834f704bdf7767722e9/comfy/context_windows.py#L479-L488)

## 可重用的 20／30 秒比較規劃

這是尚未執行的比較方式，不是既有影片或專案的操作依賴。先以 `context_window_plan()` 離線核對實際窗數、尾窗及 prompt region，再準備本次素材、提示與獨立 API graph；GPU 執行另依本次授權與預算。

可依序規劃以下四種設定：

| 案例 | 路徑 | 設定 |
| --- | --- | --- |
| CW20 | Omni Context Windows | 20 秒、124／39、pyramid、FreeNoise、8 steps、單一完整敘事 prompt |
| CT20 | 原生 Continuum | 2×10 秒、現有 Balanced 22-frame continuity、20 steps、strict compatibility |
| CW30 | Omni Context Windows | 同 CW20，改 30 秒 |
| CT30 | 原生 Continuum | 同 CT20，改 3×10 秒 |

共用 A100 STANDARD／`high_mem=false`、640×384、24fps、相同 seed 與內容／聲音要求；同一主體完成清楚的三段連續動作，固定外觀、場景與物件狀態，並保留一段跨接點可聽的聲音。付費配置前先選好單幀參考／起始畫面、最終提示與輸出位置。Omni 使用 reference conditioning；Continuum 若接相同圖片，使用其已支援的 first-frame 或原生 reference 輸入並記明實際接線，不能聲稱兩種條件等價。

Continuum 需先依 sequence 輸入契約編譯每個 chunk 的動作與初末態，避免把完整三段事件重複送給每塊，造成不公平的重複／倒序。從 repo 根目錄可直接重算 CW 規劃：

```bash
PYTHONPATH=scripts python3 - <<'PYTHON'
import json
from comfyui_workflows import context_window_plan

for seconds in (20, 30):
    plan = context_window_plan(seconds, prompt_count=3, split_conds_to_windows=True)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
PYTHON
```

這裡的三份 prompt 用來核對 region 分配；表中的單一完整 prompt 比較需改成 `prompt_count=1`、`split_conds_to_windows=False`。規劃只計算時間格與接線，不含成片品質結論。

兩路的母模、text encoder、步數及延續機制不同，這是製作路線比較；不能將結果解讀為只改 Context Windows 的因果實驗。權重取得與模型切換另外計量；在同一 VM 重用已驗檔案，模型載入成本也分開報告。不得為準備比較而中止其他 live job；需要切換工作台／權重時先確認原作業完成、保存與既有 queue。

先看 20 秒兩例的完整循環，再以更新的剩餘預算決定是否可完成並保存 30 秒兩例。每例只提交一次、保存原 prompt ID 與 receipt，逐例抓回本機；失聯時查原 queue/history，不重送。同一任務的 CU cap 不重設，保存與停止餘量由外部 guard 執行。

每例記錄：

- **身份／場景：** 起、中、末及每個 window／Continuum 接點前後，臉、服裝、道具與空間是否漂移。
- **動作：** 三段事件的順序、可辨識性，有無重複、重置、跳步；說明實際發生時間，不用 prompt 設計代替證據。
- **影音：** 跨接點的聲線、音量、環境聲與動作音效連續性；有台詞時查聽感、口型及句尾完整性。完整 ffprobe／影音解碼及實際速度播放分開記錄。
- **時間／資源：** 下載／載入／生成／解碼／本機保存的完整耗時、provider CU 與採樣間隔下的 VRAM 峰值。冷首次與後續片分列，原生總時長與交付裁切時長分列。

上述 GPU 比較尚未執行。離線 window／schema／graph／notebook 測試通過，只能支持接線與計算契約。

# ComfyUI workspace：Continuum、Ref2VA-VSA 與 FastH3 Omni

[獨立 Colab notebook](../notebooks/ComfyUI_Colab.ipynb) 提供安裝、UI、API 工作流與程序管理。工具內嵌於 notebook，不需要先 clone 本專案。這是新增入口；原 FastH3 L4 與 DiffSynth notebook 保留原流程。

2026-10-28 新增 `h3-omni-int8`：[FastVideo/FastH3-Omni-Comfy](https://huggingface.co/FastVideo/FastH3-Omni-Comfy) 的八步 Ref2VA INT8 ConvRot 模型，以及可選的參考圖尺寸 `REF_IMAGE_SIZE="max" / "match"`。Omni 的 bundle 與 preset 都選 `h3-omni-int8`；使用原生節點、不加 Turbo LoRA 或 VSA transplant。新 Omni 接線及 `max` 設定目前只做離線驗證，未做 GPU 生成／人物相似度實測。[版本、量化選擇與 hybrid 研究](../research/h3_omni_20261028.md) 記錄來源與限制。

初始交付只有來源／離線契約檢查；後續新增 [A100 40GB STANDARD 三組 one-shot 實測](../projects/ninja-continuum-a10040-20261019/RESULTS.md)：同一 server 跑完 Ref Turbo4、Ref Turbo8、Ref Turbo4＋VSA，各36秒、6段，三張人物照片每段均接入 Continuum。三組均通過864幀與完整影音解碼檢查；內容限制、實際接點、費用及原片見結果頁。這不代表其他 preset 或 notebook UI 已驗證，也不把單支片當成一般品質／速度保證。模型磁碟大小仍不等於 VRAM。[來源報告](../research/comfy_h3_extensions_20261019.md) 記錄固定版證據與限制；Veda 本次暫不實作。

[L4 STANDARD 真人版後續實測](../projects/ninja-continuum-live-l4-20261019/RESULTS.md) 已完成兩支各20秒、4×5秒的 Continuum＋Ref Turbo4＋VSA one-shot，三張照片每段均接入。此專案保留同款 INT8 母模，改用動態分層／磁碟卸載、6GiB 額外顯存 headroom 與 INT8 video VAE；整卡每5秒取樣的觀測峰值為15.39／15.77GiB。兩支480幀與完整影音解碼通過；斜前方鏡位、分路跳躍及枝條回彈未穩定達成，原片與內容限制均保留。這項證據只涵蓋該配置，不能套用至所有 bundle；通用 notebook UI 仍未實測。

[Spark-H3 評估](../research/spark_h3_20261019.md) 另行保存：它有加速與記憶體調整選項，但正式套件排除本工作台的 ComfyUI 0.42，且沒有 Spark／Veda 同條件峰值 VRAM 數據，因此本次只研究、不安裝。

## 在 Colab 開啟 UI

1. 自行選擇合適 GPU，開啟 notebook，執行設定與離線計畫格。預設啟用 `continuum`、`ref2va-vsa`，`MODEL_BUNDLE="none"`。先檢視計畫中的版本、模型清單與下載 GiB。
2. 執行安裝格：使用獨立 venv，沿用既有 Torch/CUDA。執行模型格前，明確選 `h3-continuum`、`h3-ref2va-vsa` 或 `h3-omni-int8`，重跑設定與計畫。`none` 不下載任何模型。
3. 執行啟動格，以 Colab 原生 `output.serve_kernel_port_as_iframe` 顯示 UI。`SHOW_COMFYUI=False` 可只啟動 API。要略過安裝／啟動，可關閉 `INSTALL_COMFYUI`／`START_COMFYUI`。
4. UI 可建立自己的 workflow；要交給工具執行，從 ComfyUI 匯出 **API 格式 JSON**，填入 B 區 `API_WORKFLOW_PATH`。若留空，B 區會依 `PRESET` 建立 starter。`PROMPT` 留空會使用該 preset 對應範例；自填 Ref2VA 提示會檢查六欄與 `<Picture 1>`。`RUN_API=False` 預設不生成；明確開啟後只重跑工作執行格。

**server 啟動後如要更換模型 bundle**，先明確執行停止格，再修改 bundle、重跑設定／計畫／下載格，最後啟動 server 更新 loader 模型清單。server 運行期間下載會被拒絕。執行停止後，記得把 `STOP_COMFYUI` 改回 False。

預設 root 為 `/content/comfyui-workspace`、port 為 `8190`，與 FastH3 的 `/content/fast-h3`、`8188` 分開。若同時執行，仍會競爭同一 GPU/RAM；選不同 root 與 port 並不增加硬體容量。此工具不配置 GPU 或建立 Colab runtime。

## 工作流與模型契約

| Preset / model bundle | 模型下載 | 用途與邊界 |
| --- | --- | --- |
| `h3-continuum` | 37.32 GiB | 分塊延續；Core attention、原生 20-step res_multistep starter，不加 Turbo，不需要上游完整範本的 KJ、Spectrum、rgthree。它不是完整上游 UI 範本。 |
| `h3-ref2va-vsa` | 44.96 GiB | 實驗性原生 Ref2VA，使用專用 Ref2VA INT8 ConvRot checkpoint、Ref2VA Turbo4、獨立 gate、FP16 video VAE；Euler。不是原 FastH3 T2VA student 的參考圖模式。 |
| `h3-omni-int8` | 49.15 GiB | FastH3 Omni 原生 Ref2VA，INT8 DiT／含 vision tower 的 INT8 Qwen3-VL／INT8 video VAE／FP32 audio VAE；8-step Euler/simple、guidance 1、shift 12/3。無額外 LoRA、VSA patch 或 custom node；下載量不代表 VRAM 或 L4 容量保證。 |

以上為固定 catalog 的下載量，還要預留安裝、輸入、輸出及暫存磁碟空間；實際清單以計畫格為準。非空模型下載前，工具會檢查硬體／kernel 條件。

Continuum 與 Ref2VA-VSA starter 分開執行，未驗證兩者組合。Ref2VA-VSA 會拒絕既存 attention override 或 DiT block replacement；不要另外接 Sage、Sol 或其他 attention patch。其上游要求 NVIDIA 24 GB、CUDA Sol attention，實際是否可執行仍需在目標環境驗收。

Ref2VA 圖片放在 ComfyUI `input/`，`REFERENCE_IMAGE` 用相對檔名（例如 `reference.png`），提示需遵循原生 Ref2VA 六欄格式並對應 `<Picture 1>`：

```text
subject_definitions: <Subject 1> is the red toy train in <Picture 1>.
summary: [reference generation] The referenced toy train rolls across a table.
retention_analysis: <Subject 1> (appears in [Shot 1]): fully_preserved.
detailed_description: [Shot 1] <Subject 1> from <Picture 1> rolls steadily across a wooden table.
overall_soundscape: Wheels rattle softly.
non_diegetic_music: N/A.
```

`REF_IMAGE_SIZE` 適用 `h3-ref2va-vsa` 及 `h3-omni-int8`，會直接傳入 `MiniMaxH3ReferenceToVideo.ref_image_size`。Notebook 表單預設 `max`；Python `build_graph()` 未指定時，Omni 預設 `max`，既有 Ref2VA-VSA 保留 `match`。

| 值 | 原生節點實際處理 | 使用取捨 |
| --- | --- | --- |
| `match` | 按輸出像素面積等比例縮小參考圖；不放大小圖 | 預覽、速度或記憶體優先 |
| `max` | 保留原圖至最高 2048px 短邊；不放大小圖，尺寸取 32 倍數 | 保留更多臉部／服裝細節，可能慢數倍並增加記憶體；低解析原照不會憑空增細節 |

這是[原生 Ref2VA 的細節設定](https://docs.comfy.org/tutorials/video/minimax/minimax-h3#setting-the-output-resolution)，不是混合 FL2VA／Ref2VA 權重，也不是人物相似度保證。比較時固定原照、prompt、seed、輸出尺寸、步數，只切換 `match`／`max`，再看臉、髮型與服裝；本次沒有執行這項 GPU 對照。

Omni starter 接一張圖片，使用原生 dense attention；影片／音訊或多圖 references 需自訂 API graph。Omni 已蒸餾成八步，不要再接 Ref Turbo4／Turbo8，也不要套舊 FastH3 V2 的 video shift 10。發布者指出原生 ComfyUI 的 PDD 時間格與 VSA 幾何不同於 FastVideo runtime，所以不能沿用另一 runtime 的速度或品質數字。這份 script 沿用現有 ComfyUI pin；其 H3 模型與 detector 原始碼與 Omni 轉檔使用的版本一致。

社群 [FL2VA + Ref2VA hybrid](https://huggingface.co/smhfacct/Minimax-H3-fl2va-ref2va-hybrid-models) 是 FL2VA 母模加上後段 Ref2VA AdaLN 權重的實驗性 merge。作者描述的是畫質與 reference 能力的主觀取捨，沒有證明普遍比純 Ref2VA 更像本人；本次保留研究，不把它當作 Omni 或 `max` 的同義設定。

請按實際素材修改，不要直接沿用 T2VA 的三欄預設提示。非 Continuum 的原生 H3 影格會對齊 `17n+5`；5 秒輸入可產生 124 幀（約 5.167 秒），不是精確最終片長保證。Continuum 的 `CHUNKS` 是分塊數，`DURATION_SECONDS` 是每塊秒數。

安裝格的 `stage_workflows()` 會把 API starter 放入 `<root>/workflows/`。也可先查看 repo 裡的 [Continuum starter](../workflows/comfyui_h3/h3-continuum.api.json)、[Ref2VA-VSA starter](../workflows/comfyui_h3/h3-ref2va-vsa.api.json) 與 [Omni INT8 starter](../workflows/comfyui_h3/h3-omni-int8.api.json)。API JSON 由 `run_api` 執行；目前沒有驗證可直接拖入 UI 編輯器。

UI 可使用 ComfyUI 內建節點及本次勾選的擴充，處理自選模型與工作流。工具只載入 catalog 選定的 custom-node 目錄；新增其他擴充需先在 `scripts/comfyui_catalog.json` 加入 repo、固定 commit、目錄與預期 node IDs，再重新封裝 notebook。它不會自動安裝未知工作流缺少的套件。

Ref2VA-VSA 的工具預檢要求 Ampere 以上、24 GB 等級 NVIDIA GPU，並實際跑小型 BF16 Sol CUDA kernel；通過只代表該小型 kernel 可執行，不代表完整模型、參考圖及目標尺寸放得下。下載核對固定 revision、bytes 與 SHA-256；預設官方 HF／Xet 路徑最多兩檔並行、重用校驗成功的完整檔，驗證後 hardlink 至本機模型目錄。工具不清 cache，但 partial 由 SDK 管理；Hub 1.33.0／Xet 1.7.0 程序終止後不能接續舊 partial。控制斷線應保留原背景下載，詳見 [快速部署](COLAB_QUICK_DEPLOY.md)。舊 HTTP 串流路徑可明確選 `--download-backend http`，其未完成傳輸不保留；沒有自動 fallback。環境無法滿足固定依賴時會停止，錯誤詳見 `state/install.log`、`state/download-progress.json`、`state/model-preflight.log` 或 `state/server.log`。

## 路徑與保存

| 內容 | 預設位置 |
| --- | --- |
| 內嵌工具還原目錄 | `/content/comfyui-workspace-toolkit/` |
| ComfyUI / 模型 | `<root>/ComfyUI/` / `<root>/ComfyUI/models/` |
| 輸入圖片 | `<root>/ComfyUI/input/` |
| 工作流 | `<root>/workflows/` |
| 生成輸出 | `<root>/ComfyUI/output/`（以 API 回傳為準） |
| 管理紀錄 | `workspace.state` 指向的目錄；狀態格顯示實際資訊 |

先播放輸出、檢查音訊，再從 Colab Files 下載檔案；或在獨立格執行：

```python
from google.colab import files
files.download("/content/comfyui-workspace/ComfyUI/output/你的影片.mp4")
```

Continuum Take/session 的中間資料也需保存。確認該工作流 `run_storage` 的實際位置，把 Take、session 與最終輸出一起備份；只下載 MP4 無法保留重選 Take 的狀態。`/content` 不是永久儲存。

API 每次送件保存 `<root>/runs/<prompt_id>/workflow.api.json`、`receipt.json` 與完成／失敗的 history。`execution_complete` 只表示 ComfyUI 完成執行；媒體完整性與內容驗收另計。逾時會記為 `timeout_may_be_running`，不自動重送或中斷；先用狀態格與 `workspace.client.get_json('/history/' + prompt_id)` 查原工作。

`STOP_COMFYUI=False` 避免 Run All 立刻關閉 server。明確開啟停止格只會停止此工具管理的 ComfyUI 程序。下載完成後，另從 Colab 選單停止／刪除 runtime，或用你現有的 Colab 管理工具釋放 runtime。

## 本地 CLI 與 notebook 匯出

以下指令在已 clone 本專案的環境使用；`plan` 不連網、不安裝、不下載。先看計畫再執行安裝與下載：

```bash
python3 scripts/comfyui_workspace.py plan --root /content/comfyui-workspace --port 8190 --extensions continuum,ref2va-vsa --bundle h3-continuum
python3 scripts/comfyui_workspace.py install --root /content/comfyui-workspace --port 8190 --extensions continuum,ref2va-vsa
python3 scripts/comfyui_workspace.py download --root /content/comfyui-workspace --bundle h3-continuum
python3 scripts/comfyui_workspace.py start --root /content/comfyui-workspace --port 8190 --extensions continuum,ref2va-vsa
python3 scripts/comfyui_workspace.py run --root /content/comfyui-workspace --port 8190 --workflow /content/custom_api.json --timeout 1800
python3 scripts/comfyui_workspace.py status --root /content/comfyui-workspace --port 8190
python3 scripts/comfyui_workspace.py stop --root /content/comfyui-workspace --port 8190
```

只使用原生 Omni 可將 CLI 的 `--extensions` 設為空字串；離線預覽不下載模型：

```bash
python3 scripts/comfyui_workspace.py plan --root /content/comfyui-workspace --extensions '' --bundle h3-omni-int8
```

可沿用現有 `export_cells.py`，在已連線的 persistent Colab kernel 執行。`setup` 包含設定、離線計畫、安裝、可選下載、啟動；`clip` 僅包含工作設定與可選 API 執行。狀態與停止格有各自標籤，不包含在這兩個區段；`all` 可編譯但仍有 `RUN_API=False`、`STOP_COMFYUI=False` 保護。

```bash
python3 scripts/export_cells.py setup --notebook notebooks/ComfyUI_Colab.ipynb --output /tmp/comfyui-setup.py
python3 scripts/export_cells.py clip --notebook notebooks/ComfyUI_Colab.ipynb --output /tmp/comfyui-clip.py
```

更改 toolkit 後以 `python3 scripts/build_comfyui_notebook.py` 重新封裝；內嵌來源由 builder 的 `BUNDLE_FILES` 管理，包含下述批次排程器。builder 只重建此 workspace notebook，不修改舊 FastH3 notebook。

### 批次：生成、取回與審查並行

單鏡 `workspace.run_api(...)` 保留同步行為。批次可拆成 `workspace.submit_api(workflow_path, prompt_id=...)` 與 `workspace.wait_api(prompt_id, timeout=...)`，交由 `colab_video_pipeline.Pipeline` 的單一 GPU producer 自動接續；取回與 QA 各一條工作線，前一鏡未下載／未審完不會卡住下一個 ready job。使用者已授權的重跑以新 ID、`priority="retake"` 加到所有待跑一般鏡頭之前，當前 GPU 工作正常完成。

接線介面如下；在配置 GPU 前把既有 Colab adapter、保存、QA 與准入 callbacks 準備好：

```python
from colab_video_pipeline import Pipeline

pipeline = Pipeline("/path/to/project/pipeline")
pipeline.enqueue("s01-take01", {"workflow": "/path/to/s01.api.json"})
pipeline.enqueue("s02-take01", {"workflow": "/path/to/s02.api.json"})

# submit(attempt): ws.submit_api(attempt["payload"]["workflow"],
#                               prompt_id=attempt["prompt_id"])
# wait(attempt, submission): ws.wait_api(attempt["prompt_id"], timeout=...)
# fetch(attempt, execution): actual transfer + identity/hash verification
# review(attempt, artifact): local full decode + requested content checks
pipeline.run(submit=submit, wait=wait, fetch=fetch, review=review,
             admit=admit_current_budget, on_saved_drain=notify_resource_owner)
```

這是 adapter 接線範例，callbacks 使用本次既有的執行與傳輸工具。若 controller 與 ComfyUI 同在 VM，`fetch` 只搬到 VM staging 就只代表 VM 保存；Mac 取回另行並行，精確 endpoint 釋放仍須等必要產物實際存回。若 controller 在本機，`fetch` 可直接接 Colab 下載器。排程器不自行配置／停止 Colab、不推定新生成授權、不自動重抽。

`on_saved_drain` 在必要取回完成後、完整內容 QA 結束前通知資源擁有者；當前沒有 ready jobs 時不為未定重跑持續租 GPU。尚未滿足實際輸入依賴的鏡頭用 `ready=False`，輸入準備好再 `set_ready`，其他 ready 鏡頭照常跑。提交狀態不確定就對帳原 UUID，不重送。完整排程、保存積壓及預算關鍵路徑規則見 [共用 runtime 流程](../skills/colab-video-studio/references/runtime-monitoring.md#批次排程生成保存與驗收並行)。本次僅離線驗證控制行為，沒有新增 GPU 效能或畫質結論。

原生 Omni 可先使用 [快速部署](COLAB_QUICK_DEPLOY.md) 封好素材、原 project adapter 與第一鏡，再以單一背景 worker 自動接續 setup → 首鏡。共用 workspace 的 `install --environment PATH` 可還原已驗證且基底相容的離線環境；沒有指定環境包時沿用線上安裝。

2026-10-28 執行 `python3 -m unittest discover -s tests -p 'test_comfyui_*.py' -v`，28 項離線檢查通過，包含來源 schema 的必要欄位／型別接線、三組模型清單完整性、下載損壞與既存檔案保護、server 身分與停止等待、失敗／逾時收據，以及 notebook 內嵌來源、預設行為、匯出編譯與可重現建置。新增檢查確認 Omni 八步、無額外 Turbo／gate、`max`／`match` 傳至原生 conditioning，以及無 custom node 的離線計畫。來源 schema 是固定版本的靜態快照，沒有代替真實 ComfyUI import 或 GPU 生成。

使用者提供的 YZ 金魚 workflow 與 HyperFlow-Infinity 已完成[來源與移植界面研究](../research/h3_workflow_hyperflow_20261028.md)。前者使用 hybrid／12步／SelfLift；後者本來就是本地 H3 的多 GPU harness，需原始 latent 交接，尚未移植到此 notebook。

# Repo 工具定位

本 skill 隨 `colab-utils` repo 使用，`<repo>` 指該 checkout。工具位於 repo 根 `scripts/`，不是 skill 自帶 scripts。缺 repo 或依賴時報能力缺口，不能拿歷史專案腳本或不同 backend 冒充入口。

| 分支／用途 | Canonical 入口 | 何時讀 |
| --- | --- | --- |
| 原 H3／FastH3 共用 notebook | `notebooks/MiniMax_H3_A100.ipynb` | 讀 cell IDs、tags、BACKEND、所需表單與 validator；具體問題才取相關函式 |
| FastH3 獨立 notebook | `notebooks/FastH3_ComfyUI_L4.ipynb` | FastH3 notebook 操作 |
| Pika H3 Flex | `scripts/pika_h3.py`、`notebooks/Pika_H3_Flex_Colab.ipynb` | 指定 `pika` 時讀 [Pika 契約](pika-h3-flex.md)；`plan/install/generate/status`，與 Omni／Studio 分開 |
| Notebook 匯出 | `scripts/export_cells.py` | `setup`／`clip` tags 匯出到指定 `--output`；不執行匯出源碼 |
| 原生 Omni 快速部署 | `scripts/colab_video_bootstrap.py`、`scripts/comfyui_environment.py` | [預備包／離線環境／首鏡銜接](../../../doc/COLAB_QUICK_DEPLOY.md)；沿用原 project adapter，不配置 VM、不另建 job 身分 |
| Omni Context Windows（實驗） | `scripts/comfyui_workflows.py`、`notebooks/ComfyUI_Colab.ipynb` | 指定 Context Windows 時讀 [實際視窗／prompt region 與20／30秒比較計畫](../../../doc/H3_CONTEXT_WINDOWS.md)；使用新 Core pin；短段有重複台詞等已知限制，20／30秒比較未執行 |
| FastH3 CLI | `scripts/fast_h3_colab.py --help` | `prepare/start/setup/generate/status/fetch/refresh/stop` 與參數 |
| Comfy graph | `scripts/fast_h3_workflow.py --help`、`workflows/fast_h3_l4.json`／`.api.json` | graph export 指定 `--output-dir`；不帶此值會重建 canonical workflows |
| 模型／版本 pin | `scripts/fast_h3_lock.json` | revision、bytes／SHA、時序／VSA 契約 |
| Runtime／媒體 validator | `scripts/fast_h3_runtime.py` | 具體 setup、queue、reference、verify_media 或 receipt 問題 |
| Node／HTTP client | `scripts/fast_h3_nodes.py`、`scripts/fast_h3_client.py` | LoRA target、reference trace、cache、node schema 或 queue／history 邊界 |
| 同 endpoint refresh | `scripts/refresh_fast_h3_session.py` | CLI Python 環境中的 proxy 恢復；不配置 VM |
| 操作說明 | `doc/FAST_H3_L4.md`、`USAGE.md` | 對應工具流程與已安裝 Colab CLI 用法 |
| 限時試驗 recorder／sealer／audit | `scripts/record_fast_h3_trial.py`、`seal_fast_h3_trial.py`、`audit_fast_h3_trial.py` | 僅明確的 [agent/session 試驗](agent-validation.md) |

本機用 `python3` 查看已提供 CLI help。未知入口先確認參數解析再執行；`--help` 不保證未知 generator 沒有副作用。Colab CLI help 可能寫安裝環境的 log，受 sandbox 限制時讀已安裝 source 或按既有授權處理，不輸出憑證。

離線 FastH3 prepare 與 notebook export 指向當次可寫目錄，不重建 notebook／canonical graph。`scripts/build_fast_h3_notebooks.py` 只在共享 runtime／lock 修改且需要同步 notebook 時使用。讀 notebook JSON 時先列 cell IDs／tags，再選狹窄源碼，不打印巨型 `FAST_H3_SOURCES`。

工具變更的驗證按邊界選擇：graph／notebook／runtime 可用 `tests.test_fast_h3_workflow`、`tests.test_fast_h3_notebooks`、`tests.test_fast_h3_runtime`；影响原 backend 加 `tests.test_notebook_workflow`，HTTP／session 變更加對應 checks。文档修改驗結構與引用即可。Fakes 只支持本機契約，不能證明 GPU 容量或內容品質。

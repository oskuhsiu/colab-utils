# Colab：縮短生成前的下載、安裝、編譯與載入時間

記錄日期：2026-10-12。

**狀態更新（2026-10-31）：原生 Omni 已實作離線環境包工具、官方 HF／Xet 下載與單一背景部署到首鏡入口，見 [快速部署操作與驗證範圍](../doc/COLAB_QUICK_DEPLOY.md)。三輪離線故障測試及兩台 T4 STANDARD 無生成演練完成：線上安裝約 39 秒，實建環境包後四次離線還原約 24–25 秒；另驗兩個 VAE 的下載、完整檔重用和同 worker 重連。包傳輸需數分鐘，未證明離線包端到端更快；固定 HF／Xet 不支援跨程序 partial 續傳。未做模型載入／生成或 A100 速度比較；C01 小批次與條件式編譯快取仍為下述計畫。證據見 [無生成演練](../research/colab-preflight-rehearsal-20261031.md)。**

## 目標與前提

- 使用者直接取得上游已量化好的權重，沿用目前模型、版本與工作流。
- 縮短新 session 到第一個成功生成結果的時間，並減少同一 session 內重複安裝、啟動程序與初始化模型。
- 將可重用的程式、套件與編譯產物保存到持久儲存，再還原到 runtime 本機磁碟。
- 分開計量下載、校驗、安裝、編譯、載入、首次生成與後續生成；只報告實際量到的節省時間與 CU。

## 已有證據

| 項目 | 目前觀察 | 對本計畫的意義 |
| --- | --- | --- |
| C01 標準 T4 準備 | 共 805.214 秒；模型下載與校驗 700.594 秒；其他準備合計 104.621 秒 | 其他準備包含安裝、來源取得及檢查，不能全部算成編譯時間；單改環境安裝不能聲稱省掉整段約 13.4 分鐘 |
| C01 生成 | TE → DiT → VAE 分三個獨立程序；12.67 GiB RAM 已完成 512×288／121f 影音輸出 | 小批次優化須保留分階段釋放記憶體，避免 TE、DiT、VAE 同時保留 |
| Qwen／原 H3 | 已有同一 kernel 重用 pipeline 的邏輯 | 這項能力已存在；不能當成本輪新增的省時成果 |
| FastH3 | 已有安裝 signature、模型校驗紀錄、server 重用；HF 權重到模型目錄使用 hard link | 同一 runtime 已會略過部分重複工作；優先研究跨 session 的環境重建成本 |
| FastH3／C01 | 現行路線均停用 Comfy compiler | 不能預設通用 `torch.compile` 快取會加速這兩條路線；停用 Comfy compiler 也不代表所有擴充或 kernel 都沒有 JIT 成本 |

本機來源：

- [C01 準備時間](../projects/kandinsky6-lite-t4-20261011/results/setup-status.json)、[下載／校驗 receipt](../projects/kandinsky6-lite-t4-20261011/results/logs/assets-C01.json)、[標準 T4 實測](../doc/KANDINSKY6_LITE_T4.md)。
- [C01 環境安裝](../projects/kandinsky6-lite-t4-20261011/setup_remote.py)、[分階段程序](../projects/kandinsky6-lite-t4-20261011/staged_worker.py)。
- [FastH3 runtime](../scripts/fast_h3_runtime.py)、[FastH3 L4 已驗配置](../doc/FAST_H3_L4.md)。
- [Qwen notebook 建置器](../scripts/build_qwen_comic_notebook.py)、[H3 pipeline 重用](../skills/colab-video-studio/scripts/h3_setup.py)。

## 方案與優先順序

### 1. 優先建立離線環境包

保存固定版本的程式來源、必要 custom nodes、依賴 lock／constraints、套件 wheelhouse 與 manifest。來源取得及套件建置只在環境包更新時執行；新 session 將包複製到 `/content`，解壓並離線安裝。

- 安裝使用僅含 wheel 的來源，可配合 `--no-index --find-links` 與 `--only-binary=:all:`；缺少相容 wheel 時明確回報，避免意外回退到長時間 source build。
- 記錄 Python／ABI、PyTorch、CUDA 與必要 GPU architecture、程式 commit、依賴版本及檔案 hash。原生 CUDA 擴充按相容環境分包。
- 相容時沿用 Colab 既有 Torch；C01 目前固定的 Torch 2.10／cu128 配置先保留，不能為省安裝時間直接換成未驗版本。
- 不將完整 venv 視為任意 Colab runtime 都能直接還原的通用映像。wheelhouse 還原後仍有安裝與 import 成本。
- 程式包解壓到本機後執行，避免從 mounted Drive 遍歷大量小檔案。
- FastH3 現有 `_checkout()` 以 `.git` 判斷來源；若使用無 `.git` 的來源包，後續 bootstrap 須核對 manifest，不能直接塞進現有 checkout 流程。

**待驗收：** 新 session 可從環境包完成安裝與既有 kernel／dtype probe；沒有意外 source build；把環境包傳輸、解壓及安裝時間全部算入比較。

### 2. 優先減少模型與程序的重複初始化

Qwen／H3 保留現有 pipeline 重用。C01 研究有界小批次的分階段處理：

```text
TE 程序：編碼多個已確定的 prompt，逐項保存 conditioning → 終止
DiT 程序：逐項生成 latent，逐項保存 → 終止
VAE 程序：逐項解碼影音、保存 MP4 → 終止
```

- 首次只用兩個任務驗證，沿用已成功的尺寸、採樣設定與模型版本。
- 減少程序啟動與模型初始化，不假定 disk-backed loading 的所有權重都能常駐 GPU。
- 各項 conditioning／latent／MP4 帶 task ID、prompt、seed、模型與設定身分；已完成項目核對 manifest 後才可略過。
- 每階段確實釋放上一階段的程序；保留 finite 檢查、完整影音解碼與資源紀錄。
- 比較原逐片方式與小批次方式的總時間、RAM／VRAM 峰值及生成結果；不能用舊輸出 cache 命中代替新採樣。

**待驗收：** 兩個任務都完成；符合原精度及媒體契約；記憶體峰值可接受；沒有重複模型初始化或錯配中間產物。

### 3. 依實際成本處理編譯快取

先區分安裝期 source build、CUDA extension 載入期 JIT，以及 `torch.compile`／Inductor／Triton 的 graph 編譯與 autotuning。

- 需要 source build 的原生擴充，優先建立符合目標環境的預編譯 wheel。
- 只有實際使用 JIT／compiler 且日誌顯示有成本的路線，才保存對應快取。
- `TORCH_EXTENSIONS_DIR` 只指定編譯目錄，不保證新程序不重編；須驗證實際命中。
- `torch.compile` 可依版本使用磁碟快取或 cache artifact 匯出／載入。版本、GPU、graph／shape／設定不符時可能失效；T4 與 L4 分開管理。
- 快取包還原到本機後使用。有效性檢查失敗時回到原安裝／編譯流程，保留失效原因。
- 維持現行 FastH3／C01 的 Comfy compiler 設定，不為建立快取重新啟用已有失敗證據的配置。

**待驗收：** 在相容的新 runtime 看見快取命中，實際編譯時間減少，生成與 kernel probe 均通過。未啟用 compiler 的路線不列此項收益。

### 4. 權重來源與本機磁碟

- Drive 可保存上游已量化權重，但 mount 不會把模型預先載入 RAM／VRAM。
- Drive 公開連結下載到 `/content` 仍須傳輸完整檔案，不能預設比 Hugging Face 快。
- 對會反覆從磁碟載入權重的 offload／mmap 路線，先使用 runtime 本機磁碟，再評估其他來源。
- 如要比較 HF 與 Drive，只比較同一個權重、同一 runtime、相同校驗要求的端到端取檔時間；目前尚未實測。
- 每次新 VM 的必要檔案傳輸、校驗及模型載入仍計入成本；同一 runtime 沿用已驗檔案與既有重用機制。

## 後續實作範圍

先選一條既有成功路線試辦，不一次修改所有 notebook：

1. **離線環境包：** 建立來源／wheelhouse／manifest 建置工具與本機還原入口，接到所選路線的安裝階段。
2. **階段耗時：** 在既有 phase／receipt 增加或細分安裝、編譯、權重載入時間，保留現有下載及媒體驗證紀錄。
3. **C01 小批次：** 在分階段 runner 上增加有界任務清單，維持各階段分程序及逐項保存。
4. **條件式編譯快取：** 只有取得實際編譯成本證據後再加入，按目標環境管理。

同一 session 重用與新 session 還原分開比較。第一片的比較包含全部準備成本；後續片另報。速度不能從單一歷史數字推算成固定節省比例。

## 驗證安排與目前完成範圍

2026-10-12 當時僅完成來源檢查與計畫記錄；2026-10-31 的原生 Omni 實作與本機驗證範圍見頁首更新。GPU 實測待後續安排，不從離線檢查推定省時比例。

有可用資源後，先以一個新 session 測環境還原及 kernel probe，再驗一個小生成任務。通過後才比較兩項任務的小批次；每次立即保存成果，完成後釋放 runtime，將 CU／耗時與原始日誌對應。

## 官方依據

來源核對日期：2026-10-12。官方能力不代表本專案已取得相同改善幅度。

- [pip install：本機 wheel 安裝與 binary 選項](https://pip.pypa.io/en/stable/cli/pip_install/)。
- [PyTorch CUDA／C++ extension：建置目錄與 GPU architecture](https://docs.pytorch.org/docs/main/cpp_extension.html)。
- [PyTorch compile cache：相容性與可攜 cache artifacts](https://docs.pytorch.org/tutorials/recipes/torch_compile_caching_tutorial.html)。
- [Google Colab FAQ：Drive I/O、runtime 生命週期與檔案持久性](https://research.google.com/colaboratory/faq.html)。

平台移植另參考 [L4／T4／Kaggle 適用性評估](../doc/VIDEO_MODEL_L4_T4_KAGGLE.md)；本計畫不將不同 GPU 的編譯產物視為自動相容。

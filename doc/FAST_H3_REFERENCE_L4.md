# FastH3 人物圖片參照：L4 實驗分支

圖片經原生 `MiniMaxH3ReferenceToVideo` 同時送入 Qwen 與 video VAE，並在四次 DiT forward 核對非零 `ref_img` rows。模型維持既有 1300-step 四步 FastH3 student；此 student 只蒸餾 T2VA，因此新增模式標為 **experimental_ref2va_ood**，沒有改稱正式 OmniRef 或默换原 H3。

## 使用

原 H3 notebook 和獨立 FastH3 notebook 都已新增 `FAST_H3_MODE`、`FAST_H3_REFERENCES_JSON`。Notebook JSON 填 Colab 上已存在的圖片路徑，例如 `["/content/portrait.jpg"]`，最多三張。原 DiffSynth 的 references 選項仍獨立保留。

CLI config 使用 `generation_mode: "experimental_ref2va_ood"` 和 `reference_paths: ["本機圖片路徑"]`；CLI 自動上傳、runtime 按 SHA 複製到 Comfy input 根目錄。範例 config 見 [primary_cold.json](../projects/fast-h3-ref-l4/20261009/primary_cold.json)。提示使用官方 Ref2VA 六欄格式，`<Picture N>` 恰好對應圖片順序。

```bash
python3 scripts/fast_h3_colab.py prepare --backend comfy --config <config.json> --output <run-dir>
python3 scripts/fast_h3_colab.py setup --backend comfy --session <既有L4> --output <run-dir>
python3 scripts/fast_h3_colab.py generate --backend comfy --session <既有L4> --config <config.json> --output <run-dir>
```

獨立 UI/API template 見 `workflows/fast_h3_l4_ref_experimental.json`／`.api.json`。匯入 UI 後先上傳真實圖片並在 LoadImage 選取；每次新採樣改 request_id 或 seed，CLI 會自動產生新 request_id。這可保留相同 seed 和條件快取，同時強制 sampler 重新執行。

## 已量測的 5 秒結果

864×480、24 fps、120 frames、32 kHz stereo；每支均有四次圖片 latent trace、200 native VSA、零 fallback，並完整解碼。

| 條件 | 完整生成 | 採樣 | 第一次 forward |
| --- | ---: | ---: | ---: |
| 首次載入／編碼 | 161.55 s | 84.68 s | 53.52 s |
| 同 prompt／照片／seed，條件快取命中，新採樣 | 65.92 s | 44.13 s | 13.04 s |
| 只換照片，條件重新編碼 | 146.30 s | 81.85 s | 50.35 s |

完整時間由準備／下載後送圖開始，包含文字與圖片條件、模型載入、採樣、影音解碼、儲存和驗證；不含本機圖片上傳。首 forward 可能包含動態載入，不能當純算力時間。同條件 warm 由 history 的 cache nodes 和新 sampler request／四條 trace 證明，並非沿用快取 MP4。精確數據見 [benchmark.json](../projects/fast-h3-ref-l4/20261009/benchmark.json)。

固定文字和 seed 換照片，短髮男孩變成長髮瀏海女孩，支持「照片在此對照影響生成角色」。人物長相仍近似、年齡偏幼；身份保真度保留 **needs_review**。單人近景成功不證明多人、仙子裝、弓箭或長故事連續性。

## 保存與驗收

每支保存來源 file SHA／順序／尺寸、RGB tensor 與 VAE latent SHA／shape、四次實際 layout、prompt／seed／workflow、模型版本、資源取樣及 MP4 hash。技術與內容分開驗：200 VSA 不能單獨證明 ref 輸入，更不能證明原臉保留。參照接線／限制見 [skill reference](../skills/minimax-h3-colab/references/fast-h3-reference.md)。

速度與內容研究：[速度](../research/h3_fast_h3_speed_20261009.md)、[內容符合度](../research/h3_fast_h3_alignment_20261009.md)。外部硬體 benchmark 不當作本機 L4 實測。

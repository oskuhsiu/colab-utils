# FastH3 圖片參照實驗

僅用於明示的 `experimental_ref2va_ood`。Pinned Kijai 1300-step 四步 student 的蒸餾範圍是 T2VA；原生 ComfyUI node 能接圖片，不代表此 student 已蒸餾 Ref2VA 或保證人物相似度。其他 OmniRef student／recipe 不與這套 checkpoint 混用。

## 輸入與接線

CLI config：`generation_mode: "experimental_ref2va_ood"`、`reference_paths` 為 1–3 張本機圖片。CLI 上傳到指定 session，runtime 解碼、按內容 SHA 複製到 ComfyUI input 根目錄，以兼容 stock LoadImage 選單。

Notebook 用 `FAST_H3_MODE` 與 `FAST_H3_REFERENCES_JSON`（Colab `/content` 路徑）；原 DiffSynth `REFERENCE_PATHS` 不屬此 backend。此實驗只接圖片，沒有 reference video／audio 或首尾幀。T2VA 嚴格拒絕 references，只有明示實驗開 `allow_unsupported_conditioning`。

Graph：LoadImage → FastH3ExperimentalReference → 原生 MiniMaxH3ReferenceToVideo；圖片送入 Qwen 和 video VAE，`ref_image_size=match`。Prompt 依 [Ref 六欄規格](official-prompting.md#ref2va-六欄與來源對應)，`summary` 以 `[reference generation]` 開始，Picture labels 必須恰好對應實際輸入順序。

一張原照可能有多人，Subject 指向實際身份來源並區分臉髮、年齡、衣服與背景用途。裁切看實際輸入內容、記錄原像素座標與 hash；裁切不是輸出像素硬鎖。簡化參照或動作是有需要時的診斷方案，不是所有任務必做預覽。

## 條件生效的證據

保存 `reference-manifest.json` 的原始 bytes SHA、尺寸與順序。Receipt 的 `reference` 應包含 RGB tensor／VAE latent hash、latent shape 及每次 DiT forward 的 `ref_img` rows；此 pinned graph 要有四次非零 image-conditioned layouts／forward timing，加上四步、200 VSA calls、零 fallback、完整 decoded MP4。

若 trace 缺失，核對 tracker 是否穿過 Comfy model-options copier／clone 邊界；本地以 opaque trace object 處理，查 `scripts/fast_h3_nodes.py` 對應 wrapper。VSA 計數不能代替四次 reference trace。Prompt 圖號、graph 連線或輸出變化也不能代替條件證據。

技術條件與身份 verdict 分開。對照原照與相關原尺寸影格判斷身份／髮型／衣服，其他內容依 [通用驗收](../../colab-video-studio/references/video-review.md#通用驗收)。此實驗不默換原生 Ref checkpoint；若另外授權身份後製，按 Studio 的 people 分支驗證並保留原生 verdict，後製結果不回填成 student 原生能力。

## 暖機與條件快取

同 prompt／照片／seed 的 warm 對照可沿用條件快取，但 sampler 必須重新執行。Runtime 用新的 request identity；實驗 graph 的 FastH3SampleRequest 只使 sampler 重新執行，保留原 seed。核對新 prompt ID、新 receipt、四次 trace 及新 MP4，避免把全圖 cache hit 當新生成。

照片或 prompt 改變時另標條件重新編碼；不要與條件完整 cache-hit 的 warm run 混比。報 `metrics.total_seconds`、`reference.sampler_seconds` 和四個 CUDA-synchronized `forward_seconds` 的各自範圍，首 forward 可能仍含動態載入；後製時間另計。

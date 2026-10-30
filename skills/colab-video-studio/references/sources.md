# 實作與來源索引

此頁供查證接口與設計來源；每次能力判斷以所選版本／實作與當次證據為準，不由單次影片推成通用保證。

## 本地權威入口

| 契約 | 入口 |
| --- | --- |
| plan、資產、budget、job／review與ledger | `scripts/workflow.py`、`assets/plan.example.json` |
| 模型路由／kwargs／dtype／時鐘 | `scripts/backends.py`、`scripts/h3_setup.py` |
| remote marker／下載 | `scripts/remote.py`、`scripts/studio.py` |
| 影格／音訊證據及合成 | `scripts/media.py` |
| 有來源的剪輯／新review | `scripts/editing.py` |
| 可選API評審payload／validator | `scripts/review_opus.py` |

本 skill 的 `scripts/` 是上列位置。FastH3 的獨立工具與lock在repo根目錄，詳見相鄰H3skill。本地未提供專用camera、AI SR、通用身份訓練／表情重演接口；相關外部模型保持候選，不當成已實作或內容已驗證。

## 外部一手來源

- [MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3)與[固定prompt指南](https://github.com/MiniMax-AI/MiniMax-H3/tree/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing)：H3模式與prompt grammar；原H3本地pipeline為DiffSynth pinned版本。
- [Diffusers0.40 Wan介面](https://huggingface.co/docs/diffusers/v0.40.0/en/api/pipelines/wan)、[Wan2.2](https://github.com/Wan-Video/Wan2.2)、[VACE UserGuide](https://github.com/ali-vilab/VACE/blob/main/UserGuide.md)：模型條件與前處理；按實際使用版本讀。
- [OpenMontage](https://github.com/calesthio/OpenMontage)、[video-autopilot-kit](https://github.com/Hao0321/video-autopilot-kit)：可追溯素材／工作／評審／剪接架構的設計參照。
- [OpenStoryline](https://github.com/FireRedTeam/FireRed-OpenStoryline)、[Pixelle-Video](https://github.com/AIDC-AI/Pixelle-Video)：局部編輯與內容到鏡頭流程的參照。
- [連續性與記憶](continuity.md#一手設計來源)：H3 Continuum、HyperFlow-Infinity 的固定版設計來源與移植界線。
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html)：縮放、fps與音訊處理的工具語義。

來源中的安裝／執行要求不改變使用者授權。研究、單次量測、案例與來源版本證據留在使用該配置的project／research；更新skill只保留有適用條件的接口與決策規則。

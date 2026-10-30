# H3／FastH3 公開社群原帖補查

查閱日：2026-10-10。目的限定為找可讀的第一手 X、Facebook 公開貼文，或作者同步到 GitHub／blog／Reddit／YouTube 的原始測試；不重做 02 已有數字，不把 trending/Grok 摘要當證據。低資源目標是單 L4；中資源是單 A100 + High RAM。RTX 3060/5060 Ti/4080S/4090/5090 等只保留實際條件，不外推到目標 GPU。

## 可讀的 firsthand／作者同步測試

|ID／來源|條件與 workflow|可核對結果|限制|
|---|---|---|---|
|SOC01 [Kasei-san 16GB workflows](https://github.com/kasei-san/minimax-h3-comfyui-workflows)|作者 RTX 5060 Ti 16GB、RAM 32GB、Windows10、PCIe3 x8；ComfyUI，官方 pruned INT8 ConvRot + NVFP4 TE/VAEs，Turbo 可切換。|T2V 1024×576、約 5.2s：Turbo 171.6s／通常 379.2s；I2V 0.6MP：207.7／704.4s。固定 seed、864×480、124 frames、20 steps 的比較：無加速 270.9s，EasyCache 210.7s 但音訊變噪，Turbo 4/6 steps 117.6/114.4s。|作者自測 workflow；未對 L4/A100；Turbo/EasyCache 結果是作者設定下的 single machine evidence。|
|SOC02 [GenVidKit local ledger](https://www.genvidkit.com/workflows)|作者固定 seed、1344×768、124 frames、20 steps、ComfyUI 0.31/PyTorch cu130；RTX 3060 12GB、VM RAM 47.05 GiB、無 swap；T2V/I2V audio on，R2V audio off。|T2V 2175.5/2176.2s、I2V 2373.7/2378.1s、R2V 2581.8/2579.8s；峰值 VRAM 10,863–11,649 MiB，RAM 43,587–43,910 MiB；每項兩次 raw runs。|三任務不同日期／輸入／audio 狀態，作者明示不是 controlled task comparison；仍是完整 workflow＋硬體 ledger。|
|SOC03 [Reddit H3→LTX 2.3](https://www.reddit.com/r/StableDiffusion/comments/1vejlal/minimax_h3_ltx_23_spatial_upscale_yes/)|RTX 4080S 16GB、RAM 64GB；標準 ComfyUI H3 I2V + LTX 2.3 spatial upscale；workflow 公開於 Pastebin。|H3 736×736、0.5MP、5s、20 steps 約 205s；LTX 2.3 3 steps 約 125s；作者提供可下載 graph。|沒有固定 seed／量化檔名／peak RAM；是 pipeline timing，不是 H3 與 LTX 的畫質 benchmark。|
|SOC04 [Reddit H3 int8→LTX→RTX VSR](https://www.reddit.com/r/StableDiffusion/comments/1vj2ldp/an_unexpected_find_minimax_h3_ltx_23_upscale_rtx/)|RTX 4080S 16GB、RAM 64GB；H3 int8 T2V/R2V + LTX2.3 + Comfy RTX VSR。|H3 0.7MP、10s 約 12:40；LTX ×1.5 3:46；RTX VSR ×1.5 <10s；總 2K 2592×1440 約 16 min；有 YouTube full-res 與 workflow links。|單次／single user、無 seed/steps/frames；LTX 會引入音訊路徑問題，作者與留言提到可把原 H3 audio passthrough。|
|SOC05 [ai-muninn FastH3 vs base](https://ai-muninn.com/en/blog/fasth3-rtx-5090-comfyui)|作者 RTX 5090 32GB、Windows、ComfyUI 0.37；FastH3 V2、原 H3 pruned NVFP4；同 first frame、同 Mandarin line、5s/124 frames、warm、兩 seeds。|1344×768：FastH3 8 steps 59.8/57.4s；原 H3 20 steps 166.3/168.2s，原 H3 10 steps 90.1/83.6s；包含 text encode/decode/save。832×480 FastH3 V2 18.7/18.7s；作者用 Whisper 檢查 Mandarin。|作者是第一手 blog，GPU 非 target；V2/Trim 是 distilled FastH3，未測 distilled Ref2VA；主觀觀看「可用」，無客觀畫質 metric。|
|SOC06 **資源數據不一致，不採為benchmark** [MiniMax H3 ComfyUI 50-clip test](https://minimaxh3.co/open-source/comfyui)|作者工程團隊在 RTX 4090 測 raw MiniMaxAI weights（FP8 diffusion + NVFP4/AWQ TE）；Comfy lowvram，20 steps。|608×352、20.75s 約 353s／峰值 46,250 MiB；5s/124 frames 55.6s／41,546 MiB；960×544 24 min／48,490 MiB。50 clip sweep 覆蓋 motion、dialogue、sports、hands、text、duration。|主代理讀到頁面明寫單RTX4090／24GB，卻把41,546–48,490MiB標為Peak VRAM，內部矛盾。未釐清是否誤標RAM／staging footprint；硬體／耗時表不納入可用benchmark。50-clip與品質也僅是該站自述，作者身份／原始workflow未驗。|
|SOC07 [WanGP／Wan2GP release notes](https://github.com/lucazin/Wan2GP)|WanGP 同時支援 Wan 2.1/2.2、LTX-2、MiniMax H3；H3 以 pruned/full、INT8/FP8/GGUF/NVFP4 選擇；含 control video、depth/generic control、Ref2VA、RAM/VRAM priority。|此fork的 release note 報 H3 5s/124 frames/832×480 約 5–6GB VRAM、15s 約 8–9GB；W4A8 需 RTX 30+ 相容 INT8 kernel；Ref2VA reference pixel budget 可把速度改善至約 2×；官方 profile 尚待更成熟。|此為`lucazin/Wan2GP` fork的changelog；canonical請見09的INF18，不以此fork確認目前版本。不是完整同 seed render ledger；時間／RAM／精度組合沒有逐 run 固定，且低 VRAM 數字是作者宣稱。|

## blocked／discovery-only

|平台／來源|結果|可用程度|
|---|---|---|
|X search：`MiniMax H3`、`MiniMax-H3`、`FastH3`、日文量化／VRAM／workflow，並排除 `/i/`、`trending`|搜尋引擎仍主要返回 `x.com/i/trending` 的 Grok 自動摘要；摘要只露出 super_bonochin、TlanoAI、Kin no Niwatori、Hirokazu Yokohara/aigeboku 等 handle 和「12GB／6→2.5 min」線索，沒有原 status URL／完整條件。|snippet-only lead，未納入數字或品質 claim。|
|Facebook public groups/posts：H3／FastH3、ComfyUI、public model/workflow、VRAM/time、L4|一輪寬查只返回舊的台灣 Stable Diffusion 討論、無關 Wan2.2/Q4 貼文或 login wall；沒有可讀 H3 原帖。|blocked/search boundary；不代表 Facebook 全站不存在資料。|
|YouTube／Bilibili／Civitai 定位|可找到「8GB workflow」YouTube 標題與 Civitai workflow 連結；Bilibili 查詢只返回無關平台／舊文件，Civitai 多為 workflow 索引而非可讀測試正文。沒有登入或繞牆。|actual result URL 可作 discovery，不能支持量化品質或性能。|

## Search boundary 與缺口

查詢分三輪：X（英文／日文術語與 handles）、Facebook（擴大到 public model/workflow/case）、作者同步來源（GitHub、Reddit、YouTube、Civitai、Bilibili；H3、FastH3、Wan/Wan2GP、LTX、control、ComfyUI）。X／FB 在一輪擴展後只重複摘要或 blocked，已停止。主要新 evidence 是 SOC01、SOC02、SOC05、SOC07 的 workflow／resource 條件，以及 SOC03/04 的 H3＋LTX 跨 family 實測；仍缺公開可讀、同一 L4/A100 + High RAM 的 H3/FastH3 與 Wan/LTX/control 同 seed 影片對照。


主代理補充核查：SOC06保留作「原頁自述且資源欄內部不一致」的線索，未用於L4／A100候選判斷。SOC07為fork資料，與canonical Wan2GP版本分開。

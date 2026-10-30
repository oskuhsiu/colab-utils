# Colab 單張 A100：近期影片生成模型與玩家變種試用表

查證基準日：**2026-10-11，Asia/Taipei**。目標是製作影片，優先評估文字生影片（T2V）、圖片生影片（I2V），以及實際可用的畫面、動作、人物一致性與生成成本。

## 1. 先看結論與使用範圍

**首選起點：L01，LTX-2.5 Distilled INT8 ConvRot + Conv VAE。** 先與 H01 的 MiniMax H3 PDD 8 步、H02 的 Larry Turbo v4 EMA 6 步比較。C01 的 Kandinsky 6 Lite Distill 用來確認新一代小模型的效率；再試 C02 的 Pro INT8 玩家轉檔。

這是根據模型結構、現有整合與硬體限制排出的**試用順序**，不是已實測的 A100 排名。本文件查過來源、權重清單、版本、工作流與程式介面；**沒有在 Colab/A100 上安裝或生成影片**。任何「作者較好／較快」的主張，仍需用下方同一套題目驗證。

時間規則：優先 **2026-07-11～2026-10-11** 的新模型或實質變種；最早只接受 **2026-04-11**。日期按模型釋出或權重提交判斷，不能用 README 更新日期、倉庫建立日期或舊權重重新上傳日期充數。LTX-2.5 的官方發表月份為 2026-08；H3 官方公告在 7/31，社群可用權重與變種在 8 月起；Kandinsky 6 在 10/6 正式釋出。Bernini-R 是 6/1 的實質微調，底模 Wan2.2 較舊，單獨標示。

硬體預設是 **A100 40GB、單 GPU、僅推論**。worker 必須先讀取實際 VRAM、CPU RAM、剩餘磁碟、driver 與 PyTorch 版本。A100 80GB 的結果另記，不可混在同一排行榜。以下 RAM 值是安排測試的建議門檻，不是量測峰值或成功保證。

「開源模型」在本文件包含開放權重：LTX-2.5、H3 有自訂授權，Kandinsky 6 主模型為 MIT，Bernini 為 Apache-2.0。玩家轉檔不會自動改變底模授權。遇到 gated 模型須用已獲授權的 Hugging Face 帳號；本文件不替使用者接受條款。

**不用再搜尋安裝文章。** 下載與安裝仍需要網路；確切來源、版本、檔名、設定、範例工作流和執行程式都列在本文。從指定來源下載後，可以直接閱讀固定版本內附的程式及文件。

## 2. 建議嘗試列表

P0 先完成；P1 接著比較；P2 最後測。先跑每列一支約 5 秒的 T2V 影片，再測 I2V；進入決選才增加 seed。相同底模的量化、VAE、LoRA 和工作流配置是不同「測試配置」，不是不同基礎模型。

| ID／優先級 | 模型與變種 | 實質版本時間 | 執行器／初始採樣 | A100 40GB 的工作條件與測試目的 |
| --- | --- | --- | --- | --- |
| **L01／P0** | **LTX-2.5 22B Distilled，官方 INT8 ConvRot DiT + INT8 Gemma4 + Conv VAE** | 2026-08，新底模 | ComfyUI；官方兩階段 **8+3 步**，CFG 1 | CPU 分階段卸載；RAM 建議 ≥48GB，64GB 較有餘裕。主模型檔 20.03GiB。最先找「品質／效率」的實用基線 |
| L02／P1 | L01 改用官方 Diffusion Video VAE | 同上 | 同 L01，僅換 video VAE | 比較細節、紋理與解碼成本；保留 decoder 的額外耗時，不可算成免費品質提升 |
| L03／P1 | realrebelai LTX-2.5 **GGUF Q6_K** | 2026-08-12，玩家量化 | ComfyUI-GGUF；同 L01 | DiT 17.38GiB；檢查是否比官方 INT8 更省記憶體且品質可接受。只換 transformer，TE 與 VAE 保持一致 |
| L04／P2 | joeygambino LTX-2.5 **mix4x8-17GB** | 2026-08，玩家混合量化 | ComfyUI 原生 loader；同 L01 | 檔案實為 15.84GiB；A100 的實際量化 kernel／cast 路徑待測。這是實驗項，不把作者的重建誤差當成影片品質分數 |
| L05／P2 | L01 的**單階段 8 步**配置 | LTX-2.5 的採樣配置 | ComfyUI；直接在輸出解析度生成，CFG 1 | 與兩階段比較速度、構圖和細節；單階段跑全解析度，不能預先假設一定比 8+3 快 |
| **H01／P0** | **MiniMax H3 FL2VA Pruned rank8 INT8 + PDD 8-Step** | 2026-08-26，PDD；8 月的 pruned | **WanGP**；Euler、固定 8 步、CFG 1 | 原 33B 模型的玩家剪枝／量化推論方案；主模型 19.61GiB。RAM 建議 ≥64GB。PDD heads 與 LoRA 都要載入 |
| **H02／P0** | **H3 Comfy Pruned INT8 + Larry Turbo v4 step600 EMA** | 2026-08-07，玩家蒸餾 | ComfyUI + Larry 專用節點；**6 步**、simple、strength 1 | 主模型 19.53GiB；RAM 建議 ≥64GB。人物與細節的主要候選；再以 8 步驗證快速動作、音訊 |
| H03／P1 | H3 WanGP Pruned INT8 + **LightX2V FL2V 4-step v1.2 768p** | **2026-09-04**，較新的實質 LoRA | WanGP；4 步、Euler、video shift 6、CFG 1 | 比老 v0.1、v1.0 更值得先試的四步版；第一次用 480p 檢查執行，再到 1344×768。四步的動作與聲音損失另記 |
| H04／P1 | H3 Comfy Pruned INT8 + **LightX2V 8-step v1.0，非 768p 特製版** | 2026-08，8 步蒸餾 | ComfyUI；8 步、Euler/simple、shift 12/3、LoRA 1 | 選用官方 Comfy 模板已使用的八步檔，作四步版的品質對照。不要把檔名近似的 8/27「768p」版偷偷替換進來 |
| H05／P2 | H3 Pruned INT8 + **drbaph HyperFlow 8-step pruned Comfy 轉檔** | 原 HyperFlow **9/17**；Comfy 轉檔 9 月 | ComfyUI；固定 manual sigmas、8 步、Euler、LoRA 1 | 比較 9 月的新加速方法。原 HyperFlow 有雙時間 conditioning；這列是社群轉檔，不能視為原版 pipeline 的完全等價結果 |
| H06／P1，品質對照 | H3 Comfy Pruned INT8，**不加加速 LoRA** | 2026-08 的新底模／剪枝版 | ComfyUI；20 步、Euler/simple、CFG 1 | H02/H04/H05 的對照組；檢查少步蒸餾是否造成臉、動作、材質或音訊損失 |
| H07／P2 | H02 改用 **H3 Pruned W6A8** | **2026-09-29**，新的量化權重 | ComfyUI；Larry 6 步，其他相同 | DiT 14.89GiB。只改 DiT 量化，以測記憶體／cast 成本和畫面損失；A100 執行路徑未實測 |
| **C01／P0** | **Kandinsky 6 Lite Distill 3B BF16** | **2026-10-06**，新底模 | 官方 Comfy 擴充；**PiFlow 10 NFE**、CFG 1 | DiT 5.94GiB；RAM 建議 ≥32GB。864×480、121 frames、24fps；新小模型效率基線，含原生音訊 |
| C02／P1 | **Kandinsky 6 Pro Distill 29B，DeepBeepMeep INT8 ConvRot** | 底模 10/6；量化 **10/8** | 官方 Comfy 擴充 + 原生 UNETLoader；PiFlow 10 NFE | DiT **29.29GiB**，CPU offload，RAM 建議 ≥64GB。已讀 header 確認 `comfy_quant_v1`，但尚未 GPU 實跑，先做相容性檢查 |
| C03／P2，條件式 | Kandinsky 6 Pro Distill，官方 BF16 | 2026-10-06 | 同 C02，PiFlow 10 NFE | DiT **56.20GiB**，40GB 無法整個常駐 GPU；CPU／block offload。40GB 測試建議 RAM ≥96GB；不足就 SKIP_RESOURCE。80GB 也保留分階段卸載 |
| B01／P2，功能試驗 | **Bernini-R 14B，WanGP 高／低噪 INT8 版** | 底模微調 **2026-06-01**；玩家量化 6/4 | WanGP；40 步、UniPC、CFG 4/4、shift 5 | 六個月內的舊 Wan2.2 實質新變種。測參考圖生影片／影片修改；只有 renderer，不需 full Bernini 的 MLLM planner。沒有原生聲音 |

初始產出配置：LTX 輸出 **896×512、121 frames、24fps**，兩階段第一階段 **448×256**；H3 **832×480、124 frames、24fps**；Kandinsky 6 **864×480、121 frames、24fps**；Bernini **832×480、81 frames、16fps**。這些都是約 5 秒，解析度與幀數依各自合法規格，**不是完全相同計算量**。回報時列出實際像素、fps、時長。

製作用第二輪：LTX **1280×704**（兩階段第一階段 640×352），H3 **1344×768**，幀數不變。Kandinsky 6 的主測保持官方 SD 設定；它的 Full-HD 是額外 SR 流程，另行計時，不當成原生 Full-HD 的生成能力。

## 3. 執行前需要理解的差異

| 名稱 | worker 應採取的處理 |
| --- | --- |
| 量化（INT8／GGUF／W6A8／mixed） | 主要改變權重記憶體與數值。A100 沒有 Hopper/Ada 的原生 FP8 計算能力；儲存 FP8 可以 cast 後跑，但不等於原生 FP8 加速 |
| 蒸餾／Turbo LoRA | 必須配對底模、變種與採樣。一次只開一套加速 LoRA；不能把 PDD、Turbo、HyperFlow 疊在一起 |
| Pruned | H3 削減／預計算 AdaLN 等推論部分；不同 repack 不是逐位元相同的底模。WanGP rank8 與 Comfy pruned 分別使用自己的相容方案 |
| WanGP、ComfyUI、LightX2V | 是執行器／整合工具，不是影片模型。記憶體卸載與 kernel 會影響結果與速度，必須記錄 |
| LTX 8+3 | 第一階段 8 次 DiT 去噪，再做 latent upsample 與 3 次 refinement；Diffusion VAE 還有 decoder 成本。不能整條流程報成「只跑 8 步」 |
| NVFP4 | LTX 的 NVFP4 DiT 是 Blackwell 路線，不列入 A100。**H3 Qwen TE 的 `nvfp4_awq` 是例外：Comfy 作者明示不需 Blackwell**；仍是另一個量化配置，不能替換後假裝與 INT8 TE 相同 |

先關閉 prompt enhancer、風格 LoRA、畫面插幀、外部放大、face refiner、TeaCache/MagCache/First Block Cache 和自動聲音修復。主測先用 SDPA。若要測 SageAttention2 或 cache，等模型成功生成後另開配置；保留相同 prompt/seed 做 A/B。

## 4. 已查過，但不排入主清單

| 模型／玩家方案 | 原因 |
| --- | --- |
| HunyuanVideo 1.5、官方 480p I2V step-distill、LightX2V 4-step T2V | 現有相關權重主要為 2025-11～12；不符合此次六個月窗口。CFG-distilled 仍是 50 步，不能誤稱 8 步 |
| Wan2.2 TI2V 5B、老 A14B、Seko Lightning v1/v1.1/v2 | 底模與這些蒸餾版主要在 2025 年；此次不以老經典占用主測資源 |
| Enhanced Lightning v2、Rapid AllInOne | 沒有足夠證據把相關核心權重算成最近六個月的實質改版；Rapid 作者亦已標示停止維護。單一合併檔的方便性不構成新鮮度 |
| LightX2V Wan2.2 720p 4-step `260412` | **符合六個月窗口**：權重 4/12、公告 4/20。作者供新高／低噪 BF16 pair；此次沒有核對到對應新 720p 權重的同版 Comfy 量化。先不拿 2025 年 FP8 檔冒充新 720p 版 |
| LightX2V Wan2.2 NVFP4 QAT + sparse | 5/29 是實質新變種，硬體目標為 Blackwell；A100 不採用其專用 NVFP4 快速路徑 |
| Helios-Distilled、LTX-2.3 | 核心釋出在 2026 年 2～3 月；7 月格式／整合更新不能重新計算底模年齡 |
| FastH3 VSA preview、VDN-H3 | 是近期真變種，也已查過；但專用 attention、preview／架構模組需要另一條驗證線。H100/H200/B200 多卡速度不能換算成 Colab A100 單卡速度。第二批再研究，不混入這次可直接執行的核心矩陣 |
| Prism preview-alpha/beta | 2026-10 新模型；官方單卡 720p 配置以 **80GB GPU + CPU offload** 為條件，1080p/2K 建議多卡 FSDP。先不排到 40GB 的必跑項 |
| Viggle Animate、H3 character-swap/person-remover、LTX Ripple／控制／修復 LoRA | 各有用途，但輸入與評分屬動作轉移、影片編輯或特效。等一般 T2V/I2V 主模型選出後，按實際影片需求增加 |

## 5. 固定程式與來源版本

### 5.0 worker 的起始步驟

先把本檔放在 `/content/video_trials/trials.md`，再在 Colab 執行下面 cell；它會取出本文七支腳本，並從測試表建立 `prompts/T01.txt`～`T05.txt`、`A01.txt`～`A05.txt`。不會下載模型。後續指令都從 `/content/video_trials` 執行。

```python
from pathlib import Path
import re

trial_root = Path('/content/video_trials')
trial_root.mkdir(parents=True,exist_ok=True)
document = (trial_root/'trials.md').read_text(encoding='utf-8')
for filename,language,body in re.findall(r'<!-- FILE:([A-Za-z0-9_.-]+) -->\s*```(python|bash)\s*\n(.*?)\n```',document,re.S):
    (trial_root/filename).write_text(body+'\n',encoding='utf-8')
for folder in ['jobs','prompts','logs','renders']:
    (trial_root/folder).mkdir(exist_ok=True)
for line in document.splitlines():
    cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
    if len(cells)==4 and re.fullmatch(r'T0[1-5]',cells[0]):
        (trial_root/'prompts'/f'{cells[0]}.txt').write_text(cells[2]+'\n',encoding='utf-8')
        (trial_root/'prompts'/f'A{cells[0][1:]}.txt').write_text(cells[3]+'\n',encoding='utf-8')
print('Scripts and T2V prompts prepared:',trial_root)
```

建議第一個完整工作：執行 `setup_comfy.sh` → 下載 L01 assets → 前景啟動 Comfy → `make_ltx_job.py` 產生 L01 API JSON → `run_comfy.py` 送件 → 查看原片並填紀錄。環境、模型權重、生成分開處理；成功後按 P0/P1/P2 排程。WanGP 的 H01/H03 改用其專用 venv 與 builder。

不要執行未固定版本的 `git pull`。若必須修復相容問題，另建一份 runtime，記錄新的 commit 和失敗原因。

| 元件 | 固定 Git commit | 用途 |
| --- | --- | --- |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI) | `7f7fd918ed0815c5d5ef2ccfe44bfc8e72cfd217`，0.39.0 | LTX／H3／Kandinsky 執行器 |
| [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) | `3bf3ca62595f1764c47d01c35c8e5dfe47e1a88f` | 官方 LTX 節點與 decoder 支援 |
| [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | `6ea2651e7df66d7585f6ffee804b20e92fb38b8a` | L03；已核對 loader 會傳遞 GGUF scalar metadata |
| [ComfyUI-MiniMax-H3-Turbo](https://github.com/larryvrh/ComfyUI-MiniMax-H3-Turbo) | `4274783a23afcfdbea3b4876cb79effd6c510785` | H02/H07；保留 repo 內 `h3_silu_temb_grid.safetensors` |
| [kandinsky-6](https://github.com/kandinskylab/kandinsky-6) | `f19c9b8ec2fcea5d391f5391983a540fc5e004da` | **只把 `comfyui/` 複製為擴充**，不用安裝其 Python 3.13 CLI pipeline |
| [Wan2GP](https://github.com/deepbeepmeep/Wan2GP) | `6479db36bdc2619a904a852bba9c2d78e1a83f82` | H01/H03/B01；原生 headless queue |
| [workflow_templates](https://github.com/Comfy-Org/workflow_templates) | `00309dce76e9c4f436dc85144d39eccc863fb304` | 本地工作流；不選 `api_*` 付費服務模板 |

### 5.1 Colab 環境

以下 Bash 放在 Colab `%%bash` cell。另建 venv，不覆蓋 notebook 的 Python。`nvidia-smi` 顯示的 CUDA 是 driver 能支援的版本，不是現在 PyTorch 的 CUDA runtime；兩者都要保存。

先做一次盤點：`nvidia-smi`、`free -h`、`df -h /content`。每個模型家族至少預留約 100GB 可用磁碟；不要一口氣下載全表。若可用磁碟不足，先跳過或搬移已完成且可重下載的權重，保留影片、設定和結果。不要刪除其他專案資料。

<!-- FILE:setup_comfy.sh -->
```bash
set -euo pipefail
VIDEO_TRIAL_ROOT=/content/video_trials
mkdir -p "$VIDEO_TRIAL_ROOT/logs" "$VIDEO_TRIAL_ROOT/renders"
python -m pip install uv
uv venv "$VIDEO_TRIAL_ROOT/venv_comfy" --python 3.12
VIDEO_TRIAL_PY="$VIDEO_TRIAL_ROOT/venv_comfy/bin/python"

# 起始建議 cu130。driver 最大支援 12.8／12.6 時改 cu128／cu126。
# 最大支援低於 12.6 記 BLOCKED_DRIVER；不更換 Colab host driver。
VIDEO_TRIAL_TORCH_INDEX=cu130
uv pip install --python "$VIDEO_TRIAL_PY" torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 \
  --index-url "https://download.pytorch.org/whl/$VIDEO_TRIAL_TORCH_INDEX"

git clone https://github.com/Comfy-Org/ComfyUI.git "$VIDEO_TRIAL_ROOT/ComfyUI"
git -C "$VIDEO_TRIAL_ROOT/ComfyUI" checkout 7f7fd918ed0815c5d5ef2ccfe44bfc8e72cfd217
uv pip install --python "$VIDEO_TRIAL_PY" -r "$VIDEO_TRIAL_ROOT/ComfyUI/requirements.txt"

git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/ComfyUI-LTXVideo"
git -C "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/ComfyUI-LTXVideo" checkout 3bf3ca62595f1764c47d01c35c8e5dfe47e1a88f
uv pip install --python "$VIDEO_TRIAL_PY" -r "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/ComfyUI-LTXVideo/requirements.txt"

git clone https://github.com/city96/ComfyUI-GGUF.git "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/ComfyUI-GGUF"
git -C "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/ComfyUI-GGUF" checkout 6ea2651e7df66d7585f6ffee804b20e92fb38b8a
uv pip install --python "$VIDEO_TRIAL_PY" -r "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/ComfyUI-GGUF/requirements.txt"

git clone https://github.com/larryvrh/ComfyUI-MiniMax-H3-Turbo.git "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo"
git -C "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo" checkout 4274783a23afcfdbea3b4876cb79effd6c510785

git clone https://github.com/kandinskylab/kandinsky-6.git "$VIDEO_TRIAL_ROOT/kandinsky-6-source"
git -C "$VIDEO_TRIAL_ROOT/kandinsky-6-source" checkout f19c9b8ec2fcea5d391f5391983a540fc5e004da
cp -a "$VIDEO_TRIAL_ROOT/kandinsky-6-source/comfyui" "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/kandinsky6"
uv pip install --python "$VIDEO_TRIAL_PY" -r "$VIDEO_TRIAL_ROOT/ComfyUI/custom_nodes/kandinsky6/requirements.txt"
uv pip check --python "$VIDEO_TRIAL_PY"
uv pip freeze --python "$VIDEO_TRIAL_PY" > "$VIDEO_TRIAL_ROOT/logs/comfy-pip-freeze.txt"
"$VIDEO_TRIAL_PY" -c 'import torch; print(torch.__version__, torch.version.cuda); print(torch.cuda.get_device_name(), torch.cuda.get_device_capability()); print(torch.cuda.get_device_properties(0).total_memory/2**30)'
```

**注意依賴安裝可能調整 PyTorch。** 安裝完再讀一次版本；若離開 2.10.0，先解決衝突，不把不同 runtime 的時間混在一起。上方 `uv pip freeze` 指向實際的 venv，不依賴 venv 內另有 pip。

若 cu128／較舊 driver 在 import `comfy-kitchen` 出現二進位 driver 錯誤，使用**同版官方 Python-only wheel**，保留 GPU 推論但可能失去專用 kernel。只在這個錯誤發生時執行：

```bash
uv pip install --python /content/video_trials/venv_comfy/bin/python --reinstall --no-deps \
  https://files.pythonhosted.org/packages/9e/08/0a904ae1a1b82f57e7990eee8d93d48466a185934aa585cc625cdb27761e/comfy_kitchen-0.2.37-py3-none-any.whl
```

不能因 Python-only fallback 成功 import 就宣稱 INT8 有硬體加速。若某個量化 kernel 仍不支援，記 `BLOCKED_KERNEL`，繼續可跑的 GGUF／BF16 小模型，不強行改權重。

啟動 ComfyUI（首次先在前景看 custom node 載入是否成功）：

```bash
cd /content/video_trials/ComfyUI
/content/video_trials/venv_comfy/bin/python main.py \
  --listen 127.0.0.1 --port 8188 --use-pytorch-cross-attention \
  --disable-dynamic-vram --reserve-vram 3
```

這裡固定關掉新 dynamic VRAM 路徑，讓初始比較使用同一種傳統記憶體管理。若遇 OOM，再試 `--lowvram`，並把它記為另一個配置；這個旗標會讓 text encoder 上 CPU，速度可能改變。Colab 控制 UI 可在 notebook 使用 `google.colab.output.serve_kernel_port_as_iframe(8188, height=900)`；headless worker 直接用 localhost API 即可。

### 5.2 WanGP 環境與執行

H01/H03 另用 Python 3.11.14 venv；Torch 仍固定 2.10.0/0.25.0/2.10.0，以 driver 支援的 cu130 或 cu128 wheel 安裝。Comfy 和 WanGP 不同時占用同一張 GPU。

<!-- FILE:setup_wangp.sh -->
```bash
set -euo pipefail
VIDEO_TRIAL_ROOT=/content/video_trials
mkdir -p "$VIDEO_TRIAL_ROOT/logs" "$VIDEO_TRIAL_ROOT/renders"
python -m pip install uv
uv venv "$VIDEO_TRIAL_ROOT/venv_wangp" --python 3.11.14
VIDEO_TRIAL_PY="$VIDEO_TRIAL_ROOT/venv_wangp/bin/python"
VIDEO_TRIAL_TORCH_INDEX=cu130  # 同前：driver 最大支援 12.8／12.6 時改 cu128／cu126
uv pip install --python "$VIDEO_TRIAL_PY" torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url "https://download.pytorch.org/whl/$VIDEO_TRIAL_TORCH_INDEX"
git clone https://github.com/deepbeepmeep/Wan2GP.git "$VIDEO_TRIAL_ROOT/Wan2GP"
git -C "$VIDEO_TRIAL_ROOT/Wan2GP" checkout 6479db36bdc2619a904a852bba9c2d78e1a83f82
uv pip install --python "$VIDEO_TRIAL_PY" -r "$VIDEO_TRIAL_ROOT/Wan2GP/requirements.txt"
uv pip check --python "$VIDEO_TRIAL_PY"
uv pip freeze --python "$VIDEO_TRIAL_PY" > "$VIDEO_TRIAL_ROOT/logs/wangp-pip-freeze.txt"
```

WanGP 固定的是 `comfy-kitchen==0.2.35`，與 Comfy venv 的 0.2.37 分開。若 cu128/cu126 import 時遇到同類 driver 二進位錯誤，僅在 WanGP venv 改裝**官方同版 Python-only wheel**：

```bash
uv pip install --python /content/video_trials/venv_wangp/bin/python --reinstall --no-deps \
  https://files.pythonhosted.org/packages/14/60/8f075cceb07cb78d3792446b1156b7f5a41b260ac60645ef1483e34f71ce/comfy_kitchen-0.2.35-py3-none-any.whl
```

第一次可啟動 `python wgp.py --profile 4 --attention sdpa`，確認配置中的 DiT/TE 量化都是 INT8，VAE 使用 INT8 ConvRot 或 Auto，關閉 cache、prompt enhancer 和額外 phase。**不要開 Deepy 或另外下載 prompt rewriter LLM。** 生成設定 JSON 與全域記憶體／量化配置不是同一份檔案；都要保存。

H01/H03 可直接從下方 `make_wangp_job.py` 產生 JSON，之後在 Wan2GP 目錄執行：

```bash
/content/video_trials/venv_wangp/bin/python wgp.py --process /content/video_trials/jobs/H01.json --dry-run --profile 4 --attention sdpa
/content/video_trials/venv_wangp/bin/python wgp.py --process /content/video_trials/jobs/H01.json --output-dir /content/video_trials/renders/H01 --profile 4 --attention sdpa
```

`--dry-run` 只代表設定／佇列驗證，**不代表權重、GPU、kernel 或生成品質通過**。退出碼 0 為工作成功、1 為出錯、130 為中斷。輸入圖片路徑須能在執行主機讀取；使用絕對路徑最省事。

## 6. 權重下載清單

下表的 R 編號指向固定 revision；附錄 manifest 含完整檔名、目的路徑、實際 bytes 和可取得的 LFS SHA-256。容量是權重檔案大小，**不是峰值 VRAM**。Comfy assets 與 WanGP repack 不互換。
| R | Hugging Face 倉庫 | 固定 revision |
| --- | --- | --- |
| R1 | [Lightricks/LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5) | `2356ce76915d6c48d313d7e8b25900e1dd3abaa8` |
| R2 | [realrebelai/LTX-2.5_GGUFs](https://huggingface.co/realrebelai/LTX-2.5_GGUFs) | `112436f97aaf99ce13ecb7b7eca7e2f6c128d3ec` |
| R3 | [joeygambino/LTX-2.5-Quantized](https://huggingface.co/joeygambino/LTX-2.5-Quantized) | `00f505424717d526f7b00f51c415de789c3f661c` |
| R4 | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) | `e5eb578a89295337b8ff433a035929ce0279e0b6` |
| R5 | [larryvrh/MiniMax-H3-Turbo-Lora](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora) | `43a74557ac3f6539db8e0f2a959d03feb7a81480` |
| R6 | [drbaph/MiniMax-H3-Turbo-Lora-ComfyUI](https://huggingface.co/drbaph/MiniMax-H3-Turbo-Lora-ComfyUI) | `bb2bc497cbaca89dadd0bcf1856eed4f8275be20` |
| R7 | [lightx2v/Minimax-h3-Turbo](https://huggingface.co/lightx2v/Minimax-h3-Turbo) | `3ec17a324ced54151364f24f8b5fb6bf7e26414f` |
| R8 | [DeepBeepMeep/MiniMax-H3](https://huggingface.co/DeepBeepMeep/MiniMax-H3) | `adc81ccb71352192214d83d5fafb9487e860be39` |
| R9 | [kandinskylab/Kandinsky-6.0-Lite-distill-5s-Diffusers](https://huggingface.co/kandinskylab/Kandinsky-6.0-Lite-distill-5s-Diffusers) | `efbaeb9961770cc82fece5b9cb2197049d8c983c` |
| R10 | [kandinskylab/Kandinsky-6.0-Pro-distill-5s-Diffusers](https://huggingface.co/kandinskylab/Kandinsky-6.0-Pro-distill-5s-Diffusers) | `1018d5828716e8bea3de99609f45c924de9c5564` |
| R11 | [DeepBeepMeep/Kandinsky6](https://huggingface.co/DeepBeepMeep/Kandinsky6) | `66912fedfbb8cbe7fa699eb0e25a53042d7cd1a4` |
| R12 | [Comfy-Org/Qwen-Image_ComfyUI](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI) | `1f12b17be14c89b026c51a91d67c32f84bb047bc` |
| R13 | [Comfy-Org/HunyuanVideo_repackaged](https://huggingface.co/Comfy-Org/HunyuanVideo_repackaged) | `533a43813f01517d9e624f9e824a85bb94094120` |
| R14 | [hkchengrex/MMAudio](https://huggingface.co/hkchengrex/MMAudio) | `eb13a1a98fdbec91753775c57b074ccdfc60587c` |
| R15 | [nvidia/bigvgan_v2_44khz_128band_512x](https://huggingface.co/nvidia/bigvgan_v2_44khz_128band_512x) | `95a9d1dcb12906c03edd938d77b9333d6ded7dfb` |
| R16 | [DeepBeepMeep/Wan2.2](https://huggingface.co/DeepBeepMeep/Wan2.2) | `cf8a5e27316cb4004227c31224050c6f266d9e54` |

| Asset ID | R | 精確來源檔名 | 安裝目的路徑（相對 `/content/video_trials`） | GiB |
| --- | --- | --- | --- | --- |
| L-D | R1 | `diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | `ComfyUI/models/diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | 20.03 |
| L-TE | R1 | `text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | `ComfyUI/models/text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | 14.32 |
| L-CV | R1 | `vae/ltx-2.5-video-vae-conv-bf16.safetensors` | `ComfyUI/models/vae/ltx-2.5-video-vae-conv-bf16.safetensors` | 1.35 |
| L-DV | R1 | `vae/ltx-2.5-video-vae-bf16.safetensors` | `ComfyUI/models/vae/ltx-2.5-video-vae-bf16.safetensors` | 1.37 |
| L-AV | R1 | `vae/ltx-2.5-audio-vae-bf16.safetensors` | `ComfyUI/models/vae/ltx-2.5-audio-vae-bf16.safetensors` | 0.34 |
| L-UP | R1 | `latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | `ComfyUI/models/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | 0.93 |
| L-Q6 | R2 | `LTX-2.5-Distilled-Q6_K.gguf` | `ComfyUI/models/unet/LTX-2.5-Distilled-Q6_K.gguf` | 17.38 |
| L-Q4 | R2 | `LTX-2.5-Distilled-Q4_K_M.gguf` | `ComfyUI/models/unet/LTX-2.5-Distilled-Q4_K_M.gguf` | 14.05 |
| L-M17 | R3 | `LTX25-distilled-DiT-comfy-mix4x8-17GB.safetensors` | `ComfyUI/models/diffusion_models/LTX25-distilled-DiT-comfy-mix4x8-17GB.safetensors` | 15.84 |
| H-D | R4 | `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `ComfyUI/models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 19.53 |
| H-W6 | R4 | `diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors` | `ComfyUI/models/diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors` | 14.89 |
| H-TE | R4 | `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | `ComfyUI/models/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | 25.28 |
| H-TE4 | R4 | `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `ComfyUI/models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 14.61 |
| H-V | R4 | `vae/minimax_h3_video_vae_int8_convrot.safetensors` | `ComfyUI/models/vae/minimax_h3_video_vae_int8_convrot.safetensors` | 2.62 |
| H-A | R4 | `vae/minimax_h3_audio_vae_fp32.safetensors` | `ComfyUI/models/vae/minimax_h3_audio_vae_fp32.safetensors` | 0.56 |
| H-LARRY | R5 | `minimax_h3_turbo_v4_step600_ema.safetensors` | `ComfyUI/models/loras/minimax_h3_turbo_v4_step600_ema.safetensors` | 0.73 |
| H-LX8 | R7 | `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | `ComfyUI/models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | 1.82 |
| H-HYPER | R6 | `minimax_h3_hyperflow_8step_v1.0_comfyui_pruned_bf16.safetensors` | `ComfyUI/models/loras/minimax_h3_hyperflow_8step_v1.0_comfyui_pruned_bf16.safetensors` | 3.64 |
| W-H3 | R8 | `MiniMax-H3-FL2VA-pruned_rank8_int8_convrot.safetensors` | `Wan2GP/ckpts/MiniMax-H3-FL2VA-pruned_rank8_int8_convrot.safetensors` | 19.61 |
| W-TE | R8 | `Qwen3-VL-32B-Instruct/Qwen3-VL-32B-Instruct-layer50_quanto_bf16_int8.safetensors` | `Wan2GP/ckpts/Qwen3-VL-32B-Instruct/Qwen3-VL-32B-Instruct-layer50_quanto_bf16_int8.safetensors` | 24.89 |
| W-V | R8 | `minimax_h3/minimax_h3_video_vae_int8_convrot.safetensors` | `Wan2GP/ckpts/minimax_h3/minimax_h3_video_vae_int8_convrot.safetensors` | 2.62 |
| W-A | R8 | `MiniMax-H3-audio_vae_fp32.safetensors` | `Wan2GP/ckpts/MiniMax-H3-audio_vae_fp32.safetensors` | 0.56 |
| W-UP | R8 | `minimax_h3/minimax_h3_latent_upscaler_3d_bf16.safetensors` | `Wan2GP/ckpts/minimax_h3/minimax_h3_latent_upscaler_3d_bf16.safetensors` | 0.64 |
| W-PDD | R8 | `minimax_h3_fl2va_pdd_8step_heads_bf16.safetensors` | `Wan2GP/ckpts/minimax_h3_fl2va_pdd_8step_heads_bf16.safetensors` | 0.04 |
| W-PDDL | R8 | `loras/minimax_h3_fl2va_pdd_8step_lora_bf16.safetensors` | `Wan2GP/loras/minimax_h3/minimax_h3_fl2va_pdd_8step_lora_bf16.safetensors` | 1.24 |
| W-LX4 | R8 | `loras/minimax_h3_lightx2v_fl2v_turbo_4step_alpha8_v1.2_768p_bf16.safetensors` | `Wan2GP/loras/minimax_h3/minimax_h3_lightx2v_fl2v_turbo_4step_alpha8_v1.2_768p_bf16.safetensors` | 1.29 |
| W-T1 | R8 | `Qwen3-VL-32B-Instruct/config.json` | `Wan2GP/ckpts/Qwen3-VL-32B-Instruct/config.json` | 0.00 |
| W-T2 | R8 | `Qwen3-VL-32B-Instruct/tokenizer.json` | `Wan2GP/ckpts/Qwen3-VL-32B-Instruct/tokenizer.json` | 0.01 |
| W-T3 | R8 | `Qwen3-VL-32B-Instruct/tokenizer_config.json` | `Wan2GP/ckpts/Qwen3-VL-32B-Instruct/tokenizer_config.json` | 0.00 |
| W-T4 | R8 | `Qwen3-VL-32B-Instruct/preprocessor_config.json` | `Wan2GP/ckpts/Qwen3-VL-32B-Instruct/preprocessor_config.json` | 0.00 |
| W-T5 | R8 | `Qwen3-VL-32B-Instruct/vocab.json` | `Wan2GP/ckpts/Qwen3-VL-32B-Instruct/vocab.json` | 0.00 |
| K-LITE | R9 | `transformer/diffusion_pytorch_model.safetensors` | `ComfyUI/models/diffusion_models/Kandinsky-6.0-Lite-distill-5s-Diffusers/transformer/diffusion_pytorch_model.safetensors` | 5.94 |
| K-PRO | R10 | `transformer/diffusion_pytorch_model.safetensors` | `ComfyUI/models/diffusion_models/Kandinsky-6.0-Pro-distill-5s-Diffusers/transformer/diffusion_pytorch_model.safetensors` | 56.20 |
| K-PRO8 | R11 | `kandinsky6_pro_distill_int8_convrot.safetensors` | `ComfyUI/models/diffusion_models/kandinsky6_pro_distill_int8_convrot.safetensors` | 29.29 |
| K-TE | R12 | `split_files/text_encoders/qwen_2.5_vl_7b.safetensors` | `ComfyUI/models/text_encoders/qwen_2.5_vl_7b.safetensors` | 15.45 |
| K-CLIP | R13 | `split_files/text_encoders/clip_l.safetensors` | `ComfyUI/models/text_encoders/clip_l.safetensors` | 0.23 |
| K-V | R13 | `split_files/vae/hunyuan_video_vae_bf16.safetensors` | `ComfyUI/models/vae/hunyuan_video_vae_bf16.safetensors` | 0.46 |
| K-A | R14 | `ext_weights/v1-44.pth` | `ComfyUI/models/audio_vae/v1-44.pth` | 1.14 |
| K-VOC | R15 | `bigvgan_generator.pt` | `ComfyUI/models/audio_vae/bigvgan_vocoder/bigvgan_generator.pt` | 0.46 |
| K-VCFG | R15 | `config.json` | `ComfyUI/models/audio_vae/bigvgan_vocoder/config.json` | 0.00 |
| B-H | R16 | `bernini_r_wan2.2_high_quanto_bf16_int8.safetensors` | `Wan2GP/ckpts/bernini_r_wan2.2_high_quanto_bf16_int8.safetensors` | 13.53 |
| B-L | R16 | `bernini_r_wan2.2_low_quanto_bf16_int8.safetensors` | `Wan2GP/ckpts/bernini_r_wan2.2_low_quanto_bf16_int8.safetensors` | 13.53 |

小型 tokenizer/config 檔案顯示 0.00GiB，仍需下載。H3 WanGP 的原生 PDD 是 **heads + LoRA + 配對底模**；少掉 heads 不能當成 PDD 成功。模型放在 `Wan2GP/ckpts`，不是 `ckpt`。

Kandinsky 的 video VAE 來自**舊 HunyuanVideo** repack，是新模型沿用的零件；這不表示把舊 Hunyuan 基礎影片模型加回近期名單。它不是 HunyuanVideo 1.5 的 VAE。音訊需 `v1-44.pth` 與 BigVGAN 的權重、config 成套。

### 6.1 一次只下載一個 trial

把下方程式存成 `fetch_assets.py`，把這份 Markdown 保留在 `/content/video_trials/trials.md`。Hugging Face token 可透過 Colab secret `HF_TOKEN` 或現有登入取得，**不要印出 token**。範例：

```bash
/content/video_trials/venv_comfy/bin/python fetch_assets.py --md /content/video_trials/trials.md --trial L01 --root /content/video_trials
```

程式以 HF cache + symlink 避免重複權重；先做磁碟檢查，下載後檢查 bytes。第一次下載完成後，再加 `--verify-sha` 做一次完整 checksum；這個讀檔耗時不算生成速度。既有檔案不覆寫；有衝突就停止，避免誤換模型。

<!-- FILE:fetch_assets.py -->
```python
import argparse, hashlib, json, os, re, shutil
from pathlib import Path
from huggingface_hub import hf_hub_download

p = argparse.ArgumentParser()
p.add_argument('--md', required=True)
p.add_argument('--trial', required=True)
p.add_argument('--root', default='/content/video_trials')
p.add_argument('--verify-sha', action='store_true')
args = p.parse_args()
text = Path(args.md).read_text(encoding='utf-8')
match = re.search(r'<!-- ASSET_MANIFEST -->\s*```json\s*(.*?)\s*```', text, re.S)
if not match:
    raise SystemExit('Missing embedded asset manifest')
m = json.loads(match.group(1))
if args.trial not in m['trials']:
    raise SystemExit('Unknown trial: ' + args.trial)
root = Path(args.root).resolve()
root.mkdir(parents=True, exist_ok=True)
cache = root / 'hf_cache'
by_id = {a['id']: a for a in m['assets']}
chosen = [by_id[i] for i in dict.fromkeys(m['trials'][args.trial])]
need = sum(a.get('bytes') or 0 for a in chosen if not (root / a['dest']).exists())
if shutil.disk_usage(root).free < need + 5 * 2**30:
    raise SystemExit(f'SKIP_DISK: need about {need / 2**30:.1f} GiB plus 5 GiB reserve')
token = os.environ.get('HF_TOKEN')
if not token:
    try:
        from google.colab import userdata
        token = userdata.get('HF_TOKEN')
    except Exception:
        token = None
records = []
for a in chosen:
    repo = m['repos'][a['repo']]
    src = Path(hf_hub_download(repo_id=repo['repo_id'], revision=repo['revision'],
                              filename=a['file'], cache_dir=str(cache), token=token))
    expected = a.get('bytes')
    if expected is not None and src.stat().st_size != expected:
        raise RuntimeError('SIZE_MISMATCH: ' + a['id'])
    if args.verify_sha and a.get('sha256'):
        h = hashlib.sha256()
        with src.open('rb') as f:
            for block in iter(lambda: f.read(16 * 2**20), b''):
                h.update(block)
        if h.hexdigest() != a['sha256']:
            raise RuntimeError('SHA_MISMATCH: ' + a['id'])
    dest = root / a['dest']
    dest.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(dest):
        if dest.resolve() != src.resolve():
            raise RuntimeError('DESTINATION_CONFLICT: ' + str(dest))
    else:
        dest.symlink_to(src.resolve())
    records.append(dict(asset=a['id'], repo=repo['repo_id'], revision=repo['revision'],
                        filename=a['file'], bytes=src.stat().st_size, installed=str(dest)))
    print(a['id'], 'ready')
(root / 'logs').mkdir(exist_ok=True)
(root / 'logs' / f'assets-{args.trial}.json').write_text(
    json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
```

## 7. 各配置的操作細節

### 7.1 LTX-2.5

使用固定模板：

- T2V：<https://raw.githubusercontent.com/Comfy-Org/workflow_templates/00309dce76e9c4f436dc85144d39eccc863fb304/templates/video_ltx2_5_t2v.json>
- I2V：<https://raw.githubusercontent.com/Comfy-Org/workflow_templates/00309dce76e9c4f436dc85144d39eccc863fb304/templates/video_ltx2_5_i2v.json>

模板是 UI workflow JSON，包含 subgraph，**不能原封不動 POST 到 `/prompt`**。可以匯入 UI 後依 trial 調整，再匯出 API format；純 CLI worker 直接用本節 `make_ltx_job.py`。這個 builder 依固定模板的節點與連線建立平面 API graph，移除 prompt enhancer／前端 subgraph，保留兩階段 AV latent 流程。程式介面已靜態核對，實際載入與生成仍由 worker 驗證。

| ID | 需改的節點／參數 |
| --- | --- |
| L01 | UNETLoader 選 L-D；LTX text encoder 選 L-TE；video VAE 選 **L-CV**，audio VAE 選 L-AV；latent upscaler 選 L-UP。兩階段、prompt enhancer 關、影片/音訊 CFG 都 1；輸出 896×512，第一階段 448×256；兩個 sampler 都 `euler_ancestral` |
| L02 | 同 L01，只將 video VAE 改 L-DV。保留模板內 decoder 參數與 tiled decode；把 VAE decode 時間與額外迭代獨立記錄 |
| L03 | 同 L01，只以 `Unet Loader (GGUF)` 替換 UNETLoader，選 L-Q6。不可拿沒有 LTX-2.5 `config` metadata 的任意 GGUF。Q6 OOM 且卸載無效才試 `L03-Q4`，另記結果 |
| L04 | 同 L01，只選 L-M17 原生 safetensors。首次 `weight_dtype=default`，不再加第二次量化；保留載入／kernel 日誌 |
| L05 | 使用 L01 第一階段的輸出路徑，取消 latent upsample 和第二階段 refinement，第一階段改為最終 896×512，直接接相同 AV split/decode/save。保留第一階段 sigma 序列 |

LTX 固定 sigma 序列：

```text
stage 1: 1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0
stage 2: 0.85, 0.7250, 0.4219, 0.0
```

9 個 sigma 點是 8 個去噪區間；4 個點是 3 個區間。**不用普通 scheduler 用 steps=8 重新生一條近似曲線**。frames 必須 `%8 == 1`，width/height 要除以 32 整除；兩階段最終尺寸用 64 的倍數，方便第一階段除以二。TE 要用 **LTX-2.5 的 Gemma4 with projection**，不換 Gemma3、一般 Gemma4 或 LTX-2.3 的文字編碼器。

896×512 的初始測試不代表模型最高品質；成功後測 1280×704。前者每幀 458,752 pixels、後者 901,120 pixels，性能比較須標明。不要默默把 704 改成不符合尺寸限制的 720。

<!-- FILE:make_ltx_job.py -->
```python
import argparse, json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--trial', choices=['L01','L02','L03','L03-Q4','L04','L05'], required=True)
p.add_argument('--out', required=True)
p.add_argument('--prompt-file', required=True)
p.add_argument('--audio-file')
p.add_argument('--first-frame', help='Image filename already in ComfyUI/input')
p.add_argument('--seed', type=int, default=42)
p.add_argument('--production', action='store_true')
args = p.parse_args()
video = Path(args.prompt_file).read_text(encoding='utf-8').strip()
audio = Path(args.audio_file).read_text(encoding='utf-8').strip() if args.audio_file else 'Natural room tone and sounds matching the visible action. No music.'
w,h = (1280,704) if args.production else (896,512)
two_stage = args.trial != 'L05'
sw,sh = (w//2,h//2) if two_stage else (w,h)
g = {}
def node(i, cls, **inputs):
    g[str(i)] = dict(class_type=cls, inputs=inputs)
def ref(i, slot=0):
    return [str(i),slot]

if args.trial in ['L03','L03-Q4']:
    name = 'LTX-2.5-Distilled-Q6_K.gguf' if args.trial=='L03' else 'LTX-2.5-Distilled-Q4_K_M.gguf'
    node(1,'UnetLoaderGGUF',unet_name=name)
else:
    name = 'LTX25-distilled-DiT-comfy-mix4x8-17GB.safetensors' if args.trial=='L04' else 'ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors'
    node(1,'UNETLoader',unet_name=name,weight_dtype='default')
node(2,'CLIPLoader',clip_name='gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors',type='ltxv',device='default')
node(3,'VAELoader',vae_name='ltx-2.5-video-vae-bf16.safetensors' if args.trial=='L02' else 'ltx-2.5-video-vae-conv-bf16.safetensors')
node(4,'VAELoader',vae_name='ltx-2.5-audio-vae-bf16.safetensors')
node(5,'CLIPTextEncode',clip=ref(2),text=video+'\n'+audio)
node(6,'CLIPTextEncode',clip=ref(2),text='pc game, console game, video game, cartoon, childish, ugly')
node(7,'LTXVConditioning',positive=ref(5),negative=ref(6),frame_rate=24.0)
node(8,'EmptyLTXVLatentVideo',width=sw,height=sh,length=121,batch_size=1)
node(9,'LTXVEmptyLatentAudio',frames_number=121,frame_rate=24.0,batch_size=1,audio_vae=ref(4))
v = ref(8)
if args.first_frame:
    node(40,'LoadImage',image=args.first_frame)
    node(41,'ImageScale',image=ref(40),upscale_method='lanczos',width=w,height=h,crop='center')
    node(42,'LTXVPreprocess',image=ref(41),img_compression=18)
    node(43,'LTXVImgToVideoInplace',vae=ref(3),image=ref(42),latent=v,strength=0.7,bypass=False)
    v = ref(43)
node(10,'LTXVConcatAVLatent',video_latent=v,audio_latent=ref(9))
node(11,'RandomNoise',noise_seed=args.seed)
node(12,'KSamplerSelect',sampler_name='euler_ancestral')
node(13,'ManualSigmas',sigmas='1.0,0.99375,0.9875,0.98125,0.975,0.909375,0.725,0.421875,0.0')
node(14,'LTXVDualCFGGuider',model=ref(1),positive=ref(7,0),negative=ref(7,1),video_cfg=1.0,audio_cfg=1.0)
node(15,'SamplerCustomAdvanced',noise=ref(11),guider=ref(14),sampler=ref(12),sigmas=ref(13),latent_image=ref(10))
node(16,'LTXVSeparateAVLatent',av_latent=ref(15))
split = 16
if two_stage:
    node(20,'LatentUpscaleModelLoader',model_name='ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors')
    node(21,'LTXVLatentUpsampler',samples=ref(16,0),upscale_model=ref(20),vae=ref(3))
    v = ref(21)
    if args.first_frame:
        node(44,'LTXVImgToVideoInplace',vae=ref(3),image=ref(42),latent=v,strength=1.0,bypass=False)
        v = ref(44)
    node(22,'LTXVConcatAVLatent',video_latent=v,audio_latent=ref(16,1))
    node(23,'RandomNoise',noise_seed=args.seed)
    node(24,'ManualSigmas',sigmas='0.85,0.7250,0.4219,0.0')
    node(25,'SamplerCustomAdvanced',noise=ref(23),guider=ref(14),sampler=ref(12),sigmas=ref(24),latent_image=ref(22))
    node(26,'LTXVSeparateAVLatent',av_latent=ref(25))
    split = 26
node(30,'VAEDecodeTiled',samples=ref(split,0),vae=ref(3),tile_size=512,overlap=64,temporal_size=64,temporal_overlap=16)
node(31,'LTXVAudioVAEDecode',samples=ref(split,1),audio_vae=ref(4))
node(32,'CreateVideo',images=ref(30),audio=ref(31),fps=24.0)
node(33,'SaveVideo',video=ref(32),filename_prefix=f'{args.trial}/seed-{args.seed}',format='mp4',
     **{'format.codec':'h264','format.codec.encoding':'re-encode','format.codec.encoding.crf':18.0})
out = Path(args.out)
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(g,ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
```

建立例：`python make_ltx_job.py --trial L01 --prompt-file prompts/T01.txt --audio-file prompts/A01.txt --out jobs/L01-api.json`。I2V 加 `--first-frame ref_portrait.png`；製作解析度加 `--production`。兩階段的 noise seed 都固定成傳入 seed；I2V strength 保留官方模板的第一階段 0.7、第二階段 1.0，並使用 img_compression 18。這些 preprocessing／strength 要與輸入圖一起保存。

### 7.2 MiniMax H3：Comfy 配置

下方 `make_comfy_job.py` 提供 H02/H04/H05/H06/H07 和 C01/C02/C03 的 **API graph**，不用先手工改 UI 模板。先下載該 trial assets，Comfy 重新啟動或刷新 loader 清單後產生 JSON。首次由 `/object_info`、`/prompt` 的驗證確認節點／檔案存在；本文的 API 範例只有靜態核對，worker 要完成 runtime 驗證。

| ID | DiT／LoRA／採樣 | 特別注意 |
| --- | --- | --- |
| H02 | H-D + H-LARRY；Larry 專用 LoRA + Sampler；6 步，simple，video/audio shift **12/3**；strength 1 | `low_vram=false` 起步；OOM 才改 true，它會 merge，量化底模可能變軟。原始 Larry LoRA 能透過專用節點恢復 pruned 的時間 conditioning；不可用普通 LoRA loader 取代 |
| H04 | H-D + H-LX8；普通 LoraLoaderModelOnly；8 步，Euler/simple，12/3；strength 1 | 這是非 768p 特製八步版，與固定官方模板的檔名一致；不要混入四步版或別的 alpha/namespace 轉檔 |
| H05 | H-D + H-HYPER；pruned 轉檔，普通 loader；Euler、manual sigmas；strength 1 | 使用下面已套 video shift 的九點序列，不再 shift 一次。記錄「Comfy conversion」，不宣稱重現原版 HyperFlow 的 H200 數據 |
| H06 | H-D，無 LoRA；20 步，Euler/simple，12/3，CFG 1 | 20 步是此次同 runtime 對照值；不是宣稱等同官方 Diffusers 49 NFE 的完整基線 |
| H07 | 同 H02，只把 H-D 換 H-W6 | 非同一大小或數值的底模；如不支援 W6A8 記 BLOCKED_KERNEL，不自行把它轉 BF16 後算 W6A8 成功 |

HyperFlow Comfy 轉檔推薦的 **video schedule**：

```text
1.0, 0.9939097854, 0.9842874953, 0.9660637197, 0.9230769231, 0.8349423898, 0.6968520491, 0.4687533149, 0.0
```

轉檔 README 後段另列 `1.0, 0.931506, 0.839236, 0.703462, 0.5, 0.296538, 0.160764, 0.068494, 0.0`。**數值核對顯示**後者經 `12*s/(1+11*s)` 後近似首段序列，屬尚未套 video shift 的時間點。這是本文件的數值推導；此處 ManualSigmas 使用首段已 shift 的版本，防止重複 shift。若要測未 shift 序列，另開配置，不混入 H05。

H3 frames 是 **17*k+5**；約 5 秒用 **124 frames**，不是 LTX 的 121。寬高為 32 的倍數。影片/audio 的時間表分別是 12/3，Comfy 的 AV model sampling 會處理映射，不能只把音訊當成普通影片 latent。

H3 的 FL2VA 能文字、第一／最後幀生影音；多張人物／物件參考是 **Ref2VA** 路線，不能在 FL2VA checkpoint 上改名稱就算支援。若主測選出 H3，再用官方 `video_minimax_h3_r2v.json` 加測 Ref2VA；配對 Ref2VA 底模與加速檔，不沿用 FL2VA 的 PDD。

### 7.3 MiniMax H3：WanGP 配置

H01 用 model ID `minimax_h3_fl2va_pruned_pdd`，由原生 model definition 載入 PDD LoRA/heads；不再手加 Turbo。H03 用 `minimax_h3_fl2va_pruned` + **v1.2 768p** LoRA；profile 可對照 `profiles/minimax_h3_fl2va/Turbo Lightx2v FL2V 4 Steps v1.2 768p.json`。

H01 固定 8 步、Euler；H03 4 步、Euler、flow_shift 6。兩者 guidance 1、單 phase，prompt enhancer 關，初始 832×480/124 frames。**H01 不使用 H03 的 flow shift**；PDD 預設是 12。生成 JSON 裡的 `settings_version` 使用來源樣本的 2.73；固定程序會處理自己的設定遷移。

<!-- FILE:make_wangp_job.py -->
```python
import argparse, json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--trial', choices=['H01', 'H03'], required=True)
p.add_argument('--out', required=True)
p.add_argument('--prompt-file', required=True)
p.add_argument('--audio-file')
p.add_argument('--seed', type=int, default=42)
p.add_argument('--first-frame')
p.add_argument('--root', default='/content/video_trials')
p.add_argument('--production', action='store_true')
args = p.parse_args()
video = Path(args.prompt_file).read_text(encoding='utf-8').strip()
audio = Path(args.audio_file).read_text(encoding='utf-8').strip() if args.audio_file else 'Natural room tone and sounds matching the visible action. No music.'
prompt = f'integrated_multimodal_description: [Shot 1] {video}\noverall_soundscape: {audio}\nnon_diegetic_music: None.'
job = dict(image_mode=0, model_type='minimax_h3_fl2va_pruned_pdd' if args.trial == 'H01'
           else 'minimax_h3_fl2va_pruned', settings_version=2.73,
           prompt=prompt, seed=args.seed,
           num_inference_steps=8 if args.trial == 'H01' else 4,
           resolution='1344x768' if args.production else '832x480', video_length=124,
           sliding_window_size=362, sliding_window_overlap=18, guidance_phases=1,
           guidance_scale=1.0, sample_solver='euler', flow_shift=12 if args.trial == 'H01' else 6,
           prompt_enhancer='', multi_prompts_gen_type='PW', activated_loras=[],
           loras_multipliers='', image_prompt_type='T', video_prompt_type='', audio_prompt_type='')
if args.trial == 'H03':
    job['activated_loras'] = [str((Path(args.root) / 'Wan2GP/loras/minimax_h3/minimax_h3_lightx2v_fl2v_turbo_4step_alpha8_v1.2_768p_bf16.safetensors').resolve())]
    job['loras_multipliers'] = '1.0'
if args.first_frame:
    job['image_start'] = str(Path(args.first_frame).resolve())
    job['image_prompt_type'] = 'S'
out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
```

建立例：`python make_wangp_job.py --trial H01 --prompt-file prompts/T01.txt --audio-file prompts/A01.txt --out jobs/H01.json`。builder 會把 video/audio captions 包成與 Comfy 試驗相同的 H3 結構化 prompt。

此處 LoRA 使用已下載檔案的絕對路徑；若改安裝根目錄，對 builder 傳 `--root`。WanGP 的 `image_mode=0` 表示輸出影片，I2V 仍保留 0；起始圖透過 `image_start` + `image_prompt_type='S'` 啟用，`video_prompt_type='I'` 是一般參考圖功能，不能拿來代替起始幀。H3 WanGP text encoder 量化由全域 config 控制；初始使用 INT8，若要改 Q4_K_M 另列配置，不與 Comfy INT8 TE 冒充同一底模比較。

### 7.4 Kandinsky 6

官方 Comfy 擴充能直接辨識 Lite/Pro distilled，專用 sampler 自動執行 **PiFlow**。固定 **10 步、CFG 1、denoise 1、audio scaling 0.417**；不用一般 KSampler 指定「Euler 十步」代替 PiFlow。UI 內 sampler/scheduler selectors 在 distilled 模型上不主導取樣。

Qwen2.5-VL 7B + CLIP-L 是必要 TE；Qwen3.5-9B 是可關閉的 prompt beautifier。純 API graph 直接用固定 video/audio captions，**不需要 beautifier 或 SR 權重**。原官方 UI 模板包含 SR branch，若想用它須先移除 SR branch，將原 VAEDecode 和 audio decode 直接接 CreateVideo；此處 API graph 已完成這個配置。

C02 的玩家量化 safetensors header 已讀取，包含 `quantization_format=int8_convrot`、`convrot_format=comfy_quant_v1`，與原生量化格式一致；**尚未驗證實際 loader／kernel／生成結果**。如果檔案被正確辨識為 Pro distilled、PiFlow head grid=10 且完成生成，才算通過。C03 為官方 BF16 的品質／相容對照，需更多主記憶體，不是 40GB 保證必跑。

### 7.5 直接建立 Comfy API graph

`--prompt-file` 只讀 video caption，`--audio-file` 另讀聲音敘述；H3 自行合成結構化 prompt。H02/H07 可再用 `--steps 8`；H04/H05 固定 8；C01/C02/C03 固定 10。不要改 distilled 的步數後仍沿用原 ID。

<!-- FILE:make_comfy_job.py -->
```python
import argparse, json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--trial', choices=['H02','H04','H05','H06','H07','C01','C02','C03'], required=True)
p.add_argument('--out', required=True)
p.add_argument('--prompt-file', required=True)
p.add_argument('--audio-file')
p.add_argument('--seed', type=int, default=42)
p.add_argument('--first-frame', help='Image filename already in ComfyUI/input')
p.add_argument('--production', action='store_true')
p.add_argument('--steps', type=int)
p.add_argument('--low-vram-lora', action='store_true')
args = p.parse_args()
video = Path(args.prompt_file).read_text(encoding='utf-8').strip()
audio = Path(args.audio_file).read_text(encoding='utf-8').strip() if args.audio_file else 'Natural room tone and sounds matching the visible action. No music.'
g = {}
def node(i, cls, **inputs):
    g[str(i)] = dict(class_type=cls, inputs=inputs)
def ref(i, slot=0):
    return [str(i), slot]

if args.trial.startswith('C'):
    if args.production:
        raise SystemExit('K6 main matrix stays at official SD settings; evaluate SR separately')
    if args.steps is not None and args.steps != 10:
        raise SystemExit('K6 distilled PiFlow is fixed to 10 NFE in this matrix')
    files = {
      'C01':'Kandinsky-6.0-Lite-distill-5s-Diffusers/transformer/diffusion_pytorch_model.safetensors',
      'C02':'kandinsky6_pro_distill_int8_convrot.safetensors',
      'C03':'Kandinsky-6.0-Pro-distill-5s-Diffusers/transformer/diffusion_pytorch_model.safetensors'}
    node(1,'UNETLoader',unet_name=files[args.trial],weight_dtype='default')
    node(2,'DualCLIPLoader',clip_name1='qwen_2.5_vl_7b.safetensors',clip_name2='clip_l.safetensors',type='kandinsky5',device='default')
    node(3,'VAELoader',vae_name='hunyuan_video_vae_bf16.safetensors')
    node(4,'Kandinsky6AudioVAELoader',tod_vae='v1-44.pth',bigvgan_dir='bigvgan_vocoder',mode='44k',scaling_factor=0.417)
    node(5,'Kandinsky6TextEncode',clip=ref(2),video_caption=video,audio_caption=audio)
    node(6,'Kandinsky6TextEncode',clip=ref(2),video_caption='',audio_caption='')
    node(7,'Kandinsky6EmptyLatent',width=864,height=480,length=121,fps=24.0,batch_size=1)
    pos,neg,latent = ref(5),ref(6),ref(7)
    if args.first_frame:
        node(13,'LoadImage',image=args.first_frame)
        node(14,'ImageScale',image=ref(13),upscale_method='lanczos',width=864,height=480,crop='center')
        node(15,'VAEEncode',pixels=ref(14),vae=ref(3))
        node(16,'Kandinsky6ImageToVideoAudio',positive=pos,negative=neg,empty_latent=latent,reference_latent=ref(15))
        pos,neg,latent=ref(16,0),ref(16,1),ref(16,2)
    node(8,'Kandinsky6Sampler',model=ref(1),seed=args.seed,steps=10,cfg=1.0,sampler_name='euler',scheduler='simple',positive=pos,negative=neg,latent_image=latent,denoise=1.0)
    node(9,'VAEDecode',samples=ref(8),vae=ref(3))
    node(10,'Kandinsky6AudioVAEDecode',audio_vae=ref(4),joint_latent=ref(8))
    node(11,'CreateVideo',images=ref(9),audio=ref(10),fps=24.0)
    node(12,'SaveVideo',video=ref(11),filename_prefix=f'{args.trial}/seed-{args.seed}',format='mp4',
         **{'format.codec':'h264','format.codec.encoding':'re-encode','format.codec.encoding.crf':18.0})
else:
    steps = {'H02':6,'H04':8,'H05':8,'H06':20,'H07':6}[args.trial]
    if args.steps is not None:
        if args.trial not in ['H02','H07'] or args.steps not in [6,8]:
            raise SystemExit('Only Larry trials may change 6 to 8 steps here')
        steps=args.steps
    w,h=(1344,768) if args.production else (832,480)
    model='minimax_h3_fl2va_pruned_w6a8.safetensors' if args.trial=='H07' else 'minimax_h3_fl2va_pruned_int8_convrot.safetensors'
    node(1,'UNETLoader',unet_name=model,weight_dtype='default')
    node(2,'CLIPLoader',clip_name='qwen3vl_32b_minimax_h3_int8_convrot.safetensors',type='minimax',device='default')
    node(3,'VAELoader',vae_name='minimax_h3_video_vae_int8_convrot.safetensors')
    node(4,'VAELoader',vae_name='minimax_h3_audio_vae_fp32.safetensors')
    node(5,'MiniMaxH3ImageToVideo',clip=ref(2),vae=ref(3),prompt=f'integrated_multimodal_description: [Shot 1] {video}\noverall_soundscape: {audio}\nnon_diegetic_music: None.',width=w,height=h,length=124)
    if args.first_frame:
        node(21,'LoadImage',image=args.first_frame)
        node(22,'ImageScale',image=ref(21),upscale_method='lanczos',width=w,height=h,crop='center')
        g['5']['inputs']['first_frame']=ref(22)
    node(20,'MiniMaxH3SigmaShift',model=ref(1),shift_video=12.0,shift_audio=3.0)
    model_ref=ref(20)
    if args.trial in ['H02','H07']:
        node(6,'MiniMaxH3TurboLoRA',model=model_ref,lora_name='minimax_h3_turbo_v4_step600_ema.safetensors',strength=1.0,low_vram=args.low_vram_lora)
        node(7,'MiniMaxH3TurboSampler')
        model_ref=ref(6)
    elif args.trial in ['H04','H05']:
        lora='minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors' if args.trial=='H04' else 'minimax_h3_hyperflow_8step_v1.0_comfyui_pruned_bf16.safetensors'
        node(6,'LoraLoaderModelOnly',model=model_ref,lora_name=lora,strength_model=1.0)
        model_ref=ref(6)
        node(7,'KSamplerSelect',sampler_name='euler')
    else:
        node(7,'KSamplerSelect',sampler_name='euler')
    node(8,'BasicGuider',model=model_ref,conditioning=ref(5,0))
    if args.trial=='H05':
        node(9,'ManualSigmas',sigmas='1.0,0.9939097854,0.9842874953,0.9660637197,0.9230769231,0.8349423898,0.6968520491,0.4687533149,0.0')
    else:
        node(9,'BasicScheduler',model=model_ref,scheduler='simple',steps=steps,denoise=1.0)
    node(10,'RandomNoise',noise_seed=args.seed)
    node(11,'SamplerCustomAdvanced',noise=ref(10),guider=ref(8),sampler=ref(7),sigmas=ref(9),latent_image=ref(5,1))
    node(12,'VAEDecode',samples=ref(11,1),vae=ref(3))
    node(13,'VAEDecodeAudio',samples=ref(11,1),vae=ref(4))
    node(14,'CreateVideo',images=ref(12),audio=ref(13),fps=24.0)
    node(15,'SaveVideo',video=ref(14),filename_prefix=f'{args.trial}/seed-{args.seed}',format='mp4',
         **{'format.codec':'h264','format.codec.encoding':'re-encode','format.codec.encoding.crf':18.0})
out=Path(args.out)
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(g,ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
```

API 建置範例（不用假定 node ID，程式已固定）：

```bash
python make_comfy_job.py --trial H02 --prompt-file prompts/T01.txt --audio-file prompts/A01.txt --out /content/video_trials/jobs/H02-api.json
python make_comfy_job.py --trial C01 --prompt-file prompts/T01.txt --audio-file prompts/A01.txt --out /content/video_trials/jobs/C01-api.json
```

這些 graph 依 ComfyUI 0.39 的 DynamicCombo API 使用 `format.codec` 等欄位，固定 MP4／H.264／CRF 18；不能只把舊版的平面 `codec='h264'` 抄進這個版本。H3 API graph 已明確加入 `MiniMaxH3SigmaShift`，video/audio shift 為 12/3；這是實際 node ID，UI 顯示名稱為 `ModelSamplingMiniMaxH3`。首次仍查 loader／採樣日誌；不能在聲音錯誤時仍給生成通過。H3 UI 參考模板：

- <https://raw.githubusercontent.com/Comfy-Org/workflow_templates/00309dce76e9c4f436dc85144d39eccc863fb304/templates/video_minimax_h3_t2v.json>
- <https://raw.githubusercontent.com/Comfy-Org/workflow_templates/00309dce76e9c4f436dc85144d39eccc863fb304/templates/video_minimax_h3_i2v.json>
- Larry 完整示例：<https://raw.githubusercontent.com/larryvrh/ComfyUI-MiniMax-H3-Turbo/4274783a23afcfdbea3b4876cb79effd6c510785/example_workflows/minimax_h3_t2v_turbo.json>

### 7.6 Bernini-R

這是功能試驗，不與原生影音模型用同一個音訊分數競爭。先用 WanGP `bernini` 的內建 preset，DiT INT8、高／低噪兩份都要有；配套 text encoder/VAE 由**固定 WanGP handler**自動選取。保留所有自動下載 URL、檔名、checksum 到 `assets-B01-runtime.json`。只使用 renderer，不裝 full Bernini 的語義 planner。

第一個任務：同一支已產出的約 5 秒人物影片 + 一張衣服參考圖，只改外衣，保留臉、背景、動作和鏡頭。設定從 `defaults/bernini.json` 開始：832×480、81 frames、UniPC、40 步、shift 5、guidance 4/4、noise switch 875、`video_prompt_type=VI`，不加 Lightning。從 UI 指定來源影片和 reference image 後 **Export Settings**，再 `--process` 執行。

若沒有衣服圖，改為「把外衣改成純紅色」，移除 reference image flag，保留 video guide。不要把不同任務混在一起。加入參考圖時至少 15 步是作者整合的起點，初始仍用 40；四步 LoRA 可留在純影片修改的後續試驗，不能放進主參考圖測試。

本項所需輸入可從前面完成的影片取得，無須替它搜尋網路素材。這列的完整 run 必須先從 preset 產生含 media 路徑的設定，不能把 defaults 裡的「模型定義 JSON」當成完整工作 JSON。

## 8. 固定測試題目

所有模型使用相同**影片意圖**；只將音訊／對話包成各模型規定的語法。固定英文 prompt，方便排除中文解析差異；需要中文製作時，決選後再加中文測試。先關掉 rewriter，不能讓某個模型自己把簡單題目改成較容易生成的題目。

| 題號 | 用途 | Video caption（直接複製到文字檔） | Audio caption |
| --- | --- | --- | --- |
| T01 | 手部、人物穩定、物件互動 | A single continuous five-second realistic shot. An adult woman in a plain blue shirt sits at a wooden table. She picks up a white ceramic cup with her right hand, takes one small sip, and places the cup back on the same spot. Her face, clothes and cup stay consistent. Medium shot, locked camera, soft daylight. | Quiet room tone. A soft ceramic contact when the cup is picked up and placed down. No speech and no music. |
| T02 | 動作、遮擋、快速運動 | A single continuous five-second realistic shot. A red bicycle ridden by an adult cyclist moves from left to right behind two thin tree trunks. The bicycle and rider reappear consistently after each occlusion. Side tracking camera at a steady speed, bright afternoon, natural motion. | Bicycle tire noise on a paved path and gentle outdoor wind. No speech and no music. |
| T03 | 運鏡、材質、商品一致性 | A single continuous five-second product shot. A matte black metal wristwatch rests on a pale stone pedestal. The camera makes a slow 45-degree orbit. The watch keeps the same shape, face layout and strap. Soft moving reflections, subtle depth of field, clean studio background. | Very quiet studio room tone. No speech, music or dramatic effects. |
| T04 | 音畫對齊 | A single continuous five-second realistic shot. An adult drummer taps a small wooden drum exactly three times, with clear pauses between taps. Both hands and the drum remain visible. Locked medium shot. | Exactly three dry wooden drum hits synchronized to the visible taps. Quiet background, no speech and no music. |
| T05 | 風格與空間穩定 | A single continuous five-second stylized 3D animation. A small orange robot gently waves one hand while walking two steps toward the camera in a cozy workshop. Its head, eyes and body proportions stay unchanged. Slow camera push-in, warm light, detailed but stable background. | Two soft mechanical footsteps and a quiet servo sound during the wave. No speech and no music. |

T01～T03 為核心；T04/T05 是決選擴充題。第一次只跑 **T01 + seed 42**。成功後用 T02 做動作壓力測試，避免只看靜態樣本選模型。

I2V 共用一張起始圖，不讓每個模型各自先生成圖。可直接下載官方 Kandinsky 6 的示例 portrait，然後所有模型使用相同檔案：

<https://raw.githubusercontent.com/kandinskylab/kandinsky-6/f19c9b8ec2fcea5d391f5391983a540fc5e004da/comfyui/example_inputs/kandinsky6_i2va_portrait.png>

I01 video caption：`A single continuous five-second shot of the person in the reference image. The person slowly turns their head a little to the left, looks back toward the camera, and gives a subtle smile. Preserve the same face, hair, clothes and background. Gentle natural movement. Locked camera.` Audio：`Quiet natural room tone. No speech and no music.`

下載後保存原檔 SHA-256，依目標畫布 crop/resize，把每個 runtime 實際送入的圖也保存。Comfy `--first-frame` 指向已放在 `ComfyUI/input` 的檔名；WanGP `--first-frame` 用絕對路徑。不要把原圖拉伸與中心裁切的差異誤判成身份保持能力。

I02 商品一致性：選定一個已完成 T03 的影片，取第一幀一次、保存為固定 `ref_watch.png`；**所有模型都用同一張**。Caption：`A single continuous five-second product shot of the watch in the reference image. The camera slowly moves closer and slightly to the right. Preserve the exact watch shape, dial layout, strap, pedestal and materials. Subtle natural reflections. No cuts.`

對話另立 A03，只對原生影音模型：在同一人物的五秒單鏡头內說 `The camera is ready.`，對照字幕、發音、嘴型、說話是否完成。LTX 用自然文字加引號；H3 用 `(S1) <d>[English] The camera is ready.</d>`；Kandinsky video caption 用 `<S>The camera is ready.<E>`，聲音敘述放 audio caption。這個語法差異不是對模型額外提示。

Seeds：初測 `42`；決選 `42, 3407, 20261011`。固定 seed 不保證不同 GPU／kernel 逐位元一致，也不代表不同模型的噪聲相同。

## 9. 執行、記錄與續跑

### 9.1 Comfy API 送件與完成判定

先在相同主機啟動 Comfy；`jobs/*.json` 必須是 API graph。以下程式先讀 `/object_info` 檢查 class，再 POST。它不會按未知 node ID 改 prompt，prompt/seed 由前面的 builder 或匯出的 graph 確定。

<!-- FILE:run_comfy.py -->
```python
import argparse, json, time, urllib.request, urllib.error
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--job',required=True)
p.add_argument('--base-url',default='http://127.0.0.1:8188')
p.add_argument('--record',required=True)
p.add_argument('--timeout',type=float,default=1800)
args=p.parse_args()
job=json.loads(Path(args.job).read_text(encoding='utf-8'))
if 'nodes' in job or any(not isinstance(v,dict) or 'class_type' not in v for v in job.values()):
    raise SystemExit('Expected API graph, not UI workflow JSON')
def call(path,data=None):
    body=json.dumps(data).encode() if data is not None else None
    req=urllib.request.Request(args.base_url+path,data=body,
                               headers={'Content-Type':'application/json'} if body else {})
    try:
        with urllib.request.urlopen(req,timeout=45) as f:
            return json.load(f)
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode(errors='replace')) from e
info=call('/object_info')
missing=sorted({n['class_type'] for n in job.values()}-set(info))
if missing:
    raise SystemExit('BLOCKED_NODE: '+', '.join(missing))
start=time.perf_counter()
reply=call('/prompt',{'prompt':job})
if reply.get('node_errors'):
    raise SystemExit(json.dumps(reply['node_errors'],ensure_ascii=False))
pid=reply['prompt_id']
while True:
    history=call('/history/'+pid)
    item=history.get(pid)
    if item:
        elapsed=time.perf_counter()-start
        record=dict(prompt_id=pid,elapsed_wall_seconds=elapsed,job=args.job,history=item)
        target=Path(args.record)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        status=item.get('status',{})
        if status.get('status_str')=='error' or not status.get('completed',False):
            raise SystemExit('GENERATION_FAILED: inspect saved history')
        if not item.get('outputs'):
            raise SystemExit('NO_SAVED_OUTPUT: inspect workflow output node')
        print('Completed',pid,round(elapsed,2),'seconds; inspect MP4 before scoring')
        break
    if time.perf_counter()-start>args.timeout:
        # This benchmark uses a dedicated idle server; interrupt only its own queued run.
        call('/interrupt',{})
        raise SystemExit('TIMEOUT: generation interrupted; save logs and continue next trial')
    time.sleep(2)
```

執行例：`python run_comfy.py --job jobs/H02-api.json --record logs/H02-T01-seed42.json`。`elapsed_wall_seconds` 包含該次權重載入、編碼、去噪和解碼；模型下載事先完成。**不含下載不等於不含載入**；要把 cold start 與 warmed run 分開。

程式只對專用、空閒的 Comfy server 使用 `/interrupt`。若 server 供其他工作共用，不使用上述 timeout 自動 interrupt；採個別 process／獨立 port，避免中斷別人的工作。這是執行隔離需求，不影響模型評分。

### 9.2 量測欄位

每支影片保存：完整 API/settings JSON、Git SHA、HF revision/checksum、pip freeze、driver、GPU 型號/VRAM、CPU RAM、輸入檔與 hash、prompt、seed、原 MP4、原音訊與 log。

| 指標 | 記法 |
| --- | --- |
| download_seconds | 首次下載另記，不放進生成耗時 |
| cold_load_seconds | 新 process／換模型的載入時間 |
| text_encode_seconds | 若有快取，要標明 hit/miss；不同 prompt 不能假裝是相同 warm cache |
| denoise_seconds／NFE | 讀 runtime log；記真實 forward 次數與階段，不以步數猜時間 |
| decode_seconds | video VAE、audio VAE、vocoder 各自記；不能遺漏 Diffusion VAE |
| total_wall_seconds | 準備好本地權重後，送件到可播放 MP4 完成；第一次 cold、第二次同設定 warm 各記 |
| peak_gpu_mib | 用 `nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv -lms 500` 於工作期間記錄；是採樣峰值，可能漏短暫峰值 |
| peak_allocated/reserved | 若能加 PyTorch instrumentation，記 allocator 的 max 值；它不等同 nvidia-smi，也不包含所有 process |
| peak_cpu_ram | 監測 process tree RSS 與系統可用 RAM；不能只看主 process |
| actual_clip | 用 ffprobe 讀真正 width/height/fps/frame count/duration/audio sample rate；保留要求值與實際值兩欄 |

ffprobe 指令：

```bash
ffprobe -v error -count_frames -show_entries stream=index,codec_type,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,sample_rate,channels:format=duration -of json renders/example.mp4
```

不要先插幀／超分／裁剪後才評分。縮圖無法判定時間一致性；worker 要觀看原片，或交回給使用者評分。若 worker 沒有視聽能力，品質欄填 `NEEDS_HUMAN_REVIEW`，不能只因檔案生成就填高分。

### 9.3 品質與選擇規則

| 面向 | 0～5 分判斷 |
| --- | --- |
| prompt following | 主體、指定動作、方向、鏡頭是否完成；0 為失敗，3 可用但有偏差，5 正確完成 |
| temporal consistency | 臉、手、衣服、物件、背景是否跳變，遮擋後是否回到同一形象 |
| motion/physics | 有沒有動作不足、滑動、穿模、拖影、錯誤互動或突然跳鏡 |
| visual detail | 臉、手、材質、邊緣與背景細節；不能用銳化假象代替結構正確 |
| I2V identity | 起始圖角色／商品特徵是否保留；T2V 填 N/A |
| audio/AV sync | 三次敲擊是否三個聲音，嘴型／說話是否對齊；Bernini 填 N/A，不填 0 |

品質與速度分別報，不先塞成主觀單一總分。先淘汰生成失敗、嚴重身份／動作錯誤，再找**在品質相近時較快、記憶體較省、失敗率較低**的配置。品質是否「相近」由同一人盲看，保留每題分數與具體缺陷。

回報至少四個用途的勝者：快速草稿、一般 720p 製作、人物／商品 I2V、原生聲音／對話。沒有某項任務的測試就標 `NOT_TESTED`，不推測勝者。

### 9.4 分批與失敗處理

1. **相容性 smoke**：P0 每列 T01/seed42 一支；查 MP4 可播放、時長、音訊；完成後測 I01。
2. **動作檢查**：可用候選跑 T02/seed42。四步模型不能只通過靜態就入選。
3. **P1 變種**：按同底模分批，避免反覆載入與整套重下載。先選有希望改善瓶頸的變種。
4. **決選**：最多 3 個配置 × T01/T02/T03 × 3 seeds；I2V 再對 I01/I02。製作用解析度另跑，不能由 480p 成功推論 768p 必成功。
5. **P2**：有資源才跑；條件不符填 skip。主模型勝者選出後才安排 SR、長片續接、Ref2VA、控制／編輯 LoRA。

| 錯誤 | 先做的處理 | 終止／紀錄規則 |
| --- | --- | --- |
| CUDA OOM | 保存 log；確定別的 process 已退出；先降低 offload residency／加 tiled decode；必要時 `--lowvram`；**一次只改一項** | 同一配置最多重試 2 次。改解析度／frames 要新 ID，不能報原設定成功 |
| CPU RAM OOM／process 被 kill | 查系統 RAM、process tree、是否把 TE/DiT 全份 BF16 同時複製 | SKIP_RESOURCE；不能把它記成「模型品質差」 |
| missing/unexpected tensor／shape mismatch | 核對 base、pruned/full、FL2VA/Ref2VA、namespace、HF revision；LTX GGUF 核對 config metadata | BLOCKED_FORMAT；不要使用 ignore-missing 強行生成後評分 |
| unsupported kernel／CUDA binary error | 核對 driver、Torch runtime、comfy-kitchen wheel；用本文的官方同版 Python fallback | BLOCKED_KERNEL；保持原始失敗。A100 不強跑 Blackwell NVFP4 DiT |
| 401/403 | 核對帳號是否已獲模型存取授權、token 是否傳入 | BLOCKED_AUTH；不要用來源不明的鏡像繞過；先完成其他可下載模型 |
| 工作停滯／超時 | 記最後階段；初始每支設 **30 分鐘**上限，純編譯 warmup 另記，下載不算其中 | TIMEOUT；這是測試預算，不是模型預期速度。切下一列繼續 |
| Comfy `/prompt` 400 | 看 node_errors、缺少 node/必填欄位/模型清單，保存錯誤與 graph | BLOCKED_NODE/GRAPH；不能把 UI workflow JSON 當 API graph |

逐支保存 `results.jsonl` 或 CSV，已完成且有影片／設定／結果的工作不重跑。Colab 斷線前後以 job key `trial-prompt-seed-resolution-fps-frames-runtime` 續跑；不能只靠 filename 判斷完成。

每支完成後，將影片、設定、log 與結果同步到使用者指定的持久輸出目錄（例如已掛載的 Drive）；Colab 的 `/content` 暫存不能作為唯一交付位置。重連時先還原這些紀錄，再決定哪些 job 未完成；權重按固定 manifest 重建即可。

## 10. worker 最終交付格式

```csv
trial,prompt_id,seed,task,model_revision,runtime_commit,gpu,vram_gib,ram_gib,width,height,frames,fps,duration_s,steps_or_nfe,cold_or_warm,load_s,encode_s,denoise_s,decode_s,total_s,peak_gpu_mib,peak_cpu_gib,prompt_score,temporal_score,motion_score,detail_score,identity_score,audio_score,status,video_path,settings_path,notes
```

空白數字代表沒有量測；N/A 代表不適用，兩者不要混用。最終 Markdown 摘要表：

| 用途 | 最佳配置 | 可用率 | 產出規格 | cold / warm 耗時 | 峰值 VRAM / RAM | 主要問題 | 支持此選擇的影片與設定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 快速草稿 | 待測 | 待測 | 待測 | 待測 | 待測 | 待測 | 待測 |
| 一般影片製作 | 待測 | 待測 | 待測 | 待測 | 待測 | 待測 | 待測 |
| 人物／商品 I2V | 待測 | 待測 | 待測 | 待測 | 待測 | 待測 | 待測 |
| 原生聲音／對話 | 待測 | 待測 | 待測 | 待測 | 待測 | 待測 | 待測 |

## 11. 核對來源與本文件驗證範圍

本文件使用作者／官方原始來源。釋出日期有公告時採公告；沒有公告時列實際權重提交，不以 repo `lastModified` 整體時間冒充所有檔案日期。

| 主題 | 主要來源 |
| --- | --- |
| LTX-2.5／採樣／尺寸／TE | [官方模型卡](https://huggingface.co/Lightricks/LTX-2.5)、[Comfy 官方釋出頁](https://comfy.org/ltx-2.5/)、[LTX 系統需求](https://docs.ltx.io/open-source-model/getting-started/system-requirements) |
| LTX GGUF config 問題 | [realrebelai 模型卡](https://huggingface.co/realrebelai/LTX-2.5_GGUFs)、[固定 city96 loader](https://github.com/city96/ComfyUI-GGUF/blob/6ea2651e7df66d7585f6ffee804b20e92fb38b8a/loader.py) |
| LTX mixed 4/8-bit | [joeygambino 原始說明與 manifest](https://huggingface.co/joeygambino/LTX-2.5-Quantized) |
| H3 底模與正式公告 | [MiniMax 7/31 公告](https://www.minimax.io/blog/minimax-h3)、[官方權重](https://huggingface.co/MiniMaxAI/MiniMax-H3)、[官方整理的社群整合](https://github.com/MiniMax-AI/awesome-minimax-h3-integration) |
| H3 Comfy pruned／W6A8／TE 特例 | [Comfy-Org repack](https://huggingface.co/Comfy-Org/MiniMax-H3)、[W6A8 提交記錄](https://huggingface.co/Comfy-Org/MiniMax-H3/commits/main) |
| H3 PDD | [Alibaba PAI 原始 LoRA](https://huggingface.co/alibaba-pai/MiniMax-H3-Acc-LoRAs)、[PDD 論文](https://arxiv.org/abs/2607.26004)、[WanGP model definition](https://github.com/deepbeepmeep/Wan2GP/blob/6479db36bdc2619a904a852bba9c2d78e1a83f82/defaults/minimax_h3_fl2va_pruned_pdd.json) |
| H3 Larry Turbo | [作者模型卡與提交](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora)、[專用節點](https://github.com/larryvrh/ComfyUI-MiniMax-H3-Turbo) |
| H3 LightX2V v1.2 與八步版 | [作者權重](https://huggingface.co/lightx2v/Minimax-h3-Turbo)、[權重提交](https://huggingface.co/lightx2v/Minimax-h3-Turbo/commits/main)、[LightX2V 更新紀錄](https://github.com/ModelTC/LightX2V) |
| H3 HyperFlow 原版與社群轉檔 | [原版模型卡](https://huggingface.co/videorebirth/hyperflow)、[原版 loader](https://github.com/Video-Rebirth/hyperflow)、[drbaph 轉檔／採樣說明](https://huggingface.co/drbaph/MiniMax-H3-Turbo-Lora-ComfyUI) |
| Kandinsky 6 10/6 釋出／Lite／Pro／PiFlow | [官方 repo](https://github.com/kandinskylab/kandinsky-6)、[固定 Comfy 說明](https://github.com/kandinskylab/kandinsky-6/blob/f19c9b8ec2fcea5d391f5391983a540fc5e004da/comfyui/README.md)、[官方研究](https://arxiv.org/abs/2610.05608) |
| Kandinsky 6 玩家 INT8 | [DeepBeepMeep 檔案](https://huggingface.co/DeepBeepMeep/Kandinsky6)、[10/8 提交](https://huggingface.co/DeepBeepMeep/Kandinsky6/commits/main)；本文件另讀取 Pro INT8 header 確認格式 |
| Bernini-R | [ByteDance 官方模型](https://huggingface.co/ByteDance/Bernini-R)、[renderer 說明](https://github.com/bytedance/Bernini/blob/main/docs/bernini_r.md)、[WanGP preset](https://github.com/deepbeepmeep/Wan2GP/blob/6479db36bdc2619a904a852bba9c2d78e1a83f82/defaults/bernini.json) |
| Wan 720p 4/12 新權重 | [作者提交](https://huggingface.co/lightx2v/Wan2.2-Distill-Models/commits/main)、[作者更新公告](https://github.com/ModelTC/LightX2V) |
| Rapid 停止維護 | [作者模型卡](https://huggingface.co/Phr00t/WAN2.2-14B-Rapid-AllInOne) |
| Prism 單卡資源條件 | [官方 repo](https://github.com/Tencent-Hunyuan/Prism) |
| 程式安裝與批次 | [PyTorch 2.10 官方安裝](https://pytorch.org/get-started/previous-versions/)、[WanGP CLI](https://github.com/deepbeepmeep/Wan2GP/blob/6479db36bdc2619a904a852bba9c2d78e1a83f82/docs/CLI.md)、[Comfy API server](https://github.com/Comfy-Org/ComfyUI) |

已做：逐檔對照 HF API snapshot 的檔名／bytes／revision；讀取固定工作流及相關 loader/sampler 原始碼；核對新變種提交時間；讀取 Kandinsky Pro INT8 safetensors header；檢查本文 Python/Bash 語法、manifest 引用與 JSON graph 結構。

未做：Colab 安裝、A100 kernel 選擇、實際 GPU 記憶體峰值、生成時間、畫面／音訊品質評分。worker 必須把這些測完才可填入結果；本文沒有提供虛構秒數或「保證不 OOM」。

## 附錄 A. 機器可讀的固定下載 manifest

`fetch_assets.py` 從這個區塊自動讀取，不需要手工抄長檔名。`bytes` 與 `sha256` 由 HF API 查得；小型 Git 檔案可能沒有 LFS SHA-256，仍用固定 repo revision。

<!-- ASSET_MANIFEST -->
```json
{
  "date": "2026-10-11",
  "repos": {
    "R1": {
      "repo_id": "Lightricks/LTX-2.5",
      "revision": "2356ce76915d6c48d313d7e8b25900e1dd3abaa8"
    },
    "R2": {
      "repo_id": "realrebelai/LTX-2.5_GGUFs",
      "revision": "112436f97aaf99ce13ecb7b7eca7e2f6c128d3ec"
    },
    "R3": {
      "repo_id": "joeygambino/LTX-2.5-Quantized",
      "revision": "00f505424717d526f7b00f51c415de789c3f661c"
    },
    "R4": {
      "repo_id": "Comfy-Org/MiniMax-H3",
      "revision": "e5eb578a89295337b8ff433a035929ce0279e0b6"
    },
    "R5": {
      "repo_id": "larryvrh/MiniMax-H3-Turbo-Lora",
      "revision": "43a74557ac3f6539db8e0f2a959d03feb7a81480"
    },
    "R6": {
      "repo_id": "drbaph/MiniMax-H3-Turbo-Lora-ComfyUI",
      "revision": "bb2bc497cbaca89dadd0bcf1856eed4f8275be20"
    },
    "R7": {
      "repo_id": "lightx2v/Minimax-h3-Turbo",
      "revision": "3ec17a324ced54151364f24f8b5fb6bf7e26414f"
    },
    "R8": {
      "repo_id": "DeepBeepMeep/MiniMax-H3",
      "revision": "adc81ccb71352192214d83d5fafb9487e860be39"
    },
    "R9": {
      "repo_id": "kandinskylab/Kandinsky-6.0-Lite-distill-5s-Diffusers",
      "revision": "efbaeb9961770cc82fece5b9cb2197049d8c983c"
    },
    "R10": {
      "repo_id": "kandinskylab/Kandinsky-6.0-Pro-distill-5s-Diffusers",
      "revision": "1018d5828716e8bea3de99609f45c924de9c5564"
    },
    "R11": {
      "repo_id": "DeepBeepMeep/Kandinsky6",
      "revision": "66912fedfbb8cbe7fa699eb0e25a53042d7cd1a4"
    },
    "R12": {
      "repo_id": "Comfy-Org/Qwen-Image_ComfyUI",
      "revision": "1f12b17be14c89b026c51a91d67c32f84bb047bc"
    },
    "R13": {
      "repo_id": "Comfy-Org/HunyuanVideo_repackaged",
      "revision": "533a43813f01517d9e624f9e824a85bb94094120"
    },
    "R14": {
      "repo_id": "hkchengrex/MMAudio",
      "revision": "eb13a1a98fdbec91753775c57b074ccdfc60587c"
    },
    "R15": {
      "repo_id": "nvidia/bigvgan_v2_44khz_128band_512x",
      "revision": "95a9d1dcb12906c03edd938d77b9333d6ded7dfb"
    },
    "R16": {
      "repo_id": "DeepBeepMeep/Wan2.2",
      "revision": "cf8a5e27316cb4004227c31224050c6f266d9e54"
    }
  },
  "assets": [
    {
      "id": "L-D",
      "repo": "R1",
      "file": "diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
      "dest": "ComfyUI/models/diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
      "bytes": 21504034224,
      "sha256": "c4279eeff115cbeaca494bd2183e7d768c38fe85a184dc6afbb7159157c44334"
    },
    {
      "id": "L-TE",
      "repo": "R1",
      "file": "text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
      "dest": "ComfyUI/models/text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
      "bytes": 15372969374,
      "sha256": "6ce688a0aa98a5fa36a9f1e6c3f42152a498cc2b53ee8c15674c64244f91487f"
    },
    {
      "id": "L-CV",
      "repo": "R1",
      "file": "vae/ltx-2.5-video-vae-conv-bf16.safetensors",
      "dest": "ComfyUI/models/vae/ltx-2.5-video-vae-conv-bf16.safetensors",
      "bytes": 1452269922,
      "sha256": "685b06ee3d9b2039647698fc4ea33175112462fc374e2777312c907897dfce8d"
    },
    {
      "id": "L-DV",
      "repo": "R1",
      "file": "vae/ltx-2.5-video-vae-bf16.safetensors",
      "dest": "ComfyUI/models/vae/ltx-2.5-video-vae-bf16.safetensors",
      "bytes": 1472223346,
      "sha256": "847e14ca7f3355debca0cea4eaa24ac0fbcdf0061da054ac89ca638a869ddba3"
    },
    {
      "id": "L-AV",
      "repo": "R1",
      "file": "vae/ltx-2.5-audio-vae-bf16.safetensors",
      "dest": "ComfyUI/models/vae/ltx-2.5-audio-vae-bf16.safetensors",
      "bytes": 364866540,
      "sha256": "c52733d37f6a7fb7949c3dc0fb468c6cb2169e4d836983a73babb9f0d54837a5"
    },
    {
      "id": "L-UP",
      "repo": "R1",
      "file": "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
      "dest": "ComfyUI/models/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
      "bytes": 995778752,
      "sha256": "eb5a71fe4068ee87ccdb1c3aa635e547ca76bd2d30ae20ae889f2c325c0677e8"
    },
    {
      "id": "L-Q6",
      "repo": "R2",
      "file": "LTX-2.5-Distilled-Q6_K.gguf",
      "dest": "ComfyUI/models/unet/LTX-2.5-Distilled-Q6_K.gguf",
      "bytes": 18659348480,
      "sha256": "fcf52206e0a0a4534a6421d0c79ba3155145a525d3104ebcbf3f1cb86ab44389"
    },
    {
      "id": "L-Q4",
      "repo": "R2",
      "file": "LTX-2.5-Distilled-Q4_K_M.gguf",
      "dest": "ComfyUI/models/unet/LTX-2.5-Distilled-Q4_K_M.gguf",
      "bytes": 15086587904,
      "sha256": "41504b7ad8cc97bdaeef1513e1e42d333879dfed48eabcfdc3cbd680134012ba"
    },
    {
      "id": "L-M17",
      "repo": "R3",
      "file": "LTX25-distilled-DiT-comfy-mix4x8-17GB.safetensors",
      "dest": "ComfyUI/models/diffusion_models/LTX25-distilled-DiT-comfy-mix4x8-17GB.safetensors",
      "bytes": 17010342592,
      "sha256": "bc60f65a29499eae96b431b39970d84f9c43ddc7669de54da840a567d8838047"
    },
    {
      "id": "H-D",
      "repo": "R4",
      "file": "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
      "dest": "ComfyUI/models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
      "bytes": 20970379616,
      "sha256": "e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a"
    },
    {
      "id": "H-W6",
      "repo": "R4",
      "file": "diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors",
      "dest": "ComfyUI/models/diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors",
      "bytes": 15983746636,
      "sha256": "ac746a2e41628ab25afd44d2b22a7fab8d7e66cd07a01bf89ed9d74b0d3f0c35"
    },
    {
      "id": "H-TE",
      "repo": "R4",
      "file": "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
      "dest": "ComfyUI/models/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
      "bytes": 27141342152,
      "sha256": "bc2ced0fbea64757fa9acddccfc0b3f4819d1dcf1da6c124d690d368be283923"
    },
    {
      "id": "H-TE4",
      "repo": "R4",
      "file": "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
      "dest": "ComfyUI/models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
      "bytes": 15687142551,
      "sha256": "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6"
    },
    {
      "id": "H-V",
      "repo": "R4",
      "file": "vae/minimax_h3_video_vae_int8_convrot.safetensors",
      "dest": "ComfyUI/models/vae/minimax_h3_video_vae_int8_convrot.safetensors",
      "bytes": 2811065184,
      "sha256": "52a2c8c73583c86e4f41cdcce3a6ad0ea562987bc0bf3d60a0cef5f5c8e60c0e"
    },
    {
      "id": "H-A",
      "repo": "R4",
      "file": "vae/minimax_h3_audio_vae_fp32.safetensors",
      "dest": "ComfyUI/models/vae/minimax_h3_audio_vae_fp32.safetensors",
      "bytes": 605254808,
      "sha256": "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48"
    },
    {
      "id": "H-LARRY",
      "repo": "R5",
      "file": "minimax_h3_turbo_v4_step600_ema.safetensors",
      "dest": "ComfyUI/models/loras/minimax_h3_turbo_v4_step600_ema.safetensors",
      "bytes": 779849816,
      "sha256": "5f3a626cd72c93a8b9318d6760c510bc5092d2ab13aaba1f932c5bab07a416d3"
    },
    {
      "id": "H-LX8",
      "repo": "R7",
      "file": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
      "dest": "ComfyUI/models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
      "bytes": 1956193000,
      "sha256": "2339acdf19bfe123f46b971ea35d367a84adb85de43627e1eceafa5a5b2b111e"
    },
    {
      "id": "H-HYPER",
      "repo": "R6",
      "file": "minimax_h3_hyperflow_8step_v1.0_comfyui_pruned_bf16.safetensors",
      "dest": "ComfyUI/models/loras/minimax_h3_hyperflow_8step_v1.0_comfyui_pruned_bf16.safetensors",
      "bytes": 3912313312,
      "sha256": "d8e9c618c12614aeae605a1fb7da42ae626ba79b8d53f534dfbfb119de28f06f"
    },
    {
      "id": "W-H3",
      "repo": "R8",
      "file": "MiniMax-H3-FL2VA-pruned_rank8_int8_convrot.safetensors",
      "dest": "Wan2GP/ckpts/MiniMax-H3-FL2VA-pruned_rank8_int8_convrot.safetensors",
      "bytes": 21057674787,
      "sha256": "30ff400f974b11a1ef13d216c5d9f6439a9c10322a3988b0374a39672ce286f0"
    },
    {
      "id": "W-TE",
      "repo": "R8",
      "file": "Qwen3-VL-32B-Instruct/Qwen3-VL-32B-Instruct-layer50_quanto_bf16_int8.safetensors",
      "dest": "Wan2GP/ckpts/Qwen3-VL-32B-Instruct/Qwen3-VL-32B-Instruct-layer50_quanto_bf16_int8.safetensors",
      "bytes": 26723791903,
      "sha256": "4df8fc5237746b3b058745d6ec8fe1e54a9721bdc663d35d2d1806952672f301"
    },
    {
      "id": "W-V",
      "repo": "R8",
      "file": "minimax_h3/minimax_h3_video_vae_int8_convrot.safetensors",
      "dest": "Wan2GP/ckpts/minimax_h3/minimax_h3_video_vae_int8_convrot.safetensors",
      "bytes": 2811065184,
      "sha256": "52a2c8c73583c86e4f41cdcce3a6ad0ea562987bc0bf3d60a0cef5f5c8e60c0e"
    },
    {
      "id": "W-A",
      "repo": "R8",
      "file": "MiniMax-H3-audio_vae_fp32.safetensors",
      "dest": "Wan2GP/ckpts/MiniMax-H3-audio_vae_fp32.safetensors",
      "bytes": 605429308,
      "sha256": "37dddc2f3e6d5d5139d823d5ea283bbf304dadcb885b1ccda818aa13dade5ea2"
    },
    {
      "id": "W-UP",
      "repo": "R8",
      "file": "minimax_h3/minimax_h3_latent_upscaler_3d_bf16.safetensors",
      "dest": "Wan2GP/ckpts/minimax_h3/minimax_h3_latent_upscaler_3d_bf16.safetensors",
      "bytes": 690592992,
      "sha256": "4f57821f5837f32f7142b67d815606dbd7550f194e5c769f7d6c3f83b146a5e6"
    },
    {
      "id": "W-PDD",
      "repo": "R8",
      "file": "minimax_h3_fl2va_pdd_8step_heads_bf16.safetensors",
      "dest": "Wan2GP/ckpts/minimax_h3_fl2va_pdd_8step_heads_bf16.safetensors",
      "bytes": 44049080,
      "sha256": "4073ac7c77c76e8beaa9e6676d94a33d9e449826d880d1eadd6e93854a9710a9"
    },
    {
      "id": "W-PDDL",
      "repo": "R8",
      "file": "loras/minimax_h3_fl2va_pdd_8step_lora_bf16.safetensors",
      "dest": "Wan2GP/loras/minimax_h3/minimax_h3_fl2va_pdd_8step_lora_bf16.safetensors",
      "bytes": 1328407024,
      "sha256": "c59d2b8661bb0dba7b09b8dae22059145576cc63e6f1203cc4d875310928c2bb"
    },
    {
      "id": "W-LX4",
      "repo": "R8",
      "file": "loras/minimax_h3_lightx2v_fl2v_turbo_4step_alpha8_v1.2_768p_bf16.safetensors",
      "dest": "Wan2GP/loras/minimax_h3/minimax_h3_lightx2v_fl2v_turbo_4step_alpha8_v1.2_768p_bf16.safetensors",
      "bytes": 1383708248,
      "sha256": "c85d39eaa1c743f3efea61dfb47ee5924fb6f7011ece924a9498f9eecd795f3f"
    },
    {
      "id": "W-T1",
      "repo": "R8",
      "file": "Qwen3-VL-32B-Instruct/config.json",
      "dest": "Wan2GP/ckpts/Qwen3-VL-32B-Instruct/config.json",
      "bytes": 1474,
      "sha256": null
    },
    {
      "id": "W-T2",
      "repo": "R8",
      "file": "Qwen3-VL-32B-Instruct/tokenizer.json",
      "dest": "Wan2GP/ckpts/Qwen3-VL-32B-Instruct/tokenizer.json",
      "bytes": 7032403,
      "sha256": null
    },
    {
      "id": "W-T3",
      "repo": "R8",
      "file": "Qwen3-VL-32B-Instruct/tokenizer_config.json",
      "dest": "Wan2GP/ckpts/Qwen3-VL-32B-Instruct/tokenizer_config.json",
      "bytes": 11004,
      "sha256": null
    },
    {
      "id": "W-T4",
      "repo": "R8",
      "file": "Qwen3-VL-32B-Instruct/preprocessor_config.json",
      "dest": "Wan2GP/ckpts/Qwen3-VL-32B-Instruct/preprocessor_config.json",
      "bytes": 390,
      "sha256": null
    },
    {
      "id": "W-T5",
      "repo": "R8",
      "file": "Qwen3-VL-32B-Instruct/vocab.json",
      "dest": "Wan2GP/ckpts/Qwen3-VL-32B-Instruct/vocab.json",
      "bytes": 2776833,
      "sha256": null
    },
    {
      "id": "K-LITE",
      "repo": "R9",
      "file": "transformer/diffusion_pytorch_model.safetensors",
      "dest": "ComfyUI/models/diffusion_models/Kandinsky-6.0-Lite-distill-5s-Diffusers/transformer/diffusion_pytorch_model.safetensors",
      "bytes": 6381599096,
      "sha256": "b1b52668561d9138d93bb4da13c9999e615bf569be9f8cf65732d54652447f53"
    },
    {
      "id": "K-PRO",
      "repo": "R10",
      "file": "transformer/diffusion_pytorch_model.safetensors",
      "dest": "ComfyUI/models/diffusion_models/Kandinsky-6.0-Pro-distill-5s-Diffusers/transformer/diffusion_pytorch_model.safetensors",
      "bytes": 60344993576,
      "sha256": "f84ea3266560bbd1f203a874b8cee43e080073820facaf3306cab8fae2798a97"
    },
    {
      "id": "K-PRO8",
      "repo": "R11",
      "file": "kandinsky6_pro_distill_int8_convrot.safetensors",
      "dest": "ComfyUI/models/diffusion_models/kandinsky6_pro_distill_int8_convrot.safetensors",
      "bytes": 31447593829,
      "sha256": "e2f58e8016bab049a9005b3f3664ad4342bd760e4e409d538d691f0b331c18d3"
    },
    {
      "id": "K-TE",
      "repo": "R12",
      "file": "split_files/text_encoders/qwen_2.5_vl_7b.safetensors",
      "dest": "ComfyUI/models/text_encoders/qwen_2.5_vl_7b.safetensors",
      "bytes": 16584415576,
      "sha256": "cfafd739459bc86257397259f612a9aee88e5b98e85b5c0d0d1717e898b3463a"
    },
    {
      "id": "K-CLIP",
      "repo": "R13",
      "file": "split_files/text_encoders/clip_l.safetensors",
      "dest": "ComfyUI/models/text_encoders/clip_l.safetensors",
      "bytes": 246144152,
      "sha256": "660c6f5b1abae9dc498ac2d21e1347d2abdb0cf6c0c0c8576cd796491d9a6cdd"
    },
    {
      "id": "K-V",
      "repo": "R13",
      "file": "split_files/vae/hunyuan_video_vae_bf16.safetensors",
      "dest": "ComfyUI/models/vae/hunyuan_video_vae_bf16.safetensors",
      "bytes": 492984198,
      "sha256": "e8f8553275406d84ccf22e7a47601650d8f98bdb8aa9ccfdd6506b57a9701aed"
    },
    {
      "id": "K-A",
      "repo": "R14",
      "file": "ext_weights/v1-44.pth",
      "dest": "ComfyUI/models/audio_vae/v1-44.pth",
      "bytes": 1221942998,
      "sha256": "ab6cc15dc31947675f75c950c41f4dcfd0d6d1817555ac871f809ec388e4651a"
    },
    {
      "id": "K-VOC",
      "repo": "R15",
      "file": "bigvgan_generator.pt",
      "dest": "ComfyUI/models/audio_vae/bigvgan_vocoder/bigvgan_generator.pt",
      "bytes": 489041291,
      "sha256": "d9fe7ec6bd0b44ed9d66973d5012d8181c1570b01e5c72df51973e241dccd357"
    },
    {
      "id": "K-VCFG",
      "repo": "R15",
      "file": "config.json",
      "dest": "ComfyUI/models/audio_vae/bigvgan_vocoder/config.json",
      "bytes": 1403,
      "sha256": null
    },
    {
      "id": "B-H",
      "repo": "R16",
      "file": "bernini_r_wan2.2_high_quanto_bf16_int8.safetensors",
      "dest": "Wan2GP/ckpts/bernini_r_wan2.2_high_quanto_bf16_int8.safetensors",
      "bytes": 14532497697,
      "sha256": "29baa458c30b6110725334f84c05ee389a9c3cfa267ea463f1f9420f2c10015b"
    },
    {
      "id": "B-L",
      "repo": "R16",
      "file": "bernini_r_wan2.2_low_quanto_bf16_int8.safetensors",
      "dest": "Wan2GP/ckpts/bernini_r_wan2.2_low_quanto_bf16_int8.safetensors",
      "bytes": 14532497697,
      "sha256": "e0aeac07735c9de28f48dd9b3a31c17647ace7297b91caf83f45ffd6ddb9453c"
    }
  ],
  "trials": {
    "L01": [
      "L-D",
      "L-TE",
      "L-CV",
      "L-AV",
      "L-UP"
    ],
    "L02": [
      "L-D",
      "L-TE",
      "L-DV",
      "L-AV",
      "L-UP"
    ],
    "L03": [
      "L-Q6",
      "L-TE",
      "L-CV",
      "L-AV",
      "L-UP"
    ],
    "L03-Q4": [
      "L-Q4",
      "L-TE",
      "L-CV",
      "L-AV",
      "L-UP"
    ],
    "L04": [
      "L-M17",
      "L-TE",
      "L-CV",
      "L-AV",
      "L-UP"
    ],
    "L05": [
      "L-D",
      "L-TE",
      "L-CV",
      "L-AV"
    ],
    "H01": [
      "W-H3",
      "W-TE",
      "W-V",
      "W-A",
      "W-UP",
      "W-T1",
      "W-T2",
      "W-T3",
      "W-T4",
      "W-T5",
      "W-PDD",
      "W-PDDL"
    ],
    "H02": [
      "H-D",
      "H-TE",
      "H-V",
      "H-A",
      "H-LARRY"
    ],
    "H03": [
      "W-H3",
      "W-TE",
      "W-V",
      "W-A",
      "W-UP",
      "W-T1",
      "W-T2",
      "W-T3",
      "W-T4",
      "W-T5",
      "W-LX4"
    ],
    "H04": [
      "H-D",
      "H-TE",
      "H-V",
      "H-A",
      "H-LX8"
    ],
    "H05": [
      "H-D",
      "H-TE",
      "H-V",
      "H-A",
      "H-HYPER"
    ],
    "H06": [
      "H-D",
      "H-TE",
      "H-V",
      "H-A"
    ],
    "H07": [
      "H-W6",
      "H-TE",
      "H-V",
      "H-A",
      "H-LARRY"
    ],
    "H-TE4": [
      "H-TE4"
    ],
    "C01": [
      "K-TE",
      "K-CLIP",
      "K-V",
      "K-A",
      "K-VOC",
      "K-VCFG",
      "K-LITE"
    ],
    "C02": [
      "K-TE",
      "K-CLIP",
      "K-V",
      "K-A",
      "K-VOC",
      "K-VCFG",
      "K-PRO8"
    ],
    "C03": [
      "K-TE",
      "K-CLIP",
      "K-V",
      "K-A",
      "K-VOC",
      "K-VCFG",
      "K-PRO"
    ],
    "B01": [
      "B-H",
      "B-L"
    ]
  }
}
```

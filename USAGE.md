# MiniMax-H3 使用方式

新影片工作請先使用 [Colab Video Studio](skills/colab-video-studio/SKILL.md) 與[可執行流程](skills/colab-video-studio/references/workflow.md)。這份指南保留單片 H3 notebook 的設定與操作，不能以其技術 PASS 取代新流程的人物／動作／接點驗收。

開啟 [MiniMax_H3_A100.ipynb](notebooks/MiniMax_H3_A100.ipynb)。**A 區只做一次；之後每片只修改並執行 B 區。** 片長可調整為 5–15 秒（每秒一格），解析度由 B 區選擇；輸出為 24 FPS、立體聲。

```text
A 區：模型選單 -> 檢查硬體 -> 安裝 -> 下載 -> 載入模型
                                                    |
B 區：本片 prompt / 首尾圖 -> 產片、驗證、預覽 <------+
                ^                    |
                +------ 下一片 ------+
```

模型模式、量化配套與推論參數見 [H3 模型契約](skills/minimax-h3-colab/references/models.md)。目前只有之前的原版 BF16／50-step／15s／480p 在 A100 80GB 完整實測；新增 Turbo、量化及續片模式尚未 GPU 實測。

## 1. 啟動與模型選單

### Colab 網站

1. 在 [Colab](https://colab.research.google.com/) 上傳 reusable notebook，選擇 GPU runtime，建議 high RAM。
2. 在 **1. 模型與量化選單** 選定模型與權重，再依序執行 **1–5**。
3. 看到「模型已就緒」後，移到下方 **6. 本片內容**。
4. 填好內容，執行 **6**，再執行 **7. 產片、驗證與預覽**。
5. 下一片只重做 **6–7**，不要使用「全部執行」。

建議組合：

| 使用情境 | 模型選單 | 權重選單 |
| :--- | :--- | :--- |
| 有 80GB，先求品質與速度平衡 | Turbo 8-step v1.0 768p | BF16 original |
| 40GB，先評估實用量化 | Turbo 8-step v1.0 768p | INT8 ConvRot pruned |
| 想縮小下載與權重佔用 | Turbo 8-step v1.0 768p | NF4 pruned |
| 快速試動作／構圖 | Turbo 4-step v1.2 768p | 沿用選定的權重格式 |
| 比較 Turbo 是否犧牲畫質 | Original 50-step | BF16 original，或維持同一量化方便對照 |

40GB 標示是待驗證候選，80GB 標示是建議容量；都不是所有片長／解析度的成功保證。V100 沒有 40GB 版本，這份 notebook 的 BF16 運算也不支援 V100。硬體格會顯示實際 GPU 並檢查相容性。

模型 steps、video shift 和 audio shift 由選項一起設定，日常產片不用手動改。若真的要換模型／量化，修改 **1** 並重新執行 **1–5**；相同設定會沿用已載入的 pipeline。新 runtime／kernel 需要重新初始化；只重新啟動 kernel 通常保留磁碟快取，停止 VM 則不保證保留。

### Agent／終端機

本機 CLI 已安裝及認證。先檢查現有 session：

```bash
cd /path/to/colab-utils
colab --auth oauth2 usage
colab --auth oauth2 sessions
```

沒有 `minimax-h3-a100` 時才建立：

```bash
colab --auth oauth2 new -s minimax-h3-a100 --gpu A100 --high-mem
```

在本機 notebook 編輯器選好模型／權重。只匯出 A 區並執行一次：

```bash
python3 scripts/export_cells.py setup --output /tmp/h3-setup.py
colab --auth oauth2 exec -s minimax-h3-a100 \
  -f /tmp/h3-setup.py --timeout 7200
```

之後修改 notebook 的 **6. 本片內容**，每片只執行下面兩行：

```bash
python3 scripts/export_cells.py clip --output /tmp/h3-clip.py
colab --auth oauth2 exec -s minimax-h3-a100 \
  -f /tmp/h3-clip.py --timeout 7200
```

這兩次 `exec` 必須使用**相同 session 與 kernel**。B 區不包含安裝、下載或模型重載；模型未就緒或選項已變更時會停止並提示先完成 A 區。匯出腳本使用標準函式庫，沒有額外本機套件需求。

CLI 0.7.2 即使遠端 Python 失敗也可能回傳 exit code 0。請檢查本次輸出的 `PASS`、資料夾與 `metrics.json` 中的 `"status": "verified"`。Python 分區執行不產生 `_output.ipynb`，也不覆蓋已保存的歷史 notebook。

## 2. 每片只改下方內容

| 欄位 | 用途 |
| :--- | :--- |
| `RUN_NAME` | 片名，英數／底線／連字號；每次自動加時間戳，不覆蓋前次 |
| `PROMPT` | 場景、動作、鏡頭、時間順序、音效／對白 |
| `FIRST_IMAGE_PATH` | Colab 上的首圖路徑；留空則不用 |
| `LAST_IMAGE_PATH` | Colab 上的尾圖路徑；留空則不用 |
| `CONTINUE_PREVIOUS` | 使用本 kernel 上一片成功驗證影片的最後一格作首圖 |
| `DURATION_SECONDS` | 5–15 秒，每秒可調；預設 5 秒 |
| `RESOLUTION` | 480p 或 768p，橫向／直向 |
| `SEED` | 預設 `random`，每次產片使用新 seed；填整數可固定，實際 seed 記在 metrics |

不改 A 區，模型就會繼續沿用。每次產片重新讀取首尾圖，清空欄位也會清除前一片的圖片條件。

H3 使用 24 FPS、`17n+5` 個生成影格；15 秒會先生成 362 格，再保留 360 格。最後兩格被裁掉，所以續片使用**輸出 MP4 的實際最後一格**，不假設輸入尾圖就是輸出末格。[固定版本 pipeline](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/diffsynth/pipelines/minimax_h3_audio_video.py)。

## 3. Prompt 寫法

寫清楚「誰、在哪裡、依序做什麼、鏡頭如何移動、最後停在哪裡、聽到什麼」。時間標記是生成指引，不是精準剪輯指令。例如：

```text
Cinematic CGI at a coastal rocket launch site in daylight.
0–4 seconds: A tall white rocket prepares to launch, with engine rumble
and vapor around the pad. A gigantic gorilla steps out beside the tower.
4–10 seconds: The gorilla grasps the entire rocket with both hands,
lifts it clear of the pad, raises it overhead, and throws it upward.
The rocket clearly leaves its hands.
10–15 seconds: The camera follows the same rocket through the clouds
and into space, ending above the curved blue Earth.
Keep the gorilla's size and the rocket's shape consistent.
Audio: heavy footsteps, engine rumble, a roar, metal creaking, and a
powerful rushing sound during the throw. No dialogue or on-screen text.
```

大幅快速動作要留意 4-step 的拖影與細節；可以選 8-step 或原版比較。

有首圖時，描述**從這張圖接下來發生什麼**，避免 prompt 重新建立與圖片矛盾的場景。可用 `Use <Picture 1> as the opening frame at 0.00 seconds.` 指定開頭，並描述保留的角色、光線、位置、鏡頭方向。[MiniMax prompt guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md)。

## 4. 首圖、尾圖與參考圖片

在網站的 Files 面板上傳圖片，或從本機上傳：

```bash
colab --auth oauth2 upload -s minimax-h3-a100 refs/start.png /content/start.png
colab --auth oauth2 upload -s minimax-h3-a100 refs/end.png /content/end.png
```

`refs/start.png` 必須是本機存在的圖片；產片欄位填的是**遠端** `/content/start.png`。

| 想要的模式 | 欄位設定 |
| :--- | :--- |
| 文字產片 | 首尾圖空白，`CONTINUE_PREVIOUS = False` |
| 首圖動畫 | 只填 `FIRST_IMAGE_PATH` |
| 首尾圖引導 | 兩個圖片路徑都填 |
| 只引導結尾 | 只填 `LAST_IMAGE_PATH` |
| 續接上一片 | 首圖空白，`CONTINUE_PREVIOUS = True`；尾圖仍可選填 |

首尾圖會被 resize 到輸出畫布，建議先準備相同比例。不要同時勾續接並填首圖，否則會提示兩個來源衝突。

首尾圖是 **FL2VA 端點條件**。若多張人物／風格照片只作為參考，請在 A 區選 `TASK_MODE = "Ref2VA | 多張圖片／多段影片參考"`，並把素材路徑依語意順序填入 B 區 `REFERENCE_PATHS` JSON 陣列。Ref2VA 支援最多 9 張圖片、3 段影片、合計 12 個參考檔；專用 `Ref2VA Turbo 8-step v1.0 768p` adapter 和 `Original 50-step` 都可選，FL2VA 的 Turbo adapter 不可用於 Ref2VA。切換模式後請重新執行 A 區 1–5。 Ref2VA 可選原生 `BF16 original`、`NF4 pruned` 或 `NF4 original`；INT8 尚未接入。BF16 會載入 `Ref2VA/` 下的 transformer、text encoder、video/audio VAE 與 processor。原生 BF16 Ref2VA Turbo8 已在 A100 80GB 完成 7 秒、1312×736 的音畫技術驗證；這不代表分鏡或視覺品質已驗收。離線測試另外驗證下載／載入路徑及 adapter 選擇。需要明確首尾畫面與連續動線時，使用本節的 FL2VA 首尾圖設定，並檢查實際輸出端點。

例如：

```python
REFERENCE_PATHS = '["/content/ref/character_a.jpg", "/content/ref/character_b.jpg"]'
```

[DiffSynth FL2VA 範例](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/examples/minimax_h3/model_inference/MiniMax-H3-FL2VA.py)、[DiffSynth Ref2VA 範例](https://github.com/modelscope/DiffSynth-Studio/blob/7686e54d41d25c0e8ed5f1318acc23b6bb832654/examples/minimax_h3/model_inference/MiniMax-H3-Ref2VA.py)、[Ref2VA Turbo sampling settings](https://recipes.vllm.ai/MiniMaxAI/MiniMax-H3)。

## 5. 保存影片

每次建立 `/content/minimax-h3-runs/<片名>_<時間戳>/`，其中有 `video.mp4`、`metrics.json`、`resources.json`、`prompt.txt`、模型 manifest 和首／中／末格預覽。

網站可在額外一格下載：

```python
from google.colab import files
files.download(str(OUTPUT_PATH))
```

CLI 可用最新**成功驗證**的結果定位，再下載：

```bash
mkdir -p artifacts/rocket_moon
colab --auth oauth2 download -s minimax-h3-a100 \
  /content/minimax-h3-runs/latest.json artifacts/rocket_moon/latest.json
```

接著在本機執行：

```python
import json
import subprocess
from pathlib import Path

destination = Path("artifacts/rocket_moon")
latest = json.loads((destination / "latest.json").read_text())
for filename in ("video.mp4", "metrics.json", "prompt.txt", "preview_last.png", "model_manifest.json"):
    subprocess.run([
        "colab", "--auth", "oauth2", "download", "-s", "minimax-h3-a100",
        f"{latest['run_dir']}/{filename}", str(destination / filename),
    ], check=True)
```

每片改用自己的本機資料夾。若本次失敗，`latest.json` 仍指向**前次成功結果**；先確認本次 `PASS`，不要把舊片誤認為新片。

## 6. 一片接一片

同一 kernel 剛完成 clip A：在 **6** 改片名和 prompt、清空首圖、勾 `CONTINUE_PREVIOUS`，再執行 **6–7**。模型不重載，產生的 clip B 使用 A 的實際最後一格。

如果從本次已下載的影片開始，將下列 `path/to/clip-a.mp4` 換成實際素材路徑，再於本機取最後一格：

```bash
mkdir -p refs
ffmpeg -hide_banner -loglevel error -y \
  -i path/to/clip-a.mp4 \
  -an -fps_mode passthrough -update 1 refs/rocket_end.png
colab --auth oauth2 upload -s minimax-h3-a100 \
  refs/rocket_end.png /content/rocket_end.png
```

上面的命令會從本次素材建立並上傳 `refs/rocket_end.png`；此例假設前片結尾為火箭已在地球上空。設定 `FIRST_IMAGE_PATH = "/content/rocket_end.png"`、`CONTINUE_PREVIOUS = False`，使用以下 prompt：

```text
Use <Picture 1> as the opening frame at 0.00 seconds.
Continue the same shot: the same white-and-black rocket is already
above Earth's blue curved horizon. Preserve its design, orientation,
lighting, and initial screen position. The camera smoothly follows it
as it coasts farther from Earth. The Moon gradually appears ahead,
and the rocket travels toward it. End with the rocket approaching
the Moon while Earth recedes in the background.
Cinematic CGI consistent with the opening image, one continuous shot.
Audio: a soft cinematic low rumble fading to quiet ambience.
No dialogue, text, logos, or return to the launchpad.
```

這份續片 prompt 是操作範例，尚未生成第二片。首圖延續外觀與構圖，但不傳遞前片的運動速度、模型內部狀態或聲軌；仍需檢查接縫。

兩片都下載後，將下列輸入換成本次兩支 15 秒影片的實際路徑，在本機合併：

```bash
ffmpeg -hide_banner -y \
  -i path/to/clip-a.mp4 \
  -i path/to/clip-b.mp4 \
  -filter_complex \
  "[0:v]setpts=PTS-STARTPTS[v0];[0:a]asetpts=PTS-STARTPTS[a0];[1:v]setpts=PTS-STARTPTS[v1];[1:a]asetpts=PTS-STARTPTS[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -crf 18 -preset medium -r 24 \
  -c:a aac -ar 32000 -ac 2 -movflags +faststart -t 30 \
  artifacts/combined-story.mp4
```

兩片需同尺寸、FPS、音訊格式；`-t 30` 是兩支 15 秒的總長，片長不同時改成總秒數。這是直接拼接，不會生成額外過場。聲音接縫需要時再做淡化。clip C 使用 B 的末格，以此類推。

## 7. 結束與疑難排解

下載完所有影片後才停止 runtime：

```bash
colab --auth oauth2 stop -s minimax-h3-a100
colab --auth oauth2 usage
colab --auth oauth2 sessions
```

確認 session 已釋放；沒有其他 runtime 時費率應為零。停止 VM 後，遠端模型、圖片與影片都視為暫存。

| 狀況 | 處理 |
| :--- | :--- |
| 修改 prompt 後還是舊內容 | 先執行 **6** 再執行 **7**；CLI 也要重新匯出 `clip` |
| 提示模型選項已變更 | 先完成 **1–5**；B 區不會偷偷替你載入另一個模型 |
| BF16 切 INT8，提示重新啟動 kernel | 套件已安裝但舊 kernel 已快取缺少後端的模組；重新啟動 kernel 再跑 A 區 |
| GPU out of memory | 先用 480p／5s 檢查；再考慮 INT8／NF4，或 80GB。依失敗 metrics 看實際峰值；不要由檔案大小推斷 |
| 4-step 畫面拖影、音訊差 | 選 8-step 或原版比較；重新跑 A 區換模型。不要只把任意 adapter 步數拉高 |
| 想確認程式流程 | 本機執行 `python3 -m unittest discover -s tests -v`；離線測試不代表 GPU 畫質或記憶體通過 |

可給 agent 的要求範例：「沿用現在已載入的模型，只改 B 區。產生 rocket_moon，15 秒 480p，以前片最後一格續接火箭飛向月球，下載影片與 metrics；全部完成後停止 runtime。」

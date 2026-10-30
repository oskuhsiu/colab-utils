# 執行與資料契約

Python3.10+、FFmpeg／ffprobe、已認證的 Google Colab CLI。指令碼的本機部分只用標準函式庫；GPU runtime 才安裝模型依賴。`VIDEO_SKILL` 是本 SKILL.md 所在目錄；指令從持有 project 的工作區執行。

```bash
VIDEO_SKILL=/path/to/colab-video-studio
python3 "$VIDEO_SKILL/scripts/studio.py" init \
  --project projects/new-film --kind provided-person --request '使用者原文'
```

完成 `assets/` 與 `plan.json` 後：

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" prepare --project projects/new-film
python3 "$VIDEO_SKILL/scripts/studio.py" reserve --project projects/new-film --shot s01
colab --auth oauth2 usage
colab --auth oauth2 sessions
# 只有沒有適用 runtime 時才建立，session 名稱要獨立。
colab --auth oauth2 new -s new-film --gpu "$SELECTED_GPU"
# SELECTED_GPU 依當次允許硬體和已準備配置設定；RAM 選項只在需要時使用。
python3 "$VIDEO_SKILL/scripts/studio.py" submit --project projects/new-film \
  --attempt s01_RETURNED_ID --session new-film --timeout 3600
```

`reserve` 回傳真實 attempt ID，勿照抄示例。`submit` 上傳封存包、執行一段、下載 ZIP，檢查 receipt 與原尺寸完整解碼。成功只到 `technically_valid`。同設定下一段沿用 model；不同 route 切換會釋放舊 adapter。H3 不與 Wan 依賴設定並行執行。

`submit` 的控制器在等遠端執行時，另開本機監看程序，按 [runtime-monitoring.md](runtime-monitoring.md) 持續抓 `progress`、receipt、資源資料與新增日誌。不要讓等待主程序取代監看。當前共用 `studio.py` 沒有完整資源輪詢服務，需明確配置外部 watcher；只呼叫一次 `status` 不符合此規則。

失去連線／逾時：

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" status --project projects/new-film --attempt s01_RETURNED_ID
python3 "$VIDEO_SKILL/scripts/studio.py" fetch --project projects/new-film --attempt s01_RETURNED_ID
```

這是查詢已提交的工作，不重送 inference。VM 消失也不能重新提交原 attempt；本機 ledger 是持久依據。上傳失敗、遠端 Python 失敗、transport 中斷要查具體狀態；本機 CLI 零 exit code 不替代遠端 marker／receipt。

```text
request + characters + source assets
                 |
          prepare immutable job
                 |
       local reserve -> upload -> submit
                 |                 |
                 |          lost reply / VM
                 |                 |
                 |          needs_reconcile
                 v
       generated -> full decode -> technically_valid
                                     |
                             inspect time evidence
                                     |
                       pass / fail / unknown review
                                     |
                          selection + join review
                                     |
                         export + final playback QA
```

## plan.json 的關鍵欄位

`assets` 用穩定 ID：`path` 必須在 project 內，`role` 區分 identity/keyframe/pose/control/mask/face/audio 等，`source` 原始基準或 derived，`status=ready` 表示準備檢查已通過，`derived_from` 儲存源頭。每個 character 的 `identity_assets` 是凍結原始身份基準；對虛構人物也是最初選定的角色圖，不是第N代影片臉。

每個 shot 儲存 `characters`、最終 `prompt`、`inputs` 中實際 asset IDs、寬高／秒數／seed、`start_state`／`end_state`、`transition` 和 `criteria`。`continuous` 的規劃邊界必須吻合，實際效果另由 join QA 判斷。`request.text` 始終儲存使用者原文。

`settings.backend` 與可選 shot.settings 合併。immutable revision、native fps、輸出／模型 frames 由編譯器固定。`budget.max_total_attempts`、`max_attempts_per_shot` 是當次明確試驗範圍，不是這個 skill 的所有任務共用額度。預算變化不自動再生成；每次重試仍以新 reserve 執行。

`qa.event_windows` 每個 action criterion 都需指定 start/end，預設8fps，快速事件可提高至 native fps。`qa.regions` 用原影片像素 `[x,y,width,height]`；可用多個區間檢查臉／手／道具，裁切不會創造原片沒有的細節。

四個介面分別由 `workflow.prepare`、`studio.submit`、`media.evidence`、`media.assemble` 實現。模型邏輯由 backends.py 隔離，不把外部 repo 的 UI、資料庫或商用 API 平臺整個搬進 Colab。

## 檢查與合成

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" inspect --project projects/new-film --attempt s01_RETURNED_ID
```

開啟 `attempts/<id>/evidence/`，填寫 review-template.json 的副本：所有 criterion、實際 reviewer、理由和存在的 evidence IDs；未看清或未聽到寫 unknown。需要 Opus 時見 video-review.md。

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" review --project projects/new-film \
  --attempt s01_RETURNED_ID --file projects/new-film/attempts/s01_RETURNED_ID/review-draft.json
```

`selection.json` 是 shot ID→attempt ID 的 JSON object，必須包含全部 required shots。多段用 `joins`，看其 manifest 指向的左尾／右首、原照及音軌，填寫 join review。

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" joins --project projects/new-film --selection projects/new-film/selection.json
python3 "$VIDEO_SKILL/scripts/studio.py" assemble --project projects/new-film \
  --selection projects/new-film/selection.json --join-review projects/new-film/joins/review.json
colab --auth oauth2 stop -s new-film
colab --auth oauth2 usage
colab --auth oauth2 sessions
```

合成後依 [評審分工與放行](video-review.md#評審分工與放行) 完成實際成片驗收與交付紀錄；逐段與接點通過不替代成片放行。

較長的 QA 開始前即可先停止 runtime；不需要等合成完成才停止。輸入 ZIP、local job/ledger、result、technical metadata、review 與 delivery report 全保留。最終檔案已存在時不覆蓋；新剪輯／新要求使用新 project revision。

## 原始素材較長時：挑完整動作再剪成指定秒數

複雜交互先留足模型原始序列，再用有來源的剪輯決策製作短片。`delivery.duration_seconds` 可指定整片秒數，`shots[].duration_seconds` 是原始生成長度，兩者不必相同。原始片的內容review通過後，`edits.json` 以shot ID指定 `start`、`end`（原片秒數）和 `duration_seconds`（成片該段秒數）。每個區間都需保留完整要求動作；必要的速度變化不能掩蓋缺失步驟。

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" edit-prepare --project projects/new-film \
  --selection projects/new-film/selection.json --edits projects/new-film/edits.json --run edit01
python3 "$VIDEO_SKILL/scripts/studio.py" edit-inspect --project projects/new-film --run edit01
```

實際編碼後的片段位於 `edits/edit01/segments/<shot>/`，保留原始job／review／影片SHA、剪入出時間、速度、source native fps與delivery fps。這是FFmpeg後製，沒有新model inference。每個剪過的片段都要重新填寫并驗證review，不能沿用原始片通過代替剪輯後通過。可用 `studio.py review --file ...` 或 `workflow.accept_review(directory,file)` 儲存剪後review；前者原本定位attempts，只適合原始片，剪後使用後者的明確directory。

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" edit-joins --project projects/new-film --run edit01
python3 "$VIDEO_SKILL/scripts/studio.py" edit-assemble --project projects/new-film \
  --run edit01 --join-review projects/new-film/joins/review.json
```

接點review必須指向這一次剪輯的實際檔案與SHA。相同原始selection、不同剪輯run不能共用另一個run的join通過。所有剪後段與接點通過、秒數合計符合delivery，才輸出；最後仍看實際成片。當前這個後製介面不處理含pose/depth等時間控制影片的重取樣，以免用原控制時間0錯比剪後時間；需要這類素材時另做完整控制conform。

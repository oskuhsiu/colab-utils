# 執行與資料契約

Python3.10+、FFmpeg／ffprobe、已認證的 Google Colab CLI。指令碼的本機部分只用標準函式庫；GPU runtime 才安裝模型依賴。`VIDEO_SKILL` 是本 SKILL.md 所在目錄；指令從持有 project 的工作區執行。[new-film 計畫樣板](../assets/templates/new-film/plan.json) 是唯讀來源，`init` 會複製到本次指定的 `PROJECT_DIR`；在工作副本編輯，不將製作結果寫回模板目錄。

```bash
VIDEO_SKILL=/path/to/colab-video-studio
PROJECT_DIR=/path/to/current-film
python3 "$VIDEO_SKILL/scripts/studio.py" init \
  --project "$PROJECT_DIR" --kind provided-person --request '使用者原文'
```

完成 `assets/` 與 `plan.json` 後：

新對白／心聲／旁白製作先完成 [對白估時與語速](../../video-production/references/dialogue-pacing.md) 的預算與編譯。Studio 原生 H3 shot 使用 `audio="native"`、`duration_seconds="auto"` 與結構化 `dialogue_timing`；`prepare` 會把逐句目標、生成長度及 `dialogue_timing_result` 寫入 immutable job。刻意固定片長可用數字，發聲目標仍獨立。原生 ComfyUI／Pika 則先用該頁的 `dialogue_timing.py compile-api` 產生實際提交的 API graph 及 report，再進既有批次入口。兩者都在 GPU 配置前核對，不能只在分鏡留下估時。

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" prepare --project "$PROJECT_DIR"
python3 "$VIDEO_SKILL/scripts/studio.py" reserve --project "$PROJECT_DIR" --shot s01
colab --auth oauth2 usage
colab --auth oauth2 sessions
# 只有沒有適用 runtime 時才建立，session 名稱要獨立。
colab --auth oauth2 new -s new-film --gpu "$SELECTED_GPU"
# SELECTED_GPU 依當次允許硬體和已準備配置設定；RAM 選項只在需要時使用。
python3 "$VIDEO_SKILL/scripts/studio.py" submit --project "$PROJECT_DIR" \
  --attempt s01_RETURNED_ID --session new-film --timeout 3600
```

`reserve` 回傳真實 attempt ID，勿照抄示例。Studio 的 `submit` 是單鏡同步入口：上傳封存包、執行一段、下載 ZIP，檢查 receipt 與原尺寸完整解碼，成功只到 `technically_valid`。批次依 [並行排程](runtime-monitoring.md#批次排程生成保存與驗收並行) 拆開執行、保存與審查；原生 ComfyUI 入口見下節，不把同步 `submit → fetch → review` 迴圈當批次控制器。同設定下一段沿用 model；不同 route 切換會釋放舊 adapter。H3 不與 Wan 依賴設定並行執行。

`submit` 的控制器在等遠端執行時，另開本機監看程序，按 [runtime-monitoring.md](runtime-monitoring.md) 持續抓 `progress`、receipt、資源資料與新增日誌。不要讓等待主程序取代監看。當前共用 `studio.py` 沒有完整資源輪詢服務，需明確配置外部 watcher；只呼叫一次 `status` 不符合此規則。

失去連線／逾時：

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" status --project "$PROJECT_DIR" --attempt s01_RETURNED_ID
python3 "$VIDEO_SKILL/scripts/studio.py" fetch --project "$PROJECT_DIR" --attempt s01_RETURNED_ID
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
       backend complete ---------> next ready job on GPU
                 |
       fetch + identity/hash save
                 |
       full decode -> technically_valid -> content review
                                             |
                         authorized new retake -> ready priority queue
                                             |
                              selection + join review
                                             |
                             export + final playback QA
```

## 原生 ComfyUI 批次接續

`ComfyWorkspace.submit_api(workflow_path, prompt_id=...)` 保存原 prompt ID／收據後單次提交並返回；`wait_api(prompt_id, timeout=...)` 只等待／對帳原作業，不下載、不重送。`run_api` 保留為兩者的同步 wrapper。批次以獨立 producer 呼叫這兩個方法，原作業 `execution_complete` 後立刻選下一個 ready job；保存 worker 另用原 history／output 身分取回資料。

共用 `scripts/colab_video_pipeline.py` 提供 `Pipeline` 的持久隊列及單一生成、取回、審查工作線。`enqueue` 放入準備完成的 immutable attempt；`priority="retake"` 讓新修正排在尚未提交的一般 attempts 前。真正有輸入依賴的 attempt 先設 `ready=False`，由負責準備該輸入的控制器在條件成立後 `set_ready`；它不會卡住其他 ready attempts。

隊列封存 payload JSON 與 UUID。若 payload 引用外部 workflow／素材路徑，adapter 在 enqueue 前先放入本次固定快照並記 hash，提交前核對；不讓待跑 job 指向仍會被其他 agent 改動的共用圖檔。修正提示或輸入就建立新的 attempt，既有 attempt 的 payload 保留。

`Pipeline.run` 的 `submit`／`wait` callbacks 接既有 backend，`fetch` callback 負責**實際要求的保存目的地**、來源身分及 hash，`review` callback 在獨立工作線做完整解碼與內容審查。Colab 控制器若在 VM 內，只把 ComfyUI 輸出搬到 VM staging，不等於已取回 Mac；此時外部取回工作也要持續並行，資源擁有者須等真正必要產物已保存後才能釋放。把 `fetch` 接成本機 Colab 下載器時，`on_saved_drain` 才可直接作為保存完成後停止所屬 runtime 的通知。

必要取回尚在進行時，控制器繼續接收新 ready jobs，包括審查後加入的重跑；不先進入只下載、不生成的關閉流程。當沒有 ready jobs 且必要取回已結束，才關閉本輪生成窗口並通知資源擁有者。其後才到達的新工作保留待下一輪准入；已因預算或未知提交停止的批次也不會自行重開。

配置 GPU 前就備好這些 callbacks、待跑 jobs、保存目的地、預算准入及獨立 guard。排程核心不配置／釋放 Colab、不推定授權、不自動重抽；停止仍由既有資源擁有者作用於精確 endpoint。提交狀態不確定時對帳原 ID；傳輸失敗可恢復原產物，不新建一次推論。預算的並行完成時間與單一停止餘量以 [runtime-monitoring.md](runtime-monitoring.md#提交前的預算判斷) 為準。

## plan.json 的關鍵欄位

`assets` 用穩定 ID：`path` 必須在 project 內，`role` 區分 identity/keyframe/pose/control/mask/face/audio 等，`source` 原始基準或 derived，`status=ready` 表示準備檢查已通過，`derived_from` 儲存源頭。每個 character 的 `identity_assets` 是凍結原始身份基準；對虛構人物也是最初選定的角色圖，不是第N代影片臉。

每個 shot 儲存 `characters`、最終 `prompt`、`inputs` 中實際 asset IDs、寬高／秒數／seed、`start_state`／`end_state`、`transition` 和 `criteria`。`continuous` 的規劃邊界必須吻合，實際效果另由 join QA 判斷。`request.text` 始終儲存使用者原文。

情緒種類、felt／shown 強度及劇本依據可作為 shot 的附加內容標註，隨 immutable job 保存並交給審查；任意 plan 頂層標註不會自動進入 job。生成 adapter 讀取的是編譯後 `shot.prompt` 與既定輸入，不會自動將情緒級別轉成表演或推論參數。使用 `dialogue_timing` 時，將逐句語氣放入 `utterances[].delivery`，強度標註不放入 timing 物件／utterance。依 [內容與分鏡](story-planning.md#將情緒強度交給生成與驗收) 核對編譯後 prompt、可觀察的 `criteria` 與必要事件窗，維持既有 schema。

`settings.backend` 與可選 shot.settings 合併。immutable revision、native fps、輸出／模型 frames 由編譯器固定。`budget.max_total_attempts`、`max_attempts_per_shot` 是當次明確試驗範圍，不是這個 skill 的所有任務共用額度。預算變化不自動再生成；每次重試仍以新 reserve 執行。

`qa.event_windows` 每個 action criterion 都需指定 start/end，預設8fps，快速事件可提高至 native fps。`qa.regions` 用原影片像素 `[x,y,width,height]`；可用多個區間檢查臉／手／道具，裁切不會創造原片沒有的細節。

四個介面分別由 `workflow.prepare`、`studio.submit`、`media.evidence`、`media.assemble` 實現。模型邏輯由 backends.py 隔離，不把外部 repo 的 UI、資料庫或商用 API 平臺整個搬進 Colab。

## 檢查與合成

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" inspect --project "$PROJECT_DIR" --attempt s01_RETURNED_ID
```

開啟 `attempts/<id>/evidence/`，填寫 review-template.json 的副本：所有 criterion、實際 reviewer、理由和存在的 evidence IDs；未看清或未聽到寫 unknown。需要 Opus 時見 video-review.md。

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" review --project "$PROJECT_DIR" \
  --attempt s01_RETURNED_ID --file "$PROJECT_DIR/attempts/s01_RETURNED_ID/review-draft.json"
```

`selection.json` 是 shot ID→attempt ID 的 JSON object，必須包含全部 required shots。多段用 `joins`，看其 manifest 指向的左尾／右首、原照及音軌，填寫 join review。

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" joins --project "$PROJECT_DIR" --selection "$PROJECT_DIR/selection.json"
python3 "$VIDEO_SKILL/scripts/studio.py" assemble --project "$PROJECT_DIR" \
  --selection "$PROJECT_DIR/selection.json" --join-review "$PROJECT_DIR/joins/review.json"
colab --auth oauth2 stop -s new-film
colab --auth oauth2 usage
colab --auth oauth2 sessions
```

合成後依 [評審分工與放行](video-review.md#評審分工與放行) 完成實際成片驗收與交付紀錄；逐段與接點通過不替代成片放行。

較長的 QA 開始前即可先停止 runtime；不需要等合成完成才停止。輸入 ZIP、local job/ledger、result、technical metadata、review 與 delivery report 全保留。最終檔案已存在時不覆蓋；新剪輯／新要求使用新 project revision。

## 原始素材較長時：挑完整動作再剪成指定秒數

複雜交互先留足模型原始序列，再用有來源的剪輯決策製作短片。`delivery.duration_seconds` 可指定整片秒數，`shots[].duration_seconds` 是原始生成長度，兩者不必相同。原始片的內容review通過後，`edits.json` 以shot ID指定 `start`、`end`（原片秒數）和 `duration_seconds`（成片該段秒數）。每個區間都需保留完整要求動作；必要的速度變化不能掩蓋缺失步驟。

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" edit-prepare --project "$PROJECT_DIR" \
  --selection "$PROJECT_DIR/selection.json" --edits "$PROJECT_DIR/edits.json" --run edit01
python3 "$VIDEO_SKILL/scripts/studio.py" edit-inspect --project "$PROJECT_DIR" --run edit01
```

實際編碼後的片段位於 `edits/edit01/segments/<shot>/`，保留原始job／review／影片SHA、剪入出時間、速度、source native fps與delivery fps。這是FFmpeg後製，沒有新model inference。每個剪過的片段都要重新填寫并驗證review，不能沿用原始片通過代替剪輯後通過。可用 `studio.py review --file ...` 或 `workflow.accept_review(directory,file)` 儲存剪後review；前者原本定位attempts，只適合原始片，剪後使用後者的明確directory。

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" edit-joins --project "$PROJECT_DIR" --run edit01
python3 "$VIDEO_SKILL/scripts/studio.py" edit-assemble --project "$PROJECT_DIR" \
  --run edit01 --join-review "$PROJECT_DIR/joins/review.json"
```

接點review必須指向這一次剪輯的實際檔案與SHA。相同原始selection、不同剪輯run不能共用另一個run的join通過。所有剪後段與接點通過、秒數合計符合delivery，才輸出；最後仍看實際成片。當前這個後製介面不處理含pose/depth等時間控制影片的重取樣，以免用原控制時間0錯比剪後時間；需要這類素材時另做完整控制conform。

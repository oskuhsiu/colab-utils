# 執行與資料契約

Python3.10+、FFmpeg／ffprobe、已認證的 Google Colab CLI。指令碼的本機部分只用標準函式庫；GPU runtime 才安裝模型依賴。`VIDEO_SKILL` 是本 SKILL.md 所在目錄；指令從持有 project 的工作區執行。[new-film 計畫樣板](../assets/templates/new-film/plan.json) 是唯讀來源，`init` 會複製到本次指定的 `PROJECT_DIR`；在工作副本編輯，不將製作結果寫回模板目錄。

```bash
VIDEO_SKILL=/path/to/colab-video-studio
PROJECT_DIR=/path/to/current-film
python3 "$VIDEO_SKILL/scripts/studio.py" init \
  --project "$PROJECT_DIR" --kind provided-person --request '使用者原文'
```

完成 `assets/` 與 `plan.json` 後：

新對白／心聲／旁白製作先完成 [對白估時與語速](../../video-production/references/dialogue-pacing.md) 的時間預算。一般輪替語音預設使用 compiler；特殊重疊、非支援語言或外部音軌可採該頁明示的 timing-only／人工編譯路徑，記明估計或實測依據、未支援能力與逐句時間，不為工具限制改寫劇本。Studio 原生 H3 shot 使用 `audio="native"`、`duration_seconds="auto"` 與結構化 `dialogue_timing`；`prepare` 會把逐句目標、生成長度及 `dialogue_timing_result` 寫入 immutable job。刻意固定片長可用數字，發聲目標仍獨立。原生 ComfyUI／Pika 則先用該頁的 `dialogue_timing.py compile-api` 產生實際提交的 API graph 及 report，再進既有批次入口。compiler 與替代路徑都在 GPU 配置前核對實際提交內容與模型限制，不能只在分鏡留下估時，也不把人工規劃冒稱實測。

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

### 支援模式與監看邊界

`studio.py submit` 支援**有人監督的單鏡同步工作**，不假裝已提供無人值守的批次成本控制器。先核對已授權的時間／CU／嘗試限制、確切 session 與可用停止入口；操作者須保持可介入。`--timeout` 是 transport 等候時間，**不會停止遠端 GPU 或計費**。不能監督、不能確認停止入口或不能保證當次成本上限時，不開始付費工作。

可在另一個程序執行已提供的唯讀 watcher：

```bash
python3 "$VIDEO_SKILL/scripts/watch_attempt.py" --project "$PROJECT_DIR" \
  --attempt s01_RETURNED_ID --duration 300 --interval 10 --poll-timeout 30
```

它只下載原 attempt 的 progress、核對 job 身分並保存 `watch-state.json`，不重新提交。每次讀取及整輪監看都有期限；缺資料、身分不符或 transport 失敗就回報 `needs_reconcile`。`generated` 仍須 `fetch` 與 hash／完整解碼確認，監看逾時也不等於工作停止。此 watcher **不量測 CU、不釋放 runtime、不取代硬停止 guard**。

無人值守或長批次只有在外部控制器已接好 endpoint 專屬成本准入、獨立停止／釋放與原 ID 對帳，並驗證其失敗路徑後才可使用。缺少這些能力時採上述有人監督單鏡流程或暫停，不能要求 agent 臨時拼接一套後宣稱具備可靠批次保護。

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

此節是進階整合 API，不是開箱可用的批次 runner。配置 GPU 前就備好並測試這些 callbacks、待跑 jobs、保存目的地、預算准入及獨立 guard；無完整接線時使用上方有人監督模式，不自行把同步 submit 冒充無人值守批次。排程核心不配置／釋放 Colab、不推定授權、不自動重抽；停止仍由既有資源擁有者作用於精確 endpoint。提交狀態不確定時對帳原 ID；傳輸失敗可恢復原產物，不新建一次推論。預算的並行完成時間與單一停止餘量以 [runtime-monitoring.md](runtime-monitoring.md#提交前的預算判斷) 為準。

## plan.json 的關鍵欄位

跨鏡的角色／場景／道具／聲線名稱綁定，或已有配音音軌的共用量測／字幕／剪輯時鐘，可按需使用 [共用引用與音訊](reference-audio.md)。它編譯到下列既有 asset IDs／inputs，不增加生成路徑；沒有這些需求時保留原格式。

`assets` 用穩定 ID：`path` 必須在 project 內，`role` 區分 identity/keyframe/pose/control/mask/face/audio 等，`source` 原始基準或 derived，`status=ready` 表示準備檢查已通過，`derived_from` 儲存源頭。每個 character 的 `identity_assets` 是凍結原始身份基準；對虛構人物也是最初選定的角色圖，不是第N代影片臉。

每個 shot 儲存 `characters`、最終 `prompt`、`inputs` 中實際 asset IDs、寬高／秒數／seed、`start_state`／`end_state`、`transition` 和 `criteria`。`continuous` 的規劃邊界必須吻合，實際效果另由 join QA 判斷。`request.text` 始終儲存使用者原文。

情緒種類、felt／shown 強度及劇本依據可作為 shot 的附加內容標註，隨 immutable job 保存並交給審查；任意 plan 頂層標註不會自動進入 job。生成 adapter 讀取的是編譯後 `shot.prompt` 與既定輸入，不會自動將情緒級別轉成表演或推論參數。使用 `dialogue_timing` 時，將逐句語氣放入 `utterances[].delivery`，強度標註不放入 timing 物件／utterance。依 [內容與分鏡](story-planning.md#將情緒強度交給生成與驗收) 核對編譯後 prompt、可觀察的 `criteria` 與必要事件窗，維持既有 schema。

`dialogue_timing.action_beats` 是可選的 [局部動作窗](../../video-production/references/dialogue-pacing.md#局部動作窗)：每項 `start_seconds`／`end_seconds`／`description`，可加 `playback`。它與台詞共用片內時鐘但不互相拉長；無台詞可省略 `utterances`，保留 `audio="none"`。Studio 會把動作寫進 H3 或 Wan 的最終 prompt；已匯入獨立音軌的路徑也編譯動作，不再加入原生台詞或重排錄音。H3 用原有動態欄位，Wan 用一般提示文字，各沿用自身 frame 格。`description` 的 typed references 與 base prompt 一樣只解析實際已供圖；其他入口使用已解析的 provider labels。這不是物理硬控制，`motion_precision="strict"` 仍須控制素材與對應 backend。

`settings.backend` 與可選 shot.settings 合併。immutable revision、native fps、輸出／模型 frames 由編譯器固定。`budget.max_total_attempts`、`max_attempts_per_shot` 是當次明確試驗範圍，不是這個 skill 的所有任務共用額度。預算變化不自動再生成；每次重試仍以新 reserve 執行。提交會在鎖內重新核對當前額度、建立唯一 claim，並在上傳完成、遠端執行前再核對一次。已預約、失敗或結果不明的 attempt 仍消耗額度；若後來降低上限到既有預約數以下，新的提交會 fail closed，不上傳／不執行（上傳期間降低則不執行）。此時明確對帳當次授權，不刪除歷史來繞過額度；已生成影片仍可取證／審查／剪輯。

`qa.event_windows` 每個 action criterion 都需指定 start/end，預設8fps，快速事件可提高至 native fps。`qa.regions` 用原影片像素 `[x,y,width,height]`；可用多個區間檢查臉／手／道具，裁切不會創造原片沒有的細節。

四個介面分別由 `workflow.prepare`、`studio.submit`、`media.evidence`、`media.assemble` 實現。模型邏輯由 backends.py 隔離，不把外部 repo 的 UI、資料庫或商用 API 平臺整個搬進 Colab。

## 檢查與合成

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" inspect --project "$PROJECT_DIR" --attempt s01_RETURNED_ID
```

`inspect` 使用當前計畫的 QA／criteria 產生新證據版本，不重新生成影片；舊版本保留，舊 review 不會自動通過新規格。開啟 `attempts/<id>/evidence/manifest.json` 所指的版本，填寫 review-template.json 的副本：所有 criterion、實際 reviewer、理由和存在的 evidence IDs；未看清或未聽到寫 unknown。需要 Opus 時見 video-review.md。

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

預設 `assemble`／`edit-assemble` 仍要求所有片段與接點通過。使用者只要試片或已接受缺陷時，可明確指定 `--preview --preview-reason '當次試片目的與未通過項'`，輸出命名為 `preview.mp4` 與帶狀態的報告，不產生合格成片宣告；身分、hash、完整解碼與剪輯來源檢查仍不可跳過。

合成後依 [評審分工與放行](video-review.md#評審分工與放行) 完成實際成片驗收與交付紀錄；逐段與接點通過不替代成片放行。

較長的 QA 開始前即可先停止 runtime；不需要等合成完成才停止。輸入 ZIP、local job/ledger、result、technical metadata、review 與 delivery report 全保留。最終檔案已存在時不覆蓋；新剪輯／新要求使用新 project revision。

## 原始素材較長時：挑完整動作再剪成指定秒數

複雜交互先留足模型原始序列，再用有來源的剪輯決策製作短片。`delivery.duration_seconds` 可指定整片秒數，`shots[].duration_seconds` 是原始生成長度，兩者不必相同。原始片通過來源身分、hash 與完整解碼後，即可用 `edits.json` 以shot ID指定 `start`、`end`（原片秒數）和 `duration_seconds`（成片該段秒數）。原始內容 review 可為 fail／unknown 或尚未審查，保留其狀態供剪後評審；不能把裁切本身當品質通過。每個區間都需保留完整要求動作；必要的速度變化不能掩蓋缺失步驟。

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

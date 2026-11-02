# 對白估時與語速

新製作有對白、心聲或旁白時，先建立逐句語音預算，再選生成長度。台詞的自然發聲時間、句間刻意停頓、換人、動作與反應分開記錄；較長鏡頭或模型最短長度不表示要放慢台詞填滿全片。情緒與聲線沿用表演設計，只有需要時才明確改變語速；「緊張」「低聲」本身不等於慢速。

## 建立可調整的估計

已有整段配音 WAV 且需要重用字幕／剪輯時間時，可按需用 [共用音訊產物](../../colab-video-studio/references/reference-audio.md) 匯入實際 PCM 量測與已提供的逐句／對齊邊界，再由本 planner 編譯；不必手抄秒數。該路徑不執行 TTS／ASR，不會把估時當 alignment，也不改變原生 H3 的聲畫生成路徑。

優先使用符合當句表演的試讀或已有配音實測秒數 `measured_utterance_seconds`（包含句內停頓）；此時不再加標點停頓，也不再套 `rate_multiplier`。尚無實測時，共用離線 planner 以漢字及拉丁文字詞估計。起始 policy 是漢字每秒5字、拉丁文字每秒2.8詞，逗號0.12秒、句末0.25秒、省略號0.35秒、換人0.2秒、開場0.25秒及收尾0.35秒。這些是可調整的工作假設，並非各語言、演員或模型的固定自然語速；依題材、試讀和使用者回饋調整 `policy` 或逐句 `rate_multiplier`。

數字、縮寫與混語需先按真正念法寫出，或提供實測。拉丁字詞包含重音字母，NFC／NFD 拼法採相同計數；不同語言仍需指定正確 `language`，估計速率不是通用語言事實。其他文字系統可提供實測，或明確標示未實測的 `planned_utterance_seconds` 與必填 `timing_note`；後者含句內停頓，不可冒稱量測。兩種秒數不得同時提供。逐句 `delivery` 保留語氣；避免同時寫互相衝突的慢速要求或另一套發聲時間窗。

```json
{
  "utterances": [
    {"speaker": "甲", "text": "等一下，你看見了嗎？", "language": "Chinese", "voice_mode": "spoken", "pause_after_seconds": 0.4},
    {"speaker": "乙", "text": "看見了。", "language": "Chinese", "voice_mode": "spoken", "not_before_seconds": 3.5}
  ],
  "action_end_seconds": 7,
  "reaction_seconds": 0.6
}
```

`utterances` 按發聲順序排列，全文不含 `<d>` 標記。`voice_mode` 支援 `spoken`、`inner`、`offscreen`、`telephone`、`narration`、`silent_mouthed_inner`（同一句心聲配無聲嘴型，不新增現場口說），仍須核對實際聲音／嘴型。`not_before_seconds` 是片內最早起點，可表示先完成動作才說話；`pause_after_seconds` 是該句之後的刻意安靜時間，另計換人停頓。`action_end_seconds` 是與對話可並行的動作完成時點，不把全部動作秒數再加到對話上；`reaction_seconds` 接在最後一句及其停頓之後。片長取兩條時間線的較晚末點再加收尾。

## 重疊口說與明確時間線

需要插話、重疊口說或旁白並行時，設 `timing_mode: "explicit"`，每句提供片內 `start_seconds`。此模式不自動串行、不加換人間隔，不能混用 `not_before_seconds`；反應與收尾從所有句子的最晚末點計算。每句仍可用估計、實測或明確未實測的手動目標。這只是可審閱的提示意圖，不保證 H3 能生成正確重疊聲音；按實際能力試片或改用分軌配音／混音，不能未經允許把插話改成輪流講。

```json
{
  "timing_mode": "explicit",
  "utterances": [
    {"speaker": "A", "text": "等等，我還沒說完。", "start_seconds": 0.5, "planned_utterance_seconds": 2.5, "timing_note": "未試讀的工作目標"},
    {"speaker": "B", "text": "我知道！", "start_seconds": 1.5, "measured_utterance_seconds": 0.8}
  ]
}
```

實測欄位只填真實試讀／配音取得的值；範例數字不是任何台詞的實測證據。

## 正常生成入口

一般輪替對白預設使用以下 compiler；在凍結 job、配置 GPU 或提交前，核對逐句時間目標與真正送入模型的 prompt。它不是唯一許可入口。工具不能表達的表演／輸入契約可採下述替代路徑，保留逐句時間依據、版本與未驗證限制；不得靜默改戲或以整段片長代替發聲時間。

**原生 ComfyUI／預設 Pika：** 在當次 project 準備 `timing.json`，並由既有 API starter 建立 `base.api.json`：先換好當次圖片、尺寸、視覺／動作及環境聲提示。移除 starter 的示例 `No text or dialogue.`；base 不放正式台詞 `<d>` 或另一套對白時窗。然後執行 repo 內的共用 compiler：

```bash
python3 skills/colab-video-studio/scripts/dialogue_timing.py plan --input "$PROJECT_DIR/timing.json"
python3 skills/colab-video-studio/scripts/dialogue_timing.py compile-api \
  --input "$PROJECT_DIR/timing.json" --workflow "$PROJECT_DIR/base.api.json" \
  --output "$PROJECT_DIR/shot-v1.api.json" --report "$PROJECT_DIR/shot-v1.timing.json"
```

把產出的 **`shot-v1.api.json`** 交給既有 `ComfyWorkspace.submit_api`／批次保存流程。compiler 只改原生 H3 conditioning node 的 prompt 與 length，保留模型、Pika adapter、採樣、seed、素材綁定和尺寸；輸出不覆寫已有 revision。各句只插入一次，發聲目標不隨片長拉長，剩餘時間留給安靜動作、聆聽和反應。

**Studio `plan.json`：** 新原生 H3 語音 shot 設 `audio: "native"`、`duration_seconds: "auto"`，加上以上物件作為 `dialogue_timing`，再走既有 `studio.py prepare`。它會在 `compile_job` 產生 `dialogue_timing_result`、實際 prompt 與 frame 數；不需另跑第二套生成器。若分鏡刻意需要較長固定鏡頭，可保留數字 `duration_seconds`；語音目標不會因此伸長。其他 backend 先用 `plan` 做離線預算，再依實際工具編譯，不能把 H3 的 frame 格套過去。

H3／Pika 此入口依既有工具契約使用5–15整數秒、24fps、`17n+5` frames 向上量化：5秒要求為124frames（5.1667秒），15秒為362frames（15.0833秒）。例如約3秒台詞仍可生成最短片段，說完後維持安靜反應，再按完整表演剪入；不能要求台詞延伸到5秒。`clip_seconds` 可指定固定生成長度，過短或超限會拒絕，不壓縮或截斷台詞。超過模型上限時，按完整互動重新分配動作／停頓或安排有理由且承接實際末態的分次生成；不一律拆成短句鏡頭。

## 工具不適用時的替代路徑

非原生 H3 graph、分軌聲音或 compiler 尚不能表達的設計，可以只用 `plan` 產出時間報告，再由對應工具或人工編譯到模型契約。也可保留獨立的逐句時間表與實際 prompt，不填 Studio 的 `dialogue_timing`，以免被再次編譯。至少保存台詞、角色／模式、各句起訖、實測或未實測依據、生成片長／幀數與量化核對、實際送出的 graph／prompt。手動編譯必須核對完整台詞無重複或遺漏、聲音／嘴型要求、片長足夠且符合模型限制。

這條路不跳過提交前的成本與授權、不改變最終聲畫驗收，也不把時間表當成輸出已合格。若所選模型實際不支援必要表演，保留能力缺口，提出受授權範圍內的製作方法，不悄悄刪除要求。

## 實際輸出回饋

估算與 prompt 只改善規劃意圖，模型原生發聲仍可能快慢漂移、超窗或忽略停頓。第一次可用試片就聆聽語速及語氣，核對完整台詞與首尾，再以 ASR 字詞時點輔助調整下一批的 policy／delivery。ASR 的首字到末字時間包含中間停頓，字詞時長總和也不等於聲學發聲時長；不能只用字數除以整段秒數宣稱聽感自然。缺少實際聆聽或新生成驗證時，明記未驗證；不要以全片加速代替此規劃修正。

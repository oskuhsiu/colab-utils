# 對白估時與語速

新製作有對白、心聲或旁白時，先建立逐句語音預算，再選生成長度。台詞的自然發聲時間、句間刻意停頓、換人、動作與反應分開記錄；較長鏡頭或模型最短長度不表示要放慢台詞填滿全片。情緒與聲線沿用表演設計，只有需要時才明確改變語速；「緊張」「低聲」本身不等於慢速。

## 建立可調整的估計

優先使用符合當句表演的試讀或已有配音實測秒數 `measured_utterance_seconds`（包含句內停頓）；此時不再加標點停頓，也不再套 `rate_multiplier`。尚無實測時，共用離線 planner 以漢字及拉丁文字詞估計。起始 policy 是漢字每秒5字、拉丁文字每秒2.8詞，逗號0.12秒、句末0.25秒、省略號0.35秒、換人0.2秒、開場0.25秒及收尾0.35秒。這些是可調整的工作假設，並非各語言、演員或模型的固定自然語速；依題材、試讀和使用者回饋調整 `policy` 或逐句 `rate_multiplier`。

數字、縮寫與混語需先按真正念法寫出，或提供實測。其他文字系統目前須提供實測與正確 `language`。逐句 `delivery` 保留語氣；避免同時寫互相衝突的慢速要求或另一套發聲時間窗。

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

`utterances` 按發聲順序排列，全文不含 `<d>` 標記。`voice_mode` 支援 `spoken`、`inner`、`offscreen`、`telephone`、`narration`，仍須核對實際聲音／嘴型。`not_before_seconds` 是片內最早起點，可表示先完成動作才說話；`pause_after_seconds` 是該句之後的刻意安靜時間，另計換人停頓。`action_end_seconds` 是與對話可並行的動作完成時點，不把全部動作秒數再加到對話上；`reaction_seconds` 接在最後一句及其停頓之後。片長取兩條時間線的較晚末點再加收尾。

## 正常生成入口

新 H3／Pika 原生聲畫製作在凍結 job、配置 GPU 或提交前，必須執行以下對應入口並核對產出的 timing report 與真正送入模型的 prompt。舊無 timing 的 caller 保持相容，但新對白 job 不沿用手填的寬鬆語音窗口。

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

## 實際輸出回饋

估算與 prompt 只改善規劃意圖，模型原生發聲仍可能快慢漂移、超窗或忽略停頓。第一次可用試片就聆聽語速及語氣，核對完整台詞與首尾，再以 ASR 字詞時點輔助調整下一批的 policy／delivery。ASR 的首字到末字時間包含中間停頓，字詞時長總和也不等於聲學發聲時長；不能只用字數除以整段秒數宣稱聽感自然。缺少實際聆聽或新生成驗證時，明記未驗證；不要以全片加速代替此規劃修正。

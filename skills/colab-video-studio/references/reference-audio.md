# 共用引用與音訊：按需使用的本機編譯

適用跨鏡重用角色／場景／關鍵道具，或已有配音音軌的短劇。只有一張指定圖、無台詞、或直接用原生 H3 聲音時，不必建立新目錄或音訊產物；原有 asset IDs、`audio="native"` 和 timing-only 路徑仍可用。

這一層只做確定的引用解析、既有 WAV 的量測與時間座標轉換。**不會生成／複製聲線、做 ASR／forced alignment、分配 GPU、呼叫付費 API，或自動增加圖片。** 不增加資料庫、另一套排程或混音引擎。錄音、TTS、混音仍用當次已選工具；完成音軌後才匯入。

## 引用直接編譯到既有 inputs

延伸 `plan.json` 的現有 `characters`；有用到才增加 `scenes`、`props`、`voices`。`references` 的葉節點仍是原有 `assets` ID，不另存一份圖片。

```json
{
  "characters": [{
    "id": "mei", "name": "梅", "aliases": ["Mei"],
    "identity_assets": ["mei-original"], "voice_id": "mei-voice",
    "references": {"coat": {"front": "mei-original", "side": "mei-side"}}
  }],
  "scenes": [{"id": "room", "name": "教室", "references": {"night": {"wide": "room-night"}}}],
  "props": [{"id": "key", "references": {"closed": {"front": "key-image"}}}],
  "voices": [{"id": "mei-voice", "description": "A low, clear adult voice"}]
}
```

實際 shot 可用結構化引用或有界 token：

```json
{
  "inputs": {
    "references": [
      {"kind": "scene", "ref": "room", "variant": "night", "view": "wide"},
      "@{character:梅/coat/side}",
      "@{prop:key/closed/front}"
    ]
  },
  "prompt": "... @{character:mei/coat/side} holds @{prop:key/closed/front} in @{scene:room/night/wide} ..."
}
```

這是欄位片段，不是完整 H3 prompt；仍需其正式欄位／task tag。`prepare` 將上述 input 編譯為 `room-night, mei-side, key-image`，H3 prompt 對應 `<Picture 2>`, `<Picture 3>`, `<Picture 1>`。`first_frame`／`last_frame` 也可用同樣的引用，picture 次序固定依 adapter 的先首幀後末幀，不依 JSON key 次序。

- Canonical ID 優先；`@名稱`（例如 `speaker_ref="@梅"`）強制按名稱／別名查找。匹配採 Unicode NFC、區分大小寫，不做模糊搜尋。同名／別名衝突必須改用明確 ID。
- variant 和 view 都必填，不選第一張、不退回其他角度。缺檔、未 ready、身份 lineage 不符仍由既有檢查拒絕。
- prompt token 必須對應**恰好一個已實際提供的 input**；不能只在 prose 寫 token 就補圖。其他 backend 可以使用結構化 inputs，但不接受 H3 picture token。
- 明確引用的 character 自動加入該 shot 的 `characters`，所以原有身份基準與 identity／wardrobe criteria 仍須具備。
- 一般 prose 的 `@梅` 不會猜測替換。圖片 token 使用 `@{kind:ref/variant/view}`；名稱含 `/`、`:` 等分隔字時使用 canonical ID。

原生 H3 的逐句 `speaker_ref` 可取代手寫 `speaker`：

```json
{"speaker_ref": "mei", "text": "等等。", "voice_mode": "spoken", "delivery": "Short, urgent, without shouting."}
```

compiler 沿用 character 的 `voice_id`，將聲線 description 與當句 delivery 寫入實際 prompt。**這只是聲線意圖，不是 speaker embedding、聲線複製或穩定聲線的實測證明。** 仍需聆聽生成結果；不因此宣稱 backend 支援音訊 conditioning。

## 匯入已存在的實際音軌

先用既有錄音／配音／混音工具產生本機 PCM WAV，放在 project 內。第一次支援無壓縮整數 PCM WAV；其他格式仍可走既有 `audio_track`，或明確用 FFmpeg 轉成 WAV 後匯入，不會偷偷轉檔／下載模型。

在 `assets` 為它設定正常 audio asset，並指向準備建立的 manifest：

```json
"dialogue": {
  "path": "audio/scene.wav", "role": "audio", "source": "recorded",
  "status": "ready", "audio_artifact": "audio/scene.json"
}
```

匯入 spec 的秒數全部在**原 WAV 的零起點時鐘**，不是剪後或逐句歸零時間：

```json
{
  "asset_id": "dialogue",
  "utterances": [{
    "id": "u1", "character_id": "mei", "voice_id": "mei-voice",
    "text": "等等。", "start_seconds": 0.3, "end_seconds": 1.1
  }],
  "alignment": {
    "method": "manual", "provenance": "Boundaries annotated against the original recording",
    "sentences": [{"utterance_id": "u1", "text": "等等。", "start_seconds": 0.3, "end_seconds": 1.1}],
    "words": []
  }
}
```

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" audio-import --project "$PROJECT_DIR" \
  --file "$PROJECT_DIR/audio/import.json" --output audio/scene.json
```

只量測實際 PCM frame count、sample rate、duration、檔案 hash；不從文字猜測秒數。utterance span 是所提供的邊界，不冒稱自動辨識。沒有可信的 word／sentence timing 時省略 `alignment`；會標記 unavailable，不能據此假造逐字字幕。`manual`、`provider`、`forced`、`asr` 代表匯入資料的來源，不代表本工具執行了那些工作；來源聲稱仍須核對。

shot 沿用既有單一 `audio_track` 與 `dialogue_timing`：

```json
{
  "audio": "separate", "inputs": {"audio_track": "dialogue"},
  "duration_seconds": "auto",
  "dialogue_timing": {"utterances": [{"id": "u1", "speaker_ref": "mei", "text": "等等。"}]}
}
```

`prepare` 核對目前 text／speaker／voice 與 manifest、WAV hash／量測值，再把 supplied span 交給既有 dialogue compiler。不需手抄 measured duration 或 start time。完整 WAV 必須放得下；不壓縮台詞或截尾來符合片長。預設不再替完整錄音增加估時器的 lead／tail；明示 reaction、tail 或 clip duration 仍會採用。明確提供的重疊時間保留，包括同一角色的口說與心聲／回憶聲層，不另加限制旗標。

這個**既有錄音**分支不接受逐句 `voice_mode`、`delivery`、`rate_multiplier`，避免欄位看似生效、其實沒有改變錄音或畫面。可見的嘴型、表情、情緒與聽者反應寫進 `shot.prompt`；要改錄音表演／語速就先另製音軌再匯入。原生 H3 的上述逐句欄位仍照原本的 prompt compiler 生效。`audio_timeline` 是 compiler-owned output，不能直接放進 source plan 來繞過 artifact 驗證。

**此 Studio 的 separate audio 是生成後 mux，不是 lip-sync 或聲線 conditioning。** 原影片的聲軌會被替換；需保留的環境音／音效應先包含在所匯入的完整混音中。可見說話者的嘴型、語氣、情緒與聲音身份仍需成片聆聽／觀看驗證。

## 同一時間軸供字幕與剪輯使用

```bash
python3 "$VIDEO_SKILL/scripts/studio.py" prepare --project "$PROJECT_DIR"
python3 "$VIDEO_SKILL/scripts/studio.py" audio-srt --project "$PROJECT_DIR" \
  --shot s01 --output subtitles/s01.srt
# 已完成既有 edit-prepare 時，使用同一 edit recipe 的裁切／變速時鐘：
python3 "$VIDEO_SKILL/scripts/studio.py" audio-srt --project "$PROJECT_DIR" \
  --shot s01 --run edit-v1 --output subtitles/s01-edit-v1.srt
```

SRT 只使用 supplied sentence timings；沒有時直接報缺資料，不把字數平均切成假 alignment。可交給既有 [FFmpeg caption](../../ffmpeg-skill/SKILL.md) 燒入或 mux。輸出不得覆寫，修改時另存 revision。

若要保留短句原有邊界，使用 `caption.py video.mp4 --srt subtitles.srt --mode mux --min-duration 0 --output captioned.mp4`；caption 預設 `--min-duration 1.0` 會延長短 cue。長句換行／拆 cue 仍依 caption 的版面設定，處理後核對實際字幕時鐘，不把原 SRT 當最終結果的證明。

`edit-prepare` 會將同一 `audio_timeline` 隨 trim／speed 映射到 edited clock，保留來源 WAV hash／utterance ID。之後只修正 sentence／word alignment 時，`audio-srt --run` 會通過原本的 source／media／recipe 與 frozen job hash 檢查，再以同一剪輯配方在記憶體映射最新邊界；不改舊 job／receipt／影片，也不為字幕重跑 encode。可剪除完整 utterance，但切到 utterance 中間會拒絕，避免半句音訊配完整字幕；需要這種改編時先明確重編音軌及台詞、另匯入。變速後的映射是座標換算，不是重新對齊或聽感驗收。

更動 WAV bytes、text、speaker 或 character 的 voice binding 會拒絕舊產物，需對帳後重新匯入。單改未使用的資產、別名、view 或字幕 alignment 不會使原始生成影片失效；編譯後的實際 prompt、duration、選用圖片與 WAV bytes 仍決定 generation identity。PR1 的舊 digest 依原版本核對，再比較同一 generation-input projection，不改寫舊 receipt。

測試／限制與成本量測見 [PR2 驗證記錄](../../../research/reference-audio-artifacts-20261101.md)。離線合約能證明引用／hash／時鐘接線，不能證明生成畫質、真實聲線一致性或實際少重抽幾次。

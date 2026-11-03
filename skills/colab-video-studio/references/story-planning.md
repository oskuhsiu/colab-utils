# 內容與分鏡

用於寫稿、重編內容或安排多鏡作品。先讓內容本身可審，再把鏡頭轉成模型工作。

## 依作品目的選結構

確認觀眾、看完要理解／感受／採取什麼，以及必留的事件、資訊、台詞與素材。已有稿件時，先辨認哪些可調；改編保持使用者要求的意思、角色和風格。

- 敘事作品：角色的目的、選擇、結果與反應形成可追蹤的進展；衝突、反轉或情緒回收按題材需要使用。
- 廣告／展示：主張、可見證據與行動呼籲互相支持，鏡頭服務於要展示的特點。
- 教學／說明：必要前置資訊、操作與可辨認的結果順序清楚，留足觀眾跟上步驟的時間。
- 氛圍／音樂作品：以視覺、聲音和節奏組織體驗，可不採角色衝突或敘事反轉。

非敘事的短或單鏡需求可直接落成鏡頭。敘事先按 [先定劇情，再定鏡頭](../../video-production/references/drama-preproduction.md#先定劇情再定鏡頭) 寫可連續演出的場景，再按視角與資訊需要拆鏡；簡短單幕可直接用幾句連續動作，不新增文件。複雜作品的節拍表輔助整理，不代替發現、選擇與反應的過程。未指定總時長時先由內容估長，不自訂分鐘數或鏡數填滿；使用者指定的時長仍須遵守。重複內容若沒有敘事、說明或節奏用途，考慮刪除或合併。

文字改編先把環境與動作描寫轉成可見的空間、道具、光線、行為及聲音；角色內心可由表演或必要心聲承載，旁白依所選敘述觀點提供資訊，避免按原文字數填滿片長。

含角色表演、對白或內心話的敘事片，生成前必讀 [情緒與表演](../../video-production/references/emotion-and-performance.md)：先讓事件改變角色的行為與逐句表演，需要比較強弱時再用 E0–E4、felt／shown 與壓抑理由協助交接；不逐鏡強填分級表。建立口說／心聲／無聲說話等模式的聲音和嘴型關係，再編譯最終提示。避免把日常、蓄勢與高潮都寫成同一套微表情。

小說／短劇改編或跨集製作時，可用相鄰 skill 的 [短劇前製與交接模板](../../video-production/references/drama-preproduction.md) 整理劇本、共用角色／場景／關鍵道具及逐鏡聲畫。轉成 Studio job 時，再依 [執行契約](workflow.md) 填入實際 asset IDs、`inputs` 與 `start_state`／`end_state`；前製表本身不是可提交的 `plan.json`。

小說改編、續集、混用計畫與現有參考素材，或多人反應有交接時，讀 [改編與鏡頭決策](../../video-production/references/adaptation-shot-and-edit.md) 的相關段落，將資訊揭露邊界、實際前集末態、已核對的素材用途及注意交接帶入既有計畫。

## 把內容交接變成鏡頭

每鏡指定用途、可見動作／資訊、景別、聲音與下一鏡承接點。含動作、對話或操作過程時，依 [段內時間線與具體表演](../../video-production/references/intrashot-staging.md) 細化同一片段內的各階段，交代互動對象、注意力、動作過程與留下的狀態。連續／同框要求按使用者指定保留。

剪入長度依內容決定，與模型支援的生成長度、動作自身速度分開安排；短促事件不攤滿模型片長，前後反應也不為填空白而拖長。編譯時核對每鏡的秒數和完整動態提示，確認片內時間線、對話對象／視線與台詞輪替沒有遺漏，秒數沒有被批次預設覆寫。素材可較長，再選完整有效區間；配音和字幕與實際畫面對齊。

局部動作需要明確時間窗時，可在既有 `dialogue_timing` 放 [action_beats](../../video-production/references/dialogue-pacing.md#局部動作窗)，無台詞也適用。compiler 將具體動作和快慢窗口寫入最終 prompt，不拿台詞或整段片長縮放；只有 `action_end_seconds` 仍只是總預算，不會產生動作內容。已有完整提示可直接沿用，不要求每鏡加表。將重要事件的速度、觸發後才反應及支撐／接觸結果寫進既有 action criterion；沿用事件窗取證，正常播放檢查速度，不另加一層評審。

喜劇才檢查鋪陳、期待、揭露與反應；懸疑、產品展示或教學按其目的審查。複雜互動需辨認哪些結果必須看見，避免只安排起態和末態卻沒有因果。

## 將情緒強度交給生成與驗收

把強度標註轉成符合當鏡時序的表情、動作、呼吸與逐句語氣；級別本身不是控制參數。新語音 job 依 [對白估時與語速](../../video-production/references/dialogue-pacing.md) 編譯：視覺／動作放進 base prompt，逐句表演放 `dialogue_timing.utterances[].delivery`，台詞只放 `text`，再核對 `dialogue_timing_result` 與 job 最終 `shot.prompt`。若前製工具使用 `visual_prompt_en`／`delivery`，也追到真正合成後的內容；不要在 base 預放 `<d>` 或重複對白時窗。

Studio 會保留 shot 內的附加標註並交給 reviewer，但 backend 不會自動解讀情緒級別；只放在 plan 頂層的全片情緒表也不會自動進入各 job。felt／shown 留在 shot 標註或 criteria，不加到只接受既定欄位的 timing 物件／utterance。強度不自動改 `rate_multiplier` 或片長；語氣改動若影響發聲時間，按試讀／估計更新預算。情緒轉折可以在同一完整互動內發生，沿用連續鏡頭規劃。

為重要表演在既有 `criteria` 補上強度目標、事件區間與可觀察錨點，讓「有一點情緒」不會直接等於達標。視覺與必須聽驗的表演分開列；下列是恐懼 shown E3 的局部示例，合併到當鏡 criteria，保留原有必要判準並依實際發聲模式改寫：

```json
[
  {
    "id": "performance-visual",
    "kind": "performance",
    "requirement": "After recognizing the threat at the doorway, the character's ongoing action abruptly stops, the hand tightens around the phone and the body recoils. These cues sustain the planned strong fear (shown E3) through the end instead of a passing worried glance. Judge visible acting, not an inferred inner state."
  },
  {
    "id": "performance-delivery",
    "kind": "audio",
    "requirement": "During the spoken warning, the first phrase catches, a brief pause separates the phrases, and the remaining words rush out in a frightened whisper. Quiet volume must retain urgency; verify by listening, or mark unknown."
  }
]
```

在既有 `qa.event_windows` 為重要反應安排涵蓋觸發前後的取樣；現有 action 等必要事件窗仍需保留。單張臉部畫面或字幕不能證明完整強度變化。完全無聲的鏡頭只加適用的視覺判準，不為套用示例新增台詞或聲軌。

## 規劃完成條件

對照要求，確認每項重要內容有畫面／聲音承載，相鄰鏡頭的資訊與狀態能接上，且選定模型或控制素材能接收所需條件。指出有待試片的能力，不將文字描述當成已實現。

抽查實際序列化提示中的段內動作、互動對象／視線、情緒強度與轉折、逐句 `delivery`、發聲方式、嘴型與聲音處理，確認上游標註沒有在編譯時遺漏或被共用設定覆蓋。對照預定級別所需的可讀證據，移除不合劇情的固定克制／平穩語氣；有來源依據的壓抑仍保留。這些標註須轉成 backend 支援的提示／後製設定，不預設現有 adapter 自動接收新欄位。

在既有審稿中連讀當場與相鄰段落，不只逐鏡查欄位：動機／發現是否可追，快事件與後續反應是否分開估時，情緒是否改變行動，切點有無讓過程重新起步。節奏有風險時，以紙上剪接檢查預計節奏，或以已有素材、經授權的簡單 animatic 檢視實際長度；敘事或理解有爭議時可做獨立審稿。按任務複雜度選擇驗證，規劃通過不等於藝術品質或生成結果通過。

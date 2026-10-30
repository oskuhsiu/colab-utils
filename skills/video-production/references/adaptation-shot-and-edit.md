# 改編、鏡頭與剪輯決策

小說改編、跨集續作、參考素材整理、多人互動或生成素材選段時，使用相關段落補足現有前製與剪輯紀錄。沿用作品已選的畫風、節奏與表演尺度；單鏡修正只補會影響結果的資訊。這些是製作方法，不能據此推定成片已符合使用者喜好。

## 原著資訊與跨集交接

把重要原著內容對應到場次或鏡頭，分清必留事實、可改的呈現方式，以及目前還不能揭露的資訊。記錄來源位置與改編理由，讓刪併、換視角或改用聲音之後仍能查到原意。懸疑作品另分「角色已知」和「觀眾已知」；角色不能因提示詞寫了真相就提前表現得知情，心聲也不能無意間替觀眾解開尚未揭露的謎。

跨集續作先讀當章及必要的前集交接，整理實際末態：時間／地點、角色已知資訊、關係、持物、服裝／傷勢、未解事件與仍持續的後果。區分原著設定、前集原本打算呈現的內容與前集實際成片已讓觀眾知道的內容；前集未拍出的關鍵資訊，不能直接當成觀眾已知。必要補述或修正安排在本集可理解的位置，保留使用者允許的改編範圍。

可在既有節拍表增加以下欄位，無須另建固定文件套件：

```text
來源位置／必留事實／可替換的表現方式／暫不揭露的資訊
承載場次或鏡頭／角色此刻知道什麼／觀眾此刻知道什麼
跨集繼承狀態／本集改變與依據／刪併或補述理由
```

## 參考素材的狀態與控制範圍

區分「計畫製作」、「檔案存在但內容尚未核對」與「已實際查看且適用」的素材。圖片提示稿或待補槽位可以支援文字規劃；實際生成輸入須解析到可讀檔案及已確認內容。找不到必要參考時，先查現有素材，再依原有授權補圖或調整可行方案，更新真正的輸入；維持使用者指定的工具與製作方式。

每張實際參考記用途、輸入順序、應保持的事實，以及哪些部分由本鏡重新決定。例如角色圖負責臉與服裝，姿勢、背景和本句情緒由分鏡決定；場景圖負責出入口及地理，機位與人物走位由本鏡決定。聲音參考負責聲線身份，本句的語氣、情緒、台詞與心聲聽感依 [情緒與表演](emotion-and-performance.md) 編排。

跨鏡容易漂移的特徵，可整理成短而明確、能反覆引用的外觀或狀態描述，綁到資產 ID 和適用鏡頭，例如外觀「深藍色短外套」、當鏡狀態「鑰匙仍在右手」。穩定身份與暫時狀態分開；換裝、受傷或物件轉手後只更新受影響的狀態。核對最終提示和實際輸入是否保留這些事實，勿只在資產表寫「保持一致」。描述沿用不等於模型已實現一致性，仍按實際畫面驗收。

沿用專案現有資產 ID 與 backend schema，將上述用途和狀態轉成模型真正支援的參考綁定與提示；上游素材代碼或「不得控制」說明不會自動變成模型參數。

## 多人反應與鏡頭注意中心

先選觀眾此刻需要注意的角色、物件、聲源或空間，再安排觸發如何被接收、誰先反應、其他人何時理解。多人同框時，各人的反應來自其位置、目標與已知資訊；例如近門者先聽見把手聲而停手，另一人看到他停住才轉頭。只描述真正參與變化的人，讓保有原狀或刻意掩飾也能成立。

只有注意中心真的改變時，記「目前焦點 -> 可見／可聽觸發 -> 新焦點」。景別須讀得到所選反應，遠景可用停手、重心或距離變化，近景才依賴細小眼神。運鏡或切鏡說清在何事發生時開始、讓觀眾看見什麼、停在哪裡；固定鏡頭也可用等待和畫外聲形成壓力。

涉及接觸、持物或走位時，核對起點、路徑、釋放／接住與末態，尤其同一隻手是否同時被安排兩項互斥工作。必要動作、逐句語音與反應共用同一時間預算；放不下時調整分鏡並同步最終提示。依當次能力決定拆鏡或控制方式，保留故事必須看見的因果。

## 先記素材事實，再決定剪哪裡

先逐段檢視實際素材，記錄可用的畫面／聲音區間、動作和台詞落點，以及缺陷出現時間。將觀察與取捨分開：例如「6.2 秒起右手道具變形」是觀察；「在 5.8 秒反應完成後切走」是剪輯決定。可用畫面和可用聲音可能是不同區間，保留來源與時間對應。

在既有選材或剪輯單補足：

```text
素材／版本／實際檢視範圍：
可用畫面區間與聲音區間／缺陷時間與現象：
選定入點及理由／出點及理由／承載的資訊、動作或情緒：
相鄰接點與聲音安排／未採用內容及其去向：
```

按資訊與表演選入出點：保留辨認、猶豫、恐懼等待與語句首尾需要的時間；移除沒有敘事作用的重複表演或生成漂移。刪掉的必要資訊要有其他素材承接，否則列為缺口並修正。生成長度、可用區間與剪入長度分開記，交付時長依使用者限制處理。

台詞引發反應時，可比較在話語中途切到聽者、聲音持續的 L-cut，或先聽到下一鏡聲音再換畫面的 J-cut；也可讓話語先落地、停頓後再切。按場面需要選擇，保留音軌連續、說話人、可聽範圍及該句發聲模式。實際剪輯工具是否會連同原聲裁切要另核對；字幕隨完整語句定位。處理後依 [驗收與放行](../../colab-video-studio/references/video-review.md) 重查受影響的聲畫與接點。

## 審查方法與創作選擇

把事實／介面錯誤、會損害觀眾理解的問題，以及單純的風格建議分清。指出重複、過度解釋或節奏單一時，引用具體位置並說明損失：例如畫面已揭示角色選擇，後續台詞又把同一意思解釋一次；或連續反應鏡都以相同推近取代各人的不同立場。反覆構圖、沉默與緩慢節奏也可能是有意的懸疑、儀式或人物表現，按其作用判斷。

沿用使用者已接受的作品基準。表演強弱、停頓、鏡頭數與配樂密度隨本場目的決定；每鏡不必增加情緒強度，也不為了填滿模板替所有人物加上微動作。檢查過的文字與引用只能支持設計交接，實際情緒、嘴型和聽感仍需要成片證據。

## 來源、修改與授權

2026-10-30 選擇性整理改寫自 [zenstory-ai/drama-skills](https://github.com/zenstory-ai/drama-skills)，固定版本 `7e6336047ddb3c6344b3c3966a81ad8008d23c11`。主要依據為其改編、資產、分鏡，以及以下資料；詳細取用對照見 [研究紀錄](../../../research/drama-skills-evaluation-20261030.md)。

- [表演、動作與注意交接](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-video-prompts/references/performance-action-timing.md)。
- [素材可用區間](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-edit/references/generated-footage.md)、[剪輯入出點](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-edit/references/cut-craft.md)。
- [去模板感與誤報](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-review/references/anti-template-repair.md)。

修改：合併為按需參考、採繁體中文與本地製作契約；補入前集實際成片資訊與既有心聲規則的交接；不引入整套技能、固定文件格式、供應商執行器、短劇風格或數字節奏配方。本頁改寫內容沿用 MIT；其他既有文件依各自授權。

```text
MIT License

Copyright (c) 2026 drama-skills contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

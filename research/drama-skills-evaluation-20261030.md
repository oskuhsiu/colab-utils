# Drama Skills 選擇性取用評估

查核日期：2026-10-30。上游：[zenstory-ai/drama-skills](https://github.com/zenstory-ai/drama-skills)，固定提交 [`7e6336047ddb3c6344b3c3966a81ad8008d23c11`](https://github.com/zenstory-ai/drama-skills/tree/7e6336047ddb3c6344b3c3966a81ad8008d23c11)。以下結論針對此版本。

本次分支：`experiment/drama-skills-ch2`；起點為 `master` 的 `2897c92`。依使用者要求，選擇性改寫留在試用分支，供審閱及第二章製作；是否併入由使用者後續決定。本次未合併。

## 採用的部分與實際變更

我的判斷：值得借用的是讓創作意圖能追到實際輸入、畫面與剪輯的交接方法。它們有助於定位遺漏或錯接；是否符合使用者偏好的藝術效果，仍須由實際作品確認。

改寫集中在 [改編、鏡頭與剪輯決策](../skills/video-production/references/adaptation-shot-and-edit.md)，由現有 `video-production`、Studio 內容規劃和驗收文件按需引導閱讀。

| 取用主題 | 上游可核對的機制 | 本地整合與取捨 |
| --- | --- | --- |
| 原著資訊與跨集交接 | 來源事實須有呈現落點；世界事實、角色認知、觀眾知情分開；集間繼承具體狀態。[S1]、[S2] | 補來源到鏡頭／聲音的對應與暫不揭露資訊。本地另補「前集實際成片已呈現什麼」，避免把前集未拍出的設定當作觀眾已知。 |
| 參考素材狀態與控制範圍 | 提示稿、計畫掛圖與真實檔案分開；實際參考記順序、用途及控制邊界；跨鏡特徵帶進最終提示。[S3]、[S4] | 採計畫／存在未核對／已查看適用三種描述，沿用現有 asset IDs。穩定外觀與暫時狀態分開；不引入上游固定代碼、逐字字串檢查器或新 backend 欄位。 |
| 多人反應與觀看焦點 | 反應來自目標、資訊與位置；注意中心由可見／可聽觸發交接，並須被當前景別讀到。[S5] | 補誰先察覺、誰從他人的反應才理解，以及運鏡的觸發與落點。保留原有情緒與表演規則，不新增數值情緒標尺或固定反應秒數。 |
| 素材可用區間與剪輯理由 | 先觀察素材，再決定取捨；入出點按資訊與表演選，聲音可跨切點。[S6]、[S7] | 在原有剪輯單補缺陷時間、畫面／聲音可用區間、入出點理由及刪去資訊的承接。J/L-cut 為依場面選用的方法，沒有固定秒數。 |
| 區分缺陷與風格選擇 | 重複或過度解釋需指出位置與具體損失；有意重複、固定鏡與人物口癖可成立。[S8] | 驗收意見分清事實／介面錯誤、理解問題及風格建議。保留慢節奏、沉默與持續情緒的空間。 |

## 保留既有設計

角色目標、情緒觸發與外顯反應、逐句 `delivery`、聲線身份與當場語氣分離、最終序列化提示核對，已在我們的 skills 中，本次沒有另搬一套。心聲保持較空洞的聽感且沒有該句發音嘴型；「無聲的說話」保持嘴型加同一句心聲。上游的 VO／OS 名稱不取代這些定義。

現有原著前製模板另有自己的來源及授權；此次 MIT 改寫放在獨立參考頁，原文件保持原有授權範圍。

## 未採用的部分

- **整套十一個 skills、固定文件骨架與專用狀態管理。** 上游以多份 Markdown 及專有欄位交接。[S9] 我們已有劇本、資產、job、ledger 與剪輯介面，這次只補缺少的資訊。
- **短劇節奏數值起點。** 上游提出首鉤 5 秒、真人平均鏡長 2.5 秒、近景類比例至少 0.45 等候選值，也明確說明須經創作者接受才核對。[S10] 本次沒有將這些候選值、豎屏取景或峰值收尾變成我們的預設。
- **特定模型的表演配方。** 上游 H3 小樣本建議兩處可見反應、觸發後約 1.5 秒落下，同頁也限制其外推範圍。[S5] 本次只採角色、觸發、可讀反應的原則，沒有移植數字、評分或跨模型效果主張；H3 官方提示契約保持原樣。
- **供應商執行器、Dashboard、Remotion 與逐次生產確認流程。** 上游每個 job 要獨立 prepare／confirm／run，重試亦再確認。[S11] 本次沒有安裝或執行其工具；續用我們既有的授權、預算、生成與驗收方式。
- **範例作品的畫風、配樂、字幕樣式與表演尺度。** 沒有用它的成片作為本地品質標準。

## 授權與證據限制

上游根目錄採 [MIT License][S12]。本次改寫頁保留完整著作權、許可與免責文字，並列來源及修改範圍；沒有改變 repo 其他文件的授權。

查閱證據涵蓋 develop／novel-analyze／write／assets／storyboard 的相關指引，以及 video-prompts、edit、review、produce 的相關章節與授權。這是文字與介面交接評估，未執行上游腳本、安裝全套 skills、生成媒體或試製第二章；沒有藉此證明藝術品質、嘴型控制或實際情緒效果。

## 本地驗證

兩個受影響的 skill 通過 `quick_validate.py`，17 個本地連結及章節錨點可解析，MIT 授權文字與上游逐字一致，提交差異無空白錯誤。另由未參與改寫的代理完成一個虛構懸疑續集的離線文字試用，主代理核對其實際草稿：沒有提前揭露禁令知情或門內身分，未把缺少的圖檔當成現有輸入，保留心聲與嘴型的區分，剪輯候選保留完整話語及反應並拒用狀態不符的收手鏡。這只支持該案例的文字規劃與交接；測試產物位於 Git 忽略的 `tests/drama-skills-branch-trial-20261030/`，沒有生成或觀看實際影片。

## 固定版本來源

- [S1：原著事實的呈現落點](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-develop/references/adaptation-craft.md#L254-L277)。
- [S2：世界／角色／觀眾資訊與跨集記憶](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-develop/references/serial-character-and-memory.md#L159-L235)。
- [S3：參考素材的證據與控制用途](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-storyboard/SKILL.md#L115-L154)。
- [S4：跨鏡外觀鎖與狀態的區分](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-assets/references/continuity-lock.md#L13-L55)。
- [S5：表演過程、模型小樣本配方與注意交接](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-video-prompts/references/performance-action-timing.md#L89-L140)。
- [S6：生成素材可用區間](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-edit/references/generated-footage.md#L3-L25)。
- [S7：入出點、聲音跨切與時長取捨](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-edit/references/cut-craft.md#L3-L61)。
- [S8：去模板感的證據、診斷與誤報](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-review/references/anti-template-repair.md#L13-L87)。
- [S9：上游的工作文件與十一個技能](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/README.md)。
- [S10：可由創作者改寫的節奏候選值](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-develop/references/episode-design.md#L502-L552)。
- [S11：上游生產確認流程](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-produce/SKILL.md#L47-L61)。
- [S12：MIT 授權](https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/LICENSE)。

[S1]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-develop/references/adaptation-craft.md#L254-L277
[S2]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-develop/references/serial-character-and-memory.md#L159-L235
[S3]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-storyboard/SKILL.md#L115-L154
[S4]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-assets/references/continuity-lock.md#L13-L55
[S5]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-video-prompts/references/performance-action-timing.md#L89-L140
[S6]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-edit/references/generated-footage.md#L3-L25
[S7]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-edit/references/cut-craft.md#L3-L61
[S8]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-review/references/anti-template-repair.md#L13-L87
[S9]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/README.md
[S10]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-develop/references/episode-design.md#L502-L552
[S11]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/skills/short-drama-produce/SKILL.md#L47-L61
[S12]: https://github.com/zenstory-ai/drama-skills/blob/7e6336047ddb3c6344b3c3966a81ad8008d23c11/LICENSE

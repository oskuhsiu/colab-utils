# 本地模型與控制介面

本表描述 repo 的 `scripts/backends.py`／`workflow.py`（位於本 skill）的實作，外部模型的全部能力不等於此 adapter 已接入。版本、格點、steps／dtype 和可用 kwargs 以實際 backend／準備檢查為準。

| Backend | 此 adapter 的輸入 | 原生時鐘／主要界線 |
| --- | --- | --- |
| h3 / fl2va | 可用 first_frame／last_frame | 24fps、17n+5模型frames；與 refs互斥 |
| h3 / ref2va | 有序圖片 references | 同H3時鐘；不接video/audio refs，不提供硬端點 |
| wan22-ti2v | 無圖T2V或first_frame I2V | 24fps、4n+1；此路徑不接last_frame |
| wan22-i2v-a14b | first_frame、checkpoint的雙denoiser | 16fps、4n+1；不接尾圖／自訂LoRA／camera path |
| wan21-vace | control_video、可選mask_video和references | 16fps、4n+1；本地1.3B路徑，品質另驗 |
| wan22-animate | first_frame、pose_video、face_video；replace加background／mask | 30fps、分段driver；不接通用自訂LoRA |

上表之外，舊 FastH3 的原生 T2VA／實驗圖片參照走 repo 根目錄 `scripts/fast_h3_colab.py`；原生 H3／Continuum／FastH3 Omni 走 [ComfyUI workspace](../../../doc/COMFYUI_WORKSPACE.md)。模式、模型與參數由 [H3 skill](../../minimax-h3-colab/SKILL.md) 及所選路徑管理，不能把某個 student 或 Studio adapter 的輸入契約套給其他路徑。

## 條件與前處理

依需求選真正接收該條件的接口。圖片、端點、pose／layout、face driver、reference video與音軌用途分開；檔案改名或 prompt 宣稱不會接上新分支。人體 pose 不控制全部手指／物件物理，必要細節另有可見控制或鏡頭設計。

影響劇情的物件數量、開閉或位置若不穩定，先明確描述所需可見狀態，再考慮模型支援的場景／道具參考、關鍵幀或 layout，並保留人物素材的身份用途。改過條件後驗實際內容；同時換圖與改 prompt 的成功只能支持該組合，不能歸因於單一技巧。

本地 `make_control.py` 支援人工18-joint normalized座標的keyframes插值，格式看工具help；這是人工軌跡，不是動作捕捉。解剖與速度按來源／設計驗收。

VACE mask 在此 adapter 使用黑=條件、白=生成；重取樣按native時鐘，mask用nearest，短輸入可能保持末格。保存縮放／時間映射，確認需要的控制涵蓋完整區間；不能把補格當動作完成。角色替換另讀 [character-replacement.md](character-replacement.md)。

## 設定與支援範圍

H3的prompt／speedLoRA／shift／loader比例讀相鄰H3skill。Wan的模型dtype、VAE與offload取自這個backend實作；硬體實查容量與支援精度，不從文件的另一套offloadrecipe推定本地必可運行。

保持 documented／implemented／tested條件與當次內容驗收的區別。新模型或輸入組合若未接入先描述缺口；已允範圍內可作隔離短測，明確版本與結果後再採用，不暗中更換使用者指定的模型／控制。

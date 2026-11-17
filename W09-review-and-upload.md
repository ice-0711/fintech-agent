# W09-E｜GitHub 手動上傳清單（2026-11-16）

## 上傳前
1. 在 Canva W09（DAHbFMHx9GA）確認第 18、20、23、28 頁正文與備註；第 28 頁備註需包含 D 評分與 B 核對文件來源。
2. 將 Canva **整份 28 頁**匯出為 PowerPoint（.pptx），重新命名 `deck-v8.pptx`。確認講者備註有包含在匯出檔案中，若 Canva 匯出未包含，另保存講稿文件並在 PR 註明。
3. 用 PowerPoint 開啟確認字型、圖片、頁數及頁面順序。28 頁與工作包原先 16 主頁＋4 備用頁的配置不同，須在 PR 提醒組長確認。

## W09-E 交付路徑
- `slides/deck-v8.pptx`：從最新版 Canva 匯出；**目前尚未提供本檔**。
- `figures/final-figure-register.md`：八張圖表登錄表，含來源、責任與正式結果限制。
- `slides/v12-evaluation-template.pptx`：6 頁實驗設計／開發證據補充模板，**不是**整份 Canva 簡報。

## GitHub 操作
1. 到 `kk1030-bit/fintech-agent`，從 main 建立 `E-W09-presentation-review` 分支（若已存在則使用現有分支）。
2. 依上述相對路徑上傳三份檔案；如路徑已存在，先比對差異，勿直接覆蓋組員的新版。
3. Commit 建議：`docs(E): prepare W09 evaluation slides and figure register`
4. 開 PR 至 main，貼上 PR 說明；等待 C／組長核准，不自行合併。

## 審閱界線
- D dual v2 開發集 10 案，D 判定 8 符合預期、2 不符合；B 核對 10 筆停止原因與執行次數一致。這**不是**正式 60-run 成效。
- 20 保留案 × 3 模式＝60 次為正式研究設計與排程，不代表已執行完成。
- 正式品質／成本／NA 圖仍須等待 D 的正式輸出、B 評分及組長核准；不能造數。
- 9 份前瞻觀察不併入 60 次正式研究。
- `evaluation/d-drafts/rubric-v1-final.md` 文件自身仍有待簽欄位，引用時標明版本狀態。

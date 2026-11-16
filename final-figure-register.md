# W09-E｜八張圖表來源登錄表（開發證據已補，正式結果不造數）

狀態：E 文書整理版，待 C／組長確認最終圖號及 D 正式實驗輸出。來源均為 GitHub main。以下「可用」只代表有來源可引用，不代表正式實驗已完成。

| 圖號（暫編） | 圖表主題 | 目前可用內容 | 來源與責任 | 狀態／使用限制 |
|---|---|---|---|---|
| F01 | 三模式正式實驗設計 | 20 保留案 × 3 模式＝60 run；每配額日 6 run，規劃 11/16–11/25 | D `evaluation/d-drafts/v12-runner-freeze.md`；組長排程 | 可用設計圖，不能寫成實際完成 |
| F02 | single／dual／workflow 流程差異 | 三模式共用輸入、快照與預算；工具選擇及覆核流程不同 | D `evaluation/d-drafts/v12-runner-freeze.md` 第二、七節 | 可用流程圖 |
| F03 | dual v2 開發集逐案結果 | D 評分 10 案：8 符合預期、2 不符合；CASE-15、18 缺下一確認訊號 | D `evaluation/d-drafts/calib-v2-scores-D.txt`；B `calib-v2-check-B.md` | 可用開發案例圖，**不得稱正式成效** |
| F04 | dual v2 停止原因與資源次數 | 10 筆模型發送／工具呼叫／補查與 D 紀錄一致 | B `evaluation/d-drafts/calib-v2-check-B.md` 第三節 | 可用開發耗用圖；不是金額成本 |
| F05 | 正式三模式品質比較 | 評分維度及 unknown／unsupported／supported 定義可先展示 | D `evaluation/d-drafts/rubric-v1-final.md`；`v12-runner-freeze.md` | 正式數值待匿名匯出與核准評分；rubric 文件原標草稿 |
| F06 | 正式三模式資源成本 | 每 job 8 模型發送、10 工具、2 補查、180 秒限制 | D `evaluation/d-drafts/v12-runner-freeze.md` | 目前僅能做成本口徑／限制圖；正式耗用待結果 |
| F07 | NA 與不足證據處理 | unknown 是主張標籤；insufficient 是整份報告狀態；零主張支持率 NA | D `evaluation/d-drafts/rubric-v1-final.md`、`runner-smoke.md` | 可用規則圖；正式 NA 分布待結果 |
| F08 | 版本與前瞻成果分流 | 校準／smoke／正式研究條件分開；9 份前瞻不屬於 60 run | D `evaluation/d-drafts/v12-runner-freeze.md` 第四、七節 | 可用版本示意；前瞻 v1/v2 不混比 |

## 統一註記
- D 的 dual v2 校準是在舊 focus 條件及補股價前執行；11/14 預演與正式研究採案例 task，不能直接比較。
- 正式實驗 60 run 的品質、成本、NA 分布尚無可核准數值；待組長執行及 B／D 評分後填入。
- E 不開啟保留集題目或答案，不自行判讀主張正誤，不把開發集結果冒充正式成效。
- 每張正式結果圖待補：核准 CSV、資料版本、有效分母／NA、評分者、核准日期、圖表編號。

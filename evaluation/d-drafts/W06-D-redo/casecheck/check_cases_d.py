"""D 的案例核對（離線、只讀）：核對 dev-cases.json 的標準主張與擾動位置，是否和 fixtures 快照對得上。
用法：python3 check_cases_d.py <含 evaluation/dev-cases.json 與 fixtures/dev/case_fixtures.json 的目錄>
只處理開發案。不處理保留案（保留案由 D 本人核對，不放進 AI 的輸入）。
輸出：每案每項 OK / 需人工確認 / 不一致。「OK」只代表結構對得上，不代表標準答案正確。"""
import json, re, sys, os
from datetime import datetime
R = sys.argv[1] if len(sys.argv) > 1 else "."
cases = json.load(open(os.path.join(R, "evaluation/dev-cases.json"), encoding="utf-8"))["cases"]
fx = json.load(open(os.path.join(R, "fixtures/dev/case_fixtures.json"), encoding="utf-8"))["snapshots"]
t = lambda s: datetime.fromisoformat(s)
NUM = re.compile(r"\d[\d,]*\.?\d*")
def nums(text): return {x.replace(",", "").rstrip(".") for x in NUM.findall(text or "") if len(x.replace(",", "")) >= 3}
rows = []
for c in cases:
    cid = c["case_id"]; res = []
    snap = fx.get(c["source_snapshot_id"])
    if not snap: print(cid, "不一致：找不到快照", c["source_snapshot_id"]); continue
    evs = {e["evidence_version_id"]: e for e in snap.get("evidences", [])}
    cut = t(c["cutoff_at"])
    # 1 擾動位置存在
    for p in (c.get("perturbation_location") or []):
        if "evidence_version_id" not in p:  # 工具擾動（例如 CASE-26 的 tool_simulation）
            ok = bool(snap.get(p["field"]))
            res.append(("工具擾動設定存在", "OK" if ok else "需人工確認", f'{p.get("tool")}.{p["field"]}：快照內' + ("有" if ok else "找不到") + "對應設定"))
            continue
        e = evs.get(p["evidence_version_id"])
        if not e: res.append(("擾動來源存在", "不一致", f'{p["evidence_version_id"]} 不在快照'))
        elif p["field"] not in e: res.append(("擾動欄位存在", "不一致", f'{p["field"]} 不在 {p["evidence_version_id"]}'))
        else: res.append(("擾動位置存在", "OK", f'{p["evidence_version_id"]}.{p["field"]}'))
        # 2 擾動內容與 detail 的明顯關鍵事實
        if e and p["field"] == "paragraph" and "null" in p.get("detail", "") and e.get("paragraph") is not None:
            res.append(("擾動=paragraph 為 null", "不一致", "paragraph 不是 null"))
        if e and p["field"] == "available_at" and "晚於" in p.get("detail", ""):
            res.append(("擾動=cutoff 後公告", "OK" if t(e["available_at"]) > cut else "不一致", e["available_at"]))
    # 3 非擾動來源 available_at <= cutoff
    pert = {p.get("evidence_version_id") for p in (c.get("perturbation_location") or [])}
    for k, e in evs.items():
        if k not in pert and e.get("available_at") and t(e["available_at"]) > cut:
            res.append(("非擾動來源可得時間", "不一致", f"{k} 晚於 cutoff"))
    # 4 標準主張的數字是否出現在某個來源（含財務快照）
    pool = " ".join((e.get("paragraph") or "") for e in evs.values()) + " " + json.dumps(snap.get("financial_snapshot", {}), ensure_ascii=False)
    pn = {x.replace(",", "") for x in NUM.findall(pool)}
    for s in (c.get("expected_supported_claims") or []):
        miss = [n for n in nums(s) if n not in pn and n not in {"2026", "2025"}]
        res.append(("標準主張數字", "OK" if not miss else "需人工確認", f"{s[:34]}…；未在來源逐字出現：{miss}" if miss else s[:34] + "…"))
    if not c.get("expected_supported_claims"):
        res.append(("標準主張", "OK", "無（案例預期不補造事實）"))
    # 5 合成旗標
    flags = {bool(e.get("synthetic_fixture")) for e in evs.values()}
    if c.get("synthetic_fixture") is False and True in flags and cid not in ("CASE-18",):
        res.append(("合成旗標", "需人工確認", f"案例 synthetic_fixture=false，但來源含合成：{[k for k,e in evs.items() if e.get('synthetic_fixture')]}"))
    elif c.get("synthetic_fixture") is True and flags == {False}:
        res.append(("合成旗標", "需人工確認", "案例標合成，但來源都不是合成"))
    else: res.append(("合成旗標", "OK", f"case={c.get('synthetic_fixture')}"))
    rows.append((cid, c["variant"], res))
bad = 0
for cid, var, res in rows:
    print(f"\n{cid} {var}")
    for name, st, d in res:
        bad += st != "OK"
        print(f"  [{st}] {name}：{d}")
print(f"\n共 {len(rows)} 案；非 OK 項目 {bad} 個（不一致 = 要修；需人工確認 = D 要看原文）")

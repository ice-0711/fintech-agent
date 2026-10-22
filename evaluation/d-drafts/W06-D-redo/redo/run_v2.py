"""離線比對：用 dev_drafts_v2.json 的 10 份草稿跑 reviewer_checks.check_draft，對照預期決定。
用法：REPO_SNAP=<含 fixtures/dev 與 evaluation/dev-cases.json 的目錄> python3 run_v2.py
只讀開發案；不連網；不呼叫模型。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reviewer_checks import check_draft
from reviewer_v12 import validate_review
R = os.environ.get("REPO_SNAP", ".")
fx = json.load(open(os.path.join(R, "fixtures/dev/case_fixtures.json"), encoding="utf-8"))["snapshots"]
cases = {c["case_id"]: c for c in json.load(open(os.path.join(R, "evaluation/dev-cases.json"), encoding="utf-8"))["cases"]}
here = os.path.dirname(os.path.abspath(__file__))
entries = json.load(open(os.path.join(here, "dev_drafts_v2.json"), encoding="utf-8"))["entries"]
out, ok = [], 0
for e in entries:
    c = cases[e["case_id"]]
    sid = c["source_snapshot_id"]
    snap = dict(fx[sid]); snap.setdefault("ticker", c["ticker"])
    try:
        res = check_draft(e["draft"], snap, c["cutoff_at"], sid, observations=e.get("observations"))
        rv = res["review"]; got = rv["decision"]; crit = sorted({i["claim_id"] for i in rv["issues"] if i["severity"] == "critical"})
        errs = validate_review(rv, [x["claim_id"] for x in e["draft"]["claims"]])
        codes = [t for t in res.get("trace", [])][:6]
    except Exception as ex:
        got, crit, errs, codes = "ERROR", [], [repr(ex)], []
    match = (got == e["expected_decision"] and crit == sorted(e["expected_critical_claims"]) and not errs)
    ok += match
    out.append({"id": e["id"], "expected": e["expected_decision"], "got": got, "expected_critical": e["expected_critical_claims"], "got_critical": crit, "schema_errors": errs, "match": match})
    print(f'{e["id"]:16} expected={e["expected_decision"]:12} got={got:12} critical={crit} match={match}' + (f" ERR={errs}" if errs else ""))
print(f"{ok}/{len(entries)} 符合預期")
json.dump(out, open(os.path.join(here, "dev-drafts-v2-results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

"""B 盲評紀錄轉 CSV：把填好的評分紀錄（export_for_scoring.py 產生的 score-template-*.txt 格式）
轉成 W10／W11 交付的兩個 CSV，並在轉檔前檢查有沒有漏填。

    python scripts/scores_to_csv.py evaluation/formal/scoring-v2/scores-B.txt --batch batch1
    python scripts/scores_to_csv.py evaluation/formal/scoring-v2/scores-B.txt --batch batch2

    批次照決策 42：依 evaluation/run-plan.json，第 1–5 個配額日的 10 案為 batch1、第 6–10 日為 batch2
    （只讀 case_id 與 quota_day_index）。也可以用 --cases 直接列案例。

輸出（以 --batch batch1、--rater B 為例）
- ratings-B-batch1.csv：一個主張一列（answer_id、case_id、claim_id、kind、label、是否計分、理由）。
- v12-batch1-scores.csv：一份答卷一列（各標註數量、計分分母、引用可解析數/總數、植入錯誤、拒答、整體結果）。

讀得懂的寫法（與 rubric-v1-final.md 第六節、校準 v1／v2 評分檔一致）：
    <answer_id> | 案例: <case_id>
      c1(fact): 標註: supported   理由: ...
      c2: unsupported  理由: ...
      c3(unknown類): 不計分 ...
      引用可解析數/總數: 2/3
      植入錯誤: 預期 1 個、被指出 1 個、修正 0 個     （11/16 起範本固定有這行，要填完；舊寫法「預期1 指出1 修正0」也可）
      拒答: 是否選 insufficient: 否   是否說明缺口: 否  （同上；舊寫法「否 說明缺口: 否」也可）
      整體結果: 符合預期   理由: ...
      備註: ...
其他行（停止原因等）略過不讀。

規則
- 標註只能是 supported／unsupported／unknown；kind 為 inference、unknown，或標「不計分」的主張不進分母。
- 還留著範本空白（標註空白、整體結果仍是「符合預期 / 不符合預期」、引用數空白）就報錯，不產生 CSV。
- 「不確定」視為未完成，報錯；請先決定標註，把猶豫寫在備註。
- 只處理 --cases 列出的案例（批次範圍由組長公布的案例清單決定）；清單中的案例若沒有任何答卷也報錯。
- 本程式只讀評分紀錄檔，不讀保留集、不讀對照表，也不在終端印出主張內容。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

LABELS = ("supported", "unsupported", "unknown")
UNSCORED_KINDS = ("inference", "unknown", "unknown類")
OVERALL = ("符合預期", "不符合預期")

HEAD = re.compile(r"^(\S+)\s*\|\s*案例[:：]\s*([A-Za-z0-9_-]+)")
CLAIM = re.compile(r"^\s+(c\d+)(?:\(([^)]*)\))?[:：]\s*(.*)$")
CITES = re.compile(r"^\s+引用可解析數/總數[:：]\s*(\d+)\s*/\s*(\d+)")
CITES_LINE = re.compile(r"^\s+引用可解析數/總數[:：]")
INJECT = re.compile(r"^\s+植入錯誤[:：]\s*預期\s*(\d+)\s*個?\s*[、，,]?\s*(?:被)?指出\s*(\d+)\s*個?\s*[、，,]?\s*修正\s*(\d+)")
INJECT_LINE = re.compile(r"^\s+植入錯誤[:：]")
REFUSE = re.compile(r"^\s+拒答[:：]\s*(?:是否選\s*insufficient[:：]\s*)?(是|否)\s+(?:是否)?說明缺口[:：]?\s*(是|否)\s*$")
REFUSE_LINE = re.compile(r"^\s+拒答[:：]")
OVERALL_LINE = re.compile(r"^\s+整體結果[:：]\s*(.*)$")
NOTE_LINE = re.compile(r"^\s+備註[:：]\s*(.*)$")
REASON = re.compile(r"理由[:：]\s*(.*)$")


def _split_reason(text: str) -> tuple[str, str]:
    m = REASON.search(text)
    if not m:
        return text.strip(), ""
    return text[:m.start()].strip(), m.group(1).strip()


def parse(text: str) -> tuple[list[dict], list[str]]:
    """Return (answers, errors). Errors cite answer_id and claim_id only, never claim text."""
    answers: list[dict] = []
    errors: list[str] = []
    cur: dict | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if (m := HEAD.match(line)):
            cur = {"answer_id": m.group(1), "case_id": m.group(2), "claims": [], "cites": None,
                   "inject": None, "refuse": None, "overall": None, "overall_reason": "", "note": ""}
            answers.append(cur)
            continue
        if cur is None or not line.strip():
            continue
        if (m := CLAIM.match(line)):
            cid, kind, rest = m.group(1), (m.group(2) or "").strip(), m.group(3)
            rest = re.sub(r"^標註[:：]\s*", "", rest.strip())
            label_part, reason = _split_reason(rest)
            label = label_part.split()[0].rstrip(",，") if label_part.split() else ""
            if label.startswith("不計分") or kind in UNSCORED_KINDS:
                scored, label = False, (label if label in LABELS else "不計分")
                reason = reason or label_part.removeprefix("不計分").lstrip(",， ")
            elif label in LABELS:
                scored = True
            else:
                scored = True
                errors.append(f"{cur['answer_id']} {cid}：標註「{label or '空白'}」不是 supported／unsupported／unknown")
            if scored and not reason:
                errors.append(f"{cur['answer_id']} {cid}：缺理由")
            cur["claims"].append({"claim_id": cid, "kind": kind, "label": label, "scored": scored, "reason": reason})
        elif CITES_LINE.match(line):
            m = CITES.match(line)
            if not m:
                errors.append(f"{cur['answer_id']}：引用可解析數/總數未填")
            else:
                ok, total = int(m.group(1)), int(m.group(2))
                if ok > total:
                    errors.append(f"{cur['answer_id']}：可解析數 {ok} 大於總數 {total}")
                cur["cites"] = (ok, total)
        elif INJECT_LINE.match(line):
            m = INJECT.match(line)
            if not m:
                errors.append(f"{cur['answer_id']}：植入錯誤未填完（每格填數字，沒有植入就填 0）")
            else:
                cur["inject"] = tuple(int(x) for x in m.groups())
        elif REFUSE_LINE.match(line):
            m = REFUSE.match(line)
            if not m:
                errors.append(f"{cur['answer_id']}：拒答未填完（兩格各選「是」或「否」，不要留「是 / 否」）")
            else:
                cur["refuse"] = m.groups()
        elif (m := OVERALL_LINE.match(line)):
            verdict, reason = _split_reason(m.group(1))
            if verdict not in OVERALL:
                errors.append(f"{cur['answer_id']}：整體結果「{verdict or '空白'}」需填 符合預期 或 不符合預期")
            cur["overall"], cur["overall_reason"] = verdict, reason
        elif (m := NOTE_LINE.match(line)):
            cur["note"] = m.group(1).strip()
    for a in answers:
        if a["cites"] is None:
            errors.append(f"{a['answer_id']}：缺「引用可解析數/總數」")
        if a["overall"] is None:
            errors.append(f"{a['answer_id']}：缺「整體結果」")
    ids = [a["answer_id"] for a in answers]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"{dup}：答卷編號重複")
    return answers, errors


def cases_for_batch(plan: Path, batch: str) -> list[str]:
    """決策 42：batch1＝第 1–5 個配額日的案例、batch2＝第 6–10 日，順序照執行計畫。"""
    days = {"batch1": range(1, 6), "batch2": range(6, 11)}.get(batch)
    if days is None:
        raise SystemExit("沒給 --cases 時，--batch 只能是 batch1 或 batch2")
    runs = json.loads(plan.read_text(encoding="utf-8"))["runs"]
    return list(dict.fromkeys(r["case_id"] for r in runs if r["quota_day_index"] in days))


def write_csvs(answers: list[dict], out_dir: Path, rater: str, batch: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ratings = out_dir / f"ratings-{rater}-{batch}.csv"
    scores = out_dir / f"v12-{batch}-scores.csv"
    with ratings.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rater", "answer_id", "case_id", "claim_id", "kind", "label", "scored", "reason"])
        for a in answers:
            for c in a["claims"]:
                w.writerow([rater, a["answer_id"], a["case_id"], c["claim_id"], c["kind"], c["label"],
                            "yes" if c["scored"] else "no", c["reason"]])
    na = "NA"
    with scores.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rater", "answer_id", "case_id", "claims_total", "claims_scored", "supported", "unsupported",
                    "unknown", "cites_resolvable", "cites_total", "inject_expected", "inject_flagged",
                    "inject_fixed", "chose_insufficient", "explained_gap", "overall", "overall_reason", "note"])
        for a in answers:
            sc = [c for c in a["claims"] if c["scored"]]
            n = {lab: sum(c["label"] == lab for c in sc) for lab in LABELS}
            inj = a["inject"] or (na, na, na)
            ref = a["refuse"] or (na, na)
            w.writerow([rater, a["answer_id"], a["case_id"], len(a["claims"]), len(sc), n["supported"],
                        n["unsupported"], n["unknown"], *a["cites"], *inj, *ref, a["overall"],
                        a["overall_reason"], a["note"]])
    return ratings, scores


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="評分紀錄檔轉 W10／W11 CSV（只讀評分檔）")
    ap.add_argument("scores_file")
    ap.add_argument("--cases", help="本批案例，以逗號分隔；不給就依 --plan 與 --batch 自動取")
    ap.add_argument("--plan", default="evaluation/run-plan.json", help="執行計畫（只讀 case_id、quota_day_index）")
    ap.add_argument("--batch", required=True, help="batch1 或 batch2")
    ap.add_argument("--rater", default="B")
    ap.add_argument("--out-dir", default="evaluation")
    args = ap.parse_args(argv)

    answers, errors = parse(Path(args.scores_file).read_text(encoding="utf-8"))
    if args.cases:
        wanted = [c.strip() for c in args.cases.split(",") if c.strip()]
    else:
        wanted = cases_for_batch(Path(args.plan), args.batch)
    picked = [a for a in answers if a["case_id"] in wanted]
    errors = [e for e in errors if e.split("：")[0].split()[0] in {a["answer_id"] for a in picked}]
    for c in wanted:
        if not any(a["case_id"] == c for a in picked):
            errors.append(f"{c}：評分檔中沒有這個案例的答卷")
    if errors:
        print(f"有 {len(errors)} 個問題，未產生 CSV：")
        for e in errors:
            print("  -", e)
        return 1
    ratings, scores = write_csvs(picked, Path(args.out_dir), args.rater, args.batch)
    n_claims = sum(len(a["claims"]) for a in picked)
    n_scored = sum(c["scored"] for a in picked for c in a["claims"])
    print(f"{len(wanted)} 案、{len(picked)} 份答卷、{n_claims} 個主張（計分 {n_scored}）")
    print(f"已寫出 {ratings} 與 {scores}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
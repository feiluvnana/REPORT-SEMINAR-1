"""Step 4 run audit: completeness, tool-call audit, schema sanity, and per-run cost table.

Writes result/run/run_summary.csv. Usage: .venv/bin/python script/audit_runs.py
"""
import csv
import json
import re
import statistics as st
import sys

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
from collections import Counter
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from paths import RUN_DIR, doc_path
TOOLS=["T1","T2","T3","T4"]; DOCS=["keepass","peering","gammaj","seeded_lms"]
GT_RE=re.compile(r"ground_truth|seed_key|final_gt|expert_pass|gt_hidden", re.I)
FORBID=re.compile(r"^(search_web|read_url_content|browser_.*|run_command)$")
problems=[]; rows=[]
status=list(csv.DictReader(open(RUN_DIR/"run_status.csv",encoding="utf-8")))
print("status rows:",Counter(r["status"] for r in status))
for t in TOOLS:
    for d in DOCS:
        reqs=[r["req_id"] for r in json.load(open(doc_path(d),encoding="utf-8"))["requirements"]]
        order={r:i for i,r in enumerate(reqs)}
        for k in (1,2,3):
            base=RUN_DIR/t/d; j=base/f"run_{k}.json"; m=base/f"run_{k}.meta.json"; l=base/f"run_{k}.log"
            if not (j.exists() and m.exists() and l.exists()):
                problems.append(f"{t}/{d}/{k}: missing file"); continue
            out=json.load(open(j,encoding="utf-8")); meta=json.load(open(m,encoding="utf-8"))
            f=out["findings"]
            if out["doc_id"]!=d: problems.append(f"{t}/{d}/{k}: doc_id {out['doc_id']}")
            bad=[x["req_id"] for x in f if x["req_id"] not in order]
            if bad: problems.append(f"{t}/{d}/{k}: unknown req_id {bad[:3]}")
            pairs=Counter((x["req_id"],x["type"]) for x in f); dup=sum(v-1 for v in pairs.values() if v>1)
            anchor=sum(1 for x in f if x["type"]=="inconsistency" and any(r in order and order[r]>order.get(x["req_id"],-1) for r in x.get("related_ids",[])))
            done=[s for s in meta["tool_calls"] if s.get("state") in (None,"DONE")]
            names=Counter(s["tool_name"] for s in done)
            forb=[n for n in names if FORBID.match(n or "")]
            skill=any((s.get("path") or "").replace("\\","/").endswith("skill/req-defect-detector/SKILL.md") for s in done)
            other=[s["path"] for s in done if s.get("path") and not s["path"].replace("\\","/").endswith("SKILL.md")]
            if forb: problems.append(f"{t}/{d}/{k}: forbidden {forb}")
            if t in ("T2","T4") and not skill: problems.append(f"{t}/{d}/{k}: SKILL.md not read")
            if t in ("T1","T3") and done: problems.append(f"{t}/{d}/{k}: plain run used tools {dict(names)}")
            if other: problems.append(f"{t}/{d}/{k}: other reads {other}")
            if meta.get("audit_errors"): problems.append(f"{t}/{d}/{k}: audit {meta['audit_errors']}")
            if meta.get("denied_actions"): problems.append(f"{t}/{d}/{k}: denied {meta['denied_actions']}")
            if GT_RE.search(l.read_text(encoding="utf-8",errors="replace")): problems.append(f"{t}/{d}/{k}: GT string in log")
            u=meta.get("usage") or {}
            rows.append(dict(tool=t,doc_id=d,run=k,findings=len(f),dup_pairs=dup,misanchored_inconsistency=anchor,
                 n_amb=sum(x["type"]=="ambiguity" for x in f),n_inc=sum(x["type"]=="incompleteness" for x in f),n_con=sum(x["type"]=="inconsistency" for x in f),
                 duration_s=round(meta.get("duration_seconds") or 0,1),input_tokens=u.get("input_tokens"),output_tokens=u.get("output_tokens"),
                 thinking_tokens=u.get("thinking_tokens"),total_tokens=u.get("total_tokens"),tool_calls=";".join(f"{a}x{b}" for a,b in names.items()),skill_read=skill))
with open(RUN_DIR/"run_summary.csv","w",newline="",encoding="utf-8") as fh:
    w=csv.DictWriter(fh,fieldnames=list(rows[0]),lineterminator="\n"); w.writeheader(); w.writerows(rows)
print("runs checked:",len(rows)); print("PROBLEMS:",len(problems)); [print(" ",p) for p in problems]
print("\ntool  runs findings(mean,min-max)  dup  misanch  dur_s(mean,max)  total_tok(mean)  skill_read")
for t in TOOLS:
    R=[r for r in rows if r["tool"]==t]
    fs=[r["findings"] for r in R]; ds=[r["duration_s"] for r in R]; tk=[r["total_tokens"] or 0 for r in R]
    print(f"{t}   {len(R)}   {st.mean(fs):5.1f} ({min(fs)}-{max(fs)})   {sum(r['dup_pairs'] for r in R)}   {sum(r['misanchored_inconsistency'] for r in R)}   {st.mean(ds):5.0f} ({max(ds):.0f})   {st.mean(tk):8.0f}   {sum(r['skill_read'] for r in R)}/{len(R)}")
print("\nfindings per doc (mean of 3):")
for d in DOCS:
    print(f"  {d:11s}", "  ".join(f"{t}:{st.mean(r['findings'] for r in rows if r['tool']==t and r['doc_id']==d):5.1f}" for t in TOOLS))
print("\ntype mix per tool (total over 12 runs):")
for t in TOOLS:
    R=[r for r in rows if r["tool"]==t]; print(f"  {t} amb {sum(r['n_amb'] for r in R)}  inc {sum(r['n_inc'] for r in R)}  con {sum(r['n_con'] for r in R)}")
print("\ntotal agy time %.1f min, total tokens %d"%(sum(r["duration_s"] for r in rows)/60, sum(r["total_tokens"] or 0 for r in rows)))

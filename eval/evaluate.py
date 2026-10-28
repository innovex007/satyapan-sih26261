"""make eval: compare the pipeline's findings with data/answer_key.json.  Prints and saves eval/results.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlmodel import Session, select  # noqa: E402

from app.core.config import STORAGE_DIR  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.models import Application, Finding  # noqa: E402
from app.pipeline.accuracy import classification_accuracy, fact_accuracy  # noqa: E402

RULE_FOR_TYPE = {1: "CHK-COMPLETE", 2: "CHK-EXPIRY", 3: "CHK-XDOC-LAND", 4: "CHK-FORENSIC", 5: "CHK-TWIN", 6: "SRC-QR", 7: "SRC-SIG", 8: "CHK-FACULTY", 9: "CHK-SHAREDLAND", 10: "CHK-TIMELINE"}
TYPE_NAME = {1: "Missing document", 2: "Expired Fire NOC", 3: "Land-area mismatch", 4: "Date edited after signing", 5: "Lab photo reused",
             6: "QR differs from print", 7: "Unsigned / broken signature", 8: "Duplicate faculty ID", 9: "Shared land parcel", 10: "Impossible timeline"}


def main():
    key = json.loads((ROOT / "data" / "answer_key.json").read_text(encoding="utf-8"))
    clean = {a["id"] for a in key["applications"] if a["clean"]}
    current = {a["id"] for a in key["applications"]}
    expected_unavail = {(e["application_id"], e["doc_type"]) for e in key["source_expectations"] if e["expected_status"] == "Source unavailable"}
    with Session(engine) as s:
        findings = [f for f in s.exec(select(Finding)).all() if f.application_id in current]
        lanes = {a.id: a.risk_lane for a in s.exec(select(Application)).all()}
        cls, facts = classification_accuracy(s), fact_accuracy(s)

    def rule(f):
        return f.rule_id.split("/", 1)[1]

    used: set[int] = set()
    per_type = {t: {"found": 0, "total": 0} for t in RULE_FOR_TYPE}
    missed = []
    for d in key["defects"]:
        t = d["type_id"]
        per_type[t]["total"] += 1
        hit = next((f for f in findings if f.id not in used and f.application_id == d["application_id"] and rule(f).startswith(RULE_FOR_TYPE[t])
                    and (t != 1 or f.evidence[0]["doc_type"] == d["doc_type"])
                    and (t != 5 or f.evidence[0]["filename"] == d["document"])), None)
        if hit:
            used.add(hit.id)
            per_type[t]["found"] += 1
        else:
            missed.append((d["application_id"], TYPE_NAME[t], d["document"]))

    def expected_nondefect(f):
        return rule(f) == "SRC-ISSUER-01" and (f.application_id, f.evidence[0]["doc_type"]) in expected_unavail

    extra = [f for f in findings if f.id not in used and not expected_nondefect(f)]
    false_alarms = [f for f in extra if f.application_id in clean]
    clean_docs = sum(len(a["documents"]) for a in key["applications"] if a["clean"])
    found = sum(v["found"] for v in per_type.values())
    timing = json.loads((STORAGE_DIR / "pipeline_timing.json").read_text())

    decoys = key.get("decoys", [])
    decoys_flagged = [d["application_id"] for d in decoys if any(f.application_id == d["application_id"] and rule(f).startswith("CHK-SHAREDLAND") for f in findings)]
    heroes = {}
    def has(app, prefix, status=None):
        return any(f.application_id == app and rule(f).startswith(prefix) and (status is None or f.status == status) for f in findings)
    heroes["EoA-DEMO-0417 land-area mismatch"] = has("EoA-DEMO-0417", "CHK-XDOC-LAND", "Mismatch detected")
    heroes["EoA-DEMO-0417 twin of #4417"] = has("EoA-DEMO-0417", "CHK-TWIN", "Manual review required")
    heroes["EoA-DEMO-0422 Fire NOC expired"] = has("EoA-DEMO-0422", "CHK-EXPIRY", "Expired")
    heroes["EoA-DEMO-0422 QR mismatch"] = has("EoA-DEMO-0422", "SRC-QR", "Mismatch detected")
    heroes["EoA-DEMO-0431 forensic indicator"] = has("EoA-DEMO-0431", "CHK-FORENSIC", "Manual review required")
    heroes["EoA-DEMO-0431 source unavailable"] = has("EoA-DEMO-0431", "SRC-ISSUER-01", "Source unavailable")
    heroes["EoA-DEMO-0440 clean -> Green, no flags"] = lanes["EoA-DEMO-0440"] == "Green" and not any(f.application_id == "EoA-DEMO-0440" for f in findings)

    res = {
        "planted_found": found, "planted_total": len(key["defects"]), "per_type": {TYPE_NAME[t]: v for t, v in per_type.items()},
        "missed": missed, "clean_applications": len(clean), "false_alarms_on_clean": len(false_alarms),
        "false_alarm_detail": [(f.application_id, f.rule_id.split('/')[1], f.reason[:90]) for f in false_alarms],
        "false_alarms_per_100_clean_docs": round(100 * len(false_alarms) / max(clean_docs, 1), 1),
        "unplanned_findings_total": len(extra),
        "unplanned_detail": [(f.application_id, f.rule_id.split("/")[1], f.status, f.reason[:160]) for f in extra],
        "precision": round(found / max(found + len(extra), 1), 3), "recall": round(found / len(key["defects"]), 3),
        "ocr_scanned_facts": {k: facts["scan"][k] for k in ("tp", "expected", "precision", "recall", "f1")},
        "text_layer_facts": {k: facts["text"][k] for k in ("tp", "expected", "precision", "recall", "f1")},
        "classification": {k: cls[k] for k in ("correct", "total", "accuracy")},
        "avg_seconds_per_application": timing["avg_seconds_per_application"],
        "risk_lanes": {l: sum(1 for a in current if lanes.get(a) == l) for l in ("Green", "Amber", "Red")},
        "decoys": len(decoys), "decoys_flagged": len(decoys_flagged), "hero_cases": heroes, "note": "Measured on synthetic data; simulated sources.",
    }
    sys.path.insert(0, str(ROOT / "eval"))
    from twin_scan import run as twin_run

    tw = twin_run(verbose=False)
    res["twins"] = {
        "detected": tw["detected"], "planted": tw["planted_twins"], "by_type": {k: {"detected": sum(v["detected"] for v in rows), "total": len(rows),
                        "stage": sorted({v["kind"] or "missed" for v in rows}), "min_inliers": min(v["inliers"] for v in rows)} for k, rows in tw["detection"].items()},
        "hard_negatives": tw["hard_negatives"], "unplanted_pairs": tw["unplanted_pairs"], "false_matches": tw["false_matches"],
        "threshold_min_inliers": tw["threshold_min_inliers"], "max_inliers_non_twin": tw["max_inliers_on_non_twin"],
        "min_inliers_reshot": tw["min_inliers_on_orb_verified_twin"], "margin_below": tw["margin_below_threshold"], "margin_above": tw["margin_above_threshold"]}
    (ROOT / "eval" / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"\nPlanted defects found: {found}/{len(key['defects'])}   precision {res['precision']}   recall {res['recall']}")
    for n, v in res["per_type"].items():
        print(f"  {n:<30} {v['found']}/{v['total']}")
    print(f"False alarms on the {len(clean)} clean applications: {len(false_alarms)}  ({res['false_alarms_per_100_clean_docs']} per 100 clean documents)")
    for d in res["false_alarm_detail"]:
        print("   ", d)
    print(f"Unplanned findings on all applications: {len(extra)}")
    for d in res["unplanned_detail"]:
        print("   ", d)
    s_, t_ = res["ocr_scanned_facts"], res["text_layer_facts"]
    print(f"Scanned-fact OCR accuracy: {s_['tp']}/{s_['expected']}  (P {s_['precision']:.3f} R {s_['recall']:.3f} F1 {s_['f1']:.3f})")
    print(f"Text-layer fact accuracy:  {t_['tp']}/{t_['expected']}  (F1 {t_['f1']:.3f})")
    print(f"Classification: {cls['correct']}/{cls['total']} ({cls['accuracy']:.1%})")
    print(f"Average processing time per application: {res['avg_seconds_per_application']}s   Risk lanes: {res['risk_lanes']}")
    t = res["twins"]
    print(f"Twin detection: {t['detected']}/{t['planted']}  " + "; ".join(f"{k}: {v['detected']}/{v['total']} via {'+'.join(v['stage'])}" for k, v in t["by_type"].items()))
    print(f"  hard negatives flagged: {sum(h['flagged'] for h in t['hard_negatives'])}/{len(t['hard_negatives'])}   false matches on {t['unplanted_pairs']} unplanted pairs: {t['false_matches']}   "
          f"threshold {t['threshold_min_inliers']} (max non-twin {t['max_inliers_non_twin']}, min re-shot {t['min_inliers_reshot']})")
    print(f"Shared-land decoys flagged: {len(decoys_flagged)}/{len(decoys)}")
    print("Hero cases:", {k: ("OK" if v else "MISS") for k, v in heroes.items()})
    if missed:
        print("Missed:", missed)


if __name__ == "__main__":
    main()

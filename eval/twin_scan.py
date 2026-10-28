"""Twin detector measured against the answer key (two-stage: pHash, then ORB + RANSAC).

Reports: detection by type (hero re-shot, real copies, drawn copies), the chem-lab / lecture-hall hard negatives,
false matches over every unplanted cross-institution pair, and the margin to the ORB inlier threshold.
    python eval/twin_scan.py            (needs `make seed`)"""
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image  # noqa: E402

from app.pipeline import similarity as sim  # noqa: E402


def run(verbose=True) -> dict:
    key = json.loads((ROOT / "data" / "answer_key.json").read_text(encoding="utf-8"))
    cfg = sim.cfg()
    thr = cfg["orb"]["min_inliers"]
    imgs = []  # dict per image
    for a in key["applications"] + key["last_year_applications"]:
        for d in a["documents"]:
            if d["kind"] == "image":
                p = ROOT / "storage" / d["path"]
                imgs.append({"inst": a["permanent_id"], "app": a["id"], "file": d["file"], "type": d["doc_type"], "path": p, "ph": sim.fingerprint(Image.open(p))["phash"],
                             "real": d.get("real_photo"), "mode": d.get("real_mode")})

    expected = {}
    for d in key["defects"]:
        if d["type_id"] == 5:
            det = d["detail"]
            pair = frozenset({(d["application_id"], d["document"]), (det["source_application"], det["source_file"])})
            expected[pair] = {"kind": det.get("twin_kind", "copy"), "app": d["application_id"], "real": bool(det.get("base")) or det.get("twin_kind") == "reshot",
                              "label": ("hero re-shot" if det.get("twin_kind") == "reshot" else "real-photo copy" if det.get("base") else "drawn-room copy")}

    def family(im):
        r = im["real"] or ""
        return "chem_lab" if r.startswith("chem_lab") else "lecture_hall" if r.startswith("lecture_hall") else None

    found, nontwin, hard = {}, [], []
    for A, B in combinations(imgs, 2):
        if A["inst"] == B["inst"]:
            continue
        pair = frozenset({(A["app"], A["file"]), (B["app"], B["file"])})
        ok = sim.orb_applies(A["type"], B["type"])
        r = sim.compare(A["ph"], B["ph"], A["path"], B["path"], cfg, ok)
        # for pairs that involve a real photo also measure ORB regardless of the pHash filter (honest margin)
        orb = r["orb"] or (sim.orb_verify(A["path"], B["path"], cfg) if ok and (A["real"] or B["real"]) else None)
        inl = orb["inliers"] if orb else 0
        if pair in expected:
            found[pair] = (r, inl)
        else:
            nontwin.append((inl, r["phash_distance"], A["app"], A["file"], B["app"], B["file"], r["twin"]))
            fa, fb = family(A), family(B)
            if fa and fa == fb and A["real"] != B["real"]:
                hard.append({"pair": f"{A['real']} @ {A['app']}  vs  {B['real']} @ {B['app']}", "phash": r["phash_distance"], "inliers": inl, "flagged": r["twin"]})

    by_label: dict[str, list] = {}
    for pair, meta in expected.items():
        r, inl = found[pair]
        by_label.setdefault(meta["label"], []).append({"app": meta["app"], "phash": r["phash_distance"], "inliers": inl, "kind": r["kind"], "detected": r["twin"]})
    nontwin.sort(reverse=True)
    fps = [x for x in nontwin if x[6]]
    twin_inl = [v["inliers"] for rows in by_label.values() for v in rows if v["kind"] == "reshot" or not v["detected"] or v["inliers"]]
    reshot_inl = [v["inliers"] for rows in by_label.values() for v in rows if v["kind"] == "reshot"]
    max_non = nontwin[0][0] if nontwin else 0
    out = {
        "threshold_min_inliers": thr, "detection": by_label,
        "detected": sum(v["detected"] for rows in by_label.values() for v in rows), "planted_twins": sum(len(r) for r in by_label.values()),
        "hard_negatives": hard, "unplanted_pairs": len(nontwin), "false_matches": len(fps),
        "false_match_detail": [(x[2], x[3], x[4], x[5], x[0]) for x in fps],
        "max_inliers_on_non_twin": max_non, "max_non_twin_pair": nontwin[0][2:6] if nontwin else None,
        "min_inliers_on_orb_verified_twin": min(reshot_inl) if reshot_inl else None,
        "margin_below_threshold": thr - max_non,
        "margin_above_threshold": (min(reshot_inl) - thr) if reshot_inl else None,
        "top_non_twin_inliers": [(x[0], x[2], x[3], x[4], x[5]) for x in nontwin[:8]],
    }
    if verbose:
        print(f"ORB threshold (min inliers): {thr}   candidate filter: pHash <= {cfg['hash_candidate_max']}, copy: pHash <= {cfg['hash_flag_max']}")
        for label, rows in by_label.items():
            for v in rows:
                print(f"  {label:<16} {v['app']:<15} pHash {v['phash']:>2}  inliers {v['inliers']:>4}  -> {v['kind'] or 'NOT DETECTED'}")
        print(f"Planted twins detected: {out['detected']}/{out['planted_twins']}")
        print("Hard negatives (similar-looking, different rooms):")
        for h in hard:
            print(f"  pHash {h['phash']:>2}  inliers {h['inliers']:>3}  flagged={h['flagged']}   {h['pair']}")
        print(f"Unplanted cross-institution pairs checked: {len(nontwin)}   false matches: {len(fps)}")
        print(f"Highest ORB inliers on any non-twin pair: {max_non} {out['max_non_twin_pair']}")
        print(f"Lowest inliers on an ORB-verified twin: {out['min_inliers_on_orb_verified_twin']}")
        print(f"Margin: {out['margin_below_threshold']} inliers below threshold on the non-twin side, {out['margin_above_threshold']} above on the twin side")
        print("Top non-twin pairs by inliers:")
        for t in out["top_non_twin_inliers"]:
            print("  ", t)
    (ROOT / "eval" / "twin_results.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out


if __name__ == "__main__":
    run()

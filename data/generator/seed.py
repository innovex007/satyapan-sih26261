"""make seed  ->  python -m data.generator.seed --seed 42

Generates the synthetic dataset (files + answer_key.json + mock_registry.json) and loads the database.
Re-running resets storage/files and the database."""
import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

import imagehash  # noqa: E402
import yaml  # noqa: E402
from PIL import Image  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app.core.config import STORAGE_DIR  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.models import Application, Document, Institution  # noqa: E402
from data.generator.build import build  # noqa: E402
from data.generator.world import build_world  # noqa: E402

RULES = ROOT / "backend" / "app" / "rules" / "aph_2026_27.yaml"


def load_db(answer: dict, world: dict, seed: int) -> dict:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    rng = random.Random(seed + 7)
    counts = {"institutions": 0, "applications": 0, "documents": 0}
    with Session(engine) as s:
        inst_ids: dict[str, int] = {}

        def inst(name, perm, state="", region="", pin="", archive=False):
            if perm in inst_ids:
                return inst_ids[perm]
            i = Institution(name=name, aliases=[], permanent_id=perm, state=state, region=region, pincode=pin, archive_only=archive)
            s.add(i)
            s.flush()
            inst_ids[perm] = i.id
            counts["institutions"] += 1
            return i.id

        def docs_for(app_id, docs):
            for d in docs:
                s.add(Document(application_id=app_id, doc_type="unclassified", category_group="Unclassified", filename=d["file"],
                               pages=d["pages"], file_path=d["path"], quality_ok=True))
                counts["documents"] += 1

        wa = {a["id"]: a for a in world["apps"]}
        for a in answer["applications"]:
            t = wa[a["id"]]["truth"]
            iid = inst(a["institution"], a["permanent_id"], t["state"], t["region"], t["pincode"])
            sub = datetime.combine(wa[a["id"]]["submitted"], datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=rng.randint(9, 18), minutes=rng.randint(0, 59))
            s.add(Application(id=a["id"], institution_id=iid, category=a["category"], academic_session="2026-27", submitted_at=sub, status="Received"))
            counts["applications"] += 1
            docs_for(a["id"], a["documents"])
        for ly in answer["last_year_applications"]:
            iid = inst(ly["institution"], ly["permanent_id"], archive=ly["archive_only"])
            s.add(Application(id=ly["id"], institution_id=iid, category="Extension of Approval", academic_session="2025-26",
                              submitted_at=datetime(2025, 5, 20, 11, 0, tzinfo=timezone.utc), status="Reviewed", risk_lane="Green",
                              cycle_label=ly["cycle_label"]))
            counts["applications"] += 1
            docs_for(ly["id"], ly["documents"])
        s.commit()
    return counts


def sanity_photos(answer: dict) -> tuple[int, int]:
    """Smallest distance (by any of pHash/dHash/wHash) between images of different institutions, excluding planted twin pairs."""
    imgs = []
    for a in answer["applications"] + answer["last_year_applications"]:
        for d in a["documents"]:
            if d["kind"] == "image":
                im = Image.open(STORAGE_DIR / d["path"])
                imgs.append((a["permanent_id"], a["id"], d["file"], (imagehash.phash(im), imagehash.dhash(im), imagehash.whash(im))))
    planted = {(x["application_id"], x["detail"].get("source_application")) for x in answer["defects"] if x["type_id"] == 5}
    planted |= {(b, a) for a, b in planted}
    best, close = 99, 0
    for (i1, a1, f1, h1), (i2, a2, f2, h2) in combinations(imgs, 2):
        if i1 == i2 or (a1, a2) in planted:
            continue
        dist = h1[0] - h2[0]  # pHash: the detector's metric
        best = min(best, dist)
        close += dist <= 6
    return best, close


def hero_table(answer: dict) -> str:
    defects = answer["defects"]

    def find(app, tid):
        return next(d for d in defects if d["application_id"] == app and d["type_id"] == tid)

    twin = find("EoA-DEMO-0417", 5)["detail"]
    fire = find("EoA-DEMO-0422", 2)["detail"]
    edit = find("EoA-DEMO-0431", 4)["detail"]
    luc = next(e for e in answer["source_expectations"] if e["application_id"] == "EoA-DEMO-0431" and e["doc_type"] == "land_use_cert")
    rows = [
        ("EoA-DEMO-0417", "Land area: deed 10.00 acres vs plan 8.50 acres", "Mismatch detected (side-by-side, both regions pinned)"),
        ("EoA-DEMO-0417", f"Lab photo is the SAME ROOM as #{twin['source_application'].split('-')[-1]}'s 2025 file, re-shot (pHash dist {twin['phash_distance']}; keypoint-verified)", "Manual review required (Twin search, keypoint lines)"),
        ("EoA-DEMO-0422", f"Fire NOC valid till {fire['printed_valid_till']} vs session start 2026-07-01", "Expired"),
        ("EoA-DEMO-0422", "Fire NOC QR says valid till 2027-03-31, print says 31-03-2026", "Mismatch detected"),
        ("EoA-DEMO-0431", f"Affidavit date edited after signing ({edit['original']} -> {edit['edited']}); Courier font outlier", "Manual review required (preliminary, 2 indicators)"),
        ("EoA-DEMO-0431", f"Land-use certificate issuer has no online channel ({luc['channel']})", "Source unavailable + drafted letter"),
        ("EoA-DEMO-0440", "No planted defects", "Verified everywhere, Green lane"),
    ]
    w0, w1 = 15, max(len(r[1]) for r in rows)
    out = ["", f"{'HERO CASE':<{w0}} {'WHAT IS PLANTED':<{w1}}  EXPECTED RESULT", "-" * (w0 + w1 + 40)]
    out += [f"{a:<{w0}} {b:<{w1}}  {c}" for a, b, c in rows]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--no-pipeline", action="store_true", help="skip running the pipeline on the seeded applications")
    args = ap.parse_args()
    t0 = time.time()
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    world = build_world(args.seed, rules)
    out = build(world, rules, STORAGE_DIR / "files", args.seed)
    answer, registry = out["answer"], out["registry"]
    (ROOT / "data" / "answer_key.json").write_text(json.dumps(answer, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "data" / "mock_registry.json").write_text(json.dumps(registry, indent=1), encoding="utf-8")

    counts = load_db(answer, world, args.seed) if not args.no_db else {}
    n_files = sum(len(a["documents"]) for a in answer["applications"] + answer["last_year_applications"])
    scans = [(a["id"], d["file"]) for a in answer["applications"] for d in a["documents"] if d["kind"] == "scan"]
    types = {}
    for d in answer["defects"]:
        types[d["type"]] = types.get(d["type"], 0) + 1
    best, close = sanity_photos(answer)

    print(f"\nSeeded in {time.time() - t0:.0f}s  (seed {args.seed})  {counts}")
    print(f"Files: {n_files}   image-only scans: {len(scans)}   clean applications: {sum(a['clean'] for a in answer['applications'])}")
    print(f"Planted defects: {len(answer['defects'])}  " + ", ".join(f"{k}={v}" for k, v in sorted(types.items())))
    print(f"Photo sanity: closest unplanted cross-institution pair has pHash distance {best} ({close} pair(s) within 6)")
    print(hero_table(answer))
    print("\nAnswer key: data/answer_key.json   Mock registry: data/mock_registry.json\n")
    if not args.no_db and not args.no_pipeline:
        print("Running the pipeline on all applications ...")
        from app.pipeline.run import run_all

        run_all()


if __name__ == "__main__":
    main()

"""Near-duplicate image evidence, two stages (thresholds in the rule file, twin: ...).

 stage 1  pHash distance <= hash_flag_max                       -> kind "copy"   (exact / edited copy)
 stage 2  pHash distance <= hash_candidate_max, then ORB keypoints + ratio test + RANSAC homography with
          inliers >= min_inliers                                -> kind "reshot" (same room, photographed again)
Both mean "Manual review required"; neither says anything about intent."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image

from ..rules.loader import load_rules


def cfg() -> dict:
    return load_rules()["twin"]


def fingerprint(img: Image.Image) -> dict:
    return {"phash": str(imagehash.phash(img)), "dhash": str(imagehash.dhash(img)), "whash": str(imagehash.whash(img))}


def phash_distance(a: str, b: str) -> int:
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))


def _gray(path: str, max_side: int):
    g = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    s = max_side / max(g.shape)
    return cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else g


@lru_cache(maxsize=4096)
def _orb(path: str, n: int, max_side: int):
    kp, des = cv2.ORB_create(nfeatures=n).detectAndCompute(_gray(path, max_side), None)
    return [k.pt for k in kp], des


def _match(path_a: str, path_b: str, o: dict):
    (pa, da), (pb, db) = _orb(path_a, o["n_features"], o["max_side"]), _orb(path_b, o["n_features"], o["max_side"])
    if da is None or db is None or len(pa) < 8 or len(pb) < 8:
        return [], None, pa, pb
    knn = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    good = [m for m, *rest in knn if rest and m.distance < o["ratio"] * rest[0].distance]
    if len(good) < 4:
        return good, None, pa, pb
    src = np.float32([pa[m.queryIdx] for m in good]).reshape(-1, 1, 2)
    dst = np.float32([pb[m.trainIdx] for m in good]).reshape(-1, 1, 2)
    _, mask = cv2.findHomography(src, dst, cv2.RANSAC, o["ransac_px"])
    return good, mask, pa, pb


_cache: dict[tuple, dict] = {}


def orb_verify(path_a: str | Path, path_b: str | Path, c: dict | None = None) -> dict:
    """{good, inliers, pass}; symmetric, so results are cached per unordered pair."""
    o = (c or cfg())["orb"]
    key = (tuple(sorted((str(path_a), str(path_b)))), o["n_features"], o["max_side"], o["ratio"], o["ransac_px"])
    if key not in _cache:
        good, mask, _, _ = _match(str(path_a), str(path_b), o)
        inl = int(mask.sum()) if mask is not None else 0
        _cache[key] = {"good": len(good), "inliers": inl}
    r = _cache[key]
    return {**r, "pass": r["inliers"] >= o["min_inliers"]}


STAGE2_TYPES = ("lab_photo", "building_photo")


def orb_applies(type_a: str, type_b: str) -> bool:
    """Keypoint stage only compares like with like (lab photo vs lab photo, building vs building); video frames use stage 1 only."""
    return type_a == type_b and type_a in STAGE2_TYPES


def compare(phash_a: str, phash_b: str, path_a, path_b, c: dict | None = None, orb_ok: bool = True) -> dict:
    """Two-stage verdict for one pair of images from different institutions."""
    c = c or cfg()
    d = phash_distance(phash_a, phash_b)
    res = {"phash_distance": d, "orb": None, "kind": None, "twin": False}
    if d <= c["hash_flag_max"]:
        res.update(kind="copy", twin=True)
    elif orb_ok and d <= c["hash_candidate_max"]:
        res["orb"] = orb_verify(path_a, path_b, c)
        if res["orb"]["pass"]:
            res.update(kind="reshot", twin=True)
    return res


def draw_matches(path_a: str | Path, path_b: str | Path, max_lines: int = 70, height: int = 360) -> bytes:
    """Side-by-side PNG with the RANSAC-inlier keypoint matches drawn as lines."""
    c = cfg()["orb"]
    good, mask, pa, pb = _match(str(path_a), str(path_b), c)
    ga, gb = cv2.cvtColor(_gray(str(path_a), c["max_side"]), cv2.COLOR_GRAY2BGR), cv2.cvtColor(_gray(str(path_b), c["max_side"]), cv2.COLOR_GRAY2BGR)
    # colour the originals (grey keypoints image is only the geometry reference)
    ca = cv2.resize(cv2.imdecode(np.fromfile(str(path_a), dtype=np.uint8), cv2.IMREAD_COLOR), (ga.shape[1], ga.shape[0]))
    cb = cv2.resize(cv2.imdecode(np.fromfile(str(path_b), dtype=np.uint8), cv2.IMREAD_COLOR), (gb.shape[1], gb.shape[0]))
    inl = [m for m, k in zip(good, mask.ravel().tolist() if mask is not None else []) if k]
    inl = sorted(inl, key=lambda m: m.distance)[:max_lines]
    sa, sb = height / ca.shape[0], height / cb.shape[0]
    ca, cb = cv2.resize(ca, None, fx=sa, fy=sa), cv2.resize(cb, None, fx=sb, fy=sb)
    gap = 12
    canvas = np.full((height, ca.shape[1] + gap + cb.shape[1], 3), 255, np.uint8)
    canvas[:, : ca.shape[1]], canvas[:, ca.shape[1] + gap:] = ca, cb
    rng = np.random.default_rng(1)
    for m in inl:
        x1, y1 = pa[m.queryIdx][0] * sa, pa[m.queryIdx][1] * sa
        x2, y2 = pb[m.trainIdx][0] * sb + ca.shape[1] + gap, pb[m.trainIdx][1] * sb
        col = tuple(int(v) for v in rng.integers(60, 230, 3))
        cv2.line(canvas, (int(x1), int(y1)), (int(x2), int(y2)), col, 1, cv2.LINE_AA)
        cv2.circle(canvas, (int(x1), int(y1)), 3, col, -1, cv2.LINE_AA)
        cv2.circle(canvas, (int(x2), int(y2)), 3, col, -1, cv2.LINE_AA)
    ok, png = cv2.imencode(".png", canvas)
    return png.tobytes()

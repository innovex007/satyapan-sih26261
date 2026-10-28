"""Synthetic room / building photos drawn with Pillow. A layout dict fully determines a room,
so the "twin" photo is the same layout with a small crop and brightness change."""
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1280, 960


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _light(rng: random.Random) -> list:
    """Random low-frequency lighting (window light, shadows). Part of the layout so copies of a room share it."""
    return [(rng.uniform(0.3, 1.6), rng.uniform(0.3, 1.6), rng.uniform(0, 6.28), rng.uniform(0.05, 0.11), rng.choice([-1, 1]))
            for _ in range(3)]


def lab_layout(rng: random.Random) -> dict:
    hue = rng.choice([(205, 220, 232), (232, 222, 200), (214, 232, 214), (236, 214, 214), (222, 214, 236), (240, 236, 214), (200, 214, 222)])
    return {
        "kind": "lab",
        "wall": hue,
        "floor": rng.choice([(150, 140, 128), (118, 126, 138), (160, 150, 120), (128, 112, 100)]),
        "desk": rng.choice([(140, 100, 62), (92, 72, 56), (170, 150, 120), (70, 84, 96)]),
        "screen": rng.choice([(36, 60, 96), (20, 20, 24), (40, 90, 80), (90, 40, 60)]),
        "rows": rng.choice([2, 3, 4]),
        "cols": rng.choice([3, 4, 5, 6]),
        "windows": sorted(rng.sample([0.12, 0.3, 0.5, 0.7, 0.88], rng.choice([1, 2, 3]))),
        "board": rng.random() < 0.6,
        "sky": rng.choice([(150, 200, 235), (235, 205, 160), (190, 205, 225)]),
        "horizon": rng.uniform(0.38, 0.5),
        "light_bars": rng.choice([2, 3, 4]),
        "poster": rng.random() < 0.5,
        "cam_dx": rng.uniform(-0.04, 0.04),
        "light": _light(rng),
    }


def building_layout(rng: random.Random) -> dict:
    return {
        "kind": "building",
        "wall": rng.choice([(205, 190, 165), (190, 200, 210), (225, 215, 200), (170, 120, 100)]),
        "sky": rng.choice([(150, 200, 235), (220, 225, 235), (240, 210, 170)]),
        "floors": rng.choice([2, 3, 4]),
        "bays": rng.choice([4, 5, 6]),
        "trees": [rng.uniform(0.04, 0.96) for _ in range(rng.choice([2, 3, 4]))],
        "door": rng.choice([0, 1, 2]),
        "flag": rng.random() < 0.6,
        "light": _light(rng),
    }


def _grad(draw, box, top, bot):
    x0, y0, x1, y1 = box
    for y in range(int(y0), int(y1)):
        t = (y - y0) / max(1, (y1 - y0))
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        draw.line([(x0, y), (x1, y)], fill=c)


_VIG = {}


def _finish(img: Image.Image, rng: random.Random, vignette=0.28, light=()) -> Image.Image:
    if vignette not in _VIG:
        yy, xx = np.mgrid[0:H, 0:W]
        d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        _VIG[vignette] = (1 - vignette * np.clip(d - 0.4, 0, 1)).astype(np.float32)[..., None]
    a = np.asarray(img, dtype=np.float32) * _VIG[vignette]
    if light:
        gx, gy = np.meshgrid(np.linspace(0, 1, 80, dtype=np.float32), np.linspace(0, 1, 60, dtype=np.float32))
        small = sum(amp * sgn * np.cos(2 * np.pi * (fx * gx + fy * gy) + ph) for fx, fy, ph, amp, sgn in light)
        field = np.asarray(Image.fromarray(small.astype(np.float32), "F").resize((W, H), Image.BILINEAR))
        a *= (1 + field)[..., None]
    a += np.random.default_rng(rng.randint(0, 10**6)).standard_normal(a.shape, dtype=np.float32) * 3.0
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))


def render_lab(L: dict, seed: int = 0, pan: float = 0.0) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (W, H), L["wall"])
    d = ImageDraw.Draw(img)
    hy = int(H * L["horizon"] + 120)
    _grad(d, (0, 0, W, hy), _shade(L["wall"], 1.05), _shade(L["wall"], 0.86))
    _grad(d, (0, hy, W, H), _shade(L["floor"], 0.8), _shade(L["floor"], 1.12))
    off = int((L["cam_dx"] + pan) * W)
    # ceiling light bars
    for i in range(L["light_bars"]):
        x = int(W * (i + 0.5) / L["light_bars"]) + off // 3
        d.rectangle([x - 90, 22, x + 90, 40], fill=(250, 250, 240))
    # windows on the back wall
    for wx in L["windows"]:
        x = int(W * wx) + off
        d.rectangle([x - rng.randint(50, 80), rng.randint(70, 110), x + rng.randint(50, 80), hy - rng.randint(70, 110)], fill=L["sky"], outline=(235, 235, 235), width=rng.randint(4, 10))
        d.line([x, 90, x, hy - 90], fill=(235, 235, 235), width=6)
        d.line([x - 70, (hy) // 2, x + 70, hy // 2], fill=(235, 235, 235), width=6)
    if L["board"]:
        d.rectangle([W * 0.36 + off, hy * 0.42, W * 0.64 + off, hy * 0.78], fill=(244, 246, 244), outline=(120, 120, 120), width=6)
        for k in range(3):
            d.line([W * 0.39 + off, hy * (0.5 + 0.07 * k), W * (0.5 + 0.06 * k) + off, hy * (0.5 + 0.07 * k)], fill=(60, 80, 160), width=3)
    if L["poster"]:
        d.rectangle([W * 0.04 + off, hy * 0.35, W * 0.1 + off, hy * 0.7], fill=(220, 90, 70))
    # desk rows from far to near, each in perspective
    R, C = L["rows"], L["cols"]
    for r in range(R):
        t = (r + 1) / R
        s = 0.42 + 0.58 * t
        y = hy + (H - hy - 90) * t ** 1.15
        dw, dh = 140 * s + 60 * s * (6 - C) / 4, 38 * s
        for c in range(C):
            cx = W * (c + 0.5) / C + off * s
            top, bot = y - dh, y
            d.polygon([(cx - dw / 2, bot), (cx + dw / 2, bot), (cx + dw / 2 - 6 * s, top), (cx - dw / 2 + 6 * s, top)], fill=_shade(L["desk"], rng.uniform(0.85, 1.12)))
            if rng.random() < 0.5:
                d.rectangle([cx + rng.uniform(-0.4, 0.2) * dw, top - rng.uniform(6, 22) * s, cx + rng.uniform(0.25, 0.45) * dw, top - 2 * s], fill=_shade(L["wall"], rng.uniform(0.5, 1.2)))
            d.rectangle([cx - dw / 2, bot, cx + dw / 2, bot + 9 * s], fill=_shade(L["desk"], 0.7))
            mw, mh = dw * rng.uniform(0.34, 0.56), dh * rng.uniform(1.05, 1.6)
            d.rectangle([cx - mw / 2, top - mh, cx + mw / 2, top - 4 * s], fill=(28, 28, 30))
            d.rectangle([cx - mw / 2 + 4, top - mh + 4, cx + mw / 2 - 4, top - 8 * s], fill=L["screen"])
            d.rectangle([cx - 6 * s, top - 6 * s, cx + 6 * s, top], fill=(50, 50, 50))
            d.rectangle([cx - mw * 0.45, top + 3 * s, cx + mw * 0.45, top + 10 * s], fill=(190, 190, 195))
            if (r + c + seed) % 3 == 0:
                d.rectangle([cx + dw * 0.32, top - mh * 0.6, cx + dw * 0.45, top - 3 * s], fill=(70, 70, 76))
            d.ellipse([cx - 20 * s, bot + 14 * s, cx + 20 * s, bot + 40 * s], fill=_shade(L["desk"], 0.5))
    return _finish(img, rng, light=L["light"])


def render_building(L: dict, seed: int = 0) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    _grad(d, (0, 0, W, int(H * 0.62)), _shade(L["sky"], 0.9), _shade(L["sky"], 1.1))
    d.rectangle([0, int(H * 0.62), W, H], fill=(120, 134, 112))
    px = rng.uniform(0.38, 0.62)
    d.polygon([(W * (px - 0.2), H), (W * (px + 0.2), H), (W * (px + 0.08), H * 0.7), (W * (px - 0.08), H * 0.7)], fill=(150, 150, 150))
    bx0, bx1, by1 = W * rng.uniform(0.04, 0.16), W * rng.uniform(0.84, 0.96), H * rng.uniform(0.68, 0.76)
    fh = rng.randint(96, 136)
    by0 = by1 - fh * L["floors"]
    d.rectangle([bx0, by0, bx1, by1], fill=L["wall"], outline=_shade(L["wall"], 0.6), width=rng.randint(2, 6))
    d.rectangle([bx0 - 10, by0 - rng.randint(8, 24), bx1 + 10, by0], fill=_shade(L["wall"], 0.65))
    for _ in range(rng.randint(2, 7)):  # pilasters / wall panels at random places
        x = rng.uniform(bx0, bx1 - 30)
        d.rectangle([x, by0 + 4, x + rng.randint(8, 34), by1 - 2], fill=_shade(L["wall"], rng.uniform(0.82, 1.1)))
    bw = (bx1 - bx0) / L["bays"]
    ww, wh = rng.randint(22, max(25, int(bw * 0.4))), rng.randint(30, 52)
    fr = rng.randint(2, 6)
    for f in range(L["floors"]):
        for b in range(L["bays"]):
            x = bx0 + bw * (b + 0.5) + rng.randint(-6, 6)
            y = by0 + fh * f + rng.randint(16, 34)
            if f == L["floors"] - 1 and b == L["door"] + 1:
                dw = rng.randint(24, 40)
                d.rectangle([x - dw, by1 - rng.randint(70, 100), x + dw, by1], fill=(rng.randint(50, 90), rng.randint(40, 60), 40))
            else:
                glass = tuple(max(0, min(255, c + rng.randint(-35, 35))) for c in (95, 130, 160))
                d.rectangle([x - ww, y, x + ww, y + wh], fill=glass, outline=(rng.randint(200, 250),) * 3, width=fr)
                if rng.random() < 0.4:
                    d.line([x, y, x, y + wh], fill=(235, 235, 235), width=2)
    sx = bx0 + rng.randint(20, 160)
    d.rectangle([sx, by0 + rng.randint(4, 14), sx + rng.randint(120, 330), by0 + rng.randint(26, 44)], fill=(rng.randint(20, 120), rng.randint(40, 90), rng.randint(60, 140)))
    for tx in L["trees"]:
        x = W * tx
        tw, tr = rng.randint(4, 10), rng.randint(30, 62)
        d.rectangle([x - tw, by1 - 20, x + tw, by1 + 40], fill=(90, 62, 40))
        d.ellipse([x - tr, by1 - 120 + rng.randint(-10, 10), x + tr, by1 - 10], fill=(rng.randint(40, 70), rng.randint(95, 130), rng.randint(45, 75)))
    if L["flag"]:
        fx = bx1 - rng.randint(30, 140)
        d.line([fx, by0 - 120, fx, by0 - 14], fill=(90, 90, 90), width=5)
        d.rectangle([fx + 4, by0 - 120, fx + rng.randint(36, 70), by0 - rng.randint(70, 95)], fill=(rng.randint(180, 240), rng.randint(90, 160), rng.randint(20, 70)))
    return _finish(img, rng, vignette=0.2, light=L["light"])


def derive_twin(img: Image.Image, crop: float = 0.012, brightness: float = 1.06, seed: int = 0) -> Image.Image:
    """Same room, slightly re-framed and brightened: what a reused photo looks like."""
    w, h = img.size
    dx, dy = int(w * crop), int(h * crop)
    out = img.crop((dx, dy, w - dx // 2, h - dy)).resize((w, h), Image.BILINEAR)
    a = np.asarray(out, dtype=np.float32) * brightness
    a += np.random.default_rng(seed).standard_normal(a.shape, dtype=np.float32) * 2.0
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---- harder re-use edits -------------------------------------------------------------------
import cv2  # noqa: E402

VARIANTS = {  # name -> design difficulty
    "bright_plus15": "easy", "bright_minus15": "easy", "jpeg_q60": "easy",
    "crop10": "medium", "resize70": "medium", "rotate2": "medium",
    "printed_photo": "hard",
}
VARIANT_JPEG_QUALITY = {"jpeg_q60": 60}


def _gain(img, g):
    return Image.fromarray(np.clip(np.asarray(img, dtype=np.float32) * g, 0, 255).astype(np.uint8))


def make_variant(img: Image.Image, name: str, seed: int = 0) -> Image.Image:
    w, h = img.size
    if name == "bright_plus15":
        return _gain(img, 1.15)
    if name == "bright_minus15":
        return _gain(img, 0.85)
    if name == "jpeg_q60":
        return img.copy()  # the damage happens when it is saved at quality 60
    if name == "crop10":  # 10% of the frame removed (5% per side), scaled back up
        dx, dy = int(w * 0.05), int(h * 0.05)
        return img.crop((dx, dy, w - dx, h - dy)).resize((w, h), Image.BICUBIC)
    if name == "resize70":
        return img.resize((int(w * 0.7), int(h * 0.7)), Image.LANCZOS)
    if name == "rotate2":
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 2.0, 1.0)
        return Image.fromarray(cv2.warpAffine(np.asarray(img), m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE))
    if name == "printed_photo":  # a photo of a printed copy: perspective, table around it, blur, glare, dimmer
        rng = np.random.default_rng(seed)
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        cw, ch = int(w * 1.2), int(h * 1.2)
        jit = lambda m: rng.uniform(-m, m)  # noqa: E731
        dst = np.float32([[cw * (0.09 + jit(0.02)), ch * (0.1 + jit(0.02))], [cw * (0.92 + jit(0.02)), ch * (0.07 + jit(0.02))],
                          [cw * (0.9 + jit(0.02)), ch * (0.93 + jit(0.02))], [cw * (0.07 + jit(0.02)), ch * (0.9 + jit(0.02))]])
        table = np.full((ch, cw, 3), (118, 98, 80), np.uint8)
        table = cv2.add(table, rng.integers(0, 14, table.shape, dtype=np.uint8))
        warped = cv2.warpPerspective(np.asarray(img), cv2.getPerspectiveTransform(src, dst), (cw, ch), borderMode=cv2.BORDER_CONSTANT)
        mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), cv2.getPerspectiveTransform(src, dst), (cw, ch))
        out = np.where(mask[..., None] > 0, (warped * 0.9).astype(np.uint8), table)
        yy, xx = np.mgrid[0:ch, 0:cw]
        glare = np.exp(-(((xx - cw * 0.7) / (cw * 0.25)) ** 2 + ((yy - ch * 0.3) / (ch * 0.2)) ** 2))[..., None] * 38
        out = np.clip(out.astype(np.float32) + glare * (mask[..., None] > 0), 0, 255).astype(np.uint8)
        out = cv2.GaussianBlur(out, (0, 0), 1.6)
        return Image.fromarray(out).resize((w, h), Image.BICUBIC)
    raise ValueError(name)

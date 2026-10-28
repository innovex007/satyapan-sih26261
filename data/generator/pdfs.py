"""Synthetic PDFs (reportlab) with exact bbox capture, QR codes, digital signatures (pyHanko),
incremental edit-after-signing, and image-only 'scans'. Everything carries a SPECIMEN watermark."""
import io
import json
import random
from functools import lru_cache
from datetime import datetime
from pathlib import Path

import numpy as np
import pikepdf
import pypdfium2 as pdfium
import qrcode
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from PIL import Image, ImageFilter
from reportlab import rl_config
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .world import fmt  # noqa: E402

rl_config.useA85 = 0  # keep content streams as readable bytes (needed for the incremental edit)

W, H = A4
HERE = Path(__file__).parent
DEVANAGARI = HERE / "fonts" / "NotoSansDevanagari-Regular.ttf"
WATERMARK = "SPECIMEN – SYNTHETIC"
X_LABEL, X_VALUE = 60, 235


def norm_value(key: str, value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if key == "land_area_acres":
        return f"{float(value):.2f}"
    return str(value).strip().lower()


class Sheet:
    """One document being drawn. Records every fact with a normalised top-left bbox."""

    def __init__(self, title: str, issuer: str, producer="Demo Doc Generator 1.0", creator="Satyapan Synthetic Generator"):
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4, pageCompression=0)
        self.c.setTitle(title)
        self.c.setAuthor(issuer)
        self.c.setCreator(creator)
        self.c.setProducer(producer)
        self.facts: list[dict] = []
        self.page = 1
        self.y = H - 150
        self._page_start()
        self._header(issuer, title)

    # -- page furniture
    def _watermark(self):
        c = self.c
        c.saveState()
        c.setFillColorRGB(0.91, 0.91, 0.91)
        c.setFont("Helvetica-Bold", 44)
        c.translate(W / 2, H / 2)
        c.rotate(40)
        c.drawCentredString(0, 0, WATERMARK)
        c.restoreState()

    def _page_start(self):
        self._watermark()

    def _header(self, issuer, title):
        c = self.c
        c.setFillColorRGB(0.94, 0.95, 0.97)
        c.rect(0, H - 90, W, 90, stroke=0, fill=1)
        c.setFillColorRGB(0.12, 0.2, 0.35)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(X_LABEL, H - 42, issuer)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.setFont("Helvetica", 8)
        c.drawString(X_LABEL, H - 58, "Fictional issuer · specimen document for software testing only")
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(W / 2, H - 120, title.upper())
        self.y = H - 165

    def footer(self, text="SPECIMEN – SYNTHETIC · not an official document"):
        self.c.setFillColorRGB(0.5, 0.5, 0.5)
        self.c.setFont("Helvetica", 8)
        self.c.drawCentredString(W / 2, 28, f"{text} · page {self.page}")

    def new_page(self):
        self.footer()
        self.c.showPage()
        self.page += 1
        self._page_start()
        self.y = H - 80

    # -- content
    def _record(self, key, value, x, baseline, font, size, page=None, norm=None):
        w = stringWidth(str(value), font, size)
        top, bottom = baseline + size * 0.82 + 1.5, baseline - size * 0.24 - 1.5
        bbox = [round((x - 1.5) / W, 4), round(1 - top / H, 4), round((x + w + 1.5) / W, 4), round(1 - bottom / H, 4)]
        self.facts.append({"key": key, "value": str(value), "normalised": norm if norm is not None else norm_value(key, value),
                           "page": page or self.page, "bbox": bbox})

    def field(self, label, value, key=None, font="Helvetica", size=10, gap=26, display=None):
        c = self.c
        shown = display if display is not None else value
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont("Helvetica", 9)
        c.drawString(X_LABEL, self.y, label)
        c.setFillColorRGB(0.05, 0.05, 0.05)
        c.setFont(font, size)
        c.drawString(X_VALUE, self.y, str(shown))
        if key:
            self._record(key, shown, X_VALUE, self.y, font, size, norm=norm_value(key, value))
        self.y -= gap

    def para(self, text, size=10, gap=15, width=470, x=X_LABEL, font="Helvetica"):
        self.c.setFont(font, size)
        self.c.setFillColorRGB(0.15, 0.15, 0.15)
        line = ""
        for word in text.split():
            if stringWidth(line + " " + word, font, size) > width:
                self.c.drawString(x, self.y, line.strip())
                self.y -= gap
                line = word
            else:
                line += " " + word
        if line:
            self.c.drawString(x, self.y, line.strip())
            self.y -= gap

    def gap(self, n):
        self.y -= n

    def qr(self, payload: dict, x=W - 150, y=70, size=88):
        img = qrcode.make(json.dumps(payload, separators=(",", ":")), box_size=6, border=2).convert("RGB")
        self.c.drawImage(ImageReader(img), x, y, size, size)
        self.c.setFont("Helvetica", 7)
        self.c.setFillColorRGB(0.4, 0.4, 0.4)
        self.c.drawString(x, y - 9, "Scan to verify (specimen QR)")

    def signature_box(self, label="Authorised signatory"):
        self.c.setStrokeColorRGB(0.6, 0.6, 0.6)
        self.c.setDash(3, 3)
        self.c.rect(X_LABEL, 80, 200, 50, stroke=1, fill=0)
        self.c.setDash()
        self.c.setFont("Helvetica", 8)
        self.c.setFillColorRGB(0.45, 0.45, 0.45)
        self.c.drawString(X_LABEL + 6, 70, f"{label} (digital signature field)")

    def finish(self) -> bytes:
        self.footer()
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()


# ---------------------------------------------------------------------------------------------
# Hindi page: text shaped with HarfBuzz and drawn as vector outlines, so conjuncts/matras are correct
class _Pen(BasePen):
    def __init__(self, glyphset, path, scale, ox, oy):
        super().__init__(glyphset)
        self.p, self.s, self.ox, self.oy = path, scale, ox, oy

    def _pt(self, pt):
        return self.ox + pt[0] * self.s, self.oy + pt[1] * self.s

    def _moveTo(self, pt):
        self.p.moveTo(*self._pt(pt))

    def _lineTo(self, pt):
        self.p.lineTo(*self._pt(pt))

    def _curveToOne(self, a, b, c):
        self.p.curveTo(*self._pt(a), *self._pt(b), *self._pt(c))

    def _closePath(self):
        self.p.close()


_hb = {}


def draw_devanagari(c, text, x, y, size=13):
    if not _hb:
        face = hb.Face(hb.Blob.from_file_path(str(DEVANAGARI)))
        _hb.update(face=face, font=hb.Font(face), tt=TTFont(str(DEVANAGARI)))
        _hb["gs"] = _hb["tt"].getGlyphSet()
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(_hb["font"], buf, {})
    scale = size / _hb["face"].upem
    path = c.beginPath()
    cx = x
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = _hb["tt"].getGlyphName(info.codepoint)
        _hb["gs"][name].draw(_Pen(_hb["gs"], path, scale, cx + pos.x_offset * scale, y + pos.y_offset * scale))
        cx += pos.x_advance * scale
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawPath(path, stroke=0, fill=1, fillMode=1)
    return cx - x


def hindi_block(lines, width=470, lh=28, size=14):
    """Devanagari lines (HarfBuzz-shaped) rasterised to a transparent image, so the Hindi page is image-only like a scan."""
    import io as _io
    buf = _io.BytesIO()
    h = lh * len(lines) + 16
    c = canvas.Canvas(buf, pagesize=(width, h), pageCompression=0)
    widths = []
    for i, line in enumerate(lines):
        widths.append(draw_devanagari(c, line, 0, h - 8 - lh * (i + 1) + 8, size))
    c.showPage()
    c.save()
    gray = pdfium.PdfDocument(buf.getvalue())[0].render(scale=200 / 72).to_pil().convert("L")
    rgba = Image.new("RGBA", gray.size, (25, 25, 25, 0))
    rgba.putalpha(gray.point(lambda v: 255 - v))
    return rgba, widths, lh


HINDI_LINES = [
    "घोषणा (नमूना – काल्पनिक दस्तावेज़)",
    "मैं एतद्द्वारा घोषित करता/करती हूँ कि इस आवेदन में",
    "दी गई सभी जानकारी मेरी जानकारी के अनुसार सत्य है।",
    "संस्था के पास सभी आवश्यक प्रमाण-पत्र उपलब्ध हैं।",
]


# ---------------------------------------------------------------------------------------------
def build_pdf(doc_type: str, t: dict, opts: dict) -> dict:
    """Return {'bytes', 'facts', 'pages', 'qr', 'issuer'} for one text-layer document."""
    fn = BUILDERS[doc_type]
    return fn(t, opts)


def _done(sheet: Sheet, **extra) -> dict:
    data = sheet.finish()
    return {"bytes": data, "facts": sheet.facts, "pages": sheet.page, **extra}


def d_land_deed(t, o):
    s = Sheet("Lease deed", f"Demo Sub-Registrar Office, {t['district']}")
    s.field("Institution (lessee)", t["institution_name"], "institution_name")
    s.field("Survey number", t["survey_no"], "survey_no")
    s.field("Village", t["town"], "village")
    s.field("Land area", t["deed_area"], "land_area_acres", display=f"{t['deed_area']:.2f} acres")
    s.field("Property address", t["address"], "address", size=9)
    s.field("Deed date", t["deed_date"], "deed_date", display=t["deed_date_s"])
    s.field("Registration no.", f"REG/{t['serial']:04d}/{t['deed_date'].year}")
    s.gap(10)
    s.para("This deed of lease is made between the lessor and the lessee named above for the purpose of establishing a technical "
           "educational institution on the land described herein, for a term of thirty years.")
    s.signature_box("Registrar")
    return _done(s, issuer="Demo Sub-Registrar Office")


def d_building_plan(t, o):
    s = Sheet("Sanctioned building plan", f"Demo Town Planning Authority, {t['district']}")
    s.field("Institution", t["institution_name"], "institution_name")
    s.field("Survey number", t["survey_no"], "survey_no")
    s.field("Village", t["town"], "village")
    s.field("Plot area", t["plan_area"], "land_area_acres", display=f"{t['plan_area']:.2f} acres")
    s.field("Built-up area", t["built_up_sqm"], "built_up_sqm", display=f"{t['built_up_sqm']} sq. m")
    s.field("Site address", t["address"], "address", size=9)
    s.field("Approval date", t["plan_date"], "approval_date", display=fmt(t["plan_date"]))
    s.gap(10)
    s.para("Sanctioned plan showing academic block, laboratories, administrative block and parking as per norms. "
           "Drawing is schematic and fictional.")
    c = s.c
    c.setStrokeColorRGB(0.5, 0.5, 0.55)
    c.rect(X_LABEL, 220, 300, 170, stroke=1, fill=0)
    c.rect(X_LABEL + 20, 250, 120, 80, stroke=1, fill=0)
    c.rect(X_LABEL + 170, 250, 100, 80, stroke=1, fill=0)
    return _done(s, issuer="Demo Town Planning Authority")


def d_occupancy(t, o):
    s = Sheet("Occupancy certificate", f"Demo Municipal Corporation, {t['district']}")
    s.field("Certificate no.", t["oc_no"], "certificate_no")
    s.field("Institution", t["institution_name"], "institution_name")
    s.field("Issue date", t["oc_date"], "issue_date", display=fmt(t["oc_date"]))
    s.field("Built-up area", t["built_up_sqm"], "built_up_sqm", display=f"{t['built_up_sqm']} sq. m")
    s.field("Address", t["address"], "address", size=9)
    s.gap(8)
    s.para("It is certified that the building has been completed as per the sanctioned plan and is fit for occupation.")
    payload = {"certificate_no": t["oc_no"], "institution": t["institution_name"], "issue_date": t["oc_date"].isoformat()}
    if o.get("qr_field"):
        payload["certificate_no"] = t["oc_no"][:-1] + ("0" if t["oc_no"][-1] != "0" else "1")
    s.qr(payload)
    return _done(s, issuer=f"Demo Municipal Corporation, {t['district']}", qr=payload)


def d_fire_noc(t, o):
    s = Sheet("Fire safety no-objection certificate", f"Demo Fire Services Department, {t['district']}")
    s.field("NOC number", t["fire_no"], "noc_number")
    s.field("Institution", t["institution_name"], "institution_name")
    s.field("Valid from", t["fire_from"], "valid_from", display=fmt(t["fire_from"]))
    s.field("Valid till", t["fire_till"], "valid_till", display=fmt(t["fire_till"]))
    s.field("Premises", t["address"], "address", size=9)
    s.gap(8)
    s.para("No objection is granted from the fire-safety standpoint for the premises described above, subject to periodic inspection.")
    payload = {"noc_no": t["fire_no"], "valid_till": t["fire_till"].isoformat(), "institution": t["institution_name"]}
    if o.get("qr_field") == "valid_till":
        payload["valid_till"] = o["qr_value"].isoformat()
    elif o.get("qr_field") == "noc_no":
        payload["noc_no"] = t["fire_no"][:-1] + ("0" if t["fire_no"][-1] != "0" else "1")
    s.qr(payload)
    return _done(s, issuer=f"Demo Fire Services Department, {t['district']}", qr=payload)


def d_university_noc(t, o):
    s = Sheet("Affiliation no-objection certificate", "Demo State University, Office of the Registrar")
    s.field("NOC number", t["univ_no"], "noc_number")
    s.field("Institution", t["institution_name"], "institution_name")
    s.field("Sanctioned intake", t["intake"], "intake")
    s.field("Valid till", t["univ_till"], "valid_till", display=fmt(t["univ_till"]))
    s.gap(8)
    s.para("The university has no objection to the grant of approval to the institution named above for the programmes listed.")
    payload = {"noc_no": t["univ_no"], "valid_till": t["univ_till"].isoformat(), "institution": t["institution_name"]}
    if o.get("qr_field") == "valid_till":
        payload["valid_till"] = (t["univ_till"].replace(year=t["univ_till"].year - 1)).isoformat()
    elif o.get("qr_field") == "noc_no":
        payload["noc_no"] = t["univ_no"][:-1] + ("0" if t["univ_no"][-1] != "0" else "1")
    s.qr(payload)
    return _done(s, issuer="Demo State University, Office of the Registrar", qr=payload)


def d_affidavit(t, o):
    edited = o.get("edited_date")
    s = Sheet("Affidavit", f"Before the Notary Public (specimen), {t['district']}")
    s.c.setFont("Courier", 9)  # monospaced reference line: puts Courier in the font table of every render
    s.c.setFillColorRGB(0.3, 0.3, 0.3)
    s.c.drawString(X_LABEL, s.y + 10, f"Ref: AFF/{t['serial']:04d}/{t['aff_date'].year}")
    s.gap(14)
    s.field("Institution", t["institution_name"], "institution_name")
    s.field("Deponent (signatory)", t["signatory"], "signatory")
    date_val = edited or t["aff_date"]
    if edited:
        s.field("Date of affidavit", date_val, "affidavit_date", font="Courier", size=11, display=fmt(date_val))
    else:
        s.field("Date of affidavit", date_val, "affidavit_date", display=fmt(date_val))
    s.gap(8)
    s.para("I, the deponent, solemnly affirm and declare that the information furnished in this application is true and correct, "
           "that the institution possesses the infrastructure stated, and that no material fact has been concealed.")
    s.signature_box("Deponent")
    if o.get("hindi"):
        s.new_page()
        s.c.setFont("Helvetica-Bold", 11)
        s.c.setFillColorRGB(0.1, 0.1, 0.1)
        s.c.drawString(X_LABEL, H - 100, "Hindi declaration (page 2)")
        img, widths, lh = hindi_block(HINDI_LINES)
        bw, bh = 470, lh * len(HINDI_LINES) + 16
        ytop = H - 130
        s.c.drawImage(ImageReader(img), X_LABEL, ytop - bh, bw, bh, mask="auto")
    return _done(s, issuer="Notary (specimen)")


def d_faculty(t, o):
    s = Sheet("Faculty list", f"{t['institution_name']}")
    s.field("Institution", t["institution_name"], "institution_name", gap=22)
    s.field("Session", "2026-27", gap=26)
    c = s.c
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    for x, h in ((X_LABEL, "S.No."), (X_LABEL + 40, "Name"), (X_LABEL + 230, "Faculty ID"), (X_LABEL + 330, "Designation")):
        c.drawString(x, s.y, h)
    s.y -= 20
    for i, f in enumerate(t["faculty"], 1):
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.drawString(X_LABEL, s.y, str(i))
        c.drawString(X_LABEL + 40, s.y, f["name"])
        c.drawString(X_LABEL + 330, s.y, f["designation"])
        c.drawString(X_LABEL + 230, s.y, f["id"])
        s._record("faculty_id", f["id"], X_LABEL + 230, s.y, "Helvetica", 9)
        s.y -= 22
    return _done(s, issuer=t["institution_name"])


def d_fee(t, o):
    s = Sheet("Processing fee receipt", f"Demo Bank of Commerce, Branch {t['district']}")
    s.field("Receipt no.", t["fee_no"], "receipt_no")
    s.field("Paid by", t["institution_name"], "institution_name")
    s.field("Amount paid", t["fee_amount"], "amount", display=f"Rs. {t['fee_amount']:,}")
    s.field("Date", t["fee_date"], "receipt_date", display=fmt(t["fee_date"]))
    s.field("Purpose", "Application processing fee 2026-27")
    return _done(s, issuer="Demo Bank of Commerce")


def d_land_use(t, o):
    issuer = t["luc_issuer"]
    s = Sheet("Land-use conversion certificate", issuer)
    s.field("Certificate no.", t["luc_no"], "certificate_no")
    s.field("Institution", t["institution_name"], "institution_name")
    s.field("Survey number", t["survey_no"], "survey_no")
    s.field("Village", t["town"], "village")
    s.field("Land area", t["land_area_acres"], "land_area_acres", display=f"{t['land_area_acres']:.2f} acres")
    s.field("Converted to", "Educational use (non-agricultural)")
    s.field("Issue date", t["luc_date"], "issue_date", display=fmt(t["luc_date"]))
    s.field("Issuer", issuer, "issuer", size=9)
    s.gap(8)
    s.para("The land described above has been converted from agricultural to educational use under the applicable land-revenue rules.")
    return _done(s, issuer=issuer)



BUILDERS = {
    "land_deed": d_land_deed, "building_plan": d_building_plan, "occupancy_cert": d_occupancy, "fire_noc": d_fire_noc,
    "university_noc": d_university_noc, "affidavit": d_affidavit, "faculty_list": d_faculty, "fee_receipt": d_fee,
    "land_use_cert": d_land_use,
}


# ---------------------------------------------------------------------------------------------
# Digital signatures and tampering
@lru_cache(maxsize=1)
def _signer():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from pyhanko.sign import signers

    cache = HERE / ".cache"
    cache.mkdir(exist_ok=True)
    kp, cp = cache / "demo_signer_key.pem", cache / "demo_signer_cert.pem"
    if not (kp.exists() and cp.exists()):
        key = rsa.generate_private_key(65537, 2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Demo Signatory (synthetic, self-signed)")])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(datetime(2026, 1, 1)).not_valid_after(datetime(2031, 1, 1))
                .sign(key, hashes.SHA256()))
        kp.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        cp.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return signers.SimpleSigner.load(str(kp), str(cp))


def sign_pdf(data: bytes) -> bytes:
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers

    out = signers.PdfSigner(signers.PdfSignatureMetadata(field_name="Signature1"), signer=_signer()).sign_pdf(
        IncrementalPdfFileWriter(io.BytesIO(data)))
    return out.getvalue()


def edit_after_signing(signed: bytes, edited_pdf: bytes, editor="Demo PDF Editor 3.2") -> bytes:
    """Incremental save that swaps page-1 content for the edited render (same font table)."""
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    with pikepdf.open(io.BytesIO(edited_pdf)) as pk:
        new_content = pk.pages[0].Contents.read_bytes()
    w = IncrementalPdfFileWriter(io.BytesIO(signed))
    page = w.root["/Pages"]["/Kids"][0].get_object()
    page["/Contents"] = w.add_object(generic.StreamObject(stream_data=new_content))
    w.update_container(page)
    w.set_info(generic.DictionaryObject({
        generic.NameObject("/Producer"): generic.TextStringObject(editor),
        generic.NameObject("/ModDate"): generic.TextStringObject("D:20260620101500+05'30'"),
    }))
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def tamper_signed(signed: bytes, old: str, new: str) -> bytes:
    """Flip content inside the signed byte range so the signature no longer verifies."""
    needle = f"({old})".encode()
    assert len(old) == len(new) and needle in signed
    return signed.replace(needle, f"({new})".encode(), 1)


# ---------------------------------------------------------------------------------------------
# Scans: rasterise -> skew/blur/noise -> wrap as an image-only PDF (no text layer)
def rasterise(pdf_bytes: bytes, dpi=200) -> Image.Image:
    return pdfium.PdfDocument(pdf_bytes)[0].render(scale=dpi / 72).to_pil().convert("L")


def make_scan(pdf_bytes: bytes, facts: list, seed: int, phone=False) -> tuple[bytes, list, dict]:
    rng = random.Random(seed)
    img = rasterise(pdf_bytes)
    w, h = img.size
    angle = rng.uniform(0.5, 1.4) * rng.choice([-1, 1])
    img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur(1.3 if phone else 0.7))
    a = np.asarray(img).astype(np.float32)
    a = a * rng.uniform(0.9, 0.97) + np.random.default_rng(seed).normal(0, 4 if phone else 2.5, a.shape)
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    # rotate the recorded bboxes with the page (PIL rotates counter-clockwise for positive angles)
    th = np.deg2rad(angle)
    cx, cy = w / 2, h / 2
    new = []
    for f in facts:
        x0, y0, x1, y1 = f["bbox"]
        pts = [(x * w, y * h) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        rp = [(cx + (x - cx) * np.cos(th) + (y - cy) * np.sin(th), cy - (x - cx) * np.sin(th) + (y - cy) * np.cos(th)) for x, y in pts]
        xs, ys = [p[0] for p in rp], [p[1] for p in rp]
        g = dict(f)
        g["bbox"] = [round(min(xs) / w, 4), round(min(ys) / h, 4), round(max(xs) / w, 4), round(max(ys) / h, 4)]
        new.append(g)

    b = io.BytesIO()
    jb = io.BytesIO()
    img.save(jb, "JPEG", quality=72 if phone else 82)
    c = canvas.Canvas(b, pagesize=A4, pageCompression=0)
    c.setProducer("Demo Scanner Firmware 2.1")
    c.setCreator("Demo MFP-3000 (phone camera)" if phone else "Demo MFP-3000")
    c.setTitle("Scanned document")
    c.drawImage(ImageReader(io.BytesIO(jb.getvalue())), 0, 0, W, H)
    c.showPage()
    c.save()
    return b.getvalue(), new, {"angle_deg": round(angle, 2), "phone_photo": phone, "dpi": 200}


def image_to_jpeg(img: Image.Image, quality: int = 88) -> bytes:
    b = io.BytesIO()
    img.save(b, "JPEG", quality=quality)
    return b.getvalue()

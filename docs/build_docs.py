"""Builds the three operation guides (操作説明書) as A4 PDFs.

1. Renders illustration images from the client's sample 納品書:
   before input (out/sample_processed.pdf) and after input (out/sample_processed_baked.pdf).
2. Prints each docs/src/*.html to docs/pdf/*.pdf with headless Microsoft Edge.

Run the tests first so both PDFs in out/ exist:
    python nohin_barcode.py 納品書_サンプル3枚.pdf --out out/sample_processed.pdf
    python tests/test_pdf_flow.py out/sample_processed.pdf     (writes out/sample_processed_baked.pdf)
Usage: python docs/build_docs.py
"""
import subprocess
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import layout as L  # noqa: E402

SRC = ROOT / "docs" / "src"
IMG = SRC / "img"
OUT = ROOT / "docs" / "pdf"
EDGE_PATHS = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]
GUIDES = ["操作説明書_発行担当者様", "操作説明書_仕入先様", "操作説明書_入荷担当者様"]

SCALE = 3
# Two strips (x0, top, x1, bottom, in PDF points) stacked into one illustration.
# They are kept tight on purpose: the guide goes to every supplier, so no
# company names, addresses, phone numbers or staff names may appear.
STRIPS = [
    (295, 218, 700, 316),   # 納品書: 納入日/納入数/発注残数, 部品番号, QR
    (295, 464, 520, 503),   # 受領書: 注番/納入数
]
STRIP_GAP = 8 * SCALE
RED = (220, 38, 38)


def render(pdf_path):
    doc = pdfium.PdfDocument(str(pdf_path))
    doc.init_forms()
    image = doc[0].render(scale=SCALE, may_draw_forms=True).to_pil().convert("RGB")
    doc.close()
    return image


def illustration(page_image, boxes):
    """Stacks the STRIPS of a rendered page and outlines `boxes` (PDF points) in red."""
    parts = []
    for strip in STRIPS:
        x0, top, x1, bottom = strip
        part = page_image.crop([x0 * SCALE, top * SCALE, x1 * SCALE, bottom * SCALE])
        draw = ImageDraw.Draw(part)
        for bx0, btop, bx1, bbottom, pad in boxes:
            if btop >= top and bbottom <= bottom:
                draw.rounded_rectangle(
                    [(bx0 - x0 - pad) * SCALE, (btop - top - pad) * SCALE,
                     (bx1 - x0 + pad) * SCALE, (bbottom - top + pad) * SCALE],
                    radius=4 * SCALE, outline=RED, width=2 * SCALE)
        parts.append(part)
    width = max(p.width for p in parts)
    height = sum(p.height for p in parts) + STRIP_GAP * (len(parts) - 1)
    out = Image.new("RGB", (width, height), "white")
    y = 0
    for p in parts:
        out.paste(p, (0, y))
        y += p.height + STRIP_GAP
    return out


def make_images():
    IMG.mkdir(parents=True, exist_ok=True)
    qty = (*L.NOHIN_QTY_BOX, 3)
    qr = (*L.QR_FREE_ZONE, 0)
    juryo = (*L.JURYO_QTY_BOX, 3)
    illustration(render(ROOT / "out" / "sample_processed.pdf"), [qty]).save(IMG / "before.png")
    illustration(render(ROOT / "out" / "sample_processed_baked.pdf"), [qty, qr, juryo]).save(IMG / "after.png")
    print("images:", IMG)


def edge():
    for path in EDGE_PATHS:
        if path.exists():
            return path
    sys.exit("Microsoft Edge not found")


def make_pdfs():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in GUIDES:
        html = SRC / f"{name}.html"
        pdf = OUT / f"{name}.pdf"
        subprocess.run([str(edge()), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", html.as_uri()], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("pdf:", pdf)


if __name__ == "__main__":
    make_images()
    make_pdfs()

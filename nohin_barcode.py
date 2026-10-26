"""Adds the 納入数 input field and a 2D barcode (QR) to a FileMaker 納品書 PDF.

Usage:
    nohin_barcode.exe <input.pdf> [--chuban YN34214] [--out output.pdf]

Without --out the input file is replaced in place, which is what the FileMaker
script uses. Each page gets:
  - qty_<p>    納品書 納入数 (digits only, entered by the supplier)
  - juryo_<p>  受領書 納入数 (read-only copy of qty_<p>)
  - qr_<p>_<i> 25 x 25 read-only cells that the document JavaScript turns
               black/transparent to draw the QR code "注番,納入数"
The QR is drawn by JavaScript in Acrobat Reader, because Acrobat's own barcode
field needs Reader Extensions rights that free Reader does not have.
"""

import argparse
import logging
import os
import re
import sys
import tempfile
from pathlib import Path

import pdfplumber
import pikepdf
from pikepdf import Array, Dictionary, Name, String

import layout as L

QR_MODULES = 25
QR_MODULE_PT = 2.0
# Dark cells are drawn slightly larger so adjacent cells leave no hairline seams.
QR_CELL_OVERLAP_PT = 0.15
QTY_MAX_DIGITS = 7
CHUBAN_PATTERN = re.compile(r"^[A-Z]{1,4}\d{3,10}$")

FIELD_FLAG_READ_ONLY = 1
ANNOT_FLAG_PRINT = 4

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent
QR_JS_PATH = BASE_DIR / "js" / "qr_v2m.js"

DRAW_JS = """
function ysQrDraw(doc, page, text) {
    var m = text ? qrV2M(text) : null;
    var r, c, f, want;
    for (r = 0; r < QR_SIZE; r++) {
        for (c = 0; c < QR_SIZE; c++) {
            f = doc.getField("qr_" + page + "_" + (r * QR_SIZE + c));
            if (f === null) continue;
            want = (m !== null && m[r][c]) ? color.black : color.transparent;
            if (!color.equal(f.fillColor, want)) f.fillColor = want;
        }
    }
}
"""

QTY_KEYSTROKE_JS = (
    "if (!event.willCommit) {"
    " event.rc = /^[0-9]*$/.test(event.change);"
    " if (!event.rc) app.beep(0);"
    "}"
)


class ProcessingError(Exception):
    pass


def pdf_rect(box, inset=0.0):
    """(x0, top, x1, bottom) from the top-left origin to a PDF [llx lly urx ury]."""
    x0, top, x1, bottom = box
    return Array([x0 + inset, L.PAGE_HEIGHT - bottom + inset, x1 - inset, L.PAGE_HEIGHT - top - inset])


def read_chuban(pdf_path):
    found = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            x0, top, x1, bottom = L.CHUBAN_TEXT_ZONE
            words = [w["text"] for w in page.extract_words()
                     if w["x0"] >= x0 and w["x1"] <= x1 and w["top"] >= top and w["bottom"] <= bottom]
            found.append(words[0] if len(words) == 1 else None)
    return found


def empty_appearance(pdf, rect):
    width = float(rect[2]) - float(rect[0])
    height = float(rect[3]) - float(rect[1])
    return pdf.make_stream(b"/Tx BMC EMC", Type=Name.XObject, Subtype=Name.Form,
                           BBox=Array([0, 0, width, height]))


def js_action(pdf, script):
    return Dictionary(S=Name.JavaScript, JS=pdf.make_stream(script.encode("utf-8")))


def text_field(pdf, page, name, rect, *, read_only=False, tooltip=None, extra=None):
    field = Dictionary(
        Type=Name.Annot, Subtype=Name.Widget, FT=Name.Tx, T=String(name),
        Rect=rect, F=ANNOT_FLAG_PRINT, P=page.obj,
        DA=String("/Helv 10 Tf 0 g"), Q=1, MaxLen=QTY_MAX_DIGITS,
        Ff=FIELD_FLAG_READ_ONLY if read_only else 0,
        MK=Dictionary(), BS=Dictionary(W=0),
        AP=Dictionary(N=empty_appearance(pdf, rect)),
    )
    if tooltip:
        field.TU = String(tooltip)
    if extra:
        for key, value in extra.items():
            field[key] = value
    return pdf.make_indirect(field)


def qr_cells(pdf, page, page_index):
    zx0, ztop, zx1, zbottom = L.QR_FREE_ZONE
    size = QR_MODULES * QR_MODULE_PT
    left = zx0 + (zx1 - zx0 - size) / 2
    top = ztop + (zbottom - ztop - size) / 2
    blank = None
    cells = []
    for r in range(QR_MODULES):
        for c in range(QR_MODULES):
            x0 = left + c * QR_MODULE_PT - QR_CELL_OVERLAP_PT / 2
            y_top = top + r * QR_MODULE_PT - QR_CELL_OVERLAP_PT / 2
            box = (x0, y_top, x0 + QR_MODULE_PT + QR_CELL_OVERLAP_PT, y_top + QR_MODULE_PT + QR_CELL_OVERLAP_PT)
            rect = pdf_rect(box)
            if blank is None:
                blank = pdf.make_indirect(empty_appearance(pdf, rect))
            cells.append(pdf.make_indirect(Dictionary(
                Type=Name.Annot, Subtype=Name.Widget, FT=Name.Btn, T=String(f"qr_{page_index}_{r * QR_MODULES + c}"),
                Ff=FIELD_FLAG_READ_ONLY | (1 << 16),  # read-only push button
                Rect=rect, F=ANNOT_FLAG_PRINT, P=page.obj,
                MK=Dictionary(BG=Array([])), BS=Dictionary(W=0),
                AP=Dictionary(N=blank),
            )))
    return cells


def add_fields(src, dst, chuban_override=None):
    chubans = read_chuban(src)
    with pikepdf.open(src) as pdf:
        if "/AcroForm" in pdf.Root:
            names = {str(f.get("/T", "")) for f in pdf.Root.AcroForm.get("/Fields", [])}
            if "qty_0" in names:
                logging.info("already processed, left unchanged: %s", src)
                return False
            raise ProcessingError("PDF already contains form fields from another source")

        if chuban_override is not None:
            if len(pdf.pages) != 1:
                raise ProcessingError("--chuban can only be used with a 1-page PDF")
            chubans = [chuban_override]

        fields, calc_order = [], []
        for i, page in enumerate(pdf.pages):
            if [float(v) for v in page.MediaBox] != [0, 0, L.PAGE_WIDTH, L.PAGE_HEIGHT]:
                raise ProcessingError(f"page {i + 1}: unexpected page size {list(page.MediaBox)}")
            chuban = chubans[i]
            if chuban is None or not CHUBAN_PATTERN.match(chuban):
                raise ProcessingError(f"page {i + 1}: 注番 not found or invalid ({chuban!r})")

            qty = text_field(pdf, page, f"qty_{i}", pdf_rect(L.NOHIN_QTY_BOX, inset=1),
                             tooltip="納入数を入力してください（半角数字）",
                             extra={"/AA": Dictionary(K=js_action(pdf, QTY_KEYSTROKE_JS))})
            calc = (f'var q = this.getField("qty_{i}").valueAsString.replace(/[^0-9]/g, "");'
                    f'event.value = q;'
                    f'ysQrDraw(this, {i}, q === "" ? "" : "{chuban}," + q);')
            juryo = text_field(pdf, page, f"juryo_{i}", pdf_rect(L.JURYO_QTY_BOX, inset=1), read_only=True,
                               extra={"/AA": Dictionary(C=js_action(pdf, calc))})
            cells = qr_cells(pdf, page, i)

            annots = page.obj.get("/Annots", Array([]))
            for f in [qty, juryo] + cells:
                annots.append(f)
            page.obj.Annots = annots
            fields.extend([qty, juryo] + cells)
            calc_order.append(juryo)
            logging.info("page %d: 注番 %s", i + 1, chuban)

        helv = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica,
                                            Encoding=Name.WinAnsiEncoding))
        pdf.Root.AcroForm = Dictionary(Fields=Array(fields), CO=Array(calc_order),
                                       DA=String("/Helv 10 Tf 0 g"), DR=Dictionary(Font=Dictionary(Helv=helv)))

        script = QR_JS_PATH.read_text(encoding="utf-8") + DRAW_JS
        names = pdf.Root.get("/Names", Dictionary())
        names.JavaScript = Dictionary(Names=Array([String("ysQr"), pdf.make_indirect(js_action(pdf, script))]))
        pdf.Root.Names = names
        pdf.save(dst, object_stream_mode=pikepdf.ObjectStreamMode.generate, compress_streams=True)
    return True


def process(src, out=None, chuban=None):
    src = Path(src)
    if out is not None:
        return add_fields(src, Path(out), chuban)
    # Write to a temp file first so a failure never leaves a broken PDF.
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=src.parent)
    os.close(fd)
    try:
        changed = add_fields(src, Path(tmp), chuban)
        if changed:
            os.replace(tmp, src)
        return changed
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def log_path():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "YukiSoft"
    path.mkdir(parents=True, exist_ok=True)
    return path / "nohin_barcode.log"


def show_error(message):
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "納品書バーコード追加エラー", 0x10)
    else:
        print(message, file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description="納品書PDFに納入数入力欄と2次元バーコードを追加します")
    parser.add_argument("pdf")
    parser.add_argument("--chuban", help="注番（省略時はPDFから読み取り）")
    parser.add_argument("--out", help="出力先（省略時は元のファイルを上書き）")
    args = parser.parse_args(argv)

    logging.basicConfig(filename=log_path(), level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        process(args.pdf, args.out, args.chuban)
        logging.info("done: %s", args.pdf)
        return 0
    except Exception as exc:
        logging.exception("failed: %s", args.pdf)
        show_error(f"納品書PDFへのバーコード追加に失敗しました。\nこのPDFは送付しないでください。\n\n"
                   f"ファイル: {args.pdf}\n内容: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

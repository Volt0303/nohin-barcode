"""End-to-end check of a processed PDF without Acrobat.

1. Extracts the embedded JavaScript and runs it in a mock Acrobat API
   (tests/acrobat_sim.js) with a quantity typed on each page.
2. Bakes the resulting dark QR cells and 受領書 value into a copy of the PDF.
3. Renders it at 300 dpi and decodes the QR code on each page with OpenCV.

Usage: python tests/test_pdf_flow.py out/sample_processed.pdf
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pikepdf
from pikepdf import Array, Dictionary, Name

HERE = Path(__file__).resolve().parent
INPUTS = {0: "10000", 1: "20000", 2: "1500"}
KEY_TESTS = ["1", "0", "123", "a", "-", "１", "１２３", "1.5", " "]
EXPECTED_KEYS = {"1": True, "0": True, "123": True, "１": True, "１２３": True}


def scripts(pdf):
    doc_js = pdf.Root.Names.JavaScript.Names[1].JS.read_bytes().decode("utf-8")
    keystroke, calcs, names = None, [], []
    for f in pdf.Root.AcroForm.Fields:
        name = str(f.T)
        names.append(name)
        if name == "qty_0":
            keystroke = f.AA.K.JS.read_bytes().decode("utf-8")
        if name.startswith("juryo_"):
            calcs.append({"page": int(name.split("_")[1]), "js": f.AA.C.JS.read_bytes().decode("utf-8")})
    return doc_js, keystroke, calcs, names


def bake(pdf, pages):
    """Draws what Acrobat would draw: filled dark cells and the 受領書 text."""
    by_name = {str(f.T): f for f in pdf.Root.AcroForm.Fields}
    for page, result in pages.items():
        for i in result["dark"]:
            f = by_name[f"qr_{page}_{i}"]
            w = float(f.Rect[2]) - float(f.Rect[0])
            h = float(f.Rect[3]) - float(f.Rect[1])
            f.AP = Dictionary(N=pdf.make_stream(f"0 g 0 0 {w} {h} re f".encode(), Type=Name.XObject,
                                                Subtype=Name.Form, BBox=Array([0, 0, w, h])))
        for prefix in ("qty", "juryo"):
            f = by_name[f"{prefix}_{page}"]
            w = float(f.Rect[2]) - float(f.Rect[0])
            h = float(f.Rect[3]) - float(f.Rect[1])
            text = result["juryo"]
            stream = f"BT /Helv 10 Tf 0 g {w / 2 - len(text) * 2.78:.2f} {h / 2 - 3.5:.2f} Td ({text}) Tj ET"
            f.AP = Dictionary(N=pdf.make_stream(stream.encode(), Type=Name.XObject, Subtype=Name.Form,
                                                BBox=Array([0, 0, w, h]),
                                                Resources=Dictionary(Font=pdf.Root.AcroForm.DR.Font)))


def main(path):
    failures = []
    with pikepdf.open(path) as pdf:
        doc_js, keystroke, calcs, names = scripts(pdf)
        job = {"docJs": doc_js, "keystroke": keystroke, "calcs": calcs, "fieldNames": names,
               "inputs": {str(k): v for k, v in INPUTS.items()}, "keyTests": KEY_TESTS}
        out = subprocess.run(["node", str(HERE / "acrobat_sim.js")], input=json.dumps(job),
                             capture_output=True, text=True, check=True)
        result = json.loads(out.stdout)
        pages = {int(k): v for k, v in result["pages"].items()}

        print("ES5 syntax errors:", result["es5"] or "none")
        failures += result["es5"]
        for k in result["keys"]:
            ok = k["accepted"] == EXPECTED_KEYS.get(k["change"], False)
            print(f"  keystroke {k['change']!r:6} accepted={k['accepted']!s:5} {'OK' if ok else 'BAD'}")
            if not ok:
                failures.append(f"keystroke {k['change']!r}")

        bake(pdf, pages)
        baked = Path(path).with_name(Path(path).stem + "_baked.pdf")
        pdf.save(baked)

    prefix = baked.with_suffix("")
    subprocess.run(["pdftoppm", "-r", "300", "-png", str(baked), str(prefix)], check=True)
    pngs = sorted(prefix.parent.glob(prefix.name + "-*.png"))
    for page, png in enumerate(pngs):
        img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
        text, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        chuban = calcs[page]["js"].split('"')[-2].rstrip(",")
        expected = f"{chuban},{INPUTS[page]}"
        juryo = pages[page]["juryo"]
        ok = text == expected and juryo == INPUTS[page]
        print(f"  page {page + 1}: QR={text!r} expected={expected!r} 受領書={juryo!r} "
              f"dark cells={len(pages[page]['dark'])} {'OK' if ok else 'BAD'}")
        if not ok:
            failures.append(f"page {page + 1}")

    print("baked PDF:", baked)
    print("FAILURES:", failures or 0)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

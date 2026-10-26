"""Checks js/qr_v2m.js against the qrcode library and decodes it with OpenCV."""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import qrcode
from qrcode.util import QRData, MODE_8BIT_BYTE

DUMP = Path(__file__).with_name("qr_dump.js")
SAMPLES = ["YN34214,10000", "YN34217,20000", "YN34218,1", "YN99999,9999999", "A", "X" * 26]


def js_matrix(text, mask=None):
    args = ["node", str(DUMP), text] + ([] if mask is None else [str(mask)])
    return json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)


def reference(text, mask):
    qr = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_M, mask_pattern=mask, border=0)
    qr.add_data(QRData(text.encode("ascii"), mode=MODE_8BIT_BYTE))
    qr.make(fit=False)
    return [[int(v) for v in row] for row in qr.get_matrix()]


def decode(matrix):
    a = np.array(matrix, dtype=np.uint8)
    img = np.where(np.pad(a, 4) == 1, 0, 255).astype(np.uint8)
    img = cv2.resize(img, None, fx=10, fy=10, interpolation=cv2.INTER_NEAREST)
    text, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    return text


failures = 0
for text in SAMPLES:
    for mask in range(8):
        if js_matrix(text, mask) != reference(text, mask):
            print(f"MISMATCH text={text!r} mask={mask}")
            failures += 1
    decoded = decode(js_matrix(text))
    ok = decoded == text
    failures += not ok
    print(f"{'OK ' if ok else 'BAD'} {text!r} -> {decoded!r}")

for bad in ["X" * 27, "YN納入,1"]:
    result = js_matrix(bad)
    ok = result is None
    failures += not ok
    print(f"{'OK ' if ok else 'BAD'} rejects {bad!r}")

print("FAILURES:", failures)
sys.exit(1 if failures else 0)

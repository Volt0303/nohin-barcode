"""Fixed positions on the FileMaker 納品書 PDF (A4 landscape, 842 x 595 pt).

All rectangles are (x0, top, x1, bottom) in PDF points with the origin at the
top-left, as measured from the drawn box lines in 納品書_サンプル3枚.pdf.
The layout is identical on every page.
"""

PAGE_WIDTH = 842
PAGE_HEIGHT = 595

# 納品書: the 納入数 box between 納入日 and 発注残数.
NOHIN_QTY_BOX = (392.0, 236.5, 477.0, 253.5)

# 受領書: the 納入数 box to the right of 注番.
JURYO_QTY_BOX = (441.0, 485.5, 497.0, 499.5)

# 納品書: free area right of the large 部品番号 and left of
# その他法的要求事項 / 静電対策 / 保管期限. Nothing is drawn here.
QR_FREE_ZONE = (420.0, 255.0, 488.0, 313.0)

# 注番 value printed in the 納品書 注番 column; used when FileMaker does not
# pass it on the command line.
CHUBAN_TEXT_ZONE = (571.0, 198.0, 659.0, 215.0)  # inside the column lines at x 570 / 660

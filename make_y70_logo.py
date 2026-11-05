"""Compose SoICT horizontal lock-ups with the HUST 70-year logo (vector, no rasterising).

Takes the text part of soict_{vi,en}_h.pdf (everything right of the BK shield) and
puts hustlogo_y70.pdf in place of the shield, scaled so that
  * the TOP of the "7" bar sits level with the cap top of the first text line, and
  * the BOTTOM of the logo sits level with the baseline of the last text line.
The arrow tip pokes above the text; the page is extended upwards so it is not clipped.

usage: python3 make_y70_logo.py [assets/logo dir]   (default: ./assets/logo)
requires: PyMuPDF  (python3 -m pip install pymupdf)
"""
import sys
import pymupdf

LOGO_DIR = sys.argv[1] if len(sys.argv) > 1 else "./assets/logo"

# --- measurements of hustlogo_y70.pdf (points, page 1000 x 1000) -------------
Y70_INK_X = (19.68, 980.16)   # left / right edge of the artwork
Y70_ARROW_TOP = 49.44         # tip of the yellow arrow (highest ink)
Y70_SEVEN_TOP = 146.0         # top edge of the horizontal bar of the "7"
Y70_BOTTOM = 863.04           # bottom of "HUST" / the 7 stroke (lowest ink)

# --- measurements of the source lock-ups (points) ----------------------------
SPECS = {
    # name: (shield right edge, text left edge, cap top of line 1, baseline of last line)
    # Cap top/baseline are measured on the first letter column ("Đ"/"V", "H"/"C"), so
    # Vietnamese diacritics above the caps (e.g. the circumflex in "NỘI") are ignored.
    "soict_vi_h": (32.16, 48.00, 4.68, 43.68),
    "soict_en_h": (31.92, 47.76, 2.70, 43.98),
}

y70 = pymupdf.open(f"{LOGO_DIR}/hustlogo_y70.pdf")

for name, (shield_right, text_left, text_top, text_bottom) in SPECS.items():
    src = pymupdf.open(f"{LOGO_DIR}/{name}.pdf")
    W, H = src[0].rect.width, src[0].rect.height
    gap = text_left - shield_right                       # keep the original logo-text spacing

    s = (text_bottom - text_top) / (Y70_BOTTOM - Y70_SEVEN_TOP)   # pt per logo-pt
    logo_top = text_top - (Y70_SEVEN_TOP - Y70_ARROW_TOP) * s     # arrow tip (may be < 0)
    pad = max(0.0, -logo_top)                                     # extend page upwards
    logo_w = (Y70_INK_X[1] - Y70_INK_X[0]) * s
    logo_h = (Y70_BOTTOM - Y70_ARROW_TOP) * s
    text_w = W - text_left

    out = pymupdf.open()
    page = out.new_page(width=logo_w + gap + text_w, height=H + pad)
    clip = pymupdf.Rect(Y70_INK_X[0], Y70_ARROW_TOP, Y70_INK_X[1], Y70_BOTTOM)
    page.show_pdf_page(pymupdf.Rect(0, logo_top + pad, logo_w, logo_top + pad + logo_h),
                       y70, 0, clip=clip)
    page.show_pdf_page(pymupdf.Rect(logo_w + gap, pad, logo_w + gap + text_w, pad + H),
                       src, 0, clip=pymupdf.Rect(text_left, 0, W, H))
    dst = f"{LOGO_DIR}/{name}_y70.pdf"
    out.save(dst, garbage=4, deflate=True)
    print(f"{dst}: {page.rect.width:.2f} x {page.rect.height:.2f} pt | logo {logo_w:.2f} x {logo_h:.2f} pt, "
          f"7-top at y={text_top + pad:.2f} (text top {text_top + pad:.2f}), arrow +{pad:.2f} pt above")

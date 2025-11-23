import fitz  # PyMuPDF
from pathlib import Path
from typing import Tuple, Optional

import argparse
from rich.console import Console
from rich_argparse import RichHelpFormatter
G_CONSOLE = Console()

import csv
from pathlib import Path

def crop_pdf_region(
    input_pdf: str,
    output_pdf: str,
    page_index: int = 0,
    crop_rect: Optional[Tuple[float, float, float, float]] = None,
    relative_rect: Optional[Tuple[float, float, float, float]] = None,
):
    """
    Crop any arbitrary region of a PDF page and save it as a new PDF file (vector-preserving).

    Parameters
    ----------
    input_pdf : str
        Path to the source PDF file.
    output_pdf : str
        Path to the output PDF file.
    page_index : int, default 0
        Index of the page to crop (0 is the first page).
    crop_rect : (x1, y1, x2, y2), optional
        Absolute coordinates in the PDF coordinate system (unit: points, 72pt = 1 inch).
        If crop_rect is used, ignore relative_rect.
    relative_rect : (l, t, r, b), optional
        Relative coordinates in the range [0,1] of the page:
        - l: left, t: top, r: right, b: bottom
        Example: (0.0, 0.0, 0.5, 0.5) means the upper-left quarter of the page.
        If relative_rect is used, ignore crop_rect.
    """

    in_path = Path(input_pdf)
    out_path = Path(output_pdf)

    if not in_path.exists():
        raise FileNotFoundError(f"File not found: {in_path}")

    doc = fitz.open(str(in_path))

    if page_index < 0 or page_index >= len(doc):
        raise IndexError(f"page_index {page_index} is invalid (the file has {len(doc)} pages)")

    src_page = doc[page_index]
    page_rect = src_page.rect  # Rect(0, 0, width, height)

    # Determine the crop region
    if crop_rect is not None:
        x1, y1, x2, y2 = crop_rect
        clip = fitz.Rect(x1, y1, x2, y2)
    elif relative_rect is not None:
        l, t, r, b = relative_rect
        clip = fitz.Rect(
            page_rect.x0 + l * page_rect.width,
            page_rect.y0 + t * page_rect.height,
            page_rect.x0 + r * page_rect.width,
            page_rect.y0 + b * page_rect.height,
        )
    else:
        raise ValueError("Either crop_rect or relative_rect must be provided")

    # Create a new PDF and insert the clipped region
    dst_doc = fitz.open()
    new_page = dst_doc.new_page(width=clip.width, height=clip.height)
    new_page.show_pdf_page(new_page.rect, doc, page_index, clip=clip)

    dst_doc.save(str(out_path))
    dst_doc.close()
    doc.close()

    G_CONSOLE.print(f"Cropped page {page_index} -> {out_path.resolve()}")



def handle_single_crop(input_pdf, output_pdf, page_index, crop_rect, relative_rect, args):
    try:
        if args.dry_run:
            G_CONSOLE.print(f"[dry-run] Would crop {input_pdf} -> {output_pdf} (page {page_index}) crop={crop_rect or relative_rect}")
        else:
            crop_pdf_region(
                input_pdf=input_pdf,
                output_pdf=output_pdf,
                page_index=page_index,
                crop_rect=crop_rect,
                relative_rect=relative_rect,
            )
    except Exception as e:
        G_CONSOLE.print(f"Error processing ({input_pdf} -> {output_pdf}): {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crop a region from a PDF page and save as a new PDF.")
    parser.add_argument("input_pdf", nargs="?", type=str, help="Path to the input PDF file (single-file mode).")
    parser.add_argument("output_pdf", nargs="?", type=str, help="Path to the output PDF file (single-file mode).")
    parser.add_argument("--page_index", type=int, default=0, help="Index of the page to crop (single-file mode).")
    parser.add_argument("--crop_rect", type=float, nargs=4, metavar=('x1', 'y1', 'x2', 'y2'),
                        help="Absolute crop rectangle coordinates (x1, y1, x2, y2) (single-file mode).")
    parser.add_argument("--relative_rect", type=float, nargs=4, metavar=('l', 't', 'r', 'b'),
                        help="Relative crop rectangle coordinates (l, t, r, b) (single-file mode).")
    parser.add_argument("--csv", type=str, help="Path to CSV file describing batch crops (batch mode).")
    parser.add_argument("--dry-run", action="store_true", help="Print the jobs that would be run without executing them.")
    args = parser.parse_args()

    if args.csv: # batch mode
        csv_path = Path(args.csv)
        if not csv_path.exists():
            parser.error(f"CSV file not found: {csv_path}")

        with csv_path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row_no, row in enumerate(reader, start=1):
                # Skip blank/commented rows
                input_pdf = (row.get("input_pdf") or "").strip()
                if not input_pdf or input_pdf.startswith("#"):
                    continue

                output_pdf = (row.get("output_pdf") or "").strip()
                if not output_pdf:
                    G_CONSOLE.print(f"Skipping row {row_no}: missing output_pdf")
                    continue

                # parse page_index
                page_index = int(row.get("page_index", 0) or 0)

                # try absolute crop rect first
                try:
                    if all(k in row and row[k].strip() != "" for k in ("x1", "y1", "x2", "y2")):
                        crop_rect = (
                            float(row["x1"]),
                            float(row["y1"]),
                            float(row["x2"]),
                            float(row["y2"]),
                        )
                        relative_rect = None
                    elif all(k in row and row[k].strip() != "" for k in ("l", "t", "r", "b")):
                        relative_rect = (
                            float(row["l"]),
                            float(row["t"]),
                            float(row["r"]),
                            float(row["b"]),
                        )
                        crop_rect = None
                    else:
                        G_CONSOLE.print(f"Skipping row {row_no}: no valid crop_rect or relative_rect found")
                        continue
                except ValueError as e:
                    G_CONSOLE.print(f"Skipping row {row_no}: invalid numeric value: {e}")
                    continue

                G_CONSOLE.print(f"Processing row {row_no}: {input_pdf} -> {output_pdf} (page {page_index}) crop={crop_rect or relative_rect}")
                handle_single_crop(
                    input_pdf=input_pdf,
                    output_pdf=output_pdf,
                    page_index=page_index,
                    crop_rect=crop_rect,
                    relative_rect=relative_rect,
                    args=args,
                )
    else: # single-file mode: require positional input/output
        if not args.input_pdf or not args.output_pdf:
            parser.error("input_pdf and output_pdf are required in single-file mode (or provide --csv for batch mode).")

        if args.dry_run:
            G_CONSOLE.print(f"[dry-run] Would crop {args.input_pdf} -> {args.output_pdf} (page {args.page_index}) crop={tuple(args.crop_rect) if args.crop_rect else tuple(args.relative_rect) if args.relative_rect else None}")
        else:
            handle_single_crop(
                input_pdf=args.input_pdf,
                output_pdf=args.output_pdf,
                page_index=args.page_index,
                crop_rect=tuple(args.crop_rect) if args.crop_rect else None,
                relative_rect=tuple(args.relative_rect) if args.relative_rect else None,
                args=args,
            )

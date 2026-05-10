import argparse
import csv
import sys
from pathlib import Path
from typing import Optional, Tuple


try:
    from rich.console import Console
except ModuleNotFoundError:
    Console = None


if Console is not None:
    G_CONSOLE = Console(markup=False)
else:
    class PlainConsole:
        def print(self, *args, **kwargs):
            print(*args)

    G_CONSOLE = PlainConsole()


RectTuple = Tuple[float, float, float, float]


def require_fitz():
    try:
        import fitz  # PyMuPDF
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency: PyMuPDF. Install it with `python3 -m pip install pymupdf`."
        ) from exc
    return fitz


def validate_absolute_rect(rect: RectTuple) -> None:
    x1, y1, x2, y2 = rect
    if x1 >= x2 or y1 >= y2:
        raise ValueError("crop_rect must satisfy x1 < x2 and y1 < y2")


def validate_relative_rect(rect: RectTuple) -> None:
    l, t, r, b = rect
    if not all(0 <= value <= 1 for value in rect):
        raise ValueError("relative_rect values must be in the range [0, 1]")
    if l >= r or t >= b:
        raise ValueError("relative_rect must satisfy l < r and t < b")


def rect_intersects_page(clip, page_rect) -> bool:
    return not (
        clip.x1 <= page_rect.x0
        or clip.x0 >= page_rect.x1
        or clip.y1 <= page_rect.y0
        or clip.y0 >= page_rect.y1
    )


def crop_pdf_region(
    input_pdf: str,
    output_pdf: str,
    page_index: int = 0,
    crop_rect: Optional[RectTuple] = None,
    relative_rect: Optional[RectTuple] = None,
):
    """
    Crop an arbitrary region of a PDF page and save it as a vector-preserving PDF.

    Absolute coordinates are in PDF points. Relative coordinates are fractions of
    the selected page in the form (left, top, right, bottom).
    """
    if (crop_rect is None) == (relative_rect is None):
        raise ValueError("Provide exactly one of crop_rect or relative_rect")

    if crop_rect is not None:
        validate_absolute_rect(crop_rect)
    if relative_rect is not None:
        validate_relative_rect(relative_rect)

    fitz = require_fitz()

    in_path = Path(input_pdf)
    out_path = Path(output_pdf)

    if not in_path.exists():
        raise FileNotFoundError(f"File not found: {in_path}")

    doc = fitz.open(str(in_path))
    try:
        if page_index < 0 or page_index >= len(doc):
            raise IndexError(f"page_index {page_index} is invalid (the file has {len(doc)} pages)")

        page_rect = doc[page_index].rect

        if crop_rect is not None:
            clip = fitz.Rect(*crop_rect)
        else:
            l, t, r, b = relative_rect
            clip = fitz.Rect(
                page_rect.x0 + l * page_rect.width,
                page_rect.y0 + t * page_rect.height,
                page_rect.x0 + r * page_rect.width,
                page_rect.y0 + b * page_rect.height,
            )

        if not rect_intersects_page(clip, page_rect):
            raise ValueError(f"crop rectangle {tuple(clip)} does not intersect page rectangle {tuple(page_rect)}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        dst_doc = fitz.open()
        try:
            new_page = dst_doc.new_page(width=clip.width, height=clip.height)
            new_page.show_pdf_page(new_page.rect, doc, page_index, clip=clip)
            dst_doc.save(str(out_path))
        finally:
            dst_doc.close()
    finally:
        doc.close()

    G_CONSOLE.print(f"Cropped page {page_index} -> {out_path.resolve()}")


def handle_single_crop(input_pdf, output_pdf, page_index, crop_rect, relative_rect, dry_run=False) -> bool:
    try:
        if dry_run:
            G_CONSOLE.print(
                f"[dry-run] Would crop {input_pdf} -> {output_pdf} "
                f"(page {page_index}) crop={crop_rect or relative_rect}"
            )
            return True

        crop_pdf_region(
            input_pdf=input_pdf,
            output_pdf=output_pdf,
            page_index=page_index,
            crop_rect=crop_rect,
            relative_rect=relative_rect,
        )
        return True
    except Exception as exc:
        G_CONSOLE.print(f"Error processing ({input_pdf} -> {output_pdf}): {exc}")
        return False


def parse_batch_row(row_no: int, row: dict):
    input_pdf = (row.get("input_pdf") or "").strip()
    if not input_pdf or input_pdf.startswith("#"):
        return None

    output_pdf = (row.get("output_pdf") or "").strip()
    if not output_pdf:
        raise ValueError(f"row {row_no}: missing output_pdf")

    try:
        page_index = int(row.get("page_index", 0) or 0)
    except ValueError as exc:
        raise ValueError(f"row {row_no}: invalid page_index: {exc}") from exc

    has_absolute = all(k in row and row[k].strip() != "" for k in ("x1", "y1", "x2", "y2"))
    has_relative = all(k in row and row[k].strip() != "" for k in ("l", "t", "r", "b"))

    if has_absolute and has_relative:
        raise ValueError(f"row {row_no}: provide only one of absolute or relative crop coordinates")
    if not has_absolute and not has_relative:
        raise ValueError(f"row {row_no}: no valid crop_rect or relative_rect found")

    try:
        if has_absolute:
            crop_rect = tuple(float(row[k]) for k in ("x1", "y1", "x2", "y2"))
            validate_absolute_rect(crop_rect)
            relative_rect = None
        else:
            relative_rect = tuple(float(row[k]) for k in ("l", "t", "r", "b"))
            validate_relative_rect(relative_rect)
            crop_rect = None
    except ValueError as exc:
        raise ValueError(f"row {row_no}: invalid crop coordinates: {exc}") from exc

    return input_pdf, output_pdf, page_index, crop_rect, relative_rect


def run_batch(csv_path: Path, dry_run: bool) -> int:
    if not csv_path.exists():
        G_CONSOLE.print(f"CSV file not found: {csv_path}")
        return 2

    failures = 0
    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row_no, row in enumerate(reader, start=1):
            try:
                parsed = parse_batch_row(row_no, row)
            except ValueError as exc:
                failures += 1
                G_CONSOLE.print(f"Skipping {exc}")
                continue

            if parsed is None:
                continue

            input_pdf, output_pdf, page_index, crop_rect, relative_rect = parsed
            G_CONSOLE.print(
                f"Processing row {row_no}: {input_pdf} -> {output_pdf} "
                f"(page {page_index}) crop={crop_rect or relative_rect}"
            )
            if not handle_single_crop(input_pdf, output_pdf, page_index, crop_rect, relative_rect, dry_run=dry_run):
                failures += 1

    if failures:
        G_CONSOLE.print(f"Completed with {failures} failed row(s).")
        return 1

    return 0


def default_csv_path() -> Path:
    return Path(__file__).resolve().parent / "crop_data.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Crop a region from a PDF page and save it as a vector PDF. "
            "Requires PyMuPDF for actual cropping."
        )
    )
    parser.add_argument("input_pdf", nargs="?", type=str, help="Path to the input PDF file (single-file mode).")
    parser.add_argument("output_pdf", nargs="?", type=str, help="Path to the output PDF file (single-file mode).")
    parser.add_argument("--page_index", type=int, default=0, help="Index of the page to crop (single-file mode).")
    parser.add_argument(
        "--crop_rect",
        type=float,
        nargs=4,
        metavar=("x1", "y1", "x2", "y2"),
        help="Absolute crop rectangle coordinates in PDF points.",
    )
    parser.add_argument(
        "--relative_rect",
        type=float,
        nargs=4,
        metavar=("l", "t", "r", "b"),
        help="Relative crop rectangle coordinates in [0, 1].",
    )
    parser.add_argument("--csv", type=str, help="Path to CSV file describing batch crops.")
    parser.add_argument(
        "--run-default",
        action="store_true",
        help="Run the default crop_data.csv job list next to this script.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print jobs without writing PDFs.")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.csv and args.run_default:
        parser.error("use only one of --csv or --run-default")

    if args.csv or args.run_default:
        if args.input_pdf or args.output_pdf:
            parser.error("positional input/output PDFs cannot be used with batch mode")
        csv_path = Path(args.csv) if args.csv else default_csv_path()
        return run_batch(csv_path, args.dry_run)

    if not args.input_pdf or not args.output_pdf:
        parser.error("input_pdf and output_pdf are required in single-file mode (or provide --csv/--run-default)")

    if (args.crop_rect is None) == (args.relative_rect is None):
        parser.error("single-file mode requires exactly one of --crop_rect or --relative_rect")

    crop_rect = tuple(args.crop_rect) if args.crop_rect else None
    relative_rect = tuple(args.relative_rect) if args.relative_rect else None

    try:
        if crop_rect is not None:
            validate_absolute_rect(crop_rect)
        if relative_rect is not None:
            validate_relative_rect(relative_rect)
    except ValueError as exc:
        parser.error(str(exc))

    return 0 if handle_single_crop(
        args.input_pdf,
        args.output_pdf,
        args.page_index,
        crop_rect,
        relative_rect,
        dry_run=args.dry_run,
    ) else 1


if __name__ == "__main__":
    sys.exit(main())

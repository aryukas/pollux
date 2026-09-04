from pathlib import Path

import pymupdf

from ocr import PolluxOCR
from table_reconstructor import (
    reconstruct_rows,
)


PDF_PATH = Path(__file__).parent / "financial_statements.pdf"
CASH_FLOW_PAGE = 14


def render_pdf_page(
    pdf_path: Path,
    page_number: int,
    scale: float = 2.0,
) -> Path:
    """
    Render one PDF page to a temporary PNG image.
    """

    pdf = pymupdf.open(str(pdf_path))

    try:
        if page_number < 1 or page_number > len(pdf):
            raise ValueError(
                f"Page {page_number} does not exist. "
                f"PDF contains {len(pdf)} pages."
            )

        page = pdf[page_number - 1]

        matrix = pymupdf.Matrix(
            scale,
            scale,
        )

        pix = page.get_pixmap(
            matrix=matrix,
            colorspace=pymupdf.csRGB,
            alpha=False,
        )

        output_path = (
            Path(__file__).parent
            / "_table_test_page.png"
        )

        pix.save(str(output_path))

        return output_path

    finally:
        pdf.close()


def main() -> None:
    print()
    print("=" * 100)
    print("POLLUX CASH FLOW TABLE RECONSTRUCTION TEST")
    print("=" * 100)

    if not PDF_PATH.exists():
        print()
        print(f"ERROR: PDF not found: {PDF_PATH}")
        print("=" * 100)
        return

    image_path: Path | None = None

    try:
        print()
        print("Rendering Cash Flow Statement page...")

        image_path = render_pdf_page(
            PDF_PATH,
            CASH_FLOW_PAGE,
            scale=2.0,
        )

        print(f"Rendered: {image_path.name}")

        print()
        print("Initializing PaddleOCR...")

        engine = PolluxOCR()

        print("Running OCR...")
        print()

        results = engine.process_image(
            str(image_path),
            page_number=CASH_FLOW_PAGE,
        )

        print(
            f"OCR elements detected: {len(results)}"
        )

        print()
        print("Reconstructing financial table...")

        columns, rows = reconstruct_rows(
            results,
            y_tolerance=12.0,
        )

        print()

        if columns is None:
            print(
                "ERROR: Could not detect financial "
                "statement column headers."
            )
            return

        print("-" * 100)

        print(
            f"Description anchor : "
            f"X = {columns.description_x:.2f}"
        )

        print(
            f"Current-year anchor: "
            f"X = {columns.current_year_x:.2f}"
        )

        print(
            f"Previous-year anchor: "
            f"X = {columns.previous_year_x:.2f}"
        )

        print(
            f"Current year      : "
            f"{columns.current_year}"
        )

        print(
            f"Previous year     : "
            f"{columns.previous_year}"
        )

        print("-" * 100)

        print()
        print(
            f"Reconstructed rows: {len(rows)}"
        )

        print()
        print("-" * 100)

        for index, row in enumerate(
            rows,
            start=1,
        ):
            current = (
                ", ".join(
                    row.current_candidates
                )
                if row.current_candidates
                else "-"
            )

            previous = (
                ", ".join(
                    row.previous_candidates
                )
                if row.previous_candidates
                else "-"
            )

            flags = []

            if row.ambiguous_current:
                flags.append(
                    "AMBIGUOUS_CURRENT"
                )

            if row.ambiguous_previous:
                flags.append(
                    "AMBIGUOUS_PREVIOUS"
                )

            flag_text = (
                f" | {', '.join(flags)}"
                if flags
                else ""
            )

            print(
                f"ROW {index:02d} "
                f"| Y={row.y_center:8.2f}"
            )

            print(
                f"     DESCRIPTION: "
                f"{row.description or '-'}"
            )

            print(
                f"     CURRENT: "
                f"{current}"
            )

            print(
                f"     PREVIOUS: "
                f"{previous}"
                f"{flag_text}"
            )

        print("-" * 100)

        print()
        print("=" * 100)
        print("TABLE RECONSTRUCTION TEST COMPLETE")
        print("=" * 100)

    except Exception as exc:
        print()
        print("=" * 100)
        print("TABLE RECONSTRUCTION TEST FAILED")
        print("=" * 100)
        print(
            f"{type(exc).__name__}: {exc}"
        )
        print("=" * 100)

    finally:
        if (
            image_path is not None
            and image_path.exists()
        ):
            image_path.unlink()


if __name__ == "__main__":
    main()
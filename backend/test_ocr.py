from pathlib import Path

import pymupdf

from ocr import PolluxOCR


PDF_PATH = Path(__file__).parent / "financial_statements.pdf"

# Human-readable page number.
# This is only for testing. The final Pollux pipeline
# must discover the Cash Flow Statement dynamically.
CASH_FLOW_PAGE = 14


def render_pdf_page(
    pdf_path: Path,
    page_number: int,
    scale: float = 2.0,
) -> Path:
    """
    Render one PDF page to a temporary PNG image.

    page_number is 1-based.
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
            / "_cash_flow_page.png"
        )

        pix.save(str(output_path))

        return output_path

    finally:
        pdf.close()


def main() -> None:
    print()
    print("=" * 80)
    print("POLLUX CASH FLOW OCR + BOUNDING BOX TEST")
    print("=" * 80)

    if not PDF_PATH.exists():
        print()
        print(f"ERROR: PDF not found: {PDF_PATH}")
        print("=" * 80)
        return

    print(f"PDF: {PDF_PATH.name}")
    print(f"Target page: {CASH_FLOW_PAGE}")

    image_path: Path | None = None

    try:
        # ------------------------------------------------------------
        # Render page
        # ------------------------------------------------------------

        print()
        print("Rendering Cash Flow Statement page...")

        image_path = render_pdf_page(
            PDF_PATH,
            CASH_FLOW_PAGE,
            scale=2.0,
        )

        print(f"Rendered: {image_path.name}")

        # ------------------------------------------------------------
        # OCR
        # ------------------------------------------------------------

        print()
        print("Initializing PaddleOCR...")

        engine = PolluxOCR()

        print("Running OCR...")
        print()

        results = engine.process_image(
            str(image_path),
            page_number=CASH_FLOW_PAGE,
        )

        # ------------------------------------------------------------
        # Results
        # ------------------------------------------------------------

        print(
            f"Detected text elements: {len(results)}"
        )

        print()
        print("-" * 80)

        for index, item in enumerate(
            results,
            start=1,
        ):
            print(
                f"{index:03d} | "
                f"{item.confidence:.3f} | "
                f"{item.text}"
            )

            print(
                f"      BBOX: {item.bbox}"
            )

        print("-" * 80)

        print()
        print("=" * 80)
        print("OCR + BOUNDING BOX TEST COMPLETE")
        print("=" * 80)

    except Exception as exc:
        print()
        print("=" * 80)
        print("OCR TEST FAILED")
        print("=" * 80)
        print(
            f"{type(exc).__name__}: {exc}"
        )
        print("=" * 80)

    finally:
        # Remove temporary rendered image.
        if (
            image_path is not None
            and image_path.exists()
        ):
            image_path.unlink()


if __name__ == "__main__":
    main()
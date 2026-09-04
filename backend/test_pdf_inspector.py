from pathlib import Path

from pdf_inspector import inspect_pdf, print_inspection


TEST_PDF = Path(__file__).parent / "test.pdf"


def main():
    if not TEST_PDF.exists():
        print(f"ERROR: PDF not found: {TEST_PDF}")
        return

    try:
        result = inspect_pdf(TEST_PDF)
        print_inspection(result)

    except Exception as exc:
        print()
        print("=" * 70)
        print("POLLUX PDF INSPECTION ERROR")
        print("=" * 70)
        print(f"{type(exc).__name__}: {exc}")
        print("=" * 70)


if __name__ == "__main__":
    main()
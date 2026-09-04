from pathlib import Path

from pdf_inspector import inspect_pdf


PDF_PATH = Path("test.pdf")


def main():
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found: {PDF_PATH.resolve()}")
        return

    content = PDF_PATH.read_bytes()

    result = inspect_pdf(content)

    print("\n" + "=" * 70)
    print("POLLUX PDF INSPECTION")
    print("=" * 70)

    print(f"Pages: {result['page_count']}")
    print(f"Has bookmarks/outline: {result['has_outline']}")

    print("\nBOOKMARK DETECTION")
    print("-" * 70)

    if result["outline_statements"]:
        for statement, pages in result["outline_statements"].items():
            if pages:
                print(f"{statement}: pages {pages}")
    else:
        print("No financial statements detected from bookmarks.")

    print("\nNATIVE TEXT DETECTION")
    print("-" * 70)

    for statement, pages in result["text_statements"].items():
        if pages:
            print(f"{statement}: pages {pages}")
        else:
            print(f"{statement}: not detected")

    print("\nCOMBINED DETECTION")
    print("-" * 70)

    for statement, pages in result["statements"].items():
        if pages:
            print(f"{statement}: pages {pages}")
        else:
            print(f"{statement}: not detected")

    print("\nPAGE SUMMARY")
    print("-" * 70)

    for page in result["pages"]:
        if page["statements"]:
            print(
                f"Page {page['page']}: "
                f"{', '.join(page['statements'])}"
            )

    print("=" * 70)


if __name__ == "__main__":
    main()
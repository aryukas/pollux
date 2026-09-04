from io import BytesIO
from typing import Any

from pypdf import PdfReader


STATEMENT_KEYWORDS = {
    "balance_sheet": (
        "balance sheet",
        "statement of financial position",
        "statement of financial condition",
    ),
    "income_statement": (
        "income statement",
        "statement of income",
        "statement of operations",
        "statement of profit and loss",
        "profit and loss statement",
        "profit & loss statement",
        "statement of comprehensive income",
    ),
    "cash_flow_statement": (
        "cash flow statement",
        "statement of cash flows",
        "statement of cash flow",
    ),
}


CASH_FLOW_SECTION_KEYWORDS = (
    "cash flows from operating activities",
    "cash flow from operating activities",
    "cash flows from investing activities",
    "cash flow from investing activities",
    "cash flows from financing activities",
    "cash flow from financing activities",
    "net increase in cash",
    "net decrease in cash",
    "net change in cash",
    "cash and cash equivalents",
)


def _normalise_text(text: str) -> str:
    """
    Normalise extracted PDF text for reliable matching.
    """
    return " ".join(text.lower().split())


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """
    Return True when at least one keyword is present.
    """
    return any(keyword in text for keyword in keywords)


def _classify_page(text: str) -> list[str]:
    """
    Identify likely financial statement types on a page.

    Cash Flow Statement detection uses both:
    - a statement title
    - characteristic cash-flow sections
    """
    normalised_text = _normalise_text(text)

    matches: list[str] = []

    # Balance Sheet
    if _contains_any(
        normalised_text,
        STATEMENT_KEYWORDS["balance_sheet"],
    ):
        matches.append("balance_sheet")

    # Income Statement
    if _contains_any(
        normalised_text,
        STATEMENT_KEYWORDS["income_statement"],
    ):
        matches.append("income_statement")

    # Cash Flow Statement
    has_cash_flow_title = _contains_any(
        normalised_text,
        STATEMENT_KEYWORDS["cash_flow_statement"],
    )

    cash_flow_sections = [
        keyword
        for keyword in CASH_FLOW_SECTION_KEYWORDS
        if keyword in normalised_text
    ]

    # A page is considered a likely Cash Flow Statement page when:
    # 1. It contains a Cash Flow Statement title, OR
    # 2. It contains multiple characteristic cash-flow sections.
    if has_cash_flow_title or len(cash_flow_sections) >= 2:
        matches.append("cash_flow_statement")

    return matches


def _extract_outline(reader: PdfReader) -> list[dict[str, Any]]:
    """
    Extract PDF bookmarks/outlines.

    Returns a lightweight representation containing:
    - bookmark title
    - target page when available
    """
    outline_items: list[dict[str, Any]] = []

    try:
        outline = reader.outline
    except Exception:
        return outline_items

    def process_items(items: list[Any], level: int = 0) -> None:
        for item in items:
            if isinstance(item, list):
                process_items(item, level + 1)
                continue

            title = getattr(item, "title", None)

            if not title:
                continue

            try:
                page_number = reader.get_destination_page_number(item) + 1
            except Exception:
                page_number = None

            outline_items.append(
                {
                    "title": str(title),
                    "page": page_number,
                    "level": level,
                }
            )

    process_items(outline)

    return outline_items


def _find_statement_pages_from_outline(
    outline: list[dict[str, Any]],
) -> dict[str, list[int]]:
    """
    Identify financial statement pages from PDF bookmarks.
    """
    detected: dict[str, list[int]] = {
        "balance_sheet": [],
        "income_statement": [],
        "cash_flow_statement": [],
    }

    for item in outline:
        title = _normalise_text(item["title"])
        page = item["page"]

        if page is None:
            continue

        if _contains_any(
            title,
            STATEMENT_KEYWORDS["balance_sheet"],
        ):
            detected["balance_sheet"].append(page)

        if _contains_any(
            title,
            STATEMENT_KEYWORDS["income_statement"],
        ):
            detected["income_statement"].append(page)

        if _contains_any(
            title,
            STATEMENT_KEYWORDS["cash_flow_statement"],
        ):
            detected["cash_flow_statement"].append(page)

    return detected


def inspect_pdf(content: bytes) -> dict[str, Any]:
    """
    Inspect a PDF without OCR.

    The inspector checks:

    1. PDF page count
    2. PDF bookmarks/outlines
    3. Native PDF text
    4. Financial statement titles
    5. Characteristic Cash Flow Statement sections

    OCR is intentionally NOT used here.
    """
    reader = PdfReader(BytesIO(content))

    page_count = len(reader.pages)

    outline = _extract_outline(reader)

    outline_statements = _find_statement_pages_from_outline(
        outline
    )

    pages: list[dict[str, Any]] = []

    text_statements: dict[str, list[int]] = {
        "balance_sheet": [],
        "income_statement": [],
        "cash_flow_statement": [],
    }

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        text = page.extract_text() or ""

        statements = _classify_page(text)

        for statement in statements:
            text_statements[statement].append(page_number)

        pages.append(
            {
                "page": page_number,
                "text": text,
                "text_available": bool(text.strip()),
                "statements": statements,
            }
        )

    # Combine evidence from bookmarks and page text.
    combined_statements: dict[str, list[int]] = {}

    for statement_type in text_statements:
        combined_pages = set(
            outline_statements[statement_type]
            + text_statements[statement_type]
        )

        combined_statements[statement_type] = sorted(
            combined_pages
        )

    return {
        "page_count": page_count,
        "has_outline": bool(outline),
        "outline": outline,
        "outline_statements": outline_statements,
        "text_statements": text_statements,
        "statements": combined_statements,
        "pages": pages,
    }
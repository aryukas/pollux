from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Dict, List

from pypdf import PdfReader


FINANCIAL_STATEMENT_KEYWORDS = {
    "balance_sheet": [
        "balance sheet",
        "statement of financial position",
    ],
    "income_statement": [
        "profit and loss",
        "profit & loss",
        "statement of profit and loss",
        "income statement",
    ],
    "cash_flow_statement": [
        "cash flow statement",
        "cash flows from",
        "statement of cash flows",
    ],
}


@dataclass
class AttachmentInfo:
    name: str
    size_bytes: int
    is_pdf: bool


@dataclass
class PDFInspectionResult:
    file_name: str
    page_count: int
    has_outline: bool

    native_text_pages: Dict[str, List[int]] = field(default_factory=dict)

    attachments: List[AttachmentInfo] = field(default_factory=list)

    financial_statement_attachment: str | None = None

    attachment_page_count: int | None = None

    attachment_native_text_pages: Dict[str, List[int]] = field(
        default_factory=dict
    )


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def detect_statements(reader: PdfReader) -> Dict[str, List[int]]:
    detected = {
        "balance_sheet": [],
        "income_statement": [],
        "cash_flow_statement": [],
    }

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        text = normalize_text(text)

        for statement_type, keywords in FINANCIAL_STATEMENT_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                detected[statement_type].append(page_number)

    return detected


def get_attachment_bytes(reader: PdfReader, attachment_name: str) -> bytes:
    attachments = reader.attachments

    data = attachments[attachment_name]

    # pypdf versions may expose attachment data slightly differently.
    if isinstance(data, bytes):
        return data

    if isinstance(data, list):
        if not data:
            return b""

        first_item = data[0]

        if isinstance(first_item, bytes):
            return first_item

        if isinstance(first_item, tuple) and len(first_item) >= 2:
            return first_item[1]

    if isinstance(data, tuple) and len(data) >= 2:
        return data[1]

    raise TypeError(
        f"Unsupported attachment data format for: {attachment_name}"
    )


def is_pdf_attachment(name: str, content: bytes) -> bool:
    extension = Path(name).suffix.lower()

    if extension == ".pdf":
        return True

    return content.startswith(b"%PDF")


def choose_financial_statement_attachment(
    attachments: List[AttachmentInfo],
) -> str | None:

    # Strongest signal: filename explicitly indicates annual report /
    # financial statements.
    preferred_keywords = [
        "ar_fs",
        "financial_statement",
        "financial_statements",
        "annual_report",
        "annualreport",
    ]

    for attachment in attachments:
        name = attachment.name.lower()

        if not attachment.is_pdf:
            continue

        if any(keyword in name for keyword in preferred_keywords):
            return attachment.name

    # Secondary signal: filenames containing financial/report terminology.
    secondary_keywords = [
        "financial",
        "statement",
        "accounts",
        "report",
    ]

    for attachment in attachments:
        name = attachment.name.lower()

        if not attachment.is_pdf:
            continue

        if any(keyword in name for keyword in secondary_keywords):
            return attachment.name

    return None


def inspect_pdf(file_path: str | Path) -> PDFInspectionResult:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    with path.open("rb") as file:
        content = file.read()

    return inspect_pdf_bytes(
        content=content,
        file_name=path.name,
    )


def inspect_pdf_bytes(
    content: bytes,
    file_name: str = "uploaded.pdf",
) -> PDFInspectionResult:

    reader = PdfReader(BytesIO(content))

    page_count = len(reader.pages)

    has_outline = bool(reader.outline)

    native_text_pages = detect_statements(reader)

    attachment_infos: List[AttachmentInfo] = []

    for name in reader.attachments.keys():
        try:
            attachment_content = get_attachment_bytes(reader, name)
        except Exception:
            attachment_content = b""

        attachment_infos.append(
            AttachmentInfo(
                name=name,
                size_bytes=len(attachment_content),
                is_pdf=is_pdf_attachment(
                    name,
                    attachment_content,
                ),
            )
        )

    selected_attachment = choose_financial_statement_attachment(
        attachment_infos
    )

    attachment_page_count = None
    attachment_native_text_pages: Dict[str, List[int]] = {}

    if selected_attachment:
        attachment_content = get_attachment_bytes(
            reader,
            selected_attachment,
        )

        attachment_reader = PdfReader(BytesIO(attachment_content))

        attachment_page_count = len(attachment_reader.pages)

        attachment_native_text_pages = detect_statements(
            attachment_reader
        )

    return PDFInspectionResult(
        file_name=file_name,
        page_count=page_count,
        has_outline=has_outline,
        native_text_pages=native_text_pages,
        attachments=attachment_infos,
        financial_statement_attachment=selected_attachment,
        attachment_page_count=attachment_page_count,
        attachment_native_text_pages=attachment_native_text_pages,
    )


def print_inspection(result: PDFInspectionResult) -> None:
    print()
    print("=" * 70)
    print("POLLUX PDF INSPECTION")
    print("=" * 70)

    print(f"File: {result.file_name}")
    print(f"Pages: {result.page_count}")
    print(f"Has bookmarks/outline: {result.has_outline}")

    print()
    print("OUTER PDF NATIVE TEXT DETECTION")
    print("-" * 70)

    for statement_type, pages in result.native_text_pages.items():
        if pages:
            print(f"{statement_type}: pages {pages}")
        else:
            print(f"{statement_type}: not detected")

    print()
    print("EMBEDDED ATTACHMENTS")
    print("-" * 70)

    if not result.attachments:
        print("No embedded attachments detected.")
    else:
        for attachment in result.attachments:
            pdf_status = "PDF" if attachment.is_pdf else "non-PDF"

            print(
                f"- {attachment.name} "
                f"({attachment.size_bytes:,} bytes, {pdf_status})"
            )

    print()
    print("FINANCIAL STATEMENT ATTACHMENT")
    print("-" * 70)

    if result.financial_statement_attachment:
        print(
            f"Selected: {result.financial_statement_attachment}"
        )
        print(
            f"Pages: {result.attachment_page_count}"
        )
    else:
        print("No financial statement attachment selected.")

    print()
    print("ATTACHED PDF NATIVE TEXT DETECTION")
    print("-" * 70)

    if result.financial_statement_attachment:

        for statement_type, pages in (
            result.attachment_native_text_pages.items()
        ):
            if pages:
                print(
                    f"{statement_type}: pages {pages}"
                )
            else:
                print(
                    f"{statement_type}: not detected"
                )

    print("=" * 70)
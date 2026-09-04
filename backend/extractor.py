from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable
import re

from table_reconstructor import ReconstructedRow


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

@dataclass
class ExtractedRow:
    description: str
    current: float | int | None
    previous: float | int | None
    section: str
    row_type: str = "data"


@dataclass
class ExtractedStatement:
    statement_type: str
    current_year: int | None
    previous_year: int | None
    sections: dict[str, list[ExtractedRow]]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "current_year": self.current_year,
            "previous_year": self.previous_year,
            "sections": {
                name: [asdict(row) for row in rows]
                for name, rows in self.sections.items()
            },
            "validation": {
                "status": "warning" if self.warnings else "valid",
                "warnings": self.warnings,
            },
        }


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def normalize_description(text: str) -> str:
    """
    Normalize OCR-generated description text without changing its meaning.
    """
    value = text.strip()

    if not value:
        return ""

    value = re.sub(r"\s+", " ", value)

    # Common OCR spacing artifacts.
    value = re.sub(r"\s*/\s*", "/", value)
    value = re.sub(r"\(\s+", "(", value)
    value = re.sub(r"\s+\)", ")", value)

    return value.strip()


def normalized_search_text(text: str) -> str:
    """
    Produce a comparison-friendly representation for section detection.
    """
    value = normalize_description(text).lower()

    # OCR punctuation/spacing variations.
    value = value.replace("–", "-")
    value = value.replace("—", "-")
    value = re.sub(r"[^a-z0-9]+", " ", value)

    return re.sub(r"\s+", " ", value).strip()


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

SECTION_PATTERNS = {
    "operating": (
        "cash flows from operating activities",
        "cash flow from operating activities",
    ),
    "investing": (
        "cash flows from investing activities",
        "cash flow from investing activities",
    ),
    "financing": (
        "cash flows from financing activities",
        "cash flow from financing activities",
    ),
}


def detect_section(description: str) -> str | None:
    """
    Return the financial section represented by a row, if any.
    """
    text = normalized_search_text(description)

    if not text:
        return None

    for section, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if pattern in text:
                return section

    return None


# ---------------------------------------------------------------------------
# Header / footer filtering
# ---------------------------------------------------------------------------

HEADER_PATTERNS = (
    "cash flow statement",
    "cash flows statement",
    "particulars",
    "for the period",
    "for period",
    "current year",
    "previous year",
    "year ended",
    "year ending",
    "in thousands",
    "in lakhs",
    "in lacs",
    "in crores",
    "in millions",
    "in rupees",
    "rs.",
    "rs",
)

FOOTER_PATTERNS = (
    "pune",
    "place:",
    "date:",
    "authorised signatory",
    "authorized signatory",
    "director",
    "directors",
    "auditor",
    "signature",
)


def is_header_or_metadata(description: str) -> bool:
    text = normalized_search_text(description)

    if not text:
        return True

    for pattern in HEADER_PATTERNS:
        normalized_pattern = normalized_search_text(pattern)
        if normalized_pattern in text:
            return True

    return False


def is_footer_or_signature(description: str) -> bool:
    text = normalized_search_text(description)

    if not text:
        return True

    for pattern in FOOTER_PATTERNS:
        normalized_pattern = normalized_search_text(pattern)

        if text == normalized_pattern:
            return True

        if text.startswith(normalized_pattern + " "):
            return True

    return False


# ---------------------------------------------------------------------------
# Row classification
# ---------------------------------------------------------------------------

TOTAL_PATTERNS = (
    "cash generated from",
    "cash generated",
    "cash used in operations",
    "net cash from operating activities",
    "net cash from investing activities",
    "net cash from financing activities",
    "net change in cash",
    "net increase in cash",
    "net decrease in cash",
    "cash and cash equivalents",
)


def is_total_row(description: str) -> bool:
    text = normalized_search_text(description)

    return any(pattern in text for pattern in TOTAL_PATTERNS)


def has_numeric_value(row: ReconstructedRow) -> bool:
    return bool(
        getattr(row, "current_numbers", [])
        or getattr(row, "previous_numbers", [])
    )


def extract_numeric_value(row: ReconstructedRow, column: str):
    """
    Extract the selected numeric candidate from a reconstructed row.

    The table reconstructor stores candidate financial numbers. The
    extractor uses the first selected candidate and does not alter it.
    """
    attribute_name = (
        "current_numbers"
        if column == "current"
        else "previous_numbers"
    )

    candidates = getattr(row, attribute_name, [])

    if not candidates:
        return None

    candidate = candidates[0]

    if hasattr(candidate, "numeric_value"):
        return candidate.numeric_value

    if isinstance(candidate, dict):
        return candidate.get("numeric_value")

    if isinstance(candidate, (int, float)):
        return candidate

    return None


# ---------------------------------------------------------------------------
# Year extraction
# ---------------------------------------------------------------------------

YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def extract_years(rows: Iterable[ReconstructedRow]) -> tuple[int | None, int | None]:
    """
    Try to identify the current and previous reporting years from the
    reconstructed rows.

    Preference is given to rows containing explicit year labels.
    """
    years: list[int] = []

    for row in rows:
        description = normalize_description(getattr(row, "description", ""))

        for match in YEAR_PATTERN.findall(description):
            # findall with the current regex returns only the prefix.
            pass

        matches = re.findall(r"\b(?:19|20)\d{2}\b", description)

        for value in matches:
            year = int(value)

            if year not in years:
                years.append(year)

    if len(years) >= 2:
        years.sort(reverse=True)
        return years[0], years[1]

    return None, None


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_statement(
    rows: Iterable[ReconstructedRow],
    current_year: int | None = None,
    previous_year: int | None = None,
) -> ExtractedStatement:
    """
    Convert reconstructed rows into a clean cash-flow statement.

    This function intentionally does not:
      - perform OCR
      - reconstruct geometry
      - correct suspicious numbers
      - recalculate financial values

    Those responsibilities belong to earlier/later pipeline stages.
    """
    rows = list(rows)

    warnings: list[str] = []

    if not rows:
        warnings.append("No reconstructed rows were supplied.")

        return ExtractedStatement(
            statement_type="cash_flow_statement",
            current_year=current_year,
            previous_year=previous_year,
            sections={
                "operating": [],
                "investing": [],
                "financing": [],
            },
            warnings=warnings,
        )

    # Infer years only when they were not supplied explicitly.
    if current_year is None or previous_year is None:
        detected_current, detected_previous = extract_years(rows)

        if current_year is None:
            current_year = detected_current

        if previous_year is None:
            previous_year = detected_previous

    sections: dict[str, list[ExtractedRow]] = {
        "operating": [],
        "investing": [],
        "financing": [],
    }

    current_section: str | None = None
    seen_descriptions: set[tuple[str, str]] = set()

    for row in rows:
        description = normalize_description(
            getattr(row, "description", "")
        )

        if not description:
            continue

        # Section heading.
        detected_section = detect_section(description)

        if detected_section:
            current_section = detected_section
            continue

        # Ignore document metadata before/after the statement.
        if is_header_or_metadata(description):
            continue

        if is_footer_or_signature(description):
            continue

        # We only extract rows once a cash-flow section has been identified.
        if current_section is None:
            continue

        current_value = extract_numeric_value(row, "current")
        previous_value = extract_numeric_value(row, "previous")

        # A row without financial values is normally a subsection label or
        # OCR noise. Do not invent values for it.
        if current_value is None and previous_value is None:
            continue

        key = (
            current_section,
            normalized_search_text(description),
        )

        if key in seen_descriptions:
            warnings.append(
                f"Duplicate row ignored: '{description}' "
                f"in {current_section} section."
            )
            continue

        seen_descriptions.add(key)

        row_type = "total" if is_total_row(description) else "data"

        sections[current_section].append(
            ExtractedRow(
                description=description,
                current=current_value,
                previous=previous_value,
                section=current_section,
                row_type=row_type,
            )
        )

    # Basic structural warnings.
    for section_name, section_rows in sections.items():
        if not section_rows:
            warnings.append(
                f"No financial rows were extracted for "
                f"{section_name} activities."
            )

    if current_year is None:
        warnings.append("Current reporting year could not be determined.")

    if previous_year is None:
        warnings.append("Previous reporting year could not be determined.")

    return ExtractedStatement(
        statement_type="cash_flow_statement",
        current_year=current_year,
        previous_year=previous_year,
        sections=sections,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def extract_from_reconstruction(
    reconstruction_result: Any,
) -> dict[str, Any]:
    """
    Accept either:
      - a list of ReconstructedRow objects
      - an object containing a `rows` attribute
      - a dictionary containing `rows`

    Returns JSON-serializable structured data.
    """
    if reconstruction_result is None:
        rows = []
    elif isinstance(reconstruction_result, dict):
        rows = reconstruction_result.get("rows", [])
    elif hasattr(reconstruction_result, "rows"):
        rows = reconstruction_result.rows
    else:
        rows = reconstruction_result

    statement = extract_statement(rows)

    return statement.to_dict()


if __name__ == "__main__":
    print(
        "Pollux extractor module loaded successfully."
    )
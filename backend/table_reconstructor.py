from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from ocr import OCRResult
from financial_numbers import FinancialNumber, parse_financial_number


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_Y_TOLERANCE = 12.0

MIN_COLUMN_SEPARATION = 60.0

MAX_YEAR_COLUMN_DISTANCE = 180.0

DEFAULT_DESCRIPTION_X = 0.0


# ============================================================================
# Data structures
# ============================================================================


@dataclass
class OCRRow:
    """
    OCR elements grouped into one physical visual row.
    """

    y_center: float
    elements: list[OCRResult] = field(default_factory=list)


@dataclass
class TableColumns:
    """
    Dynamically detected financial statement column anchors.
    """

    description_x: float
    current_year_x: float
    previous_year_x: float

    current_year: int | None = None
    previous_year: int | None = None


@dataclass
class ClassifiedRow:
    """
    One physical OCR row classified into description and
    current/previous-year numeric candidates.
    """

    y_center: float

    description: list[OCRResult] = field(
        default_factory=list
    )

    current_year: list[OCRResult] = field(
        default_factory=list
    )

    previous_year: list[OCRResult] = field(
        default_factory=list
    )


@dataclass
class ReconstructedRow:
    """
    Higher-level financial statement row.

    Multiple numeric candidates are preserved intentionally.
    """

    y_center: float

    description: str

    current_candidates: list[str] = field(
        default_factory=list
    )

    previous_candidates: list[str] = field(
        default_factory=list
    )

    current_confidences: list[float] = field(
        default_factory=list
    )

    previous_confidences: list[float] = field(
        default_factory=list
    )

    current_numbers: list[FinancialNumber] = field(
        default_factory=list
    )

    previous_numbers: list[FinancialNumber] = field(
        default_factory=list
    )

    ambiguous_current: bool = False

    ambiguous_previous: bool = False


# ============================================================================
# Bounding-box helpers
# ============================================================================


def _x_values(
    result: OCRResult,
) -> list[float]:
    """
    Extract valid X coordinates from an OCR bounding box.
    """

    if not result.bbox:
        return []

    values: list[float] = []

    for point in result.bbox:
        if len(point) < 2:
            continue

        try:
            values.append(float(point[0]))
        except (TypeError, ValueError):
            continue

    return values


def _y_values(
    result: OCRResult,
) -> list[float]:
    """
    Extract valid Y coordinates from an OCR bounding box.
    """

    if not result.bbox:
        return []

    values: list[float] = []

    for point in result.bbox:
        if len(point) < 2:
            continue

        try:
            values.append(float(point[1]))
        except (TypeError, ValueError):
            continue

    return values


def get_x_start(
    result: OCRResult,
) -> float:
    """
    Return the left-most X coordinate.
    """

    values = _x_values(result)

    if not values:
        return 0.0

    return min(values)


def get_x_end(
    result: OCRResult,
) -> float:
    """
    Return the right-most X coordinate.
    """

    values = _x_values(result)

    if not values:
        return 0.0

    return max(values)


def get_x_center(
    result: OCRResult,
) -> float:
    """
    Return the horizontal center of an OCR bounding box.
    """

    values = _x_values(result)

    if not values:
        return 0.0

    return (
        min(values) + max(values)
    ) / 2.0


def get_y_start(
    result: OCRResult,
) -> float:
    """
    Return the top-most Y coordinate.
    """

    values = _y_values(result)

    if not values:
        return 0.0

    return min(values)


def get_y_end(
    result: OCRResult,
) -> float:
    """
    Return the bottom-most Y coordinate.
    """

    values = _y_values(result)

    if not values:
        return 0.0

    return max(values)


def get_y_center(
    result: OCRResult,
) -> float:
    """
    Return the vertical center of an OCR bounding box.
    """

    values = _y_values(result)

    if not values:
        return 0.0

    return (
        min(values) + max(values)
    ) / 2.0


# ============================================================================
# Physical OCR row grouping
# ============================================================================


def group_into_rows(
    results: Iterable[OCRResult],
    y_tolerance: float = DEFAULT_Y_TOLERANCE,
) -> list[OCRRow]:
    """
    Group OCR detections that share approximately the same
    vertical position.

    This operates only on physical OCR alignment.
    It does not merge multiline descriptions.
    """

    sorted_results = sorted(
        results,
        key=lambda result: (
            get_y_center(result),
            get_x_start(result),
        ),
    )

    rows: list[OCRRow] = []

    for result in sorted_results:
        y_center = get_y_center(result)

        if not rows:
            rows.append(
                OCRRow(
                    y_center=y_center,
                    elements=[result],
                )
            )
            continue

        current_row = rows[-1]

        if (
            abs(
                y_center - current_row.y_center
            )
            <= y_tolerance
        ):
            current_row.elements.append(
                result
            )

            current_row.y_center = (
                sum(
                    get_y_center(element)
                    for element in current_row.elements
                )
                / len(current_row.elements)
            )

        else:
            rows.append(
                OCRRow(
                    y_center=y_center,
                    elements=[result],
                )
            )

    return rows


# ============================================================================
# Row ordering / text
# ============================================================================


def sort_row_elements(
    row: OCRRow,
) -> list[OCRResult]:
    """
    Sort OCR elements from left to right.
    """

    return sorted(
        row.elements,
        key=get_x_start,
    )


def get_row_elements_with_positions(
    row: OCRRow,
) -> list[tuple[OCRResult, float]]:
    """
    Return row elements with their X centers.
    """

    positioned = [
        (
            element,
            get_x_center(element),
        )
        for element in row.elements
    ]

    return sorted(
        positioned,
        key=lambda item: item[1],
    )


def row_text(
    row: OCRRow,
) -> str:
    """
    Return OCR text in left-to-right order.
    """

    return " ".join(
        element.text.strip()
        for element in sort_row_elements(row)
        if element.text.strip()
    )


# ============================================================================
# Header / year detection
# ============================================================================


def _extract_year(
    text: str,
) -> int | None:
    """
    Extract a year from a 31-Mar-YYYY style date.
    """

    normalized = " ".join(
        text.lower().split()
    )

    match = re.search(
        r"\b31\s*[-/ ]\s*mar\s*[-/ ]\s*(\d{4})\b",
        normalized,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return int(match.group(1))


def find_year_header_anchors(
    rows: Iterable[OCRRow],
) -> TableColumns | None:
    """Detect the two adjacent financial years and the description anchor.

    Year labels must occur on the same physical OCR row. "Particulars" may
    occur on a neighboring header row because scanned documents frequently
    split multi-line headers during OCR.
    """
    all_rows = list(rows)
    candidates = []

    for row in all_rows:
        years = []
        for element, x in get_row_elements_with_positions(row):
            year = _extract_year(element.text)
            if year is not None:
                years.append((year, element, x))
        if len(years) < 2:
            continue

        years.sort(key=lambda item: item[2])
        for i, left in enumerate(years):
            for right in years[i + 1:]:
                if abs(left[0] - right[0]) != 1:
                    continue
                separation = abs(left[2] - right[2])
                if separation < MIN_COLUMN_SEPARATION:
                    continue
                confidence = float(left[1].confidence) + float(right[1].confidence)
                candidates.append((confidence, row, left, right))

    if not candidates:
        return None

    _, header_row, left, right = max(
        candidates,
        key=lambda item: item[0],
    )

    left_year, _, left_x = left
    right_year, _, right_x = right

    if left_year >= right_year:
        current_year, current_x = left_year, left_x
        previous_year, previous_x = right_year, right_x
    else:
        current_year, current_x = right_year, right_x
        previous_year, previous_x = left_year, left_x

    # "Particulars" is often on the row immediately above the date row.
    description_x = None
    for row in all_rows:
        if abs(row.y_center - header_row.y_center) > 100.0:
            continue
        for element, x in get_row_elements_with_positions(row):
            text = " ".join(element.text.lower().split())
            if "particulars" in text:
                description_x = x
                break
        if description_x is not None:
            break

    if description_x is None:
        # Use the left-most plausible header text before the numeric columns.
        header_candidates = []
        for row in all_rows:
            if abs(row.y_center - header_row.y_center) > 100.0:
                continue
            for element, x in get_row_elements_with_positions(row):
                text = element.text.strip()
                if not text or _extract_year(text) is not None:
                    continue
                if is_numeric_candidate(text):
                    continue
                if x < min(current_x, previous_x):
                    header_candidates.append(x)
        if header_candidates:
            description_x = min(header_candidates)

    if description_x is None:
        # Financial statement descriptions are normally left of the first
        # numeric column. Keep this as a last-resort geometric anchor.
        description_x = max(0.0, min(current_x, previous_x) * 0.50)

    return TableColumns(
        description_x=description_x,
        current_year_x=current_x,
        previous_year_x=previous_x,
        current_year=current_year,
        previous_year=previous_year,
    )


# ============================================================================
# Numeric recognition
# ============================================================================


def is_numeric_candidate(
    text: str,
) -> bool:
    """
    Determine whether OCR text resembles a financial number.
    """

    cleaned = text.strip()

    if not cleaned:
        return False

    cleaned = cleaned.replace(
        "Rs.",
        "",
    )

    cleaned = cleaned.replace(
        "Rs",
        "",
    )

    cleaned = cleaned.strip()

    pattern = re.compile(
        r"""
        ^
        [(\[]?
        \s*
        [-+]?
        \d
        [\d,.\s]*
        \s*
        [)\]]?
        $
        """,
        re.VERBOSE,
    )

    return bool(
        pattern.match(cleaned)
    )


def normalize_numeric_text(
    text: str,
) -> str:
    """
    Normalize OCR financial-number formatting.

    Parentheses are preserved because they represent negative values.
    Common OCR errors such as ``(1.014`` are normalized to ``(1,014)``.
    """
    parsed = parse_financial_number(text)

    if parsed is not None:
        return parsed.normalized_text

    # Preserve the previous conservative fallback for values that are
    # recognized by the table classifier but rejected by the parser.
    value = text.strip()

    value = value.replace("Rs.", "", 1).strip()
    value = value.replace("Rs", "", 1).strip()
    value = value.replace("[", "(")
    value = value.replace("]", ")")

    match = re.fullmatch(
        r"(\(?\s*[-+]?\s*\d{1,3})\.(\d{3})\s*\)?",
        value,
    )

    if match:
        prefix = match.group(1)
        suffix = match.group(2)
        negative = value.startswith("(")

        normalized = (
            f"{prefix.replace('.', '')},{suffix}"
        )

        if negative and not normalized.startswith("("):
            normalized = f"({normalized})"

        return normalized

    if value.startswith("(") and not value.endswith(")"):
        value += ")"

    return value


def numeric_value_key(
    text: str,
) -> str:
    """
    Generate a normalized comparison key.
    """

    value = normalize_numeric_text(
        text
    )

    negative = (
        value.startswith("(")
        and value.endswith(")")
    )

    value = (
        value.replace("(", "")
        .replace(")", "")
        .replace(",", "")
        .replace(" ", "")
    )

    if negative:
        return f"-{value}"

    return value


# ============================================================================
# Column classification
# ============================================================================


def classify_x_position(
    x_center: float,
    columns: TableColumns,
) -> str:
    """
    Classify an X position using the nearest table anchor.
    """

    distances = {
        "description": abs(
            x_center
            - columns.description_x
        ),
        "current_year": abs(
            x_center
            - columns.current_year_x
        ),
        "previous_year": abs(
            x_center
            - columns.previous_year_x
        ),
    }

    return min(
        distances,
        key=distances.get,
    )


def _classify_numeric_candidate(
    result: OCRResult,
    columns: TableColumns,
) -> str | None:
    """
    Assign a numeric OCR element to the nearest year column.
    """

    x_center = get_x_center(
        result
    )

    current_distance = abs(
        x_center
        - columns.current_year_x
    )

    previous_distance = abs(
        x_center
        - columns.previous_year_x
    )

    candidates = [
        (
            "current_year",
            current_distance,
        ),
        (
            "previous_year",
            previous_distance,
        ),
    ]

    column, distance = min(
        candidates,
        key=lambda item: item[1],
    )

    if (
        distance
        > MAX_YEAR_COLUMN_DISTANCE
    ):
        return None

    return column


def classify_row(
    row: OCRRow,
    columns: TableColumns,
) -> ClassifiedRow:
    """Classify OCR elements by financial table geometry.

    Numeric-looking elements are assigned to the nearest year column.
    Non-numeric elements remain description text. This also handles OCR
    that accidentally places a number in the same OCR text line as a label.
    """
    description = []
    current_year = []
    previous_year = []

    for element in row.elements:
        text = element.text.strip()
        if not text:
            continue

        if is_numeric_candidate(text):
            numeric_column = _classify_numeric_candidate(element, columns)
            if numeric_column == "current_year":
                current_year.append(element)
                continue
            if numeric_column == "previous_year":
                previous_year.append(element)
                continue

        # Some OCR engines return "label 10,454" as one detection. Extract
        # a trailing financial number without losing the label.
        match = re.match(
            r"^(.*?)(?:\\s+)([\\(\\[]?[-+]?\\d[\\d,./ ]*[\\)\\]]?)$",
            text,
        )
        if match and is_numeric_candidate(match.group(2)):
            number_text = match.group(2)
            label_text = match.group(1).strip()
            numeric_column = _classify_numeric_candidate(element, columns)
            if numeric_column == "current_year":
                synthetic = OCRResult(
                    text=number_text,
                    confidence=element.confidence,
                    bbox=element.bbox,
                    page_number=element.page_number,
                )
                current_year.append(synthetic)
                if label_text:
                    description.append(
                        OCRResult(
                            text=label_text,
                            confidence=element.confidence,
                            bbox=element.bbox,
                            page_number=element.page_number,
                        )
                    )
                continue
            if numeric_column == "previous_year":
                synthetic = OCRResult(
                    text=number_text,
                    confidence=element.confidence,
                    bbox=element.bbox,
                    page_number=element.page_number,
                )
                previous_year.append(synthetic)
                if label_text:
                    description.append(
                        OCRResult(
                            text=label_text,
                            confidence=element.confidence,
                            bbox=element.bbox,
                            page_number=element.page_number,
                        )
                    )
                continue

        description.append(element)

    description.sort(key=get_x_start)
    current_year.sort(key=get_x_start)
    previous_year.sort(key=get_x_start)

    return ClassifiedRow(
        y_center=row.y_center,
        description=description,
        current_year=current_year,
        previous_year=previous_year,
    )


# ============================================================================
# Description reconstruction
# ============================================================================


def classified_row_text(
    elements: Sequence[OCRResult],
) -> str:
    """
    Combine OCR elements from left to right.
    """

    return " ".join(
        element.text.strip()
        for element in sorted(
            elements,
            key=get_x_start,
        )
        if element.text.strip()
    )


def _description_start_x(
    row: ClassifiedRow,
) -> float | None:
    """
    Return the left-most X position of description text.
    """

    if not row.description:
        return None

    return min(
        get_x_start(element)
        for element in row.description
    )


def _description_end_x(
    row: ClassifiedRow,
) -> float | None:
    """
    Return the right-most X position of description text.
    """

    if not row.description:
        return None

    return max(
        get_x_end(element)
        for element in row.description
    )


def _description_last_word(
    row: ClassifiedRow,
) -> str:
    """
    Return the final word of a description.
    """

    text = classified_row_text(
        row.description
    )

    words = text.strip(
        " :;,.-"
    ).split()

    if not words:
        return ""

    return words[-1].lower()


def _description_first_word(
    row: ClassifiedRow,
) -> str:
    """
    Return the first word of a description.
    """

    text = classified_row_text(
        row.description
    )

    words = text.strip(
        " :;,.-"
    ).split()

    if not words:
        return ""

    return words[0].lower()


def _has_numeric_candidates(
    row: ClassifiedRow,
) -> bool:
    """
    Return True if the row contains any financial number.
    """

    return bool(
        row.current_year
        or row.previous_year
    )


def _looks_like_section_heading(
    row: ClassifiedRow,
) -> bool:
    """
    Identify common financial-statement section headings.

    Examples:

        Cash flows from operating activities
        Cash flows from investing activities
        Cash flows from financing activities
        Adjustments for:
    """

    text = classified_row_text(
        row.description
    ).lower()

    if not text:
        return False

    section_patterns = (
        "cash flows from operating activities",
        "cash flows from investing activities",
        "cash flows from financing activities",
        "adjustments for",
    )

    return any(
        pattern in text
        for pattern in section_patterns
    )


def _can_merge_as_continuation(
    previous: ClassifiedRow,
    current: ClassifiedRow,
    max_line_gap: float,
) -> bool:
    """
    Conservative multiline-description detector.

    A continuation is accepted only when:

    1. Both rows contain description text.
    2. They are vertically close.
    3. The previous row strongly looks incomplete.
    4. The current row does not look like a new financial row.
    5. Section headings are never merged.
    """

    if not previous.description:
        return False

    if not current.description:
        return False

    vertical_gap = (
        current.y_center
        - previous.y_center
    )

    if (
        vertical_gap < 0
        or vertical_gap > max_line_gap
    ):
        return False

    if _looks_like_section_heading(
        previous
    ):
        return False

    if _looks_like_section_heading(
        current
    ):
        return False

    previous_has_numbers = (
        _has_numeric_candidates(
            previous
        )
    )

    current_has_numbers = (
        _has_numeric_candidates(
            current
        )
    )

    # If both rows already contain financial numbers,
    # they are separate financial rows.
    if (
        previous_has_numbers
        and current_has_numbers
    ):
        return False

    previous_text = classified_row_text(
        previous.description
    ).strip()

    current_text = classified_row_text(
        current.description
    ).strip()

    if not previous_text or not current_text:
        return False

    previous_last = (
        _description_last_word(
            previous
        )
    )

    current_first = (
        _description_first_word(
            current
        )
    )

    # Strong continuation indicators.
    continuation_endings = {
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "from",
        "with",
        "on",
        "the",
    }

    if previous_last in continuation_endings:
        return True

    # A line ending with a hyphen is almost certainly wrapped.
    if previous_text.endswith("-"):
        return True

    # If the current line is indented relative to the previous line,
    # that is strong evidence of wrapping.
    previous_start = (
        _description_start_x(
            previous
        )
    )

    current_start = (
        _description_start_x(
            current
        )
    )

    if (
        previous_start is not None
        and current_start is not None
        and current_start
        > previous_start + 15.0
    ):
        return True

    # A line with no numbers following an incomplete description
    # can be a continuation. Keep this conservative.
    if not previous_has_numbers and not current_has_numbers:
        return (
            current_first
            not in {
                "cash",
                "profit",
                "net",
                "purchase",
                "proceeds",
                "increase",
                "(increase)",
                "direct",
                "operating",
                "depreciation",
            }
        )

    return False


def merge_multiline_rows(
    rows: Sequence[ClassifiedRow],
    max_line_gap: float = 38.0,
) -> list[ClassifiedRow]:
    """
    Merge only high-confidence multiline descriptions.

    Numeric candidates are preserved exactly as detected.
    """

    if not rows:
        return []

    merged: list[ClassifiedRow] = []

    for row in rows:
        if not merged:
            merged.append(row)
            continue

        previous = merged[-1]

        if _can_merge_as_continuation(
            previous,
            row,
            max_line_gap,
        ):
            previous.description.extend(
                row.description
            )

            previous.current_year.extend(
                row.current_year
            )

            previous.previous_year.extend(
                row.previous_year
            )

            previous.description.sort(
                key=get_x_start
            )

            previous.current_year.sort(
                key=get_x_start
            )

            previous.previous_year.sort(
                key=get_x_start
            )

            continue

        merged.append(row)

    return merged


# ============================================================================
# Candidate cleanup
# ============================================================================


def _deduplicate_candidates(
    elements: Sequence[OCRResult],
) -> list[OCRResult]:
    """
    Remove duplicate OCR detections only when both their normalized
    value and physical position are effectively identical.
    """

    unique: list[OCRResult] = []

    for element in elements:
        key = numeric_value_key(
            element.text
        )

        x = get_x_center(
            element
        )

        y = get_y_center(
            element
        )

        duplicate = False

        for existing in unique:
            existing_key = (
                numeric_value_key(
                    existing.text
                )
            )

            if key != existing_key:
                continue

            existing_x = get_x_center(
                existing
            )

            existing_y = get_y_center(
                existing
            )

            if (
                abs(
                    x - existing_x
                )
                <= 20.0
                and abs(
                    y - existing_y
                )
                <= 10.0
            ):
                duplicate = True
                break

        if not duplicate:
            unique.append(
                element
            )

    return unique


def _candidate_texts(
    elements: Sequence[OCRResult],
) -> tuple[
    list[str],
    list[float],
]:
    """
    Normalize numeric candidates and return their confidence scores.
    """

    elements = _deduplicate_candidates(
        elements
    )

    texts: list[str] = []

    confidences: list[float] = []

    for element in elements:
        texts.append(
            normalize_numeric_text(
                element.text
            )
        )

        confidences.append(
            float(element.confidence)
        )

    return (
        texts,
        confidences,
    )


def _candidate_numbers(
    elements: Sequence[OCRResult],
) -> tuple[
    list[str],
    list[FinancialNumber],
    list[float],
]:
    """
    Deduplicate OCR numeric detections and parse them into typed
    financial numbers.

    The string representation is retained for diagnostics while the
    FinancialNumber objects provide normalized numeric values and signs.
    """
    elements = _deduplicate_candidates(elements)

    texts: list[str] = []
    numbers: list[FinancialNumber] = []
    confidences: list[float] = []

    for element in elements:
        parsed = parse_financial_number(
            element.text,
            confidence=float(element.confidence),
        )

        if parsed is None:
            continue

        texts.append(parsed.normalized_text)
        numbers.append(parsed)
        confidences.append(parsed.confidence)

    return texts, numbers, confidences

def remove_duplicate_numeric_rows(
    rows: Sequence[ClassifiedRow],
    max_y_gap: float = 35.0,
) -> list[ClassifiedRow]:
    """Remove a number-only OCR duplicate immediately following a real row."""
    if not rows:
        return []

    cleaned = []
    for row in rows:
        if cleaned:
            previous = cleaned[-1]
            if (
                not row.description
                and previous.description
                and _has_numeric_candidates(row)
                and _has_numeric_candidates(previous)
                and 0 <= row.y_center - previous.y_center <= max_y_gap
            ):
                current_a = sorted(numeric_value_key(x.text) for x in row.current_year)
                current_b = sorted(numeric_value_key(x.text) for x in previous.current_year)
                previous_a = sorted(numeric_value_key(x.text) for x in row.previous_year)
                previous_b = sorted(numeric_value_key(x.text) for x in previous.previous_year)
                if current_a == current_b and previous_a == previous_b:
                    continue
        cleaned.append(row)
    return cleaned


def _select_best_numeric_candidate(
    elements: Sequence[OCRResult],
    anchor_x: float,
) -> OCRResult | None:
    """Select the candidate closest to its expected numeric column."""
    unique = _deduplicate_candidates(elements)
    if not unique:
        return None
    return min(
        unique,
        key=lambda element: (
            abs(get_x_center(element) - anchor_x),
            -float(element.confidence),
        ),
    )


def _selected_candidate_numbers(
    elements: Sequence[OCRResult],
    anchor_x: float,
) -> tuple[list[str], list[FinancialNumber], list[float]]:
    selected = _select_best_numeric_candidate(elements, anchor_x)
    if selected is None:
        return [], [], []

    parsed = parse_financial_number(
        selected.text,
        confidence=float(selected.confidence),
    )
    if parsed is None:
        return [], [], []

    return [parsed.normalized_text], [parsed], [parsed.confidence]


# ============================================================================
# Complete reconstruction
# ============================================================================


def reconstruct_rows(
    results: Iterable[OCRResult],
    y_tolerance: float = DEFAULT_Y_TOLERANCE,
) -> tuple[
    TableColumns | None,
    list[ReconstructedRow],
]:
    """
    Execute the geometry-based table reconstruction pipeline.
    """

    results = list(results)

    physical_rows = group_into_rows(
        results,
        y_tolerance=y_tolerance,
    )

    columns = find_year_header_anchors(
        physical_rows
    )

    if columns is None:
        return None, []

    classified_rows: list[
        ClassifiedRow
    ] = []

    for row in physical_rows:
        classified_rows.append(
            classify_row(
                row,
                columns,
            )
        )

    classified_rows = (
        merge_multiline_rows(
            classified_rows
        )
    )

    classified_rows = (
        remove_duplicate_numeric_rows(
            classified_rows
        )
    )

    reconstructed: list[
        ReconstructedRow
    ] = []

    for row in classified_rows:
        description = (
            classified_row_text(
                row.description
            )
        )

        (
            current_texts,
            current_numbers,
            current_confidences,
        ) = _selected_candidate_numbers(
            row.current_year,
            columns.current_year_x,
        )

        (
            previous_texts,
            previous_numbers,
            previous_confidences,
        ) = _selected_candidate_numbers(
            row.previous_year,
            columns.previous_year_x,
        )

        reconstructed.append(
            ReconstructedRow(
                y_center=row.y_center,
                description=description,
                current_candidates=current_texts,
                previous_candidates=previous_texts,
                current_numbers=current_numbers,
                previous_numbers=previous_numbers,
                current_confidences=current_confidences,
                previous_confidences=previous_confidences,
                ambiguous_current=(
                    len(current_texts) > 1
                ),
                ambiguous_previous=(
                    len(previous_texts) > 1
                ),
            )
        )

    return (
        columns,
        reconstructed,
    )


# ============================================================================
# Debug helpers
# ============================================================================


def format_row_debug(
    row: OCRRow,
) -> str:
    """
    Format a physical OCR row with X coordinates.
    """

    parts: list[str] = []

    for (
        element,
        x_center,
    ) in get_row_elements_with_positions(
        row
    ):
        parts.append(
            f"{element.text} "
            f"[x={x_center:.1f}]"
        )

    return " | ".join(parts)


def format_classified_row_debug(
    row: ClassifiedRow,
) -> str:
    """
    Format a classified row for diagnostics.
    """

    description = (
        classified_row_text(
            row.description
        )
    )

    current = [
        (
            f"{element.text} "
            f"[x={get_x_center(element):.1f}]"
        )
        for element in row.current_year
    ]

    previous = [
        (
            f"{element.text} "
            f"[x={get_x_center(element):.1f}]"
        )
        for element in row.previous_year
    ]

    return (
        f"DESCRIPTION: "
        f"{description or '-'} | "
        f"CURRENT: "
        f"{', '.join(current) or '-'} | "
        f"PREVIOUS: "
        f"{', '.join(previous) or '-'}"
    )


def format_reconstructed_row(
    row: ReconstructedRow,
    index: int,
) -> str:
    """
    Format a reconstructed row for diagnostics.

    Shows both normalized OCR strings and parsed numeric values.
    """
    def format_numbers(
        candidates: list[str],
        numbers: list[FinancialNumber],
    ) -> str:
        if not numbers:
            return "-"

        parts: list[str] = []

        for candidate, number in zip(candidates, numbers):
            parts.append(
                f"{candidate} -> {number.numeric_value}"
            )

        return ", ".join(parts)

    current = format_numbers(
        row.current_candidates,
        row.current_numbers,
    )

    previous = format_numbers(
        row.previous_candidates,
        row.previous_numbers,
    )

    flags: list[str] = []

    if row.ambiguous_current:
        flags.append("AMBIGUOUS_CURRENT")

    if row.ambiguous_previous:
        flags.append("AMBIGUOUS_PREVIOUS")

    flag_text = (
        f" [{', '.join(flags)}]"
        if flags
        else ""
    )

    return (
        f"ROW {index:02d} "
        f"| Y={row.y_center:8.2f} "
        f"| {row.description or '-'} "
        f"| CURRENT={current} "
        f"| PREVIOUS={previous}"
        f"{flag_text}"
    )


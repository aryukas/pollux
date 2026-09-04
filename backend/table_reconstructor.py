from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from ocr import OCRResult


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
    """
    Detect current and previous year column anchors.
    """

    year_headers: list[
        tuple[int, float, float]
    ] = []

    description_x: float | None = None

    for row in rows:
        for element, x_center in (
            get_row_elements_with_positions(row)
        ):
            text = " ".join(
                element.text.lower().split()
            )

            if "particulars" in text:
                description_x = x_center

            year = _extract_year(text)

            if year is not None:
                year_headers.append(
                    (
                        year,
                        x_center,
                        get_y_center(element),
                    )
                )

    if description_x is None:
        description_x = DEFAULT_DESCRIPTION_X

    if not year_headers:
        return None

    unique_headers: list[
        tuple[int, float, float]
    ] = []

    for year, x_center, y_center in year_headers:
        duplicate = False

        for (
            existing_year,
            existing_x,
            existing_y,
        ) in unique_headers:
            if (
                year == existing_year
                and abs(
                    x_center - existing_x
                )
                < 40.0
                and abs(
                    y_center - existing_y
                )
                < 40.0
            ):
                duplicate = True
                break

        if not duplicate:
            unique_headers.append(
                (
                    year,
                    x_center,
                    y_center,
                )
            )

    if len(unique_headers) < 2:
        return None

    current_year, current_x, _ = (
        unique_headers[0]
    )

    previous_year, previous_x, _ = (
        unique_headers[1]
    )

    if (
        abs(
            current_x - previous_x
        )
        < MIN_COLUMN_SEPARATION
    ):
        return None

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
    Normalize common OCR formatting errors.

    Example:

        (1.014) -> (1,014)

    The function remains conservative and does not
    invent decimal precision.
    """

    value = text.strip()

    value = value.replace(
        "Rs.",
        "",
    ).strip()

    value = value.replace(
        "Rs",
        "",
    ).strip()

    value = value.replace(
        "[",
        "(",
    )

    value = value.replace(
        "]",
        ")",
    )

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

        if (
            negative
            and not normalized.startswith("(")
        ):
            normalized = (
                f"({normalized})"
            )

        return normalized

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
    """
    Separate one physical OCR row into:

        description
        current-year candidates
        previous-year candidates

    No numeric candidate is silently discarded.
    """

    description: list[OCRResult] = []

    current_year: list[OCRResult] = []

    previous_year: list[OCRResult] = []

    for element in row.elements:
        text = element.text.strip()

        if not text:
            continue

        if is_numeric_candidate(text):
            numeric_column = (
                _classify_numeric_candidate(
                    element,
                    columns,
                )
            )

            if (
                numeric_column
                == "current_year"
            ):
                current_year.append(
                    element
                )
                continue

            if (
                numeric_column
                == "previous_year"
            ):
                previous_year.append(
                    element
                )
                continue

        description.append(
            element
        )

    description.sort(
        key=get_x_start
    )

    current_year.sort(
        key=get_x_start
    )

    previous_year.sort(
        key=get_x_start
    )

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
            current_confidences,
        ) = _candidate_texts(
            row.current_year
        )

        (
            previous_texts,
            previous_confidences,
        ) = _candidate_texts(
            row.previous_year
        )

        reconstructed.append(
            ReconstructedRow(
                y_center=row.y_center,
                description=description,
                current_candidates=current_texts,
                previous_candidates=previous_texts,
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
    """

    current = ", ".join(
        row.current_candidates
    ) or "-"

    previous = ", ".join(
        row.previous_candidates
    ) or "-"

    flags: list[str] = []

    if row.ambiguous_current:
        flags.append(
            "AMBIGUOUS_CURRENT"
        )

    if row.ambiguous_previous:
        flags.append(
            "AMBIGUOUS_PREVIOUS"
        )

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
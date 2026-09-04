from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from table_reconstructor import ReconstructedRow


# ============================================================================
# Configuration
# ============================================================================

MIN_OCR_CONFIDENCE = 0.60
DUPLICATE_Y_TOLERANCE = 20.0
ARITHMETIC_TOLERANCE = 1.0


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class ValidationIssue:
    level: str
    code: str
    message: str
    row_index: int | None = None


@dataclass
class ValidationResult:
    status: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        return [
            issue.message
            for issue in self.issues
            if issue.level == "warning"
        ]

    @property
    def errors(self) -> list[str]:
        return [
            issue.message
            for issue in self.issues
            if issue.level == "error"
        ]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "warnings": self.warnings,
            "errors": self.errors,
            "issues": [
                {
                    "level": issue.level,
                    "code": issue.code,
                    "message": issue.message,
                    "row_index": issue.row_index,
                }
                for issue in self.issues
            ],
        }


# ============================================================================
# Helpers
# ============================================================================

def _description(row: ReconstructedRow) -> str:
    return " ".join(
        str(row.description or "").lower().split()
    )


def _value(
    row: ReconstructedRow,
    column: str,
) -> int | float | None:
    numbers = (
        row.current_numbers
        if column == "current"
        else row.previous_numbers
    )

    if not numbers:
        return None

    return numbers[0].numeric_value


def _confidence(
    row: ReconstructedRow,
    column: str,
) -> float | None:
    confidences = (
        row.current_confidences
        if column == "current"
        else row.previous_confidences
    )

    if not confidences:
        return None

    return float(confidences[0])


def _add_issue(
    issues: list[ValidationIssue],
    level: str,
    code: str,
    message: str,
    row_index: int | None = None,
) -> None:
    issues.append(
        ValidationIssue(
            level=level,
            code=code,
            message=message,
            row_index=row_index,
        )
    )


# ============================================================================
# Number validation
# ============================================================================

def validate_numeric_values(
    rows: Sequence[ReconstructedRow],
    issues: list[ValidationIssue],
) -> None:
    for index, row in enumerate(rows, start=1):

        for column in ("current", "previous"):
            numbers = (
                row.current_numbers
                if column == "current"
                else row.previous_numbers
            )

            candidates = (
                row.current_candidates
                if column == "current"
                else row.previous_candidates
            )

            if candidates and not numbers:
                _add_issue(
                    issues,
                    "error",
                    "INVALID_NUMBER",
                    (
                        f"Row {index} ('{row.description}') contains "
                        f"a numeric candidate for {column} year that "
                        f"could not be parsed."
                    ),
                    index,
                )


# ============================================================================
# Missing value validation
# ============================================================================

def validate_missing_values(
    rows: Sequence[ReconstructedRow],
    issues: list[ValidationIssue],
) -> None:
    for index, row in enumerate(rows, start=1):

        current = _value(row, "current")
        previous = _value(row, "previous")

        if current is None and previous is None:
            continue

        if current is None and previous is not None:
            _add_issue(
                issues,
                "warning",
                "MISSING_CURRENT_VALUE",
                (
                    f"Row {index} ('{row.description}') is missing "
                    "the current-year value."
                ),
                index,
            )

        if previous is None and current is not None:
            _add_issue(
                issues,
                "warning",
                "MISSING_PREVIOUS_VALUE",
                (
                    f"Row {index} ('{row.description}') is missing "
                    "the previous-year value."
                ),
                index,
            )


# ============================================================================
# OCR confidence validation
# ============================================================================

def validate_confidence(
    rows: Sequence[ReconstructedRow],
    issues: list[ValidationIssue],
) -> None:
    for index, row in enumerate(rows, start=1):

        for column in ("current", "previous"):
            confidence = _confidence(row, column)

            if confidence is None:
                continue

            if confidence < MIN_OCR_CONFIDENCE:
                _add_issue(
                    issues,
                    "warning",
                    "LOW_OCR_CONFIDENCE",
                    (
                        f"Row {index} ('{row.description}') has low "
                        f"OCR confidence ({confidence:.2f}) for "
                        f"the {column}-year value."
                    ),
                    index,
                )


# ============================================================================
# Ambiguity validation
# ============================================================================

def validate_ambiguity(
    rows: Sequence[ReconstructedRow],
    issues: list[ValidationIssue],
) -> None:
    for index, row in enumerate(rows, start=1):

        if row.ambiguous_current:
            _add_issue(
                issues,
                "warning",
                "AMBIGUOUS_CURRENT",
                (
                    f"Row {index} ('{row.description}') contains "
                    "multiple possible current-year numeric candidates."
                ),
                index,
            )

        if row.ambiguous_previous:
            _add_issue(
                issues,
                "warning",
                "AMBIGUOUS_PREVIOUS",
                (
                    f"Row {index} ('{row.description}') contains "
                    "multiple possible previous-year numeric candidates."
                ),
                index,
            )


# ============================================================================
# Duplicate row validation
# ============================================================================

def validate_duplicate_rows(
    rows: Sequence[ReconstructedRow],
    issues: list[ValidationIssue],
) -> None:
    seen: dict[str, int] = {}

    for index, row in enumerate(rows, start=1):
        description = _description(row)

        if not description:
            continue

        if description in seen:
            previous_index = seen[description]

            _add_issue(
                issues,
                "warning",
                "DUPLICATE_ROW",
                (
                    f"Duplicate row description detected at rows "
                    f"{previous_index} and {index}: "
                    f"'{row.description}'."
                ),
                index,
            )
        else:
            seen[description] = index


# ============================================================================
# Section / subtotal validation
# ============================================================================

def _find_row(
    rows: Sequence[ReconstructedRow],
    text: str,
) -> ReconstructedRow | None:
    text = text.lower()

    for row in rows:
        description = _description(row)

        if text in description:
            return row

    return None


def _check_arithmetic(
    rows: Sequence[ReconstructedRow],
    total_description: str,
    component_descriptions: Sequence[str],
    issues: list[ValidationIssue],
) -> None:
    total_row = _find_row(rows, total_description)

    if total_row is None:
        return

    for column in ("current", "previous"):
        total = _value(total_row, column)

        if total is None:
            continue

        values = []

        for description in component_descriptions:
            row = _find_row(rows, description)

            if row is None:
                return

            value = _value(row, column)

            if value is None:
                return

            values.append(value)

        calculated = sum(values)

        if abs(calculated - total) >= ARITHMETIC_TOLERANCE:
            _add_issue(
                issues,
                "warning",
                "ARITHMETIC_MISMATCH",
                (
                    f"'{total_row.description}' does not reconcile "
                    f"for the {column} year. "
                    f"Expected {calculated}, extracted {total}."
                ),
            )


def validate_operating_totals(
    rows: Sequence[ReconstructedRow],
    issues: list[ValidationIssue],
) -> None:
    """
    Validate the basic operating cash-flow subtotal.

    This check is intentionally conservative. If a required component
    is absent, no conclusion is made.
    """

    _check_arithmetic(
        rows,
        "operating profit before working capital changes",
        [
            "profit before taxation",
            "depreciation and amortization expense",
        ],
        issues,
    )


def validate_financing_total(
    rows: Sequence[ReconstructedRow],
    issues: list[ValidationIssue],
) -> None:
    _check_arithmetic(
        rows,
        "net cash from financing activities",
        [
            "proceeds from long term borrowings",
            "proceeds from short term borrowings",
        ],
        issues,
    )


# ============================================================================
# Cash-flow reconciliation
# ============================================================================

def _find_value(
    rows: Sequence[ReconstructedRow],
    descriptions: Sequence[str],
    column: str,
) -> float | int | None:

    for description in descriptions:
        row = _find_row(rows, description)

        if row is not None:
            value = _value(row, column)

            if value is not None:
                return value

    return None


def validate_cash_flow_reconciliation(
    rows: Sequence[ReconstructedRow],
    issues: list[ValidationIssue],
) -> None:
    """
    Validate:

        Operating + Investing + Financing = Net Change in Cash

    only when all required rows exist.

    The validator never invents a missing cash figure.
    """

    for column in ("current", "previous"):

        operating = _find_value(
            rows,
            ["net cash from operating activities"],
            column,
        )

        investing = _find_value(
            rows,
            ["net cash from investing activities"],
            column,
        )

        financing = _find_value(
            rows,
            ["net cash from financing activities"],
            column,
        )

        net_change = _find_value(
            rows,
            [
                "net change in cash",
                "net increase in cash",
                "net decrease in cash",
            ],
            column,
        )

        if (
            operating is None
            or investing is None
            or financing is None
            or net_change is None
        ):
            continue

        calculated = (
            operating
            + investing
            + financing
        )

        if abs(calculated - net_change) >= ARITHMETIC_TOLERANCE:
            _add_issue(
                issues,
                "warning",
                "CASH_RECONCILIATION_MISMATCH",
                (
                    f"Cash-flow reconciliation does not match for "
                    f"the {column} year. "
                    f"Expected {calculated}, extracted {net_change}."
                ),
            )


# ============================================================================
# Main validation
# ============================================================================

def validate_rows(
    rows: Sequence[ReconstructedRow],
) -> ValidationResult:
    """
    Run all structural and financial validation checks.

    Important:
        This function reports problems.
        It never changes extracted values.
    """

    issues: list[ValidationIssue] = []

    rows = list(rows)

    if not rows:
        _add_issue(
            issues,
            "error",
            "NO_ROWS",
            "No reconstructed rows were supplied for validation.",
        )

        return ValidationResult(
            status="error",
            issues=issues,
        )

    validate_numeric_values(
        rows,
        issues,
    )

    validate_missing_values(
        rows,
        issues,
    )

    validate_confidence(
        rows,
        issues,
    )

    validate_ambiguity(
        rows,
        issues,
    )

    validate_duplicate_rows(
        rows,
        issues,
    )

    validate_operating_totals(
        rows,
        issues,
    )

    validate_financing_total(
        rows,
        issues,
    )

    validate_cash_flow_reconciliation(
        rows,
        issues,
    )

    has_errors = any(
        issue.level == "error"
        for issue in issues
    )

    has_warnings = any(
        issue.level == "warning"
        for issue in issues
    )

    if has_errors:
        status = "error"
    elif has_warnings:
        status = "warning"
    else:
        status = "valid"

    return ValidationResult(
        status=status,
        issues=issues,
    )


# ============================================================================
# Convenience function
# ============================================================================

def validate_reconstruction(
    columns,
    rows: Sequence[ReconstructedRow],
) -> ValidationResult:
    """
    Validate a table reconstruction result.

    `columns` is accepted for pipeline compatibility and future
    column-level validation.
    """

    return validate_rows(rows)


if __name__ == "__main__":
    print("Pollux validator module loaded successfully.")
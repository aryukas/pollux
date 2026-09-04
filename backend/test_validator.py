from __future__ import annotations

from dataclasses import dataclass

from table_reconstructor import ReconstructedRow
from validator import validate_rows


@dataclass
class MockNumber:
    numeric_value: int | float


def make_row(
    description: str,
    current: int | float | None = None,
    previous: int | float | None = None,
    current_confidence: float = 0.95,
    previous_confidence: float = 0.95,
) -> ReconstructedRow:
    return ReconstructedRow(
        y_center=0.0,
        description=description,
        current_candidates=(
            [str(current)]
            if current is not None
            else []
        ),
        previous_candidates=(
            [str(previous)]
            if previous is not None
            else []
        ),
        current_confidences=(
            [current_confidence]
            if current is not None
            else []
        ),
        previous_confidences=(
            [previous_confidence]
            if previous is not None
            else []
        ),
        current_numbers=(
            [MockNumber(current)]
            if current is not None
            else []
        ),
        previous_numbers=(
            [MockNumber(previous)]
            if previous is not None
            else []
        ),
    )


def build_valid_rows():
    return [
        make_row(
            "Profit before taxation",
            10473,
            10194,
        ),
        make_row(
            "Depreciation and amortization expense",
            1533,
            1194,
        ),
        make_row(
            "Operating Profit Before working capital changes",
            12006,
            11388,
        ),
        make_row(
            "Proceeds from long term borrowings",
            -400,
            1669,
        ),
        make_row(
            "Proceeds from short term borrowings",
            4,
            436,
        ),
        make_row(
            "Net cash from financing activities",
            -396,
            2105,
        ),
    ]


def test_empty_rows():
    result = validate_rows([])

    assert result.status == "error"

    assert "NO_ROWS" in {
        issue.code
        for issue in result.issues
    }


def test_valid_numeric_values():
    rows = [
        make_row(
            "Profit before taxation",
            10473,
            10194,
        )
    ]

    result = validate_rows(rows)

    assert not any(
        issue.code == "INVALID_NUMBER"
        for issue in result.issues
    )


def test_missing_current_value():
    rows = [
        make_row(
            "Profit before taxation",
            None,
            10194,
        )
    ]

    result = validate_rows(rows)

    assert any(
        issue.code == "MISSING_CURRENT_VALUE"
        for issue in result.issues
    )


def test_missing_previous_value():
    rows = [
        make_row(
            "Profit before taxation",
            10473,
            None,
        )
    ]

    result = validate_rows(rows)

    assert any(
        issue.code == "MISSING_PREVIOUS_VALUE"
        for issue in result.issues
    )


def test_low_confidence():
    rows = [
        make_row(
            "Profit before taxation",
            10473,
            10194,
            current_confidence=0.40,
            previous_confidence=0.95,
        )
    ]

    result = validate_rows(rows)

    assert any(
        issue.code == "LOW_OCR_CONFIDENCE"
        for issue in result.issues
    )


def test_ambiguity():
    row = make_row(
        "Profit before taxation",
        10473,
        10194,
    )

    row.ambiguous_current = True

    result = validate_rows([row])

    assert any(
        issue.code == "AMBIGUOUS_CURRENT"
        for issue in result.issues
    )


def test_duplicate_rows():
    rows = [
        make_row(
            "Profit before taxation",
            10473,
            10194,
        ),
        make_row(
            "Profit before taxation",
            10473,
            10194,
        ),
    ]

    result = validate_rows(rows)

    assert any(
        issue.code == "DUPLICATE_ROW"
        for issue in result.issues
    )


def test_financing_arithmetic_mismatch():
    """
    Deliberately provide an incorrect financing total.

    Current year:
        -400 + 4 = -396

    Extracted total:
        -395

    Therefore the validator must report a mismatch.
    """

    rows = [
        make_row(
            "Proceeds from long term borrowings",
            -400,
            1669,
        ),
        make_row(
            "Proceeds from short term borrowings",
            4,
            436,
        ),
        make_row(
            "Net cash from financing activities",
            -395,
            2105,
        ),
    ]

    result = validate_rows(rows)

    assert any(
        issue.code == "ARITHMETIC_MISMATCH"
        for issue in result.issues
    )


def test_financing_arithmetic_valid():
    """
    Both years reconcile correctly.

    Current:
        -400 + 4 = -396

    Previous:
        1669 + 436 = 2105
    """

    rows = [
        make_row(
            "Proceeds from long term borrowings",
            -400,
            1669,
        ),
        make_row(
            "Proceeds from short term borrowings",
            4,
            436,
        ),
        make_row(
            "Net cash from financing activities",
            -396,
            2105,
        ),
    ]

    result = validate_rows(rows)

    assert not any(
        issue.code == "ARITHMETIC_MISMATCH"
        for issue in result.issues
    )


def test_no_silent_correction():
    """
    Validator must report an incorrect value without changing it.
    """

    rows = [
        make_row(
            "Proceeds from long term borrowings",
            -400,
            1669,
        ),
        make_row(
            "Proceeds from short term borrowings",
            4,
            436,
        ),
        make_row(
            "Net cash from financing activities",
            -396,
            9999,
        ),
    ]

    original_value = (
        rows[-1]
        .previous_numbers[0]
        .numeric_value
    )

    result = validate_rows(rows)

    assert result.status == "warning"

    assert (
        rows[-1]
        .previous_numbers[0]
        .numeric_value
        == original_value
    )

    assert original_value == 9999


def test_cash_reconciliation_only_when_available():
    """
    If the statement does not contain a Net Change in Cash row,
    the validator must not invent one.
    """

    rows = [
        make_row(
            "Net cash from operating activities",
            25966,
            10697,
        ),
        make_row(
            "Net cash from investing activities",
            -2084,
            -3073,
        ),
        make_row(
            "Net cash from financing activities",
            -396,
            2104,
        ),
    ]

    result = validate_rows(rows)

    assert not any(
        issue.code == "CASH_RECONCILIATION_MISMATCH"
        for issue in result.issues
    )


def test_cash_reconciliation_mismatch():
    """
    When all three cash-flow sections and Net Change in Cash exist,
    reconciliation must be checked.
    """

    rows = [
        make_row(
            "Net cash from operating activities",
            25966,
            10697,
        ),
        make_row(
            "Net cash from investing activities",
            -2084,
            -3073,
        ),
        make_row(
            "Net cash from financing activities",
            -396,
            2104,
        ),
        make_row(
            "Net change in cash",
            25000,
            5000,
        ),
    ]

    result = validate_rows(rows)

    assert any(
        issue.code == "CASH_RECONCILIATION_MISMATCH"
        for issue in result.issues
    )


def test_cash_reconciliation_valid():
    """
    Current year:
        25966 - 2084 - 396 = 23486

    Previous year:
        10697 - 3073 + 2104 = 9728
    """

    rows = [
        make_row(
            "Net cash from operating activities",
            25966,
            10697,
        ),
        make_row(
            "Net cash from investing activities",
            -2084,
            -3073,
        ),
        make_row(
            "Net cash from financing activities",
            -396,
            2104,
        ),
        make_row(
            "Net change in cash",
            23486,
            9728,
        ),
    ]

    result = validate_rows(rows)

    assert not any(
        issue.code == "CASH_RECONCILIATION_MISMATCH"
        for issue in result.issues
    )


def test_to_dict():
    rows = [
        make_row(
            "Profit before taxation",
            10473,
            10194,
        )
    ]

    result = validate_rows(rows)

    output = result.to_dict()

    assert "status" in output
    assert "warnings" in output
    assert "errors" in output
    assert "issues" in output


def test_realistic_financing_values():
    rows = [
        make_row(
            "Proceeds from long term borrowings",
            -400,
            1669,
        ),
        make_row(
            "Proceeds from short term borrowings",
            4,
            436,
        ),
        make_row(
            "Net cash from financing activities",
            -396,
            2105,
        ),
    ]

    result = validate_rows(rows)

    assert not any(
        issue.code == "ARITHMETIC_MISMATCH"
        for issue in result.issues
    )


def test_validation_does_not_change_values():
    rows = build_valid_rows()

    before = [
        (
            (
                row.current_numbers[0].numeric_value
                if row.current_numbers
                else None
            ),
            (
                row.previous_numbers[0].numeric_value
                if row.previous_numbers
                else None
            ),
        )
        for row in rows
    ]

    validate_rows(rows)

    after = [
        (
            (
                row.current_numbers[0].numeric_value
                if row.current_numbers
                else None
            ),
            (
                row.previous_numbers[0].numeric_value
                if row.previous_numbers
                else None
            ),
        )
        for row in rows
    ]

    assert before == after


def test_validation_status_warning_on_mismatch():
    rows = [
        make_row(
            "Proceeds from long term borrowings",
            -400,
            1669,
        ),
        make_row(
            "Proceeds from short term borrowings",
            4,
            436,
        ),
        make_row(
            "Net cash from financing activities",
            -395,
            2105,
        ),
    ]

    result = validate_rows(rows)

    assert result.status == "warning"


def test_validation_status_valid_when_no_issues():
    rows = [
        make_row(
            "Profit before taxation",
            10473,
            10194,
        )
    ]

    result = validate_rows(rows)

    assert result.status == "valid"


if __name__ == "__main__":
    print("\n" + "=" * 90)
    print("POLLUX VALIDATOR TEST")
    print("=" * 90)

    test_empty_rows()
    test_valid_numeric_values()
    test_missing_current_value()
    test_missing_previous_value()
    test_low_confidence()
    test_ambiguity()
    test_duplicate_rows()
    test_financing_arithmetic_mismatch()
    test_financing_arithmetic_valid()
    test_no_silent_correction()
    test_cash_reconciliation_only_when_available()
    test_cash_reconciliation_mismatch()
    test_cash_reconciliation_valid()
    test_to_dict()
    test_realistic_financing_values()
    test_validation_does_not_change_values()
    test_validation_status_warning_on_mismatch()
    test_validation_status_valid_when_no_issues()

    print("\n" + "=" * 90)
    print("ALL VALIDATOR TESTS PASSED")
    print("=" * 90)
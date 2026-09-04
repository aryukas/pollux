from __future__ import annotations

from table_reconstructor import ReconstructedRow
from extractor import extract_statement


def make_row(
    description: str,
    current: int | float | None = None,
    previous: int | float | None = None,
) -> ReconstructedRow:
    """
    Create a minimal reconstructed row for extractor testing.

    The extractor expects current_numbers / previous_numbers to contain
    objects with a numeric_value attribute. A tiny test double is used here
    instead of involving OCR.
    """

    class Number:
        def __init__(self, value):
            self.numeric_value = value

    return ReconstructedRow(
        y_center=0.0,
        description=description,
        current_numbers=(
            [Number(current)]
            if current is not None
            else []
        ),
        previous_numbers=(
            [Number(previous)]
            if previous is not None
            else []
        ),
    )


def build_test_rows() -> list[ReconstructedRow]:
    """
    Representative Cash Flow Statement reconstruction.
    """

    return [
        # Document metadata — should be removed.
        make_row(
            "Universal Orbital Systems Private Limited"
        ),
        make_row(
            "Cash Flow Statement as at 31-March-2023 (in Thousands)"
        ),
        make_row(
            "Particulars for the period 01-Apr-2022 to 31-Mar-2023"
        ),

        # Operating section.
        make_row(
            "Cash flows from operating activities"
        ),
        make_row(
            "Profit before taxation",
            10473,
            10194,
        ),
        make_row(
            "Adjustments for"
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
            "(Increase)/ decrease in trade receivables",
            -1014,
            1055,
        ),
        make_row(
            "(Increase)/ decrease in Short-Term Loans and Advances",
            1170,
            -92,
        ),
        make_row(
            "(Increase)/ decrease in Long-Term Loans and Advances"
        ),
        make_row(
            "(Increase)/ decrease in Inventories",
            317,
            -1048,
        ),
        make_row(
            "(Increase)/ decrease in Other Current Assets",
            5097,
            4561,
        ),
        make_row(
            "Increase/ (decrease) in trade payables",
            10454,
            835,
        ),
        make_row(
            "Increase/ (decrease) in Other Current Liabilities",
            2339,
            517,
        ),
        make_row(
            "Increase/ (decrease) in Short-Term Provisions",
            -1583,
            -3698,
        ),
        make_row(
            "Cash Generated from/(Used in) Operations",
            16780,
            2129,
        ),
        make_row(
            "Direct Taxes Paid",
            -2820,
            -2820,
        ),
        make_row(
            "Net cash from operating activities",
            25966,
            10697,
        ),

        # Investing section.
        make_row(
            "Cash flows from investing activities"
        ),
        make_row(
            "Purchase of property, plant and equipment",
            -2084,
            -3673,
        ),
        make_row(
            "Net cash from investing activities",
            -2084,
            -3073,
        ),

        # Financing section.
        make_row(
            "Cash flows from financing activities"
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
            2104,
        ),

        # Footer — should be removed.
        make_row("PUNE"),
    ]


def test_extractor():
    rows = build_test_rows()

    statement = extract_statement(
        rows,
        current_year=2023,
        previous_year=2022,
    )

    print("\n" + "=" * 90)
    print("POLLUX EXTRACTOR TEST")
    print("=" * 90)

    print(f"\nStatement type : {statement.statement_type}")
    print(f"Current year   : {statement.current_year}")
    print(f"Previous year  : {statement.previous_year}")

    print("\n" + "-" * 90)

    for section_name, section_rows in statement.sections.items():
        print(f"\n{section_name.upper()} ACTIVITIES")

        if not section_rows:
            print("  NO ROWS")
            continue

        for row in section_rows:
            current = (
                "-"
                if row.current is None
                else row.current
            )

            previous = (
                "-"
                if row.previous is None
                else row.previous
            )

            print(
                f"  [{row.row_type.upper():5}] "
                f"{row.description:<65} "
                f"{current:>10} "
                f"{previous:>10}"
            )

    print("\n" + "-" * 90)

    print("\nWARNINGS")

    if statement.warnings:
        for warning in statement.warnings:
            print(f"  - {warning}")
    else:
        print("  None")

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    assert statement.statement_type == "cash_flow_statement"

    assert statement.current_year == 2023
    assert statement.previous_year == 2022

    # Three sections must be identified.
    assert statement.sections["operating"]
    assert statement.sections["investing"]
    assert statement.sections["financing"]

    # --------------------------------------------------------------
    # Operating assertions
    # --------------------------------------------------------------

    operating = statement.sections["operating"]

    profit = next(
        row
        for row in operating
        if "profit before taxation" in row.description.lower()
    )

    assert profit.current == 10473
    assert profit.previous == 10194

    depreciation = next(
        row
        for row in operating
        if "depreciation" in row.description.lower()
    )

    assert depreciation.current == 1533
    assert depreciation.previous == 1194

    receivables = next(
        row
        for row in operating
        if "trade receivables" in row.description.lower()
    )

    assert receivables.current == -1014
    assert receivables.previous == 1055

    operating_total = next(
        row
        for row in operating
        if "net cash from operating activities"
        in row.description.lower()
    )

    assert operating_total.current == 25966
    assert operating_total.previous == 10697
    assert operating_total.row_type == "total"

    # --------------------------------------------------------------
    # Investing assertions
    # --------------------------------------------------------------

    investing = statement.sections["investing"]

    ppe = next(
        row
        for row in investing
        if "property, plant and equipment"
        in row.description.lower()
    )

    assert ppe.current == -2084
    assert ppe.previous == -3673

    investing_total = next(
        row
        for row in investing
        if "net cash from investing activities"
        in row.description.lower()
    )

    assert investing_total.current == -2084
    assert investing_total.previous == -3073
    assert investing_total.row_type == "total"

    # --------------------------------------------------------------
    # Financing assertions
    # --------------------------------------------------------------

    financing = statement.sections["financing"]

    long_term = next(
        row
        for row in financing
        if "long term borrowings"
        in row.description.lower()
    )

    assert long_term.current == -400
    assert long_term.previous == 1669

    short_term = next(
        row
        for row in financing
        if "short term borrowings"
        in row.description.lower()
    )

    assert short_term.current == 4
    assert short_term.previous == 436

    financing_total = next(
        row
        for row in financing
        if "net cash from financing activities"
        in row.description.lower()
    )

    assert financing_total.current == -396
    assert financing_total.previous == 2104
    assert financing_total.row_type == "total"

    # --------------------------------------------------------------
    # Noise filtering
    # --------------------------------------------------------------

    all_descriptions = [
        row.description.lower()
        for section in statement.sections.values()
        for row in section
    ]

    assert not any(
        "universal orbital systems" in description
        for description in all_descriptions
    )

    assert not any(
        description == "pune"
        for description in all_descriptions
    )

    # --------------------------------------------------------------
    # JSON serialization
    # --------------------------------------------------------------

    output = statement.to_dict()

    assert output["statement_type"] == "cash_flow_statement"
    assert output["current_year"] == 2023
    assert output["previous_year"] == 2022

    assert "operating" in output["sections"]
    assert "investing" in output["sections"]
    assert "financing" in output["sections"]

    assert "validation" in output
    assert "status" in output["validation"]
    assert "warnings" in output["validation"]

    print("\n" + "=" * 90)
    print("ALL EXTRACTOR TESTS PASSED")
    print("=" * 90)


if __name__ == "__main__":
    test_extractor()
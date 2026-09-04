from financial_numbers import (
    is_financial_number,
    parse_financial_number,
)


def test_positive_number():
    result = parse_financial_number("10,473")

    assert result is not None
    assert result.numeric_value == 10473
    assert result.is_negative is False


def test_parentheses_are_negative():
    result = parse_financial_number("(1,014)")

    assert result is not None
    assert result.numeric_value == -1014
    assert result.is_negative is True


def test_parentheses_without_closing_bracket():
    result = parse_financial_number("(1.014")

    assert result is not None
    assert result.normalized_text == "(1,014)"
    assert result.numeric_value == -1014
    assert result.is_negative is True


def test_second_ocr_example():
    result = parse_financial_number("(2.084")

    assert result is not None
    assert result.normalized_text == "(2,084)"
    assert result.numeric_value == -2084
    assert result.is_negative is True


def test_small_negative_number():
    result = parse_financial_number("(92)")

    assert result is not None
    assert result.numeric_value == -92
    assert result.is_negative is True


def test_explicit_negative_number():
    result = parse_financial_number("-400")

    assert result is not None
    assert result.numeric_value == -400
    assert result.is_negative is True


def test_zero():
    result = parse_financial_number("0")

    assert result is not None
    assert result.numeric_value == 0
    assert result.is_negative is False


def test_currency_symbol():
    result = parse_financial_number("₹10,473")

    assert result is not None
    assert result.numeric_value == 10473


def test_invalid_text():
    assert parse_financial_number("hello") is None


def test_empty_text():
    assert parse_financial_number("") is None


def test_financial_number_detection():
    assert is_financial_number("10,473")
    assert is_financial_number("(1,014)")
    assert is_financial_number("(1.014")
    assert not is_financial_number("Profit before taxation")


def test_confidence_is_clamped():
    result = parse_financial_number("10,473", confidence=2.0)

    assert result is not None
    assert result.confidence == 1.0

    result = parse_financial_number("10,473", confidence=-1.0)

    assert result is not None
    assert result.confidence == 0.0


def main():
    test_positive_number()
    test_parentheses_are_negative()
    test_parentheses_without_closing_bracket()
    test_second_ocr_example()
    test_small_negative_number()
    test_explicit_negative_number()
    test_zero()
    test_currency_symbol()
    test_invalid_text()
    test_empty_text()
    test_financial_number_detection()
    test_confidence_is_clamped()

    print("All financial number tests passed.")


if __name__ == "__main__":
    main()
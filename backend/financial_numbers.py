from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class FinancialNumber:
    raw_text: str
    normalized_text: str
    numeric_value: float | int | None
    is_negative: bool
    confidence: float


def normalize_financial_text(text: str) -> str:
    """
    Normalize OCR output before numeric parsing.

    Handles common OCR errors found in financial statements:
    - periods used instead of commas in thousands separators
    - whitespace inside numbers
    - missing closing parenthesis
    - different bracket characters
    """
    value = text.strip()

    if not value:
        return ""

    # Normalize whitespace.
    value = re.sub(r"\s+", "", value)

    # Normalize common bracket variants.
    value = (
        value.replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
    )

    # OCR may recognize a thousands comma as a period:
    # (1.014 -> (1,014
    #
    # Only replace periods when they appear between digit groups.
    value = re.sub(
        r"(?<=\d)\.(?=\d{3}(?:\D|$))",
        ",",
        value,
    )

    # Remove accidental repeated commas.
    value = re.sub(r",+", ",", value)

    # If OCR captured an opening parenthesis but lost the closing one,
    # restore it.
    if value.startswith("(") and not value.endswith(")"):
        value += ")"

    return value


def parse_financial_number(
    text: str,
    confidence: float = 1.0,
) -> FinancialNumber | None:
    """
    Parse an OCR-detected financial number.

    Parentheses represent negative values in financial statements.

    Examples:
        10,473   -> 10473
        (1,014)  -> -1014
        (92)     -> -92
        (1.014   -> -1014
        -400     -> -400
    """
    raw_text = text

    if not text or not text.strip():
        return None

    normalized = normalize_financial_text(text)

    if not normalized:
        return None

    is_negative = False

    # Parentheses are the standard financial-statement notation
    # for negative values.
    if normalized.startswith("(") and normalized.endswith(")"):
        is_negative = True
        numeric_text = normalized[1:-1]
    else:
        numeric_text = normalized

    # Explicit minus sign is also supported.
    if numeric_text.startswith("-"):
        is_negative = True
        numeric_text = numeric_text[1:]

    # Remove currency symbols and other harmless OCR artifacts.
    numeric_text = re.sub(r"[₹$€£]", "", numeric_text)

    # Remove spaces that may remain after normalization.
    numeric_text = numeric_text.replace(" ", "")

    # A valid financial number should contain only digits and
    # optionally one decimal point/comma grouping.
    if not re.fullmatch(r"\d+(?:,\d{3})*(?:\.\d+)?", numeric_text):
        return None

    # Remove thousands separators.
    numeric_text = numeric_text.replace(",", "")

    try:
        if "." in numeric_text:
            numeric_value: float | int = float(numeric_text)
        else:
            numeric_value = int(numeric_text)
    except ValueError:
        return None

    if is_negative:
        numeric_value = -numeric_value

    return FinancialNumber(
        raw_text=raw_text,
        normalized_text=normalized,
        numeric_value=numeric_value,
        is_negative=is_negative,
        confidence=max(0.0, min(1.0, confidence)),
    )


def is_financial_number(text: str) -> bool:
    """
    Return True when the supplied OCR text can be interpreted
    as a financial number.
    """
    return parse_financial_number(text) is not None
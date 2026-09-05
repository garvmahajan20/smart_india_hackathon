import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Tuple, Union

# Number word mappings for simple English durations
WORD_TO_NUM = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"
}

def normalize_numeric(value: Any, default_unit: Optional[str] = None) -> Tuple[Optional[Decimal], Optional[str]]:
    """
    Normalizes monetary and numeric expressions to Python Decimal.
    Supports Indian denominations: Lakhs, Crores, Millions, Thousands.
    Preserves precision with Decimal; avoids floating-point inaccuracies.
    """
    if value is None or isinstance(value, bool):
        return None, default_unit

    if isinstance(value, Decimal):
        return value, default_unit or "COUNT"

    if isinstance(value, (int,)):
        return Decimal(str(value)), default_unit or "COUNT"

    if isinstance(value, float):
        # Convert via str to avoid float binary approximation artifacts
        return Decimal(str(value)), default_unit or "COUNT"

    if not isinstance(value, str):
        return None, default_unit

    cleaned = value.strip().lower()
    if not cleaned:
        return None, default_unit

    detected_unit = default_unit

    # Check for currency symbols / terms
    if any(curr in cleaned for curr in ["?", "rs.", "rs", "inr", "rupees"]):
        detected_unit = "INR"
        cleaned = re.sub(r"[?]|rs\.?|inr|rupees", "", cleaned).strip()

    # Detect scale multipliers
    multiplier = Decimal("1")
    if re.search(r"\b(crores?|crs?)\b", cleaned):
        multiplier = Decimal("10000000")
        detected_unit = "INR" if detected_unit == "INR" else "COUNT"
        cleaned = re.sub(r"\b(crores?|crs?)\b", "", cleaned).strip()
    elif re.search(r"\b(lakhs?|lacs?)\b", cleaned):
        multiplier = Decimal("100000")
        detected_unit = "INR" if detected_unit == "INR" else "COUNT"
        cleaned = re.sub(r"\b(lakhs?|lacs?)\b", "", cleaned).strip()
    elif re.search(r"\b(millions?|m)\b", cleaned):
        multiplier = Decimal("1000000")
        cleaned = re.sub(r"\b(millions?|m)\b", "", cleaned).strip()
    elif re.search(r"\b(thousands?|k)\b", cleaned):
        multiplier = Decimal("1000")
        cleaned = re.sub(r"\b(thousands?|k)\b", "", cleaned).strip()

    # Clean commas, spaces
    cleaned = cleaned.replace(",", "").strip()

    # Check if remaining string has non-currency alphabetic characters (e.g. ISO 9001:2015, Grade A)
    # If so, it is an alphanumeric code or categorical string, not a pure numeric value
    remaining_text = re.sub(r"[?$]|\b(rs\.?|inr|rupees|crores?|crs?|lakhs?|lacs?|millions?|thousands?|k|m|cr)\b", "", cleaned).strip()
    if re.search(r"[a-zA-Z]", remaining_text):
        return None, default_unit

    # Match numeric token
    num_match = re.search(r"[-+]?\d*\.?\d+", cleaned)
    if not num_match:
        return None, default_unit

    try:
        base_num = Decimal(num_match.group(0))
        final_val = base_num * multiplier
        return final_val, detected_unit or "COUNT"
    except (InvalidOperation, ValueError):
        return None, default_unit

def normalize_currency(value: Any, default_unit: str = "INR") -> Tuple[Optional[Decimal], str]:
    """
    Normalizes any currency string (?31 lakh, INR 3100000, 31,00,000) into base INR Decimal.
    """
    val, _ = normalize_numeric(value, default_unit="INR")
    return val, "INR"

def normalize_date(value: Any) -> Optional[date]:
    """
    Deterministically normalizes a date string or datetime object into datetime.date.
    Never calls datetime.now().
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    if not cleaned or cleaned.lower() in ["na", "n/a", "not available"]:
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    # Attempt to extract YYYY-MM-DD or DD-MM-YYYY using regex if embedded in text
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", cleaned)
    if iso_match:
        try:
            return datetime.strptime(iso_match.group(0), "%Y-%m-%d").date()
        except ValueError:
            pass

    ind_match = re.search(r"\b(\d{2})[-/](\d{2})[-/](\d{4})\b", cleaned)
    if ind_match:
        d_str = f"{ind_match.group(1)}-{ind_match.group(2)}-{ind_match.group(3)}"
        try:
            return datetime.strptime(d_str, "%d-%m-%Y").date()
        except ValueError:
            pass

    return None

def normalize_duration(value: Any, target_unit: str = "MONTHS") -> Tuple[Optional[Decimal], str]:
    """
    Normalizes duration expressions (e.g. '3 years', '36 months', 'two years', '90 days')
    to standard months (1 year = 12 months) or days (1 month = 30 days, 1 year = 365 days).
    """
    if value is None or isinstance(value, bool):
        return None, target_unit

    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)), target_unit

    if not isinstance(value, str):
        return None, target_unit

    cleaned = value.strip().lower()
    for word, digit in WORD_TO_NUM.items():
        cleaned = re.sub(rf"\b{word}\b", digit, cleaned)

    # Extract numeric part
    num_match = re.search(r"\b(\d+(?:\.\d+)?)\b", cleaned)
    if not num_match:
        return None, target_unit

    try:
        qty = Decimal(num_match.group(1))
    except (InvalidOperation, ValueError):
        return None, target_unit

    if re.search(r"\b(years?|yrs?|yr)\b", cleaned):
        if target_unit == "MONTHS":
            return qty * Decimal("12"), "MONTHS"
        elif target_unit == "DAYS":
            return qty * Decimal("365"), "DAYS"
        else:
            return qty, "YEARS"
    elif re.search(r"\b(months?|mths?|mth|mo)\b", cleaned):
        if target_unit == "MONTHS":
            return qty, "MONTHS"
        elif target_unit == "DAYS":
            return qty * Decimal("30"), "DAYS"
        else:
            return qty / Decimal("12"), "YEARS"
    elif re.search(r"\b(days?|d)\b", cleaned):
        if target_unit == "DAYS":
            return qty, "DAYS"
        elif target_unit == "MONTHS":
            return qty / Decimal("30"), "MONTHS"
        else:
            return qty / Decimal("365"), "YEARS"

    # Default fallback
    return qty, target_unit

def normalize_boolean(value: Any) -> Optional[bool]:
    """
    Normalizes natural language truth values to strict boolean.
    Supports: Yes/No, true/false, Y/N, 1/0, required/not required.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, Decimal)):
        return bool(value)

    if not isinstance(value, str):
        return None

    cleaned = value.strip().lower()
    if cleaned in ["true", "yes", "y", "1", "required", "submitted", "available", "valid", "compliant"]:
        return True
    if cleaned in ["false", "no", "n", "0", "not required", "exempted", "not available", "invalid", "non-compliant", "na", "n/a"]:
        return False

    return None

def normalize_categorical(value: Any) -> Optional[str]:
    """
    Standardizes whitespace and case for categorical/text comparisons.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value).strip().upper()

    # Collapse multiple spaces and uppercase
    collapsed = " ".join(value.strip().split())
    return collapsed.upper()

def normalize_existence(value: Any) -> bool:
    """
    Checks if a fact/document/evidence exists and contains non-empty value.
    Booleans (True/False) and Numbers (including 0) are valid existing values.
    """
    if value is None:
        return False
    if isinstance(value, (bool, int, float, Decimal)):
        return True
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if not cleaned or cleaned in ["na", "n/a", "not available", "none", "null", "missing"]:
            return False
        return True
    if isinstance(value, (list, dict, set, tuple)):
        return len(value) > 0
    return True

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, List, Optional, Tuple, Union

from .models import ComplianceStatus
from .normalization import (
    normalize_boolean,
    normalize_categorical,
    normalize_currency,
    normalize_date,
    normalize_duration,
    normalize_existence,
    normalize_numeric,
)

@dataclass
class OperatorResult:
    status: ComplianceStatus
    reason: str
    requires_human_review: bool = False

def _try_numeric_comparison(actual: Any, expected: Any) -> Optional[Tuple[Decimal, Decimal]]:
    """
    Attempts to normalize both values to Decimal for numerical comparison.
    Handles currency strings, lakhs, crores, etc.
    """
    act_num, _ = normalize_numeric(actual)
    exp_num, _ = normalize_numeric(expected)
    if act_num is not None and exp_num is not None:
        return act_num, exp_num
    return None

def _try_date_comparison(actual: Any, expected: Any) -> Optional[Tuple[date, date]]:
    """
    Attempts to normalize both values to datetime.date.
    """
    act_d = normalize_date(actual)
    exp_d = normalize_date(expected)
    if act_d is not None and exp_d is not None:
        return act_d, exp_d
    return None

def _try_duration_comparison(actual: Any, expected: Any) -> Optional[Tuple[Decimal, Decimal]]:
    """
    Attempts to normalize duration expressions to unified months.
    """
    act_dur, _ = normalize_duration(actual, target_unit="MONTHS")
    exp_dur, _ = normalize_duration(expected, target_unit="MONTHS")
    if act_dur is not None and exp_dur is not None:
        return act_dur, exp_dur
    return None

def evaluate_gte(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    # 1. Try Duration
    dur_pair = _try_duration_comparison(actual, expected)
    if dur_pair is not None and ("year" in str(actual).lower() or "month" in str(actual).lower() or "day" in str(actual).lower() or "year" in str(expected).lower() or "month" in str(expected).lower()):
        act_d, exp_d = dur_pair
        if act_d >= exp_d:
            return OperatorResult(ComplianceStatus.PASS, f"Actual duration ({actual}) meets or exceeds required ({expected}).")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Actual duration ({actual}) is less than required ({expected}).")

    # 2. Try Numeric / Currency
    num_pair = _try_numeric_comparison(actual, expected)
    if num_pair is not None:
        act_n, exp_n = num_pair
        if act_n >= exp_n:
            return OperatorResult(ComplianceStatus.PASS, f"Actual value ({actual}) meets or exceeds threshold ({expected}).")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Actual value ({actual}) is below threshold ({expected}).")

    # 3. Try Date
    date_pair = _try_date_comparison(actual, expected)
    if date_pair is not None:
        act_d, exp_d = date_pair
        if act_d >= exp_d:
            return OperatorResult(ComplianceStatus.PASS, f"Actual date ({act_d}) is on or after required date ({exp_d}).")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Actual date ({act_d}) is before required date ({exp_d}).")

    return OperatorResult(ComplianceStatus.REVIEW, f"Incompatible types or unparseable values for '>=' comparison: actual='{actual}', expected='{expected}'.", requires_human_review=True)

def evaluate_lte(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    dur_pair = _try_duration_comparison(actual, expected)
    if dur_pair is not None and ("year" in str(actual).lower() or "month" in str(actual).lower() or "day" in str(actual).lower() or "year" in str(expected).lower() or "month" in str(expected).lower()):
        act_d, exp_d = dur_pair
        if act_d <= exp_d:
            return OperatorResult(ComplianceStatus.PASS, f"Actual duration ({actual}) is within limit ({expected}).")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Actual duration ({actual}) exceeds limit ({expected}).")

    num_pair = _try_numeric_comparison(actual, expected)
    if num_pair is not None:
        act_n, exp_n = num_pair
        if act_n <= exp_n:
            return OperatorResult(ComplianceStatus.PASS, f"Actual value ({actual}) is within limit ({expected}).")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Actual value ({actual}) exceeds maximum allowed ({expected}).")

    date_pair = _try_date_comparison(actual, expected)
    if date_pair is not None:
        act_d, exp_d = date_pair
        if act_d <= exp_d:
            return OperatorResult(ComplianceStatus.PASS, f"Actual date ({act_d}) is on or before deadline ({exp_d}).")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Actual date ({act_d}) is after deadline ({exp_d}).")

    return OperatorResult(ComplianceStatus.REVIEW, f"Incompatible types or unparseable values for '<=' comparison: actual='{actual}', expected='{expected}'.", requires_human_review=True)

def evaluate_gt(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    num_pair = _try_numeric_comparison(actual, expected)
    if num_pair is not None:
        act_n, exp_n = num_pair
        if act_n > exp_n:
            return OperatorResult(ComplianceStatus.PASS, f"Actual value ({actual}) strictly exceeds ({expected}).")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Actual value ({actual}) does not strictly exceed ({expected}).")
    return OperatorResult(ComplianceStatus.REVIEW, f"Incompatible types for '>' comparison: actual='{actual}', expected='{expected}'.", requires_human_review=True)

def evaluate_lt(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    num_pair = _try_numeric_comparison(actual, expected)
    if num_pair is not None:
        act_n, exp_n = num_pair
        if act_n < exp_n:
            return OperatorResult(ComplianceStatus.PASS, f"Actual value ({actual}) is strictly less than ({expected}).")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Actual value ({actual}) is not strictly less than ({expected}).")
    return OperatorResult(ComplianceStatus.REVIEW, f"Incompatible types for '<' comparison: actual='{actual}', expected='{expected}'.", requires_human_review=True)

def evaluate_eq(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    # 1. Boolean check
    act_b = normalize_boolean(actual)
    exp_b = normalize_boolean(expected)
    if act_b is not None and exp_b is not None and (isinstance(actual, bool) or isinstance(expected, bool) or str(actual).lower() in ["yes", "no", "true", "false", "y", "n"] or str(expected).lower() in ["yes", "no", "true", "false", "y", "n"]):
        if act_b == exp_b:
            return OperatorResult(ComplianceStatus.PASS, f"Boolean requirement matched: {act_b} == {exp_b}.")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Boolean requirement mismatch: actual {act_b} != expected {exp_b}.")

    # 2. Try Duration check
    dur_pair = _try_duration_comparison(actual, expected)
    if dur_pair is not None and any(unit_w in str(actual).lower() or unit_w in str(expected).lower() for unit_w in ["year", "month", "day"]):
        act_d, exp_d = dur_pair
        if act_d == exp_d:
            return OperatorResult(ComplianceStatus.PASS, f"Duration equality matched: {actual} == {expected}.")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Duration mismatch: {actual} != {expected}.")

    # 2. Numeric check
    num_pair = _try_numeric_comparison(actual, expected)
    if num_pair is not None:
        act_n, exp_n = num_pair
        if act_n == exp_n:
            return OperatorResult(ComplianceStatus.PASS, f"Numeric equality matched: {actual} == {expected}.")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Numeric equality failed: actual {actual} != expected {expected}.")

    # 3. Categorical string check
    act_cat = normalize_categorical(actual)
    exp_cat = normalize_categorical(expected)
    if act_cat is not None and exp_cat is not None:
        if act_cat == exp_cat:
            return OperatorResult(ComplianceStatus.PASS, f"Categorical match: '{actual}' == '{expected}'.")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Categorical mismatch: '{actual}' != '{expected}'.")

    # 4. Fallback exact equality
    if actual == expected:
        return OperatorResult(ComplianceStatus.PASS, f"Exact match: {actual} == {expected}.")
    return OperatorResult(ComplianceStatus.FAIL, f"Values do not match: actual '{actual}' != expected '{expected}'.")

def evaluate_neq(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    if not normalize_existence(actual):
        return OperatorResult(ComplianceStatus.MISSING, f"Missing value for '!=' comparison. Missing data must NEVER return PASS.", requires_human_review=True)
    eq_res = evaluate_eq(actual, expected, field_name)
    if eq_res.status == ComplianceStatus.PASS:
        return OperatorResult(ComplianceStatus.FAIL, f"Values match but inequality was required: actual '{actual}' == expected '{expected}'.")
    elif eq_res.status == ComplianceStatus.FAIL:
        return OperatorResult(ComplianceStatus.PASS, f"Inequality satisfied: actual '{actual}' != expected '{expected}'.")
    return eq_res

def evaluate_in(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    if actual is None:
        return OperatorResult(ComplianceStatus.FAIL, "Actual value is missing for 'IN' check.")

    act_cat = normalize_categorical(actual)

    # Expected could be a list, set, or comma-separated string
    candidates: List[str] = []
    if isinstance(expected, (list, set, tuple)):
        candidates = [normalize_categorical(x) or "" for x in expected]
    elif isinstance(expected, str):
        candidates = [normalize_categorical(x) or "" for x in expected.split(",")]
    else:
        candidates = [normalize_categorical(expected) or ""]

    if act_cat in candidates:
        return OperatorResult(ComplianceStatus.PASS, f"Actual value '{actual}' is in approved list ({expected}).")
    return OperatorResult(ComplianceStatus.FAIL, f"Actual value '{actual}' is not in approved list ({expected}).")

def evaluate_not_in(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    if not normalize_existence(actual):
        return OperatorResult(ComplianceStatus.MISSING, f"Missing value for 'NOT_IN' comparison. Missing data must NEVER return PASS.", requires_human_review=True)
    in_res = evaluate_in(actual, expected, field_name)
    if in_res.status == ComplianceStatus.PASS:
        return OperatorResult(ComplianceStatus.FAIL, f"Actual value '{actual}' is in prohibited list ({expected}).")
    elif in_res.status == ComplianceStatus.FAIL:
        return OperatorResult(ComplianceStatus.PASS, f"Actual value '{actual}' is not in prohibited list ({expected}).")
    return in_res

def evaluate_contains(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    if actual is None or expected is None:
        return OperatorResult(ComplianceStatus.FAIL, f"Missing value for 'CONTAINS' check: actual='{actual}', expected='{expected}'.")

    act_str = str(actual).lower()
    exp_str = str(expected).lower()
    if exp_str in act_str:
        return OperatorResult(ComplianceStatus.PASS, f"Actual text contains '{expected}'.")
    return OperatorResult(ComplianceStatus.FAIL, f"Actual text does not contain '{expected}'.")

def evaluate_matches(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    if actual is None or expected is None:
        return OperatorResult(ComplianceStatus.FAIL, f"Missing value for 'MATCHES' pattern check.")

    try:
        if re.search(str(expected), str(actual), re.IGNORECASE):
            return OperatorResult(ComplianceStatus.PASS, f"Actual text matches pattern '{expected}'.")
        return OperatorResult(ComplianceStatus.FAIL, f"Actual text does not match pattern '{expected}'.")
    except re.error as e:
        return OperatorResult(ComplianceStatus.REVIEW, f"Invalid regex pattern '{expected}': {e}", requires_human_review=True)

def evaluate_exists(actual: Any, expected: Any = None, field_name: str = "") -> OperatorResult:
    exists = normalize_existence(actual)
    if exists:
        return OperatorResult(ComplianceStatus.PASS, f"Required document/fact is present.")
    return OperatorResult(ComplianceStatus.MISSING, f"Required document/fact is missing or empty.")

def evaluate_valid_on(actual: Any, reference_date: Any, field_name: str = "") -> OperatorResult:
    """
    Evaluates whether a certificate/record is valid on the reference date (e.g. tender closing date).
    Supports actual as dict with issue_date and expiry_date, or as an expiry date string.
    """
    ref_d = normalize_date(reference_date)
    if ref_d is None:
        return OperatorResult(ComplianceStatus.REVIEW, f"Reference date '{reference_date}' is invalid or missing.", requires_human_review=True)

    # Actual as dict containing certificate validity attributes
    if isinstance(actual, dict):
        # Direct boolean flag if verified
        if actual.get("valid") is False or actual.get("is_valid") is False:
            return OperatorResult(ComplianceStatus.FAIL, f"Certificate explicitly marked invalid.")

        iss_d = normalize_date(actual.get("issue_date"))
        exp_d = normalize_date(actual.get("expiry_date"))

        if iss_d and exp_d:
            if iss_d <= ref_d <= exp_d:
                return OperatorResult(ComplianceStatus.PASS, f"Certificate is valid on {ref_d} (issued: {iss_d}, expires: {exp_d}).")
            elif ref_d < iss_d:
                return OperatorResult(ComplianceStatus.FAIL, f"Certificate issue date ({iss_d}) is after reference date ({ref_d}).")
            else:
                return OperatorResult(ComplianceStatus.FAIL, f"Certificate expired on {exp_d}, prior to reference date {ref_d}.")
        elif exp_d:
            if ref_d <= exp_d:
                return OperatorResult(ComplianceStatus.PASS, f"Certificate valid on {ref_d} (expires: {exp_d}).")
            else:
                return OperatorResult(ComplianceStatus.FAIL, f"Certificate expired on {exp_d}, prior to reference date {ref_d}.")

    # Actual as date string representing expiry date
    exp_d = normalize_date(actual)
    if exp_d is not None:
        if ref_d <= exp_d:
            return OperatorResult(ComplianceStatus.PASS, f"Certificate valid on {ref_d} (expires: {exp_d}).")
        else:
            return OperatorResult(ComplianceStatus.FAIL, f"Certificate expired on {exp_d}, prior to reference date {ref_d}.")

    return OperatorResult(ComplianceStatus.REVIEW, f"Could not determine certificate validity on {ref_d} from actual='{actual}'.", requires_human_review=True)

def evaluate_before(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    date_pair = _try_date_comparison(actual, expected)
    if date_pair is None:
        return OperatorResult(ComplianceStatus.REVIEW, f"Incompatible dates for 'BEFORE': actual='{actual}', expected='{expected}'.", requires_human_review=True)
    act_d, exp_d = date_pair
    if act_d < exp_d:
        return OperatorResult(ComplianceStatus.PASS, f"Date {act_d} is strictly before {exp_d}.")
    return OperatorResult(ComplianceStatus.FAIL, f"Date {act_d} is not before {exp_d}.")

def evaluate_after(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    date_pair = _try_date_comparison(actual, expected)
    if date_pair is None:
        return OperatorResult(ComplianceStatus.REVIEW, f"Incompatible dates for 'AFTER': actual='{actual}', expected='{expected}'.", requires_human_review=True)
    act_d, exp_d = date_pair
    if act_d > exp_d:
        return OperatorResult(ComplianceStatus.PASS, f"Date {act_d} is strictly after {exp_d}.")
    return OperatorResult(ComplianceStatus.FAIL, f"Date {act_d} is not after {exp_d}.")

def evaluate_between(actual: Any, expected: Any, field_name: str = "") -> OperatorResult:
    """
    Checks if actual value is within [lower, upper] inclusive.
    """
    lower, upper = None, None
    if isinstance(expected, (list, tuple)) and len(expected) >= 2:
        lower, upper = expected[0], expected[1]
    elif isinstance(expected, str) and ("to" in expected or "-" in expected):
        parts = re.split(r"\s+to\s+|-", expected)
        if len(parts) >= 2:
            lower, upper = parts[0].strip(), parts[1].strip()

    if lower is None or upper is None:
        return OperatorResult(ComplianceStatus.REVIEW, f"Invalid 'BETWEEN' expected range: {expected}.", requires_human_review=True)

    # Try numeric
    num_act, _ = normalize_numeric(actual)
    num_low, _ = normalize_numeric(lower)
    num_upp, _ = normalize_numeric(upper)
    if num_act is not None and num_low is not None and num_upp is not None:
        if num_low <= num_act <= num_upp:
            return OperatorResult(ComplianceStatus.PASS, f"Value {actual} is within range [{lower}, {upper}].")
        return OperatorResult(ComplianceStatus.FAIL, f"Value {actual} is outside range [{lower}, {upper}].")

    # Try date
    d_act = normalize_date(actual)
    d_low = normalize_date(lower)
    d_upp = normalize_date(upper)
    if d_act is not None and d_low is not None and d_upp is not None:
        if d_low <= d_act <= d_upp:
            return OperatorResult(ComplianceStatus.PASS, f"Date {d_act} is within range [{d_low}, {d_upp}].")
        return OperatorResult(ComplianceStatus.FAIL, f"Date {d_act} is outside range [{d_low}, {d_upp}].")

    return OperatorResult(ComplianceStatus.REVIEW, f"Incompatible types for 'BETWEEN': actual='{actual}', range='[{lower}, {upper}]'.", requires_human_review=True)

OPERATOR_DISPATCH = {
    ">=": evaluate_gte,
    "<=": evaluate_lte,
    ">": evaluate_gt,
    "<": evaluate_lt,
    "==": evaluate_eq,
    "!=": evaluate_neq,
    "IN": evaluate_in,
    "NOT_IN": evaluate_not_in,
    "CONTAINS": evaluate_contains,
    "MATCHES": evaluate_matches,
    "EXISTS": evaluate_exists,
    "VALID_ON": evaluate_valid_on,
    "BEFORE": evaluate_before,
    "AFTER": evaluate_after,
    "BETWEEN": evaluate_between,
}

def evaluate_operator(operator: str, actual: Any, expected: Any = None, field_name: str = "") -> OperatorResult:
    """
    Dispatches to deterministic operator handler.
    CRITICAL RULE: Missing or invalid data must NEVER return PASS.
    """
    op_clean = operator.strip()

    # UNIVERSAL GUARD: Missing or null actual value must NEVER return PASS
    if actual is None:
        if op_clean == "EXISTS":
            return OperatorResult(ComplianceStatus.MISSING, "Required document/fact is absent. Missing data must NEVER return PASS.")
        return OperatorResult(
            status=ComplianceStatus.MISSING,
            reason=f"Actual value for '{field_name or 'requirement'}' is null/missing. Missing data must NEVER return PASS.",
            requires_human_review=True
        )

    if isinstance(actual, str) and not actual.strip():
        if op_clean == "EXISTS":
            return OperatorResult(ComplianceStatus.MISSING, "Required document/fact is empty. Empty data must NEVER return PASS.")
        return OperatorResult(
            status=ComplianceStatus.MISSING,
            reason=f"Actual value for '{field_name or 'requirement'}' is empty string. Empty data must NEVER return PASS.",
            requires_human_review=True
        )
    handler = OPERATOR_DISPATCH.get(op_clean)
    if not handler:
        return OperatorResult(
            status=ComplianceStatus.REVIEW,
            reason=f"Unsupported operator '{operator}'. Must be reviewed by officer.",
            requires_human_review=True
        )

    try:
        return handler(actual, expected, field_name)
    except Exception as e:
        return OperatorResult(
            status=ComplianceStatus.REVIEW,
            reason=f"Error evaluating operator '{operator}': {str(e)}",
            requires_human_review=True
        )

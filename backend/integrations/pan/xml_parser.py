# -*- coding: utf-8 -*-
"""
API Setu PAN XML Certificate Parser.
Defensively parses official API Setu PAN Verification Record XML payloads.
Features:
- XXE attack prevention: explicitly rejects DOCTYPE and ENTITY declarations.
- Extracts exact field paths for ProvenanceDAG explainability.
- Preserves issuer, status, holder name, DOB, and certificate number.
"""

import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional, Tuple

from .models import PANVerificationResponse, PANVerificationStatus


class PANXMLParsingError(Exception):
    """Raised when XML fails parsing or violates security constraints."""
    pass


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_pan_verification_xml(
    xml_string: str,
    txn_id: str,
    http_status: int = 200,
    queried_pan: str = "",
    latency_ms: float = 0.0,
    response_hash: Optional[str] = None,
) -> PANVerificationResponse:
    """
    Parses official API Setu PAN XML response into normalized PANVerificationResponse.
    Records exact XML field paths for provenance tracking.
    """
    if not xml_string or not xml_string.strip():
        raise PANXMLParsingError("Empty XML payload cannot be parsed")

    # Strict XXE Prevention
    if "<!DOCTYPE" in xml_string or "<!ENTITY" in xml_string:
        raise PANXMLParsingError("XML containing DOCTYPE or ENTITY declarations is rejected for security")

    try:
        root = ET.fromstring(xml_string.strip())
    except ET.ParseError as e:
        raise PANXMLParsingError(f"Malformed XML payload: {e}") from e

    # Find the Certificate element (root or child)
    cert_elem = None
    root_tag = _strip_ns(root.tag)
    if root_tag == "Certificate":
        cert_elem = root
    else:
        for elem in root.iter():
            if _strip_ns(elem.tag) == "Certificate":
                cert_elem = elem
                break

    if cert_elem is None:
        raise PANXMLParsingError("Missing <Certificate> element in API Setu response")

    xml_paths: Dict[str, str] = {}

    # Extract Certificate attributes
    cert_type = cert_elem.attrib.get("type", "PANCR")
    cert_number = cert_elem.attrib.get("number", "")
    cert_status = cert_elem.attrib.get("status", "A").upper()  # A = Active
    issue_date = cert_elem.attrib.get("issueDate") or cert_elem.attrib.get("verifiedOn")

    if cert_type:
        xml_paths["certificate_type"] = "/Certificate/@type"
    if cert_number:
        xml_paths["certificate_number"] = "/Certificate/@number"
    if cert_status:
        xml_paths["certificate_status"] = "/Certificate/@status"
    if issue_date:
        xml_paths["verified_on"] = "/Certificate/@issueDate"

    extracted_pan = ""
    holder_name = None
    holder_dob = None
    issuer_name = "Income Tax Department"

    for child in cert_elem:
        tag = _strip_ns(child.tag)

        if tag == "IssuedBy":
            for sub in child:
                sub_tag = _strip_ns(sub.tag)
                if sub_tag in ("Organization", "Authority"):
                    name = sub.attrib.get("name", "") or (sub.text or "").strip()
                    if name:
                        issuer_name = name
                        xml_paths["issuer"] = f"/Certificate/IssuedBy/{sub_tag}/@name"

        elif tag == "IssuedTo":
            for sub in child:
                sub_tag = _strip_ns(sub.tag)
                if sub_tag == "Person":
                    holder_name = sub.attrib.get("name", "") or (sub.text or "").strip()
                    holder_dob = sub.attrib.get("dob")
                    if holder_name:
                        xml_paths["verified_name"] = "/Certificate/IssuedTo/Person/@name"
                    if holder_dob:
                        xml_paths["verified_dob"] = "/Certificate/IssuedTo/Person/@dob"

        elif tag == "CertificateData":
            for sub in child:
                sub_tag = _strip_ns(sub.tag)
                if sub_tag == "PAN":
                    num = sub.attrib.get("num", "") or (sub.text or "").strip()
                    if num:
                        extracted_pan = num
                        xml_paths["pan"] = "/Certificate/CertificateData/PAN/@num"
                elif sub_tag in ("PANNo", "panno"):
                    extracted_pan = (sub.text or "").strip()
                    xml_paths["pan"] = f"/Certificate/CertificateData/{sub_tag}"

    # Fallback to cert_number if PAN was not explicitly in CertificateData
    if not extracted_pan and cert_number:
        extracted_pan = cert_number
        xml_paths["pan"] = "/Certificate/@number"

    final_pan = (extracted_pan or queried_pan).strip().upper()

    # Determine verification status
    is_active = (cert_status == "A")
    status = PANVerificationStatus.VERIFIED if is_active else PANVerificationStatus.NOT_VERIFIED

    return PANVerificationResponse(
        txn_id=txn_id,
        status=status,
        http_status=http_status,
        pan=final_pan,
        verified_name=holder_name,
        verified_dob=holder_dob,
        issuer=issuer_name,
        certificate_type=cert_type,
        certificate_number=cert_number or final_pan,
        certificate_status=cert_status,
        verified_on=issue_date,
        raw_response=xml_string,
        response_hash=response_hash,
        xml_field_paths=xml_paths,
        latency_ms=latency_ms,
        is_live=True,
    )

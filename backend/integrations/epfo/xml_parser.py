# -*- coding: utf-8 -*-
"""
Secure XML Parser for API Setu EPFO XML Responses.
Used for:
- Scheme Certificate (epfsc)
- Pension Certificate (pecer)
Enforces:
- Strict XXE protection (rejects DOCTYPE, ENTITY declarations)
- Exact XML XPath field provenance tracking
- Safe failure on malformed XML or JSON error envelopes
"""

import hashlib
from typing import Dict, Optional
import xml.etree.ElementTree as ET

from .models import (
    EPFOEndpointType,
    EPFOVerificationResponse,
    EPFOVerificationStatus,
)


class EPFOXMLParsingError(Exception):
    """Raised when EPFO XML is malformed, invalid, or violates security policies."""
    pass


def parse_epfo_certificate_xml(
    xml_string: str,
    endpoint_type: EPFOEndpointType,
    txn_id: str,
    http_status: int = 200,
    queried_identifier: Optional[str] = None,
    latency_ms: Optional[float] = None,
    is_live: bool = False,
) -> EPFOVerificationResponse:
    """
    Parses authoritative API Setu EPFO XML response into normalized EPFOVerificationResponse.
    Guarantees strict XXE safety by rejecting DTDs/Entities.
    """
    if not xml_string or not xml_string.strip():
        raise EPFOXMLParsingError("EPFO response XML is empty")

    lowered = xml_string.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise EPFOXMLParsingError("XXE Injection attempt detected: DOCTYPE and ENTITY declarations are forbidden")

    try:
        parser = ET.XMLParser()
        root = ET.fromstring(xml_string, parser=parser)
    except ET.ParseError as pe:
        raise EPFOXMLParsingError(f"Malformed XML response: {pe}")

    xml_field_paths: Dict[str, str] = {}
    response_hash = hashlib.sha256(xml_string.encode("utf-8")).hexdigest()

    certificate_number: Optional[str] = None
    member_name: Optional[str] = None
    dob: Optional[str] = None
    father_husband_name: Optional[str] = None
    issue_date: Optional[str] = None
    issuer: Optional[str] = "Employees' Provident Fund Organisation"

    # Iterate over elements
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        tag_lower = tag.lower()

        # Check attributes
        for k, v in elem.attrib.items():
            k_lower = k.lower()
            if "name" in k_lower and not member_name:
                member_name = v.strip()
                xml_field_paths["member_name"] = f"//{tag}/@{k}"
            elif ("scno" in k_lower or "ppono" in k_lower or "certno" in k_lower or "number" in k_lower) and not certificate_number:
                certificate_number = v.strip().upper()
                xml_field_paths["certificate_number"] = f"//{tag}/@{k}"
            elif "dob" in k_lower and not dob:
                dob = v.strip()
                xml_field_paths["dob"] = f"//{tag}/@{k}"

        # Check text tags
        if tag_lower in ("scno", "ppono", "certificateno", "certificatenumber", "orderno") and elem.text:
            certificate_number = elem.text.strip().upper()
            xml_field_paths["certificate_number"] = f"//{tag}/text()"
        elif tag_lower in ("membername", "name", "beneficiaryname", "pensionername") and elem.text:
            member_name = elem.text.strip()
            xml_field_paths["member_name"] = f"//{tag}/text()"
        elif tag_lower in ("dob", "dateofbirth") and elem.text:
            dob = elem.text.strip()
            xml_field_paths["dob"] = f"//{tag}/text()"
        elif tag_lower in ("fathername", "husbandname", "father_husband_name") and elem.text:
            father_husband_name = elem.text.strip()
            xml_field_paths["father_husband_name"] = f"//{tag}/text()"
        elif tag_lower in ("issuedate", "dateofissue") and elem.text:
            issue_date = elem.text.strip()
            xml_field_paths["issue_date"] = f"//{tag}/text()"

    resolved_id = certificate_number or queried_identifier or "UNKNOWN"
    status = EPFOVerificationStatus.VERIFIED if (certificate_number or member_name) else EPFOVerificationStatus.NOT_VERIFIED

    return EPFOVerificationResponse(
        endpoint_type=endpoint_type,
        identifier=resolved_id,
        txn_id=txn_id,
        status=status,
        http_status=http_status,
        format="xml",
        member_name=member_name,
        dob=dob,
        father_husband_name=father_husband_name,
        certificate_number=certificate_number or resolved_id,
        issue_date=issue_date,
        issuer=issuer,
        raw_response=xml_string,
        response_hash=response_hash,
        xml_field_paths=xml_field_paths,
        latency_ms=latency_ms,
        is_live=is_live,
    )

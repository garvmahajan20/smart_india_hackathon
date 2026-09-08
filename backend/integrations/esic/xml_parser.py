# -*- coding: utf-8 -*-
"""
Secure XML Parser for API Setu ESIC Responses.
Used for:
- Health Passbook (esich)
- Pehchan Card (phcrd)
Enforces:
- Strict XXE protection (rejects DOCTYPE, ENTITY declarations)
- Exact XML XPath field provenance tracking
- Safe failure on malformed XML or JSON error envelopes
"""

import hashlib
from typing import Dict, Optional
import xml.etree.ElementTree as ET

from .models import (
    ESICEndpointType,
    ESICVerificationResponse,
    ESICVerificationStatus,
)


class ESICXMLParsingError(Exception):
    """Raised when ESIC XML is malformed, invalid, or violates security policies."""
    pass


def parse_esic_certificate_xml(
    xml_string: str,
    endpoint_type: ESICEndpointType,
    txn_id: str,
    http_status: int = 200,
    queried_ip: Optional[str] = None,
    latency_ms: Optional[float] = None,
    is_live: bool = False,
) -> ESICVerificationResponse:
    """
    Parses authoritative API Setu ESIC XML response into normalized ESICVerificationResponse.
    Guarantees strict XXE safety by rejecting DTDs/Entities.
    """
    if not xml_string or not xml_string.strip():
        raise ESICXMLParsingError("ESIC response XML is empty")

    lowered = xml_string.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise ESICXMLParsingError("XXE Injection attempt detected: DOCTYPE and ENTITY declarations are forbidden")

    try:
        parser = ET.XMLParser()
        root = ET.fromstring(xml_string, parser=parser)
    except ET.ParseError as pe:
        raise ESICXMLParsingError(f"Malformed XML response: {pe}")

    xml_field_paths: Dict[str, str] = {}
    response_hash = hashlib.sha256(xml_string.encode("utf-8")).hexdigest()

    ip_number: Optional[str] = None
    insured_person_name: Optional[str] = None
    employer_name: Optional[str] = None
    dispensary: Optional[str] = None
    date_of_registration: Optional[str] = None
    relation: Optional[str] = None
    certificate_number: Optional[str] = None
    issuer: Optional[str] = "Employees State Insurance Corporation"

    # Iterate over elements
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        tag_lower = tag.lower()

        # Check attributes
        for k, v in elem.attrib.items():
            k_lower = k.lower()
            if ("ipnumber" in k_lower or "ip_no" in k_lower or "number" in k_lower) and not ip_number:
                ip_number = v.strip()
                xml_field_paths["ip_number"] = f"//{tag}/@{k}"
            elif ("name" in k_lower or "insured" in k_lower) and not insured_person_name:
                insured_person_name = v.strip()
                xml_field_paths["insured_person_name"] = f"//{tag}/@{k}"
            elif "employer" in k_lower and not employer_name:
                employer_name = v.strip()
                xml_field_paths["employer_name"] = f"//{tag}/@{k}"
            elif "dispensary" in k_lower and not dispensary:
                dispensary = v.strip()
                xml_field_paths["dispensary"] = f"//{tag}/@{k}"

        # Check text tags
        if tag_lower in ("ipnumber", "ip_number", "ipno", "insuredpersonnumber") and elem.text:
            ip_number = elem.text.strip()
            xml_field_paths["ip_number"] = f"//{tag}/text()"
        elif tag_lower in ("name", "insuredpersonname", "membername", "personname") and elem.text:
            insured_person_name = elem.text.strip()
            xml_field_paths["insured_person_name"] = f"//{tag}/text()"
        elif tag_lower in ("employername", "employer", "unitname") and elem.text:
            employer_name = elem.text.strip()
            xml_field_paths["employer_name"] = f"//{tag}/text()"
        elif tag_lower in ("dispensary", "dispensaryname") and elem.text:
            dispensary = elem.text.strip()
            xml_field_paths["dispensary"] = f"//{tag}/text()"
        elif tag_lower in ("dateofregistration", "registrationdate", "doj") and elem.text:
            date_of_registration = elem.text.strip()
            xml_field_paths["date_of_registration"] = f"//{tag}/text()"
        elif tag_lower in ("relation", "relationship") and elem.text:
            relation = elem.text.strip()
            xml_field_paths["relation"] = f"//{tag}/text()"
        elif tag_lower in ("certificatenumber", "cardnumber") and elem.text:
            certificate_number = elem.text.strip()
            xml_field_paths["certificate_number"] = f"//{tag}/text()"

    resolved_ip = ip_number or queried_ip or "UNKNOWN"
    status = ESICVerificationStatus.VERIFIED if (ip_number or insured_person_name) else ESICVerificationStatus.NOT_VERIFIED

    return ESICVerificationResponse(
        endpoint_type=endpoint_type,
        ip_number=resolved_ip,
        txn_id=txn_id,
        status=status,
        http_status=http_status,
        format="xml",
        insured_person_name=insured_person_name,
        employer_name=employer_name,
        dispensary=dispensary,
        date_of_registration=date_of_registration,
        relation=relation,
        certificate_number=certificate_number or resolved_ip,
        issuer=issuer,
        raw_response=xml_string,
        response_hash=response_hash,
        xml_field_paths=xml_field_paths,
        latency_ms=latency_ms,
        is_live=is_live,
    )

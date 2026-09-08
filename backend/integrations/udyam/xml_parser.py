# -*- coding: utf-8 -*-
"""
Secure XML Parser for API Setu / MSME Udyam Certificate Response.
Enforces:
- Strict XXE protection (rejects DOCTYPE, ENTITY declarations)
- Path-based extraction preserving exact XML XPath field provenance
- Safe failure on malformed XML or JSON error envelopes
"""

import hashlib
from typing import Dict, Optional
import xml.etree.ElementTree as ET

from .models import UdyamVerificationResponse, UdyamVerificationStatus


class UdyamXMLParsingError(Exception):
    """Raised when Udyam XML is malformed, invalid, or violates security policies."""
    pass


def parse_udyam_verification_xml(
    xml_string: str,
    txn_id: str,
    http_status: int = 200,
    queried_udyam: Optional[str] = None,
    latency_ms: Optional[float] = None,
    is_live: bool = False,
) -> UdyamVerificationResponse:
    """
    Parses authoritative API Setu Udyam XML response into normalized UdyamVerificationResponse.
    Guarantees strict XXE safety by rejecting DTDs/Entities.
    """
    if not xml_string or not xml_string.strip():
        raise UdyamXMLParsingError("Udyam response XML is empty")

    # XXE Security Check
    lowered = xml_string.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise UdyamXMLParsingError("XXE Injection attempt detected: DOCTYPE and ENTITY declarations are forbidden")

    try:
        parser = ET.XMLParser()
        root = ET.fromstring(xml_string, parser=parser)
    except ET.ParseError as pe:
        raise UdyamXMLParsingError(f"Malformed XML response: {pe}")

    xml_field_paths: Dict[str, str] = {}
    response_hash = hashlib.sha256(xml_string.encode("utf-8")).hexdigest()

    # Extract metadata attributes from root or child elements
    # API Setu certificates typically wrap inside <Certificate> or <UdyamCertificate>
    certificate_type = root.attrib.get("type") or root.tag
    certificate_number = root.attrib.get("number")
    issuer = root.attrib.get("issuer", "Ministry of Micro, Small and Medium Enterprises")

    udyam_num: Optional[str] = None
    enterprise_name: Optional[str] = None
    enterprise_type: Optional[str] = None
    major_activity: Optional[str] = None
    date_of_commencement: Optional[str] = None
    social_category: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None

    # Search known element paths in CertificateData / UdyamRegistration / Enterprise
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]  # Strip XML namespace if present
        tag_lower = tag.lower()

        if tag_lower in ("udyamregistration", "udyamcertificate", "msme", "enterprise"):
            for k, v in elem.attrib.items():
                k_lower = k.lower()
                if "udyam" in k_lower or k_lower == "number":
                    udyam_num = v.strip().upper()
                    xml_field_paths["udyam_number"] = f"//{tag}/@{k}"
                elif "name" in k_lower or "enterprise" in k_lower:
                    enterprise_name = v.strip()
                    xml_field_paths["enterprise_name"] = f"//{tag}/@{k}"
                elif "type" in k_lower or "category" in k_lower:
                    enterprise_type = v.strip()
                    xml_field_paths["enterprise_type"] = f"//{tag}/@{k}"
                elif "activity" in k_lower:
                    major_activity = v.strip()
                    xml_field_paths["major_activity"] = f"//{tag}/@{k}"

        # Check child text tags
        if tag_lower in ("udyamnumber", "udyam_registration_number", "registrationnumber") and elem.text:
            udyam_num = elem.text.strip().upper()
            xml_field_paths["udyam_number"] = f"//{tag}/text()"
        elif tag_lower in ("enterprisename", "name_of_enterprise", "unitname") and elem.text:
            enterprise_name = elem.text.strip()
            xml_field_paths["enterprise_name"] = f"//{tag}/text()"
        elif tag_lower in ("enterprisetype", "classification", "msmetype", "category") and elem.text:
            enterprise_type = elem.text.strip()
            xml_field_paths["enterprise_type"] = f"//{tag}/text()"
        elif tag_lower in ("majoractivity", "activity") and elem.text:
            major_activity = elem.text.strip()
            xml_field_paths["major_activity"] = f"//{tag}/text()"
        elif tag_lower in ("dateofcommencement", "commencementdate", "incorporationdate") and elem.text:
            date_of_commencement = elem.text.strip()
            xml_field_paths["date_of_commencement"] = f"//{tag}/text()"
        elif tag_lower in ("socialcategory", "caste") and elem.text:
            social_category = elem.text.strip()
            xml_field_paths["social_category"] = f"//{tag}/text()"
        elif tag_lower == "state" and elem.text:
            state = elem.text.strip()
            xml_field_paths["state"] = f"//{tag}/text()"
        elif tag_lower == "district" and elem.text:
            district = elem.text.strip()
            xml_field_paths["district"] = f"//{tag}/text()"

    # Resolve final Udyam number
    resolved_udyam = udyam_num or queried_udyam or "UNKNOWN"
    if resolved_udyam:
        resolved_udyam = resolved_udyam.strip().upper()

    status = UdyamVerificationStatus.VERIFIED if udyam_num or enterprise_name else UdyamVerificationStatus.NOT_VERIFIED

    return UdyamVerificationResponse(
        txn_id=txn_id,
        status=status,
        http_status=http_status,
        udyam_number=resolved_udyam,
        enterprise_name=enterprise_name,
        enterprise_type=enterprise_type,
        major_activity=major_activity,
        date_of_commencement=date_of_commencement,
        social_category=social_category,
        state=state,
        district=district,
        issuer=issuer,
        certificate_type=certificate_type,
        certificate_number=certificate_number or udyam_num,
        raw_response=xml_string,
        response_hash=response_hash,
        xml_field_paths=xml_field_paths,
        latency_ms=latency_ms,
        is_live=is_live,
    )

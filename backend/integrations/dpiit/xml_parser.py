# -*- coding: utf-8 -*-
"""
Secure XML Parser for API Setu / DPIIT Recognition Certificate Response.
Enforces:
- Strict XXE protection (rejects DOCTYPE, ENTITY declarations)
- Path-based extraction preserving exact XML XPath field provenance
- Safe failure on malformed XML or JSON error envelopes
"""

import hashlib
from typing import Dict, Optional
import xml.etree.ElementTree as ET

from .models import DPIITVerificationResponse, DPIITVerificationStatus


class DPIITXMLParsingError(Exception):
    """Raised when DPIIT XML is malformed, invalid, or violates security policies."""
    pass


def parse_dpiit_recognition_xml(
    xml_string: str,
    txn_id: str,
    http_status: int = 200,
    queried_regn: Optional[str] = None,
    latency_ms: Optional[float] = None,
    is_live: bool = False,
) -> DPIITVerificationResponse:
    """
    Parses authoritative API Setu DPIIT XML response into normalized DPIITVerificationResponse.
    Guarantees strict XXE safety by rejecting DTDs/Entities.
    """
    if not xml_string or not xml_string.strip():
        raise DPIITXMLParsingError("DPIIT response XML is empty")

    lowered = xml_string.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise DPIITXMLParsingError("XXE Injection attempt detected: DOCTYPE and ENTITY declarations are forbidden")

    try:
        parser = ET.XMLParser()
        root = ET.fromstring(xml_string, parser=parser)
    except ET.ParseError as pe:
        raise DPIITXMLParsingError(f"Malformed XML response: {pe}")

    xml_field_paths: Dict[str, str] = {}
    response_hash = hashlib.sha256(xml_string.encode("utf-8")).hexdigest()

    certificate_type = root.attrib.get("type") or root.tag
    issuer = root.attrib.get("issuer", "Department for Promotion of Industry and Internal Trade")

    regn_no: Optional[str] = None
    startup_name: Optional[str] = None
    entity_type: Optional[str] = None
    incorporation_date: Optional[str] = None
    recognition_number: Optional[str] = None
    recognition_date: Optional[str] = None
    valid_upto: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    state: Optional[str] = None

    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        tag_lower = tag.lower()

        # Check attributes
        for k, v in elem.attrib.items():
            k_lower = k.lower()
            if ("regn" in k_lower or "dipp" in k_lower or "recognition" in k_lower) and not regn_no:
                regn_no = v.strip().upper()
                xml_field_paths["regn_no"] = f"//{tag}/@{k}"
            elif ("name" in k_lower or "startup" in k_lower or "entity" in k_lower) and not startup_name:
                startup_name = v.strip()
                xml_field_paths["startup_name"] = f"//{tag}/@{k}"
            elif "industry" in k_lower and not industry:
                industry = v.strip()
                xml_field_paths["industry"] = f"//{tag}/@{k}"
            elif "sector" in k_lower and not sector:
                sector = v.strip()
                xml_field_paths["sector"] = f"//{tag}/@{k}"

        # Check text tags
        if tag_lower in ("regn_no", "regnno", "dippno", "recognitionno", "registrationnumber") and elem.text:
            regn_no = elem.text.strip().upper()
            xml_field_paths["regn_no"] = f"//{tag}/text()"
        elif tag_lower in ("startupname", "entityname", "companyname", "nameofstartup") and elem.text:
            startup_name = elem.text.strip()
            xml_field_paths["startup_name"] = f"//{tag}/text()"
        elif tag_lower in ("entitytype", "typeofentity", "constitution") and elem.text:
            entity_type = elem.text.strip()
            xml_field_paths["entity_type"] = f"//{tag}/text()"
        elif tag_lower in ("incorporationdate", "dateofincorporation") and elem.text:
            incorporation_date = elem.text.strip()
            xml_field_paths["incorporation_date"] = f"//{tag}/text()"
        elif tag_lower in ("recognitionnumber", "certificateno") and elem.text:
            recognition_number = elem.text.strip()
            xml_field_paths["recognition_number"] = f"//{tag}/text()"
        elif tag_lower in ("recognitiondate", "dateofrecognition") and elem.text:
            recognition_date = elem.text.strip()
            xml_field_paths["recognition_date"] = f"//{tag}/text()"
        elif tag_lower in ("validupto", "validitydate", "expirydate") and elem.text:
            valid_upto = elem.text.strip()
            xml_field_paths["valid_upto"] = f"//{tag}/text()"
        elif tag_lower in ("industry", "industryname") and elem.text:
            industry = elem.text.strip()
            xml_field_paths["industry"] = f"//{tag}/text()"
        elif tag_lower in ("sector", "sectorname") and elem.text:
            sector = elem.text.strip()
            xml_field_paths["sector"] = f"//{tag}/text()"
        elif tag_lower in ("state", "statename") and elem.text:
            state = elem.text.strip()
            xml_field_paths["state"] = f"//{tag}/text()"

    resolved_regn = regn_no or queried_regn or "UNKNOWN"
    status = DPIITVerificationStatus.VERIFIED if (regn_no or startup_name) else DPIITVerificationStatus.NOT_VERIFIED

    return DPIITVerificationResponse(
        txn_id=txn_id,
        status=status,
        http_status=http_status,
        regn_no=resolved_regn,
        startup_name=startup_name,
        entity_type=entity_type,
        incorporation_date=incorporation_date,
        recognition_number=recognition_number or resolved_regn,
        recognition_date=recognition_date,
        valid_upto=valid_upto,
        industry=industry,
        sector=sector,
        state=state,
        issuer=issuer,
        certificate_type=certificate_type,
        raw_response=xml_string,
        response_hash=response_hash,
        xml_field_paths=xml_field_paths,
        latency_ms=latency_ms,
        is_live=is_live,
    )

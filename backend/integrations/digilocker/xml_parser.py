# -*- coding: utf-8 -*-
"""
DigiLocker / API Setu Official XML Specification Parser.
Safely parses PullDocResponse and Certificate payloads without external entity resolution (XXE safe).
Extracts embedded base64 PDF bytes and canonical certificate attributes.
"""

import base64
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional, Tuple

from .models import DigiLockerParsedCertificate


class DigiLockerXMLParsingError(Exception):
    """Raised when DigiLocker XML response fails structural or security validation."""
    pass


def _strip_tag_namespace(tag: str) -> str:
    """Removes XML namespace prefix if present: {http://...}Tag -> Tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_digilocker_certificate_xml(xml_string: str) -> DigiLockerParsedCertificate:
    """
    Parses official DigiLocker XML Certificate element.
    Structure per API Setu specification:
    <Certificate name="..." type="..." number="..." status="..." issueDate="..." validFromDate="..." expiryDate="...">
      <IssuedBy>
        <Organization name="..." code="..."/>
      </IssuedBy>
      <IssuedTo>
        <Person name="..." uid="..." .../>
        <Organization name="..." type="..." .../>
      </IssuedTo>
      <CertificateData>
        <Key>Value</Key>
        ...
      </CertificateData>
    </Certificate>
    """
    if not xml_string or not xml_string.strip():
        raise DigiLockerXMLParsingError("Empty XML payload cannot be parsed")

    # Defensive check against external entity attacks (XXE prevention)
    if "<!DOCTYPE" in xml_string or "<!ENTITY" in xml_string:
        raise DigiLockerXMLParsingError("XML containing DOCTYPE or ENTITY declarations is rejected for security")

    try:
        root = ET.fromstring(xml_string.strip())
    except ET.ParseError as e:
        raise DigiLockerXMLParsingError(f"Malformed XML payload: {e}") from e

    # Find the <Certificate> element (either root or a descendant)
    cert_elem = None
    root_tag = _strip_tag_namespace(root.tag)
    if root_tag == "Certificate":
        cert_elem = root
    else:
        for elem in root.iter():
            if _strip_tag_namespace(elem.tag) == "Certificate":
                cert_elem = elem
                break

    if cert_elem is None:
        raise DigiLockerXMLParsingError("Missing <Certificate> element in DigiLocker XML")

    # Extract Certificate top-level attributes
    cert_attrs = {k: v for k, v in cert_elem.attrib.items()}
    cert_name = cert_attrs.get("name", "Unknown Certificate")
    cert_type = cert_attrs.get("type", "UNKNOWN").upper()
    cert_number = cert_attrs.get("number", "")
    issue_date = cert_attrs.get("issueDate")
    valid_from = cert_attrs.get("validFromDate")
    expiry_date = cert_attrs.get("expiryDate")
    status = cert_attrs.get("status", "A").upper()

    issuer_name = ""
    issuer_code = ""
    recipient_name = ""
    recipient_uid = None
    recipient_org = None
    cert_data: Dict[str, Any] = {}

    for child in cert_elem:
        tag = _strip_tag_namespace(child.tag)
        if tag == "IssuedBy":
            for sub in child:
                sub_tag = _strip_tag_namespace(sub.tag)
                if sub_tag in ("Organization", "Authority"):
                    issuer_name = sub.attrib.get("name", "")
                    issuer_code = sub.attrib.get("code", "")
                    if not issuer_name and sub.text:
                        issuer_name = sub.text.strip()
        elif tag == "IssuedTo":
            for sub in child:
                sub_tag = _strip_tag_namespace(sub.tag)
                if sub_tag == "Person":
                    recipient_name = sub.attrib.get("name", "") or (sub.text.strip() if sub.text else "")
                    recipient_uid = sub.attrib.get("uid")
                elif sub_tag == "Organization":
                    recipient_org = sub.attrib.get("name", "") or (sub.text.strip() if sub.text else "")
                    if not recipient_name and recipient_org:
                        recipient_name = recipient_org
        elif tag == "CertificateData":
            for data_elem in child:
                field_key = _strip_tag_namespace(data_elem.tag)
                val = (data_elem.text or "").strip()
                # Include attributes if any
                if data_elem.attrib:
                    cert_data[field_key] = {"value": val, "attributes": dict(data_elem.attrib)}
                else:
                    cert_data[field_key] = val

    # If status is "A", certificate is active/valid
    is_valid = (status == "A")

    return DigiLockerParsedCertificate(
        certificate_type=cert_type,
        certificate_name=cert_name,
        certificate_number=cert_number,
        issue_date=issue_date,
        valid_from=valid_from,
        expiry_date=expiry_date,
        status=status,
        issuer_name=issuer_name,
        issuer_code=issuer_code,
        recipient_name=recipient_name,
        recipient_uid=recipient_uid,
        recipient_organization=recipient_org,
        certificate_data=cert_data,
        raw_xml=xml_string,
        is_valid=is_valid,
    )


def parse_pull_doc_response(xml_string: str) -> Tuple[Optional[bytes], Optional[DigiLockerParsedCertificate], Dict[str, Any]]:
    """
    Parses official API Setu <PullDocResponse> envelope.
    Standard envelope format:
    <PullDocResponse xmlns="...">
      <ResponseStatus status="1" ts="..." txn="...">...</ResponseStatus>
      <DocDetails>
        <DocContent>...Base64 Encoded PDF...</DocContent>
        <DataContent>...Base64 Encoded or Raw XML...</DataContent>
      </DocDetails>
    </PullDocResponse>

    Returns: (pdf_bytes, parsed_certificate, metadata)
    """
    if not xml_string or not xml_string.strip():
        raise DigiLockerXMLParsingError("Empty PullDocResponse payload")

    if "<!DOCTYPE" in xml_string or "<!ENTITY" in xml_string:
        raise DigiLockerXMLParsingError("XML containing DOCTYPE or ENTITY declarations is rejected for security")

    try:
        root = ET.fromstring(xml_string.strip())
    except ET.ParseError as e:
        # Check if xml_string is direct Certificate XML
        try:
            cert = parse_digilocker_certificate_xml(xml_string)
            return None, cert, {"status": "1", "source": "DIRECT_CERTIFICATE"}
        except Exception:
            raise DigiLockerXMLParsingError(f"Invalid PullDocResponse XML: {e}") from e

    root_tag = _strip_tag_namespace(root.tag)
    if root_tag == "Certificate":
        cert = parse_digilocker_certificate_xml(xml_string)
        return None, cert, {"status": "1", "source": "DIRECT_CERTIFICATE"}

    metadata: Dict[str, Any] = {}
    pdf_bytes: Optional[bytes] = None
    parsed_cert: Optional[DigiLockerParsedCertificate] = None

    # Check ResponseStatus
    for elem in root.iter():
        tag = _strip_tag_namespace(elem.tag)
        if tag == "ResponseStatus":
            metadata["response_status"] = elem.attrib.get("status", "0")
            metadata["ts"] = elem.attrib.get("ts")
            metadata["txn"] = elem.attrib.get("txn")
            metadata["status_message"] = (elem.text or "").strip()
            if elem.attrib.get("status") == "0":
                # Error response from API Setu
                raise DigiLockerXMLParsingError(
                    f"API Setu returned failure status: {metadata['status_message'] or 'Unknown error'}"
                )

    # Extract DocContent (PDF)
    for elem in root.iter():
        tag = _strip_tag_namespace(elem.tag)
        if tag == "DocContent" and elem.text:
            raw_b64 = elem.text.strip()
            try:
                decoded = base64.b64decode(raw_b64)
                if decoded.startswith(b"%PDF-") or len(decoded) > 0:
                    pdf_bytes = decoded
            except Exception:
                pass

        elif tag == "DataContent" and elem.text:
            data_str = elem.text.strip()
            # Can be base64-encoded inner XML or raw XML
            inner_xml = ""
            try:
                decoded_inner = base64.b64decode(data_str).decode("utf-8")
                if "<Certificate" in decoded_inner:
                    inner_xml = decoded_inner
            except Exception:
                if "<Certificate" in data_str:
                    inner_xml = data_str

            if inner_xml:
                try:
                    parsed_cert = parse_digilocker_certificate_xml(inner_xml)
                except Exception:
                    pass

    # If Certificate was not in DataContent, search entire tree
    if parsed_cert is None:
        try:
            parsed_cert = parse_digilocker_certificate_xml(xml_string)
        except Exception:
            pass

    return pdf_bytes, parsed_cert, metadata

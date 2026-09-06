# -*- coding: utf-8 -*-
"""
DigiLocker / API Setu Sandbox Integration Models.
Provides strongly typed dataclasses for OAuth tokens, user profiles,
document descriptors, parsed government certificates, and pulled payloads.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DigiLockerTokenResponse:
    """
    Standardized response from DigiLocker OAuth 2.0 Token Endpoint.
    """
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: Optional[str] = None
    refresh_token: Optional[str] = None
    consent_valid_till: Optional[str] = None
    digilocker_id: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, mask_token: bool = False) -> Dict[str, Any]:
        tok = self.access_token
        if mask_token and tok:
            tok = f"{tok[:4]}...{tok[-4:]}" if len(tok) > 8 else "***REDACTED***"
        ref_tok = self.refresh_token
        if mask_token and ref_tok:
            ref_tok = f"{ref_tok[:4]}...{ref_tok[-4:]}" if len(ref_tok) > 8 else "***REDACTED***"

        return {
            "access_token": tok,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
            "refresh_token": ref_tok,
            "consent_valid_till": self.consent_valid_till,
            "digilocker_id": self.digilocker_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DigiLockerTokenResponse":
        return cls(
            access_token=data.get("access_token", ""),
            token_type=data.get("token_type", "Bearer"),
            expires_in=int(data.get("expires_in", 3600)),
            scope=data.get("scope"),
            refresh_token=data.get("refresh_token"),
            consent_valid_till=data.get("consent_valid_till"),
            digilocker_id=data.get("digilockerid") or data.get("digilocker_id"),
            raw_response={k: v for k, v in data.items() if k not in ("access_token", "refresh_token")},
        )


@dataclass
class DigiLockerUserDetails:
    """
    User details returned by DigiLocker /user endpoint.
    """
    digilocker_id: str
    name: str
    dob: Optional[str] = None
    gender: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    eaadhaar: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "digilocker_id": self.digilocker_id,
            "name": self.name,
            "dob": self.dob,
            "gender": self.gender,
            "mobile": self.mobile,
            "email": self.email,
            "eaadhaar": self.eaadhaar,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DigiLockerUserDetails":
        return cls(
            digilocker_id=str(data.get("digilockerid") or data.get("digilocker_id") or ""),
            name=str(data.get("name") or ""),
            dob=data.get("dob"),
            gender=data.get("gender"),
            mobile=data.get("mobile"),
            email=data.get("email"),
            eaadhaar=data.get("eaadhaar"),
        )


@dataclass
class DigiLockerDocumentItem:
    """
    Descriptor for an issued document available in the user's DigiLocker.
    """
    uri: str
    name: str
    doc_type: str
    date: Optional[str] = None
    issuer: Optional[str] = None
    issuer_id: Optional[str] = None
    mime: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "doc_type": self.doc_type,
            "date": self.date,
            "issuer": self.issuer,
            "issuer_id": self.issuer_id,
            "mime": self.mime,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DigiLockerDocumentItem":
        return cls(
            uri=str(data.get("uri") or data.get("doc_id") or ""),
            name=str(data.get("name") or data.get("description") or ""),
            doc_type=str(data.get("type") or data.get("doctype") or data.get("doc_type") or "UNKNOWN"),
            date=data.get("date"),
            issuer=data.get("issuer"),
            issuer_id=data.get("issuer_id"),
            mime=data.get("mime", "application/pdf"),
            description=data.get("description"),
        )


@dataclass
class DigiLockerParsedCertificate:
    """
    Structured representation of a parsed official DigiLocker XML Certificate.
    Matches standard API Setu XML specification:
    <Certificate name="..." type="..." number="..." status="..." issueDate="...">
    """
    certificate_type: str
    certificate_name: str
    certificate_number: str
    issue_date: Optional[str] = None
    valid_from: Optional[str] = None
    expiry_date: Optional[str] = None
    status: str = "A"  # A = Active
    issuer_name: str = ""
    issuer_code: str = ""
    recipient_name: str = ""
    recipient_uid: Optional[str] = None
    recipient_organization: Optional[str] = None
    certificate_data: Dict[str, Any] = field(default_factory=dict)
    raw_xml: Optional[str] = None
    is_valid: bool = True
    verification_source: str = "DIGILOCKER_SANDBOX"

    def to_dict(self, include_raw_xml: bool = False) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "certificate_type": self.certificate_type,
            "certificate_name": self.certificate_name,
            "certificate_number": self.certificate_number,
            "issue_date": self.issue_date,
            "valid_from": self.valid_from,
            "expiry_date": self.expiry_date,
            "status": self.status,
            "issuer_name": self.issuer_name,
            "issuer_code": self.issuer_code,
            "recipient_name": self.recipient_name,
            "recipient_uid": self.recipient_uid,
            "recipient_organization": self.recipient_organization,
            "certificate_data": self.certificate_data,
            "is_valid": self.is_valid,
            "verification_source": self.verification_source,
        }
        if include_raw_xml and self.raw_xml:
            res["raw_xml"] = self.raw_xml
        return res


@dataclass
class DigiLockerPulledDocument:
    """
    Payload and parsed artifact returned after pulling a document from DigiLocker.
    """
    doc_uri: str
    doc_type: str
    mime_type: str = "application/pdf"
    pdf_content: Optional[bytes] = None
    xml_content: Optional[str] = None
    certificate: Optional[DigiLockerParsedCertificate] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_uri": self.doc_uri,
            "doc_type": self.doc_type,
            "mime_type": self.mime_type,
            "has_pdf": self.pdf_content is not None,
            "pdf_size_bytes": len(self.pdf_content) if self.pdf_content else 0,
            "has_xml": self.xml_content is not None,
            "certificate": self.certificate.to_dict() if self.certificate else None,
            "metadata": self.metadata,
        }

# -*- coding: utf-8 -*-
"""
FastAPI Router for DigiLocker / API Setu Sandbox Integration.
Endpoints:
- GET  /api/v1/integrations/digilocker/status
- GET  /api/v1/integrations/digilocker/authorize
- GET  /api/v1/integrations/digilocker/callback
- GET  /api/v1/integrations/digilocker/user
- GET  /api/v1/integrations/digilocker/documents
- POST /api/v1/integrations/digilocker/pull
- POST /api/v1/integrations/digilocker/revoke
- GET  /api/v1/integrations/digilocker/audit-logs
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from backend.integrations.digilocker import (
    DigiLockerAuthError,
    DigiLockerClientError,
    DigiLockerConfig,
    DigiLockerEvidenceAdapter,
    DigiLockerNetworkError,
    DigiLockerSandboxClient,
    default_audit_logger,
    default_pkce_store,
)

router = APIRouter(prefix="/api/v1/integrations/digilocker", tags=["DigiLocker Integration"])

# Dependency to provide client instance
def get_digilocker_client() -> DigiLockerSandboxClient:
    config = DigiLockerConfig.from_env()
    return DigiLockerSandboxClient(config=config, audit_logger=default_audit_logger)


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------
class DigiLockerStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    environment: str
    base_url: str
    redirect_uri: str


class AuthorizeResponse(BaseModel):
    authorization_url: str
    state: str
    code_challenge: str


class TokenExchangeResponse(BaseModel):
    status: str = "SUCCESS"
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: Optional[str] = None
    access_token_hash: str
    access_token: str
    digilocker_id: Optional[str] = None


class PullDocumentRequest(BaseModel):
    doc_uri: str = Field(..., description="URI or ID of document in DigiLocker")
    doc_type: Optional[str] = Field(None, description="Document type identifier")
    token: Optional[str] = Field(None, description="Access token (if not sent in Authorization header)")
    bid_id: Optional[str] = Field(None, description="Optional bid ID to bind extracted BidderFact")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform parsed certificate into BidderFact")


class RevokeTokenRequest(BaseModel):
    token: str = Field(..., description="Access or refresh token to revoke")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _extract_token(authorization: Optional[str] = Header(None), fallback_token: Optional[str] = None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if fallback_token and fallback_token.strip():
        return fallback_token.strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid Bearer authorization token.",
    )


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@router.get("/status", response_model=DigiLockerStatusResponse)
async def get_status(client: DigiLockerSandboxClient = Depends(get_digilocker_client)):
    """
    Returns the current status, mode, and configuration of DigiLocker sandbox integration.
    """
    cfg = client.config
    return DigiLockerStatusResponse(
        enabled=cfg.enabled,
        configured=cfg.is_configured(),
        environment=cfg.environment,
        base_url=cfg.base_url,
        redirect_uri=cfg.redirect_uri,
    )


@router.get("/authorize", response_model=AuthorizeResponse)
async def get_authorization_url(
    scope: str = "openid profile",
    client: DigiLockerSandboxClient = Depends(get_digilocker_client),
):
    """
    Initiates PKCE OAuth 2.0 flow. Generates cryptographically secure state and
    code_verifier, registers verifier in state store, and returns authorization URL.
    """
    auth_data = client.get_authorization_url(scope=scope)

    # Securely store state -> verifier mapping for callback completion
    default_pkce_store.store(
        state=auth_data["state"],
        verifier=auth_data["code_verifier"],
        metadata={"scope": scope},
    )

    return AuthorizeResponse(
        authorization_url=auth_data["url"],
        state=auth_data["state"],
        code_challenge=auth_data["code_challenge"],
    )


@router.get("/callback", response_model=TokenExchangeResponse)
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    client: DigiLockerSandboxClient = Depends(get_digilocker_client),
):
    """
    Receives OAuth redirect callback from DigiLocker / API Setu sandbox.
    Validates state token, retrieves PKCE code_verifier, and exchanges code for access token.
    """
    if error:
        default_audit_logger.log(
            event_type="OAUTH_CALLBACK_ERROR",
            status="FAILED",
            trace_id=state,
            details={"error": error, "description": error_description},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DigiLocker returned authorization error: {error_description or error}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both 'code' and 'state' query parameters are required in callback.",
        )

    # Validate state and retrieve code_verifier (one-time use)
    verifier = default_pkce_store.pop(state)
    if not verifier:
        default_audit_logger.log(
            event_type="OAUTH_STATE_INVALID",
            status="FAILED",
            trace_id=state,
            details={"reason": "State token not found or expired"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or previously used state parameter (CSRF protection).",
        )

    # Exchange code using PKCE verifier
    try:
        token_resp = client.exchange_code(code=code, code_verifier=verifier)
    except DigiLockerAuthError as ae:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(ae))
    except DigiLockerNetworkError as ne:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(ne))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token exchange failed.")

    from backend.integrations.digilocker.audit import hash_token
    return TokenExchangeResponse(
        status="SUCCESS",
        token_type=token_resp.token_type,
        expires_in=token_resp.expires_in,
        scope=token_resp.scope,
        access_token_hash=hash_token(token_resp.access_token),
        access_token=token_resp.access_token,
        digilocker_id=token_resp.digilocker_id,
    )


@router.get("/user")
async def get_user_profile(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    client: DigiLockerSandboxClient = Depends(get_digilocker_client),
):
    """
    Fetches user profile details for the authenticated DigiLocker account.
    """
    access_token = _extract_token(authorization, token)
    try:
        user = client.get_user_details(access_token)
        return user.to_dict()
    except DigiLockerAuthError as ae:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(ae))
    except DigiLockerNetworkError as ne:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(ne))
    except DigiLockerClientError as ce:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ce))


@router.get("/documents")
async def get_issued_documents(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    client: DigiLockerSandboxClient = Depends(get_digilocker_client),
):
    """
    Lists issued certificates available in the user's DigiLocker repository.
    """
    access_token = _extract_token(authorization, token)
    try:
        docs = client.get_issued_documents(access_token)
        return [d.to_dict() for d in docs]
    except DigiLockerAuthError as ae:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(ae))
    except DigiLockerNetworkError as ne:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(ne))
    except DigiLockerClientError as ce:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ce))


@router.post("/pull")
async def pull_document(
    request: PullDocumentRequest,
    authorization: Optional[str] = Header(None),
    client: DigiLockerSandboxClient = Depends(get_digilocker_client),
):
    """
    Pulls a specific document/certificate by URI from DigiLocker sandbox.
    Optionally transforms the parsed certificate into a canonical BidderFact.
    """
    access_token = _extract_token(authorization, request.token)
    try:
        pulled = client.pull_document(
            access_token=access_token,
            doc_uri=request.doc_uri,
            doc_type=request.doc_type,
        )
    except DigiLockerAuthError as ae:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(ae))
    except DigiLockerNetworkError as ne:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(ne))
    except DigiLockerClientError as ce:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ce))

    res = pulled.to_dict()

    # Optional BidderFact transformation
    if request.convert_to_bidder_fact and pulled.certificate:
        bid_id = request.bid_id or "BID-DL-PULLED"
        fact = DigiLockerEvidenceAdapter.certificate_to_bidder_fact(pulled.certificate, bid_id=bid_id)
        res["bidder_fact"] = fact.to_dict()

    return res


@router.post("/revoke")
async def revoke_token(
    request: RevokeTokenRequest,
    client: DigiLockerSandboxClient = Depends(get_digilocker_client),
):
    """
    Revokes an active access or refresh token.
    """
    success = client.revoke_token(request.token)
    return {"revoked": success}


@router.get("/audit-logs")
async def get_audit_logs(
    event_type: Optional[str] = Query(None),
):
    """
    Retrieves sanitized audit logs for government integration transactions.
    Guaranteed zero secret leakage.
    """
    events = default_audit_logger.get_events(event_type=event_type)
    return {"count": len(events), "events": events}

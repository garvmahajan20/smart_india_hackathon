# -*- coding: utf-8 -*-
import hashlib
import os
import shutil
import tempfile
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import load_dotenv
from backend.extraction.models import LLMMode
from backend.orchestration import VerificationOrchestrator
from .schemas import (
    AggregatedVerificationResponse,
    ErrorResponse,
    HealthResponse,
    HumanReviewItemResponse,
    VerificationDossierResponse,
)

load_dotenv()

# Limits & Security Configuration
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXTENSIONS = {".pdf"}
PDF_MAGIC_HEADER = b"%PDF-"

app = FastAPI(
    title="GeM Bid Compliance Verification Platform API",
    description="End-to-End Orchestration & Verification Engine for GeM Procurement",
    version="1.0.0",
)

# Enable CORS for future frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Orchestrator Instances (cached/mock by default to conserve quota)
_orchestrator = VerificationOrchestrator(mode=LLMMode.MOCK)

def get_orchestrator(mode_str: str = "mock") -> VerificationOrchestrator:
    mode_upper = mode_str.upper()
    if mode_upper == "LIVE":
        return VerificationOrchestrator(mode=LLMMode.LIVE)
    elif mode_upper == "CACHED":
        return VerificationOrchestrator(mode=LLMMode.CACHED)
    return _orchestrator

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "detail": None},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception):
    # Never leak internal stack traces or secrets to clients
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal processing error occurred during verification.", "detail": None},
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    active_model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    return HealthResponse(
        status="HEALTHY",
        version="1.0.0",
        active_model=active_model,
        mode=_orchestrator.mode.value if hasattr(_orchestrator.mode, 'value') else str(_orchestrator.mode),
    )

def _validate_and_save_file(upload_file: UploadFile, target_dir: str) -> str:
    # 1. Filename & Path Traversal Validation
    raw_name = upload_file.filename or "document.pdf"
    if ".." in raw_name or "/" in raw_name or "\\" in raw_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path traversal detected in filename: {raw_name}",
        )
    safe_name = os.path.basename(raw_name)

    # 2. Extension Validation
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Only .pdf files are accepted.",
        )

    # 3. Read Content & Check Size
    content = upload_file.file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{safe_name}' exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    # 4. Magic Byte Check
    if not content.startswith(PDF_MAGIC_HEADER):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{safe_name}' is not a valid PDF (missing %PDF- header).",
        )

    # 5. Write to secure isolated path
    dest_path = os.path.join(target_dir, safe_name)
    with open(dest_path, "wb") as f:
        f.write(content)

    return dest_path

@app.post(
    "/api/v1/verify",
    response_model=AggregatedVerificationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def verify_bid(
    tender_file: UploadFile = File(..., description="Tender document PDF"),
    bid_files: List[UploadFile] = File(..., description="Bidder submission PDF(s)"),
    tender_id: Optional[str] = Form(None),
    bid_id: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    mode: Optional[str] = Form("mock"),
):
    """
    End-to-End Bid Verification Endpoint.
    Ingests uploaded tender and bid PDFs, extracts requirements and claims,
    and runs deterministic compliance and integrity verification.
    """
    if not bid_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one bidder document must be uploaded.",
        )

    # Create secure isolated temporary directory for file processing
    temp_dir = tempfile.mkdtemp(prefix="gem_verif_")
    try:
        # Validate and save tender file
        tender_path = _validate_and_save_file(tender_file, temp_dir)

        # Validate and save bid files
        bid_paths = []
        for bf in bid_files:
            b_path = _validate_and_save_file(bf, temp_dir)
            bid_paths.append(b_path)

        # Get orchestrator for requested mode (defaults to MOCK to conserve quota)
        orch = get_orchestrator(mode or "mock")

        # Execute end-to-end verification
        try:
            aggregated, _ = orch.verify_submission(
                tender_document_path=tender_path,
                bid_document_paths=bid_paths,
                tender_id=tender_id,
                bid_id=bid_id,
                company_name_hint=company_name,
            )
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve),
            )

        return aggregated.to_dict()

    finally:
        # Secure deterministic cleanup: purge temporary directory and uploads
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

@app.get(
    "/api/v1/verification/{verification_id}",
    response_model=AggregatedVerificationResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_verification_status(verification_id: str):
    """
    Retrieves verification status and summary by verification ID.
    """
    res = _orchestrator.get_verification(verification_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification '{verification_id}' not found.",
        )
    return res.to_dict()

@app.get(
    "/api/v1/verification/{verification_id}/dossier",
    response_model=VerificationDossierResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_verification_dossier(verification_id: str):
    """
    Retrieves complete machine-readable audit dossier for procurement officers.
    """
    dossier = _orchestrator.get_dossier(verification_id)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier for verification '{verification_id}' not found.",
        )
    return dossier.to_dict()

@app.get(
    "/api/v1/verification/{verification_id}/review-items",
    response_model=List[HumanReviewItemResponse],
    responses={404: {"model": ErrorResponse}}
)
async def get_verification_review_items(verification_id: str):
    """
    Retrieves human review queue items for a verification.
    """
    res = _orchestrator.get_verification(verification_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification '{verification_id}' not found.",
        )
    return res.human_review_items

import dataclasses as dc
from enum import Enum
from typing import Any, Dict, List, Optional

class LLMMode(str, Enum):
    LIVE = "LIVE"
    CACHED = "CACHED"
    MOCK = "MOCK"

class ExtractionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    GROUNDING_FAILED = "GROUNDING_FAILED"
    SCHEMA_FAILED = "SCHEMA_FAILED"
    FAILED = "FAILED"

@dc.dataclass
class LLMProviderResponse:
    """
    Standard response returned by an LLM provider.
    """
    content: str
    model_name: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: float = 0.0
    is_mock: bool = False
    is_cached: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "model_name": self.model_name,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_ms": round(self.latency_ms, 2),
            "is_mock": self.is_mock,
            "is_cached": self.is_cached,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMProviderResponse":
        return cls(
            content=data["content"],
            model_name=data["model_name"],
            prompt_tokens=data.get("prompt_tokens"),
            completion_tokens=data.get("completion_tokens"),
            latency_ms=data.get("latency_ms", 0.0),
            is_mock=data.get("is_mock", False),
            is_cached=data.get("is_cached", False),
            error=data.get("error"),
        )

@dc.dataclass
class CandidateRequirement:
    """
    Candidate requirement parsed from LLM structured JSON output
    prior to deterministic evidence grounding and normalization.
    """
    description: str
    category: str
    field: Optional[str] = None
    operator: str = "=="
    expected_value: Any = None
    mandatory: bool = True
    evidence_block_ids: List[str] = dc.field(default_factory=list)
    source_clause: Optional[str] = None
    applicability: Optional[Dict[str, Any]] = None
    extraction_confidence: str = "HIGH"
    requirement_type: Optional[str] = "BIDDER_COMPLIANCE"
    source_pass: Optional[str] = None

@dc.dataclass
class CandidateFact:
    """
    Candidate bidder fact parsed from LLM structured JSON output
    prior to deterministic evidence grounding and normalization.
    """
    field: str
    raw_value: Any
    evidence_block_ids: List[str] = dc.field(default_factory=list)
    extraction_confidence: str = "HIGH"
    metadata: Optional[Dict[str, Any]] = None

@dc.dataclass
class GroundingValidationResult:
    """
    Result of deterministic evidence grounding validation.
    """
    is_valid: bool
    status: ExtractionStatus
    errors: List[str] = dc.field(default_factory=list)
    warnings: List[str] = dc.field(default_factory=list)
    resolved_evidence: List[Dict[str, Any]] = dc.field(default_factory=list)
    primary_page: int = 1
    primary_bbox: Optional[List[float]] = None
    raw_snippet: str = ""

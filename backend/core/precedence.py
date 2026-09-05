from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import SourceType, TenderRequirement

# Canonical Priority Mapping
SOURCE_PRIORITY_MAP: Dict[str, int] = {
    SourceType.CORRIGENDUM.value: 4,
    SourceType.ATC.value: 3,
    SourceType.BUYER_ADDED_SPECIFIC.value: 3,
    SourceType.STC.value: 2,
    SourceType.GTC.value: 1,
    SourceType.CUSTOM.value: 1,
    SourceType.INFERRED.value: 0,
    SourceType.UNSPECIFIED.value: 0,
    SourceType.UNKNOWN.value: 0,
}

@dataclass
class PrecedenceResolutionResult:
    all_requirements: List[TenderRequirement]
    effective_requirements: List[TenderRequirement]
    superseded_requirements: List[TenderRequirement]
    precedence_chains: Dict[str, List[str]] = field(default_factory=dict)
    explanations: List[str] = field(default_factory=list)

def resolve_precedence(requirements: List[TenderRequirement]) -> PrecedenceResolutionResult:
    """
    Resolves GTC < STC < ATC precedence deterministically.
    Higher priority overrides conflicting requirements on the same field/dimension.
    CRITICAL RULE: Lower-priority requirements are NEVER deleted.
    Their provenance and superseded_by relationships are fully preserved.
    """
    # Group requirements by conflict dimension (primarily the 'field' key)
    grouped: Dict[str, List[TenderRequirement]] = defaultdict(list)
    for req in requirements:
        # If source_priority is 0 or default, populate from known source_type if available
        if req.source_priority == 0 and req.source_type in SOURCE_PRIORITY_MAP:
            req.source_priority = SOURCE_PRIORITY_MAP[req.source_type]

        # Use field as conflict dimension, fallback to requirement_id if field is None
        dim = req.field if req.field else f"unique_{req.requirement_id}"
        grouped[dim].append(req)

    all_reqs: List[TenderRequirement] = []
    effective_reqs: List[TenderRequirement] = []
    superseded_reqs: List[TenderRequirement] = []
    chains: Dict[str, List[str]] = {}
    explanations: List[str] = []

    for dim, req_list in grouped.items():
        if len(req_list) == 1:
            # Single requirement for this dimension - no conflict
            req = req_list[0]
            req.is_effective = True
            req.superseded_by = None
            req.supersedes = None
            all_reqs.append(req)
            effective_reqs.append(req)
            continue

        # Multiple requirements for the same dimension: sort by priority descending
        # Secondary sort by requirement_id for deterministic tie-breaking
        sorted_reqs = sorted(
            req_list,
            key=lambda r: (r.source_priority, r.requirement_id),
            reverse=True
        )

        chain_ids = [r.requirement_id for r in sorted_reqs]
        chains[dim] = chain_ids

        # Highest priority requirement becomes the effective requirement
        winner = sorted_reqs[0]
        winner.is_effective = True
        winner.superseded_by = None

        # Lower priority requirements are superseded
        superseded_ids = []
        for i in range(1, len(sorted_reqs)):
            lower = sorted_reqs[i]
            higher = sorted_reqs[i - 1]
            lower.is_effective = False
            lower.superseded_by = winner.requirement_id
            lower.precedence_notes = (
                f"Superseded by {winner.requirement_id} "
                f"({winner.source_type}, priority {winner.source_priority}) on field '{dim}'."
            )
            superseded_reqs.append(lower)
            superseded_ids.append(lower.requirement_id)

            explanation = (
                f"Precedence applied on '{dim}': {lower.requirement_id} ({lower.source_type}, prio {lower.source_priority}) "
                f"superseded by {winner.requirement_id} ({winner.source_type}, prio {winner.source_priority})."
            )
            explanations.append(explanation)

        winner.supersedes = ", ".join(superseded_ids)
        effective_reqs.append(winner)
        all_reqs.extend(sorted_reqs)

    return PrecedenceResolutionResult(
        all_requirements=all_reqs,
        effective_requirements=effective_reqs,
        superseded_requirements=superseded_reqs,
        precedence_chains=chains,
        explanations=explanations
    )

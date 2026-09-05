# -*- coding: utf-8 -*-
"""
Phase 10B.5: Adversarial & Tamper Regression Framework.

Defines:
1. Attack taxonomy enumerations (Categories, Target Layers, Detection Mechanisms).
2. AdversarialAttackResult data model for deterministic tracking.
3. AdversarialManifest registry for recording and verifying all attack executions.
4. Metric calculations (detected, rejected, silently accepted, false positives, false negatives).
"""

from dataclasses import dataclass, field as dc_field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import json
import time


class AttackCategory(str, Enum):
    EVIDENCE = "EVIDENCE_ATTACK"
    PROVENANCE = "PROVENANCE_ATTACK"
    ONTOLOGY = "ONTOLOGY_ATTACK"
    REQUIREMENT = "REQUIREMENT_ATTACK"
    RULE_ENGINE = "RULE_ENGINE_ATTACK"
    CROSS_FIELD = "CROSS_FIELD_SWAP"
    CONTRADICTION = "CONTRADICTION_ATTACK"
    GOVERNMENT = "GOVERNMENT_RESPONSE_ATTACK"
    AGGREGATION = "AGGREGATION_ATTACK"
    SNAPSHOT = "SNAPSHOT_ATTACK"
    REPLAY = "REPLAY_ATTACK"
    CROSS_LAYER = "CROSS_LAYER_ATTACK"
    NEGATIVE_CONTROL = "NEGATIVE_CONTROL"


class TargetLayer(str, Enum):
    INGESTION = "STEP_6_INGESTION"
    EVIDENCE_GROUNDER = "EVIDENCE_GROUNDER"
    CANONICAL_ONTOLOGY = "CANONICAL_ONTOLOGY"
    RULE_ENGINE = "STEP_4_RULE_ENGINE"
    CONTRADICTION_ENGINE = "STEP_5_CONTRADICTION_ENGINE"
    GOVERNMENT_ADAPTER = "STEP_5_GOVERNMENT_ADAPTER"
    AGGREGATOR = "STEP_8_AGGREGATOR"
    PROVENANCE_DAG = "PROVENANCE_DAG"
    AUDIT_SNAPSHOT = "AUDIT_SNAPSHOT"
    REPLAY_ENGINE = "DETERMINISTIC_REPLAY_ENGINE"
    MULTI_LAYER = "MULTI_LAYER_DEFENSE"


class DetectionMechanism(str, Enum):
    GROUNDING_FAILURE = "GROUNDING_FAILURE"
    ONTOLOGY_REJECTION = "ONTOLOGY_REJECTION"
    COMPLIANCE_STATUS_FAIL = "COMPLIANCE_STATUS_FAIL"
    INTEGRITY_CONTRADICTION = "INTEGRITY_CONTRADICTION"
    HUMAN_REVIEW_FLAG = "HUMAN_REVIEW_FLAG"
    SNAPSHOT_HASH_MISMATCH = "SNAPSHOT_HASH_MISMATCH"
    CONFIG_HASH_MISMATCH = "CONFIG_HASH_MISMATCH"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
    REPLAY_MISMATCH = "REPLAY_MISMATCH"
    DAG_PROVENANCE_MISMATCH = "DAG_PROVENANCE_MISMATCH"
    DAG_CYCLE_DETECTED = "DAG_CYCLE_DETECTED"
    ACCEPTED_CLEAN = "ACCEPTED_CLEAN"  # Expected for negative controls


@dataclass
class AdversarialAttackResult:
    """Structured deterministic report of an individual adversarial attack test."""
    attack_id: str
    category: str
    description: str
    mutation: str
    target_layer: str
    expected_detection: str
    actual_detection: str
    expected_status: str
    actual_status: str
    passed: bool
    affected_ids: List[str] = dc_field(default_factory=list)
    deterministic: bool = True
    execution_time_ms: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AdversarialManifest:
    """
    Central deterministic registry tracking adversarial regression results.
    Validates anti-tampering invariants:
        silently_accepted == 0
        false_negative_count == 0
    """

    def __init__(self, manifest_name: str = "SIH_ADVERSARIAL_MANIFEST_V1"):
        self.manifest_name = manifest_name
        self.results: List[AdversarialAttackResult] = []
        self.results_by_id: Dict[str, AdversarialAttackResult] = {}
        self.created_at = time.time()

    def record(self, result: AdversarialAttackResult) -> None:
        self.results.append(result)
        self.results_by_id[result.attack_id] = result

    @property
    def total_attacks(self) -> int:
        return len(self.results)

    @property
    def attacks_detected(self) -> int:
        """Count of attacks that triggered an active defense detection."""
        return sum(
            1 for r in self.results
            if r.category != AttackCategory.NEGATIVE_CONTROL.value
            and r.actual_detection != DetectionMechanism.ACCEPTED_CLEAN.value
        )

    @property
    def attacks_rejected(self) -> int:
        """Count of attacks where the system actively refused or flagged the mutation."""
        return sum(
            1 for r in self.results
            if r.category != AttackCategory.NEGATIVE_CONTROL.value and r.passed
        )

    @property
    def attacks_silently_accepted(self) -> int:
        """CRITICAL: Unauthorized mutations that slipped through without detection."""
        return sum(
            1 for r in self.results
            if r.category != AttackCategory.NEGATIVE_CONTROL.value
            and r.actual_detection == DetectionMechanism.ACCEPTED_CLEAN.value
        )

    @property
    def false_positive_count(self) -> int:
        """Legitimate negative controls that were incorrectly rejected."""
        return sum(
            1 for r in self.results
            if r.category == AttackCategory.NEGATIVE_CONTROL.value and not r.passed
        )

    @property
    def false_negative_count(self) -> int:
        """Attacks that failed to be detected."""
        return sum(
            1 for r in self.results
            if r.category != AttackCategory.NEGATIVE_CONTROL.value and not r.passed
        )

    @property
    def deterministic_pass_count(self) -> int:
        """All tests (attacks + negative controls) that passed as expected."""
        return sum(1 for r in self.results if r.passed and r.deterministic)

    def summary(self) -> Dict[str, Any]:
        return {
            "manifest_name": self.manifest_name,
            "total_attacks": self.total_attacks,
            "attacks_detected": self.attacks_detected,
            "attacks_rejected": self.attacks_rejected,
            "attacks_silently_accepted": self.attacks_silently_accepted,
            "false_positive_count": self.false_positive_count,
            "false_negative_count": self.false_negative_count,
            "deterministic_pass_count": self.deterministic_pass_count,
            "pass_rate_pct": (self.deterministic_pass_count / self.total_attacks * 100.0) if self.total_attacks > 0 else 0.0,
        }

    def print_summary(self) -> None:
        s = self.summary()
        print("=" * 80)
        print(f"       ADVERSARIAL REGRESSION MANIFEST: {self.manifest_name}")
        print("=" * 80)
        print(f"  Total Attacks Executed       : {s['total_attacks']}")
        print(f"  Attacks Successfully Detected: {s['attacks_detected']}")
        print(f"  Attacks Rejected / Flagged   : {s['attacks_rejected']}")
        print(f"  Attacks Silently Accepted    : {s['attacks_silently_accepted']} (Target: 0)")
        print(f"  False Positives              : {s['false_positive_count']} (Target: 0)")
        print(f"  False Negatives              : {s['false_negative_count']} (Target: 0)")
        print(f"  Deterministic Pass Count     : {s['deterministic_pass_count']} / {s['total_attacks']} ({s['pass_rate_pct']:.2f}%)")
        print("=" * 80)

    def to_json(self, indent: int = 2) -> str:
        data = {
            "summary": self.summary(),
            "results": [r.to_dict() for r in self.results],
        }
        return json.dumps(data, indent=indent, ensure_ascii=False)

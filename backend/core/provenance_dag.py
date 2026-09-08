# -*- coding: utf-8 -*-
"""
Deterministic In-Memory Provenance DAG & Explainability Trace.

Architectural Principles:
    DECISION IS DETERMINISTIC
    PROVENANCE IS EXPLICIT
    EVIDENCE IS PHYSICAL
    GRAPH IS EXPLANATORY, NOT DECISION-MAKING

Connects physical document evidence to normalized bidder facts, canonical field identity,
deterministic compliance verification results, cross-document integrity findings,
and human-review items. Strictly acyclic, in-memory, stdlib-only, and byte-for-byte deterministic.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import BidderFact, TenderRequirement, VerificationResult
from .ontology import ResolutionStatus, resolve_field
from backend.verification.models import IntegrityFinding


class NodeType(str, Enum):
    TENDER_REQUIREMENT = "TENDER_REQUIREMENT"
    BIDDER_FACT = "BIDDER_FACT"
    PHYSICAL_TEXT_BLOCK = "PHYSICAL_TEXT_BLOCK"
    CANONICAL_FIELD = "CANONICAL_FIELD"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"
    INTEGRITY_FINDING = "INTEGRITY_FINDING"
    HUMAN_REVIEW_ITEM = "HUMAN_REVIEW_ITEM"
    OFFICER_ADJUDICATION = "OFFICER_ADJUDICATION"


class EdgeType(str, Enum):
    REQUIREMENT_HAS_EVIDENCE = "REQUIREMENT_HAS_EVIDENCE"
    FACT_SATISFIES_REQUIREMENT = "FACT_SATISFIES_REQUIREMENT"
    FACT_GROUNDED_BY = "FACT_GROUNDED_BY"
    FACT_CANONICALIZED_AS = "FACT_CANONICALIZED_AS"
    RESULT_EVALUATES_REQUIREMENT = "RESULT_EVALUATES_REQUIREMENT"
    RESULT_EVALUATES_FACT = "RESULT_EVALUATES_FACT"
    RESULT_SUPPORTED_BY = "RESULT_SUPPORTED_BY"
    RESULT_AFFECTED_BY_INTEGRITY = "RESULT_AFFECTED_BY_INTEGRITY"
    INTEGRITY_FINDING_COMPARES = "INTEGRITY_FINDING_COMPARES"
    REVIEW_ITEM_FOR_RESULT = "REVIEW_ITEM_FOR_RESULT"
    REVIEW_ITEM_SUPPORTED_BY = "REVIEW_ITEM_SUPPORTED_BY"
    ADJUDICATION_FOR_REVIEW_ITEM = "ADJUDICATION_FOR_REVIEW_ITEM"
    ADJUDICATION_OVERRIDES_RESULT = "ADJUDICATION_OVERRIDES_RESULT"


class GraphValidationError(Exception):
    """Raised when the provenance graph violates structural invariants."""
    pass


class CycleDetectedError(GraphValidationError):
    """Raised when an edge or graph construction would violate acyclicity."""
    pass


@dataclass(frozen=True)
class ProvenanceNode:
    """Represents a discrete immutable entity in the provenance DAG."""
    node_id: str
    node_type: str
    label: str
    properties: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "properties": self.properties,
        }


@dataclass(frozen=True)
class ProvenanceEdge:
    """Represents a directed typed dependency between two provenance nodes."""
    edge_id: str
    source_id: str
    edge_type: str
    target_id: str
    properties: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "edge_type": self.edge_type,
            "target_id": self.target_id,
            "properties": self.properties,
        }


def make_block_node_id(document: str, page: int, block_id: Optional[str] = None, bbox: Optional[List[float]] = None, snippet: Optional[str] = None) -> str:
    """
    Deterministically computes a stable ID for a physical evidence text block.
    Prefers explicit block_id; falls back to bbox coordinates, then snippet hash.
    """
    doc_clean = str(document or "UNKNOWN_DOC").strip().replace(" ", "_")
    p = max(1, int(page or 1))
    if block_id:
        b_clean = str(block_id).strip().replace(" ", "_")
        return f"BLOCK:{doc_clean}:P{p}:{b_clean}"
    elif bbox and len(bbox) == 4:
        b_coords = "_".join(f"{float(c):.1f}" for c in bbox)
        return f"BLOCK:{doc_clean}:P{p}:BBOX_{b_coords}"
    elif snippet:
        snip_hash = hashlib.sha256(snippet.strip().encode("utf-8")).hexdigest()[:10].upper()
        return f"BLOCK:{doc_clean}:P{p}:SNIP_{snip_hash}"
    else:
        return f"BLOCK:{doc_clean}:P{p}:PRIMARY"


def make_edge_id(source_id: str, edge_type: str, target_id: str, discriminator: Optional[str] = None) -> str:
    """Computes a deterministic unique identifier for a directed edge."""
    disc = f":{discriminator}" if discriminator else ""
    return f"EDGE:{source_id}:{edge_type}:{target_id}{disc}"


class ProvenanceDAG:
    """
    Deterministic In-Memory Directed Acyclic Graph.
    Maintains typed nodes, directed edges, and bidirectional adjacency indices.
    """

    def __init__(self, bid_id: Optional[str] = None, tender_id: Optional[str] = None):
        self.bid_id = bid_id or "UNKNOWN_BID"
        self.tender_id = tender_id or "UNKNOWN_TENDER"
        self.nodes: Dict[str, ProvenanceNode] = {}
        self.edges: Dict[str, ProvenanceEdge] = {}
        self.adj: Dict[str, List[str]] = {}       # source_id -> list of edge_ids
        self.rev_adj: Dict[str, List[str]] = {}   # target_id -> list of edge_ids

    def add_node(self, node: ProvenanceNode) -> ProvenanceNode:
        """Adds a node to the graph. Idempotent if identical."""
        if node.node_id in self.nodes:
            existing = self.nodes[node.node_id]
            if existing.node_type != node.node_type:
                raise GraphValidationError(
                    f"Conflicting node registration for ID '{node.node_id}': "
                    f"existing type '{existing.node_type}' != incoming type '{node.node_type}'"
                )
            return existing

        self.nodes[node.node_id] = node
        self.adj[node.node_id] = []
        self.rev_adj[node.node_id] = []
        return node

    def add_edge(self, edge: ProvenanceEdge) -> ProvenanceEdge:
        """
        Adds a directed edge between two existing nodes.
        Validates endpoints and enforces deduplication and acyclicity.
        """
        if edge.source_id not in self.nodes:
            raise GraphValidationError(
                f"Dangling edge source: node '{edge.source_id}' does not exist in graph"
            )
        if edge.target_id not in self.nodes:
            raise GraphValidationError(
                f"Dangling edge target: node '{edge.target_id}' does not exist in graph"
            )

        # Idempotent deduplication
        if edge.edge_id in self.edges:
            return self.edges[edge.edge_id]

        # Prevent self-loops
        if edge.source_id == edge.target_id:
            raise CycleDetectedError(
                f"Self-loop cycle detected: source and target are both '{edge.source_id}'"
            )

        # Quick cycle guard: check if target can reach source (reverse path exists)
        if self._can_reach(edge.target_id, edge.source_id):
            raise CycleDetectedError(
                f"Cycle detected: adding edge '{edge.source_id}' -> '{edge.target_id}' creates a cycle"
            )

        self.edges[edge.edge_id] = edge
        self.adj[edge.source_id].append(edge.edge_id)
        self.rev_adj[edge.target_id].append(edge.edge_id)
        return edge

    def _can_reach(self, start_id: str, goal_id: str, visited: Optional[Set[str]] = None) -> bool:
        """DFS check to determine if goal_id is reachable from start_id."""
        if start_id == goal_id:
            return True
        if visited is None:
            visited = set()
        visited.add(start_id)

        for edge_id in self.adj.get(start_id, []):
            target = self.edges[edge_id].target_id
            if target not in visited:
                if self._can_reach(target, goal_id, visited):
                    return True
        return False

    def validate(self) -> None:
        """
        Validates complete graph structural invariants:
        - Unique IDs
        - No dangling endpoints
        - Strictly acyclic
        - Valid node and edge types
        """
        valid_node_types = {t.value for t in NodeType}
        valid_edge_types = {t.value for t in EdgeType}

        for n_id, node in self.nodes.items():
            if node.node_type not in valid_node_types:
                raise GraphValidationError(f"Invalid node_type '{node.node_type}' for node '{n_id}'")

        for e_id, edge in self.edges.items():
            if edge.edge_type not in valid_edge_types:
                raise GraphValidationError(f"Invalid edge_type '{edge.edge_type}' for edge '{e_id}'")
            if edge.source_id not in self.nodes:
                raise GraphValidationError(f"Dangling edge source '{edge.source_id}' in edge '{e_id}'")
            if edge.target_id not in self.nodes:
                raise GraphValidationError(f"Dangling edge target '{edge.target_id}' in edge '{e_id}'")

        # Cycle check via topological sort (Kahn's Algorithm)
        in_degrees = {n_id: 0 for n_id in self.nodes}
        for edge in self.edges.values():
            in_degrees[edge.target_id] += 1

        queue = [n_id for n_id, deg in in_degrees.items() if deg == 0]
        visited_count = 0

        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for e_id in self.adj.get(curr, []):
                tgt = self.edges[e_id].target_id
                in_degrees[tgt] -= 1
                if in_degrees[tgt] == 0:
                    queue.append(tgt)

        if visited_count != len(self.nodes):
            raise CycleDetectedError("Topological sort failed: graph contains one or more cycles")

    # ==================== TRAVERSAL CAPABILITIES ====================

    def trace_decision(self, result_id: str) -> Dict[str, Any]:
        """
        Decision -> Evidence Traversal.
        Given a VerificationResult ID, traverses downward to retrieve all linked
        requirements, facts, canonical fields, and physical text blocks.
        """
        node_id = result_id if result_id.startswith("RESULT:") else f"RESULT:{result_id}"
        if node_id not in self.nodes:
            raise KeyError(f"Verification result node '{node_id}' not found in provenance graph")

        result_node = self.nodes[node_id]
        trace: Dict[str, Any] = {
            "result_id": result_node.properties.get("verification_id", result_id),
            "status": result_node.properties.get("status"),
            "severity": result_node.properties.get("severity"),
            "requirements": [],
            "facts": [],
            "canonical_fields": [],
            "evidence_blocks": [],
            "integrity_findings": [],
            "review_items": [],
            "decision_rule": {
                "operator": result_node.properties.get("operator_used"),
                "expected": result_node.properties.get("expected"),
                "actual": result_node.properties.get("actual"),
                "reason": result_node.properties.get("reason"),
            },
        }

        # Downward edges from result
        for e_id in self.adj.get(node_id, []):
            edge = self.edges[e_id]
            tgt_node = self.nodes[edge.target_id]

            if edge.edge_type == EdgeType.RESULT_EVALUATES_REQUIREMENT.value:
                trace["requirements"].append(tgt_node.properties)
                # Requirement physical evidence
                for req_e_id in self.adj.get(tgt_node.node_id, []):
                    req_edge = self.edges[req_e_id]
                    if req_edge.edge_type == EdgeType.REQUIREMENT_HAS_EVIDENCE.value:
                        blk = self.nodes[req_edge.target_id]
                        if blk.properties not in trace["evidence_blocks"]:
                            trace["evidence_blocks"].append(blk.properties)

            elif edge.edge_type == EdgeType.RESULT_EVALUATES_FACT.value:
                trace["facts"].append(tgt_node.properties)
                # Fact evidence blocks and canonical field
                for f_e_id in self.adj.get(tgt_node.node_id, []):
                    f_edge = self.edges[f_e_id]
                    if f_edge.edge_type == EdgeType.FACT_GROUNDED_BY.value:
                        blk = self.nodes[f_edge.target_id]
                        if blk.properties not in trace["evidence_blocks"]:
                            trace["evidence_blocks"].append(blk.properties)
                    elif f_edge.edge_type == EdgeType.FACT_CANONICALIZED_AS.value:
                        cf_node = self.nodes[f_edge.target_id]
                        if cf_node.properties not in trace["canonical_fields"]:
                            trace["canonical_fields"].append(cf_node.properties)

            elif edge.edge_type == EdgeType.RESULT_SUPPORTED_BY.value:
                if tgt_node.properties not in trace["evidence_blocks"]:
                    trace["evidence_blocks"].append(tgt_node.properties)

            elif edge.edge_type == EdgeType.RESULT_AFFECTED_BY_INTEGRITY.value:
                trace["integrity_findings"].append(tgt_node.properties)

        # Inward edges to result (e.g. from Review Items)
        for e_id in self.rev_adj.get(node_id, []):
            edge = self.edges[e_id]
            src_node = self.nodes[edge.source_id]
            if edge.edge_type == EdgeType.REVIEW_ITEM_FOR_RESULT.value:
                trace["review_items"].append(src_node.properties)

        return trace

    def trace_evidence_to_decisions(self, block_id: str) -> Dict[str, Any]:
        """
        Evidence -> Decisions Traversal.
        Given a PhysicalTextBlock ID, traverses upward to find all facts, verification
        results, integrity findings, and human review items that depend on it.
        """
        target_node = None
        for n_id, n in self.nodes.items():
            if n.node_type == NodeType.PHYSICAL_TEXT_BLOCK.value:
                if n_id == block_id or n.properties.get("block_id") == block_id or block_id in n_id:
                    target_node = n
                    break

        if not target_node:
            raise KeyError(f"Evidence block '{block_id}' not found in provenance graph")

        trace: Dict[str, Any] = {
            "evidence_block": target_node.properties,
            "facts": [],
            "requirements": [],
            "verification_results": [],
            "integrity_findings": [],
            "review_items": [],
        }

        # Upward traversal from evidence block
        visited_nodes: Set[str] = set()

        def _traverse_up(curr_id: str):
            for e_id in self.rev_adj.get(curr_id, []):
                edge = self.edges[e_id]
                src = self.nodes[edge.source_id]
                if src.node_id in visited_nodes:
                    continue
                visited_nodes.add(src.node_id)

                if src.node_type == NodeType.BIDDER_FACT.value:
                    trace["facts"].append(src.properties)
                    _traverse_up(src.node_id)
                elif src.node_type == NodeType.TENDER_REQUIREMENT.value:
                    trace["requirements"].append(src.properties)
                    _traverse_up(src.node_id)
                elif src.node_type == NodeType.VERIFICATION_RESULT.value:
                    trace["verification_results"].append(src.properties)
                    _traverse_up(src.node_id)
                elif src.node_type == NodeType.INTEGRITY_FINDING.value:
                    trace["integrity_findings"].append(src.properties)
                    _traverse_up(src.node_id)
                elif src.node_type == NodeType.HUMAN_REVIEW_ITEM.value:
                    trace["review_items"].append(src.properties)

        _traverse_up(target_node.node_id)
        return trace

    def trace_fact(self, fact_id: str) -> Dict[str, Any]:
        """
        Fact -> Provenance Traversal.
        Retrieves all physical blocks grounding the fact, its canonical field, and evaluated results.
        """
        node_id = fact_id if fact_id.startswith("FACT:") else f"FACT:{fact_id}"
        if node_id not in self.nodes:
            raise KeyError(f"Fact node '{node_id}' not found in provenance graph")

        fact_node = self.nodes[node_id]
        trace: Dict[str, Any] = {
            "fact": fact_node.properties,
            "evidence_blocks": [],
            "canonical_field": None,
            "satisfied_requirements": [],
            "verification_results": [],
        }

        for e_id in self.adj.get(node_id, []):
            edge = self.edges[e_id]
            tgt = self.nodes[edge.target_id]
            if edge.edge_type == EdgeType.FACT_GROUNDED_BY.value:
                trace["evidence_blocks"].append(tgt.properties)
            elif edge.edge_type == EdgeType.FACT_CANONICALIZED_AS.value:
                trace["canonical_field"] = tgt.properties
            elif edge.edge_type == EdgeType.FACT_SATISFIES_REQUIREMENT.value:
                trace["satisfied_requirements"].append(tgt.properties)

        for e_id in self.rev_adj.get(node_id, []):
            edge = self.edges[e_id]
            src = self.nodes[edge.source_id]
            if edge.edge_type == EdgeType.RESULT_EVALUATES_FACT.value:
                trace["verification_results"].append(src.properties)

        return trace

    def trace_integrity(self, finding_id: str) -> Dict[str, Any]:
        """
        Integrity Finding -> Evidence Traversal.
        Retrieves all facts compared, physical blocks, canonical field, and review items.
        """
        node_id = finding_id if finding_id.startswith("INTEGRITY:") else f"INTEGRITY:{finding_id}"
        if node_id not in self.nodes:
            raise KeyError(f"Integrity finding node '{node_id}' not found in provenance graph")

        finding_node = self.nodes[node_id]
        trace: Dict[str, Any] = {
            "finding": finding_node.properties,
            "compared_facts": [],
            "evidence_blocks": [],
            "canonical_field": None,
            "review_items": [],
        }

        for e_id in self.adj.get(node_id, []):
            edge = self.edges[e_id]
            tgt = self.nodes[edge.target_id]
            if edge.edge_type == EdgeType.INTEGRITY_FINDING_COMPARES.value:
                trace["compared_facts"].append(tgt.properties)
            elif edge.edge_type == EdgeType.RESULT_SUPPORTED_BY.value:
                trace["evidence_blocks"].append(tgt.properties)
            elif edge.edge_type == EdgeType.FACT_CANONICALIZED_AS.value:
                trace["canonical_field"] = tgt.properties

        for e_id in self.rev_adj.get(node_id, []):
            edge = self.edges[e_id]
            src = self.nodes[edge.source_id]
            if edge.edge_type == EdgeType.REVIEW_ITEM_FOR_RESULT.value:
                trace["review_items"].append(src.properties)

        return trace

    # ==================== DETERMINISTIC SERIALIZATION ====================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes graph to a deterministic dictionary with sorted keys and lists.
        Eliminates memory addresses, random IDs, and timestamps.
        """
        node_counts: Dict[str, int] = {}
        for n in self.nodes.values():
            node_counts[n.node_type] = node_counts.get(n.node_type, 0) + 1

        # Sort nodes deterministically by node_id
        sorted_nodes = [
            self.nodes[k].to_dict()
            for k in sorted(self.nodes.keys())
        ]

        # Sort edges deterministically by edge_id
        sorted_edges = [
            self.edges[k].to_dict()
            for k in sorted(self.edges.keys())
        ]

        return {
            "graph_version": "1.0.0",
            "metadata": {
                "bid_id": self.bid_id,
                "tender_id": self.tender_id,
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "node_counts": {k: node_counts[k] for k in sorted(node_counts.keys())},
                "is_acyclic": True,
            },
            "nodes": sorted_nodes,
            "edges": sorted_edges,
        }

    def to_json(self, indent: int = 2) -> str:
        """Produces byte-for-byte deterministic JSON serialization."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


class ProvenanceDAGBuilder:
    """
    Constructs a valid ProvenanceDAG from core domain objects.
    Enforces exact preservation of multi-block evidence and canonical field ontology.
    """

    @classmethod
    def build(
        cls,
        requirements: List[TenderRequirement],
        facts: List[BidderFact],
        results: List[VerificationResult],
        integrity_findings: Optional[List[IntegrityFinding]] = None,
        human_review_items: Optional[List[Any]] = None,
        bid_id: Optional[str] = None,
        tender_id: Optional[str] = None,
        adjudications: Optional[List[Any]] = None,
    ) -> ProvenanceDAG:
        """
        Builds and validates a deterministic ProvenanceDAG.
        """
        integrity_findings = integrity_findings or []
        human_review_items = human_review_items or []

        b_id = bid_id or (facts[0].bid_id if facts else "UNKNOWN_BID")
        t_id = tender_id or (requirements[0].tender_id if requirements else "UNKNOWN_TENDER")

        dag = ProvenanceDAG(bid_id=b_id, tender_id=t_id)

        # 1. CANONICAL FIELDS
        # Only create canonical nodes for successfully resolved fields.
        # UNMAPPED and AMBIGUOUS fields MUST NOT receive invented nodes.
        created_canonical_nodes: Set[str] = set()

        def _ensure_canonical_node(cf_id: Optional[str]) -> Optional[str]:
            if not cf_id:
                return None
            norm_cid = cf_id.strip().upper()
            node_id = f"FIELD:{norm_cid}"
            if node_id not in dag.nodes:
                dag.add_node(ProvenanceNode(
                    node_id=node_id,
                    node_type=NodeType.CANONICAL_FIELD.value,
                    label=f"Canonical Field: {norm_cid}",
                    properties={
                        "canonical_field_id": norm_cid,
                    },
                ))
            created_canonical_nodes.add(node_id)
            return node_id

        # 2. PHYSICAL TEXT BLOCKS
        # Maps (doc, page, block_id/coords) to block node ID
        block_node_ids: Dict[str, str] = {}

        def _get_or_create_block_node(
            doc: str,
            page: int,
            block_id: Optional[str] = None,
            bbox: Optional[List[float]] = None,
            snippet: Optional[str] = None,
            source_type: str = "BIDDER_SUBMISSION",
            doc_id: Optional[str] = None,
        ) -> str:
            node_id = make_block_node_id(doc, page, block_id, bbox, snippet)
            if node_id not in dag.nodes:
                dag.add_node(ProvenanceNode(
                    node_id=node_id,
                    node_type=NodeType.PHYSICAL_TEXT_BLOCK.value,
                    label=f"Evidence: {doc} P.{page}" + (f" [{block_id}]" if block_id else ""),
                    properties={
                        "block_id": block_id or node_id.split(":")[-1],
                        "document": doc,
                        "document_id": doc_id or doc,
                        "page": page,
                        "bbox": bbox,
                        "snippet": snippet or "",
                        "source_type": source_type,
                    },
                ))
            return node_id

        def _to_ev_dict(ev: Any) -> Dict[str, Any]:
            if isinstance(ev, dict):
                return ev
            if hasattr(ev, "to_dict") and callable(ev.to_dict):
                return ev.to_dict()
            if hasattr(ev, "__dict__"):
                return ev.__dict__
            return {}

        # 3. TENDER REQUIREMENTS & THEIR EVIDENCE
        req_node_ids: Dict[str, str] = {}
        for req in requirements:
            r_node_id = f"REQ:{req.requirement_id}"
            req_node_ids[req.requirement_id] = r_node_id
            dag.add_node(ProvenanceNode(
                node_id=r_node_id,
                node_type=NodeType.TENDER_REQUIREMENT.value,
                label=f"Requirement: {req.requirement_id}",
                properties={
                    "requirement_id": req.requirement_id,
                    "tender_id": req.tender_id,
                    "category": req.category,
                    "description": req.description,
                    "operator": req.operator,
                    "expected_value": req.expected_value,
                    "mandatory": req.mandatory,
                    "field": req.field,
                    "canonical_field": req.canonical_field,
                },
            ))

            # Requirement physical evidence blocks
            if req.evidence:
                for idx, ev_raw in enumerate(req.evidence):
                    ev = _to_ev_dict(ev_raw)
                    p = ev.get("page", req.source_page or 1)
                    bb = ev.get("bbox")
                    snip = ev.get("snippet", req.description)
                    b_id = ev.get("block_id")
                    b_node_id = _get_or_create_block_node(
                        doc=ev.get("document", f"{req.tender_id}.pdf"),
                        page=p,
                        block_id=b_id,
                        bbox=bb,
                        snippet=snip,
                        source_type="TENDER_DOCUMENT",
                    )
                    edge_id = make_edge_id(r_node_id, EdgeType.REQUIREMENT_HAS_EVIDENCE.value, b_node_id, str(idx))
                    dag.add_edge(ProvenanceEdge(
                        edge_id=edge_id,
                        source_id=r_node_id,
                        edge_type=EdgeType.REQUIREMENT_HAS_EVIDENCE.value,
                        target_id=b_node_id,
                    ))

        # 4. BIDDER FACTS, MULTI-BLOCK EVIDENCE, & ONTOLOGY RESOLUTION
        fact_node_ids: Dict[str, str] = {}
        for f in facts:
            f_node_id = f"FACT:{f.fact_id}"
            fact_node_ids[f.fact_id] = f_node_id

            dag.add_node(ProvenanceNode(
                node_id=f_node_id,
                node_type=NodeType.BIDDER_FACT.value,
                label=f"Fact: {f.field} = {f.value}",
                properties={
                    "fact_id": f.fact_id,
                    "bid_id": f.bid_id,
                    "raw_field": f.field,
                    "canonical_field": f.canonical_field,
                    "value": f.value,
                    "normalized_value": f.normalized_value,
                    "unit": f.unit,
                    "source_document": f.source_document,
                    "page": f.page,
                    "bbox": f.bbox,
                    "extraction_confidence": f.extraction_confidence,
                    "extraction_method": f.extraction_method,
                    "field_resolution": f.field_resolution,
                },
            ))

            # Multi-Block Physical Evidence Preservation
            # Phase 10B.1 explicit rule: every block in f.evidence must be a distinct node!
            if getattr(f, "evidence", None) and len(f.evidence) > 0:
                for idx, ev_raw in enumerate(f.evidence):
                    ev = _to_ev_dict(ev_raw)
                    p = ev.get("page", f.page)
                    bb = ev.get("bbox")
                    snip = ev.get("snippet", f.raw_text_snippet or "")
                    b_id = ev.get("block_id")
                    doc = ev.get("document", f.source_document)
                    doc_id = ev.get("document_id")

                    b_node_id = _get_or_create_block_node(
                        doc=doc,
                        page=p,
                        block_id=b_id,
                        bbox=bb,
                        snippet=snip,
                        source_type=ev.get("source_type", "BIDDER_SUBMISSION"),
                        doc_id=doc_id,
                    )
                    edge_id = make_edge_id(f_node_id, EdgeType.FACT_GROUNDED_BY.value, b_node_id, f"BLK_{idx}")
                    dag.add_edge(ProvenanceEdge(
                        edge_id=edge_id,
                        source_id=f_node_id,
                        edge_type=EdgeType.FACT_GROUNDED_BY.value,
                        target_id=b_node_id,
                    ))
            else:
                # Legacy single-block fallback
                b_node_id = _get_or_create_block_node(
                    doc=f.source_document,
                    page=f.page,
                    block_id=None,
                    bbox=f.bbox,
                    snippet=f.raw_text_snippet or "",
                )
                edge_id = make_edge_id(f_node_id, EdgeType.FACT_GROUNDED_BY.value, b_node_id)
                dag.add_edge(ProvenanceEdge(
                    edge_id=edge_id,
                    source_id=f_node_id,
                    edge_type=EdgeType.FACT_GROUNDED_BY.value,
                    target_id=b_node_id,
                ))

            # Canonical field connection
            if f.canonical_field:
                cf_node_id = _ensure_canonical_node(f.canonical_field)
                if cf_node_id:
                    edge_id = make_edge_id(f_node_id, EdgeType.FACT_CANONICALIZED_AS.value, cf_node_id)
                    dag.add_edge(ProvenanceEdge(
                        edge_id=edge_id,
                        source_id=f_node_id,
                        edge_type=EdgeType.FACT_CANONICALIZED_AS.value,
                        target_id=cf_node_id,
                    ))

        # 5. VERIFICATION RESULTS (Step 4 Decisions)
        result_node_ids: Dict[str, str] = {}
        for res in results:
            res_node_id = f"RESULT:{res.verification_id}"
            result_node_ids[res.verification_id] = res_node_id

            dag.add_node(ProvenanceNode(
                node_id=res_node_id,
                node_type=NodeType.VERIFICATION_RESULT.value,
                label=f"Result: {res.requirement_id} -> {res.status}",
                properties={
                    "verification_id": res.verification_id,
                    "requirement_id": res.requirement_id,
                    "fact_id": res.fact_id,
                    "status": res.status,
                    "severity": res.severity,
                    "expected": res.expected,
                    "actual": res.actual,
                    "operator_used": res.operator_used,
                    "reason": res.reason,
                    "requires_human_review": res.requires_human_review,
                },
            ))

            # Link Result -> Requirement
            if res.requirement_id in req_node_ids:
                req_id = req_node_ids[res.requirement_id]
                edge_id = make_edge_id(res_node_id, EdgeType.RESULT_EVALUATES_REQUIREMENT.value, req_id)
                dag.add_edge(ProvenanceEdge(
                    edge_id=edge_id,
                    source_id=res_node_id,
                    edge_type=EdgeType.RESULT_EVALUATES_REQUIREMENT.value,
                    target_id=req_id,
                ))

            # Link Result -> Fact & Fact -> Requirement
            if res.fact_id and res.fact_id in fact_node_ids:
                f_id = fact_node_ids[res.fact_id]
                edge_id = make_edge_id(res_node_id, EdgeType.RESULT_EVALUATES_FACT.value, f_id)
                dag.add_edge(ProvenanceEdge(
                    edge_id=edge_id,
                    source_id=res_node_id,
                    edge_type=EdgeType.RESULT_EVALUATES_FACT.value,
                    target_id=f_id,
                ))

                if res.status in ["PASS", "PARTIAL"] and res.requirement_id in req_node_ids:
                    req_id = req_node_ids[res.requirement_id]
                    edge_id = make_edge_id(f_id, EdgeType.FACT_SATISFIES_REQUIREMENT.value, req_id)
                    dag.add_edge(ProvenanceEdge(
                        edge_id=edge_id,
                        source_id=f_id,
                        edge_type=EdgeType.FACT_SATISFIES_REQUIREMENT.value,
                        target_id=req_id,
                    ))

            # Link Result -> Physical Evidence Blocks
            if res.evidence:
                for idx, ev_raw in enumerate(res.evidence):
                    ev = _to_ev_dict(ev_raw)
                    p = ev.get("page", 1)
                    bb = ev.get("bbox")
                    snip = ev.get("snippet", "")
                    b_id = ev.get("block_id")
                    doc = ev.get("document", "UNKNOWN_DOC")
                    b_node_id = _get_or_create_block_node(
                        doc=doc,
                        page=p,
                        block_id=b_id,
                        bbox=bb,
                        snippet=snip,
                    )
                    edge_id = make_edge_id(res_node_id, EdgeType.RESULT_SUPPORTED_BY.value, b_node_id, f"RES_{idx}")
                    dag.add_edge(ProvenanceEdge(
                        edge_id=edge_id,
                        source_id=res_node_id,
                        edge_type=EdgeType.RESULT_SUPPORTED_BY.value,
                        target_id=b_node_id,
                    ))

        # 6. INTEGRITY FINDINGS (Step 5 Cross-Document Anomalies)
        finding_node_ids: Dict[str, str] = {}
        for inf in integrity_findings:
            inf_node_id = f"INTEGRITY:{inf.finding_id}"
            finding_node_ids[inf.finding_id] = inf_node_id

            dag.add_node(ProvenanceNode(
                node_id=inf_node_id,
                node_type=NodeType.INTEGRITY_FINDING.value,
                label=f"Integrity Finding: {inf.finding_type} ({inf.field})",
                properties={
                    "finding_id": inf.finding_id,
                    "finding_type": inf.finding_type,
                    "field": inf.field,
                    "raw_field_a": inf.raw_field_a,
                    "raw_field_b": inf.raw_field_b,
                    "canonical_field": inf.canonical_field,
                    "severity": inf.severity,
                    "status": inf.status,
                    "description": inf.description,
                    "value_a": inf.value_a,
                    "value_b": inf.value_b,
                },
            ))

            # Physical evidence A & B
            if inf.evidence_a:
                b_node_a = _get_or_create_block_node(
                    doc=inf.evidence_a.get("document", "DOC_A"),
                    page=inf.evidence_a.get("page", 1),
                    bbox=inf.evidence_a.get("bbox"),
                    snippet=inf.evidence_a.get("snippet", ""),
                )
                dag.add_edge(ProvenanceEdge(
                    edge_id=make_edge_id(inf_node_id, EdgeType.RESULT_SUPPORTED_BY.value, b_node_a, "SIDE_A"),
                    source_id=inf_node_id,
                    edge_type=EdgeType.RESULT_SUPPORTED_BY.value,
                    target_id=b_node_a,
                ))

            if inf.evidence_b:
                b_node_b = _get_or_create_block_node(
                    doc=inf.evidence_b.get("document", "DOC_B"),
                    page=inf.evidence_b.get("page", 1),
                    bbox=inf.evidence_b.get("bbox"),
                    snippet=inf.evidence_b.get("snippet", ""),
                )
                dag.add_edge(ProvenanceEdge(
                    edge_id=make_edge_id(inf_node_id, EdgeType.RESULT_SUPPORTED_BY.value, b_node_b, "SIDE_B"),
                    source_id=inf_node_id,
                    edge_type=EdgeType.RESULT_SUPPORTED_BY.value,
                    target_id=b_node_b,
                ))

            # Link finding to compared facts if field matches
            for f in facts:
                if (
                    (inf.canonical_field and f.canonical_field == inf.canonical_field)
                    or (f.field.lower() in [str(inf.raw_field_a or "").lower(), str(inf.raw_field_b or "").lower(), inf.field.lower()])
                ):
                    f_node_id = fact_node_ids[f.fact_id]
                    edge_id = make_edge_id(inf_node_id, EdgeType.INTEGRITY_FINDING_COMPARES.value, f_node_id)
                    dag.add_edge(ProvenanceEdge(
                        edge_id=edge_id,
                        source_id=inf_node_id,
                        edge_type=EdgeType.INTEGRITY_FINDING_COMPARES.value,
                        target_id=f_node_id,
                    ))

            # Link VerificationResults affected by this integrity finding
            for res in results:
                # If the result evaluated a fact or requirement in the same canonical domain
                rel_req = next((r for r in requirements if r.requirement_id == res.requirement_id), None)
                if rel_req and (
                    (inf.canonical_field and rel_req.canonical_field == inf.canonical_field)
                    or (rel_req.field and rel_req.field.lower() in [str(inf.raw_field_a or "").lower(), str(inf.raw_field_b or "").lower(), inf.field.lower()])
                ):
                    res_node_id = result_node_ids[res.verification_id]
                    edge_id = make_edge_id(res_node_id, EdgeType.RESULT_AFFECTED_BY_INTEGRITY.value, inf_node_id)
                    dag.add_edge(ProvenanceEdge(
                        edge_id=edge_id,
                        source_id=res_node_id,
                        edge_type=EdgeType.RESULT_AFFECTED_BY_INTEGRITY.value,
                        target_id=inf_node_id,
                    ))

        # 7. HUMAN REVIEW ITEMS
        for rev in human_review_items:
            # Can be HumanReviewItem object or dict
            r_id = rev.review_id if hasattr(rev, "review_id") else rev.get("review_id", "REV-UNKNOWN")
            r_cat = rev.category if hasattr(rev, "category") else rev.get("category", "MANUAL_INSPECTION")
            r_sev = rev.severity if hasattr(rev, "severity") else rev.get("severity", "MAJOR")
            r_reason = rev.reason if hasattr(rev, "reason") else rev.get("reason", "")
            r_rel_id = rev.related_verification_id if hasattr(rev, "related_verification_id") else rev.get("related_verification_id")
            r_ev_refs = rev.evidence_references if hasattr(rev, "evidence_references") else rev.get("evidence_references", [])

            rev_node_id = f"REVIEW:{r_id}"
            dag.add_node(ProvenanceNode(
                node_id=rev_node_id,
                node_type=NodeType.HUMAN_REVIEW_ITEM.value,
                label=f"Human Review: {r_cat} ({r_id})",
                properties={
                    "review_id": r_id,
                    "category": r_cat,
                    "severity": r_sev,
                    "reason": r_reason,
                    "related_verification_id": r_rel_id,
                },
            ))

            # Link review item to its related result or integrity finding
            if r_rel_id:
                if f"RESULT:{r_rel_id}" in dag.nodes:
                    tgt_id = f"RESULT:{r_rel_id}"
                    dag.add_edge(ProvenanceEdge(
                        edge_id=make_edge_id(rev_node_id, EdgeType.REVIEW_ITEM_FOR_RESULT.value, tgt_id),
                        source_id=rev_node_id,
                        edge_type=EdgeType.REVIEW_ITEM_FOR_RESULT.value,
                        target_id=tgt_id,
                    ))
                elif f"INTEGRITY:{r_rel_id}" in dag.nodes:
                    tgt_id = f"INTEGRITY:{r_rel_id}"
                    dag.add_edge(ProvenanceEdge(
                        edge_id=make_edge_id(rev_node_id, EdgeType.REVIEW_ITEM_FOR_RESULT.value, tgt_id),
                        source_id=rev_node_id,
                        edge_type=EdgeType.REVIEW_ITEM_FOR_RESULT.value,
                        target_id=tgt_id,
                    ))

            # Link review item to its physical evidence
            for idx, ev_ref in enumerate(r_ev_refs):
                if isinstance(ev_ref, dict) and (ev_ref.get("page") or ev_ref.get("bbox")):
                    b_node_id = _get_or_create_block_node(
                        doc=ev_ref.get("document", "UNKNOWN_DOC"),
                        page=ev_ref.get("page", 1),
                        block_id=ev_ref.get("block_id"),
                        bbox=ev_ref.get("bbox"),
                        snippet=ev_ref.get("snippet", ""),
                    )
                    dag.add_edge(ProvenanceEdge(
                        edge_id=make_edge_id(rev_node_id, EdgeType.REVIEW_ITEM_SUPPORTED_BY.value, b_node_id, str(idx)),
                        source_id=rev_node_id,
                        edge_type=EdgeType.REVIEW_ITEM_SUPPORTED_BY.value,
                        target_id=b_node_id,
                    ))

        # 8. OFFICER ADJUDICATIONS
        if adjudications:
            for adj in adjudications:
                adj_id = adj.get("adjudication_id") if isinstance(adj, dict) else adj.adjudication_id
                target_id = adj.get("target_id") if isinstance(adj, dict) else adj.target_id
                decision = adj.get("decision") if isinstance(adj, dict) else adj.decision
                officer_id = adj.get("officer_id") if isinstance(adj, dict) else adj.officer_id
                justification = adj.get("justification") if isinstance(adj, dict) else adj.justification
                timestamp = adj.get("applied_at") or adj.get("timestamp") if isinstance(adj, dict) else getattr(adj, "applied_at", "")

                adj_node_id = f"ADJUDICATION:{adj_id}"
                if adj_node_id not in dag.nodes:
                    dag.add_node(ProvenanceNode(
                        node_id=adj_node_id,
                        node_type=NodeType.OFFICER_ADJUDICATION.value,
                        label=f"Officer Adjudication: {decision} by {officer_id}",
                        properties={
                            "adjudication_id": adj_id,
                            "target_id": target_id,
                            "decision": decision,
                            "officer_id": officer_id,
                            "justification": justification,
                            "timestamp": timestamp,
                        },
                    ))

                # Link adjudication to review item if present
                target_rev_node = f"REVIEW:{target_id}"
                if target_rev_node in dag.nodes:
                    edge_id = make_edge_id(adj_node_id, EdgeType.ADJUDICATION_FOR_REVIEW_ITEM.value, target_rev_node)
                    dag.add_edge(ProvenanceEdge(
                        edge_id=edge_id,
                        source_id=adj_node_id,
                        edge_type=EdgeType.ADJUDICATION_FOR_REVIEW_ITEM.value,
                        target_id=target_rev_node,
                    ))

                # Link adjudication to verification result if present
                target_res_node = result_node_ids.get(target_id)
                if not target_res_node and f"RES:{target_id}" in dag.nodes:
                    target_res_node = f"RES:{target_id}"
                if target_res_node and target_res_node in dag.nodes:
                    edge_id = make_edge_id(adj_node_id, EdgeType.ADJUDICATION_OVERRIDES_RESULT.value, target_res_node)
                    dag.add_edge(ProvenanceEdge(
                        edge_id=edge_id,
                        source_id=adj_node_id,
                        edge_type=EdgeType.ADJUDICATION_OVERRIDES_RESULT.value,
                        target_id=target_res_node,
                    ))

        # Enforce graph invariants
        dag.validate()
        return dag

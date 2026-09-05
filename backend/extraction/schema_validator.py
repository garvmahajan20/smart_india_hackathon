# -*- coding: utf-8 -*-
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import jsonschema

class SchemaValidator:
    """
    Validates candidate extractions against canonical JSON schemas.
    """

    def __init__(
        self,
        req_schema_path: str = "contracts/requirement.schema.json",
        fact_schema_path: str = "contracts/bidder_fact.schema.json"
    ):
        self.req_schema = self._load_schema(req_schema_path)
        self.fact_schema = self._load_schema(fact_schema_path)

        self.req_validator = jsonschema.Draft202012Validator(self.req_schema) if self.req_schema else None
        self.fact_validator = jsonschema.Draft202012Validator(self.fact_schema) if self.fact_schema else None

    def _load_schema(self, path: str) -> Optional[Dict[str, Any]]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def validate_requirement(self, requirement_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates requirement dictionary against contracts/requirement.schema.json.
        """
        if not self.req_validator:
            return True, []

        errors = []
        for err in self.req_validator.iter_errors(requirement_dict):
            path_str = ".".join(str(p) for p in err.path) if err.path else "root"
            errors.append(f"[{path_str}] {err.message}")

        return (len(errors) == 0), errors

    def validate_fact(self, fact_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates bidder fact dictionary against contracts/bidder_fact.schema.json.
        """
        if not self.fact_validator:
            return True, []

        errors = []
        for err in self.fact_validator.iter_errors(fact_dict):
            path_str = ".".join(str(p) for p in err.path) if err.path else "root"
            errors.append(f"[{path_str}] {err.message}")

        return (len(errors) == 0), errors

# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .models import AdapterResponse, VerificationStatus

class BaseGovernmentAdapter(ABC):
    """
    Abstract Base Class for Government Verification Adapters.
    Encapsulates registry queries behind a uniform interface.
    Designed to be swap-in ready: replacing a mock adapter with a real
    government API client requires zero modification to calling services.
    """

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    @abstractmethod
    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any
    ) -> AdapterResponse:
        """
        Queries the verification source for the given identifier.

        Args:
            identifier: The unique entity key (GSTIN, PAN, Udyam Registration number, etc.)
            expected_entity_name: Optional bidder company name to cross-check identity matching.
            timestamp: Optional caller-supplied timestamp. Never uses system clock.
            **kwargs: Adapter-specific parameters.

        Returns:
            AdapterResponse adhering to the canonical verification contract.
        """
        pass

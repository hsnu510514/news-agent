from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Sequence
import httpx
from sqlalchemy.ext.asyncio import AsyncSession


class IngestionSourceType(str, Enum):
    """Supported ingestion channels in the system."""
    RSS = "rss"
    NEWSAPI = "newsapi"
    COLLECTOR = "collector"
    EARNINGS = "earnings"
    MACRO = "macro"


@dataclass(frozen=True)
class IngestionSummary:
    """Represents the results of a single source ingestion run."""
    source_type: IngestionSourceType
    fetched_count: int
    saved_count: int
    duration_seconds: float
    error_message: Optional[str] = None


class BaseIngestAdapter:
    """Base class for all ingestion source adapters.
    
    Adapters handle network requests, parsing, and SQLAlchemy model instantiation.
    They do not manage database transaction commits or task execution progress logs.
    """

    async def fetch(self, client: httpx.AsyncClient, session: AsyncSession) -> Sequence[Any]:
        """Fetches raw data and instantiates unsaved database model records."""
        raise NotImplementedError

    async def filter_duplicates(self, items: Sequence[Any], session: AsyncSession) -> Sequence[Any]:
        """Queries the database to filter out items that already exist."""
        raise NotImplementedError

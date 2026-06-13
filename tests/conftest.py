import pytest
from unittest.mock import AsyncMock, MagicMock

# Import modules to patch
import src.storage.database as db_module
import src.storage.vectorstore as vs_module
import src.scheduler.jobs as jobs_module
from src.core.config import settings

# Patch database startup/shutdown to avoid connecting to real databases
db_module.init_db = AsyncMock()
db_module.close_db = AsyncMock()

# Patch vectorstore startup to avoid connecting to real Qdrant server
vs_module.ensure_collection = MagicMock()

# Patch scheduler startup/shutdown to avoid running background fetchers
jobs_module.start_scheduler = AsyncMock()
jobs_module.stop_scheduler = MagicMock()

@pytest.fixture(autouse=True, scope="session")
def disable_scheduler_for_tests():
    """Disable background scheduler globally during test runs to prevent background ingestion jobs from executing."""
    settings.SCHEDULER_ENABLED = False

@pytest.fixture(autouse=True)
async def cleanup_llm_queue():
    """Ensure that the LLM queue worker is stopped after every test to prevent dangling tasks on the event loop."""
    yield
    from src.core.llm import llm_queue
    await llm_queue.stop()

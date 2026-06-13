import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.main import app
from src.storage.database import get_session
from src.models.schema import Subject, SubjectTypeEnum, PotentialDuplicate

@pytest.fixture
def client_and_session():
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, mock_session
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_scan_for_duplicates_creates_records() -> None:
    # Arrange: two subjects that are similar
    subj1 = Subject(id="subj-1", name="Focuslight Technologies", type=SubjectTypeEnum.TICKER)
    subj2 = Subject(id="subj-2", name="Focuslight Tech", type=SubjectTypeEnum.TICKER)
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    
    # Mock return list of subjects and empty list of insights
    import os
    os.environ["SUBJECT_SIMILARITY_THRESHOLD"] = "0.60"

    async def mock_execute_scan(stmt):

        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "potential_duplicates" in stmt_str:
            res.all.return_value = []
        elif "subjects" in stmt_str:
            res.scalars.return_value.all.return_value = [subj1, subj2]
        elif "insights" in stmt_str:
            res.scalars.return_value.all.return_value = []
        return res
        
    mock_session.execute = AsyncMock(side_effect=mock_execute_scan)
    
    # Act
    from src.analysis.divergence import scan_for_duplicates
    stats = await scan_for_duplicates(mock_session)
    
    # Assert
    assert stats["subjects_scanned"] == 2
    assert stats["subjects_duplicates_found"] == 1
    
    # Verify a new PotentialDuplicate is added to the session
    added_objs = [call.args[0] for call in mock_session.add.call_args_list]
    assert len(added_objs) == 1
    duplicate_record = added_objs[0]
    assert isinstance(duplicate_record, PotentialDuplicate)
    assert duplicate_record.entity_type == "subject"
    assert duplicate_record.id1 == "subj-1"
    assert duplicate_record.id2 == "subj-2"
    assert duplicate_record.status == "pending"

def test_api_divergence_returns_cached_results(client_and_session) -> None:
    client, mock_session = client_and_session
    
    # Arrange: mock PotentialDuplicate records in db
    mock_dup = PotentialDuplicate(
        id="dup-1",
        entity_type="subject",
        id1="subj-1",
        id2="subj-2",
        similarity=0.83,
        status="pending"
    )
    # Mock the joins for subjects
    subj1 = Subject(id="subj-1", name="Focuslight Technologies", type=SubjectTypeEnum.TICKER)
    subj2 = Subject(id="subj-2", name="Focuslight Tech", type=SubjectTypeEnum.TICKER)
    
    mock_row = (mock_dup, subj1, subj2)
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "potential_duplicates" in stmt_str:
            if "insight" in stmt_str:
                res.all.return_value = []
            else:
                res.all.return_value = [mock_row]
        else:
            res.all.return_value = []
            res.scalars.return_value.all.return_value = []
        return res
        
    mock_session.execute = AsyncMock(side_effect=mock_execute)

    
    # Act
    response = client.get("/api/insights/divergence")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "subjects" in data
    assert len(data["subjects"]) == 1
    assert data["subjects"][0]["name1"] == "Focuslight Technologies"
    assert data["subjects"][0]["name2"] == "Focuslight Tech"
    assert data["subjects"][0]["similarity"] == 0.83


def test_resolve_ignore_endpoint(client_and_session) -> None:
    client, mock_session = client_and_session
    
    mock_dup = PotentialDuplicate(
        id="dup-123",
        entity_type="subject",
        id1="subj-1",
        id2="subj-2",
        similarity=0.83,
        status="pending"
    )
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = mock_dup
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    
    payload = {
        "entity_type": "subject",
        "id1": "subj-1",
        "id2": "subj-2",
        "action": "ignore"
    }
    response = client.post("/api/insights/divergence/resolve", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["action"] == "ignored"
    assert mock_dup.status == "ignored"
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_resolve_merge_subject_success() -> None:
    # Arrange
    subj_prim = Subject(id="subj-prim", name="Focuslight Technologies", type=SubjectTypeEnum.TICKER, tags=["A"])
    subj_sec = Subject(id="subj-sec", name="Focuslight Tech", type=SubjectTypeEnum.TICKER, tags=["B"])
    
    mock_dup = PotentialDuplicate(
        id="dup-456",
        entity_type="subject",
        id1="subj-prim",
        id2="subj-sec",
        similarity=0.83,
        status="pending"
    )
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = mock_dup
    mock_session.execute.return_value = mock_execute_result
    
    async def mock_get(model, pk):
        if pk == "subj-prim":
            return subj_prim
        elif pk == "subj-sec":
            return subj_sec
        return None
    mock_session.get = AsyncMock(side_effect=mock_get)
    
    # Act
    from src.api.routes.insights import DivergenceResolveRequest, resolve_divergence
    req = DivergenceResolveRequest(
        entity_type="subject",
        id1="subj-prim",
        id2="subj-sec",
        action="merge",
        primary_id="subj-prim"
    )
    res = await resolve_divergence(req, mock_session)
    
    # Assert
    assert res["status"] == "resolved"
    assert res["action"] == "merged"
    assert mock_dup.status == "merged"
    mock_session.delete.assert_called_once_with(subj_sec)
    assert "A" in subj_prim.tags
    assert "B" in subj_prim.tags
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_setup_jobs_seeds_missing_job() -> None:
    from src.models.schema import JobConfig
    existing_job = JobConfig(id="rss_news", name="RSS News Fetch", enabled=True, trigger_type="interval", schedule_value="30")
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [existing_job]
    mock_session.execute.return_value = mock_execute_result
    
    # Context manager mock: async with mock_session
    mock_context = MagicMock()
    mock_context.__aenter__.return_value = mock_session
    
    with patch("src.scheduler.jobs.async_session_factory", return_value=mock_context):
        with patch("src.scheduler.jobs._create_trigger"):
            with patch("src.scheduler.jobs.scheduler.add_job"):
                from src.scheduler.jobs import setup_jobs
                await setup_jobs()
                
                # Check that divergence is added to the session
                added_ids = [call.args[0].id for call in mock_session.add.call_args_list if isinstance(call.args[0], JobConfig)]
                assert "divergence" in added_ids
                assert mock_session.commit.called




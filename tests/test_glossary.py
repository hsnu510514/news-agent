import pytest
from unittest.mock import AsyncMock, MagicMock
from src.analysis.translation import get_glossary_prompt_extension, register_detected_entities
from src.models.schema import EntityGlossary
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_get_glossary_prompt_extension() -> None:
    # Arrange
    term1 = EntityGlossary(term_en="Fed", term_zh="美联储", type="institution", is_verified=True)
    term2 = EntityGlossary(term_en="Nvidia", term_zh="英伟达", type="company", is_verified=True)

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [term1, term2]
    mock_session.execute.return_value = mock_execute_result

    # Act
    text = "The fed is meeting today to discuss Nvidia Blackwell delays."
    extension = await get_glossary_prompt_extension(text, mock_session)

    # Assert
    assert "Fed <-> 美联储" in extension
    assert "Nvidia <-> 英伟达" in extension

    empty_text = "Some random text about something else."
    empty_extension = await get_glossary_prompt_extension(empty_text, mock_session)
    assert empty_extension == ""


@pytest.mark.asyncio
async def test_register_detected_entities() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none = MagicMock(side_effect=[None, EntityGlossary(term_en="Fed", term_zh="Fed")])
    mock_session.execute.return_value = mock_execute_result

    # Act
    entities = {
        "companies": ["NVDA"],
        "institutions": ["Fed"],
        "themes": []
    }
    await register_detected_entities(entities, mock_session)

    # Assert
    added_objs = [call.args[0] for call in mock_session.add.call_args_list]
    assert len(added_objs) == 1
    new_term = added_objs[0]
    assert isinstance(new_term, EntityGlossary)
    assert new_term.term_en == "NVDA"
    assert new_term.term_zh == "NVDA"
    assert new_term.type == "company"
    assert new_term.is_verified is False
    mock_session.flush.assert_called_once()


from fastapi.testclient import TestClient
from src.api.main import app
from src.storage.database import get_session

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


def test_get_glossary(client_and_session) -> None:
    client, mock_session = client_and_session
    
    term1 = EntityGlossary(id="1", term_en="Fed", term_zh="美联储", type="institution", is_verified=True)
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [term1]
    mock_session.execute.return_value = mock_execute_result

    response = client.get("/api/glossary")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["term_en"] == "Fed"


def test_create_glossary_item_new(client_and_session) -> None:
    client, mock_session = client_and_session
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_execute_result

    payload = {
        "term_en": "Nvidia",
        "term_zh": "英伟达",
        "type": "company",
        "is_verified": True
    }
    response = client.post("/api/glossary", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "created"
    assert mock_session.add.called
    assert mock_session.commit.called


def test_update_glossary_item_by_id(client_and_session) -> None:
    client, mock_session = client_and_session
    
    existing_item = EntityGlossary(id="item-123", term_en="Fed", term_zh="美联储", type="institution", is_verified=False)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = existing_item
    mock_session.execute.return_value = mock_execute_result

    payload = {
        "term_en": "Federal Reserve",
        "term_zh": "美联储",
        "type": "institution",
        "is_verified": True
    }
    response = client.put("/api/glossary/item-123", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"
    assert existing_item.term_en == "Federal Reserve"
    assert existing_item.is_verified is True
    assert mock_session.commit.called


def test_verify_glossary_item(client_and_session) -> None:
    client, mock_session = client_and_session
    
    existing_item = EntityGlossary(id="item-456", term_en="Fed", term_zh="美联储", type="institution", is_verified=False)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = existing_item
    mock_session.execute.return_value = mock_execute_result

    response = client.post("/api/glossary/item-456/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "verified"
    assert existing_item.is_verified is True
    assert mock_session.commit.called

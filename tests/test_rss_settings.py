import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.api.main import app
from src.core.config import settings

def test_rss_settings_persistence(tmp_path):
    import src.core.config as config_module
    
    test_config_file = str(tmp_path / "test_model_config.json")
    orig_path = getattr(config_module, "CONFIG_FILE_PATH", None)
    config_module.CONFIG_FILE_PATH = test_config_file

    try:
        client = TestClient(app)

        # 1. Get initial settings
        response = client.get("/api/system/models")
        assert response.status_code == 200
        data = response.json()
        assert "CUSTOM_RSS_FEEDS" in data["allocations"]
        assert data["allocations"]["CUSTOM_RSS_FEEDS"] == "[]"

        # 2. Put updated settings with a custom feed
        payload = data["allocations"].copy()
        custom_feed_json = '[{"name": "Ars Technica", "url": "https://feeds.arstechnica.com", "category": "tech_business", "language": "en"}]'
        payload["CUSTOM_RSS_FEEDS"] = custom_feed_json

        # We must patch the save_model_settings since we are testing end-to-end routing/serialization
        response = client.put("/api/system/models", json=payload)
        assert response.status_code == 200
        
        # 3. Verify it is persisted in the response and config
        response = client.get("/api/system/models")
        assert response.status_code == 200
        updated_data = response.json()
        assert updated_data["allocations"]["CUSTOM_RSS_FEEDS"] == custom_feed_json
    finally:
        if orig_path is not None:
            config_module.CONFIG_FILE_PATH = orig_path


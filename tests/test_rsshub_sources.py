from unittest.mock import patch

from src.ingest.sources import get_rss_feeds, rsshub_url


def test_rsshub_url_default_base():
    with patch("src.ingest.sources.settings") as mock_settings:
        mock_settings.RSSHUB_BASE_URL = "https://rsshub.app"
        mock_settings.RSSHUB_ACCESS_KEY = ""
        assert rsshub_url("caixin/latest") == "https://rsshub.app/caixin/latest"


def test_rsshub_url_custom_base():
    with patch("src.ingest.sources.settings") as mock_settings:
        mock_settings.RSSHUB_BASE_URL = "http://localhost:12000"
        mock_settings.RSSHUB_ACCESS_KEY = ""
        assert rsshub_url("/caixin/latest") == "http://localhost:12000/caixin/latest"


def test_rsshub_url_with_access_key():
    with patch("src.ingest.sources.settings") as mock_settings:
        mock_settings.RSSHUB_BASE_URL = "https://rsshub.example.com"
        mock_settings.RSSHUB_ACCESS_KEY = "secret123"
        assert rsshub_url("caixin/latest") == "https://rsshub.example.com/caixin/latest?key=secret123"


def test_caixin_feed_uses_rsshub_url():
    with patch("src.ingest.sources.settings") as mock_settings:
        mock_settings.RSSHUB_BASE_URL = "http://127.0.0.1:12000"
        mock_settings.RSSHUB_ACCESS_KEY = ""
        feeds = get_rss_feeds()
        caixin = next(f for f in feeds["zh"] if f["name"] == "财新网")
        assert caixin["url"] == "http://127.0.0.1:12000/caixin/latest"

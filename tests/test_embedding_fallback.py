import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.llm import get_embedding, llm_queue
from src.core.config import settings

@pytest.mark.asyncio
async def test_get_embedding_primary_success() -> None:
    # Set up models in settings
    with (
        patch.object(settings, "LLM_EMBED_MODEL", "gemini/gemini-embedding-2"),
        patch.object(settings, "LLM_EMBED_FALLBACK_MODEL", "gemini/gemini-embedding-001"),
        patch("src.core.llm.aembedding", new_callable=AsyncMock) as mock_aembedding
    ):
        mock_aembedding.return_value.data = [{"embedding": [0.1] * 768}]
        
        llm_queue.start()
        try:
            vector = await get_embedding("Hello test")
            assert vector == [0.1] * 768
            mock_aembedding.assert_called_once_with(
                model="gemini/gemini-embedding-2",
                input=["Hello test"],
                dimensions=768,
            )
        finally:
            await llm_queue.stop()

@pytest.mark.asyncio
async def test_get_embedding_fallback_success() -> None:
    # Set up models in settings
    with (
        patch.object(settings, "LLM_EMBED_MODEL", "gemini/gemini-embedding-2"),
        patch.object(settings, "LLM_EMBED_FALLBACK_MODEL", "gemini/gemini-embedding-001"),
        patch("src.core.llm.aembedding", new_callable=AsyncMock) as mock_aembedding
    ):
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.2] * 768}]
        
        # Use a function side_effect to handle retries without exhausting list iterators
        def side_effect(*args, **kwargs):
            model = kwargs.get("model")
            if model == "gemini/gemini-embedding-2":
                raise Exception("Rate limit on primary")
            return mock_response
            
        mock_aembedding.side_effect = side_effect
        
        llm_queue.start()
        try:
            vector = await get_embedding("Hello test")
            assert vector == [0.2] * 768
            assert mock_aembedding.call_count >= 2
        finally:
            await llm_queue.stop()

@pytest.mark.asyncio
async def test_get_embedding_both_fail() -> None:
    # Set up models in settings
    with (
        patch.object(settings, "LLM_EMBED_MODEL", "gemini/gemini-embedding-2"),
        patch.object(settings, "LLM_EMBED_FALLBACK_MODEL", "gemini/gemini-embedding-001"),
        patch("src.core.llm.aembedding", new_callable=AsyncMock) as mock_aembedding
    ):
        # Both calls raise exceptions, function handles arbitrary retry attempts
        def side_effect(*args, **kwargs):
            model = kwargs.get("model")
            if model == "gemini/gemini-embedding-2":
                raise Exception("Rate limit on primary")
            raise Exception("Rate limit on fallback")
            
        mock_aembedding.side_effect = side_effect
        
        llm_queue.start()
        try:
            with pytest.raises(Exception, match="Rate limit on fallback"):
                await get_embedding("Hello test")
            assert mock_aembedding.call_count >= 2
        finally:
            await llm_queue.stop()

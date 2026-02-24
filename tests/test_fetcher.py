from unittest.mock import AsyncMock, patch

import pytest

from src.fetcher import fetch_schedule_html


@pytest.mark.asyncio
async def test_fetch_schedule_html():
    mock_response = AsyncMock()
    mock_response.text = "<html>schedule</html>"
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None

    with patch("src.fetcher.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        html = await fetch_schedule_html("19624")
        assert html == "<html>schedule</html>"
        mock_client.get.assert_called_once()

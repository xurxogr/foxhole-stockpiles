"""Tests for the backend connector module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import ConnectTimeout

from foxhole_stockpiles.connectors.backend import BackendConnector


@pytest.fixture()
def connector():
    """Create a BackendConnector instance."""
    return BackendConnector(url="http://example.com")


@pytest.fixture()
def empty_connector():
    """Create an empty BackendConnector instance."""
    return BackendConnector()


@pytest.mark.asyncio
async def test_send_stockpile_empty_payload(connector):
    """Test sending an empty payload to the backend server."""
    response = await connector.send_stockpile(payload={}, api_key="test_api_key")
    assert response == {"message": "FS: Stockpile is Empty"}


@pytest.mark.asyncio
async def test_send_stockpile_no_api_key(connector):
    """Test sending a stockpile without an API key."""
    response = await connector.send_stockpile(payload={"data": "test"}, api_key="")
    assert response == {"message": "FS: API key not set"}


@pytest.mark.asyncio
async def test_send_stockpile_no_url(empty_connector):
    """Test sending a stockpile without a URL."""
    response = await empty_connector.send_stockpile(
        payload={"data": "test"}, api_key="test_api_key"
    )
    assert response == {"message": "FS: URL is not set"}


@pytest.mark.asyncio
@patch("foxhole_stockpiles.connectors.backend.AsyncClient.post", new_callable=AsyncMock)
async def test_send_stockpile_success(mock_post, connector):
    """Test sending a stockpile successfully."""
    mock_post.return_value = AsyncMock(
        status_code=200, json=Mock(return_value={"message": "Success"})
    )
    response = await connector.send_stockpile(payload={"data": "test"}, api_key="test_api_key")
    assert response == "Success"


@pytest.mark.asyncio
@patch("foxhole_stockpiles.connectors.backend.AsyncClient.post", new_callable=AsyncMock)
async def test_send_stockpile_error_response(mock_post, connector):
    """Test sending a stockpile with an error response."""
    mock_post.return_value = AsyncMock(
        status_code=400, json=Mock(return_value={"message": "Error occurred"})
    )
    response = await connector.send_stockpile(payload={"data": "test"}, api_key="test_api_key")
    assert response == "Error occurred"


@pytest.mark.asyncio
@patch("foxhole_stockpiles.connectors.backend.AsyncClient.post", new_callable=AsyncMock)
async def test_send_stockpile_http_error(mock_post, connector):
    """Test sending a stockpile with an HTTP error."""
    mock_post.return_value = AsyncMock(
        status_code=500, json=Mock(side_effect=Exception("JSON decode error"))
    )
    response = await connector.send_stockpile(payload={"data": "test"}, api_key="test_api_key")
    assert response == {"message": "HTTP code 500 sending the information to the backend server"}


@pytest.mark.asyncio
@patch("foxhole_stockpiles.connectors.backend.AsyncClient.post", new_callable=AsyncMock)
async def test_send_stockpile_connect_timeout(mock_post, connector):
    """Test sending a stockpile with a connection timeout.

    The connection timeout should be retried 3 times before raising the exception.
    due to the decorator async_retry_on_connect_timeout
    """
    mock_post.side_effect = ConnectTimeout("Connection timed out")

    # Now test that the exception is raised
    with pytest.raises(ConnectTimeout):
        await connector.send_stockpile(payload={"data": "test"}, api_key="test_api_key")

    assert mock_post.call_count == 3


@pytest.mark.asyncio
@patch("foxhole_stockpiles.connectors.backend.AsyncClient.post", new_callable=AsyncMock)
async def test_send_stockpile_general_exception(mock_post):
    """Test sending a stockpile with a general exception."""
    mock_post.side_effect = Exception("General error")

    connector = BackendConnector(url="http://example.com")
    response = await connector.send_stockpile(payload={"data": "test"}, api_key="test_api_key")
    assert response == {
        "message": "FS: Error sending stockpile to the backend server: (Exception, General error)"
    }

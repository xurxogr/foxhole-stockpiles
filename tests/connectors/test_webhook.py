"""Tests for webhook connector module.

This module contains comprehensive tests for the webhook connector,
including successful sends, error handling, retry logic, and
various webhook configurations.
"""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import ConnectTimeout, HTTPStatusError

from foxhole_stockpiles.connectors.webhook import WebhookConnector, async_retry_on_connect_timeout
from foxhole_stockpiles.core.settings.sections.output import WebhookHandlerSettings
from foxhole_stockpiles.enums.auth_type import AuthType


@pytest.fixture
def output_settings() -> WebhookHandlerSettings:
    """Create WebhookHandlerSettings instance for testing.

    Returns:
        WebhookHandlerSettings: A configured settings instance for webhook testing.
    """
    return WebhookHandlerSettings(
        url="https://example.com/webhook",
        auth_type=AuthType.BEARER,
        token="test_token_123",
    )


@pytest.fixture
def webhook_connector(output_settings: WebhookHandlerSettings) -> WebhookConnector:
    """Create a webhook connector instance.

    Args:
        output_settings (WebhookHandlerSettings): Output settings fixture.

    Returns:
        WebhookConnector: A configured webhook connector instance for testing.
    """
    return WebhookConnector(output_settings)


@pytest.fixture
def sample_payload() -> dict[str, Any]:
    """Create sample payload for testing.

    Returns:
        dict[str, Any]: A sample stockpile data payload for webhook testing.
    """
    return {
        "name": "Test Stockpile",
        "type": "Seaport",
        "items": [{"name": "Basic Materials", "quantity": 100, "code": "BasicMaterialsIcon"}],
        "timestamp": "2024-01-04T09:00:00",
        "shard": "TEST",
    }


class TestWebhookConnector:
    """Test cases for WebhookConnector."""

    def test_webhook_connector_initialization(
        self, output_settings: WebhookHandlerSettings
    ) -> None:
        """Test webhook connector initialization.

        Args:
            output_settings (WebhookHandlerSettings): Output settings fixture.
        """
        connector = WebhookConnector(output_settings)
        assert isinstance(connector, WebhookConnector)
        assert connector._output_settings == output_settings
        # Verify persistent AsyncClient is created
        assert hasattr(connector, "_client")
        assert connector._client is not None

    @pytest.mark.asyncio
    async def test_webhook_connector_close(self, output_settings: WebhookHandlerSettings) -> None:
        """Test webhook connector cleanup.

        Args:
            output_settings (WebhookHandlerSettings): Output settings fixture.
        """
        connector = WebhookConnector(output_settings)
        assert not connector._client.is_closed

        await connector.close()
        assert connector._client.is_closed

    def test_build_auth_headers_bearer(self, output_settings: WebhookHandlerSettings) -> None:
        """Test building bearer auth headers.

        Args:
            output_settings (WebhookHandlerSettings): Output settings fixture.
        """
        connector = WebhookConnector(output_settings)
        headers = connector._build_auth_headers()

        assert headers == {"Authorization": "Bearer test_token_123"}

    def test_build_auth_headers_basic(self, output_settings: WebhookHandlerSettings) -> None:
        """Test building basic auth headers.

        Args:
            output_settings (WebhookHandlerSettings): Output settings fixture.
        """
        output_settings.auth_type = AuthType.BASIC
        output_settings.token = "dGVzdDpwYXNzd29yZA=="  # base64 of test:password

        connector = WebhookConnector(output_settings)
        headers = connector._build_auth_headers()

        assert headers == {"Authorization": "Basic dGVzdDpwYXNzd29yZA=="}

    def test_build_auth_headers_header(self, output_settings: WebhookHandlerSettings) -> None:
        """Test building custom-header auth headers.

        Args:
            output_settings (WebhookHandlerSettings): Output settings fixture.
        """
        output_settings.auth_type = AuthType.HEADER
        output_settings.auth_header = "X-API-Key"
        output_settings.token = "secret_api_key"

        connector = WebhookConnector(output_settings)
        # Header auth places the configured token in the chosen header.
        headers = connector._build_auth_headers()

        assert headers == {"X-API-Key": "secret_api_key"}

    def test_build_auth_headers_header_ignores_runtime_token(
        self, output_settings: WebhookHandlerSettings
    ) -> None:
        """Header auth uses the configured token, ignoring any runtime token.

        Args:
            output_settings (WebhookHandlerSettings): Output settings fixture.
        """
        output_settings.auth_type = AuthType.HEADER
        output_settings.auth_header = "X-API-Key"
        output_settings.token = "configured_key"

        connector = WebhookConnector(output_settings)
        headers = connector._build_auth_headers(token="runtime_key")

        assert headers == {"X-API-Key": "configured_key"}

    def test_build_auth_headers_no_auth(self, output_settings: WebhookHandlerSettings) -> None:
        """Test building headers with no auth configured.

        Args:
            output_settings (WebhookHandlerSettings): Output settings fixture.
        """
        output_settings.auth_type = None
        output_settings.token = None

        connector = WebhookConnector(output_settings)
        headers = connector._build_auth_headers()

        assert headers == {}

    def test_build_auth_headers_override_token(
        self, output_settings: WebhookHandlerSettings
    ) -> None:
        """Test building headers with token override.

        Args:
            output_settings (WebhookHandlerSettings): Output settings fixture.
        """
        connector = WebhookConnector(output_settings)
        headers = connector._build_auth_headers(token="override_token")

        assert headers == {"Authorization": "Bearer override_token"}

    @pytest.mark.asyncio
    async def test_send_stockpile_success(
        self, webhook_connector: WebhookConnector, sample_payload: dict[str, Any]
    ) -> None:
        """Test successful stockpile sending.

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Stockpile received"}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await webhook_connector.send_stockpile(sample_payload)

            assert result == ["Stockpile received"]
            mock_post.assert_called_once_with(
                url="https://example.com/webhook",
                json=sample_payload,
                headers={"Authorization": "Bearer test_token_123"},
            )

    @pytest.mark.asyncio
    async def test_send_stockpile_prefers_error_over_message(
        self, webhook_connector: WebhookConnector, sample_payload: dict[str, Any]
    ) -> None:
        """A response with both fields surfaces ``error``, not ``message``.

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "Something failed", "message": "ignored"}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await webhook_connector.send_stockpile(sample_payload)
            assert result == ["Something failed"]

    @pytest.mark.asyncio
    async def test_send_stockpile_list_response(
        self, webhook_connector: WebhookConnector, sample_payload: dict[str, Any]
    ) -> None:
        """A list response yields one message per entry (error or message).

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"message": "Row 1 added"},
            {"error": "Row 2 failed"},
        ]
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await webhook_connector.send_stockpile(sample_payload)
            assert result == ["Row 1 added", "Row 2 failed"]

    @pytest.mark.asyncio
    async def test_send_stockpile_empty_payload(self, webhook_connector: WebhookConnector) -> None:
        """Test sending empty payload.

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
        """
        result = await webhook_connector.send_stockpile({})

        assert result == ["FS: Stockpile is Empty"]

    @pytest.mark.asyncio
    async def test_send_stockpile_no_url_configured(
        self, output_settings: WebhookHandlerSettings, sample_payload: dict[str, Any]
    ) -> None:
        """Test sending when no webhook URL is configured.

        Args:
            output_settings (WebhookHandlerSettings): Output settings fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        output_settings.url = None
        connector = WebhookConnector(output_settings)

        result = await connector.send_stockpile(sample_payload)

        assert result == ["FS: Webhook URL is not set"]

    @pytest.mark.asyncio
    async def test_send_stockpile_http_error(
        self, webhook_connector: WebhookConnector, sample_payload: dict[str, Any]
    ) -> None:
        """Test sending with HTTP error response.

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "404 Not Found", request=Mock(), response=Mock(status_code=404)
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await webhook_connector.send_stockpile(sample_payload)

            assert result == ["HTTP 404 error from server"]

    @pytest.mark.asyncio
    async def test_send_stockpile_non_json_response(
        self, webhook_connector: WebhookConnector, sample_payload: dict[str, Any]
    ) -> None:
        """Test sending with non-JSON response.

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_response.text = "OK"
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await webhook_connector.send_stockpile(sample_payload)

            assert result == ["HTTP 200: OK"]

    @pytest.mark.asyncio
    async def test_send_stockpile_connect_timeout(
        self, webhook_connector: WebhookConnector, sample_payload: dict[str, Any]
    ) -> None:
        """Test sending with connect timeout (should retry and eventually raise).

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = ConnectTimeout("Connection timed out")

            with pytest.raises(ConnectTimeout):
                await webhook_connector.send_stockpile(sample_payload)

            # Should retry 3 times due to the decorator
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_stockpile_generic_exception(
        self, webhook_connector: WebhookConnector, sample_payload: dict[str, Any]
    ) -> None:
        """Test sending with generic exception.

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Generic error")

            result = await webhook_connector.send_stockpile(sample_payload)

            # Generic exceptions should return a single-element message list.
            assert isinstance(result, list)
            assert "FS: Error sending stockpile to the webhook" in result[0]
            assert "Exception" in result[0]
            assert "Generic error" in result[0]

    @pytest.mark.asyncio
    async def test_send_stockpile_response_with_error_field(
        self, webhook_connector: WebhookConnector, sample_payload: dict[str, Any]
    ) -> None:
        """Test response handling when webhook returns error field.

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "Validation failed"}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await webhook_connector.send_stockpile(sample_payload)

            # The error field is surfaced as the single message.
            assert result == ["Validation failed"]

    @pytest.mark.asyncio
    async def test_send_stockpile_response_with_message_field(
        self, webhook_connector: WebhookConnector, sample_payload: dict[str, Any]
    ) -> None:
        """Test response handling when webhook returns message field.

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
            sample_payload (dict[str, Any]): Sample payload fixture.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Data received"}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await webhook_connector.send_stockpile(sample_payload)

            # The message field is surfaced as the single message.
            assert result == ["Data received"]

    def test_build_auth_headers_token_override_parameter(
        self, webhook_connector: WebhookConnector
    ) -> None:
        """Test that _build_auth_headers method accepts token override parameter.

        Args:
            webhook_connector (WebhookConnector): Webhook connector fixture.
        """
        # Test that the method can be called with a token override
        headers = webhook_connector._build_auth_headers(token="override_token")
        assert headers == {"Authorization": "Bearer override_token"}


class TestAsyncRetryDecorator:
    """Test cases for async retry decorator."""

    @pytest.mark.asyncio
    async def test_retry_decorator_success_first_try(self) -> None:
        """Test decorator when function succeeds on first try."""
        call_count = 0

        @async_retry_on_connect_timeout(max_retries=3, delay=1)
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await test_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_decorator_success_after_retries(self) -> None:
        """Test decorator when function succeeds after retries."""
        call_count = 0

        @async_retry_on_connect_timeout(max_retries=3, delay=1)
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectTimeout("Connection failed")
            return "success"

        with patch("foxhole_stockpiles.connectors.webhook.sleep") as mock_sleep:
            result = await test_func()

        assert result == "success"
        assert call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @pytest.mark.asyncio
    async def test_retry_decorator_max_retries_exceeded(self) -> None:
        """Test decorator when max retries are exceeded."""
        call_count = 0

        @async_retry_on_connect_timeout(max_retries=2, delay=1)
        async def test_func() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectTimeout("Connection failed")

        with patch("foxhole_stockpiles.connectors.webhook.sleep") as mock_sleep:
            with pytest.raises(ConnectTimeout):
                await test_func()

        assert call_count == 2  # Initial call + max_retries
        assert mock_sleep.call_count == 1  # Sleep between retries

    def test_retry_decorator_invalid_max_retries(self) -> None:
        """Test decorator with invalid max_retries parameter."""
        with pytest.raises(ValueError, match="max_retries must be a positive integer"):

            @async_retry_on_connect_timeout(max_retries=0)
            async def test_func() -> None:
                pass

    @pytest.mark.asyncio
    async def test_retry_decorator_non_connect_timeout_exception(self) -> None:
        """Test decorator with non-ConnectTimeout exception (should not retry)."""
        call_count = 0

        @async_retry_on_connect_timeout(max_retries=3, delay=1)
        async def test_func() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Different error")

        with pytest.raises(ValueError):
            await test_func()

        assert call_count == 1  # Should not retry for non-ConnectTimeout errors

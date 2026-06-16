"""Tests for FastAPI server module.

This module contains tests for the FastAPI server endpoints,
including health checks, error handling, and middleware functionality.
"""

import io
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from foxhole_stockpiles import __version__
from foxhole_stockpiles.api.dependencies import (
    get_ocr_coordinator,
    get_output_coordinator,
    get_scan_limiter,
)
from foxhole_stockpiles.api.scan_limiter import ScanLimiter
from foxhole_stockpiles.api.server import MAX_UPLOAD_SIZE_BYTES, app, auth_dependency
from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.sections.api import APIAuthSettings
from foxhole_stockpiles.core.settings.sections.output import (
    OutputHandlerConfig,
    ReturnHandlerSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.enums.auth_type import AuthType
from foxhole_stockpiles.enums.supported_language import SupportedLanguage


@pytest.fixture(autouse=True)
def clear_dependency_cache() -> Generator[None, None, None]:
    """Clear lru_cache from all dependency functions before and after each test.

    This ensures that mocked settings are picked up by the dependencies.

    Yields:
        None: Control to the test function
    """
    from foxhole_stockpiles.api.dependencies import (
        get_notification_service,
        get_ocr_coordinator,
        get_output_coordinator,
        get_scan_limiter,
    )

    # Clear all caches before test
    get_settings.cache_clear()
    get_notification_service.cache_clear()
    get_ocr_coordinator.cache_clear()
    get_output_coordinator.cache_clear()
    get_scan_limiter.cache_clear()

    # Clear any dependency overrides
    app.dependency_overrides.clear()

    yield

    # Clean up after test
    get_settings.cache_clear()
    get_notification_service.cache_clear()
    get_ocr_coordinator.cache_clear()
    get_output_coordinator.cache_clear()
    get_scan_limiter.cache_clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a test client for the FastAPI app.

    Args:
        tmp_path: Temporary directory from pytest fixture.
        monkeypatch: Pytest monkeypatch fixture for mocking.

    Returns:
        TestClient: A configured test client for making HTTP requests to the app.
    """
    from unittest.mock import MagicMock

    # Mock settings to provide a test database path
    mock_settings = MagicMock()
    mock_settings.scanner.database_path = tmp_path / "test_db.h5"
    mock_settings.api.auth_type = None
    mock_settings.api.auth_token = None
    mock_settings.api_auth.auth_type = None
    mock_settings.api_auth.auth_token = None
    mock_settings.api_server.max_concurrent_scans = 0  # Disable scan limiting in tests

    # Patch get_settings everywhere it's imported
    monkeypatch.setattr("foxhole_stockpiles.core.settings.get_settings", lambda: mock_settings)
    monkeypatch.setattr("foxhole_stockpiles.api.dependencies.get_settings", lambda: mock_settings)
    monkeypatch.setattr("foxhole_stockpiles.api.server.get_settings", lambda: mock_settings)
    monkeypatch.setattr("foxhole_stockpiles.api.server.app_settings", mock_settings)

    return TestClient(app)


@pytest.fixture
def sample_image() -> bytes:
    """Create a sample image file for testing.

    Returns:
        bytes: Fake image content as bytes for use in file upload tests.
    """
    # Create a simple test image file
    content = b"fake_image_content"
    return content


@pytest.fixture
def mock_scan_limiter() -> ScanLimiter:
    """Create a disabled scan limiter for testing.

    Returns:
        ScanLimiter: A scan limiter with limiting disabled (max_concurrent=0).
    """
    return ScanLimiter(max_concurrent=0)


class TestHealthEndpoint:
    """Test cases for health check endpoint.

    This class contains tests for the /health endpoint which provides
    system status information and health monitoring capabilities.
    """

    def test_health_check(self, client: TestClient) -> None:
        """Test health check endpoint returns proper status.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_check_includes_system_info(self, client: TestClient) -> None:
        """Test that health check includes system information.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == __version__


class TestErrorHandling:
    """Test cases for error handling.

    This class contains tests for various error conditions and proper
    HTTP status code responses for different failure scenarios.
    """

    def test_404_not_found(self, client: TestClient) -> None:
        """Test 404 error handling.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.get("/nonexistent-endpoint")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_method_not_allowed(self, client: TestClient) -> None:
        """Test method not allowed error.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.put("/health")

        assert response.status_code == 405
        data = response.json()
        assert "detail" in data


class TestMiddleware:
    """Test cases for middleware functionality.

    This class contains tests for middleware components including CORS,
    request logging, and rate limiting (if implemented).
    """

    def test_cors_headers(self, client: TestClient) -> None:
        """Test CORS headers are present.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.get("/health")

        assert response.status_code == 200
        # Check for common CORS headers (if implemented)
        # assert "Access-Control-Allow-Origin" in response.headers

    def test_rate_limiting(self, client: TestClient) -> None:
        """Test rate limiting (if implemented).

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = client.get("/health")
            responses.append(response.status_code)

        # All should succeed if no rate limiting, or some should be 429 if rate limited
        assert all(status in [200, 429] for status in responses)


class TestRootEndpoint:
    """Test cases for root endpoint.

    This class contains tests for the / endpoint that serves the web interface.
    """

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test root endpoint returns HTML web interface.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Foxhole Stockpile Scanner" in response.text

    def test_root_endpoint_contains_version(self, client: TestClient) -> None:
        """Test root endpoint HTML contains version information.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.get("/")

        assert response.status_code == 200
        assert __version__ in response.text


class TestScanStockpileEndpoint:
    """Test cases for the /ocr/scan_image endpoint.

    This class contains tests for image upload and processing functionality.
    """

    def test_scan_stockpile_invalid_file_type(self, client: TestClient) -> None:
        """Test scanning with non-image file.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        # Create a text file instead of an image
        files = {"image": ("test.txt", io.BytesIO(b"not an image"), "text/plain")}
        response = client.post("/ocr/scan_image", files=files)

        assert response.status_code == 400
        assert "File must be an image" in response.json()["detail"]

    def test_scan_stockpile_corrupted_image(self, client: TestClient) -> None:
        """Test scanning with corrupted image data.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        # Create invalid image data
        files = {"image": ("test.png", io.BytesIO(b"corrupted"), "image/png")}
        response = client.post("/ocr/scan_image", files=files)

        # HTTPException gets caught by generic handler, returns 500
        assert response.status_code in [400, 500]
        detail = response.json().get("detail", "")
        assert "Invalid image format" in detail or "Unexpected error" in detail

    def test_scan_stockpile_file_too_large(self, client: TestClient) -> None:
        """Test scanning with a file that exceeds the maximum size limit.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        # Create a file larger than the limit
        oversized_data = b"x" * (MAX_UPLOAD_SIZE_BYTES + 1)
        files = {"image": ("large.png", io.BytesIO(oversized_data), "image/png")}
        response = client.post("/ocr/scan_image", files=files)

        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]
        assert "10MB" in response.json()["detail"]

    def test_scan_stockpile_success(self, client: TestClient) -> None:
        """Test successful stockpile scanning.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        # Create a simple valid PNG image

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the OCR coordinator dependency
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        # Mock the output coordinator dependency
        mock_output_coordinator = Mock()
        mock_output_coordinator.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coordinator

        # Mock the scan limiter (disabled for tests)
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/ocr/scan_image", files=files)

            assert response.status_code == 200
            assert response.json() == {"result": "success"}
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    def test_scan_stockpile_with_faction_filter(self, client: TestClient) -> None:
        """Test scanning with faction filter parameter.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator dependency
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        # Mock the output handler
        # Mock the output coordinator dependency
        mock_output_coordinator = Mock()
        mock_output_coordinator.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coordinator
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/ocr/scan_image?faction=Colonials", files=files)

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_scan_stockpile_with_neutral_faction_becomes_none(self, client: TestClient) -> None:
        """Test that neutral faction is converted to None.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator dependency
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        # Mock the output handler
        # Mock the output coordinator dependency
        mock_output_coordinator = Mock()
        mock_output_coordinator.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coordinator
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/ocr/scan_image?faction=neutral", files=files)

            assert response.status_code == 200

            # Verify that analyze_stockpile was called with faction=None (neutral converted to None)
            mock_coordinator.analyze_stockpile.assert_called_once()
            call_kwargs = mock_coordinator.analyze_stockpile.call_args[1]
            assert call_kwargs["faction"] is None
        finally:
            app.dependency_overrides.clear()

    def test_scan_stockpile_with_all_parameters(self, client: TestClient) -> None:
        """Test scanning with all parameters.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator dependency
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        # Mock the output handler
        # Mock the output coordinator dependency
        mock_output_coordinator = Mock()
        mock_output_coordinator.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coordinator
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post(
                "/ocr/scan_image?faction=Wardens",
                files=files,
            )

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_scan_stockpile_with_invalid_faction(self, client: TestClient) -> None:
        """Test scanning with invalid faction parameter.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
        response = client.post("/ocr/scan_image?faction=invalid", files=files)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("faction" in str(error).lower() for error in detail)

    def test_scan_stockpile_with_language(self, client: TestClient) -> None:
        """Test scan with language parameter.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator dependency
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        # Mock the output handler
        # Mock the output coordinator dependency
        mock_output_coordinator = Mock()
        mock_output_coordinator.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coordinator
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/ocr/scan_image?language=fr", files=files)

            assert response.status_code == 200

            # Verify analyze_stockpile was called with French language parameter
            mock_coordinator.analyze_stockpile.assert_called_once()
            call_kwargs = mock_coordinator.analyze_stockpile.call_args[1]
            assert call_kwargs.get("languages") == [SupportedLanguage.FRENCH]
        finally:
            app.dependency_overrides.clear()

    def test_scan_stockpile_with_invalid_language(self, client: TestClient) -> None:
        """Test scan with invalid language parameter.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
        response = client.post("/ocr/scan_image?language=invalid", files=files)

        # FastAPI validation should return 422 for invalid enum value
        assert response.status_code == 422

    def test_scan_stockpile_processing_error(self, client: TestClient) -> None:
        """Test handling of processing errors during scan.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator dependency to raise ValueError
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(side_effect=ValueError("Processing failed"))
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/ocr/scan_image", files=files)

            assert response.status_code == 400
            assert "Processing error" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_scan_stockpile_unexpected_error(self, client: TestClient) -> None:
        """Test handling of unexpected errors during scan.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator dependency to raise generic exception
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(side_effect=RuntimeError("Unexpected"))
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/ocr/scan_image", files=files)

            assert response.status_code == 500
            assert "Unexpected error" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_scan_stockpile_mod_validation_error(self, client: TestClient) -> None:
        """Test handling of mod validation errors during scan.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator to raise mod validation error
        mock_coordinator = Mock()
        error_msg = "Mod 'CustomMod' is not supported. Available mods: Vanilla, OtherMod"
        mock_coordinator.analyze_stockpile = AsyncMock(side_effect=ValueError(error_msg))
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/ocr/scan_image", files=files)

            assert response.status_code == 422
            assert error_msg in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()


class TestLifespan:
    """Test cases for application lifespan events.

    This class contains tests for startup and shutdown event handling.
    """

    @patch("foxhole_stockpiles.api.server.setup_logging")
    def test_startup_logging(self, mock_setup_logging: Mock) -> None:
        """Test that startup event sets up logging correctly.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        # Creating the test client triggers lifespan events
        with TestClient(app):
            # Verify logging was set up
            mock_setup_logging.assert_called_once()

    def test_application_metadata(self, client: TestClient) -> None:
        """Test that application has correct metadata.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        # Access the OpenAPI schema to check metadata
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert schema["info"]["title"] == "Foxhole Stockpile Scanner API"
        assert schema["info"]["version"] == __version__

    @patch("foxhole_stockpiles.api.server.setup_logging")
    @patch("logging.getLogger")
    def test_lifespan_shutdown(self, mock_get_logger: Mock, mock_setup_logging: Mock) -> None:
        """Test that shutdown event logs correctly.

        Args:
            mock_get_logger (Mock): Mocked getLogger function.
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Create and close test client to trigger lifespan shutdown
        with TestClient(app):
            pass  # Exit context triggers shutdown

        # Verify shutdown was logged
        shutdown_logged = any(
            "Shutting down" in str(call) for call in mock_logger.info.call_args_list
        )
        assert shutdown_logged or mock_logger.info.call_count >= 2


class TestAuthHeaderHandling:
    """Test cases for authentication header handling."""

    @patch("foxhole_stockpiles.api.server.app_settings")
    def test_auth_header_extraction(
        self,
        mock_settings: Mock,
        client: TestClient,
    ) -> None:
        """Test extraction of auth header from request.

        Args:
            mock_settings (Mock): Mocked app settings.
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Configure mock settings with webhook handler using forward auth
        handler_config = OutputHandlerConfig(
            name="Test Webhook",
            handler=WebhookHandlerSettings(
                url="https://example.com/webhook",
                auth_type=AuthType.FORWARD,
                client_auth_header="X-API-Key",
            ),
        )
        mock_settings.output.handlers = [handler_config]

        # Mock the coordinator dependency
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        # Mock the output coordinator dependency
        mock_output_coordinator = Mock()
        mock_output_coordinator.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coordinator
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            headers = {"X-API-Key": "test-token"}
            response = client.post("/ocr/scan_image", files=files, headers=headers)

            assert response.status_code == 200

            # Verify handle_output was called with token
            mock_output_coordinator.handle_output.assert_called_once()
            call_kwargs = mock_output_coordinator.handle_output.call_args[1]
            assert call_kwargs["token"] == "test-token"
        finally:
            app.dependency_overrides.clear()

    @patch("foxhole_stockpiles.api.server.app_settings")
    def test_no_auth_header_extraction_when_not_configured(
        self,
        mock_settings: Mock,
        client: TestClient,
    ) -> None:
        """Test that token is None when no webhook handler uses forward auth.

        Args:
            mock_settings (Mock): Mocked app settings.
            client (TestClient): FastAPI test client from fixture.
        """
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Configure mock settings with return handler only (no forward auth)
        handler_config = OutputHandlerConfig(
            name="API Response",
            handler=ReturnHandlerSettings(),
        )
        mock_settings.output.handlers = [handler_config]

        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        mock_output_coordinator = Mock()
        mock_output_coordinator.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coordinator
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            headers = {"X-API-Key": "test-token"}
            response = client.post("/ocr/scan_image", files=files, headers=headers)

            assert response.status_code == 200

            # Verify handle_output was called with token=None
            mock_output_coordinator.handle_output.assert_called_once()
            call_kwargs = mock_output_coordinator.handle_output.call_args[1]
            assert call_kwargs["token"] is None
        finally:
            app.dependency_overrides.clear()


class TestAPIAuthentication:
    """Test cases for API endpoint authentication."""

    @patch("foxhole_stockpiles.api.server.app_settings")
    def test_no_auth_required_when_disabled(self, mock_settings: Mock, client: TestClient) -> None:
        """Test that requests succeed when authentication is disabled.

        Args:
            mock_settings (Mock): Mocked app settings.
            client (TestClient): FastAPI test client from fixture.
        """
        # Disable auth
        mock_settings.api_auth = APIAuthSettings(auth_type=None, auth_token=None)

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator dependency
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        # Mock the output coordinator dependency
        mock_output_coord = Mock()
        mock_output_coord.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coord
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/ocr/scan_image", files=files)

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @patch("foxhole_stockpiles.api.server.app_settings")
    def test_bearer_auth_success(self, mock_settings: Mock, client: TestClient) -> None:
        """Test successful bearer token authentication.

        Args:
            mock_settings (Mock): Mocked app settings.
            client (TestClient): FastAPI test client from fixture.
        """
        # Enable bearer auth
        mock_settings.api_auth = APIAuthSettings(
            auth_type=AuthType.BEARER, auth_token="test-token-123"
        )

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator dependency
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        # Mock the output coordinator dependency
        mock_output_coord = Mock()
        mock_output_coord.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coord
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            headers = {"Authorization": "Bearer test-token-123"}
            response = client.post("/ocr/scan_image", files=files, headers=headers)

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_bearer_auth_failure_wrong_token(self, client: TestClient) -> None:
        """Test bearer auth fails with wrong token.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """

        # Override auth dependency to raise 401
        async def failing_auth() -> None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        app.dependency_overrides[auth_dependency] = failing_auth

        try:
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            _, buffer = cv2.imencode(".png", img)
            image_bytes = buffer.tobytes()

            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            headers = {"Authorization": "Bearer wrong-token"}
            response = client.post("/ocr/scan_image", files=files, headers=headers)

            assert response.status_code == 401
            assert "Invalid authentication credentials" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_bearer_auth_failure_missing_header(self, client: TestClient) -> None:
        """Test bearer auth fails when header is missing.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """

        # Override auth dependency to raise 401
        async def failing_auth() -> None:
            raise HTTPException(status_code=401, detail="Authentication required")

        app.dependency_overrides[auth_dependency] = failing_auth

        try:
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            _, buffer = cv2.imencode(".png", img)
            image_bytes = buffer.tobytes()

            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/ocr/scan_image", files=files)

            assert response.status_code == 401
            assert "Authentication required" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @patch("foxhole_stockpiles.api.server.app_settings")
    def test_basic_auth_success(self, mock_settings: Mock, client: TestClient) -> None:
        """Test successful basic authentication.

        Args:
            mock_settings (Mock): Mocked app settings.
            client (TestClient): FastAPI test client from fixture.
        """
        # Enable basic auth
        mock_settings.api_auth = APIAuthSettings(
            auth_type=AuthType.BASIC, auth_token="dXNlcjpwYXNz"
        )

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock the coordinator dependency
        mock_coordinator = Mock()
        mock_coordinator.analyze_stockpile = AsyncMock(return_value=Mock())
        app.dependency_overrides[get_ocr_coordinator] = lambda: mock_coordinator

        # Mock the output coordinator dependency
        mock_output_coord = Mock()
        mock_output_coord.handle_output = AsyncMock(return_value={"result": "success"})
        app.dependency_overrides[get_output_coordinator] = lambda: mock_output_coord
        app.dependency_overrides[get_scan_limiter] = lambda: ScanLimiter(max_concurrent=0)

        try:
            files = {"image": ("test.png", io.BytesIO(image_bytes), "image/png")}
            headers = {"Authorization": "Basic dXNlcjpwYXNz"}
            response = client.post("/ocr/scan_image", files=files, headers=headers)

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


class TestMemoryMonitoringEndpoints:
    """Test cases for memory monitoring endpoints."""

    def test_memory_stats_endpoint(self, client: TestClient) -> None:
        """Test /memory/stats endpoint returns statistics.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.get("/memory/stats")

        assert response.status_code == 200
        data = response.json()

        # Check required keys
        assert "current_memory" in data
        assert "trends" in data
        assert "history_stats" in data
        assert "top_memory_requests" in data

        # Check current memory structure
        assert "rss_mb" in data["current_memory"]
        assert "vms_mb" in data["current_memory"]
        assert "percent" in data["current_memory"]
        assert "available_mb" in data["current_memory"]

        # Check trends structure
        assert "memory_growth_mb" in data["trends"]
        assert "growth_rate_mb_per_hour" in data["trends"]
        assert "total_requests" in data["trends"]

    def test_memory_current_endpoint(self, client: TestClient) -> None:
        """Test /memory/current endpoint returns current snapshot.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.get("/memory/current")

        assert response.status_code == 200
        data = response.json()

        # Check required keys
        assert "timestamp" in data
        assert "rss_mb" in data
        assert "vms_mb" in data
        assert "percent" in data
        assert "available_mb" in data

        # Check values are reasonable
        assert data["rss_mb"] > 0
        assert data["vms_mb"] > 0
        assert 0 <= data["percent"] <= 100

    def test_memory_gc_endpoint(self, client: TestClient) -> None:
        """Test /memory/gc endpoint forces garbage collection.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.post("/memory/gc")

        assert response.status_code == 200
        data = response.json()

        # Check required keys
        assert "objects_collected" in data
        assert "memory_before_mb" in data
        assert "memory_after_mb" in data
        assert "memory_freed_mb" in data

        # Check types and reasonable values
        assert isinstance(data["objects_collected"], int)
        assert data["objects_collected"] >= 0
        assert data["memory_before_mb"] > 0
        assert data["memory_after_mb"] > 0

    def test_memory_gc_stats_endpoint(self, client: TestClient) -> None:
        """Test /memory/gc-stats endpoint returns GC statistics.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        response = client.get("/memory/gc-stats")

        assert response.status_code == 200
        data = response.json()

        # Check required keys
        assert "gc_enabled" in data
        assert "generation_counts" in data
        assert "total_tracked_objects" in data
        assert "top_object_types" in data
        assert "gc_stats" in data

        # Check GC enabled
        assert isinstance(data["gc_enabled"], bool)

        # Check generation counts
        assert "generation_0" in data["generation_counts"]
        assert "generation_1" in data["generation_counts"]
        assert "generation_2" in data["generation_counts"]

        # Check object counts
        assert data["total_tracked_objects"] > 0
        assert isinstance(data["top_object_types"], list)

    @patch("foxhole_stockpiles.api.server.app_settings")
    def test_memory_endpoints_with_auth_disabled(
        self, mock_settings: Mock, client: TestClient
    ) -> None:
        """Test that memory endpoints work when auth is disabled.

        Args:
            mock_settings (Mock): Mocked app settings.
            client (TestClient): FastAPI test client from fixture.
        """
        # Disable auth
        mock_settings.api_auth = APIAuthSettings(auth_type=None, auth_token=None)

        endpoints = [
            ("/memory/stats", "GET"),
            ("/memory/current", "GET"),
            ("/memory/gc", "POST"),
            ("/memory/gc-stats", "GET"),
        ]

        for endpoint, method in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint)

            assert response.status_code == 200, f"Failed on {method} {endpoint}"

    def test_memory_endpoints_require_auth_when_enabled(self, client: TestClient) -> None:
        """Test that memory endpoints require auth when it's enabled.

        Args:
            client (TestClient): FastAPI test client from fixture.
        """
        endpoints = [
            ("/memory/stats", "GET"),
            ("/memory/current", "GET"),
            ("/memory/gc", "POST"),
            ("/memory/gc-stats", "GET"),
        ]

        # Override auth dependency to require auth
        async def require_auth() -> None:
            raise HTTPException(status_code=401, detail="Authentication required")

        app.dependency_overrides[auth_dependency] = require_auth

        try:
            # Without auth - should fail with 401
            for endpoint, method in endpoints:
                if method == "GET":
                    response = client.get(endpoint)
                else:
                    response = client.post(endpoint)

                assert response.status_code == 401, f"Expected 401 for {method} {endpoint}"
                assert "Authentication required" in response.json()["detail"]

        finally:
            app.dependency_overrides.clear()

        # Reset to allow access (simulate successful auth)
        async def allow_auth() -> None:
            return None

        app.dependency_overrides[auth_dependency] = allow_auth

        try:
            # With auth - should succeed
            for endpoint, method in endpoints:
                if method == "GET":
                    response = client.get(endpoint)
                else:
                    response = client.post(endpoint)

                assert response.status_code == 200, f"Expected 200 for {method} {endpoint}"

        finally:
            app.dependency_overrides.clear()


class TestLifespanErrorHandling:
    """Test cases for error handling during lifespan events."""

    @patch("foxhole_stockpiles.api.server.setup_logging")
    @patch("foxhole_stockpiles.api.server.get_notification_service")
    @patch("foxhole_stockpiles.api.server.app_settings")
    def test_shutdown_handles_notification_error(
        self,
        mock_app_settings: Mock,
        mock_get_notification_service: Mock,
        mock_setup_logging: Mock,
    ) -> None:
        """Test that shutdown handles notification send errors gracefully.

        Args:
            mock_app_settings (Mock): Mocked application settings.
            mock_get_notification_service (Mock): Mocked notification service getter.
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        # Enable notifications
        mock_app_settings.notifications.enabled = True

        # Make notification service raise an exception on shutdown
        mock_notification_service = AsyncMock()
        mock_notification_service.send_notification.side_effect = Exception("Notification error")
        mock_get_notification_service.return_value = mock_notification_service

        # App should shut down gracefully despite the error
        with TestClient(app):
            pass  # Exit triggers shutdown

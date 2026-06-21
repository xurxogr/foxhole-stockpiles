"""Tests for web routes module."""

import io
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from foxhole_stockpiles import __version__
from foxhole_stockpiles.api.dependencies import (
    get_catalog_service,
    get_scanner,
)
from foxhole_stockpiles.api.server import app
from foxhole_stockpiles.api.web.routes import _render_combined_table, _render_stockpile_table
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem


@pytest.fixture(autouse=True)
def clear_dependency_cache() -> Generator[None, None, None]:
    """Clear lru_cache from dependencies before and after each test."""
    from foxhole_stockpiles.api.dependencies import (
        get_catalog_service,
        get_notification_service,
        get_output_coordinator,
        get_scanner,
    )
    from foxhole_stockpiles.core.settings import get_settings

    # Clear caches
    get_settings.cache_clear()
    get_notification_service.cache_clear()
    get_scanner.cache_clear()
    get_output_coordinator.cache_clear()
    get_catalog_service.cache_clear()

    app.dependency_overrides.clear()

    yield

    get_settings.cache_clear()
    get_notification_service.cache_clear()
    get_scanner.cache_clear()
    get_output_coordinator.cache_clear()
    get_catalog_service.cache_clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a test client for the FastAPI app."""
    from unittest.mock import MagicMock

    mock_settings = MagicMock()
    mock_settings.scanner.database_path = tmp_path / "test_db.h5"
    mock_settings.api.auth_type = None
    mock_settings.api.auth_token = None
    mock_settings.api_auth.auth_type = None
    mock_settings.api_auth.auth_token = None

    monkeypatch.setattr("foxhole_stockpiles.core.settings.get_settings", lambda: mock_settings)
    monkeypatch.setattr("foxhole_stockpiles.api.dependencies.get_settings", lambda: mock_settings)
    monkeypatch.setattr("foxhole_stockpiles.api.server.get_settings", lambda: mock_settings)
    monkeypatch.setattr("foxhole_stockpiles.api.server.app_settings", mock_settings)

    return TestClient(app)


@pytest.fixture
def mock_catalog_service() -> Mock:
    """Create a mock catalog service."""
    service = Mock()
    service.get_display_name.side_effect = lambda code: f"Display Name for {code}"
    return service


class TestWebIndex:
    """Tests for the web index endpoint."""

    def test_web_index_returns_html(self, client: TestClient) -> None:
        """Test that GET / returns HTML."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_web_index_contains_title(self, client: TestClient) -> None:
        """Test that the page contains the title."""
        response = client.get("/")

        assert "Foxhole Stockpile Scanner" in response.text

    def test_web_index_contains_version(self, client: TestClient) -> None:
        """Test that the page contains the version."""
        response = client.get("/")

        assert __version__ in response.text

    def test_web_index_contains_upload_form(self, client: TestClient) -> None:
        """Test that the page contains the upload form."""
        response = client.get("/")

        assert 'action="/web/scan"' in response.text
        assert 'type="file"' in response.text

    def test_web_index_shows_db_error_value_error(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that ValueError database errors are displayed."""
        monkeypatch.setattr(
            "foxhole_stockpiles.api.web.routes.get_scanner",
            Mock(side_effect=ValueError("Database not configured")),
        )

        response = client.get("/")

        assert response.status_code == 200
        assert "Database not configured" in response.text

    def test_web_index_shows_db_error_file_not_found(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that FileNotFoundError database errors are displayed."""
        monkeypatch.setattr(
            "foxhole_stockpiles.api.web.routes.get_scanner",
            Mock(side_effect=FileNotFoundError("/path/to/db.h5")),
        )

        response = client.get("/")

        assert response.status_code == 200
        assert "Database file not found" in response.text

    def test_web_index_shows_db_error_generic(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that generic database errors are displayed."""
        monkeypatch.setattr(
            "foxhole_stockpiles.api.web.routes.get_scanner",
            Mock(side_effect=RuntimeError("Unexpected database error")),
        )

        response = client.get("/")

        assert response.status_code == 200
        assert "Database error" in response.text

    def test_web_index_contains_buttons(self, client: TestClient) -> None:
        """Test that the page contains scan buttons."""
        response = client.get("/")

        assert "Preview Results" in response.text
        assert "Process with Server" in response.text


class TestWebScan:
    """Tests for the web scan endpoint."""

    def test_scan_no_images(self, client: TestClient) -> None:
        """Test scanning with no images returns error."""
        app.dependency_overrides[get_scanner] = lambda: Mock()
        try:
            response = client.post("/web/scan", data={"action": "scan"})

            assert response.status_code == 422  # No file uploaded
        finally:
            app.dependency_overrides.clear()

    def test_scan_empty_filename(self, client: TestClient) -> None:
        """Test scanning with empty filename returns error."""
        app.dependency_overrides[get_scanner] = lambda: Mock()
        try:
            files = {"images": ("", io.BytesIO(b""), "image/png")}
            response = client.post("/web/scan", files=files, data={"action": "scan"})

            # FastAPI validation may return 422 or our handler returns 400
            assert response.status_code in [400, 422]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_scan_empty_images_list_direct(
        self,
        mock_catalog_service: Mock,
    ) -> None:
        """Test web_scan directly with empty images list."""
        from fastapi import Request, UploadFile

        from foxhole_stockpiles.api.web.routes import web_scan

        # Create mock request
        mock_request = Mock(spec=Request)

        # Create mock UploadFile with empty filename
        mock_upload = Mock(spec=UploadFile)
        mock_upload.filename = ""

        mock_scanner = Mock()

        response = await web_scan(
            request=mock_request,
            images=[mock_upload],
            scanner=mock_scanner,
            catalog_service=mock_catalog_service,
            action="scan",
        )

        assert response.status_code == 400
        assert "No images uploaded" in bytes(response.body).decode()

    def test_scan_invalid_content_type(
        self,
        client: TestClient,
        mock_catalog_service: Mock,
    ) -> None:
        """Test scanning with non-image file type."""
        app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_service

        # Mock coordinator
        mock_scanner = Mock()
        mock_scanner.scan = AsyncMock(
            return_value=Stockpile(
                name="Test",
                type=StockpileType.STORAGE_DEPOT,
                items=[],
            )
        )
        app.dependency_overrides[get_scanner] = lambda: mock_scanner

        try:
            files = {"images": ("test.txt", io.BytesIO(b"text content"), "text/plain")}
            response = client.post("/web/scan", files=files, data={"action": "scan"})

            # Should show warning about invalid file
            assert response.status_code in [200, 400]
        finally:
            app.dependency_overrides.clear()

    def test_scan_success_single_image(
        self,
        client: TestClient,
        mock_catalog_service: Mock,
    ) -> None:
        """Test successful scan of a single image."""
        # Create valid PNG image
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Mock coordinator
        mock_stockpile = Stockpile(
            name="Test Stockpile",
            type=StockpileType.STORAGE_DEPOT,
            items=[
                StockpileItem(code="Item1", quantity=100, crated=False),
                StockpileItem(code="Item2", quantity=50, crated=True),
            ],
        )
        mock_scanner = Mock()
        mock_scanner.scan = AsyncMock(return_value=mock_stockpile)

        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_service

        try:
            files = {"images": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/web/scan", files=files, data={"action": "scan"})

            assert response.status_code == 200
            assert "Test Stockpile" in response.text
            assert "StorageFacility" in response.text  # In-game code name
            assert "100" in response.text
            assert "50" in response.text
            assert "Crated" in response.text  # Crated badge
        finally:
            app.dependency_overrides.clear()

    def test_scan_success_multiple_images(
        self,
        client: TestClient,
        mock_catalog_service: Mock,
    ) -> None:
        """Test successful scan of multiple images shows combined table."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Two stockpiles with overlapping items
        stockpile1 = Stockpile(
            name="Stockpile 1",
            type=StockpileType.STORAGE_DEPOT,
            items=[StockpileItem(code="Item1", quantity=100, crated=False)],
        )
        stockpile2 = Stockpile(
            name="Stockpile 2",
            type=StockpileType.SEAPORT,
            items=[StockpileItem(code="Item1", quantity=50, crated=False)],
        )

        mock_scanner = Mock()
        mock_scanner.scan = AsyncMock(side_effect=[stockpile1, stockpile2])

        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_service

        try:
            files = [
                ("images", ("test1.png", io.BytesIO(image_bytes), "image/png")),
                ("images", ("test2.png", io.BytesIO(image_bytes), "image/png")),
            ]
            response = client.post("/web/scan", files=files, data={"action": "scan"})

            assert response.status_code == 200
            assert "Stockpile 1" in response.text
            assert "Stockpile 2" in response.text
            assert "Combined" in response.text
            assert "150" in response.text  # Combined quantity
        finally:
            app.dependency_overrides.clear()

    def test_scan_no_stockpiles_detected(
        self,
        client: TestClient,
        mock_catalog_service: Mock,
    ) -> None:
        """Test when no stockpiles are detected."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        # Coordinator raises exception
        mock_scanner = Mock()
        mock_scanner.scan = AsyncMock(side_effect=Exception("No stockpile found"))

        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_service

        try:
            files = {"images": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/web/scan", files=files, data={"action": "scan"})

            assert response.status_code == 400
            assert "No stockpiles detected" in response.text
        finally:
            app.dependency_overrides.clear()

    def test_scan_shows_timing(
        self,
        client: TestClient,
        mock_catalog_service: Mock,
    ) -> None:
        """Test that scan results include timing information."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", img)
        image_bytes = buffer.tobytes()

        mock_stockpile = Stockpile(
            name="Test",
            type=StockpileType.STORAGE_DEPOT,
            items=[StockpileItem(code="Item1", quantity=10, crated=False)],
        )
        mock_scanner = Mock()
        mock_scanner.scan = AsyncMock(return_value=mock_stockpile)

        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_service

        try:
            files = {"images": ("test.png", io.BytesIO(image_bytes), "image/png")}
            response = client.post("/web/scan", files=files, data={"action": "scan"})

            assert response.status_code == 200
            assert "Scan Time" in response.text
        finally:
            app.dependency_overrides.clear()

    def test_scan_corrupted_image_shows_warning(
        self,
        client: TestClient,
        mock_catalog_service: Mock,
    ) -> None:
        """Test that corrupted images show warning but continue processing."""
        # Create one valid and one corrupted image
        valid_img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".png", valid_img)
        valid_bytes = buffer.tobytes()
        corrupted_bytes = b"not a valid image"

        mock_stockpile = Stockpile(
            name="Valid Stockpile",
            type=StockpileType.STORAGE_DEPOT,
            items=[StockpileItem(code="Item1", quantity=10, crated=False)],
        )
        mock_scanner = Mock()
        mock_scanner.scan = AsyncMock(return_value=mock_stockpile)

        app.dependency_overrides[get_scanner] = lambda: mock_scanner
        app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_service

        try:
            files = [
                ("images", ("valid.png", io.BytesIO(valid_bytes), "image/png")),
                ("images", ("corrupted.png", io.BytesIO(corrupted_bytes), "image/png")),
            ]
            response = client.post("/web/scan", files=files, data={"action": "scan"})

            assert response.status_code == 200
            # Should show warning about corrupted image
            assert "Processing Warnings" in response.text
            assert "Could not decode image" in response.text
            # But still show the valid stockpile
            assert "Valid Stockpile" in response.text
        finally:
            app.dependency_overrides.clear()


class TestRenderStockpileTable:
    """Tests for _render_stockpile_table helper function."""

    def test_render_basic_table(self, mock_catalog_service: Mock) -> None:
        """Test rendering a basic stockpile table."""
        stockpile = Stockpile(
            name="Test Stockpile",
            type=StockpileType.STORAGE_DEPOT,
            items=[
                StockpileItem(code="Item1", quantity=100, crated=False),
            ],
        )

        html = _render_stockpile_table(
            stockpile=stockpile,
            catalog_service=mock_catalog_service,
        )

        assert "Test Stockpile" in html
        assert "StorageFacility" in html  # In-game code name
        assert "100" in html
        assert "Display Name for Item1" in html

    def test_render_table_with_crated_items(self, mock_catalog_service: Mock) -> None:
        """Test rendering table with crated items shows badge."""
        stockpile = Stockpile(
            name="Test",
            type=StockpileType.SEAPORT,
            items=[
                StockpileItem(code="Item1", quantity=50, crated=True),
            ],
        )

        html = _render_stockpile_table(
            stockpile=stockpile,
            catalog_service=mock_catalog_service,
        )

        assert "Crated" in html
        assert "crated-badge" in html

    def test_render_table_with_unknown_quantity(self, mock_catalog_service: Mock) -> None:
        """Test rendering table with unknown quantity shows ?."""
        stockpile = Stockpile(
            name="Test",
            type=StockpileType.STORAGE_DEPOT,
            items=[
                StockpileItem(code="Item1", quantity=-1, crated=False),
            ],
        )

        html = _render_stockpile_table(
            stockpile=stockpile,
            catalog_service=mock_catalog_service,
        )

        assert ">?<" in html

    def test_render_table_with_undefined_type(self, mock_catalog_service: Mock) -> None:
        """Test rendering table with undefined stockpile type."""
        stockpile = Stockpile(
            name="Test",
            type=StockpileType.UNDEFINED,
            items=[],
        )

        html = _render_stockpile_table(
            stockpile=stockpile,
            catalog_service=mock_catalog_service,
        )

        assert "Undefined" in html

    def test_render_table_with_empty_name(self, mock_catalog_service: Mock) -> None:
        """Test rendering table with empty stockpile name shows Unnamed."""
        stockpile = Stockpile(
            name="",
            type=StockpileType.STORAGE_DEPOT,
            items=[],
        )

        html = _render_stockpile_table(
            stockpile=stockpile,
            catalog_service=mock_catalog_service,
        )

        assert "Unnamed" in html


class TestRenderCombinedTable:
    """Tests for _render_combined_table helper function."""

    def test_render_combined_table(self, mock_catalog_service: Mock) -> None:
        """Test rendering a combined table."""
        combined_items = {
            ("Item1", False): 150,
            ("Item2", True): 75,
        }

        html = _render_combined_table(
            combined_items=combined_items,
            catalog_service=mock_catalog_service,
        )

        assert "Combined" in html
        assert "150" in html
        assert "75" in html
        assert "225 total items" in html  # Total quantity

    def test_render_combined_table_sorted_by_name(self, mock_catalog_service: Mock) -> None:
        """Test that combined table is sorted by display name."""
        # Set up catalog service to return predictable names
        mock_catalog_service.get_display_name.side_effect = lambda code: {
            "ZItem": "Zebra Item",
            "AItem": "Alpha Item",
        }.get(code, code)

        combined_items = {
            ("ZItem", False): 10,
            ("AItem", False): 20,
        }

        html = _render_combined_table(
            combined_items=combined_items,
            catalog_service=mock_catalog_service,
        )

        # Alpha should appear before Zebra
        alpha_pos = html.find("Alpha Item")
        zebra_pos = html.find("Zebra Item")
        assert alpha_pos < zebra_pos

    def test_render_combined_table_with_crated(self, mock_catalog_service: Mock) -> None:
        """Test combined table shows crated badge."""
        combined_items = {("Item1", True): 100}

        html = _render_combined_table(
            combined_items=combined_items,
            catalog_service=mock_catalog_service,
        )

        assert "Crated" in html
        assert "crated-badge" in html

"""Tests for api.dependencies module."""

from unittest.mock import Mock, patch

import pytest

from foxhole_stockpiles.api.dependencies import (
    clear_dependency_caches,
    get_notification_service,
    get_output_coordinator,
    get_scanner,
)
from foxhole_stockpiles.core.events import EventBus
from foxhole_stockpiles.services.notification_service import NotificationService


class TestGetNotificationService:
    """Test suite for get_notification_service dependency."""

    def test_get_notification_service_returns_singleton(self) -> None:
        """Test that get_notification_service returns the same instance."""
        # Clear the cache first
        get_notification_service.cache_clear()

        with patch("foxhole_stockpiles.api.dependencies.get_settings") as mock_settings:
            with patch("foxhole_stockpiles.api.dependencies.get_event_bus") as mock_event_bus:
                mock_settings.return_value.notifications.enabled = False
                mock_event_bus.return_value = EventBus()

                service1 = get_notification_service()
                service2 = get_notification_service()

                assert service1 is service2
                assert isinstance(service1, NotificationService)

        get_notification_service.cache_clear()

    def test_get_notification_service_initializes_service(self) -> None:
        """Test that get_notification_service initializes the service."""
        get_notification_service.cache_clear()

        with patch("foxhole_stockpiles.api.dependencies.get_settings") as mock_settings:
            with patch("foxhole_stockpiles.api.dependencies.get_event_bus") as mock_event_bus:
                with patch(
                    "foxhole_stockpiles.api.dependencies.NotificationService"
                ) as mock_service_class:
                    mock_settings.return_value.notifications.enabled = False
                    mock_event_bus.return_value = EventBus()
                    mock_service = Mock()
                    mock_service_class.return_value = mock_service

                    result = get_notification_service()

                    mock_service.initialize.assert_called_once()
                    assert result is mock_service

        get_notification_service.cache_clear()


class TestGetScanner:
    """Test suite for get_scanner dependency."""

    def test_get_scanner_returns_singleton(self) -> None:
        """Test that get_scanner returns the same instance."""
        get_scanner.cache_clear()

        with patch("foxhole_stockpiles.api.dependencies.get_settings") as mock_settings:
            with patch("foxhole_stockpiles.api.dependencies.Scanner") as mock_scanner_class:
                mock_settings.return_value.scanner.database_path = "/path/to/db.h5"
                mock_scanner = Mock()
                mock_scanner_class.return_value = mock_scanner

                scanner1 = get_scanner()
                scanner2 = get_scanner()

                assert scanner1 is scanner2
                assert scanner1 is mock_scanner

        get_scanner.cache_clear()

    def test_get_scanner_raises_when_database_path_none(self) -> None:
        """Test that the scanner raises ValueError when database_path is None."""
        get_scanner.cache_clear()

        with patch("foxhole_stockpiles.api.dependencies.get_settings") as mock_settings:
            scanner_config = Mock()
            scanner_config.database_path = None
            mock_settings.return_value.scanner = scanner_config

            with pytest.raises(ValueError, match="scanner.database_path must be configured"):
                get_scanner()

        get_scanner.cache_clear()

    def test_get_scanner_creates_with_settings(self) -> None:
        """Test that get_scanner builds a Scanner from the scanner settings."""
        get_scanner.cache_clear()

        with patch("foxhole_stockpiles.api.dependencies.get_settings") as mock_settings:
            with patch("foxhole_stockpiles.api.dependencies.Scanner") as mock_scanner_class:
                mock_scanner_config = Mock()
                mock_scanner_config.database_path = "/path/to/db.h5"
                mock_settings.return_value.scanner = mock_scanner_config

                get_scanner()

                mock_scanner_class.assert_called_once_with(mock_scanner_config)

        get_scanner.cache_clear()


class TestGetOutputCoordinator:
    """Test suite for get_output_coordinator dependency."""

    def test_get_output_coordinator_returns_singleton(self) -> None:
        """Test that get_output_coordinator returns the same instance."""
        get_output_coordinator.cache_clear()

        with patch("foxhole_stockpiles.api.dependencies.get_settings") as mock_settings:
            with patch(
                "foxhole_stockpiles.api.dependencies.OutputCoordinator"
            ) as mock_coordinator_class:
                mock_settings_obj = Mock()
                mock_settings.return_value = mock_settings_obj
                mock_coordinator = Mock()
                mock_coordinator_class.return_value = mock_coordinator

                coordinator1 = get_output_coordinator()
                coordinator2 = get_output_coordinator()

                assert coordinator1 is coordinator2
                assert coordinator1 is mock_coordinator

        get_output_coordinator.cache_clear()

    def test_get_output_coordinator_creates_with_settings(self) -> None:
        """Test that get_output_coordinator creates OutputCoordinator with output settings."""
        get_output_coordinator.cache_clear()

        with patch("foxhole_stockpiles.api.dependencies.get_settings") as mock_settings:
            with patch(
                "foxhole_stockpiles.api.dependencies.OutputCoordinator"
            ) as mock_coordinator_class:
                mock_settings_obj = Mock()
                mock_settings.return_value = mock_settings_obj

                get_output_coordinator()

                mock_coordinator_class.assert_called_once_with(
                    output_settings=mock_settings_obj.output
                )

        get_output_coordinator.cache_clear()


class TestClearDependencyCaches:
    """Test suite for clear_dependency_caches function."""

    def test_clear_dependency_caches_shuts_down_notification_service(self) -> None:
        """Test that clear_dependency_caches calls shutdown on notification service."""
        # First, populate the notification service cache
        get_notification_service.cache_clear()

        with patch("foxhole_stockpiles.api.dependencies.get_settings") as mock_settings:
            with patch("foxhole_stockpiles.api.dependencies.get_event_bus") as mock_event_bus:
                mock_settings.return_value.notifications.enabled = False
                mock_event_bus.return_value = EventBus()

                service = get_notification_service()

                # Spy on the shutdown method
                with patch.object(service, "shutdown") as mock_shutdown:
                    # Clear caches
                    clear_dependency_caches()

                    # Verify shutdown was called
                    mock_shutdown.assert_called_once()

        get_notification_service.cache_clear()

    def test_clear_dependency_caches_handles_empty_cache(self) -> None:
        """Test that clear_dependency_caches handles case when no cache exists."""
        # Clear all caches first
        get_notification_service.cache_clear()
        get_scanner.cache_clear()
        get_output_coordinator.cache_clear()

        # Should not raise any exception
        clear_dependency_caches()

"""FastAPI dependency injection providers."""

import logging
from functools import lru_cache

from foxhole_stockpiles.api.scan_limiter import ScanLimiter
from foxhole_stockpiles.core.events import get_event_bus
from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.services.catalog_service import CatalogService
from foxhole_stockpiles.services.notification_service import NotificationService
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator
from fs_ocr._impl.coordinator import OCRCoordinator

logger = logging.getLogger(__name__)


@lru_cache
def get_scan_limiter() -> ScanLimiter:
    """Get the scan limiter singleton.

    Limits concurrent scan operations per worker to prevent CPU contention.

    Returns:
        ScanLimiter: The scan limiter instance.
    """
    settings = get_settings()
    return ScanLimiter(max_concurrent=settings.api_server.max_concurrent_scans)


@lru_cache
def get_notification_service() -> NotificationService:
    """Get the notification service singleton.

    Returns:
        NotificationService: The notification service instance
    """
    settings = get_settings()
    event_bus = get_event_bus()
    service = NotificationService(settings.notifications, event_bus=event_bus)
    service.initialize()
    return service


@lru_cache
def get_ocr_coordinator() -> OCRCoordinator:
    """Get the OCR coordinator singleton.

    This creates a single OCRCoordinator instance that is reused across all requests,
    significantly reducing memory usage and initialization overhead.

    Returns:
        OCRCoordinator: The OCR coordinator instance

    Raises:
        ValueError: If database_path is not configured in settings
    """
    settings = get_settings()
    event_bus = get_event_bus()

    if settings.scanner.database_path is None:
        raise ValueError("scanner.database_path must be configured for the server")

    return OCRCoordinator(config=settings.scanner, event_bus=event_bus)


@lru_cache
def get_output_coordinator() -> OutputCoordinator:
    """Get the output coordinator singleton.

    This creates a single OutputCoordinator instance that is reused across all requests,
    reducing memory usage from repeated handler initialization.

    Returns:
        OutputCoordinator: The output coordinator instance
    """
    settings = get_settings()
    return OutputCoordinator(output_settings=settings.output)


@lru_cache
def get_catalog_service() -> CatalogService:
    """Get the catalog service singleton.

    Returns:
        CatalogService: The catalog service instance
    """
    settings = get_settings()
    catalog_path = settings.database_builder.catalog_file
    return CatalogService(catalog_path=catalog_path)


def clear_dependency_caches() -> None:
    """Clear all dependency caches.

    Call this when the server stops to ensure next start picks up fresh settings.
    """
    logger.info("Clearing all dependency caches")

    # Shutdown notification service to unsubscribe event handlers before clearing cache
    try:
        # Check if the cache has an entry (service was initialized)
        cache_info = get_notification_service.cache_info()
        if cache_info.currsize > 0:
            notification_service = get_notification_service()
            notification_service.shutdown()
    except Exception as e:
        logger.warning(f"Error shutting down notification service: {e}")

    get_catalog_service.cache_clear()
    get_output_coordinator.cache_clear()
    get_ocr_coordinator.cache_clear()
    get_notification_service.cache_clear()
    get_scan_limiter.cache_clear()

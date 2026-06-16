"""Web interface routes for the API server."""

import html
import json
import logging
import time
from pathlib import Path
from typing import Annotated

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from foxhole_stockpiles import __version__
from foxhole_stockpiles.api.dependencies import (
    get_catalog_service,
    get_ocr_coordinator,
)
from foxhole_stockpiles.core.utils import get_bundled_resource_path, is_frozen
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.catalog_service import CatalogService
from fs_ocr._impl.coordinator import OCRCoordinator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["web"])


def _get_templates_dir() -> Path:
    """Get the templates directory, handling both dev and PyInstaller bundle."""
    if is_frozen():
        return get_bundled_resource_path("foxhole_stockpiles/api/templates")
    # Development mode
    return Path(__file__).parent.parent / "templates"


# Set up Jinja2 templates
templates_dir = _get_templates_dir()
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=HTMLResponse)
async def web_index(request: Request) -> HTMLResponse:
    """Render the main upload page.

    Args:
        request: The FastAPI request object.

    Returns:
        HTML response with the upload page.
    """
    db_error = None

    try:
        # Try to get the OCR coordinator to check if database is accessible
        get_ocr_coordinator()
    except ValueError as e:
        db_error = str(e)
    except FileNotFoundError as e:
        db_error = f"Database file not found: {e}"
    except Exception as e:
        db_error = f"Database error: {e}"

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "version": __version__,
            "db_error": db_error,
        },
    )


@router.post("/web/scan", response_class=HTMLResponse)
async def web_scan(
    request: Request,
    images: list[UploadFile],
    coordinator: Annotated[OCRCoordinator, Depends(get_ocr_coordinator)],
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
    action: Annotated[str, Form()] = "scan",
) -> HTMLResponse:
    """Scan uploaded screenshots and return HTML results.

    Args:
        request: The FastAPI request object.
        images: List of uploaded image files.
        action: Form action ('scan' or 'send').
        coordinator: OCR coordinator for scanning.
        catalog_service: Catalog service for display names.

    Returns:
        HTML response with scan results.
    """
    if not images or not images[0].filename:
        return HTMLResponse(
            '<div class="alert alert-error"><span class="alert-icon">!</span>'
            "<div>No images uploaded</div></div>",
            status_code=400,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    stockpiles: list[Stockpile] = []
    errors: list[str] = []
    scan_start_time = time.perf_counter()

    # Process each uploaded image
    for image in images:
        if not image.content_type or not image.content_type.startswith("image/"):
            errors.append(f"{image.filename}: Not a valid image file")
            continue

        try:
            content = await image.read()
            nparr = np.frombuffer(content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                errors.append(f"{image.filename}: Could not decode image")
                continue

            image_bgr = np.asarray(img, dtype=np.uint8)
            stockpile = await coordinator.analyze_stockpile(image=image_bgr)
            stockpiles.append(stockpile)

        except Exception as e:
            logger.exception("Error processing image %s", image.filename)
            errors.append(f"{image.filename}: {str(e)}")

    scan_time = time.perf_counter() - scan_start_time

    if not stockpiles:
        error_html = (
            '<div class="alert alert-error"><span class="alert-icon">!</span><div>'
            "<strong>No stockpiles detected</strong>"
        )
        if errors:
            error_html += "<br>" + "<br>".join(errors)
        error_html += "</div></div>"
        return HTMLResponse(
            error_html,
            status_code=400,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    # Build combined table if multiple stockpiles
    combined_items: dict[tuple[str, bool], int] = {}
    if len(stockpiles) > 1:
        for stockpile in stockpiles:
            for item in stockpile.items:
                if item.quantity >= 0:  # Only include valid quantities
                    key = (item.code, item.crated)
                    combined_items[key] = combined_items.get(key, 0) + item.quantity

    # Generate HTML
    html_parts = []

    # Summary section
    total_items = sum(len(s.items) for s in stockpiles)
    total_quantity = sum(
        item.quantity for s in stockpiles for item in s.items if item.quantity >= 0
    )

    # Serialize stockpiles to JSON for download functionality
    stockpiles_json = json.dumps(
        [s.model_dump(mode="json") for s in stockpiles],
        ensure_ascii=False,
    )

    html_parts.append(f"""
    <script id="stockpile-data" type="application/json">{stockpiles_json}</script>
    <div class="card">
        <div class="card-header">
            <h2>Scan Results</h2>
            <div class="download-buttons">
                <button type="button" class="btn btn-secondary btn-sm" onclick="downloadJSON()">
                    Download JSON
                </button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="downloadTSV()">
                    Download TSV
                </button>
            </div>
        </div>
        <div class="card-body">
            <div class="summary">
                <div class="summary-item">
                    <div class="summary-value">{len(stockpiles)}</div>
                    <div class="summary-label">Stockpiles</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{total_items}</div>
                    <div class="summary-label">Item Types</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{total_quantity:,}</div>
                    <div class="summary-label">Total Items</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{scan_time:.2f}s</div>
                    <div class="summary-label">Scan Time</div>
                </div>
            </div>
        </div>
    </div>
    """)

    # Errors section
    if errors:
        html_parts.append('<div class="alert alert-warning">')
        html_parts.append('<span class="alert-icon">!</span>')
        html_parts.append("<div><strong>Processing Warnings</strong><br>")
        html_parts.append("<br>".join(errors))
        html_parts.append("</div></div>")

    # Individual stockpile tables
    for stockpile in stockpiles:
        html_parts.append(
            _render_stockpile_table(
                stockpile=stockpile,
                catalog_service=catalog_service,
            )
        )

    # Combined table
    if combined_items:
        html_parts.append(
            _render_combined_table(
                combined_items=combined_items,
                catalog_service=catalog_service,
            )
        )

    return HTMLResponse(
        content="\n".join(html_parts),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


def _render_stockpile_table(
    stockpile: Stockpile,
    catalog_service: CatalogService,
) -> str:
    """Render a stockpile as an HTML table.

    Args:
        stockpile: The stockpile to render.
        catalog_service: Service for getting display names.

    Returns:
        HTML string for the stockpile table.
    """
    rows = []
    for item in stockpile.items:
        display_name = catalog_service.get_display_name(item.code)

        crated_badge = '<span class="crated-badge">Crated</span>' if item.crated else ""
        quantity_str = f"{item.quantity:,}" if item.quantity >= 0 else "?"

        rows.append(f"""
            <tr>
                <td>{html.escape(display_name)}{crated_badge}</td>
                <td class="quantity-cell">{quantity_str}</td>
            </tr>
        """)

    # Note: stockpile.type is a string due to use_enum_values=True in Stockpile model
    stockpile_type = html.escape(stockpile.type) if stockpile.type else "Unknown"
    stockpile_name = html.escape(stockpile.name) if stockpile.name else "Unnamed"

    return f"""
    <div class="card stockpile-section">
        <div class="stockpile-header">
            <span class="stockpile-type">{stockpile_type}</span>
            <span class="stockpile-name">{stockpile_name}</span>
        </div>
        <div class="table-wrapper">
            <table class="stockpile-table">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th class="quantity-cell">Quantity</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
    </div>
    """


def _render_combined_table(
    combined_items: dict[tuple[str, bool], int],
    catalog_service: CatalogService,
) -> str:
    """Render a combined table for multiple stockpiles.

    Args:
        combined_items: Dict mapping (code, crated) to total quantity.
        catalog_service: Service for getting display names.

    Returns:
        HTML string for the combined table.
    """
    # Sort by display name
    sorted_items = sorted(
        combined_items.items(),
        key=lambda x: catalog_service.get_display_name(x[0][0]).lower(),
    )

    rows = []
    for (code, crated), quantity in sorted_items:
        display_name = catalog_service.get_display_name(code)

        crated_badge = '<span class="crated-badge">Crated</span>' if crated else ""

        rows.append(f"""
            <tr>
                <td>{html.escape(display_name)}{crated_badge}</td>
                <td class="quantity-cell">{quantity:,}</td>
            </tr>
        """)

    total_quantity = sum(combined_items.values())

    return f"""
    <div class="card stockpile-section">
        <div class="stockpile-header">
            <span class="stockpile-type combined">Combined</span>
            <span class="stockpile-name">All Stockpiles ({total_quantity:,} total items)</span>
        </div>
        <div class="table-wrapper">
            <table class="stockpile-table">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th class="quantity-cell">Quantity</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
    </div>
    """

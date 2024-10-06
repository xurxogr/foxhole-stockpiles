import logging
import time

import cv2
from fastapi import APIRouter, Request, UploadFile
import numpy

from foxhole_stockpiles.core.config import settings
from foxhole_stockpiles.connectors.backend import BackendConnector
from foxhole_stockpiles.services.ocr import OCR
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem


ocr_router = APIRouter()

@ocr_router.post("/scan_image")
async def __scan_image(image: UploadFile, request: Request):
    logger = logging.getLogger(__name__)
    api_key = request.headers.get('API_KEY')
    if not api_key:
        message = "No api key"
        logger.info(message)
        return { "message": message }

    if image is None:
        message = "No input image"
        logger.info(message)
        return { "message": message }

    bytes_as_np_array = numpy.frombuffer(await image.read(), dtype=numpy.uint8)
    image = cv2.imdecode(buf=bytes_as_np_array, flags=cv2.IMREAD_COLOR)

    ocr = OCR()
    start = time.time()
    stockpile: Stockpile = await ocr.extract_stockpile_from_image(image=image, file_name=api_key[:10])
    end = time.time()

    if not stockpile:
        message = "No stockpile found in the image"
        logger.info(message)
        return { "message": message }

    width  = image.shape[1]
    height = image.shape[0]

    if not stockpile.items:
        logger.info(f"{stockpile.type}:{stockpile.name} ({width}x{height}). Scanned image in {end - start:.2f}. No items found in the image.")
        return { "message": f"{stockpile.name}: No items found in the image" }

    logger.info(f"{stockpile.type}:{stockpile.name} ({width}x{height}). Scanned image in {end - start:.2f}.")

    items = []
    items_no_quantity = []
    item: StockpileItem
    for item in stockpile.items:
        if item.quantity == -1:
            items_no_quantity.append(item.code)

        items.append({ "code": item.code, "quantity": item.quantity, "crated": item.crated})

    stockpile_dict = {
        "stockpile_name": stockpile.name,
        "stockpile_type": stockpile.type,
        "resolution": stockpile.resolution,
        "items": items
    }

    if items_no_quantity:
        items_text = ", ".join(items_no_quantity)
        logger.error(f"{stockpile.name}: Items without quantity: {items_text}")

    url = settings.backend.url
    if url and api_key.lower() != "debug":
        connector = BackendConnector(url=url)
        try:
            return await connector.send_stockpile(payload=stockpile_dict, api_key=api_key)
        except Exception as e:
            message = f"Error sending stockpile {stockpile.name} ({stockpile.type}) to the backend server: {e.__class__.__name__}"
            logger.error(message)
            return { "message": message }

    return stockpile_dict

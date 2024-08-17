import logging

from fastapi import APIRouter
from fastapi import Request
from fastapi import UploadFile

from foxhole_stockpiles.core.config import settings
from foxhole_stockpiles.connectors.hermes import HermesConnector
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
        message = "No imput image"
        logger.info(message)
        return { "message": message }

    import time
    start = time.time()
    ocr = OCR()
    stockpile: Stockpile = await ocr.extract_stockpile_from_buffer(buffer=image, image_prefix=api_key[:10])
    end = time.time()

    if not stockpile:
        message = "No stockpile found in the image"
        logger.info(message)
        return { "message": message }

    text = stockpile.name.replace('_', '').replace('-', '')
    message = f"{stockpile.type}:{stockpile.name}. Scanned image in {end - start}"
    if text != stockpile.name:
        message += f", sent {text} to backend"
        stockpile.name == text

    logger.info(message)

    items = []
    item: StockpileItem
    for item in stockpile.items:
        items.append({ "code": item.code, "quantity": item.quantity, "crated": item.crated})

    stockpile_dict = {
        "stockpile_name": stockpile.name,
        "stockpile_type": stockpile.type,
        "items": items
    }

    url = settings.backend.url
    if url:
        hermes = HermesConnector(url=url)
        return await hermes.send_stockpile_to_hermes(stockpile=stockpile_dict, api_key=api_key)

    return stockpile_dict

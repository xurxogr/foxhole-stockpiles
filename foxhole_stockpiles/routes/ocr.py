import logging

from fastapi import APIRouter
from fastapi import Request
from fastapi import UploadFile

from foxhole_stockpiles.connectors.hermes import HermesConnector
from foxhole_stockpiles.models.singleton.ocr import OCR
from foxhole_stockpiles.models.stockpile import Stockpile


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
    stockpile: Stockpile = await ocr.extract_stockpile_from_buffer(image)
    end = time.time()
    if not stockpile:
        message = "No stockpile found in the image"
        logger.info(message)
        return { "message": message }

    logger.info("{}:{}. Scanned image in {}".format(stockpile.type, stockpile.name, end - start))

    hermes = HermesConnector()
    return await hermes.send_stockpile_to_hermes(stockpile=stockpile, api_key=api_key)

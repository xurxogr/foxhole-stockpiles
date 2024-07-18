import logging

from fastapi import APIRouter
from fastapi import Request
from fastapi import UploadFile

from foxhole_stockpiles.config.settings import Settings
from foxhole_stockpiles.connectors.hermes import HermesConnector
from foxhole_stockpiles.models.singleton.ocr import OCR
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

    if 'ELI' in text:
        data = text.split('ELI')[1]
        town = data[:3]
        number = data[-1:]
        text = "VELI-{}-{}".format(town, number)

    if text != stockpile.name:
        logger.info("{}:{}. Scanned image in {}, sent {} to Hermes".format(stockpile.type, stockpile.name, end - start, text))
        stockpile.name == text
    else:
        logger.info("{}:{}. Scanned image in {}".format(stockpile.type, stockpile.name, end - start))

    items = []
    item: StockpileItem
    for item in stockpile.items:
        items.append({ "code": item.code, "quantity": item.quantity, "crated": item.crated})
    stockpile_dict = {
        "stockpile_name": stockpile.name,
        "stockpile_type": stockpile.type,
        "items": items
    }

    settings = Settings()
    url = settings.get(section=Settings.SECTION_HERMES, option=Settings.OPTION_URL)
    if url:
        hermes = HermesConnector(url=url)
        return await hermes.send_stockpile_to_hermes(stockpile=stockpile, api_key=api_key)

    return stockpile_dict

"""OCR routes."""

import logging
import time

import cv2
import numpy
from fastapi import APIRouter, Request, UploadFile

from foxhole_stockpiles.connectors.backend import BackendConnector
from foxhole_stockpiles.core.config import settings
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.ocr import OCR

ocr_router = APIRouter()


@ocr_router.post("/scan_image")
async def scan_image(image: UploadFile, request: Request) -> dict:
    """Scan an image and extract stockpile information.

    Args:
        image (UploadFile): Image to scan
        request (Request): Request information

    Returns:
        dict: Stockpile information
    """
    logger = logging.getLogger(__name__)
    api_key = request.headers.get("API_KEY")
    if not api_key:
        return await log_and_return(message="No api key")

    if image is None:
        return await log_and_return(message="No input image")

    image = await read_image(image=image)

    ocr = OCR()
    start = time.time()
    stockpile = await ocr.extract_stockpile_from_image(image=image, file_name=api_key[:10])
    end = time.time()

    if not stockpile:
        return await log_and_return(message="No stockpile found in the image")

    width = image.shape[1]
    height = image.shape[0]

    if not stockpile.items:
        return await log_and_return(
            message=f"{stockpile.name}: No items found in the image",
            width=width,
            height=height,
            start=start,
            end=end,
        )

    logger.info(
        "%s:%s (%dx%d). Scanned image in %.2f.",
        stockpile.type,
        stockpile.name,
        width,
        height,
        end - start,
    )

    stockpile_dict = await create_stockpile_dict(stockpile=stockpile)
    return send_stockpile(stockpile=stockpile_dict, api_key=api_key)


async def log_and_return(
    message: str, width: int = None, height: int = None, start: time = None, end: time = None
):
    """Log a message and return it.

    Args:
        message (str): Message to log and return
        width (int, optional): Width of the image. Defaults to None.
        height (int, optional): Height of the image. Defaults to None.
        start (time, optional): Start time. Defaults to None.
        end (time, optional): End time. Defaults to None.

    Returns:
        dict: Message
    """
    logger = logging.getLogger(__name__)
    if width and height and start and end:
        logger.info("%s (%dx%d). Scanned image in %.2f.", message, width, height, end - start)
    else:
        logger.info(message)
    return {"message": message}


async def read_image(image: UploadFile) -> numpy.ndarray:
    """Read an image from an UploadFile.

    Args:
        image (UploadFile): Image to read

    Returns:
        numpy.ndarray: Image as a numpy array
    """
    bytes_as_np_array = numpy.frombuffer(buffer=await image.read(), dtype=numpy.uint8)
    return cv2.imdecode(buf=bytes_as_np_array, flags=cv2.IMREAD_COLOR)


async def create_stockpile_dict(stockpile: Stockpile) -> dict:
    """Create a stockpile dictionary from a Stockpile.

    Args:
        stockpile (Stockpile): Stockpile to convert

    Returns:
        dict: Stockpile dictionary
    """
    items = []
    items_no_quantity = []
    for item in stockpile.items:
        if item.quantity == -1:
            items_no_quantity.append(item.code)

        items.append({"code": item.code, "quantity": item.quantity, "crated": item.crated})

    if items_no_quantity:
        items_text = ", ".join(items_no_quantity)
        logger = logging.getLogger(__name__)
        logger.error("%s: Items without quantity: %s", stockpile.name, items_text)

    return {
        "stockpile_name": stockpile.name,
        "stockpile_type": stockpile.type,
        "resolution": stockpile.resolution,
        "items": items,
    }


async def send_stockpile(stockpile: dict, api_key: str) -> dict:
    """Send a stockpile to the backend server.

    Args:
        stockpile (dict): Stockpile to send
        api_key (str): API key to use for authentication
    """
    url = settings.backend.url
    if not url or api_key.lower() == "debug":
        return stockpile

    connector = BackendConnector(url=url)
    try:
        return await connector.send_stockpile(payload=stockpile, api_key=api_key)
    except Exception as e:
        message = (
            f"Error sending stockpile {stockpile.get('stockpile_name')} "
            f"({stockpile.get('stockpile_type')}) to the backend server: {e.__class__.__name__}"
        )
        logger = logging.getLogger(__name__)
        logger.error(message)
        return {"message": message}

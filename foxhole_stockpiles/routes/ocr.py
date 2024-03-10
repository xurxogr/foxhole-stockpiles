from fastapi import APIRouter
from fastapi import Request
from fastapi import UploadFile

from foxhole_stockpiles.connectors.hermes import HermesConnector
from foxhole_stockpiles.models.singleton.ocr import OCR


ocr_router = APIRouter()

@ocr_router.post("/scan_image")
async def __scan_image(image: UploadFile, request: Request):
    api_key = request.headers.get('API_KEY')
    if not api_key:
        return { "message": "No api key" }

    ocr = OCR()
    stockpile = await ocr.extract_stockpile_from_buffer(image)
    if stockpile:
        hermes = HermesConnector()
        return await hermes.send_stockpile_to_hermes(stockpile=stockpile, api_key=api_key)

    return stockpile

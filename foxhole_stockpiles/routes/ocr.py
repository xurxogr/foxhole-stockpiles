from fastapi import APIRouter
from fastapi import UploadFile

from foxhole_stockpiles.models.singleton.ocr import OCR

ocr_router = APIRouter()

@ocr_router.post("/scan_image")
async def __scan_image(image: UploadFile):
    ocr = OCR()
    stockpile = await ocr.extract_stockpile_from_buffer(image)
    return stockpile

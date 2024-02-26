from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import UploadFile

from foxhole_stockpiles.routes.common import get_current_username
from foxhole_stockpiles.models.singleton.stockpiles import Stockpiles
from foxhole_stockpiles.models.stockpile import Stockpile

ocr_router = APIRouter()

@ocr_router.post("/scan_image", response_model=Stockpile, response_model_exclude_none=True)
async def __scan_image(image: UploadFile, name: str, username: Annotated[str, Depends(get_current_username)]):
    stockpiles = Stockpiles()
    stockpile = await stockpiles.extract_stockpile_from_buffer(image)
    return stockpile

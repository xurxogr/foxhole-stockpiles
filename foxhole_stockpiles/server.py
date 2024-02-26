from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from foxhole_stockpiles.routes.ocr import ocr_router
from foxhole_stockpiles.routes.stockpiles import stockpiles_router
from foxhole_stockpiles.models.singleton.ocr import OCR
from foxhole_stockpiles.models.singleton.stockpiles import Stockpiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize all the singletons before being used by the API
    Stockpiles()
    OCR()
    yield

root_app = FastAPI(lifespan=lifespan)
root_app.include_router(ocr_router, prefix="/ocr")
root_app.include_router(stockpiles_router, prefix="/stockpiles")

if __name__ == '__main__':
    uvicorn.run(root_app, host='0.0.0.0', port=8010, log_level="info")

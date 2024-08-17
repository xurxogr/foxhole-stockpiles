from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from foxhole_stockpiles.core.logging import Logging
from foxhole_stockpiles.services.ocr import OCR
from foxhole_stockpiles.routes.ocr import ocr_router
from foxhole_stockpiles.routes.verification_router import verification_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize all the singletons before being used by the API
    Logging.configure_logging()
    OCR()
    yield

root_app = FastAPI(lifespan=lifespan)
root_app.include_router(ocr_router, prefix="/ocr")
root_app.include_router(verification_router, prefix="/verification")

if __name__ == '__main__':
    uvicorn.run(root_app, host='0.0.0.0', port=8010, log_level="info")

"""Main entry point for the FastAPI server."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from foxhole_stockpiles.core.logging import Logging
from foxhole_stockpiles.routers.ocr import ocr_router
from foxhole_stockpiles.routers.verification_router import verification_router
from foxhole_stockpiles.services.ocr import OCR


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all the singletons before being used by the API."""
    Logging.configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Initializing OCR")
    OCR()
    yield


root_app = FastAPI(lifespan=lifespan)
root_app.include_router(ocr_router, prefix="/ocr")
root_app.include_router(verification_router, prefix="/verification")

if __name__ == "__main__":
    uvicorn.run(root_app, host="0.0.0.0", port=8010, log_level="info")

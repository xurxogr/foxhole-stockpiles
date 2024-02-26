from fastapi import FastAPI
import uvicorn

from foxhole_stockpiles.routes.ocr import ocr_router

root_app = FastAPI()
root_app.include_router(ocr_router, prefix="/ocr")

if __name__ == '__main__':
    uvicorn.run(root_app, host='0.0.0.0', port=8010, log_level="info")

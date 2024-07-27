from fastapi import APIRouter
from fastapi import UploadFile

from foxhole_stockpiles.services.verification_service import VerificationService

verification_router = APIRouter()

@verification_router.post("/verify")
async def upload_pictures(pictures: list[UploadFile]):
    if len(pictures) != 2:
        return {"error": "Please upload exactly two pictures."}
    
    result = [
        await pictures[0].read(),
        await pictures[1].read()
    ]

    service = VerificationService()
    return await service.verify_pictures(result)

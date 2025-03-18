"""Verification router."""

from fastapi import APIRouter, UploadFile

from foxhole_stockpiles.models.verification import Verification
from foxhole_stockpiles.services.verification_service import VerificationService

verification_router = APIRouter()


@verification_router.post("/verify")
async def upload_pictures(pictures: list[UploadFile]) -> dict:
    """Verify the pictures.

    Verify the pictures uploaded by the user. It needs to be exactly two pictures.

    Args:
        pictures (list[UploadFile]): List of pictures to verify

    Returns:
        dict: Verification result
    """
    if len(pictures) != 2:
        return {"error": "Please upload exactly two pictures."}

    result = [await pictures[0].read(), await pictures[1].read()]

    service = VerificationService()
    verification = await service.verify_pictures(result)
    if isinstance(verification, Verification):
        return verification.model_dump()
    return verification

import secrets
from typing import Annotated

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import HTTPBasic
from fastapi.security import HTTPBasicCredentials

from foxhole_stockpiles.config.settings import Settings


security = HTTPBasic()

def get_current_username(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)]
):
    encoding = 'utf-8'
    settings = Settings()
    correct_username_bytes = bytes(settings.get(Settings.SECTION_API, Settings.OPTION_USERNAME), encoding)
    correct_password_bytes = bytes(settings.get(Settings.SECTION_API, Settings.OPTION_PASSWORD), encoding)

    current_username_bytes = credentials.username.encode(encoding)
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )

    current_password_bytes = credentials.password.encode(encoding)
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
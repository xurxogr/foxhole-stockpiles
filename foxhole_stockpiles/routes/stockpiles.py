from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.exceptions import HTTPException

from foxhole_stockpiles.routes.common import get_current_username
from foxhole_stockpiles.models.singleton.stockpiles import Stockpiles
from foxhole_stockpiles.models.stockpile import Stockpile


stockpiles_router = APIRouter()

@stockpiles_router.get("/", response_model=list[Stockpile], response_model_exclude_none=True)
async def get_stockpiles(username: Annotated[str, Depends(get_current_username)]):
    stockpiles = Stockpiles()
    return await stockpiles.get_stockpiles()

@stockpiles_router.post("/", response_model=Stockpile|dict, status_code=status.HTTP_201_CREATED, response_model_exclude_none=True)
async def add_stockpile(stockpile: Stockpile, username: Annotated[str, Depends(get_current_username)]):
    stockpiles = Stockpiles()
    error = await stockpiles.add_stockpile(stockpile=stockpile)

    if error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)

    return await stockpiles.get_stockpile(name=stockpile.name, region=stockpile.region)

@stockpiles_router.get("/{id}", response_model=Stockpile, response_model_exclude_none=True)
async def get_stockpile_by_id(id: str, username: Annotated[str, Depends(get_current_username)]):
    stockpiles = Stockpiles()
    stockpile = await stockpiles.get_stockpile(uid=id)
    if stockpile:
        return stockpile

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stockpile with id '{}' not found".format(id))

@stockpiles_router.get("/{region}/{name}", response_model=Stockpile, response_model_exclude_none=True)
async def get_stockpile_by_name_and_region(name: str, region: str, username: Annotated[str, Depends(get_current_username)]):
    stockpiles = Stockpiles()
    stockpile = await stockpiles.get_stockpile(name=name, region=region)
    if stockpile:
        return stockpile

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stockpile with name '{}' and region '{}' not found".format(name, region))

@stockpiles_router.delete("/{id}")
async def delete_stockpile_by_id(id: str, username: Annotated[str, Depends(get_current_username)]):
    stockpiles = Stockpiles()
    deleted = await stockpiles.del_stockpile(uid=id)
    if deleted:
        return {"message": "Stockpile successfully deleted"}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stockpile with id '{}' not found".format(id))

@stockpiles_router.delete("/{region}/{name}")
async def delete_stockpile_by_name_and_region(name: str, region: str, username: Annotated[str, Depends(get_current_username)]):
    stockpiles = Stockpiles()
    deleted = await stockpiles.del_stockpile(name=name, region=region)
    if deleted:
        return {"message": "Stockpile successfully deleted"}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stockpile with name '{}' and region '{}' not found".format(name, region))

@stockpiles_router.put("/{id}")
async def modify_stockpile_by_id(id: str, stockpile: Stockpile, username: Annotated[str, Depends(get_current_username)]):
    stockpiles = Stockpiles()
    message = await stockpiles.modify_stockpile(stockpile=stockpile, uid=id)
    if message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="id:{}. Error: {}".format(id, message))

    return {"message": "Stockpile successfully modified" }

@stockpiles_router.put("/{region}/{name}")
async def modify_stockpile_by_name_and_region(name: str, region: str, stockpile: Stockpile, username: Annotated[str, Depends(get_current_username)]):
    stockpiles = Stockpiles()
    message = await stockpiles.modify_stockpile(stockpile=stockpile, name=name, region=region)
    if message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="name '{}' and region '{}'. Error: {}".format(name, region, message))

    return {"message": "Stockpile successfully modified" }

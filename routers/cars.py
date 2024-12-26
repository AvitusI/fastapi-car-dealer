from bson import ObjectId

import cloudinary.uploader
from fastapi import (
    APIRouter,
    Body,
    File,
    Form,
    UploadFile,
    Request,
    Response,
    status,
    HTTPException,
    Depends
)
from fastapi.responses import Response
from pymongo import ReturnDocument
import cloudinary
from cloudinary import uploader # noqa: F401

from models import (
    CarModel,
    UpdateCarModel,
    CarCollectionPagination
)
from config import BaseConfig
from authentication import AuthHandler


settings = BaseConfig()

CARS_PER_PAGE = 10

router = APIRouter()

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_SECRET_KEY,
)

auth_handler = AuthHandler()


@router.post(
    "/",
    response_description="Add new car with picture",
    response_model=CarModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False
)
async def add_car_with_picture(
    request: Request,
    brand: str = Form("brand"),
    make: str = Form("make"),
    year: int = Form("year"),
    cm3: int = Form("cm3"),
    km: int = Form("km"),
    price: int = Form("price"),
    picture: UploadFile = File("picture"),
    user: str = Depends(auth_handler.auth_wrapper)
):
    cloudinary_image = cloudinary.uploader.upload(
        picture.file,
        crop="fill",
        width=800
    )

    picture_url = cloudinary_image["url"]

    car = CarModel(
        brand=brand,
        make=make,
        year=year,
        cm3=cm3,
        km=km,
        price=price,
        picture_url=picture_url,
        user_id=user["user_id"]
    )

    cars = request.app.db["cars"]
    document = car.model_dump(by_alias=True, exclude=["id"])
    inserted = await cars.insert_one(document)

    return await cars.find_one({"_id": inserted.inserted_id})


@router.get(
    "/",
    response_description="List all cars, paginated",
    response_model=CarCollectionPagination,
    response_model_by_alias=False,
)
async def list_cars(
    request: Request,
    page: int = 1,
    limit: int = CARS_PER_PAGE,
):
    cars = request.app.db["cars"]

    results = []

    cursor = cars.find().sort("companyName").limit(limit).skip((page - 1) * limit)

    total_documents = await cars.count_documents({})

    has_more = total_documents > limit * page

    async for document in cursor:
        results.append(document)

    return CarCollectionPagination(
        cars=results, 
        page=page,
        has_more=has_more
    ) 


@router.get(
    "/{id}",
    response_description="Get a single car by ID",
    response_model=CarModel,
    response_model_by_alias=False
)
async def show_car(
    id: str,
    request: Request
):
    cars = request.app.db["cars"]

    try:
        id = ObjectId(id)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f"Car {id} not found"
        )
    
    if (car := await cars.find_one({"_id": ObjectId(id)})) is not None:
        return car
    
    raise HTTPException(
        status_code=404,
        detail=f"Car with {id} not found"
    )


@router.put(
    "/{id}",
    response_description="Update car",
    response_model=CarModel,
    response_model_by_alias=False,
)
async def update_car(
    id: str,
    request: Request,
    car: UpdateCarModel = Body(...)
):
    try:
        id = ObjectId(id)
    except Exception:
        raise HTTPException(
            status_code=404, 
            detail=f"Car {id} not found"
        )

    car = {
        k: v
        for k, v in car.model_dump(by_alias=True).items()
        if v is not None and k != "_id"
    }

    cars = request.app.db["cars"]

    if len(car) >= 1:

        update_result = await cars.find_one_and_update(
            {"_id": id},
            {"$set": car},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Car {id} not found"
            )

    # The update is empty, but we should still return the matching car:
    if (existing_car := await cars.find_one({"_id": id})) is not None:
        return existing_car

    raise HTTPException(
        status_code=404, 
        detail=f"Car {id} not found"
    )


@router.delete(
    "/{id}",
    response_description="Delete a car"
)
async def delete_car(
    id: str,
    request: Request,
):
    try:
        id = ObjectId(id)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f"Car {id} not found"
        )
    
    cars = request.app.db["cars"]

    delete_result = await cars.delete_one({"_id": id})

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    
    raise HTTPException(
        status_code=404,
        detail=f"Car with {id} not found"
    )

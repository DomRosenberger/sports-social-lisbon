from datetime import datetime
import os
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from bson import ObjectId
from typing import Optional, List
import motor.motor_asyncio
from app.turnstile import validate


TURNSTILE_SITE_KEY = os.environ["TURNSTILE_SITE_KEY"]

async def not_found_error(request: Request, exc: HTTPException):
    return templates.TemplateResponse('404.html', {'request': request}, status_code=404)


async def internal_error(request: Request, exc: HTTPException):
   return templates.TemplateResponse('500.html', {'request': request}, status_code=500)


templates = Jinja2Templates(directory="templates/")

exception_handlers = {
    404: not_found_error,
    500: internal_error
}


# app = FastAPI(docs_url=None)
app = FastAPI(exception_handlers=exception_handlers)
app.mount("/static", StaticFiles(directory="static"), name="static")
client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
db = client.shorturls


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")



class User(BaseModel):
    username: str
    email: str = None
    full_name: str = None
    disabled: bool = None


class ShortUrlModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    short_url_id: str = Field(...)
    original_url: str = Field(...)
    description: str = Field(...)
    password: str = Field(...)
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "short_url_id": "volleyball",
                "original_url": "https://some-very-long-url.com/",
                "password": "some-password",
            }
        }


class UpdateShortUrlModel(BaseModel):
    short_url_id: Optional[str]
    original_url: Optional[str]
    password: Optional[str]

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "short_url_id": "volleyball",  # Resulting 
                "original_url": "https://some-very-long-url.com/",
                "password": "some-password",
            }
        }


# @app.post("/", response_description="Add new short URL", response_model=ShortUrlModel)
# async def create_shorturl(shorturl: ShortUrlModel = Body(...)):
#     shorturl = jsonable_encoder(shorturl)
#     new_shorturl = await db["shorturls"].insert_one(shorturl)
#     created_shorturl = await db["shorturls"].find_one({"_id": new_shorturl.inserted_id})
#     return JSONResponse(status_code=status.HTTP_201_CREATED, content=created_shorturl)


# @app.get(
#     "/", response_description="Process a short URL", response_model=List[ShortUrlModel]
# )
# async def list_shorturls():
#     shorturls = await db["shorturls"].find().to_list(1000)
#     return shorturls


def chunk_list(iterable, chunk_size):
    for i in range(0, len(iterable), chunk_size):
        yield iterable[i:i + chunk_size]


@app.get(
        "/", response_description="Homepage",
)
async def list_all_short_urls(request: Request):
    shorturls = await db["shorturls"].find().to_list(50)
    chunked_shorturls = chunk_list(shorturls, 3)
    return templates.TemplateResponse('home.html', context={"request": request, "chunked_shorturls": chunked_shorturls})


@app.get(
        "/volleyball-lisbon/", response_description="Show Volleyball page.",
)
async def show_volleyball_page(request: Request):
    return templates.TemplateResponse('volleyball.html', context={"request": request})


@app.get(
        "/hiking-lisbon/", response_description="Show Hiking page.",
)
async def show_hiking_page(request: Request):
    return templates.TemplateResponse('hiking.html', context={"request": request})


@app.get(
        "/whatsapp/", response_description="List all WhatsApp URLs",
)
async def list_whatsapp_groups(request: Request):
    shorturls = await db["shorturls"].find().to_list(50)
    chunked_shorturls = chunk_list(shorturls, 3)
    return templates.TemplateResponse('whatsapp.html', context={"request": request, "chunked_shorturls": chunked_shorturls})


@app.get(
    "/donate", response_description="Shows different ways to donate"
)
async def show_donation_page(request: Request):
    return templates.TemplateResponse('donate.html', context={"request": request})


@app.get(
    "/robots.txt", response_class=PlainTextResponse
)
async def show_robots_txt():
    file_name = "robots.txt"
    file_path = f"static/txt/{file_name}"
    file = open(file_path, "r")
    return PlainTextResponse(file.read())


@app.get(
    "/whatsapp/{short_url_id}", response_description="List a specific short URL form",
)
async def list_shorturls(request: Request, short_url_id: str):
    shorturl = await db["shorturls"].find_one({"short_url_id": short_url_id})
    if not shorturl:
        raise HTTPException(status_code=404, detail=f"URL {short_url_id} not found")
    if shorturl["password"]:
        return templates.TemplateResponse('form.html', context={"request": request, "short_url_id": short_url_id})
    elif shorturl["robot_check"]:
        return templates.TemplateResponse('form_turnstile.html', context={"request": request, "short_url_id": short_url_id, "turnstile_site_key": TURNSTILE_SITE_KEY})
    else:
        return RedirectResponse(shorturl["original_url"], status_code=301)


@app.post(
    "/check/{short_url_id}", response_description="List a specific short URL (after entering password)",
)
async def validate_turnstile(request: Request, short_url_id: str, challenge: str = Form(None)):
    verifyResponse = validate(challenge, user_ip=None)
    if verifyResponse.success:
        shorturl = await db["shorturls"].find_one({"short_url_id": short_url_id})
        return RedirectResponse(shorturl["original_url"], status_code=301)
    else:
        return templates.TemplateResponse('form_turnstile.html', context={"request": request, "short_url_id": short_url_id, "turnstile_site_key": TURNSTILE_SITE_KEY})



@app.post(
    "/whatsapp/{short_url_id}", response_description="List a specific short URL (after entering password)",
)
async def protected_short_url(request: Request, short_url_id: str, password: str = Form(None)):
    if not password:
        return templates.TemplateResponse('form.html', context={"request": request, "error": "Missing password", "short_url_id": short_url_id})

    shorturl = await db["shorturls"].find_one({"short_url_id": short_url_id})
    if not shorturl:
        raise HTTPException(status_code=404, detail=f"URL {short_url_id} not found")

    if password == shorturl["password"]:
        return RedirectResponse(shorturl["original_url"], status_code=301)
    return templates.TemplateResponse('form.html', context={"request": request, "error": "Wrong password", "short_url_id": short_url_id})


@app.get("/{full_path:path}")
async def catch_all(request: Request, full_path: str):
    print(f"full_path {full_path}")
    short_url = await db["shorturls"].find_one({"short_url_id": full_path})
    if not short_url:
        raise HTTPException(status_code=404, detail=f"URL {full_path} not found")
    else:
        full_url = f"/whatsapp/{full_path}"
        response = RedirectResponse(url=full_url, status_code=301)
        return response



# @app.get(
#     "/url/{id}", response_description="Get a single short URL", response_model=ShortUrlModel
# )
# async def show_shorturl(id: str):
#     if (shorturl := await db["shorturls"].find_one({"_id": id})) is not None:
#         return shorturl

#     raise HTTPException(status_code=404, detail=f"short url {id} not found")


# @app.put("/{id}", response_description="Update a short URL", response_model=ShortUrlModel)
# async def update_shorturl(id: str, shorturl: UpdateShortUrlModel = Body(...)):
#     shorturl = {k: v for k, v in shorturl.dict().items() if v is not None}

#     if len(shorturl) >= 1:
#         update_result = await db["shorturls"].update_one({"_id": id}, {"$set": shorturl})

#         if update_result.modified_count == 1:
#             if (
#                 updated_shorturl := await db["shorturls"].find_one({"_id": id})
#             ) is not None:
#                 return updated_shorturl

#     if (existing_shorturl := await db["shorturls"].find_one({"_id": id})) is not None:
#         return existing_shorturl

#     raise HTTPException(status_code=404, detail=f"Short URL {id} not found")


# @app.delete("/{id}", response_description="Delete a short URL")
# async def delete_shorturl(id: str):
#     delete_result = await db["shorturls"].delete_one({"_id": id})

#     if delete_result.deleted_count == 1:
#         return Response(status_code=status.HTTP_204_NO_CONTENT)

#     raise HTTPException(status_code=404, detail=f"Short URL {id} not found")

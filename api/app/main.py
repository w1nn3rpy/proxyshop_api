from fastapi import FastAPI
from contextlib import asynccontextmanager

from api.app.db import init_db
from api.routers import orders, proxies, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(orders.router)
app.include_router(proxies.router)
app.include_router(users.router)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from db.database import init_db
from api import webhook, admin, public


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Amazing Race Admin API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(public.router, prefix="/api", tags=["public"])


@app.get("/")
def root():
    return {"message": "Amazing Race API is running 🏁"}


@app.get("/health")
def health():
    return {"status": "ok"}
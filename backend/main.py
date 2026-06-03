from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# ─── Serve frontend static files ─────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(frontend_path, "static")),
    name="static"
)


@app.get("/")
def admin_dashboard():
    return FileResponse(os.path.join(frontend_path, "templates", "index.html"))


@app.get("/live")
def live_dashboard():
    return FileResponse(os.path.join(frontend_path, "templates", "live.html"))


@app.get("/health")
def health():
    return {"status": "ok"}

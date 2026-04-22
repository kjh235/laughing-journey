from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ffl.config import settings
from ffl.database import engine
from ffl.api.routers import address_lookup, changes, zip_lookup


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="FFL Data Service",
    description="US Federal Firearm License lookup API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(address_lookup.router, prefix="/api/v1", tags=["lookup"])
app.include_router(zip_lookup.router, prefix="/api/v1", tags=["lookup"])
app.include_router(changes.router, prefix="/api/v1", tags=["lookup"])


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


def run() -> None:
    import uvicorn
    uvicorn.run("ffl.api.main:app", host=settings.api_host, port=settings.api_port, reload=True)

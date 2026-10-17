from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import CORS_ORIGINS
from .routers import races, drivers, strategy, simulate
from .services.openf1_client import OpenF1Error

app = FastAPI(title="F1 Strategy Simulator API", version="1.0.0")


@app.exception_handler(OpenF1Error)
async def openf1_error_handler(_request: Request, exc: OpenF1Error):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(races.router)
app.include_router(drivers.router)
app.include_router(strategy.router)
app.include_router(simulate.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

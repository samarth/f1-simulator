from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .routers import races, drivers, telemetry, strategy, simulate

app = FastAPI(title="F1 Simulator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(races.router)
app.include_router(drivers.router)
app.include_router(telemetry.router)
app.include_router(strategy.router)
app.include_router(simulate.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

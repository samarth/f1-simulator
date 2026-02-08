import os

CACHE_DIR = os.environ.get("FASTF1_CACHE_DIR", "./cache")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
MAX_CONCURRENT_LOADS = 2

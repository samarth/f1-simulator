import os

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
OPENF1_BASE_URL = os.environ.get("OPENF1_BASE_URL", "https://api.openf1.org/v1")

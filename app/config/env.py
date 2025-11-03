import os
from dotenv import load_dotenv

load_dotenv()
_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
origins = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

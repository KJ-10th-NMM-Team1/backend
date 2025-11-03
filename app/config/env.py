import os
from dotenv import load_dotenv

load_dotenv()
_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
origins = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

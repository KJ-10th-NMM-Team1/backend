import os
from dotenv import load_dotenv

load_dotenv()
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")

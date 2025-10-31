import os
from dotenv import load_dotenv

class EnvConfig:
    def __init__(self):
        load_dotenv()
        self.origins = os.getenv('DEV_FRONT_ORIGIN', 'http://localhost:5173')
    
    def get_origins(self):
        return self.origins



import os, json
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


def make_db():
    env = os.getenv("APP_ENV", "dev")
    dbname = os.getenv("DB_NAME", "dupilot")

    if env == "dev":
        uri = os.getenv("MONGO_URL_DEV", "mongodb://localhost:27017")
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
    else:
        endpoint = os.environ["DOCDB_ENDPOINT"]
        port = os.getenv("DOCDB_PORT", "27017")
        params = os.getenv("DOCDB_PARAMS", "replicaSet=rs0&retryWrites=false&tls=true")
        ca = os.getenv("DOCDB_CA_PATH", "/etc/ssl/certs/global-bundle.pem")

        user, pwd = os.environ["DOCDB_USER"], os.environ["DOCDB_PASSWORD"]

        uri = f"mongodb://{user}:{pwd}@{endpoint}:{port}/{dbname}?{params}"
        client = AsyncIOMotorClient(uri, tlsCAFile=ca, serverSelectionTimeoutMS=5000)

    return client[dbname]

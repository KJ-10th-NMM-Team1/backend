from fastapi import FastAPI
from api.deps import DbDep

app = FastAPI()


@app.get("/")
async def main(db: DbDep):
    print(db)
    # users = await db["users"].find().to_list(length=10)
    # print(users)

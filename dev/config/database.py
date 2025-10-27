from motor.motor_asyncio import AsyncIOMotorDatabase # 타입 힌트를 위해 임포트
import motor.motor_asyncio

# 1. MongoDB 연결 문자열 (URI)
MONGO_URI = "mongodb://best:absc3513@localhost:27017/"

try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    client.server_info() 
    print("✅ MongoDB 연결에 성공했습니다.")
except Exception as e:
    print(f"❌ MongoDB 연결 실패: {e}")
    client = None

db = client.best

def get_db() -> AsyncIOMotorDatabase:
    return db
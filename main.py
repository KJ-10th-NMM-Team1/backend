from fastapi import FastAPI

# FastAPI 앱 인스턴스 생성
app = FastAPI()

# 루트 경로 ("/")로 GET 요청이 오면 실행될 함수 정의
@app.get("/")
async def read_root():
    # JSON 형태로 응답 반환
    return {"message": "Hello World"}

@app.get("/hello")
def test():
    return {"test": "hello"}



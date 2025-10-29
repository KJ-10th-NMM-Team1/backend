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

# /items/{item_id} 경로로 GET 요청 처리 (경로 파라미터)
@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    # item_id는 경로에서, q는 쿼리 파라미터(?q=somequery)에서 받음
    response = {"item_id": item_id}
    if q:
        response.update({"q": q})
    return response




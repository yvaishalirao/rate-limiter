from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from limiter import check_rate_limit

app = FastAPI()

class RateLimitRequest(BaseModel):
    user_id: str

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/check-rate-limit")
def check(req: RateLimitRequest):
    result = check_rate_limit(req.user_id)
    if not result['allowed']:
        raise HTTPException(status_code=429, detail=result)
    return result
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from limiter import check_rate_limit

logger = logging.getLogger(__name__)

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


@app.exception_handler(RedisConnectionError)
@app.exception_handler(RedisTimeoutError)
async def redis_error_handler(request: Request, exc):
    return JSONResponse(status_code=200, content={'allowed': True, 'remaining': -1})


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    # Never swallow 429 — let FastAPI's built-in HTTPException handler take it
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    # Fail-open only for the rate-limit route (INV-6)
    if request.url.path == '/check-rate-limit':
        logger.error("Unhandled exception on /check-rate-limit: %s", exc, exc_info=True)
        return JSONResponse(status_code=200, content={'allowed': True, 'remaining': -1})
    # All other routes surface as 500 normally
    raise exc
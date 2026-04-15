from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/check-rate-limit")
def check_rate_limit():
    return {"allowed": True, "remaining": -1}
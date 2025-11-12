from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI(title="Dummy REST API", version="0.1.0")

class EchoIn(BaseModel):
    message: str

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/echo")
async def echo(body: EchoIn):
    return {"you_said": body.message}

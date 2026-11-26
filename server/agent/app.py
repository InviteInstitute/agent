"""The FastAPI app: the /v1 routes behind the Turnstile gate, health and the gate's own route."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from agent import db, environments, gate, llm
from agent.api import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    environments.enabled()  # a misspelled ENVIRONMENTS fails the start, not the first request
    llm.client()
    yield
    db.close()


app = FastAPI(title="INVITE agent", lifespan=lifespan)
app.add_middleware(gate.TurnstileGate)
app.include_router(router)


@app.get("/healthz")
def healthz() -> dict:
    with db.pool().connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/v1/ping")
def ping() -> dict:
    """The client calls this on load, so the gate shows its challenge before the student acts."""
    return {"ok": True}


class VerifyRequest(BaseModel):
    token: str


@app.post(gate.VERIFY_PATH)
async def turnstile_verify(body: VerifyRequest, request: Request, response: Response) -> dict:
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    remote_ip = forwarded or (request.client.host if request.client else "")
    if not await gate.verify(body.token, remote_ip):
        raise HTTPException(403, "turnstile verification failed")
    response.set_cookie(
        gate.COOKIE,
        gate.new_cookie(),
        max_age=gate.COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {"ok": True}

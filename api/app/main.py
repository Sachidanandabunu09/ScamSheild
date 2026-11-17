"""HTTP boundary: validate inputs, classify, then count anonymous results."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import joblib
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.inference import check_message
from app.limiter import RateLimiter
from app.url_analyzer import analyze

MODEL_PATH = Path(os.getenv("MODEL_PATH", str(Path(__file__).resolve().parents[1] / "model/model.joblib")))
state = {}
limiter = RateLimiter()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    state["model"] = joblib.load(MODEL_PATH)
    state["metrics"] = json.loads(MODEL_PATH.with_name("metrics.json").read_text(encoding="utf-8"))
    db.init_db()
    yield
    state.clear()
    db.engine.dispose()


app = FastAPI(
    title="ScamShield India",
    version="2.0.0",
    lifespan=lifespan,
    description="Educational risk screening. Scores are not probabilities or proof of safety.",
)
InputText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class MessageIn(BaseModel):
    text: InputText


class UrlIn(BaseModel):
    url: InputText


@app.middleware("http")
async def protect(request: Request, call_next):
    if request.method == "POST":
        host = request.client.host if request.client else "unknown"
        if not limiter.allow(host):
            return JSONResponse(
                {"detail": "Too many checks. Try again in one minute."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_request, _error):
    # Default validation errors echo user input; keep private content out of errors.
    return JSONResponse(
        {"detail": "Provide a message or link containing 3 to 2000 characters."}, status_code=422
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(_request, _error):
    logger.error("Database operation failed")  # Never log query parameters or credentials.
    return JSONResponse({"detail": "Storage is temporarily unavailable. Please try again."}, status_code=503)


@app.get("/health")
def health():
    try:
        db.ping()
        database = "ok"
    except SQLAlchemyError:
        database = "down"
    ready = "model" in state and database == "ok"
    return JSONResponse(
        {"status": "ok" if ready else "unavailable", "model_loaded": "model" in state, "database": database},
        status_code=200 if ready else 503,
    )


@app.get("/model-info")
def model_info():
    return state["metrics"]


@app.post("/check/message")
def message(body: MessageIn):
    result = check_message(state["model"], body.text)
    db.log_check("message", result["verdict"])
    return result


@app.post("/check/url")
def url(body: UrlIn):
    try:
        result = analyze(body.url)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    db.log_check("url", result["verdict"])
    return result


@app.get("/stats")
def stats():
    return db.stats()

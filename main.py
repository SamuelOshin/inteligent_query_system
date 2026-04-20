"""
main.py

App entrypoint. Responsibilities:
  - Register middleware (CORS)
  - Register exception handlers — maps custom exceptions to error_response()
  - Include routers

Exception handler chain:
  AppBaseException subclasses → error_response() with their status_code
  RequestValidationError (FastAPI 422) → error_response(422)
  Exception (catch-all) → error_response(500)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.db.database import create_db_and_tables
from app.routes.profiles import router as profiles_router
from app.utils.exceptions import AppBaseException
from app.utils.responses import error_response


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Profile Intelligence Service"}

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Exception Handlers ───────────────────────────────────────────────────────

@app.exception_handler(AppBaseException)
async def app_exception_handler(request: Request, exc: AppBaseException):
    """
    Catches all custom exceptions raised anywhere in the service layer.
    Maps each to the correct HTTP status code + standard error envelope.
    """
    return error_response(message=exc.message, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Overrides FastAPI's default 422 response format.
    FastAPI's default is {"detail": [...]} — spec requires {"status": "error", "message": "..."}.
    Extracts the first validation error message and returns it cleanly.
    """
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = " → ".join(str(l) for l in first.get("loc", []) if l not in ("body", "query"))
    msg = first.get("msg", "Invalid request").replace("Value error, ", "")
    message = f"{loc}: {msg}" if loc else msg
    return error_response(message=message, status_code=422)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for any unhandled exception — never expose internals."""
    return error_response(message="Internal server error", status_code=500)


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(profiles_router)


@app.get("/health")
def health():
    return {"status": "ok"}

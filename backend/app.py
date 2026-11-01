"""FastAPI entry point for the classroom attendance application."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from classroom import router as classroom_router
from auth import router as auth_router
from bulk_import import router as bulk_router

app = FastAPI(title="Điểm danh lớp học")
app.include_router(auth_router)
app.include_router(bulk_router)
app.include_router(classroom_router)

@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "healthy"}

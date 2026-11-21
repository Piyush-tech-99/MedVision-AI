
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import upload, reports, auth


app = FastAPI(
    title="MedVision AI API",
    description="Academic medical imaging prototype. Demo responses are not diagnoses.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    upload.router,
    prefix="/api",
    tags=["Analysis"]
)

app.include_router(
    reports.router,
    prefix="/api/reports",
    tags=["Reports"]
)

app.include_router(
    auth.router,
    prefix="/api/auth",
    tags=["Authentication"]
)


@app.get("/")
def root():
    return {
        "name": "MedVision AI API",
        "status": "running",
        "mode": "academic-demo"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}

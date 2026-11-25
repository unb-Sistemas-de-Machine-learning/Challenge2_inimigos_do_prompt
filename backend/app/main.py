"""Aplicação FastAPI principal do ErgoAI."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as v1_router

app = FastAPI(
    title="ErgoAI API",
    version="0.1.0",
    description="API de RAG, recomendações ergonômicas e análise de setup do ErgoAI.",
)

allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Verifica a disponibilidade da API."""
    return {"status": "ok"}

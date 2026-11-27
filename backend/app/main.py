"""Aplicação FastAPI principal do ErgoAI."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.routes import router as v1_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="ErgoAI API",
    version="0.1.0",
    description=(
        "API de RAG e recomendações ergonômicas do ErgoAI. "
        "Processamento de vídeo da webcam permanece 100% local no navegador (RNF02)."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_https_and_security_headers(request: Request, call_next):
    """Exige HTTPS em produção (RNF03) respeitando X-Forwarded-Proto e adiciona headers de segurança."""
    runtime_settings = get_settings()
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip().lower()

    if runtime_settings.https_required and proto != "https":
        https_url = request.url.replace(scheme="https")
        return RedirectResponse(url=str(https_url), status_code=307)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Webcam-Processing"] = "local-only"
    if runtime_settings.https_required:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(v1_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Verifica a disponibilidade da API."""
    return {"status": "ok"}

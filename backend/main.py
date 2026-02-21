from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from elasticsearch import Elasticsearch
import requests

from config import settings
from routers import chat, index

app = FastAPI(
    title="GKG OSINT Chatbot API",
    version="1.0.0",
    description="Natural language query interface for the GDELT GKG Elasticsearch index",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://frontend:8501", "http://localhost:8501"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1")
app.include_router(index.router, prefix="/api/v1")


# -------------------------
# Health Check Helpers
# -------------------------

def _check_elasticsearch() -> bool:
    try:
        es = Elasticsearch(
            settings.es_host,
            basic_auth=(settings.es_username, settings.es_password),
            verify_certs=settings.es_verify_ssl,
            request_timeout=5,
        )
        return bool(es.ping())
    except Exception:
        return False


def _check_llm() -> bool:
    try:
        r = requests.get(
            f"{settings.llm_base_url}/models",
            timeout=5,
        )
        return r.status_code == 200
    except Exception:
        return False


def _check_chromadb() -> bool:
    try:
        r = requests.get(
            f"http://{settings.chroma_host}:{settings.chroma_port}/api/v2/heartbeat",
            timeout=5,
        )
        return r.status_code == 200
    except Exception:
        return False


# -------------------------
# Health Endpoint
# -------------------------

@app.get("/health")
def health_check():
    es_ok = _check_elasticsearch()
    llm_ok = _check_llm()
    chroma_ok = _check_chromadb()

    overall_ok = es_ok and llm_ok and chroma_ok

    return {
        "status": "ok" if overall_ok else "degraded",
        "elasticsearch": es_ok,
        "llm": llm_ok,
        "chromadb": chroma_ok,
    }
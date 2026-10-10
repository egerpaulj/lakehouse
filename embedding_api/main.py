"""Embedding API: takes text, returns BGE-M3 dense and sparse embeddings (one pass).

POST /embed {"texts": ["..."]} -> {"model": "...", "dimension": 1024, "embeddings": [[...]],
                                       "sparse_embeddings": [{"token_id": weight}]}
GET  /health
The model is loaded once at startup from a persistent cache (downloaded on first start only).
"""

import os
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from embeddings import BGEM3Embedder

MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
CACHE_DIR = os.environ.get("EMBEDDING_CACHE_DIR", "/models")
MAX_TEXTS = int(os.environ.get("EMBEDDING_MAX_TEXTS", "64"))

state = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    state["embedder"] = BGEM3Embedder(MODEL_NAME, cache_dir=CACHE_DIR)
    yield
    state.clear()


app = FastAPI(title="Embedding API", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: List[str] = Field(min_length=1)


class EmbedResponse(BaseModel):
    model: str
    dimension: int
    embeddings: List[List[float]]
    sparse_embeddings: List[Dict[str, float]]


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest):
    if len(request.texts) > MAX_TEXTS:
        raise HTTPException(413, f"At most {MAX_TEXTS} texts per request")
    vectors, sparse = state["embedder"].encode(request.texts)
    return EmbedResponse(
        model=MODEL_NAME,
        dimension=len(vectors[0]) if vectors else 0,
        embeddings=vectors,
        sparse_embeddings=sparse,
    )

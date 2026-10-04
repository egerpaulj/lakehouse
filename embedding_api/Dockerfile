FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY embedding_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the model into the image: downloaded once at build time (cached layer),
# so container starts never download it. Placed before the app code so code
# changes do not invalidate this layer.
ARG EMBEDDING_MODEL=BAAI/bge-m3
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL} \
    EMBEDDING_CACHE_DIR=/models
COPY embedding_api/embeddings.py .
RUN python -c "import os; from embeddings import resolve_model_path; resolve_model_path(os.environ['EMBEDDING_MODEL'], os.environ['EMBEDDING_CACHE_DIR'])"

COPY embedding_api/main.py .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

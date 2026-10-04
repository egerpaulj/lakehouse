"""BGE-M3 embedder.

Adapted from BGEM3Embedder in
https://github.com/egerpaulj/vespa_eval_framework/blob/main/src/embeddings.py
with a one-time model download into a persistent directory.
"""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-m3"


# Skip the duplicate ONNX / non-PyTorch weights to keep the one-time download small.
ALLOW_PATTERNS = ["*.json", "*.model", "*.txt", "*.py", "pytorch_model.bin", "*.pt"]


def resolve_model_path(model_name: str, cache_dir: str) -> str:
    """Return a local model directory, downloading it only if not already stored.

    A ``.complete`` marker is written after a successful download, so an
    interrupted download is resumed on the next start instead of being used.
    """
    from huggingface_hub import snapshot_download

    model_dir = os.path.join(cache_dir, model_name.replace("/", "--"))
    marker = os.path.join(model_dir, ".complete")
    if os.path.exists(marker):
        logger.info("Using cached model at %s", model_dir)
        return model_dir

    logger.info("Downloading %s into %s (one-time)", model_name, model_dir)
    snapshot_download(model_name, local_dir=model_dir, allow_patterns=ALLOW_PATTERNS)
    open(marker, "w").close()
    return model_dir


class BGEM3Embedder:
    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: str | None = None):
        from FlagEmbedding import BGEM3FlagModel

        if cache_dir:
            model_name = resolve_model_path(model_name, cache_dir)
        self.model = BGEM3FlagModel(model_name)
        self.provider = "flag"

    def encode(self, texts: List[str]) -> List[List[float]]:
        vector_data = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )["dense_vecs"]
        return [vec.tolist() for vec in vector_data]

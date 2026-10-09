"""Embedding provider boundary (TECHNICAL-DESIGN D46).

The retrieval engine depends only on ``EmbeddingClient``. Providers:

- ``local-sentence-transformers`` — DEFAULT BASELINE. ``BAAI/bge-m3`` (dense,
  1024 dims), pinned Hugging Face revision, runs fully locally (Apple MPS or
  CPU); no API key. Owner decision replacing the earlier OpenAI baseline.
- ``openai`` — optional. ``text-embedding-3-large`` (3072 dims); the API key is
  read from the environment variable named in the config and never stored.

Configurations are compared through ``EmbeddingConfig``; the cache is keyed by
provider, model, revision and dimensions, so vectors never mix.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str = "openai"
    model: str = "text-embedding-3-large"
    dimensions: int = 3072
    revision: str | None = None  # model weights revision (local models); part of the identity
    api_key_env: str = "OPENAI_API_KEY"
    endpoint: str = "https://api.openai.com/v1/embeddings"
    batch_size: int = 64
    timeout_s: float = 60.0
    max_retries: int = 3

    @property
    def identity(self) -> str:
        """Stable identity used to separate caches of different models/configurations."""
        return f"{self.provider}:{self.model}:{self.revision or '-'}:{self.dimensions}"

    def public_dict(self) -> dict:
        """Config safe to write into traces (no secrets; the key itself is never held here)."""
        return {"provider": self.provider, "model": self.model, "revision": self.revision, "dimensions": self.dimensions}


OPENAI_EMBEDDING_CONFIG = EmbeddingConfig()

LOCAL_EMBEDDING_CONFIG = EmbeddingConfig(
    provider="local-sentence-transformers",
    model="BAAI/bge-m3",
    dimensions=1024,
    revision="5617a9f61b028005a4858fdac845db406aefb181",
    api_key_env="",
    endpoint="",
    batch_size=16,
)

BASELINE_EMBEDDING_CONFIG = LOCAL_EMBEDDING_CONFIG


class EmbeddingUnavailable(RuntimeError):
    """Raised when a real provider cannot be used (e.g. no API key)."""


@runtime_checkable
class EmbeddingClient(Protocol):
    config: EmbeddingConfig
    #: True only for test doubles. Benchmark runs refuse to record results from fakes.
    is_fake: bool

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an array of shape (len(texts), config.dimensions)."""
        ...


class OpenAIEmbeddingClient:
    is_fake = False

    def __init__(self, config: EmbeddingConfig = OPENAI_EMBEDDING_CONFIG):
        self.config = config
        if not os.environ.get(config.api_key_env):
            raise EmbeddingUnavailable(f"environment variable {config.api_key_env} is not set")

    def _post(self, texts: list[str]) -> list[list[float]]:
        body = json.dumps(
            {"model": self.config.model, "input": texts, "dimensions": self.config.dimensions}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.config.endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ[self.config.api_key_env]}",
            },
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_s) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                data = sorted(payload["data"], key=lambda d: d["index"])
                return [d["embedding"] for d in data]
            except (urllib.error.URLError, TimeoutError) as exc:  # retry transient failures
                last_error = exc
                time.sleep(2**attempt)
        raise EmbeddingUnavailable(f"embedding request failed: {last_error}")

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.config.batch_size):
            vectors.extend(self._post(texts[start : start + self.config.batch_size]))
        array = np.asarray(vectors, dtype=np.float32)
        if array.shape != (len(texts), self.config.dimensions):
            raise EmbeddingUnavailable(f"unexpected embedding shape {array.shape}")
        return array


class LocalSentenceTransformerClient:
    """Local embeddings via sentence-transformers (dense vectors, L2-normalised).

    Loads the pinned revision from the local Hugging Face cache; the first use
    downloads it once. Cosine ranking does not depend on the normalisation.
    """

    is_fake = False

    def __init__(self, config: EmbeddingConfig = LOCAL_EMBEDDING_CONFIG, device: str | None = None):
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise EmbeddingUnavailable("install sentence-transformers and torch for the local provider") from exc
        self.config = config
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        try:
            self._model = SentenceTransformer(config.model, revision=config.revision, device=self.device)
        except Exception as exc:  # pragma: no cover - environment dependent
            raise EmbeddingUnavailable(f"cannot load local model {config.model}@{config.revision}: {exc}") from exc
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        dim = get_dim()
        if dim != config.dimensions:
            raise EmbeddingUnavailable(f"{config.model} produces {dim} dims, config says {config.dimensions}")

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.config.dimensions), dtype=np.float32)
        array = self._model.encode(
            texts, batch_size=self.config.batch_size, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        ).astype(np.float32)
        if array.shape != (len(texts), self.config.dimensions):
            raise EmbeddingUnavailable(f"unexpected embedding shape {array.shape}")
        return array


def make_client(config: EmbeddingConfig = BASELINE_EMBEDDING_CONFIG) -> EmbeddingClient:
    if config.provider == "local-sentence-transformers":
        return LocalSentenceTransformerClient(config)
    if config.provider == "openai":
        return OpenAIEmbeddingClient(config)
    raise ValueError(f"unknown embedding provider {config.provider!r}")

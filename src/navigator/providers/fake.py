"""Deterministic test double for ``EmbeddingClient``. TESTS ONLY.

Vectors are derived from token hashes (a bag-of-words projection), so texts that
share words get positive cosine similarity — enough to exercise ranking code.
They carry no semantic meaning. ``is_fake = True`` makes benchmark runs refuse
to record results produced with this client.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from navigator.providers.embeddings import EmbeddingConfig

FAKE_CONFIG = EmbeddingConfig(provider="fake", model="fake-hash-bow", dimensions=64, api_key_env="UNUSED")


class FakeEmbeddingClient:
    is_fake = True

    def __init__(self, config: EmbeddingConfig = FAKE_CONFIG):
        self.config = config
        self.calls: list[list[str]] = []

    def _vector(self, text: str) -> np.ndarray:
        v = np.zeros(self.config.dimensions, dtype=np.float32)
        for token in re.findall(r"\w+", text.lower()):
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            v[h % self.config.dimensions] += 1.0 if (h >> 8) % 2 else -1.0
        return v

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        return np.stack([self._vector(t) for t in texts]) if texts else np.zeros((0, self.config.dimensions), np.float32)

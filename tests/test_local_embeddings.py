"""Local embedding provider (BAAI/bge-m3). No network, no API key."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from navigator.embeddings.cache import EmbeddingCache, cache_dir
from navigator.providers.embeddings import (
    BASELINE_EMBEDDING_CONFIG,
    LOCAL_EMBEDDING_CONFIG,
    OPENAI_EMBEDDING_CONFIG,
    EmbeddingClient,
    LocalSentenceTransformerClient,
    make_client,
)
from navigator.representations.meaning import Representation

HF_SNAPSHOT = (
    Path.home()
    / ".cache/huggingface/hub/models--BAAI--bge-m3/snapshots"
    / LOCAL_EMBEDDING_CONFIG.revision
    / "pytorch_model.bin"
)
needs_local_model = pytest.mark.skipif(not HF_SNAPSHOT.exists(), reason="bge-m3 weights not in local HF cache")


def test_default_baseline_is_local_and_keyless():
    assert BASELINE_EMBEDDING_CONFIG is LOCAL_EMBEDDING_CONFIG
    cfg = BASELINE_EMBEDDING_CONFIG
    assert (cfg.provider, cfg.model, cfg.dimensions) == ("local-sentence-transformers", "BAAI/bge-m3", 1024)
    assert cfg.revision and len(cfg.revision) == 40
    assert cfg.api_key_env == "" and cfg.endpoint == ""


def test_identity_and_cache_separate_models_and_revisions(tmp_path):
    assert LOCAL_EMBEDDING_CONFIG.identity != OPENAI_EMBEDDING_CONFIG.identity
    other_rev = replace(LOCAL_EMBEDDING_CONFIG, revision="0" * 40)
    dirs = {cache_dir(tmp_path, c, "meaning-cards") for c in (LOCAL_EMBEDDING_CONFIG, OPENAI_EMBEDDING_CONFIG, other_rev)}
    assert len(dirs) == 3
    assert LOCAL_EMBEDDING_CONFIG.public_dict()["revision"] == LOCAL_EMBEDDING_CONFIG.revision


def test_cache_ignores_index_written_for_another_revision(tmp_path):
    class Stub:
        is_fake = False

        def __init__(self, config):
            self.config = config

        def embed(self, texts):
            return np.ones((len(texts), self.config.dimensions), dtype=np.float32)

    rep = Representation("C0001", "v1", "текст")
    a = replace(LOCAL_EMBEDDING_CONFIG, dimensions=8)
    EmbeddingCache(tmp_path, a, "x").embed([rep], Stub(a))
    b = replace(a, revision="1" * 40)
    assert EmbeddingCache(tmp_path, b, "x").get(rep) is None


def test_make_client_dispatch_unknown_provider():
    with pytest.raises(ValueError):
        make_client(replace(LOCAL_EMBEDDING_CONFIG, provider="nope"))


@needs_local_model
def test_local_client_embeds_russian_semantically(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    client = LocalSentenceTransformerClient()
    assert isinstance(client, EmbeddingClient) and client.is_fake is False
    v = client.embed(
        [
            "Имею ли я право выбрать собственную жизнь?",
            "Может ли человек выбрать свой путь, если это ранит близких?",
            "Сколько стоит проезд в метро?",
        ]
    )
    assert v.shape == (3, 1024) and np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-3)
    assert float(v[0] @ v[1]) > float(v[0] @ v[2])
    again = client.embed(["Имею ли я право выбрать собственную жизнь?"])
    assert np.allclose(again[0], v[0], atol=1e-4)
    assert client.embed([]).shape == (0, 1024)

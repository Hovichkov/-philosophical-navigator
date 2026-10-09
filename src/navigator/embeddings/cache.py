"""Local, rebuildable embedding cache (TECHNICAL-DESIGN D43).

Layout: ``<root>/<provider>__<model>__<revision>__<dimensions>/<namespace>/``
with ``index.json`` (entry metadata) and ``vectors.npy`` (float32 matrix).

Entry identity = (key, representation version, sha256 of the exact text) inside a
directory that is itself keyed by (provider, model, weights revision, dimensions). Therefore:
- a changed representation text or version never reuses an old vector;
- vectors of different models/configurations are never mixed.

The cache is a derived artifact: delete it and rebuild with
``navigator embed-meaning-cards``. It never contains secrets.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from navigator.providers.embeddings import EmbeddingClient, EmbeddingConfig
from navigator.representations.meaning import Representation

DEFAULT_CACHE_ROOT = Path("data/retrieval/embeddings")
CACHE_FORMAT = "embedding-cache/1.0"


def _safe(part: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", part)


def cache_dir(root: Path, config: EmbeddingConfig, namespace: str) -> Path:
    revision = _safe(config.revision[:12]) if config.revision else "norev"
    return root / f"{_safe(config.provider)}__{_safe(config.model)}__{revision}__{config.dimensions}" / _safe(namespace)


def entry_id(rep: Representation) -> str:
    return f"{rep.key}|{rep.version}|{rep.sha256}"


class EmbeddingCache:
    def __init__(self, root: Path, config: EmbeddingConfig, namespace: str):
        self.config = config
        self.dir = cache_dir(root, config, namespace)
        self.namespace = namespace
        self._entries: dict[str, dict] = {}
        self._vectors = np.zeros((0, config.dimensions), dtype=np.float32)
        self._load()

    def _load(self) -> None:
        index_path, vectors_path = self.dir / "index.json", self.dir / "vectors.npy"
        if not index_path.exists() or not vectors_path.exists():
            return
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if index.get("config") != self.config.public_dict() or index.get("format") != CACHE_FORMAT:
            return  # foreign or outdated cache: ignore, never mix
        vectors = np.load(vectors_path)
        if vectors.shape[1:] != (self.config.dimensions,):
            return
        self._entries = {e["entry_id"]: e for e in index["entries"]}
        self._vectors = vectors

    def get(self, rep: Representation) -> np.ndarray | None:
        e = self._entries.get(entry_id(rep))
        return None if e is None else self._vectors[e["row"]]

    def embed(self, reps: list[Representation], client: EmbeddingClient, persist: bool = True) -> np.ndarray:
        """Vectors aligned with ``reps``; only missing or invalidated entries are embedded."""
        if client.config.public_dict() != self.config.public_dict():
            raise ValueError("client configuration differs from cache configuration")
        missing = [r for r in reps if entry_id(r) not in self._entries]
        if missing:
            new = client.embed([r.text for r in missing])
            # drop superseded entries (same key and version, different text)
            stale = {k for r in missing for k, e in self._entries.items() if e["key"] == r.key and e["version"] == r.version}
            keep = [e for k, e in self._entries.items() if k not in stale]
            rows = [self._vectors[e["row"]] for e in keep] + list(new)
            entries = [dict(e, row=i) for i, e in enumerate(keep)]
            entries += [
                {"entry_id": entry_id(r), "key": r.key, "version": r.version, "text_sha256": r.sha256, "row": len(keep) + i}
                for i, r in enumerate(missing)
            ]
            self._entries = {e["entry_id"]: e for e in entries}
            self._vectors = np.asarray(rows, dtype=np.float32).reshape(len(rows), self.config.dimensions)
            if persist:
                self.save()
        return np.stack([self.get(r) for r in reps]) if reps else np.zeros((0, self.config.dimensions), np.float32)

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        np.save(self.dir / "vectors.npy", self._vectors)
        index = {
            "format": CACHE_FORMAT,
            "namespace": self.namespace,
            "config": self.config.public_dict(),
            "entries": sorted(self._entries.values(), key=lambda e: e["row"]),
        }
        (self.dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

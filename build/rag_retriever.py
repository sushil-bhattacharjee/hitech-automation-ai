"""
RAG Retriever — query the local Chroma vector DB built by rag_builder.py.

Used by main.py's /api/chat endpoint to fetch relevant chunks before calling
the LLM, so the model gets grounded context instead of relying on training memory.

v1.3.2 change: vector_db lives OUTSIDE build/ now. The auto-migration in
_resolve_db_path() moves an old in-build vector_db to the new location on
first run, so users upgrading from earlier versions don't lose their work.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import chromadb
import httpx

log = logging.getLogger("rag")


OLLAMA_URL     = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
EMBED_MODEL    = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")
COLLECTION_NAME = "netconf_corpus"


def _resolve_db_path() -> Path:
    """Resolve where the vector DB lives.

    v1.3.2: vector_db now lives OUTSIDE build/ to survive code upgrades.

    Resolution order:
      1. RAG_DB_PATH env var (explicit override)
      2. Sibling of build/ → ../vector_db/ (new default)

    If the OLD location (build/vector_db/) has data but the NEW location is
    empty, auto-migrate it.
    """
    env = os.environ.get("RAG_DB_PATH")
    if env:
        return Path(env).expanduser().resolve()

    new_path = (Path(__file__).parent.parent / "vector_db").resolve()
    old_path = (Path(__file__).parent / "vector_db").resolve()

    # Auto-migrate: if user has data at the old in-build location but nothing
    # at the new sibling location, move it. Done once, idempotent.
    if old_path != new_path and old_path.exists() and not new_path.exists():
        try:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_path), str(new_path))
            log.info("Migrated vector_db: %s → %s", old_path, new_path)
            print(f"🚚 RAG: migrated vector_db from {old_path} to {new_path}")
        except Exception as e:
            log.warning("vector_db migration failed: %s. Will use old path.", e)
            return old_path

    return new_path


DEFAULT_DB = _resolve_db_path()

# Singleton — but the failure case is NOT cached, so a later rebuild is detected
_collection = None


def _get_collection():
    """Open the Chroma collection. Cache on success; re-check on failure."""
    global _collection
    if _collection is not None:
        return _collection
    if not DEFAULT_DB.exists():
        return None
    try:
        client = chromadb.PersistentClient(path=str(DEFAULT_DB))
        _collection = client.get_collection(name=COLLECTION_NAME)
        log.info("RAG opened collection '%s' at %s", COLLECTION_NAME, DEFAULT_DB)
        return _collection
    except Exception as e:
        log.warning("RAG could not open collection at %s: %s", DEFAULT_DB, e)
        return None


def rag_available() -> bool:
    """Quick check: is the RAG DB built and reachable?"""
    return _get_collection() is not None


def reset_cache() -> None:
    """Clear the singleton so the next call re-opens the DB.

    Useful if rag_builder.py was just run and you want main.py to pick up
    the new collection without a service restart.
    """
    global _collection
    _collection = None


def rag_db_path() -> str:
    """Return the resolved DB path (used by /api/chat-config so the UI can show it)."""
    return str(DEFAULT_DB)


def rag_chunk_count() -> int:
    """Number of chunks in the collection right now. 0 if not built."""
    coll = _get_collection()
    if coll is None:
        return 0
    try:
        return coll.count()
    except Exception:
        return 0


# Public site: embeddings in-process (fastembed), no Ollama. The index must be
# built with the same model — see rag_build_local.py.
EMBED_BACKEND = os.environ.get("EMBED_BACKEND", "ollama")
LOCAL_EMBED_MODEL = os.environ.get("LOCAL_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
_local_model = None


def local_embed(texts: list[str], query: bool = True) -> list[list[float]]:
    global _local_model
    if _local_model is None:
        from fastembed import TextEmbedding
        _local_model = TextEmbedding(model_name=LOCAL_EMBED_MODEL)
    # small batches: memory grows with batch x sequence length (256 x 512 tokens
    # was killed with 4 GB)
    it = (_local_model.query_embed(texts, batch_size=8) if query
          else _local_model.passage_embed(texts, batch_size=8))
    return [list(map(float, v)) for v in it]


async def embed_query(text: str) -> Optional[list[float]]:
    if EMBED_BACKEND == "fastembed":
        try:
            import asyncio
            return (await asyncio.to_thread(local_embed, [text]))[0]
        except Exception as e:
            log.warning("local embedding failed: %s", e)
            return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
            )
            r.raise_for_status()
            return r.json()["embedding"]
    except Exception:
        return None


async def retrieve(query: str, k: int = 5) -> list[dict]:
    """Return the top-k most relevant chunks for the query."""
    coll = _get_collection()
    if coll is None:
        return []
    emb = await embed_query(query)
    if emb is None:
        return []
    try:
        results = coll.query(
            query_embeddings=[emb],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    out: list[dict] = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        out.append({
            "text": doc,
            "source": meta.get("source", "unknown"),
            "section": meta.get("section", ""),
            "distance": float(dist),
        })
    return out


def format_for_prompt(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(
            f"--- Reference {i} (from {c['source']}, section: {c['section']}) ---\n"
            f"{c['text']}\n"
        )
    return (
        "The following reference material was retrieved from the user's own "
        "documentation and working code. Use it as authoritative grounding when "
        "answering. Cite the source filename in your response.\n\n"
        + "\n".join(parts)
    )

"""
RAG vector DB builder — v1.3.1

Reads markdown files under a corpus directory, chunks them, generates
embeddings via local Ollama (nomic-embed-text), and stores them in a
persistent ChromaDB.

v1.3.1 improvements:
  - Resume capability: skip files already fully indexed (preserves partial work)
  - Configurable HTTP timeout (300s default, was 60s — copes with model swaps)
  - Retry with exponential backoff on transient timeouts
  - Pre-warm the embedding model so the first chunk doesn't trigger a slow load
  - --rebuild flag to force a full wipe (old behavior)
  - --verbose flag for diagnostic output

Usage:
  python rag_builder.py                  # incremental — only process new/changed files
  python rag_builder.py --rebuild        # wipe collection and rebuild everything
  python rag_builder.py --corpus PATH    # override default corpus path
  python rag_builder.py --db PATH        # override default vector DB path
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import chromadb
import httpx

# ----------------------------- config ----------------------------- #

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")
COLLECTION_NAME = "netconf_corpus"
DEFAULT_CORPUS = Path("~/DevnetExpert/mock3/software_ai/rag-corpus").expanduser()


def _resolve_db_path() -> Path:
    """Resolve where the vector DB lives.

    v1.3.2: vector_db now lives OUTSIDE build/, so it survives code upgrades.
    Resolution order:
      1. RAG_DB_PATH env var (explicit override)
      2. Sibling of build/ → ../vector_db/ (new default)
      3. Old location inside build/ if it still exists (auto-migration trigger)
    """
    env = os.environ.get("RAG_DB_PATH")
    if env:
        return Path(env).expanduser().resolve()
    # Default: sibling of build/ — build/ is __file__.parent, so go up one
    return (Path(__file__).parent.parent / "vector_db").resolve()


DEFAULT_DB = _resolve_db_path()

# v1.3.1: timeout + retry config
EMBED_TIMEOUT_S = 300.0          # was 60s in 1.3.0
EMBED_MAX_RETRIES = 3
EMBED_BACKOFF_BASE_S = 2.0

# Chunking config
MAX_CHARS_PER_CHUNK = 1500
OVERLAP_CHARS = 200


# ----------------------------- chunking ----------------------------- #

def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split markdown by headings then by length. Returns list of {id, text, meta}."""
    chunks = []
    # Split on H1/H2/H3 headings; keep heading with its block
    sections = re.split(r"\n(?=#{1,3}\s)", text)
    counter = 0
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # Further split long sections
        if len(section) <= MAX_CHARS_PER_CHUNK:
            counter += 1
            chunks.append({
                "id": f"{source}::{counter:04d}",
                "text": section,
                "meta": {"source": source, "chunk_index": counter},
            })
        else:
            start = 0
            while start < len(section):
                end = min(start + MAX_CHARS_PER_CHUNK, len(section))
                counter += 1
                chunks.append({
                    "id": f"{source}::{counter:04d}",
                    "text": section[start:end],
                    "meta": {"source": source, "chunk_index": counter},
                })
                start = end - OVERLAP_CHARS if end < len(section) else end
    return chunks


# ----------------------------- embeddings ----------------------------- #

def get_embedding(client: httpx.Client, text: str, verbose: bool = False) -> list[float]:
    """One embedding call with retry-with-backoff on transient failures."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, EMBED_MAX_RETRIES + 1):
        try:
            r = client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=EMBED_TIMEOUT_S,
            )
            r.raise_for_status()
            return r.json()["embedding"]
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_exc = e
            if attempt < EMBED_MAX_RETRIES:
                backoff = EMBED_BACKOFF_BASE_S * (2 ** (attempt - 1))
                if verbose:
                    print(f"      ⚠️  transient error: {type(e).__name__}. "
                          f"Retry {attempt}/{EMBED_MAX_RETRIES - 1} after {backoff}s …")
                time.sleep(backoff)
                continue
            raise
        except httpx.HTTPStatusError as e:
            # 4xx/5xx — usually a real error (model missing, etc.), don't retry
            raise RuntimeError(
                f"Ollama returned {e.response.status_code} for embedding call: "
                f"{e.response.text[:200]}"
            )
    # Exhausted retries
    raise RuntimeError(f"Embedding failed after {EMBED_MAX_RETRIES} attempts: {last_exc}")


def embed_batch(client: httpx.Client, texts: list[str], verbose: bool = False) -> list[list[float]]:
    """Sequential embed; Ollama's /api/embeddings is single-prompt only."""
    return [get_embedding(client, t, verbose) for t in texts]


def prewarm_embed_model(client: httpx.Client) -> None:
    """One throwaway call so subsequent chunks don't trigger model load delays."""
    try:
        client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": "warmup"},
            timeout=EMBED_TIMEOUT_S,
        )
    except Exception as e:
        print(f"   ⚠️  Pre-warm of {EMBED_MODEL} failed: {e}")
        print(f"      Continuing anyway — first real chunk may be slow.")


# ----------------------------- resume helpers (v1.3.1) ----------------------------- #

def get_existing_ids(collection) -> set[str]:
    """Fetch all chunk IDs currently in the collection."""
    try:
        all_data = collection.get(include=[])
        return set(all_data.get("ids", []))
    except Exception:
        return set()


def file_chunks_already_present(file_path: Path, existing_ids: set[str], text: str) -> bool:
    """Return True if EVERY chunk this file would produce is already in the DB."""
    chunks = chunk_markdown(text, source=file_path.name)
    if not chunks:
        return False
    chunk_ids = [c["id"] for c in chunks]
    return all(cid in existing_ids for cid in chunk_ids)


def clean_partial_file_chunks(collection, file_name: str, existing_ids: set[str]) -> int:
    """Remove any orphan chunks belonging to a partially-indexed file."""
    prefix = f"{file_name}::"
    to_delete = [cid for cid in existing_ids if cid.startswith(prefix)]
    if to_delete:
        try:
            collection.delete(ids=to_delete)
            return len(to_delete)
        except Exception:
            return 0
    return 0


# ----------------------------- main build ----------------------------- #

def build(corpus_dir: Path, db_dir: Path, rebuild: bool = False, verbose: bool = False) -> None:
    md_files = sorted(corpus_dir.rglob("*.md"))
    if not md_files:
        sys.exit(f"❌ No .md files found in {corpus_dir}")

    print(f"📂 Corpus    : {corpus_dir}")
    print(f"💾 Vector DB : {db_dir}")
    print(f"🧠 Embedder  : {EMBED_MODEL} via {OLLAMA_URL}")
    print(f"📄 Files     : {len(md_files)} markdown files")
    print(f"🔁 Mode      : {'REBUILD (full wipe)' if rebuild else 'INCREMENTAL (resume)'}")
    print()

    # Verify Ollama is reachable and the embedding model is available
    print("🔍 Checking Ollama and embedding model …")
    try:
        with httpx.Client() as c:
            r = c.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            if not any(EMBED_MODEL in m for m in models):
                sys.exit(
                    f"❌ Embedding model '{EMBED_MODEL}' not pulled.\n"
                    f"   Run: ollama pull {EMBED_MODEL}"
                )
    except httpx.RequestError as e:
        sys.exit(f"❌ Cannot reach Ollama at {OLLAMA_URL}: {e}")
    print("   ✅ Ollama reachable, embedding model present\n")

    # Set up Chroma — wipe only if --rebuild was passed
    db_dir.mkdir(parents=True, exist_ok=True)
    chroma = chromadb.PersistentClient(path=str(db_dir))

    if rebuild:
        try:
            chroma.delete_collection(COLLECTION_NAME)
            print(f"🗑️  Removed existing '{COLLECTION_NAME}' collection (rebuild mode)")
        except Exception:
            pass
        collection = chroma.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        existing_ids: set[str] = set()
    else:
        # Get-or-create — preserve any work already done
        try:
            collection = chroma.get_collection(COLLECTION_NAME)
            existing_ids = get_existing_ids(collection)
            print(f"📦 Found existing collection: {len(existing_ids)} chunks already indexed")
        except Exception:
            collection = chroma.create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            existing_ids = set()
            print("📦 Created new collection (no prior data)")
    print()

    # Pre-warm the embedding model so first real chunk doesn't trigger slow load
    print(f"🔥 Pre-warming {EMBED_MODEL} (avoids 60s+ load delay on first chunk) …")
    with httpx.Client() as warm_client:
        prewarm_embed_model(warm_client)
    print("   ✅ Warm-up complete\n")

    # Chunk + embed + insert, skipping files already done
    total_chunks = 0
    skipped_files = 0
    processed_files = 0
    t0 = time.time()
    with httpx.Client() as client:
        for fi, path in enumerate(md_files, start=1):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                print(f"   ⚠️  Skip {path.name}: {e}")
                continue
            if not text.strip():
                continue

            # Resume check: if every chunk is already indexed, skip the file
            if not rebuild and file_chunks_already_present(path, existing_ids, text):
                skipped_files += 1
                if verbose:
                    print(f"   [{fi:>3}/{len(md_files)}] {path.name:<60s}   (skip — already indexed)")
                continue

            # File is new or partially indexed — clean any partial orphan chunks first
            if not rebuild:
                removed = clean_partial_file_chunks(collection, path.name, existing_ids)
                if removed and verbose:
                    print(f"      🧹 cleaned {removed} partial chunks from previous run")

            chunks = chunk_markdown(text, source=path.name)
            if not chunks:
                continue

            try:
                embeddings = embed_batch(client, [c["text"] for c in chunks], verbose=verbose)
            except Exception as e:
                print(f"   ❌ [{fi:>3}/{len(md_files)}] {path.name}: {type(e).__name__}: {e}")
                print(f"      Stopping — re-run to resume (incremental mode is default).")
                break

            collection.add(
                ids=[c["id"] for c in chunks],
                documents=[c["text"] for c in chunks],
                embeddings=embeddings,
                metadatas=[c["meta"] for c in chunks],
            )
            total_chunks += len(chunks)
            processed_files += 1
            elapsed = time.time() - t0
            print(f"   [{fi:>3}/{len(md_files)}] {path.name:<60s} → {len(chunks):>3} chunks  "
                  f"({total_chunks} new this run, {elapsed:.0f}s elapsed)")

    print()
    print(f"✅ Build complete")
    print(f"   Files processed this run : {processed_files}")
    print(f"   Files skipped (already done): {skipped_files}")
    print(f"   New chunks added         : {total_chunks}")
    print(f"   Total time               : {time.time() - t0:.0f}s")
    print(f"   DB at: {db_dir}")


def main():
    ap = argparse.ArgumentParser(description="Build RAG vector DB from a markdown corpus.")
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS,
                    help=f"Path to corpus folder (default: {DEFAULT_CORPUS})")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB,
                    help=f"Path to Chroma DB folder (default: {DEFAULT_DB})")
    ap.add_argument("--rebuild", action="store_true",
                    help="Wipe the collection and rebuild from scratch (the old default behavior).")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Print detailed per-file status including skipped files and retry attempts.")
    args = ap.parse_args()
    build(
        args.corpus.expanduser().resolve(),
        args.db.expanduser().resolve(),
        rebuild=args.rebuild,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()

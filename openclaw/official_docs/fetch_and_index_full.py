#!/usr/bin/env python3
"""Fetch every page listed in llms.txt, store as markdown, and build a LanceDB
RAG index using a real embedding model (sentence‑transformers).

Prerequisites (installed in the bundled virtual‑env):
    pip install sentence-transformers lancedb

Run with the venv activated, e.g.:
    source "knowledge-base/openclaw/official docs/venv/bin/activate"
    python3 knowledge-base/openclaw/official\ docs/fetch_and_index_full.py
"""
import os
import re
import sys
import json
import urllib.request
from pathlib import Path

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def slugify(url: str) -> str:
    # Remove protocol and leading slashes, replace non‑alphanum with _
    slug = re.sub(r"^https?://", "", url)
    slug = re.sub(r"[^A-Za-z0-9]", "_", slug)
    # Collapse multiple underscores
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_")

def fetch_markdown(url: str) -> str:
    """Download the raw markdown content of a docs page.
    The docs site serves markdown files directly; we just GET the URL.
    """
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"[WARN] Failed to fetch {url}: {e}", file=sys.stderr)
        return ""

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    root = Path(__file__).parent.parent.parent  # workspace root
    llms_path = root / "llms.txt"
    if not llms_path.is_file():
        print(f"llms.txt not found at {llms_path}", file=sys.stderr)
        sys.exit(1)

    # Read index and extract URLs
    urls = []
    for line in llms_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.search(r"\((https?://[^)]+)\)", line)
        if m:
            urls.append(m.group(1))
    print(f"Found {len(urls)} URLs to fetch")

    # Prepare output dirs
    pages_dir = Path(__file__).parent / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # Fetch and save each page
    for url in urls:
        slug = slugify(url)
        dest = pages_dir / f"{slug}.md"
        if dest.is_file():
            continue  # skip already fetched
        md = fetch_markdown(url)
        if md:
            dest.write_text(md, encoding="utf-8")
            print(f"Saved {url} -> {dest.name}")

    # ------------------------------------------------
    # Build LanceDB index
    # ------------------------------------------------
    try:
        import lancedb
        import numpy as np
    except ImportError:
        print("LanceDB not installed – aborting", file=sys.stderr)
        sys.exit(1)

    # Load embedding model (sentence‑transformers)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-mpnet-base-v2')

    # Connect/create DB
    db_path = Path(__file__).parent / "lancedb"
    db = lancedb.connect(str(db_path))
    table_name = "openclaw_docs"
    if table_name in db.table_names():
        tbl = db.open_table(table_name)
    else:
        tbl = None

    rows = []
    for md_file in pages_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        # Simple chunking: split on double newlines
        chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
        for i, chunk in enumerate(chunks):
            emb = model.encode(chunk).astype(np.float32)
            rows.append({
                "id": f"{md_file.stem}_{i}",
                "source": md_file.name,
                "chunk_index": i,
                "content": chunk,
                "embedding": emb.tolist(),
            })

    import pandas as pd
    df = pd.DataFrame(rows)
    df["embedding"] = df["embedding"].apply(lambda a: a)  # already list

    if tbl is None:
        tbl = db.create_table(table_name, data=df, mode="overwrite")
        print(f"Created table '{table_name}' with {len(df)} rows")
    else:
        tbl.add(df)
        print(f"Appended {len(df)} rows to existing table '{table_name}'")

if __name__ == "__main__":
    main()

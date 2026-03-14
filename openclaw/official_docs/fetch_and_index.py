#!/usr/bin/env python3
"""Fetch the full OpenClaw documentation (based on the llms.txt index) and
store each page as a markdown file under ``openclaw-docs/``. Then build a
simple RAG index using LanceDB.

Steps performed by the script:
1. Load the ``llms.txt`` index (saved locally as ``llms.txt``).
2. Parse each line to extract the URL and a short title.
3. For every URL, fetch the markdown content via ``web_fetch`` (the
   OpenClaw ``web_fetch`` tool is used by this script via a subprocess call).
4. Write the content to ``openclaw-docs/<slug>.md`` where ``slug`` is a
   URL‑safe version of the path.
5. Split each document into paragraphs (or fixed‑size chunks) for better
   retrieval granularity.
6. Compute embeddings for each chunk using a local model (placeholder –
   user can replace ``embed_text`` with their preferred embedding function).
7. Store the chunks and embeddings in a LanceDB table called ``openclaw_docs``.

Prerequisites:
- ``lancedb`` Python package installed (``pip install lancedb``).
- An embedding function is required. The placeholder uses a dummy
  ``numpy.random`` vector; replace it with a real model (e.g., ``sentence‑
  transformers`` or a local vLLM inference call).
- Internet access to fetch the docs (already granted).

The script is idempotent: it skips pages that already exist and will only
add new/updated pages on subsequent runs.
"""
import os
import re
import json
import hashlib
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def slugify(url: str) -> str:
    """Create a filesystem‑safe slug from a URL.
    Example: https://docs.openclaw.ai/cli/status.md -> cli_status_md
    """
    # Remove protocol and leading slash
    path = re.sub(r"^https?://", "", url)
    path = path.replace("/", "_")
    path = path.replace(".", "_")
    return path

def fetch_markdown(url: str) -> str:
    """Fetch markdown content for a given URL using the OpenClaw web_fetch tool.
    Returns the markdown text or raises an exception on failure.
    """
    # Use the external 'web_fetch' tool via subprocess to keep the same
    # behaviour as the assistant's web_fetch command.
    result = subprocess.run(
        ["openclaw", "web_fetch", "--url", url, "--extractMode", "markdown"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to fetch {url}: {result.stderr}")
    # The tool returns JSON; extract the "text" field.
    try:
        data = json.loads(result.stdout)
        return data.get("text", "")
    except json.JSONDecodeError:
        # Fallback: assume raw markdown output
        return result.stdout

def embed_text(text: str):
    """Placeholder embedding function.
    Replace this with a real embedding model (e.g., sentence‑transformers).
    Returns a list of floats.
    """
    import numpy as np
    # Use a deterministic pseudo‑random vector based on the hash of the text.
    rng = np.random.default_rng(int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32))
    return rng.random(768).tolist()  # example dimension 768

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def main():
    base_dir = Path(__file__).parent
    docs_dir = base_dir / "openclaw-docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Load the llms.txt index – we assume it has been saved in the repo.
    index_path = base_dir.parent.parent.parent / "llms.txt"
    if not index_path.is_file():
        print(f"Index file not found at {index_path!s}", file=sys.stderr)
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

    urls = []
    for line in lines:
        # The index lines are of the form "- [Title](URL)"
        match = re.search(r"\((https?://[^)]+)\)", line)
        if match:
            urls.append(match.group(1))

    print(f"Found {len(urls)} documentation pages to process.")

    # Fetch and store markdown files
    for url in urls:
        slug = slugify(url)
        md_path = docs_dir / f"{slug}.md"
        if md_path.is_file():
            continue  # skip already fetched pages
        try:
            content = fetch_markdown(url)
            md_path.write_text(content, encoding="utf-8")
            print(f"Fetched {url} -> {md_path.name}")
        except Exception as e:
            print(f"Error fetching {url}: {e}", file=sys.stderr)

    # Build LanceDB index
    try:
        import lancedb
        import numpy as np
    except ImportError:
        print("LanceDB not installed. Installing now...", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "lancedb"])
        import lancedb
        import numpy as np

    # Connect (creates a local DB directory)
    db = lancedb.connect(str(base_dir / "lancedb"))
    table_name = "openclaw_docs"
    if table_name in db.table_names():
        tbl = db.open_table(table_name)
    else:
        # Schema will be inferred from the first batch.
        tbl = None

    # Prepare rows for ingestion
    rows = []
    for md_file in docs_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        # Simple chunking: split by double newlines
        chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
        for i, chunk in enumerate(chunks):
            embedding = embed_text(chunk)
            rows.append({
                "id": f"{md_file.stem}_{i}",
                "source": md_file.name,
                "chunk_index": i,
                "content": chunk,
                "embedding": np.array(embedding, dtype=np.float32),
            })

    # Convert to a DataFrame for LanceDB ingestion
    import pandas as pd
    df = pd.DataFrame(rows)
    # Ensure embedding column is a list of floats (LanceDB will store as vector)
    df["embedding"] = df["embedding"].apply(lambda arr: arr.tolist())

    if tbl is None:
        tbl = db.create_table(table_name, data=df, mode="overwrite")
        print(f"Created LanceDB table '{table_name}' with {len(df)} rows.")
    else:
        tbl.add(df)
        print(f"Appended {len(df)} rows to existing table '{table_name}'.")

if __name__ == "__main__":
    main()

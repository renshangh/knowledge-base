# OpenClaw Knowledge Sources

## Suggested data sources to ingest for a robust OpenClaw knowledge base

| Category | Why it’s useful | Typical ingestion method |
|---|---|---|
| **Official docs** (OpenClaw, vLLM, LanceDB, etc.) | Authoritative reference, version‑specific details | `web_fetch` or `git clone` of the docs repo |
| **Blog posts / tutorials** | Real‑world use‑cases, best‑practice patterns | RSS feeds → `web_fetch` → summarizer |
| **Podcasts / videos** (YouTube, Vimeo, conference talks) | Insights not captured in text, speaker notes | `summarize` skill with `--youtube auto` (transcript + summary) |
| **StackOverflow / GitHub Discussions** | Common problems & community solutions | `gh issue list` / `gh pr list` + `summarize` for large threads |
| **Academic papers / arXiv** | Cutting‑edge research, algorithms | `web_fetch` (PDF → text) + vector embedding into LanceDB |
| **Newsletter archives** (e.g., “AI Weekly”) | Curated news, trend tracking | Email → `openai-whisper` → summarizer |
| **Internal wikis / Confluence** | Company‑specific knowledge, SOPs | Export as markdown/HTML then ingest |
| **CSV / JSON datasets** (real‑estate listings, market metrics) | Structured data for retrieval/analysis | Direct file import into LanceDB |
| **APIs** (e.g., Zillow, OpenStreetMap) | Live data feeds for property info | Scheduled scripts that store responses as JSON |
| **Social media** (Twitter, Reddit) | Sentiment, emerging topics | `web_fetch` with API keys or RSS → summarizer |

Feel free to pick the ones that match your workflow and add any additional sources you need.

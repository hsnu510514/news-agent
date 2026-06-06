# NewsAgent

AI-powered investment research agent that automatically ingests, analyzes, and serves financial news from global sources in both Chinese and English.

## Architecture

```
Data Sources → Ingestion → Dedup → AI Analysis → Storage (DB + Vectors)
                                                        ↕
                                                  API + Dashboard
```

### Data Sources

| Source | Type | Language | Data |
|--------|------|----------|------|
| 36Kr, 华尔街见闻, 东方财富, 新浪财经, 第一财经, 财新网 | RSS | Chinese | News articles |
| Reuters, Bloomberg, CNBC, FT, Economist | RSS | English | News articles |
| NewsAPI | API | Both | Broad news coverage |
| jin10 (金十数据) | Flash feed | Chinese | Real-time flash news |
| yfinance | API | Both | Stock/earnings data |
| SEC EDGAR | API | English | Filings |
| FRED | API | English | US macro indicators |
| AKShare | API | Chinese | China macro data |

### AI Pipeline

Uses LiteLLM to route tasks to the configured LLM (defaults to Gemini):
- **Classification/Tagging** → Gemini 2.0 Flash (fast, cheap)
- **Summarization** → Gemini 2.0 Flash (excellent bilingual output)
- **Deep Analysis** → Gemini 2.5 Pro (best reasoning)
- **Embeddings** → Gemini text-embedding-004 (768 dimensions)

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose
- API keys (see `.env.example`)

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Infrastructure

```bash
docker compose up -d postgres qdrant
```

### 3. Start Backend

```bash
# Install dependencies
pip install -e ".[dev]"

# Run database migrations (or let the app auto-create tables)
alembic upgrade head

# Start the server
python src/main.py
# Or: uvicorn src.main:app --reload
```

### 4. Start Dashboard

```bash
cd dashboard
npm install
npm run dev
```

The dashboard opens at http://localhost:3000, API at http://localhost:8000.

### 5. Enable Scheduler

Set `SCHEDULER_ENABLED=true` in `.env` to auto-run ingestion and analysis on a schedule.

Or trigger manually:

```bash
# Ingest data
curl -X POST http://localhost:8000/api/trigger/ingest/rss
curl -X POST http://localhost:8000/api/trigger/ingest/newsapi
curl -X POST http://localhost:8000/api/trigger/ingest/jin10
curl -X POST http://localhost:8000/api/trigger/ingest/earnings
curl -X POST http://localhost:8000/api/trigger/ingest/macro

# Deduplicate
curl -X POST http://localhost:8000/api/trigger/dedup

# Run AI analysis
curl -X POST http://localhost:8000/api/trigger/analyze
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/news` | List news articles (with filters) |
| GET | `/api/news/{id}` | Get single article |
| GET | `/api/analysis` | List analysis results |
| GET | `/api/analysis/search?q=...` | Semantic search |
| GET | `/api/earnings` | List earnings data |
| GET | `/api/macro` | List macro indicators |
| GET | `/api/flash` | List flash news |
| POST | `/api/trigger/ingest/*` | Trigger ingestion jobs |
| POST | `/api/trigger/dedup` | Trigger deduplication |
| POST | `/api/trigger/analyze` | Trigger AI analysis |

## Configuration

All settings in `.env` or `src/core/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_CLASSIFY_MODEL` | `gemini/gemini-2.0-flash` | Model for classification |
| `LLM_SUMMARIZE_MODEL` | `gemini/gemini-2.0-flash` | Model for summarization |
| `LLM_ANALYSIS_MODEL` | `gemini/gemini-2.5-pro` | Model for deep analysis |
| `LLM_EMBED_MODEL` | `gemini/text-embedding-004` | Embedding model |
| `NEWS_FETCH_INTERVAL_MINUTES` | `30` | News fetch interval |
| `SCHEDULER_ENABLED` | `true` | Enable auto-scheduling |

## Dashboard Pages

- **Dashboard** (`/`) — Overview with stats, latest news, sentiment
- **News** (`/news`) — Full news feed with search and filters
- **Flash** (`/flash`) — Real-time flash news / 快讯
- **Earnings** (`/earnings`) — Company earnings cards
- **Macro** (`/macro`) — Economic indicators by country

## Switching LLM Providers

This project uses [LiteLLM](https://docs.litellm.ai/) as a unified interface — you can swap providers by just changing env vars, no code changes needed.

### What to change

You need to update **3 places** when switching providers:

#### 1. API Keys in `.env`

| Provider | Env Var |
|----------|---------|
| Google Gemini | `GEMINI_API_KEY=AIza...` |
| OpenAI | `OPENAI_API_KEY=sk-...` |
| Anthropic Claude | `ANTHROPIC_API_KEY=sk-ant-...` |
| Ollama (local) | `OLLAMA_BASE_URL=http://localhost:11434` (already set) |

Only fill in the keys for providers you're using. Leave others blank.

#### 2. Model Names in `.env`

Use LiteLLM's model naming convention (`provider/model-name`):

| Provider | Classify/Summarize | Deep Analysis | Embeddings |
|----------|--------------------|--------------|------------|
| **Gemini** (default) | `gemini/gemini-2.0-flash` | `gemini/gemini-2.5-pro` | `gemini/text-embedding-004` |
| OpenAI | `openai/gpt-4o-mini` | `openai/gpt-4o` | `openai/text-embedding-3-small` |
| Anthropic | `anthropic/claude-sonnet-4-20250514` | `anthropic/claude-sonnet-4-20250514` | `openai/text-embedding-3-small` ⚠️ |
| Ollama (local) | `ollama/llama3.1:8b` | `ollama/deepseek-r1:14b` | `ollama/nomic-embed-text` |
| DeepSeek | `deepseek/deepseek-chat` | `deepseek/deepseek-reasoner` | `openai/text-embedding-3-small` ⚠️ |

The 4 env vars to set:
```
LLM_CLASSIFY_MODEL=gemini/gemini-2.0-flash
LLM_SUMMARIZE_MODEL=gemini/gemini-2.0-flash
LLM_ANALYSIS_MODEL=gemini/gemini-2.5-pro
LLM_EMBED_MODEL=gemini/text-embedding-004
```

#### 3. Vector Dimension in `src/storage/vectorstore.py`

Embedding models produce vectors of different sizes. You **must** update `VECTOR_SIZE` to match your embedding model, otherwise Qdrant will reject the vectors.

**If you've already started the app and created the collection before changing embeddings**, delete the old collection first:
```bash
# Connect to Qdrant and recreate the collection
curl -X DELETE http://localhost:6333/collections/news_embeddings
```
Then restart the app — it will auto-create the collection with the new dimension.

| Embedding Model | Dimension |
|----------------|-----------|
| `gemini/text-embedding-004` | **768** ← current default |
| `openai/text-embedding-3-small` | 1536 |
| `openai/text-embedding-3-large` | 3072 |
| `ollama/nomic-embed-text` | 768 |
| `ollama/mxbai-embed-large` | 1024 |

```python
# src/storage/vectorstore.py
VECTOR_SIZE = 768  # change this to match your embedding model
```

### Example: Switch from Gemini to OpenAI

```env
# .env
GEMINI_API_KEY=           # clear this
OPENAI_API_KEY=sk-...     # add your key

LLM_CLASSIFY_MODEL=openai/gpt-4o-mini
LLM_SUMMARIZE_MODEL=openai/gpt-4o-mini
LLM_ANALYSIS_MODEL=openai/gpt-4o
LLM_EMBED_MODEL=openai/text-embedding-3-small
```

Then update `VECTOR_SIZE` in `src/storage/vectorstore.py` from `768` → `1536` and delete the old Qdrant collection.

### Example: Use Ollama for Everything (Free, Local)

```env
# .env
OLLAMA_BASE_URL=http://localhost:11434

LLM_CLASSIFY_MODEL=ollama/llama3.1:8b
LLM_SUMMARIZE_MODEL=ollama/llama3.1:8b
LLM_ANALYSIS_MODEL=ollama/deepseek-r1:14b
LLM_EMBED_MODEL=ollama/nomic-embed-text
```

Pull the models first:
```bash
ollama pull llama3.1:8b
ollama pull deepseek-r1:14b
ollama pull nomic-embed-text
```

`VECTOR_SIZE` stays `768` (nomic-embed-text produces 768-dim vectors, same as Gemini).

### Important Notes

- **You can mix providers** — e.g., use Gemini for classification (cheap) and Claude for deep analysis (high quality). Just set different providers for each `LLM_*_MODEL` var.
- **Anthropic and DeepSeek don't offer embedding models** — you must use OpenAI, Gemini, or Ollama for embeddings if you use those providers for text generation.
- **`response_format` JSON mode** is handled via prompt instructions (not `response_format` param) because not all Gemini models reliably support structured JSON output. This works with all providers.
- LiteLLM handles the API differences between providers transparently — no code changes needed beyond config.
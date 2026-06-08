# Sequential Pipeline Processing

We decided to process ingested news articles sequentially in a single-threaded pipeline rather than in parallel. While parallel processing offers higher throughput, sequential execution naturally prevents database race conditions, avoids duplicate insight creation when multiple articles cover the same event in the same batch, and operates as a natural rate limiter against LLM API rate limits (e.g. Gemini 429 exceptions).

# ADR 0006: Sequential vs. Phase-Batched AI Analysis Pipeline Tradeoffs

## Context
When running local LLM models via Ollama, the sequential article-by-article analysis pipeline (which alternates between embedding and classification models for each article) can cause model thrashing on hardware with limited VRAM. An alternative approach is a phase-batched pipeline (embedding all articles in a batch, querying all matching insights, and then classifying/analyzing all articles).

We evaluated the tradeoffs of these two approaches to document system behavior and design constraints.

## Comparison of Approaches

### 1. Sequential Article-by-Article Processing (Current Approach)
* **Pros**:
  * **Immediate Context Consistency**: If Article 1 creates or updates an insight, Article 2 (processed immediately after) sees that updated insight in the vector store query. This prevents duplicate insight creation within the same batch.
  * **Granular Checkpointing**: The pipeline commits database changes after processing each article, ensuring zero lost progress if the run times out or is cancelled.
  * **Low Memory Footprint**: Only one article's text, intermediate prompt templates, and outputs are held in memory.
* **Cons**:
  * **Model Thrashing**: Under low VRAM conditions, alternating between the embedding model and the chat model for every article causes high loading/unloading latencies.

### 2. Phase-Batched Processing (Option 1)
* **Pros**:
  * **No Model Thrashing**: Ollama loads the embedding model once, embeds all articles, then loads the chat model once to process classifications.
  * **High Throughput**: Enables running API and model calls concurrently or in parallel.
* **Cons**:
  * **Duplicate Insights (Race Condition)**: Since all articles in the batch are queried against the vector store before any insights are created/updated, multiple articles on the same new event will each propose creating a new duplicate insight.
  * **All-or-Nothing Checkpointing**: If the job crashes or times out midway through the batch, progress for the entire batch is lost unless complex partial state tracking is added.

## Decision
We decided to keep the **Sequential Article-by-Article Processing** model. The hardware running the production instances is powerful enough to fit both the embedding and chat models in VRAM simultaneously, making model thrashing a non-issue. The immediate context consistency (preventing duplicate insights) and robust database checkpointing are critical to the system's accuracy and stability.

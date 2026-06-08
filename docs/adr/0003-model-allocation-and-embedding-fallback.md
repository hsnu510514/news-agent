# Model Allocation and Embedding Fallback

We decided to allocate LLM tasks to different models based on their complexity (relevance checks to Gemini 3.1 Flash Lite, summaries to Gemma 4 26B, and main classification/deep analysis to Gemma 4 31B) to balance cost, latency, and reasoning requirements. 

Additionally, we implemented a fallback embedding mechanism that automatically switches from the primary embedding model (Gemini Embedding 2) to a secondary model (Gemini Embedding 1) if the primary model hits API rate limits or daily quota exhaustion. To match the Qdrant database's vector size constraint of 768 dimensions, all embedding calls explicitly request a 768-dimension output.

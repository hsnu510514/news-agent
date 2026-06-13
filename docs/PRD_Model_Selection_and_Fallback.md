# PRD: Dynamic Model Selection, Ollama Integration, Cost Tracking, and Two-Tier Fallbacks

## Problem Statement

Currently, NewsAgent only has fallback configuration for the embedding model, and hardcoded configurations/limits for a fixed set of Gemini models. As we add local Ollama models (such as `gemma4:12b`) and external API models (such as `deepseek-chat` or `deepseek-reasoner`), several issues arise:
1. **API Keys & Ingestion Resilience**: Managing credentials securely for background tasks while offering custom model configurations is challenging without user authentication or persistent storage security.
2. **Model Options Discovery**: Hardcoding available model options makes it impossible to select dynamically pulled local Ollama models.
3. **Quota vs Cost Tracking**: While the Gemini free tier is constrained by request-based rate limits (RPM/RPD), paid APIs (OpenAI, Anthropic, DeepSeek) are constrained by monetary costs. Displaying free-tier rate limits for paid API keys or local models is inappropriate and confusing.
4. **Resiliency & Fallbacks**: If a primary model fails due to rate limits or daily quota exhaustion during pipeline execution, the pipeline stalls. A single global fallback model is either too cheap for reasoning tasks or too expensive/powerful for simple tasks, leading to poor output quality or wasted budget.

---

## Solution

Enhance the Model Quotas and Allocation framework with:
1. **Dynamic Model Discovery**: Fetch pulled local Ollama models dynamically from the local Ollama service and combine them with a curated list of cloud models.
2. **Two-Tier Fallback Mechanism**: Implement a "Lightweight Fallback" for low-complexity tasks (`check_relevance`, `summarize`) and a "Reasoning Fallback" for high-complexity tasks (`classify`, `deep_analysis`).
3. **Split Quota & Cost Tracking Panel**: Render model quotas dynamically in the UI. Ollama models will show as "Local (Free / Unlimited)", paid API models will show accumulated USD costs (tracked via LiteLLM token cost calculation) against a configured daily spend limit, and free-tier models will retain their RPM/TPM/RPD progress bars.
4. **Secure Credential Separation**: Retain all API keys and base URLs in the `.env` file for background workers, displaying only connection status checks in the dashboard.

---

## User Stories

1. As an operator, I want to configure a **Lightweight Fallback Model** and a **Reasoning Fallback Model**, so that the news ingestion pipeline automatically fails over if a primary model is rate-limited or exhausted.
2. As a budget-conscious user, I want the system to dynamically fetch local Ollama models from my local machine, so that I can use local models for low-complexity or fallback tasks without manual configuration.
3. As a developer, I want to keep all API keys and URLs in my local `.env` file, so that they remain secure and available to background workers without being exposed on the frontend.
4. As a user, I want to see a clear indicator of whether my Gemini, OpenAI, Anthropic, or DeepSeek API keys are successfully configured in the `.env`, so that I know which providers are ready to use.
5. As an investor, I want to see the accumulated cost (in USD) for each active paid model on the dashboard, so that I can monitor my API spend.
6. As a researcher, I want to set a daily spend limit, so that the news agent stops executing paid API requests if my daily budget is exhausted.
7. As a user, I want Ollama models to be displayed as "Local (Free / Unlimited)" in the quota panel without rate limit bars, so that the interface accurately reflects local resource usage.
8. As a developer, I want input and output tokens to be tracked separately for each model, so that I can inspect the exact context token usage vs. generated token counts on the panel.

---

## Implementation Decisions

* **Configuration Additions**: Add Pydantic settings for `LLM_LIGHTWEIGHT_FALLBACK_MODEL`, `LLM_REASONING_FALLBACK_MODEL`, and `DAILY_SPEND_LIMIT`. Save and load these through `model_config.json`.
* **API Key Presence Check**: The `/api/system/models` endpoint will check for the presence of configured API keys in environment variables (returning boolean indicators) rather than exposing the keys themselves.
* **Dynamic Ollama API Call**: Query the local Ollama API tags endpoint (`GET http://localhost:11434/api/tags`) from the backend when returning the list of available models.
* **LiteLLM Cost Calculation**: In `tracked_acompletion` and `tracked_aembedding`, calculate transaction cost using `litellm.completion_cost` and log it under the active model name.
* **Daily Cost Accumulation**: Update the in-memory `ModelQuotaTracker` to track accumulated costs and reset them on calendar day changes or manual reset.
* **Two-Tier Pipeline Failover**: Update the core LLM execution functions (`check_relevance`, `summarize`, `classify`, `deep_analysis`) to catch primary model exceptions and retry using their respective fallback models.
* **UI Table Redesign**: Modify the Model Quota tab in the settings dashboard to show cost metrics (Spent USD vs daily limit) for paid providers, hide progress bars for Ollama, and keep rate limit bars only for Gemini free-tier models.

---

## Testing Decisions

* Tests should verify external behavior and logic without depending on live third-party API calls.
* Mock `litellm.acompletion` and `litellm.aembedding` to return usage metrics and simulate rate-limit exceptions to verify fallback routing.
* Test that the `ModelQuotaTracker` accumulates and resets costs correctly.
* **Prior art**: `tests/test_model_quota.py` and `tests/test_embedding_fallback.py` contain patterns for testing rate limit logging and embedding model fallbacks.

---

## Out of Scope

* Direct API calls from the React frontend to Ollama or external LLM providers (all LLM routing is handled by the FastAPI backend).
* Updating or modifying credit card balances on external API provider accounts.
* Multi-user custom budget limits (budgets are global to the NewsAgent instance).

---

## Further Notes

* Ensure all Ollama models are formatted with the `ollama/` prefix (e.g. `ollama/gemma4:12b`) to ensure proper routing by LiteLLM.
* Ensure all DeepSeek models are formatted with `deepseek/` (e.g., `deepseek/deepseek-chat`, `deepseek/deepseek-reasoner`).

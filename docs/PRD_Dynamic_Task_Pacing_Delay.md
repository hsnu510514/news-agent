# PRD: Dynamic, Model-Aware LLM Queue Pacing Delay

## Problem Statement

The news-agent ingestion pipeline currently uses a hardcoded 4.0-second task pacing delay in the LLM execution queue. This delay was introduced to stay within the 15 RPM rate limit of the Gemini Free API.

Now that the system is shifting to local models via Ollama (or other high-throughput paid cloud APIs), this static 4.0-second delay is unnecessary and slows down processing to a crawl. For example, processing a batch of 50 articles takes more than 3 minutes in pacing delays alone, even if local Ollama model calls return in under a second.

However, if the delay is removed completely, any fallbacks or dynamic switches back to Gemini Free API will instantly trigger HTTP 429 rate limit exceptions, aborting the ingestion pipeline.

## Solution

Introduce a model-aware, user-configurable pacing delay policy:
1. **Auto Mode**: The LLM task queue dynamically inspects the active model of the completed task. Local models (`ollama/`) or paid cloud APIs (`openai/`, `anthropic/`, `deepseek/`) execute with `0.0s` delay. Gemini models (`gemini/`) default to a safe `4.0s` pacing delay.
2. **Manual Override**: Expose a Task Pacing Delay setting on the Settings Page. The user can select `Auto`, `0.0s (No Delay)`, `2.0s (Medium)`, `4.0s (Safe)`, or a `Custom` number of seconds.
3. **Persistence**: The configuration is persisted to `model_config.json` via the settings API.

## User Stories

1. As a system administrator, I want the ingestion queue pacing delay to automatically adapt based on whether local or cloud models are used, so that local Ollama models run at maximum speed without artificial pauses.
2. As a system administrator, I want Gemini Free API models to be automatically paced with a 4.0-second delay, so that I don't hit 429 rate limits or exhaust daily quotas.
3. As a developer, I want to override the pacing delay manually to a fixed number of seconds (e.g. 0.0s, 1.0s, 4.0s) in the dashboard settings panel, so that I can fine-tune the system's performance.
4. As an operator, I want my custom pacing delay configurations to persist across application restarts, so that I don't have to re-configure it every time the backend resets.

## Implementation Decisions

### Modules & Settings
* Add `LLM_PACING_DELAY` (string, defaults to `"auto"`) to the settings system and save it to `model_config.json`.
* Update `LLMTaskQueue` to track the last used model name dynamically.
* Update `LLMTaskQueue._worker_loop` to compute the pacing delay after each task:
  * If the setting is `"auto"`, set delay to `4.0` if `last_used_model` starts with `gemini/`, otherwise `0.0`.
  * If the setting is numeric, parse it and use it as the delay.

### API Contracts
* **GET `/api/system/models`**: Return the active `LLM_PACING_DELAY` in the `allocations` payload.
* **PUT `/api/system/models`**: Accept the `LLM_PACING_DELAY` field, validate it, and write it to `model_config.json`.

### Frontend UI Changes
* Add a select dropdown for **Task Pacing Delay** under the Resiliency & Safety Settings section in the dashboard (Model Quotas tab).
* Show a number input field for custom pacing delay seconds if the user selects the "Custom" option.
* Pass the selected pacing value to the existing config update API when the form is submitted.

## Testing Decisions

* Tests should verify that the dynamic resolution logic functions correctly. Specifically:
  * Setting the pacing delay to `0.0` or a low value via property setter or settings works correctly in the unit tests and executes tasks without delay.
  * Setting it to `"auto"` with a Gemini model sets the delay to 4.0s.
  * Setting it to `"auto"` with an Ollama model sets the delay to 0.0s.
* Existing unit tests in `tests/test_priority_queue.py` must pass without modifications to their core assertions.

## Out of Scope

* Modifying the queue to run tasks in parallel (ADR 0001 sequential processing remains in place).
* Automatically detecting the paid billing status of a Gemini API key without user input (any Gemini model prefix will assume Free Tier under `"auto"` mode unless manually overridden).

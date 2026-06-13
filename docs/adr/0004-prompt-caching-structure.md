# ADR 0004: Prompt Caching Structure and LLM Call Design

## Context

Many LLM providers (including Gemini, DeepSeek, and Anthropic) offer substantial cost reductions (typically ~75% cheaper) and latency improvements via prompt/token caching. 
Prompt caching matches exact token prefixes starting from the beginning of the prompt/message sequence. To maximize the cache hit rate:
1. All static context (system prompts, detailed guidelines, instruction templates, output JSON schemas) must be placed at the beginning of the messages list (using the `system` role).
2. All dynamic inputs (article title, article content, database lookup matches) must be placed at the end of the messages list (using the `user` role).
3. Any trailing static instructions (like formatting reminders) must be placed inside the system prompt or before the dynamic inputs to avoid invalidating the cached prefix.

Previously, the codebase merged static prompts and dynamic inputs into a single string passed as a `user` message, or inserted dynamic data near the top of templates (e.g. `sequential.txt`), preventing caching of the bulk of the instructions.

## Decision

We will standardize all LLM calling functions and prompt templates as follows:
- LLM utility functions in `src/core/llm.py` must support separate `system_prompt` and dynamic `text`/`user_content` inputs.
- LLM messages list will always be constructed as:
  ```python
  messages = []
  if system_prompt:
      messages.append({"role": "system", "content": system_prompt})
  messages.append({"role": "user", "content": text})
  ```
- Prompt templates (like `classify.yaml`, `summarize.yaml`, `extract.yaml`, `sequential.txt`) will contain strictly static instructions and schemas, with no dynamic interpolation placeholders.
- Python logic in `src/analysis/pipeline.py` and elsewhere will pass prompt files directly as `system_prompt`, and format any dynamic run-time data (article titles, contents, insights, glossaries) into a separate user message.

## Consequences

- **Cost Savings**: Static prompt instructions (ranging from ~170 to ~1000 tokens) are cached, significantly reducing input token billing for sequential batches.
- **Wording Integrity**: The prompt texts themselves remain completely unchanged, guaranteeing identical model behavior while improving efficiency.
- **Clarity**: Doubled curly braces `{{}}` in YAML/txt files (required previously for python's `.format()`) are reverted to standard single curly braces `{}`.

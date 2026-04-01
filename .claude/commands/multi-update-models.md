# Update Model Configuration

Research the latest available models from Anthropic, OpenAI, and Google, then update the project's model configuration accordingly.

## Step 1: Read Current Config

Read the current model configuration:
- `multi_mcp/config/config.yaml` - model definitions, aliases, constraints
- `multi_mcp/settings.py` - default model and default_model_list fallback

Note which models and aliases are already present.

## Step 2: Research Latest Models

Use web search to find the latest available API models from each provider. Search the general web (e.g., "Anthropic latest Claude models API 2026", "OpenAI latest models API", "Google Gemini latest models API") in addition to checking provider docs. The doc URLs below are starting points but may become stale - always verify via general web search as well.

1. **Anthropic**: Start with https://docs.anthropic.com/en/docs/about-claude/models - also search the web for latest Claude model announcements and API model IDs
2. **OpenAI**: Start with https://platform.openai.com/docs/models - also search the web for latest GPT and o-series model announcements and API model IDs
3. **Google**: Start with https://ai.google.dev/gemini-api/docs/models - also search the web for latest Gemini model announcements and API model IDs

For each provider, determine:
- New models not yet in config.yaml
- Models that have been deprecated or shut down
- Changes to existing model capabilities (context window, output tokens, etc.)

## Step 3: Update Config

Edit `multi_mcp/config/config.yaml`:
- **Add** new models with appropriate `litellm_model` strings (prefixed with provider: `openai/`, `anthropic/`, `gemini/`)
- **Remove** models that have been shut down (not just deprecated - only remove if actually unavailable)
- **Move aliases** (like `mini`, `nano`, `gpt`, `sonnet`, `gemini`) to point to the latest generation
- **Mark** superseded models as legacy in their notes field
- **Set** `provider_web_search: true` for models that support it
- **Set** temperature constraints (e.g., `temperature: 1.0` for GPT-5 family)
- Keep the existing section structure (OpenAI, Azure, Anthropic, Google, CLI, Bedrock, OpenRouter)

If the default_model_list fallback in `settings.py` is out of sync with the field default, fix it.

## Step 4: Fix Stale References

Search for references to removed/renamed models in tests and other files:
```
grep -r "removed-model-name" tests/ multi_mcp/
```
Update any hardcoded model names in test assertions to use valid models.

## Step 5: Validate

Run the full validation suite:
```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest tests/unit/ -q
```

All checks must pass before considering the update complete.

## Step 6: Live Test

Write a script to `tmp/test_models_live.py` that:
- Loads the model config via `get_models_config()` from `multi_mcp.models.config`
- Creates a `LiteLLMClient` with a `ModelResolver` and tests each non-CLI, non-disabled API model
- Sends a minimal prompt ("Say 'hello' and nothing else.") to each model
- Runs all models concurrently with a 60s timeout each
- Reports results in a table (model name, status, response time, preview/error)
- Distinguishes between config issues and credential issues (invalid API key / missing AWS creds are not config failures)

Run with: `uv run python tmp/test_models_live.py`

All models with valid credentials must return a successful response. Report any failures and investigate whether they are config issues or credential issues.

## Notes

- Use low-cost models for any live testing
- LiteLLM model strings use provider prefix: `openai/`, `anthropic/`, `gemini/`, `azure/`, `bedrock/`
- GPT-5 family models require `temperature: 1.0` constraint
- Credential failures (invalid API key, missing AWS keys) are not config issues - report but don't treat as failures

$ARGUMENTS

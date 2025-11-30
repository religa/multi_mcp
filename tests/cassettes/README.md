# VCR Cassettes Directory

This directory stores **VCR cassettes** - recorded HTTP interactions from integration tests.

## What is VCR?

VCR (Video Cassette Recorder) is a testing pattern that:
1. **Records** real API calls on the first test run
2. **Replays** recorded responses on subsequent runs
3. **Speeds up** integration tests by 90% (no real API calls needed)
4. **Reduces costs** by avoiding repeated LLM API calls

## How It Works

### First Run (Recording Mode)
```bash
# Run with real API keys - records cassettes
RUN_E2E=1 pytest tests/integration/test_e2e_codereview.py -v
```

**What happens:**
- Test makes real API calls to OpenAI/Anthropic/Google
- VCR records: request (URI, method, body) + response (status, headers, body)
- Saves cassette as `test_e2e_codereview__test_basic_codereview.yaml`
- Test runs in ~10-15 minutes (real API latency)

### Subsequent Runs (Replay Mode)
```bash
# Run WITHOUT API keys - replays from cassettes
pytest tests/integration/test_e2e_codereview.py -v
```

**What happens:**
- Test requests match recorded requests
- VCR returns recorded responses instantly
- No real API calls made
- Test runs in ~1 minute (90% speedup!)

## Cassette Format

Cassettes are YAML files with recorded interactions:

```yaml
version: 1
interactions:
- request:
    uri: https://api.openai.com/v1/chat/completions
    method: POST
    body:
      string: '{"model": "gpt-5-mini", "messages": [...]}'
    headers:
      # Sensitive headers filtered out (api-key, authorization)
  response:
    status:
      code: 200
      message: OK
    body:
      string: '{"choices": [{"message": {"content": "..."}}]}'
```

## Common Workflows

### Re-record All Cassettes
```bash
# Delete old cassettes and record fresh ones
rm -rf tests/cassettes/*.yaml
RUN_E2E=1 pytest tests/integration/ -v
```

### Re-record Specific Test
```bash
# Delete one cassette
rm tests/cassettes/test_e2e_codereview__test_basic_codereview.yaml

# Re-run that test
RUN_E2E=1 pytest tests/integration/test_e2e_codereview.py::test_basic_codereview -v
```

### Run Without VCR (Force Real API Calls)
```bash
# Use --disable-recording flag
RUN_E2E=1 pytest tests/integration/ --disable-recording -v
```

## Security

**Sensitive data is automatically filtered:**
- `authorization` headers
- `api-key`, `x-api-key` headers
- `openai-api-key`, `anthropic-api-key`, `google-api-key` headers

**Safe to commit cassettes to git** - no API keys exposed.

## Configuration

VCR settings are in `tests/conftest.py`:

```python
@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": ["authorization", "api-key", ...],  # Security
        "record_mode": "once",  # Record once, replay thereafter
        "cassette_library_dir": "tests/cassettes",  # Storage location
        "match_on": ["uri", "method", "body"],  # Request matching
        "decode_compressed_response": True,  # Readable YAML
        "ignore_localhost": True,  # Don't record local servers
    }
```

## Record Modes

| Mode | Behavior |
|------|----------|
| `once` (default) | Record new interactions, replay existing ones |
| `new_episodes` | Record new requests, replay known ones |
| `none` | Never record, always replay (fails if cassette missing) |
| `all` | Always record, overwrite existing cassettes |

## Troubleshooting

### Test fails with "VCR cassette not found"
**Solution:** Run with `RUN_E2E=1` to record the cassette first.

### Test fails with "Request did not match cassette"
**Cause:** Request changed (different body/params).
**Solution:** Delete cassette and re-record.

### Cassette contains API keys
**Cause:** Header not in `filter_headers` list.
**Solution:** Add header to `vcr_config()` in `conftest.py`.

### Tests still slow with cassettes
**Cause:** VCR disabled or cassettes missing.
**Solution:** Check cassettes exist and `@pytest.mark.vcr` is present.

## Benefits

- **90% speedup**: Integration tests run in <1 min instead of 10-15 min
- **Cost savings**: No repeated LLM API calls during development
- **Offline testing**: Works without internet/API keys after first record
- **Deterministic**: Same responses every time (no API variability)
- **Debug friendly**: Inspect cassettes to see exact API interactions

## Best Practices

1. **Commit cassettes to git** - enables fast CI/CD runs
2. **Re-record periodically** - ensure tests work with current API behavior
3. **Use descriptive test names** - creates readable cassette filenames
4. **One cassette per test** - isolates test failures
5. **Filter all sensitive headers** - prevents credential leaks

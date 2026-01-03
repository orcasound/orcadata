# Orca Detection Data Fetcher

Scripts to fetch raw detection data from OrcaHello and Orcasound APIs with month-year bucket caching for incremental updates.

## Environment Setup

### Prerequisites

- [uv](https://github.com/astral-sh/uv) - Fast Python package installer (recommended)
- Python 3.10

### Installation

```bash
# Navigate to Reports directory
cd Reports/

# Create virtual environment with Python 3.10
uv venv --python 3.10

# Activate virtual environment
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -e .
```

## Usage

### Fetch OrcaHello API Data

Fetch moderated orca detections from the OrcaHello API (Azure-hosted):

```bash
# Full historical fetch (fetches all detections)
python fetch_orcahello.py --full

# Incremental update (fetches only new data since last run)
python fetch_orcahello.py

# Fetch specific date range
python fetch_orcahello.py --from-date 2024-01-01 --to-date 2024-06-30

# Dry run (see what would be fetched without actually fetching)
python fetch_orcahello.py --from-date 2024-01-01 --dry-run

# Force refresh cached months
python fetch_orcahello.py --from-date 2024-05-01 --force-refresh

# Verbose logging
python fetch_orcahello.py --verbose
```

**Available Options:**
- `--full` - Fetch all historical data
- `--from-date YYYY-MM-DD` - Fetch from specific date
- `--to-date YYYY-MM-DD` - Fetch until specific date
- `--force-refresh` - Re-fetch even cached months
- `--cache-dir PATH` - Cache directory (default: `./cache/orcahello`)
- `--records-per-page INT` - Page size (default: 100)
- `--delay FLOAT` - Delay between requests in seconds (default: 0.5)
- `--max-pages INT` - Limit pages for testing
- `--location TEXT` - Filter by location name
- `--dry-run` - Show what would be fetched without fetching
- `--verbose` - Detailed logging

### Fetch Orcasound API Data

Fetch human-reported orca detections from the Orcasound GraphQL API:

```bash
# Full historical fetch (human detections only)
python fetch_orcasound.py --full

# Incremental update
python fetch_orcasound.py

# Fetch only whale detections
python fetch_orcasound.py --category WHALE

# Include machine-reported detections
python fetch_orcasound.py --include-machine

# Dry run
python fetch_orcasound.py --dry-run
```

**Available Options:**
- `--full` - Fetch all historical data
- `--from-date YYYY-MM-DD` - Fetch from specific date
- `--to-date YYYY-MM-DD` - Fetch until specific date
- `--force-refresh` - Re-fetch even cached months
- `--cache-dir PATH` - Cache directory (default: `./cache/orcasound`)
- `--batch-size INT` - GraphQL limit per request (default: 1000)
- `--delay FLOAT` - Delay between requests in seconds (default: 0.5)
- `--max-batches INT` - Limit batches for testing
- `--include-machine` - Include machine-reported detections (default: human only)
- `--feed TEXT` - Filter by feed slug
- `--category TEXT` - Filter by category (WHALE, VESSEL, OTHER)
- `--dry-run` - Show what would be fetched without fetching
- `--verbose` - Detailed logging

## Cache Structure

Both scripts use the same caching strategy with month-year buckets:

```
cache/
├── orcahello/
│   ├── cache_index.json       # Index of cached months
│   ├── fetch_log.jsonl        # Overall fetch history
│   └── YYYY-MM/               # Month buckets (e.g., 2024-01/)
│       ├── raw_detections.json
│       └── metadata.jsonl
└── orcasound/
    ├── cache_index.json
    ├── fetch_log.jsonl
    └── YYYY-MM/
        ├── raw_detections.json
        └── metadata.jsonl
```

### Cache Index Format

The `cache_index.json` file tracks which months have been fetched:

```json
{
  "months": {
    "2024-01": {
      "first_fetch": "2025-01-02T10:30:00Z",
      "last_updated": "2025-01-02T10:30:00Z",
      "detection_count": 1523,
      "date_range": {
        "min_pst": "2024-01-01T00:05:23",
        "max_pst": "2024-01-31T23:58:15"
      },
      "complete": true
    }
  },
  "last_full_fetch": "2025-01-02T10:30:00Z"
}
```

**Key Concepts:**
- **complete: true** - Past month that won't change (skipped on subsequent runs)
- **complete: false** - Current month that may receive new detections (always refetched)
- Incremental updates only fetch new or incomplete months

## Cache Management

### Inspect Cache

```bash
# View cache index
cat cache/orcahello/cache_index.json | python -m json.tool

# Check specific month
ls -lh cache/orcahello/2024-01/
cat cache/orcahello/2024-01/metadata.jsonl
```

### Clear Cache

```bash
# Clear specific month
rm -rf cache/orcahello/2024-01/

# Clear all OrcaHello cache
rm -rf cache/orcahello/

# Clear all cache
rm -rf cache/
```

### Force Refresh

```bash
# Refresh specific month
python fetch_orcahello.py --from-date 2024-01-01 --to-date 2024-01-31 --force-refresh

# Current month is always refreshed automatically
python fetch_orcahello.py
```

## How Incremental Updates Work

1. **First Run** (`--full`):
   - Fetches all historical data
   - Groups by month (YYYY-MM in PST timezone)
   - Saves each month to separate bucket
   - Marks past months as `complete: true`
   - Marks current month as `complete: false`

2. **Subsequent Runs** (default):
   - Loads cache index
   - Skips months marked `complete: true`
   - Refetches current month (always incomplete)
   - Only fetches new months if date range extended

3. **Force Refresh**:
   - Re-fetches specified months even if cached
   - Updates cache with new data
   - Useful if API data was corrected/updated

## Error Recovery

### Network Failures
- Successfully fetched months are saved before crash
- Re-running the script skips cached months and continues
- Uses exponential backoff retry (5 retries per request)

### Invalid Data
- Validation errors are logged but don't stop the script
- Invalid records are skipped
- Check `metadata.jsonl` for validation errors

### Partial Fetches
- Current month: always refetched (expected behavior)
- Past months with `complete: false`: automatically refetched

## Performance Notes

### OrcaHello API
- **Total records**: ~15,700 historical detections
- **Full fetch time**: 5-10 minutes (depends on network)
- **Incremental update**: 1-2 minutes (current month only)
- **Cache size**: 50-100MB for all historical data

### Orcasound API
- **Total records**: ~10,000-15,000 human detections
- **Full fetch time**: 30-60 seconds (GraphQL is faster)
- **Incremental update**: 10-20 seconds
- **Cache size**: Similar to OrcaHello

## API Documentation

### OrcaHello API
- **Base URL**: https://aifororcasdetections.azurewebsites.net/api/detections
- **Swagger UI**: https://aifororcasdetections.azurewebsites.net/swagger/index.html
- **Type**: REST API with pagination
- **Data**: AI-moderated orca call detections with spectrograms

### Orcasound API
- **GraphQL Endpoint**: https://live.orcasound.net/api/graphql
- **GraphiQL UI**: https://live.orcasound.net/graphiql
- **Redoc UI**: https://live.orcasound.net/api/json/redoc
- **Type**: GraphQL API with offset pagination
- **Data**: Human-reported (and machine-reported) orca/vessel/other detections

## Troubleshooting

### `uv: command not found`
Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### `No module named 'requests'`
Make sure virtual environment is activated and dependencies installed:
```bash
source .venv/bin/activate
uv pip install -e .
```

### `Permission denied` errors
Ensure you have write permissions in the cache directory

### Rate limiting / 429 errors
Increase the delay between requests: `--delay 1.0`

### GraphQL errors
Check the Orcasound API status at https://live.orcasound.net/graphiql

## Files

- `fetch_orcahello.py` - OrcaHello API fetcher
- `fetch_orcasound.py` - Orcasound GraphQL API fetcher
- `fetch_utils.py` - Shared utilities (HTTP, caching, timezone)
- `orcasound_graphql.py` - GraphQL query builder
- `detection_types.py` - Pydantic data models
- `pyproject.toml` - Project dependencies
- `.python-version` - Python version (3.10)

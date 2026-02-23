# Data Models

Key Pydantic models used for detection data. Full definitions in `detection_types.py`.

## Source API Models

### OrcaHelloDetection
Raw detection from OrcaHello API (AI-moderated).
- `id`, `timestamp`, `location` (name, lat, long)
- `found`: "Yes"/"No" (moderation result)
- `reviewed`: boolean (filter to true for confirmed detections)
- `confidence`, `moderator`, `comments`, `tags`

### OrcasoundDetectionGQL
Raw detection from Orcasound GraphQL API (human-reported).
- `id`, `timestamp`, `feedId`, `feed` (name, slug, nodeName)
- `source`: "HUMAN" or "MACHINE" (filter to HUMAN)
- `category`: "WHALE", "VESSEL", "OTHER", or null
- `playlistTimestamp`, `playerOffset` (HLS stream reference)
- `description`, `listenerCount`

## Preprocessed Models

### HydrophoneLocation
Unified location mapping across sources.
- `slug`: canonical ID (e.g., "orcasound-lab")
- `display_name`, `latitude`, `longitude`
- `orcahello_name`, `orcasound_feed_slug`, `orcasound_node_name`

### CombinedDetection
Standardized detection record for CSV export.
- `source`: "orcahello_moderated", "orcahello_unmoderated", or "orcasound"
- `detection_id`: original source ID
- Timestamps: `timestamp_utc`, `timestamp_unix`, `timestamp_pacific`
- Date fields: `year_month_pacific` (YYYY-MM), `year_pacific`, `month_pacific`, `date_pacific` (YYYY-MM-DD)
- `location_slug`: standardized slug
- `srkw_positive`: determination depends on source:
  - `orcahello_moderated`: true if `found="Yes"` (moderator confirmed)
  - `orcahello_unmoderated`: always true (no moderator rejected)
  - `orcasound`: true if `category="WHALE"`
- `comments`
- Source-specific metadata: `meta_orcahello_*`, `meta_orcasound_*`

### HourlyLogbookEvent
Aggregated by (source, location, date, hour) in Pacific time.
- Timestamps: `timestamp_pacific`, `timestamp_unix`
- Date fields: `year_month_pacific` (YYYY-MM), `year_pacific`, `month_pacific`, `date_pacific` (YYYY-MM-DD), `hour_pacific`
- Counts: `detection_count`, `detection_positive_count`
- `srkw_positive`: true if threshold met per source:
  - `orcahello_moderated`: ≥1 positive detection
  - `orcahello_unmoderated`: ≥3 detections (same threshold as orcasound)
  - `orcasound`: ≥3 positive detections
- `detection_ids`, `comments` (semicolon-delimited)

### DailyLogbookEvent
Aggregated by (source, location, date) from hourly events.
- Date fields: `year_month_pacific` (YYYY-MM), `year_pacific`, `month_pacific`, `date_pacific` (YYYY-MM-DD)
- Hourly counts: `hourly_event_count`, `hourly_event_positive_count`
- Detection counts: `detection_count`, `detection_positive_count`
- `detection_ids`, `comments` (semicolon-delimited)

## Output Directory Structure

```
combined_logbook/
├── detections/
│   ├── 2024-01.csv           # Monthly CSVs are self-contained with year/month fields
│   ├── 2024-02.csv
│   ├── ...
│   ├── all_detections.csv    # Simple concatenation (--concat)
│   └── metadata.json
├── hourly_events/
│   ├── 2024-01.csv           # Monthly CSVs are self-contained with year/month fields
│   ├── ...
│   └── all_hourly_events.csv # Simple concatenation (--concat)
└── daily_events/
    ├── 2024-01.csv           # Monthly CSVs are self-contained with year/month fields
    ├── ...
    └── all_daily_events.csv  # Simple concatenation (--concat)
```

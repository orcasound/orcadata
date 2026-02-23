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
- `source`: "orcahello" or "orcasound"
- `detection_id`: original source ID
- `timestamp_utc`, `timestamp_unix`, `timestamp_pacific`
- `location_slug`: standardized slug
- `srkw_positive`: true if whale confirmed (OrcaHello `found="Yes"` or Orcasound `category="WHALE"`)
- `comments`
- Source-specific metadata: `meta_orcahello_*`, `meta_orcasound_*`

### HourlyLogbookEvent
Aggregated by (source, location, date, hour) in Pacific time.
- `date_pacific`, `hour_pacific`, `timestamp_pacific`, `timestamp_unix`
- `detection_count`, `detection_positive_count`
- `srkw_positive`: true if threshold met (OrcaHello ≥1, Orcasound ≥3)
- `detection_ids`, `comments` (semicolon-delimited)

### DailyLogbookEvent
Aggregated by (source, location, date) from hourly events.
- `date_pacific`
- `hourly_event_count`, `hourly_event_positive_count`
- `detection_count`, `detection_positive_count`
- `detection_ids`, `comments` (semicolon-delimited)

## Output Directory Structure

```
combined_logbook/
├── detections/
│   ├── 2024-01.csv
│   ├── 2024-02.csv
│   ├── ...
│   ├── all_detections.csv    # --concat
│   └── metadata.json
├── hourly_events/
│   ├── 2024-01.csv
│   ├── ...
│   └── all_hourly_events.csv # --concat
└── daily_events/
    ├── 2024-01.csv
    ├── ...
    └── all_daily_events.csv  # --concat
```

#!/usr/bin/env python3
"""
Preprocess and combine detection data from OrcaHello and Orcasound caches.

Reads cached detection data, standardizes it into a unified format, and saves
per-month event logs as CSV files.

Usage:
    python preprocess_detections.py                    # Process all months
    python preprocess_detections.py --from-date 2025-01-01 --to-date 2025-12-31
    python preprocess_detections.py --force            # Force reprocess all
    python preprocess_detections.py --locations-only   # Only regenerate locations file
    python preprocess_detections.py --dry-run          # Show what would be processed
"""

import argparse
import csv
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pytz
from detection_types import (
    CombinedDetection,
    DailyLogbookEvent,
    HourlyLogbookEvent,
    HydrophoneLocation,
    HydrophoneLocationsFile,
)
from fetch_utils import (
    ensure_directory,
    get_months_in_range,
    parse_timestamp_to_pst,
    read_json,
    setup_logging,
    write_json,
)

# Constants
CACHE_DIR = Path("./fetch_cache")
ORCAHELLO_CACHE = CACHE_DIR / "orcahello"
ORCASOUND_CACHE = CACHE_DIR / "orcasound"
OUTPUT_DIR = Path("./combined_logbook/detections")
HOURLY_DIR = Path("./combined_logbook/hourly_events")
DAILY_DIR = Path("./combined_logbook/daily_events")
LOCATIONS_FILE = CACHE_DIR / "hydrophone_locations.json"

# Source-specific thresholds for determining hourly srkw_positive
ORCAHELLO_MODERATED_HOURLY_THRESHOLD = 1  # OrcaHello moderated detections: >= 1 positive is significant
ORCAHELLO_UNMODERATED_HOURLY_THRESHOLD = 3  # OrcaHello unmoderated: >= 3 detections (same as orcasound)
ORCASOUND_HOURLY_DETECTION_THRESHOLD = 3  # Orcasound detections are not moderated, so >= 3 positives needed

# Manual alias mappings for names that don't auto-match
# Maps OrcaHello location names to canonical Orcasound slugs
ORCAHELLO_NAME_ALIASES: Dict[str, str] = {
    "Haro Strait": "orcasound-lab",  # Same physical location
    "North San Juan Channel": "north-sjc",  # Full name variant of "North SJC"
}

logger = logging.getLogger(__name__)


# --- Location Mapping ---


def normalize_to_slug(name: str) -> str:
    """Convert location name to slug format (lowercase, hyphenated)."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def scan_orcahello_locations(cache_dir: Path) -> Dict[str, Dict]:
    """Scan OrcaHello cache for unique locations with lat/long."""
    locations = {}  # name -> {lat, long}

    for month_dir in cache_dir.iterdir():
        if not month_dir.is_dir():
            continue
        raw_file = month_dir / "raw_detections.json"
        if not raw_file.exists():
            continue

        data = read_json(raw_file)
        for det in data:
            loc = det.get("location", {})
            name = loc.get("name")
            if name and name not in locations:
                locations[name] = {
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude"),
                }

    return locations


def scan_orcasound_feeds(cache_dir: Path) -> Dict[str, Dict]:
    """Scan Orcasound cache for unique feeds."""
    feeds = {}  # slug -> {name, nodeName}

    for month_dir in cache_dir.iterdir():
        if not month_dir.is_dir():
            continue
        raw_file = month_dir / "raw_detections.json"
        if not raw_file.exists():
            continue

        data = read_json(raw_file)
        for det in data:
            feed = det.get("feed", {})
            slug = feed.get("slug")
            if slug and slug not in feeds:
                feeds[slug] = {
                    "name": feed.get("name"),
                    "nodeName": feed.get("nodeName"),
                }

    return feeds


def build_hydrophone_locations() -> HydrophoneLocationsFile:
    """Build comprehensive hydrophone locations reference from both caches."""
    logger.info("Scanning caches for hydrophone locations...")

    orcahello_locs = scan_orcahello_locations(ORCAHELLO_CACHE)
    orcasound_feeds = scan_orcasound_feeds(ORCASOUND_CACHE)

    logger.info(f"Found {len(orcahello_locs)} OrcaHello locations")
    logger.info(f"Found {len(orcasound_feeds)} Orcasound feeds")

    # Build unified location records
    # Strategy: Use orcasound slugs as canonical, match orcahello by name
    locations: List[HydrophoneLocation] = []
    name_to_slug: Dict[str, str] = {}

    # Start with orcasound feeds as canonical
    for slug, feed_info in orcasound_feeds.items():
        feed_name = feed_info["name"]
        node_name = feed_info["nodeName"]

        # Try to find matching orcahello location
        orcahello_name = None
        lat, lon = None, None
        for oh_name, oh_info in orcahello_locs.items():
            if normalize_to_slug(oh_name) == slug:
                orcahello_name = oh_name
                lat = oh_info["latitude"]
                lon = oh_info["longitude"]
                break

        loc = HydrophoneLocation(
            slug=slug,
            display_name=feed_name,
            latitude=lat,
            longitude=lon,
            orcahello_name=orcahello_name,
            orcasound_feed_name=feed_name,
            orcasound_feed_slug=slug,
            orcasound_node_name=node_name,
        )
        locations.append(loc)

        # Build name_to_slug mappings
        name_to_slug[slug] = slug
        name_to_slug[feed_name] = slug
        if node_name:
            name_to_slug[node_name] = slug
        if orcahello_name:
            name_to_slug[orcahello_name] = slug

    # Add any orcahello locations not matched to orcasound
    matched_oh_names = {loc.orcahello_name for loc in locations if loc.orcahello_name}
    for oh_name, oh_info in orcahello_locs.items():
        if oh_name in matched_oh_names:
            continue

        # Check if this name has a manual alias mapping
        if oh_name in ORCAHELLO_NAME_ALIASES:
            alias_slug = ORCAHELLO_NAME_ALIASES[oh_name]
            name_to_slug[oh_name] = alias_slug
            logger.info(f"  Mapped alias: {oh_name!r} -> {alias_slug!r}")
            continue

        # Create unmapped entry for truly unmatched locations
        slug = f"unmapped_{normalize_to_slug(oh_name)}"
        loc = HydrophoneLocation(
            slug=slug,
            display_name=oh_name,
            latitude=oh_info["latitude"],
            longitude=oh_info["longitude"],
            orcahello_name=oh_name,
        )
        locations.append(loc)
        name_to_slug[oh_name] = slug

    # Sort by slug
    locations.sort(key=lambda x: x.slug)

    return HydrophoneLocationsFile(locations=locations, name_to_slug=name_to_slug)


def load_or_build_locations(force: bool = False) -> HydrophoneLocationsFile:
    """Load locations file or build it if needed."""
    if not force and LOCATIONS_FILE.exists():
        logger.info(f"Loading existing locations from {LOCATIONS_FILE}")
        data = read_json(LOCATIONS_FILE)
        return HydrophoneLocationsFile(**data)

    locations = build_hydrophone_locations()
    ensure_directory(LOCATIONS_FILE.parent)
    write_json(LOCATIONS_FILE, locations.model_dump())
    logger.info(f"Saved {len(locations.locations)} locations to {LOCATIONS_FILE}")
    return locations


# --- OrcaHelloDetection Conversion ---


def convert_orcahello_detection(
    det: Dict, name_to_slug: Dict[str, str], moderated: bool = True
) -> Optional[CombinedDetection]:
    """
    Convert OrcaHello detection to combined format.

    Args:
        det: Raw detection dict from OrcaHello API
        name_to_slug: Location name to slug mapping
        moderated: If True, source is "orcahello_moderated" and srkw_positive
                   is based on found field. If False, source is "orcahello_unmoderated"
                   and srkw_positive is always True.
    """
    # Parse and convert timestamp
    timestamp_utc = det["timestamp"]
    try:
        pst_dt = parse_timestamp_to_pst(timestamp_utc)
    except Exception as e:
        logger.warning(f"Failed to parse timestamp {timestamp_utc}: {e}")
        return None

    # Get location slug
    loc_name = det.get("location", {}).get("name", "")
    if loc_name in name_to_slug:
        location_slug = name_to_slug[loc_name]
    else:
        location_slug = f"unmapped_{normalize_to_slug(loc_name)}"

    # Determine source and srkw_positive
    if moderated:
        source = "orcahello_moderated"
        # srkw_positive based on moderator verdict (found == "Yes")
        found_val = det.get("found", "")
        srkw_positive = found_val.lower() == "yes" if found_val else False
    else:
        source = "orcahello_unmoderated"
        # Unmoderated detections are treated as positive (no moderator said "No")
        srkw_positive = True

    # Extract date fields from Pacific timestamp
    date_pacific = pst_dt.strftime("%Y-%m-%d")
    year_pacific = pst_dt.year
    month_pacific = pst_dt.strftime("%m")  # Zero-padded month string (01-12)
    year_month_pacific = pst_dt.strftime("%Y-%m")

    return CombinedDetection(
        source=source,
        detection_id=det["id"],
        timestamp_utc=timestamp_utc,
        timestamp_unix=int(pst_dt.timestamp()),
        timestamp_pacific=pst_dt.isoformat(),
        year_month_pacific=year_month_pacific,
        year_pacific=year_pacific,
        month_pacific=month_pacific,
        date_pacific=date_pacific,
        location_slug=location_slug,
        srkw_positive=srkw_positive,
        comments=det.get("comments"),
        meta_orcahello_moderator=det.get("moderator"),
        meta_orcahello_tags=det.get("tags") if det.get("tags") else None,
        meta_orcahello_confidence=det.get("confidence"),
    )


def convert_orcasound_detection(
    det: Dict, name_to_slug: Dict[str, str]
) -> Optional[CombinedDetection]:
    """Convert Orcasound detection to combined format."""
    # Parse and convert timestamp
    timestamp_utc = det["timestamp"]
    try:
        pst_dt = parse_timestamp_to_pst(timestamp_utc)
    except Exception as e:
        logger.warning(f"Failed to parse timestamp {timestamp_utc}: {e}")
        return None

    # Get location slug from feed
    feed = det.get("feed", {})
    feed_slug = feed.get("slug", "")
    if feed_slug in name_to_slug:
        location_slug = name_to_slug[feed_slug]
    else:
        location_slug = f"unmapped_{normalize_to_slug(feed.get('name', 'unknown'))}"

    # Determine srkw_positive (category == "WHALE")
    category = det.get("category")
    srkw_positive = category == "WHALE" if category else False

    # Extract date fields from Pacific timestamp
    date_pacific = pst_dt.strftime("%Y-%m-%d")
    year_pacific = pst_dt.year
    month_pacific = pst_dt.strftime("%m")  # Zero-padded month string (01-12)
    year_month_pacific = pst_dt.strftime("%Y-%m")

    return CombinedDetection(
        source="orcasound",
        detection_id=det["id"],
        timestamp_utc=timestamp_utc,
        timestamp_unix=int(pst_dt.timestamp()),
        timestamp_pacific=pst_dt.isoformat(),
        year_month_pacific=year_month_pacific,
        year_pacific=year_pacific,
        month_pacific=month_pacific,
        date_pacific=date_pacific,
        location_slug=location_slug,
        srkw_positive=srkw_positive,
        comments=det.get("description"),
        meta_orcasound_listener_count=det.get("listenerCount"),
        meta_orcasound_category=category,
        meta_orcasound_hls_timestamp=det.get("playlistTimestamp"),
        meta_orcasound_hls_offset=det.get("playerOffset"),
    )


# --- Month Processing ---


def get_available_months() -> Set[str]:
    """Get all months available in either cache."""
    months = set()

    for cache_dir in [ORCAHELLO_CACHE, ORCASOUND_CACHE]:
        if cache_dir.exists():
            for month_dir in cache_dir.iterdir():
                if month_dir.is_dir() and re.match(r"\d{4}-\d{2}", month_dir.name):
                    months.add(month_dir.name)

    return months


def process_month(
    month: str, name_to_slug: Dict[str, str], dry_run: bool = False
) -> Tuple[int, int, int, int]:
    """
    Process a single month of detections.

    Returns:
        Tuple of (orcahello_moderated_count, orcahello_unmoderated_count, orcasound_count, total_combined)
    """
    combined: List[CombinedDetection] = []

    # Process OrcaHello detections (both moderated and unmoderated)
    oh_file = ORCAHELLO_CACHE / month / "raw_detections.json"
    oh_moderated_count = 0
    oh_unmoderated_count = 0
    if oh_file.exists():
        data = read_json(oh_file)
        for det in data:
            if det.get("reviewed"):
                # Moderated detection
                converted = convert_orcahello_detection(det, name_to_slug, moderated=True)
                if converted:
                    combined.append(converted)
                    oh_moderated_count += 1
            else:
                # Unmoderated detection
                converted = convert_orcahello_detection(det, name_to_slug, moderated=False)
                if converted:
                    combined.append(converted)
                    oh_unmoderated_count += 1

    # Process Orcasound detections
    os_file = ORCASOUND_CACHE / month / "raw_detections.json"
    os_count = 0
    if os_file.exists():
        data = read_json(os_file)
        for det in data:
            # Filter: only HUMAN source
            if det.get("source") != "HUMAN":
                continue
            converted = convert_orcasound_detection(det, name_to_slug)
            if converted:
                combined.append(converted)
                os_count += 1

    # Sort by timestamp
    combined.sort(key=lambda x: x.timestamp_unix)

    total = len(combined)
    if dry_run:
        logger.info(
            f"  [DRY RUN] {month}: {oh_moderated_count} OH-mod + {oh_unmoderated_count} OH-unmod + {os_count} Orcasound = {total} total"
        )
        return (oh_moderated_count, oh_unmoderated_count, os_count, total)

    # Write CSV
    if combined:
        output_file = OUTPUT_DIR / f"{month}.csv"
        ensure_directory(OUTPUT_DIR)
        write_detections_csv(output_file, combined)
        logger.info(
            f"  {month}: {oh_moderated_count} OH-mod + {oh_unmoderated_count} OH-unmod + {os_count} Orcasound = {total} → {output_file}"
        )
    else:
        logger.info(f"  {month}: No detections to write")

    return (oh_moderated_count, oh_unmoderated_count, os_count, total)


def write_detections_csv(path: Path, detections: List[CombinedDetection]) -> None:
    """Write detections to CSV file."""
    if not detections:
        return

    # Get field names from model
    fieldnames = list(CombinedDetection.model_fields.keys())

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for det in detections:
            row = det.model_dump()
            # Convert bool to lowercase string for CSV
            row["srkw_positive"] = "true" if row["srkw_positive"] else "false"
            # Convert None to empty string
            row = {k: ("" if v is None else v) for k, v in row.items()}
            writer.writerow(row)


def write_metadata(
    total_oh_moderated: int,
    total_oh_unmoderated: int,
    total_os: int,
    total_combined: int,
    month_stats: Dict[str, Dict[str, int]],
) -> None:
    """Write processing metadata file."""
    metadata = {
        "last_processed": datetime.now(pytz.UTC).isoformat(),
        "orcahello_moderated_detections": total_oh_moderated,
        "orcahello_unmoderated_detections": total_oh_unmoderated,
        "orcasound_detections": total_os,
        "combined_detections": total_combined,
        "months_processed": {
            month: month_stats[month] for month in sorted(month_stats.keys())
        },
    }
    metadata_file = OUTPUT_DIR / "metadata.json"
    ensure_directory(OUTPUT_DIR)
    write_json(metadata_file, metadata)
    logger.info(f"Wrote metadata to {metadata_file}")


def concatenate_monthly_csvs(months: List[str]) -> int:
    """
    Concatenate all monthly CSV files into a single file.

    Args:
        months: List of month strings (YYYY-MM) to concatenate

    Returns:
        Total number of rows written
    """
    output_file = OUTPUT_DIR / "all_detections.csv"
    total_rows = 0

    fieldnames = list(CombinedDetection.model_fields.keys())

    with open(output_file, "w", newline="", encoding="utf-8") as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()

        for month in sorted(months):
            month_file = OUTPUT_DIR / f"{month}.csv"
            if not month_file.exists():
                continue

            with open(month_file, "r", newline="", encoding="utf-8") as inf:
                reader = csv.DictReader(inf)
                for row in reader:
                    writer.writerow(row)
                    total_rows += 1

    logger.info(f"Concatenated {total_rows} rows into {output_file}")
    return total_rows


# --- Aggregation Functions ---


def aggregate_detections_to_hourly(month: str) -> List[HourlyLogbookEvent]:
    """
    Aggregate detections to hourly events.

    Args:
        month: Month string (YYYY-MM)

    Returns:
        List of HourlyLogbookEvent objects
    """
    detections_file = OUTPUT_DIR / f"{month}.csv"
    if not detections_file.exists():
        logger.warning(f"No detections file found for {month}")
        return []

    hourly_events: List[HourlyLogbookEvent] = []
    grouped: Dict[Tuple[str, str, str, int], List[Dict]] = {}

    # Read and group detections
    with open(detections_file, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse timestamp_pacific to extract date and hour
            timestamp_pacific = row["timestamp_pacific"]
            try:
                # Parse the ISO timestamp
                dt = datetime.fromisoformat(timestamp_pacific.replace("Z", "+00:00"))
                # Convert to Pacific timezone if not already
                if dt.tzinfo is None:
                    pacific_tz = pytz.timezone("US/Pacific")
                    dt = pacific_tz.localize(dt)
                else:
                    pacific_tz = pytz.timezone("US/Pacific")
                    dt = dt.astimezone(pacific_tz)

                date_pacific = dt.strftime("%Y-%m-%d")
                hour_pacific = dt.hour

                # Round to hour start
                rounded_dt = dt.replace(minute=0, second=0, microsecond=0)
                timestamp_pacific_rounded = rounded_dt.isoformat()
                timestamp_unix = int(rounded_dt.timestamp())

                key = (row["source"], row["location_slug"], date_pacific, hour_pacific)
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append({
                    "row": row,
                    "timestamp_pacific_rounded": timestamp_pacific_rounded,
                    "timestamp_unix": timestamp_unix,
                })
            except Exception as e:
                logger.warning(f"Failed to parse timestamp {timestamp_pacific}: {e}")
                continue

    # Create hourly events from groups
    for (source, location_slug, date_pacific, hour_pacific), items in grouped.items():
        detection_count = len(items)
        detection_positive_count = sum(
            1 for item in items
            if item["row"].get("srkw_positive", "").strip().lower() == "true"
        )

        # Determine srkw_positive based on source-specific threshold
        if source == "orcahello_moderated":
            srkw_positive = detection_positive_count >= ORCAHELLO_MODERATED_HOURLY_THRESHOLD
        elif source == "orcahello_unmoderated":
            # For unmoderated, all detections are positive, so positive_count == total_count
            srkw_positive = detection_positive_count >= ORCAHELLO_UNMODERATED_HOURLY_THRESHOLD
        elif source == "orcasound":
            srkw_positive = detection_positive_count >= ORCASOUND_HOURLY_DETECTION_THRESHOLD
        else:
            srkw_positive = False

        # Concatenate detection IDs
        detection_ids = ";".join(item["row"]["detection_id"] for item in items)

        # Concatenate non-empty comments
        comments_list = [
            item["row"].get("comments", "").strip()
            for item in items
            if item["row"].get("comments", "").strip()
        ]
        comments = ";".join(comments_list)

        # Extract year and month from date_pacific (YYYY-MM-DD format)
        year_pacific = int(date_pacific[:4])
        month_pacific = date_pacific[5:7]  # Zero-padded month string (01-12)
        year_month_pacific = date_pacific[:7]  # YYYY-MM

        event = HourlyLogbookEvent(
            source=source,
            location_slug=location_slug,
            timestamp_pacific=items[0]["timestamp_pacific_rounded"],
            timestamp_unix=items[0]["timestamp_unix"],
            year_month_pacific=year_month_pacific,
            year_pacific=year_pacific,
            month_pacific=month_pacific,
            date_pacific=date_pacific,
            hour_pacific=hour_pacific,
            detection_count=detection_count,
            detection_positive_count=detection_positive_count,
            srkw_positive=srkw_positive,
            detection_ids=detection_ids,
            comments=comments,
        )
        hourly_events.append(event)

    # Sort by timestamp
    hourly_events.sort(key=lambda x: x.timestamp_unix)
    return hourly_events


def aggregate_hourly_to_daily(month: str) -> List[DailyLogbookEvent]:
    """
    Aggregate hourly events to daily events.

    Args:
        month: Month string (YYYY-MM)

    Returns:
        List of DailyLogbookEvent objects
    """
    hourly_file = HOURLY_DIR / f"{month}.csv"
    if not hourly_file.exists():
        logger.warning(f"No hourly events file found for {month}")
        return []

    daily_events: List[DailyLogbookEvent] = []
    grouped: Dict[Tuple[str, str, str], List[Dict]] = {}

    # Read and group hourly events
    with open(hourly_file, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["source"], row["location_slug"], row["date_pacific"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(row)

    # Create daily events from groups
    for (source, location_slug, date_pacific), items in grouped.items():
        hourly_event_count = len(items)
        hourly_event_positive_count = sum(
            1 for item in items
            if item.get("srkw_positive", "").strip().lower() == "true"
        )

        # Sum detection counts
        detection_count = sum(int(item.get("detection_count", 0)) for item in items)
        detection_positive_count = sum(
            int(item.get("detection_positive_count", 0)) for item in items
        )

        # Concatenate all detection IDs
        all_detection_ids = []
        for item in items:
            ids = item.get("detection_ids", "").split(";")
            all_detection_ids.extend([id for id in ids if id.strip()])
        detection_ids = ";".join(all_detection_ids)

        # Concatenate all non-empty comments
        all_comments = []
        for item in items:
            comments = item.get("comments", "").strip()
            if comments:
                comment_list = comments.split(";")
                all_comments.extend([c.strip() for c in comment_list if c.strip()])
        comments = ";".join(all_comments)

        # Extract year and month from date_pacific (YYYY-MM-DD format)
        year_pacific = int(date_pacific[:4])
        month_pacific = date_pacific[5:7]  # Zero-padded month string (01-12)
        year_month_pacific = date_pacific[:7]  # YYYY-MM

        # Day is positive if any hour is positive
        srkw_positive = hourly_event_positive_count > 0

        event = DailyLogbookEvent(
            source=source,
            location_slug=location_slug,
            year_month_pacific=year_month_pacific,
            year_pacific=year_pacific,
            month_pacific=month_pacific,
            date_pacific=date_pacific,
            hourly_event_count=hourly_event_count,
            hourly_event_positive_count=hourly_event_positive_count,
            detection_count=detection_count,
            detection_positive_count=detection_positive_count,
            srkw_positive=srkw_positive,
            detection_ids=detection_ids,
            comments=comments,
        )
        daily_events.append(event)

    # Sort by date
    daily_events.sort(key=lambda x: x.date_pacific)
    return daily_events


def write_hourly_csv(path: Path, events: List[HourlyLogbookEvent]) -> None:
    """Write hourly events to CSV file."""
    if not events:
        return

    fieldnames = list(HourlyLogbookEvent.model_fields.keys())

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            row = event.model_dump()
            # Convert bool to lowercase string for CSV
            row["srkw_positive"] = "true" if row["srkw_positive"] else "false"
            # Convert None to empty string
            row = {k: ("" if v is None else v) for k, v in row.items()}
            writer.writerow(row)


def write_daily_csv(path: Path, events: List[DailyLogbookEvent]) -> None:
    """Write daily events to CSV file."""
    if not events:
        return

    fieldnames = list(DailyLogbookEvent.model_fields.keys())

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            row = event.model_dump()
            # Convert None to empty string
            row = {k: ("" if v is None else v) for k, v in row.items()}
            writer.writerow(row)


def concatenate_hourly_csvs(months: List[str]) -> int:
    """
    Concatenate all monthly hourly CSV files into a single file.

    Args:
        months: List of month strings (YYYY-MM) to concatenate

    Returns:
        Total number of rows written
    """
    output_file = HOURLY_DIR / "all_hourly_events.csv"
    total_rows = 0

    fieldnames = list(HourlyLogbookEvent.model_fields.keys())

    with open(output_file, "w", newline="", encoding="utf-8") as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()

        for month in sorted(months):
            month_file = HOURLY_DIR / f"{month}.csv"
            if not month_file.exists():
                continue

            with open(month_file, "r", newline="", encoding="utf-8") as inf:
                reader = csv.DictReader(inf)
                for row in reader:
                    writer.writerow(row)
                    total_rows += 1

    logger.info(f"Concatenated {total_rows} hourly event rows into {output_file}")
    return total_rows


def concatenate_daily_csvs(months: List[str]) -> int:
    """
    Concatenate all monthly daily CSV files into a single file.

    Args:
        months: List of month strings (YYYY-MM) to concatenate

    Returns:
        Total number of rows written
    """
    output_file = DAILY_DIR / "all_daily_events.csv"
    total_rows = 0

    fieldnames = list(DailyLogbookEvent.model_fields.keys())

    with open(output_file, "w", newline="", encoding="utf-8") as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()

        for month in sorted(months):
            month_file = DAILY_DIR / f"{month}.csv"
            if not month_file.exists():
                continue

            with open(month_file, "r", newline="", encoding="utf-8") as inf:
                reader = csv.DictReader(inf)
                for row in reader:
                    writer.writerow(row)
                    total_rows += 1

    logger.info(f"Concatenated {total_rows} daily event rows into {output_file}")
    return total_rows


# --- Google Sheets Update ---


def update_google_sheets(
    config_path: Path,
    no_confirm: bool = False,
) -> None:
    """
    Update Google Sheets with concatenated CSV data.

    Args:
        config_path: Path to YAML config file
        no_confirm: Skip interactive confirmation if True
    """
    from gsheet_utils import (
        load_gsheet_config,
        get_gspread_client,
        get_csv_path,
        read_csv_as_values,
        get_sheet_info,
        update_sheet,
    )

    # Load config
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return

    config = load_gsheet_config(config_path)
    spreadsheet_id = config["spreadsheet_id"]
    sheets_config = config["sheets"]

    # Initialize client (may trigger OAuth browser flow)
    try:
        client = get_gspread_client(config)
    except Exception as e:
        logger.error(f"Failed to authenticate with Google Sheets: {e}")
        return

    logger.info(
        f"Updating Google Sheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    )

    for sheet_name, sheet_config in sheets_config.items():
        gid = sheet_config["gid"]
        csv_source = sheet_config["csv_source"]

        try:
            csv_path = get_csv_path(csv_source)
        except ValueError as e:
            logger.error(f"Skipping {sheet_name}: {e}")
            continue

        if not csv_path.exists():
            logger.warning(f"Skipping {sheet_name}: {csv_path} not found")
            continue

        # Read CSV data
        try:
            data = read_csv_as_values(csv_path)
            new_row_count = len(data)
        except Exception as e:
            logger.error(f"Failed to read {csv_path}: {e}")
            continue

        # Get current sheet info
        try:
            worksheet, old_row_count = get_sheet_info(client, spreadsheet_id, gid)
            worksheet_title = worksheet.title
        except Exception as e:
            logger.error(f"Failed to access {sheet_name} (gid={gid}): {e}")
            continue

        # Interactive confirmation unless no_confirm
        if not no_confirm:
            prompt = f"Overwrite '{worksheet_title}' ({old_row_count} rows → {new_row_count} rows)? [y/N]: "
            confirm = input(prompt).strip().lower()
            if confirm != "y":
                logger.info(f"  Skipped {worksheet_title}")
                continue

        # Update sheet
        try:
            rows_written = update_sheet(worksheet, data)
            logger.info(f"  Updated {worksheet_title}: {old_row_count} → {rows_written} rows")
        except Exception as e:
            logger.error(f"  Failed to update {sheet_name}: {e}")

    logger.info("Google Sheet update complete.")


# --- CLI ---


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess and combine detection data from OrcaHello and Orcasound."
    )
    parser.add_argument(
        "--from-date",
        type=str,
        help="Start date (YYYY-MM-DD). Defaults to earliest available.",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        help="End date (YYYY-MM-DD). Defaults to latest available.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocess all months, ignoring cache.",
    )
    parser.add_argument(
        "--locations-only",
        action="store_true",
        help="Only regenerate hydrophone locations file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without writing files.",
    )
    parser.add_argument(
        "--concat",
        action="store_true",
        help="Also create a concatenated all_detections.csv with a year_month column.",
    )
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help="Generate hourly and daily event CSVs after processing detections.",
    )
    parser.add_argument(
        "--aggregate-only",
        action="store_true",
        help="Skip detection processing, only run aggregation on existing detection CSVs.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging."
    )
    parser.add_argument(
        "--gsheet-update",
        type=str,
        metavar="CONFIG_YAML",
        help="Update Google Sheet with concatenated CSV data using the specified YAML config file.",
    )
    parser.add_argument(
        "--gsheet-noconfirm",
        action="store_true",
        help="Skip interactive confirmation when updating Google Sheets.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    # Build or load hydrophone locations
    locations = load_or_build_locations(force=args.force or args.locations_only)

    if args.locations_only:
        logger.info("Locations file regenerated. Exiting.")
        return

    # Determine months to process
    if args.aggregate_only:
        # Get months from existing detection CSVs
        available_months = set()
        if OUTPUT_DIR.exists():
            for csv_file in OUTPUT_DIR.glob("*.csv"):
                if csv_file.name != "all_detections.csv" and re.match(r"\d{4}-\d{2}\.csv", csv_file.name):
                    available_months.add(csv_file.stem)
        if not available_months:
            logger.warning("No detection CSV files found. Run detection processing first.")
            return
    else:
        # Get months from cache
        available_months = get_available_months()
        if not available_months:
            logger.warning("No cached data found. Run fetch scripts first.")
            return

    # Filter by date range if specified
    if args.from_date or args.to_date:
        from_dt = (
            datetime.strptime(args.from_date, "%Y-%m-%d").date()
            if args.from_date
            else date(2019, 1, 1)
        )
        to_dt = (
            datetime.strptime(args.to_date, "%Y-%m-%d").date()
            if args.to_date
            else date.today()
        )
        requested_months = set(get_months_in_range(from_dt, to_dt))
        months_to_process = sorted(available_months & requested_months)
    else:
        months_to_process = sorted(available_months)

    if not months_to_process:
        logger.info("No months to process in the specified range.")
        return

    # Process detections (unless aggregate-only)
    total_oh_mod, total_oh_unmod, total_os, total_combined = 0, 0, 0, 0
    month_stats: Dict[str, Dict[str, int]] = {}

    if not args.aggregate_only:
        logger.info(f"Processing {len(months_to_process)} months...")
        for month in months_to_process:
            oh_mod, oh_unmod, os, combined = process_month(
                month, locations.name_to_slug, dry_run=args.dry_run
            )
            total_oh_mod += oh_mod
            total_oh_unmod += oh_unmod
            total_os += os
            total_combined += combined
            month_stats[month] = {
                "orcahello_moderated": oh_mod,
                "orcahello_unmoderated": oh_unmod,
                "orcasound": os,
                "total": combined,
            }

        # Write metadata
        if not args.dry_run:
            write_metadata(total_oh_mod, total_oh_unmod, total_os, total_combined, month_stats)

            # Concatenate if requested
            if args.concat:
                concatenate_monthly_csvs(list(month_stats.keys()))

        logger.info(
            f"Done! Processed {total_oh_mod} OH-mod + {total_oh_unmod} OH-unmod + {total_os} Orcasound = {total_combined} total detections"
        )

    # Run aggregation if requested
    if args.aggregate or args.aggregate_only:
        logger.info(f"Aggregating {len(months_to_process)} months to hourly and daily events...")
        
        processed_months = []
        for month in months_to_process:
            # Aggregate to hourly
            hourly_events = aggregate_detections_to_hourly(month)
            if hourly_events and not args.dry_run:
                ensure_directory(HOURLY_DIR)
                hourly_file = HOURLY_DIR / f"{month}.csv"
                write_hourly_csv(hourly_file, hourly_events)
                logger.info(f"  {month}: {len(hourly_events)} hourly events → {hourly_file}")

            # Aggregate to daily
            daily_events = aggregate_hourly_to_daily(month)
            if daily_events and not args.dry_run:
                ensure_directory(DAILY_DIR)
                daily_file = DAILY_DIR / f"{month}.csv"
                write_daily_csv(daily_file, daily_events)
                logger.info(f"  {month}: {len(daily_events)} daily events → {daily_file}")

            if hourly_events or daily_events:
                processed_months.append(month)

        # Concatenate if requested
        if args.concat and not args.dry_run and processed_months:
            concatenate_hourly_csvs(processed_months)
            concatenate_daily_csvs(processed_months)

        logger.info(f"Aggregation complete for {len(processed_months)} months.")

    # Update Google Sheet if requested
    if args.gsheet_update:
        update_google_sheets(Path(args.gsheet_update), args.gsheet_noconfirm)


if __name__ == "__main__":
    main()

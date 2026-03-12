#!/usr/bin/env python3
"""Fetch orca detections from Orcasound GraphQL API with month-bucket caching.

Uses the Detection resource directly (not Candidate) per task requirements.
"""

import argparse
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytz
from detection_types import OrcasoundDetectionGQL, OrcasoundFeedGQL
from fetch_utils import (
    calculate_date_range,
    create_http_session,
    ensure_directory,
    extract_month_year_pst,
    get_cached_months,
    get_current_month_pst,
    get_month_date_range,
    get_month_dir,
    get_months_in_range,
    is_month_complete,
    parse_timestamp_to_pst,
    setup_logging,
    update_cache_index,
    write_json,
    write_jsonl_entry,
)
from orcasound_graphql import (
    DETECTIONS_QUERY,
    GRAPHQL_ENDPOINT,
    build_detection_query_variables,
    execute_graphql_query,
)

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("./fetch_cache/orcasound")
DEFAULT_BATCH_SIZE = 1000
DEFAULT_DELAY = 0.5


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch orca detections from Orcasound GraphQL API with month-bucket caching"
    )

    # Fetch mode
    parser.add_argument(
        "--full",
        action="store_true",
        help="Fetch all historical data (from 2019 to present)",
    )
    parser.add_argument(
        "--from-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Fetch from specific date (YYYY-MM-DD). Default: last 30 days",
    )
    parser.add_argument(
        "--to-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Fetch until specific date (YYYY-MM-DD). Default: today",
    )

    # Cache options
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"Cache directory path (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-fetch even cached months",
    )

    # API options
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"GraphQL limit per request (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay between requests in seconds (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        help="Limit number of batches for testing",
    )

    # Filters
    parser.add_argument(
        "--include-machine",
        action="store_true",
        help="Include machine-reported detections (default: human only)",
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=["WHALE", "VESSEL", "OTHER"],
        help="Filter by category",
    )
    parser.add_argument(
        "--feed",
        type=str,
        help="Filter by feed ID",
    )

    # Output options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without fetching",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def fetch_detections_batch(
    session,
    offset: int,
    batch_size: int,
    include_machine: bool,
    category: Optional[str],
    feed_id: Optional[str],
    timestamp_gte: Optional[str],
    timestamp_lt: Optional[str],
    timeout: int = 60,
) -> Tuple[List[OrcasoundDetectionGQL], bool, int, int]:
    """
    Fetch a single batch of detections via GraphQL.

    Args:
        session: HTTP session
        offset: Pagination offset
        batch_size: Number of records per batch
        include_machine: Include machine detections
        category: Optional category filter
        feed_id: Optional feed ID filter
        timestamp_gte: Timestamp >= filter (ISO format)
        timestamp_lt: Timestamp < filter (ISO format)
        timeout: Request timeout

    Returns:
        Tuple of (detections list, has_next_page, total_count, actual_limit)
    """
    variables = build_detection_query_variables(
        offset=offset,
        limit=batch_size,
        include_machine=include_machine,
        category=category,
        feed_id=feed_id,
        timestamp_gte=timestamp_gte,
        timestamp_lt=timestamp_lt,
    )

    try:
        data = execute_graphql_query(
            session, GRAPHQL_ENDPOINT, DETECTIONS_QUERY, variables, timeout
        )

        detections_data = data.get("detections", {})
        results = detections_data.get("results", [])
        has_next = detections_data.get("hasNextPage", False)
        total_count = detections_data.get("count", 0)
        # API may enforce a max limit lower than requested
        actual_limit = detections_data.get("limit", batch_size)

        # Parse results into Pydantic models
        detections = []
        for result in results:
            try:
                feed = OrcasoundFeedGQL(**result["feed"])
                detection = OrcasoundDetectionGQL(
                    id=result["id"],
                    timestamp=result["timestamp"],
                    source=result["source"],
                    category=result.get("category"),
                    feedId=result["feedId"],
                    playlistTimestamp=result["playlistTimestamp"],
                    playerOffset=result["playerOffset"],
                    description=result.get("description"),
                    listenerCount=result.get("listenerCount"),
                    visible=result.get("visible"),
                    feed=feed,
                )
                detections.append(detection)
            except Exception as e:
                logger.warning(f"Failed to parse detection {result.get('id')}: {e}")
                continue

        logger.info(
            f"Fetched batch at offset {offset}: {len(detections)} detections "
            f"(total: {total_count}, hasNext: {has_next}, limit: {actual_limit})"
        )

        return detections, has_next, total_count, actual_limit

    except Exception as e:
        logger.error(f"Error fetching batch at offset {offset}: {e}")
        raise


def fetch_all_detections(
    session,
    batch_size: int,
    include_machine: bool,
    category: Optional[str],
    feed_id: Optional[str],
    timestamp_gte: Optional[str],
    timestamp_lt: Optional[str],
    max_batches: Optional[int],
    delay: float,
) -> List[OrcasoundDetectionGQL]:
    """
    Fetch all detections with pagination.

    Args:
        session: HTTP session
        batch_size: Number of records per batch
        include_machine: Include machine detections
        category: Optional category filter
        feed_id: Optional feed ID filter
        timestamp_gte: Timestamp >= filter
        timestamp_lt: Timestamp < filter
        max_batches: Maximum number of batches (for testing)
        delay: Delay between requests

    Returns:
        List of all detections
    """
    all_detections = []
    offset = 0
    batch_num = 0
    actual_limit = batch_size  # Will be updated from API response

    # Log the filters being applied
    filters = []
    if not include_machine:
        filters.append("source=HUMAN")
    if category:
        filters.append(f"category={category}")
    if feed_id:
        filters.append(f"feed={feed_id}")
    if timestamp_gte:
        filters.append(f"from={timestamp_gte}")
    if timestamp_lt:
        filters.append(f"to={timestamp_lt}")
    logger.info(f"Querying API with filters: {', '.join(filters) if filters else 'none'}")

    while True:
        batch_num += 1

        # Check if we've reached max batches limit
        if max_batches and batch_num > max_batches:
            logger.info(f"Reached max batches limit: {max_batches}")
            break

        # Fetch batch
        try:
            detections, has_next, total_count, actual_limit = fetch_detections_batch(
                session,
                offset=offset,
                batch_size=batch_size,
                include_machine=include_machine,
                category=category,
                feed_id=feed_id,
                timestamp_gte=timestamp_gte,
                timestamp_lt=timestamp_lt,
            )
        except Exception as e:
            logger.error(f"Failed to fetch batch {batch_num}: {e}")
            break

        # Add detections
        all_detections.extend(detections)

        # Check if we're done
        if not detections or not has_next:
            logger.info(f"Fetched all detections in {batch_num} batches")
            break

        # Move to next page using actual limit from API (may be less than requested)
        offset += actual_limit

        # Delay before next request
        if delay > 0:
            time.sleep(delay)

    logger.info(f"Total detections fetched: {len(all_detections)}")
    return all_detections


def get_month_timestamp_range(
    detections: List[OrcasoundDetectionGQL],
) -> Tuple[str, str]:
    """
    Get min and max timestamps for a month in PST.

    Args:
        detections: List of detections for a month

    Returns:
        Tuple of (min_timestamp, max_timestamp) in PST
    """
    timestamps_pst = []
    for detection in detections:
        try:
            dt_pst = parse_timestamp_to_pst(detection.timestamp)
            timestamps_pst.append(dt_pst)
        except Exception:
            continue

    if not timestamps_pst:
        return ("", "")

    min_ts = min(timestamps_pst)
    max_ts = max(timestamps_pst)

    return (
        min_ts.strftime("%Y-%m-%dT%H:%M:%S"),
        max_ts.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def save_month_bucket(
    cache_dir: Path,
    month: str,
    detections: List[OrcasoundDetectionGQL],
) -> None:
    """
    Save month bucket to disk.

    Args:
        cache_dir: Cache directory
        month: Month string (YYYY-MM)
        detections: List of detections for the month
    """
    month_dir = get_month_dir(cache_dir, month)
    ensure_directory(month_dir)

    # Save raw detections as JSON
    detections_file = month_dir / "raw_detections.json"
    detections_data = [d.model_dump() for d in detections]
    write_json(detections_file, detections_data)

    # Write metadata
    metadata_file = month_dir / "metadata.jsonl"
    now_utc = datetime.now(pytz.UTC).isoformat()

    min_ts, max_ts = get_month_timestamp_range(detections)

    metadata = {
        "type": "save",
        "timestamp": now_utc,
        "month": month,
        "detection_count": len(detections),
        "min_timestamp_pst": min_ts,
        "max_timestamp_pst": max_ts,
    }
    write_jsonl_entry(metadata_file, metadata)

    logger.info(
        f"Saved {len(detections)} detections to {month_dir}/raw_detections.json"
    )

    # Update cache index
    update_cache_index(cache_dir, month, len(detections), min_ts, max_ts)


def log_fetch_start(cache_dir: Path, args: argparse.Namespace) -> None:
    """Log fetch start to fetch_log.jsonl."""
    ensure_directory(cache_dir)
    log_file = cache_dir / "fetch_log.jsonl"

    start_date, end_date = calculate_date_range(
        args.full, args.from_date, args.to_date, cache_dir
    )

    entry = {
        "type": "run_start",
        "timestamp": datetime.now(pytz.UTC).isoformat(),
        "mode": "full" if args.full else "incremental",
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "force_refresh": args.force_refresh,
        "include_machine": args.include_machine,
        "category_filter": args.category,
        "feed_filter": args.feed,
    }
    write_jsonl_entry(log_file, entry)


def log_fetch_complete(
    cache_dir: Path, months_updated: int, total_detections: int
) -> None:
    """Log fetch completion to fetch_log.jsonl."""
    log_file = cache_dir / "fetch_log.jsonl"

    entry = {
        "type": "run_complete",
        "timestamp": datetime.now(pytz.UTC).isoformat(),
        "months_updated": months_updated,
        "total_detections": total_detections,
    }
    write_jsonl_entry(log_file, entry)


def main():
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    logger.info("Orcasound GraphQL API Fetcher (Detection resource)")
    logger.info(f"Cache directory: {args.cache_dir}")

    # Calculate date range
    start_date, end_date = calculate_date_range(
        args.full, args.from_date, args.to_date, args.cache_dir
    )
    logger.info(f"Date range: {start_date} to {end_date}")

    # Get months in range
    months_in_range = get_months_in_range(start_date, end_date)
    logger.info(f"Months in range: {len(months_in_range)}")

    # Check cache
    cached_months = get_cached_months(args.cache_dir)
    logger.info(f"Already cached months: {len(cached_months)}")

    # Determine which months to fetch
    current_month = get_current_month_pst()
    months_to_fetch = []

    for month in months_in_range:
        is_cached = month in cached_months
        is_complete = is_month_complete(args.cache_dir, month)
        is_current = month == current_month

        if args.force_refresh:
            months_to_fetch.append(month)
            logger.info(f"  {month}: will fetch (force refresh)")
        elif is_cached and is_complete and not is_current:
            logger.info(f"  {month}: skipping (cached and complete)")
        else:
            months_to_fetch.append(month)
            reason = "current month" if is_current else "not cached or incomplete"
            logger.info(f"  {month}: will fetch ({reason})")

    if args.dry_run:
        logger.info(f"\n[DRY RUN] Would fetch {len(months_to_fetch)} months:")
        for month in months_to_fetch:
            logger.info(f"  - {month}")
        source_filter = (
            "human + machine" if args.include_machine else "human only"
        )
        logger.info(f"\nSource filter: {source_filter}")
        if args.category:
            logger.info(f"Category filter: {args.category}")
        if args.feed:
            logger.info(f"Feed filter: {args.feed}")
        logger.info("\nRe-run without --dry-run to fetch")
        return 0

    # Skip if all months are already cached
    if not months_to_fetch:
        logger.info("\nAll months already cached. Nothing to fetch.")
        logger.info("Use --force-refresh to re-fetch cached months.")
        return 0

    # Log fetch start
    log_fetch_start(args.cache_dir, args)

    # Create HTTP session
    session = create_http_session()

    # Fetch month by month
    logger.info(f"\nFetching {len(months_to_fetch)} month(s) from API...")

    months_saved = 0
    total_saved = 0
    pacific_tz = pytz.timezone("US/Pacific")

    for month in sorted(months_to_fetch):
        logger.info(f"\n--- Fetching {month} ---")

        # Get date range for this month
        month_start, month_end = get_month_date_range(month)

        # Convert to ISO timestamps for GraphQL filter
        # Start of month in PST, converted to UTC
        start_dt = pacific_tz.localize(
            datetime.combine(month_start, datetime.min.time())
        )
        timestamp_gte = start_dt.astimezone(pytz.UTC).strftime(
            "%Y-%m-%dT%H:%M:%S.000000Z"
        )

        # End of month + 2 days to capture PST month-end detections
        # (which may appear on the next UTC day due to timezone offset)
        end_dt = pacific_tz.localize(
            datetime.combine(month_end + timedelta(days=2), datetime.min.time())
        )
        timestamp_lt = end_dt.astimezone(pytz.UTC).strftime(
            "%Y-%m-%dT%H:%M:%S.000000Z"
        )

        try:
            detections = fetch_all_detections(
                session,
                batch_size=args.batch_size,
                include_machine=args.include_machine,
                category=args.category,
                feed_id=args.feed,
                timestamp_gte=timestamp_gte,
                timestamp_lt=timestamp_lt,
                max_batches=args.max_batches,
                delay=args.delay,
            )
        except Exception as e:
            logger.error(f"Failed to fetch {month}: {e}")
            continue  # Try next month

        if not detections:
            logger.info(f"No detections found for {month}")
            continue

        # Filter to only detections that belong to this PST month
        # (API query may include some from adjacent months due to UTC/PST offset)
        month_detections = [
            d for d in detections if extract_month_year_pst(d.timestamp) == month
        ]
        logger.info(
            f"Filtered to {len(month_detections)} detections for {month} "
            f"(from {len(detections)} fetched)"
        )

        if not month_detections:
            logger.info(f"No detections for {month} after PST filtering")
            continue

        # Save month bucket
        save_month_bucket(args.cache_dir, month, month_detections)
        months_saved += 1
        total_saved += len(month_detections)

    # Log completion
    log_fetch_complete(args.cache_dir, months_saved, total_saved)

    logger.info(f"\n✓ Fetch complete!")
    logger.info(f"  Months updated: {months_saved}")
    logger.info(f"  Total detections: {total_saved}")
    logger.info(f"  Cache directory: {args.cache_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

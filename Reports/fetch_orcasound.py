#!/usr/bin/env python3
"""Fetch orca detections from Orcasound GraphQL API with month-bucket caching."""

import argparse
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytz

from detection_types import (
    FlattenedOrcasoundDetection,
    OrcasoundDetection,
    OrcasoundListenerReport,
)
from fetch_utils import (
    calculate_date_range,
    create_http_session,
    ensure_directory,
    extract_month_year_pst,
    get_cached_months,
    get_current_month_pst,
    get_month_dir,
    get_months_in_range,
    is_month_complete,
    load_cache_index,
    parse_timestamp_to_pst,
    setup_logging,
    update_cache_index,
    write_json,
    write_jsonl_entry,
)
from orcasound_graphql import (
    CANDIDATES_QUERY,
    build_query_variables,
    execute_graphql_query,
)

logger = logging.getLogger(__name__)

GRAPHQL_ENDPOINT = "https://live.orcasound.net/graphiql"
DEFAULT_CACHE_DIR = Path("./cache/orcasound")
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
        help="Filter by feed slug",
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


def fetch_candidates_batch(
    session,
    offset: int,
    batch_size: int,
    category: Optional[str],
    feed_slug: Optional[str],
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Fetch a single batch of candidates via GraphQL.

    Args:
        session: HTTP session
        offset: Pagination offset
        batch_size: Number of records per batch
        category: Optional category filter
        feed_slug: Optional feed slug filter
        timeout: Request timeout

    Returns:
        Candidates response dictionary
    """
    variables = build_query_variables(offset, batch_size, category, feed_slug)

    try:
        data = execute_graphql_query(
            session, GRAPHQL_ENDPOINT, CANDIDATES_QUERY, variables, timeout
        )

        candidates_data = data.get("candidates", {})

        count = candidates_data.get("count", 0)
        has_next = candidates_data.get("hasNextPage", False)
        results = candidates_data.get("results", [])

        logger.info(
            f"Fetched batch at offset {offset}: {len(results)} candidates "
            f"(total: {count}, hasNext: {has_next})"
        )

        return candidates_data

    except Exception as e:
        logger.error(f"Error fetching batch at offset {offset}: {e}")
        raise


def fetch_all_candidates(
    session,
    batch_size: int,
    category: Optional[str],
    feed_slug: Optional[str],
    max_batches: Optional[int],
    delay: float,
) -> List[OrcasoundListenerReport]:
    """
    Fetch all candidates with pagination.

    Args:
        session: HTTP session
        batch_size: Number of records per batch
        category: Optional category filter
        feed_slug: Optional feed slug filter
        max_batches: Maximum number of batches to fetch (for testing)
        delay: Delay between requests

    Returns:
        List of all candidates
    """
    all_candidates = []
    offset = 0
    batch_num = 0

    while True:
        # Check if we've reached max batches limit
        if max_batches and batch_num >= max_batches:
            logger.info(f"Reached max batches limit: {max_batches}")
            break

        # Fetch batch
        try:
            candidates_data = fetch_candidates_batch(
                session, offset, batch_size, category, feed_slug
            )
        except Exception as e:
            logger.error(f"Failed to fetch batch at offset {offset}: {e}")
            # Save what we have so far
            break

        results = candidates_data.get("results", [])
        has_next = candidates_data.get("hasNextPage", False)

        # Parse candidates
        for result in results:
            try:
                candidate = OrcasoundListenerReport(**result)
                all_candidates.append(candidate)
            except Exception as e:
                logger.warning(f"Failed to parse candidate: {e}")
                continue

        # Check if we're done
        if not results or not has_next:
            logger.info(f"Fetched all candidates (total batches: {batch_num + 1})")
            break

        # Move to next batch
        offset += batch_size
        batch_num += 1

        # Delay before next request
        if delay > 0:
            time.sleep(delay)

    logger.info(f"Total candidates fetched: {len(all_candidates)}")
    return all_candidates


def flatten_and_filter_detections(
    candidates: List[OrcasoundListenerReport],
    include_machine: bool,
) -> List[Dict[str, Any]]:
    """
    Extract and filter detections from candidates.

    Args:
        candidates: List of candidate reports
        include_machine: Whether to include machine-reported detections

    Returns:
        List of flattened detection dictionaries
    """
    flattened = []
    human_count = 0
    machine_count = 0

    for candidate in candidates:
        for detection in candidate.detections:
            # Filter by source
            is_human = detection.source == "HUMAN"

            if not is_human:
                machine_count += 1
                if not include_machine:
                    continue

            if is_human:
                human_count += 1

            # Flatten: attach feed info from parent candidate
            flat_detection = {
                # Original detection fields
                "id": detection.id,
                "timestamp": detection.timestamp,
                "category": detection.category,
                "description": detection.description,
                "source": detection.source,
                "playlistTimestamp": detection.playlistTimestamp,
                "playerOffset": detection.playerOffset,
                "feedId": detection.feedId,
                "listenerCount": detection.listenerCount,
                "visible": detection.visible,
                "sourceIp": detection.sourceIp,
                # Denormalized from parent candidate
                "feed_name": candidate.feed.name,
                "feed_slug": candidate.feed.slug,
                "feed_node_name": candidate.feed.nodeName,
                "candidate_id": candidate.id,
            }

            flattened.append(flat_detection)

    logger.info(
        f"Filtered detections: {human_count} human, {machine_count} machine "
        f"(keeping {len(flattened)})"
    )

    return flattened


def group_detections_by_month(
    detections: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group detections by month (YYYY-MM in PST).

    Args:
        detections: List of flattened detections

    Returns:
        Dictionary mapping month string to list of detections
    """
    months: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for detection in detections:
        try:
            month = extract_month_year_pst(detection["timestamp"])
            months[month].append(detection)
        except Exception as e:
            logger.warning(
                f"Failed to parse timestamp for detection {detection['id']}: {e}"
            )
            continue

    logger.info(f"Grouped detections into {len(months)} months")
    for month, month_detections in sorted(months.items()):
        logger.info(f"  {month}: {len(month_detections)} detections")

    return dict(months)


def get_month_timestamp_range(
    detections: List[Dict[str, Any]],
) -> tuple[str, str]:
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
            dt_pst = parse_timestamp_to_pst(detection["timestamp"])
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
    detections: List[Dict[str, Any]],
) -> None:
    """
    Save month bucket to disk.

    Args:
        cache_dir: Cache directory
        month: Month string (YYYY-MM)
        detections: List of flattened detections for the month
    """
    month_dir = get_month_dir(cache_dir, month)
    ensure_directory(month_dir)

    # Save raw detections
    detections_file = month_dir / "raw_detections.json"
    write_json(detections_file, detections)

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

    logger.info("Orcasound GraphQL API Fetcher")
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

    # Log fetch start
    log_fetch_start(args.cache_dir, args)

    # Fetch all candidates
    logger.info(f"\nFetching candidates from GraphQL API...")
    session = create_http_session()

    try:
        all_candidates = fetch_all_candidates(
            session,
            args.batch_size,
            args.category,
            args.feed,
            args.max_batches,
            args.delay,
        )
    except Exception as e:
        logger.error(f"Failed to fetch candidates: {e}")
        return 1

    if not all_candidates:
        logger.warning("No candidates fetched")
        return 0

    # Flatten and filter detections
    logger.info(f"\nFlattening and filtering detections...")
    detections = flatten_and_filter_detections(
        all_candidates, args.include_machine
    )

    if not detections:
        logger.warning("No detections after filtering")
        return 0

    # Group by month
    logger.info(f"\nGrouping detections by month...")
    months_data = group_detections_by_month(detections)

    # Save month buckets
    logger.info(f"\nSaving month buckets...")
    months_saved = 0
    total_saved = 0

    for month in sorted(months_data.keys()):
        if month not in months_to_fetch:
            logger.info(f"Skipping {month} (not in fetch range)")
            continue

        month_detections = months_data[month]
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

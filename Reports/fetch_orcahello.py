#!/usr/bin/env python3
"""Fetch orca detections from OrcaHello API with month-bucket caching."""

import argparse
import logging
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytz
from detection_types import ApiResponseV1, Detection
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
    load_cache_index,
    parse_timestamp_to_pst,
    read_json,
    setup_logging,
    update_cache_index,
    write_json,
    write_jsonl_entry,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://aifororcasdetections.azurewebsites.net/api/detections"
DEFAULT_CACHE_DIR = Path("./cache/orcahello")
DEFAULT_RECORDS_PER_PAGE = 50
DEFAULT_DELAY = 0.5


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch orca detections from OrcaHello API with month-bucket caching"
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
        "--records-per-page",
        type=int,
        default=DEFAULT_RECORDS_PER_PAGE,
        help=f"Records per page (default: {DEFAULT_RECORDS_PER_PAGE})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay between requests in seconds (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Limit number of pages for testing",
    )

    # Filters
    parser.add_argument(
        "--location",
        type=str,
        help="Filter by location name (e.g., 'Bush Point')",
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


def fetch_page(
    session,
    page: int,
    records_per_page: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    location: Optional[str] = None,
    timeout: int = 30,
) -> Tuple[List[Detection], int]:
    """
    Fetch a single page of detections.

    Args:
        session: HTTP session
        page: Page number (1-indexed)
        records_per_page: Number of records per page
        date_from: Start date for filtering
        date_to: End date for filtering
        location: Optional location filter
        timeout: Request timeout in seconds

    Returns:
        Tuple of (detections list, total pages)
    """
    params = {
        "Page": page,
        "RecordsPerPage": records_per_page,
    }

    # Use date range filtering if dates are specified
    if date_from and date_to:
        params["Timeframe"] = "range"
        # API expects mm/dd/yyyy format
        params["DateFrom"] = date_from.strftime("%m/%d/%Y")
        params["DateTo"] = date_to.strftime("%m/%d/%Y")
    else:
        params["Timeframe"] = "all"

    if location:
        params["Location"] = location

    try:
        response = session.get(BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()

        data = response.json()

        # Parse response using Pydantic
        api_response = ApiResponseV1(detections=data)
        detections = api_response.detections

        # Get total pages from header (API uses lowercase headers)
        total_pages = 1
        if "totalAmountPages" in response.headers:
            total_pages = int(response.headers["totalAmountPages"])
        elif "totalamountpages" in response.headers:
            total_pages = int(response.headers["totalamountpages"])
        elif len(detections) == records_per_page:
            # If we got a full page, there might be more
            total_pages = page + 1

        logger.info(
            f"Fetched page {page}: {len(detections)} detections "
            f"(total pages: {total_pages})"
        )

        return detections, total_pages

    except Exception as e:
        logger.error(f"Error fetching page {page}: {e}")
        raise


def fetch_all_detections(
    session,
    records_per_page: int,
    date_from: Optional[date],
    date_to: Optional[date],
    location: Optional[str],
    max_pages: Optional[int],
    delay: float,
) -> List[Detection]:
    """
    Fetch all detections with pagination.

    Args:
        session: HTTP session
        records_per_page: Number of records per page
        date_from: Start date for filtering
        date_to: End date for filtering
        location: Optional location filter
        max_pages: Maximum number of pages to fetch (for testing)
        delay: Delay between requests

    Returns:
        List of all detections
    """
    all_detections = []
    page = 1
    total_pages = None

    # Log the date range being queried
    if date_from and date_to:
        logger.info(f"Querying API with date range: {date_from} to {date_to}")
    else:
        logger.info("Querying API for all historical data")

    while True:
        # Check if we've reached max pages limit
        if max_pages and page > max_pages:
            logger.info(f"Reached max pages limit: {max_pages}")
            break

        # Fetch page
        try:
            detections, detected_total = fetch_page(
                session, page, records_per_page, date_from, date_to, location
            )
        except Exception as e:
            logger.error(f"Failed to fetch page {page}: {e}")
            # Save what we have so far
            break

        # Update total pages if not set
        if total_pages is None:
            total_pages = detected_total

        # Add detections
        all_detections.extend(detections)

        # Check if we're done
        if len(detections) == 0:
            logger.info(f"No more detections on page {page}")
            break

        if page >= total_pages:
            logger.info(f"Fetched all {total_pages} pages")
            break

        # Delay before next request
        page += 1
        if delay > 0:
            time.sleep(delay)

    logger.info(f"Total detections fetched: {len(all_detections)}")
    return all_detections


def group_detections_by_month(
    detections: List[Detection],
) -> Dict[str, List[Detection]]:
    """
    Group detections by month (YYYY-MM in PST).

    Args:
        detections: List of detections

    Returns:
        Dictionary mapping month string to list of detections
    """
    months: Dict[str, List[Detection]] = defaultdict(list)

    for detection in detections:
        try:
            month = extract_month_year_pst(detection.timestamp)
            months[month].append(detection)
        except Exception as e:
            logger.warning(
                f"Failed to parse timestamp for detection {detection.id}: {e}"
            )
            continue

    logger.info(f"Grouped detections into {len(months)} months")
    for month, month_detections in sorted(months.items()):
        logger.info(f"  {month}: {len(month_detections)} detections")

    return dict(months)


def get_month_timestamp_range(
    detections: List[Detection],
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
    detections: List[Detection],
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

    # Save raw detections
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
        "location_filter": args.location,
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

    logger.info("OrcaHello API Fetcher")
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
        logger.info("\nRe-run without --dry-run to fetch")
        return 0

    # Skip if all months are already cached
    if not months_to_fetch:
        logger.info("\nAll months already cached. Nothing to fetch.")
        logger.info("Use --force-refresh to re-fetch cached months.")
        return 0

    # Log fetch start
    log_fetch_start(args.cache_dir, args)

    # Fetch month by month (only uncached months)
    logger.info(f"\nFetching {len(months_to_fetch)} month(s) from API...")
    session = create_http_session()

    months_saved = 0
    total_saved = 0

    for month in sorted(months_to_fetch):
        logger.info(f"\n--- Fetching {month} ---")

        # Get date range for this month
        month_start, month_end = get_month_date_range(month)

        # Extend end date by 2 days for API query:
        # - +1 day to capture PST month-end detections on next UTC day
        #   (e.g., PST June 30 11PM = UTC July 1 06:00)
        # - +1 more day because API DateTo is exclusive
        api_end_date = month_end + timedelta(days=2)

        try:
            detections = fetch_all_detections(
                session,
                args.records_per_page,
                month_start,
                api_end_date,
                args.location,
                args.max_pages,
                args.delay,
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
            d for d in detections
            if extract_month_year_pst(d.timestamp) == month
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

"""Shared utilities for fetching orca detection data from multiple APIs."""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytz
import requests
from urllib3.util.retry import Retry

from detection_types import CacheIndex, DateRange, MonthMetadata

# HTTP Session Management


def create_http_session(
    retries: int = 5, backoff_factor: float = 0.5
) -> requests.Session:
    """
    Create HTTP session with automatic retry logic.

    Args:
        retries: Number of retry attempts
        backoff_factor: Backoff factor for exponential backoff

    Returns:
        Configured requests.Session
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# Timezone Conversion


def parse_timestamp_to_pst(timestamp_str: str) -> datetime:
    """
    Parse UTC ISO timestamp to PST datetime.

    Args:
        timestamp_str: ISO format timestamp (e.g., '2025-08-14T01:55:02.48881Z')

    Returns:
        datetime in Pacific timezone
    """
    # Handle double timezone offset bug from API (e.g., +00:00+00:00)
    if "+00:00+00:00" in timestamp_str:
        timestamp_str = timestamp_str.replace("+00:00+00:00", "+00:00")

    # Remove fractional seconds for consistent parsing
    if "." in timestamp_str and ("+" in timestamp_str or "Z" in timestamp_str):
        # Split at decimal point, keep everything before it
        base_part = timestamp_str.split(".")[0]
        # Find timezone part (either Z or +/-)
        if "Z" in timestamp_str:
            clean_timestamp = base_part + "Z"
        elif "+" in timestamp_str:
            tz_part = "+" + timestamp_str.split("+")[-1]
            clean_timestamp = base_part + tz_part
        elif timestamp_str.count("-") > 2:  # Has negative timezone offset
            tz_part = "-" + timestamp_str.rsplit("-", 1)[-1]
            clean_timestamp = base_part + tz_part
        else:
            clean_timestamp = timestamp_str
    else:
        clean_timestamp = timestamp_str

    # Parse as ISO format with UTC offset
    if clean_timestamp.endswith("Z"):
        clean_timestamp = clean_timestamp.replace("Z", "+00:00")

    utc_dt = datetime.fromisoformat(clean_timestamp)

    # Convert to Pacific timezone (handles PST/PDT automatically)
    pacific_tz = pytz.timezone("US/Pacific")
    pst_dt = utc_dt.astimezone(pacific_tz)

    return pst_dt


def extract_month_year_pst(timestamp_str: str) -> str:
    """
    Extract YYYY-MM from UTC timestamp in PST timezone.

    Args:
        timestamp_str: ISO format timestamp

    Returns:
        Month string in format 'YYYY-MM'
    """
    dt = parse_timestamp_to_pst(timestamp_str)
    return dt.strftime("%Y-%m")


def get_current_month_pst() -> str:
    """
    Get current month in PST timezone.

    Returns:
        Current month string in format 'YYYY-MM'
    """
    pacific_tz = pytz.timezone("US/Pacific")
    now_pst = datetime.now(pacific_tz)
    return now_pst.strftime("%Y-%m")


# File I/O


def ensure_directory(path: Path) -> None:
    """
    Create directory recursively if it doesn't exist.

    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Any:
    """
    Read JSON file.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON data
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any, indent: int = 2) -> None:
    """
    Write JSON file with pretty printing.

    Args:
        path: Path to JSON file
        obj: Object to serialize
        indent: Indentation level
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)


def write_jsonl_entry(path: Path, entry: Dict[str, Any]) -> None:
    """
    Append JSONL entry to file.

    Args:
        path: Path to JSONL file
        entry: Dictionary to append
    """
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_jsonl_entries(path: Path) -> List[Dict[str, Any]]:
    """
    Read all JSONL entries from file.

    Args:
        path: Path to JSONL file

    Returns:
        List of parsed entries
    """
    entries = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


# Cache Management


def load_cache_index(cache_dir: Path) -> CacheIndex:
    """
    Load cache index or create new one.

    Args:
        cache_dir: Cache directory path

    Returns:
        CacheIndex object
    """
    index_path = cache_dir / "cache_index.json"

    if index_path.exists():
        data = read_json(index_path)
        return CacheIndex(**data)
    else:
        return CacheIndex(months={}, last_full_fetch=None)


def save_cache_index(cache_dir: Path, cache_index: CacheIndex) -> None:
    """
    Save cache index to disk.

    Args:
        cache_dir: Cache directory path
        cache_index: CacheIndex object to save
    """
    ensure_directory(cache_dir)
    index_path = cache_dir / "cache_index.json"
    write_json(index_path, cache_index.model_dump())


def update_cache_index(
    cache_dir: Path,
    month: str,
    detection_count: int,
    min_timestamp: str,
    max_timestamp: str,
) -> None:
    """
    Update cache index for a month.

    Args:
        cache_dir: Cache directory path
        month: Month string (YYYY-MM)
        detection_count: Number of detections in month
        min_timestamp: Earliest timestamp in PST
        max_timestamp: Latest timestamp in PST
    """
    cache_index = load_cache_index(cache_dir)
    current_month = get_current_month_pst()

    # Check if this is the first fetch for this month
    now_utc = datetime.now(pytz.UTC).isoformat()
    if month in cache_index.months:
        first_fetch = cache_index.months[month].first_fetch
    else:
        first_fetch = now_utc

    # Create month metadata
    cache_index.months[month] = MonthMetadata(
        first_fetch=first_fetch,
        last_updated=now_utc,
        detection_count=detection_count,
        date_range=DateRange(min_pst=min_timestamp, max_pst=max_timestamp),
        complete=(month != current_month),  # Current month is always incomplete
    )

    save_cache_index(cache_dir, cache_index)


def get_cached_months(cache_dir: Path) -> Set[str]:
    """
    Get set of already cached months.

    Args:
        cache_dir: Cache directory path

    Returns:
        Set of month strings (YYYY-MM)
    """
    cache_index = load_cache_index(cache_dir)
    return set(cache_index.months.keys())


def is_month_complete(cache_dir: Path, month: str) -> bool:
    """
    Check if month is complete (not current month).

    Args:
        cache_dir: Cache directory path
        month: Month string (YYYY-MM)

    Returns:
        True if month is complete and cached
    """
    cache_index = load_cache_index(cache_dir)

    if month not in cache_index.months:
        return False

    return cache_index.months[month].complete


def get_month_dir(cache_dir: Path, month: str) -> Path:
    """
    Get directory path for a month bucket.

    Args:
        cache_dir: Cache directory path
        month: Month string (YYYY-MM)

    Returns:
        Path to month directory
    """
    return cache_dir / month


# Date Range Calculations


def calculate_date_range(
    full_fetch: bool,
    from_date: Optional[date],
    to_date: Optional[date],
    cache_dir: Optional[Path] = None,
) -> Tuple[date, date]:
    """
    Calculate date range to fetch based on arguments and cache.

    Args:
        full_fetch: Whether to fetch all historical data
        from_date: Start date (if specified)
        to_date: End date (if specified)
        cache_dir: Cache directory (for determining last fetch)

    Returns:
        Tuple of (start_date, end_date)
    """
    today = date.today()

    if full_fetch:
        # Fetch all historical data (start from 2019 when Orcasound began)
        return (date(2019, 1, 1), today)

    if from_date:
        # Use specified date range
        end = to_date or today
        return (from_date, end)

    # Default: fetch last 30 days
    return (today - timedelta(days=30), today)


def get_months_in_range(start_date: date, end_date: date) -> List[str]:
    """
    Get list of YYYY-MM strings in date range.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        List of month strings in range
    """
    months = []
    current = start_date.replace(day=1)
    end = end_date.replace(day=1)

    while current <= end:
        months.append(current.strftime("%Y-%m"))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return months


def get_month_date_range(month: str) -> Tuple[date, date]:
    """
    Get start and end dates for a month string.

    Args:
        month: Month string in format 'YYYY-MM'

    Returns:
        Tuple of (first_day, last_day) of the month
    """
    import calendar

    year, month_num = map(int, month.split("-"))
    first_day = date(year, month_num, 1)
    last_day_num = calendar.monthrange(year, month_num)[1]
    last_day = date(year, month_num, last_day_num)
    return (first_day, last_day)


# Logging


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging.

    Args:
        verbose: Enable verbose (DEBUG) logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

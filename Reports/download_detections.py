#!/usr/bin/env python3
"""Download detection WAV and spectrogram files from OrcaHello cache.

Organizes downloads into subfolders by moderation status:
  - positive: reviewed=True and found='yes' (confirmed whale calls)
  - false_positive: reviewed=True and found='No'/'no' (not whales)
  - unmoderated: reviewed=False (pending review)
  - unknown: reviewed=True but found='don't know' or other

Directory structure:
  output_dir/
    YYYY-MM/
      positive/
        <detection_id>.wav
        <detection_id>.png
      false_positive/
        ...
      unmoderated/
        ...
"""

import argparse
import io
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import requests
import soundfile as sf
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("./fetch_cache/orcahello")
DEFAULT_OUTPUT_DIR = Path("./detection_downloads")
DEFAULT_WORKERS = 8


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_http_session() -> requests.Session:
    """Create HTTP session with retry logic."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_current_month() -> str:
    """Get current month as YYYY-MM."""
    return datetime.now().strftime("%Y-%m")


def get_last_month() -> str:
    """Get last month as YYYY-MM."""
    now = datetime.now()
    if now.month == 1:
        return f"{now.year - 1}-12"
    return f"{now.year}-{now.month - 1:02d}"


def parse_month(month_str: str) -> Tuple[int, int]:
    """Parse YYYY-MM string to (year, month)."""
    parts = month_str.split("-")
    return int(parts[0]), int(parts[1])


def get_months_in_range(start_month: str, end_month: str) -> List[str]:
    """Get list of months in range (inclusive)."""
    start_year, start_m = parse_month(start_month)
    end_year, end_m = parse_month(end_month)

    months = []
    year, month = start_year, start_m
    while (year, month) <= (end_year, end_m):
        months.append(f"{year}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def classify_detection(detection: dict) -> str:
    """Classify detection into category based on moderation status.

    Returns one of: 'positive', 'false_positive', 'unmoderated', 'unknown'
    """
    reviewed = detection.get("reviewed", False)
    found = detection.get("found", "").lower()

    if not reviewed:
        return "unmoderated"

    if found == "yes":
        return "positive"
    elif found == "no":
        return "false_positive"
    else:
        return "unknown"


def load_detections(cache_dir: Path, month: str) -> List[dict]:
    """Load detections from cache for a month."""
    month_dir = cache_dir / month
    detections_file = month_dir / "raw_detections.json"

    if not detections_file.exists():
        logger.warning(f"No detections file for {month}: {detections_file}")
        return []

    with open(detections_file, "r") as f:
        return json.load(f)


def download_wav_as_flac(
    session: requests.Session,
    url: str,
    output_path: Path,
    timeout: int = 30,
) -> bool:
    """Download WAV from URL, convert to FLAC in memory, write to output_path.

    Returns True on success, False on failure.
    """
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()

        # Read WAV from response bytes into memory
        wav_bytes = io.BytesIO(response.content)
        data, samplerate = sf.read(wav_bytes)

        # Write FLAC to disk
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, data, samplerate, format="FLAC")

        return True
    except Exception as e:
        logger.error(f"Failed to download/convert {url}: {e}")
        return False


def download_png(
    session: requests.Session,
    url: str,
    output_path: Path,
    timeout: int = 30,
) -> bool:
    """Download PNG from URL to output_path.

    Returns True on success, False on failure.
    """
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def download_detection(
    detection: dict,
    output_dir: Path,
    month: str,
    download_wav: bool,
    download_spectrogram: bool,
    categories: Optional[List[str]],
    dry_run: bool,
) -> Tuple[str, bool]:
    """Download a single detection's files.

    Returns (status_message, success_flag)
    """
    det_id = detection.get("id", "unknown")
    category = classify_detection(detection)

    # Filter by category if specified
    if categories and category not in categories:
        return ("skipped", False)

    month_output = output_dir / month / category

    # Prepare file paths
    audio_url = detection.get("audioUri", "")
    spec_url = detection.get("spectrogramUri", "")

    wav_stem = audio_url.rsplit("/", 1)[-1].rsplit(".", 1)[0] if audio_url else det_id
    png_stem = spec_url.rsplit("/", 1)[-1].rsplit(".", 1)[0] if spec_url else det_id

    flac_name = f"{wav_stem}--{det_id}.flac"
    png_name = f"{png_stem}--{det_id}.png"

    flac_path = month_output / flac_name
    png_path = month_output / png_name

    if dry_run:
        return (f"[DRY RUN] {flac_name}", True)

    # Create session for this thread
    session = create_http_session()

    # Download WAV as FLAC
    if download_wav and audio_url:
        if flac_path.exists():
            logger.debug(f"Skipping existing: {flac_name}")
        else:
            if download_wav_as_flac(session, audio_url, flac_path):
                logger.debug(f"Downloaded: {flac_name}")
            else:
                return (f"Failed WAV: {flac_name}", False)

    # Download spectrogram
    if download_spectrogram and spec_url:
        if png_path.exists():
            logger.debug(f"Skipping existing: {png_name}")
        else:
            if download_png(session, spec_url, png_path):
                logger.debug(f"Downloaded: {png_name}")
            else:
                return (f"Failed PNG: {png_name}", False)

    return ("ok", True)


def process_month(
    cache_dir: Path,
    output_dir: Path,
    month: str,
    download_wav: bool,
    download_spectrogram: bool,
    categories: Optional[List[str]],
    workers: int,
    dry_run: bool,
) -> Tuple[int, int, int]:
    """Process detections for a single month using batched parallel downloads.

    Returns (processed_count, downloaded_count, skipped_count)
    """
    detections = load_detections(cache_dir, month)
    if not detections:
        return 0, 0, 0

    processed = 0
    downloaded = 0
    skipped = 0

    # Process in batches with threadpool
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all detections
        futures = []
        for detection in detections:
            future = executor.submit(
                download_detection,
                detection,
                output_dir,
                month,
                download_wav,
                download_spectrogram,
                categories,
                dry_run,
            )
            futures.append(future)

        # Collect results with progress bar
        for future in tqdm(as_completed(futures), total=len(futures), desc=month, unit="detection"):
            status, success = future.result()
            processed += 1
            if status == "skipped":
                skipped += 1
            elif success:
                downloaded += 1

    return processed, downloaded, skipped


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Download detection WAV and spectrogram files from OrcaHello cache"
    )

    # Cache/output directories
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"OrcaHello cache directory (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for downloads (default: {DEFAULT_OUTPUT_DIR})",
    )

    # Month range selection
    parser.add_argument(
        "--month",
        type=str,
        help="Single month to process (YYYY-MM). Default: last month",
    )
    parser.add_argument(
        "--from-month",
        type=str,
        help="Start month for range (YYYY-MM)",
    )
    parser.add_argument(
        "--to-month",
        type=str,
        help="End month for range (YYYY-MM)",
    )

    # Download options
    parser.add_argument(
        "--no-wav",
        action="store_true",
        help="Skip downloading WAV files",
    )
    parser.add_argument(
        "--no-spec",
        action="store_true",
        help="Skip downloading spectrogram PNG files",
    )

    # Category filter
    parser.add_argument(
        "--category",
        type=str,
        action="append",
        choices=["positive", "false_positive", "unmoderated", "unknown"],
        help="Filter by category (can specify multiple). Default: all categories",
    )

    # Parallelism options
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of parallel download threads (default: {DEFAULT_WORKERS})",
    )

    # Output options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without downloading",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    logger.info("OrcaHello Detection Downloader")
    logger.info(f"Cache directory: {args.cache_dir}")
    logger.info(f"Output directory: {args.output_dir}")

    # Validate cache directory
    if not args.cache_dir.exists():
        logger.error(f"Cache directory does not exist: {args.cache_dir}")
        return 1

    # Determine month range
    if args.month:
        months = [args.month]
    elif args.from_month and args.to_month:
        months = get_months_in_range(args.from_month, args.to_month)
    elif args.from_month:
        months = get_months_in_range(args.from_month, get_current_month())
    elif args.to_month:
        months = [args.to_month]
    else:
        # Default: last month
        months = [get_last_month()]

    logger.info(f"Months to process: {months}")

    # Download options
    download_wav = not args.no_wav
    download_spectrogram = not args.no_spec
    categories = args.category  # None means all

    if not download_wav and not download_spectrogram:
        logger.error("Nothing to download: both --no-wav and --no-spec specified")
        return 1

    logger.info(f"Download WAV (as FLAC): {download_wav}")
    logger.info(f"Download spectrogram: {download_spectrogram}")
    if categories:
        logger.info(f"Categories: {categories}")
    else:
        logger.info("Categories: all")
    logger.info(f"Workers: {args.workers}")

    if args.dry_run:
        logger.info("[DRY RUN MODE]")

    total_processed = 0
    total_downloaded = 0
    total_skipped = 0

    for month in months:
        logger.info(f"\n--- Processing {month} ---")

        processed, downloaded, skipped = process_month(
            cache_dir=args.cache_dir,
            output_dir=args.output_dir,
            month=month,
            download_wav=download_wav,
            download_spectrogram=download_spectrogram,
            categories=categories,
            workers=args.workers,
            dry_run=args.dry_run,
        )

        logger.info(f"{month}: processed={processed}, downloaded={downloaded}, skipped={skipped}")
        total_processed += processed
        total_downloaded += downloaded
        total_skipped += skipped

    logger.info(f"\n{'[DRY RUN] ' if args.dry_run else ''}Download complete!")
    logger.info(f"  Total processed: {total_processed}")
    logger.info(f"  Total downloaded: {total_downloaded}")
    logger.info(f"  Total skipped (filtered): {total_skipped}")
    logger.info(f"  Output directory: {args.output_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

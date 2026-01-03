import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pytz
import requests
from detection_types import ApiResponseV1, Detection
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_START_PAGE = 1


def create_http_session(
    total_retries: int = 5, backoff_factor: float = 0.5
) -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(
        total=total_retries,
        read=total_retries,
        connect=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_page(
    session: requests.Session,
    base_url: str,
    page_number: int,
    timeframe: str,
    records_per_page: int,
    timeout: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    params = {
        "Page": page_number,
        "Timeframe": timeframe,
        "RecordsPerPage": records_per_page,
    }
    headers = {"accept": "application/json"}
    response = session.get(base_url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    # Ensure list
    if isinstance(data, dict):
        # In case API sometimes wraps with an object
        data = data.get("items", [])
    if not isinstance(data, list):
        raise ValueError("Unexpected response format: expected a JSON list")
    return data, {k.lower(): v for k, v in response.headers.items()}


def ensure_directory(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_jsonl_entry(path: str, entry: Dict[str, Any]) -> None:
    """Write a single JSON object as a line to a JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_jsonl_entries(path: str) -> List[Dict[str, Any]]:
    """Read all JSONL entries from a file."""
    entries = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


def is_completed_run(metadata_file: str) -> bool:
    """Check if a run has already been completed by looking for a 'complete' entry."""
    entries = read_jsonl_entries(metadata_file)
    return any(entry.get("type") == "complete" for entry in entries)


def get_existing_pages(api_responses_dir: str) -> set:
    """Get set of page numbers that already exist."""
    existing_pages = set()
    if os.path.exists(api_responses_dir):
        for filename in os.listdir(api_responses_dir):
            if filename.startswith("detections_page_") and filename.endswith(".json"):
                try:
                    page_num = int(
                        filename.replace("detections_page_", "").replace(".json", "")
                    )
                    existing_pages.add(page_num)
                except ValueError:
                    continue
    return existing_pages


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def detections_to_dataframe(detections: List[Detection]) -> pd.DataFrame:
    """Convert detection objects to DataFrame format, flattening location and excluding annotations.
    Adds PST timestamp columns based on the UTC timestamp.
    """
    csv_data = []

    # Define Pacific timezone
    pacific_tz = pytz.timezone("US/Pacific")

    for detection in detections:
        # Convert detection to dict and flatten location
        detection_dict = detection.model_dump()

        # Remove annotations field
        detection_dict.pop("annotations", None)

        # Flatten location fields
        location = detection_dict.pop("location", {})
        if location:
            detection_dict["location.name"] = location.get("name", "")
            detection_dict["location.longitude"] = location.get("longitude", 0.0)
            detection_dict["location.latitude"] = location.get("latitude", 0.0)
        else:
            detection_dict["location.name"] = ""
            detection_dict["location.longitude"] = 0.0
            detection_dict["location.latitude"] = 0.0

        # Parse timestamp and add PST columns
        timestamp_str = detection_dict.get("timestamp", "")
        if timestamp_str:
            # Parse UTC timestamp e.g. '2025-08-14T01:55:02.48881Z' -> '2025-08-14T01:55:02+00:00'
            timestamp_str = timestamp_str.rsplit(".", 1)[0] + "Z"  # remove frac seconds
            utc_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # Convert to Pacific time
            pst_dt = utc_dt.astimezone(pacific_tz)

            # Extract PST components
            detection_dict["date_pst"] = pst_dt.strftime("%Y-%m-%d")
            detection_dict["time_pst"] = pst_dt.strftime("%H:%M")
            detection_dict["year_month_pst"] = pst_dt.strftime("%Y-%m")
            detection_dict["year_pst"] = pst_dt.strftime("%Y")
            detection_dict["month_pst"] = pst_dt.strftime("%m")
            detection_dict["hour_pst"] = pst_dt.strftime("%H")
        else:
            # If no timestamp, set empty values
            detection_dict["date_pst"] = ""
            detection_dict["time_pst"] = ""
            detection_dict["year_month_pst"] = ""
            detection_dict["year_pst"] = ""
            detection_dict["month_pst"] = ""
            detection_dict["hour_pst"] = ""

        csv_data.append(detection_dict)

    # Create and return DataFrame
    df = pd.DataFrame(csv_data)
    return df


def aggregate_detections_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate detections by location and date with various counts.

    Args:
        df: DataFrame with detection data

    Returns:
        Aggregated DataFrame grouped by location.name and date_pst
    """
    # Group by location and date
    grouped = df.groupby(["location.name", "date_pst"])

    # Create aggregation dictionary
    agg_data = []

    for (location_name, date_pst), group in grouped:
        year_month_pst = date_pst.rsplit("-", 1)[0]
        year_pst, month_pst = year_month_pst.rsplit("-", 1)

        # Basic counts
        total_count = len(group)

        # Moderation counts
        count_moderated = len(group[group["reviewed"]])
        count_unmoderated = len(group[~group["reviewed"]])

        # For positive/false positive, only count reviewed records
        reviewed_group = group[group["reviewed"]]
        count_positive = len(reviewed_group[reviewed_group["found"] == "yes"])
        count_false_positive = len(reviewed_group[reviewed_group["found"] != "yes"])

        # Colon-separated list of IDs
        ids_list = ";".join(group["id"].astype(str))
        times_list = ";".join(group["time_pst"].astype(str))

        agg_row = {
            "location.name": location_name,
            "date_pst": date_pst,
            "year_month_pst": year_month_pst,
            "year_pst": year_pst,
            "month_pst": month_pst,
            "ids": ids_list,
            "times_pst": times_list,
            "count": total_count,
            "count_moderated": count_moderated,
            "count_unmoderated": count_unmoderated,
            "count_positive": count_positive,
            "count_false_positive": count_false_positive,
        }

        agg_data.append(agg_row)

    # Create aggregated DataFrame
    agg_df = pd.DataFrame(agg_data)

    # Sort by location and date
    agg_df = agg_df.sort_values(["location.name", "date_pst"]).reset_index(drop=True)

    return agg_df


def dump_api_responses(
    base_url: str,
    timeframe: str,
    records_per_page: int,
    max_pages: Optional[int],
    api_responses_dir: str,
    metadata_file: str,
    delay: float = 0.0,
) -> List[Detection]:
    """Fetch and save all API responses with streaming metadata."""
    session = create_http_session()

    # Generate timestamp for this run
    timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    combined_detections_file = os.path.join(api_responses_dir, "detections_all.json")

    # Check if run is already completed
    if is_completed_run(metadata_file) and os.path.exists(combined_detections_file):
        print(f"Run already completed, skipping. Check {metadata_file} for details.")
        combined_detections = [
            Detection.model_validate(d)
            for d in json.load(open(combined_detections_file, "r", encoding="utf-8"))
        ]
        return combined_detections

    # Get existing pages to skip
    existing_pages = get_existing_pages(api_responses_dir)
    if existing_pages:
        print(f"Found {len(existing_pages)} existing pages: {sorted(existing_pages)}")

    # Write initial metadata entry only if it doesn't exist
    entries = read_jsonl_entries(metadata_file)
    if not any(entry.get("type") == "start" for entry in entries):
        initial_metadata = {
            "type": "start",
            "base_url": base_url,
            "timeframe": timeframe,
            "records_per_page": records_per_page,
            "started_utc": timestamp_slug,
            "start_page": DEFAULT_START_PAGE,
            "max_pages": max_pages,
        }
        write_jsonl_entry(metadata_file, initial_metadata)
        print(f"Started metadata logging -> {metadata_file}")
    else:
        print(f"Using existing metadata file -> {metadata_file}")

    current_page = DEFAULT_START_PAGE
    total_pages_from_header: Optional[int] = None
    total_records_from_header: Optional[int] = None
    combined: List[Detection] = []

    while True:
        if max_pages is not None and current_page > max_pages:
            print("Reached --max-pages limit; stopping.")
            break

        # Load existing page if it exists
        if current_page in existing_pages:
            page_file = os.path.join(
                api_responses_dir, f"detections_page_{current_page}.json"
            )
            try:
                with open(page_file, "r", encoding="utf-8") as f:
                    page_items = json.load(f)
                api_response = ApiResponseV1(detections=page_items)
                combined.extend(api_response.detections)
                print(
                    f"Loaded existing page {current_page} with {len(api_response.detections)} records"
                )
            except Exception as e:
                print(f"Error loading existing page {current_page}: {e}")
                break
            current_page += 1
            continue

        try:
            page_items, headers = fetch_page(
                session=session,
                base_url=base_url,
                page_number=current_page,
                timeframe=timeframe,
                records_per_page=records_per_page,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.HTTPError as http_err:
            print(f"HTTP error on page {current_page}: {http_err}", file=sys.stderr)
            break
        except Exception as ex:
            print(f"Error on page {current_page}: {ex}", file=sys.stderr)
            break

        if total_pages_from_header is None:
            total_pages_from_header = parse_int(headers.get("totalamountpages"))
            total_records_from_header = parse_int(headers.get("totalnumberrecords"))

            # Log server header information
            if total_pages_from_header is not None:
                header_info = {
                    "type": "server_info",
                    "total_pages_header": total_pages_from_header,
                    "total_records_header": total_records_from_header,
                    "page": current_page,
                }
                write_jsonl_entry(metadata_file, header_info)
                print(f"Server reports total pages: {total_pages_from_header}")

        # Convert to Detection objects and validate
        api_response = ApiResponseV1(detections=page_items)
        detections = api_response.detections

        page_file = os.path.join(
            api_responses_dir, f"detections_page_{current_page}.json"
        )
        write_json(page_file, page_items)
        print(
            f"Saved page {current_page} with {len(detections)} records -> {page_file}"
        )

        combined.extend(detections)

        # Log page completion
        page_info = {
            "type": "page_complete",
            "page": current_page,
            "count": len(detections),
            "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        }
        write_jsonl_entry(metadata_file, page_info)

        # Decide to continue or stop
        if total_pages_from_header is not None:
            if current_page >= total_pages_from_header:
                print("Fetched all pages as per header; stopping.")
                break
        else:
            # Fallback: stop when we hit an empty page
            if len(page_items) == 0:
                print("Received empty page; stopping.")
                break

        current_page += 1
        if delay > 0:
            time.sleep(delay)

    # Save combined results
    # Convert Detection objects back to dict for JSON serialization
    combined_dicts = [detection.model_dump() for detection in combined]
    write_json(combined_detections_file, combined_dicts)
    print(
        f"Saved combined results ({len(combined)} records) -> {combined_detections_file}"
    )

    # Write completion metadata entry
    completion_metadata = {
        "type": "complete",
        "finished_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "total_pages_fetched": current_page - 1,
        "total_records_fetched": len(combined),
        "total_pages_header": total_pages_from_header,
        "total_records_header": total_records_from_header,
    }
    write_jsonl_entry(metadata_file, completion_metadata)
    print(f"Completed metadata logging -> {metadata_file}")

    return combined


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch all paginated detection entries and save locally."
    )
    parser.add_argument(
        "--timeframe",
        default="24h",
        help="Timeframe query parameter (e.g., 3h, 6h, 24h, 1w, 30d, range, all).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=30.0,
        help="Optional delay (seconds) between page requests to be polite.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.getcwd(), "downloads"),
        help="Directory to save JSON output files.",
    )
    parser.add_argument(
        "--base-url",
        default="https://aifororcasdetections.azurewebsites.net/api/detections",
        help="Base API URL for detections endpoint.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional hard cap on number of pages to fetch (in addition to server-provided total).",
    )
    parser.add_argument(
        "--records-per-page",
        type=int,
        default=100,
        help="Number of records per page to request.",
    )

    args = parser.parse_args()

    # timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d")
    # dump_name_suffix = f"{args.timeframe}_{timestamp_slug}"
    dump_name_suffix = "all_20250815"
    run_dir_name = f"detections_{dump_name_suffix}"
    output_dir = os.path.join(args.output_dir, run_dir_name)
    api_responses_dir = os.path.join(output_dir, "api_responses")
    detections_dump_dir = os.path.join(output_dir, "detections_dump")

    ensure_directory(output_dir)
    ensure_directory(api_responses_dir)
    ensure_directory(detections_dump_dir)

    print(f"Saving outputs to: {output_dir}")
    print(f"API responses will be saved to: {api_responses_dir}")
    print(f"Detections dump directory created: {detections_dump_dir}")

    # Initialize metadata JSONL file
    metadata_file = os.path.join(output_dir, "metadata.jsonl")

    # Fetch all API responses
    detections_combined = dump_api_responses(
        base_url=args.base_url,
        timeframe=args.timeframe,
        records_per_page=args.records_per_page,
        max_pages=args.max_pages,
        api_responses_dir=api_responses_dir,
        metadata_file=metadata_file,
        delay=args.delay,
    )

    if detections_combined:
        # Export detections to CSV
        csv_file = os.path.join(
            detections_dump_dir, f"detections_{dump_name_suffix}.csv"
        )
        df = detections_to_dataframe(detections_combined)
        df.to_csv(csv_file, index=False, encoding="utf-8")
        print(f"Saved CSV with {len(detections_combined)} records -> {csv_file}")

        # Export daily aggregated data
        daily_agg_file = os.path.join(
            detections_dump_dir, f"detections_{dump_name_suffix}_daily_aggregated.csv"
        )
        agg_df = aggregate_detections_daily(df)
        agg_df.to_csv(daily_agg_file, index=False, encoding="utf-8")
        print(
            f"Saved daily aggregated CSV with {len(agg_df)} records -> {daily_agg_file}"
        )
    else:
        print("No detections to export to CSV")


if __name__ == "__main__":
    main()

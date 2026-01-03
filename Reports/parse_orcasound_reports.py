#!/usr/bin/env python3
"""
Script to process Orcasound listener reports JSON files.

This script:
1. Validates JSON data into Pydantic objects
2. Flattens OrcasoundDetection entries with detection prefix
3. Creates DataFrame with important fields and saves to CSV
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytz
from detection_types import OrcasoundListenerReport


def load_and_validate_json(file_path: Path) -> List[OrcasoundListenerReport]:
    """Load JSON file and validate into Pydantic objects."""
    print(f"Loading and validating: {file_path}")

    with open(file_path, "r") as f:
        data = json.load(f)

    # Extract the candidates results
    candidates_results = data.get("data", {}).get("candidates", {}).get("results", [])

    # Validate each result into OrcasoundListenerReport
    validated_reports = []
    for i, result in enumerate(candidates_results):
        try:
            report = OrcasoundListenerReport(**result)
            validated_reports.append(report)
        except Exception as e:
            print(f"Warning: Failed to validate result {i}: {e}")
            continue

    print(f"Successfully validated {len(validated_reports)} reports")
    return validated_reports


def flatten_detections(reports: List[OrcasoundListenerReport]) -> List[Dict[str, Any]]:
    """Flatten OrcasoundDetection entries into individual records."""
    flattened = []

    for report in reports:
        # Get all fields from report except category and detections
        report_fields = report.model_dump()
        report_fields.pop("category", None)  # Remove category to avoid clash
        report_fields.pop("detections", None)  # Remove detections as we'll flatten them

        for detection in report.detections:
            # Create flattened entry
            entry = {}

            # Add detection fields with detection prefix
            detection_dict = detection.model_dump()
            for key, value in detection_dict.items():
                entry[f"detection.{key}"] = value

            # Add report fields (except category and detections)
            for key, value in report_fields.items():
                if key == "feed":
                    # Flatten feed fields
                    for feed_key, feed_value in value.items():
                        entry[f"feed.{feed_key}"] = feed_value
                else:
                    entry[f"report.{key}"] = value

            flattened.append(entry)

    print(f"Flattened into {len(flattened)} detection entries")
    return flattened


def parse_timestamp_to_pst(timestamp_str: str) -> Dict[str, str]:
    """Parse UTC timestamp and extract PST date/time components."""
    pst_fields = {}

    if timestamp_str:
        try:
            # Handle timestamp format (remove fractional seconds if present)
            # e.g. '2025-08-14T01:55:02.48881Z' -> '2025-08-14T01:55:02+00:00'
            clean_timestamp = (
                timestamp_str.rsplit(".", 1)[0] + "Z"
                if "." in timestamp_str
                else timestamp_str
            )
            utc_dt = datetime.fromisoformat(clean_timestamp.replace("Z", "+00:00"))

            # Convert to Pacific time (handles PST/PDT automatically)
            pacific_tz = pytz.timezone("America/Los_Angeles")
            pst_dt = utc_dt.astimezone(pacific_tz)

            # Extract PST components
            pst_fields["detection.date_pst"] = pst_dt.strftime("%Y-%m-%d")
            pst_fields["detection.time_pst"] = pst_dt.strftime("%H:%M")
            pst_fields["detection.year_month_pst"] = pst_dt.strftime("%Y-%m")
            pst_fields["detection.year_pst"] = pst_dt.strftime("%Y")
            pst_fields["detection.month_pst"] = pst_dt.strftime("%m")
            pst_fields["detection.hour_pst"] = pst_dt.strftime("%H")

        except Exception as e:
            print(f"Warning: Failed to parse timestamp '{timestamp_str}': {e}")
            # Set empty values for failed parsing
            for field in [
                "detection.date_pst",
                "detection.time_pst",
                "detection.year_month_pst",
                "detection.year_pst",
                "detection.month_pst",
                "detection.hour_pst",
            ]:
                pst_fields[field] = None

    return pst_fields


def create_dataframe(flattened_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """Create DataFrame with important fields."""

    # Define the important fields we want to extract
    important_fields = [
        "detection.timestamp",
        "detection.playlistTimestamp",
        "detection.description",
        "detection.source",
        "detection.id",
        "detection.category",
        "feed.name",
        "feed.id",
        "report.detectionCount",
        "report.id",
        # PST timestamp fields
        "detection.date_pst",
        "detection.time_pst",
        "detection.year_month_pst",
        "detection.year_pst",
        "detection.month_pst",
        "detection.hour_pst",
    ]

    # Extract the important fields
    df_data = []
    for entry in flattened_data:
        row = {}
        for field in important_fields:
            row[field] = entry.get(field)

        # Parse timestamp and add PST fields
        timestamp_str = entry.get("detection.timestamp", "")
        pst_fields = parse_timestamp_to_pst(timestamp_str)
        row.update(pst_fields)

        df_data.append(row)

    df = pd.DataFrame(df_data)
    print(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
    return df


def aggregate_reports_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate detections by feed and date with various counts.

    Args:
        df: DataFrame with detection data

    Returns:
        Aggregated DataFrame grouped by feed.name and detection.date_pst
    """
    # Group by feed and date
    grouped = df.groupby(["feed.name", "detection.date_pst"])

    # Create aggregation data
    agg_data = []

    for (feed_name, date_pst), group in grouped:
        # Extract date components
        year_month_pst = date_pst.rsplit("-", 1)[0] if date_pst else ""
        if year_month_pst:
            year_pst, month_pst = year_month_pst.rsplit("-", 1)
        else:
            year_pst, month_pst = "", ""

        # Basic counts
        total_count = len(group)

        # Count by source (all records)
        source_counts = group["detection.source"].value_counts().to_dict()
        count_source_human = source_counts.get("HUMAN", 0)
        count_source_other = sum(v for k, v in source_counts.items() if k != "HUMAN")

        # Count by category (only HUMAN source records)
        human_records = group[group["detection.source"] == "HUMAN"]
        category_counts = human_records["detection.category"].value_counts().to_dict()
        count_category_whale = category_counts.get("WHALE", 0)
        count_category_vessel = category_counts.get("VESSEL", 0)
        count_category_other = category_counts.get("OTHER", 0)

        # ID lists (semicolon-separated)
        report_ids = ";".join(group["report.id"].unique().astype(str))
        detection_ids = ";".join(group["detection.id"].astype(str))
        detection_times_pst = ";".join(group["detection.time_pst"].astype(str))

        agg_row = {
            "feed.name": feed_name,
            "detection.date_pst": date_pst,
            "detection.year_month_pst": year_month_pst,
            "detection.year_pst": year_pst,
            "detection.month_pst": month_pst,
            "count": total_count,
            "count_source_human": count_source_human,
            "count_source_other": count_source_other,
            "count_category_whale": count_category_whale,
            "count_category_vessel": count_category_vessel,
            "count_category_other": count_category_other,
            "report_ids": report_ids,
            "detection_ids": detection_ids,
            "detection_times_pst": detection_times_pst,
        }

        agg_data.append(agg_row)

    # Create aggregated DataFrame
    agg_df = pd.DataFrame(agg_data)

    # Sort by date first, then by feed name
    agg_df = agg_df.sort_values(["detection.date_pst", "feed.name"]).reset_index(
        drop=True
    )

    print(f"Created daily aggregated DataFrame with {len(agg_df)} rows")
    return agg_df


def process_file(input_file: Path) -> tuple[List[Dict[str, Any]], pd.DataFrame]:
    """Process a single JSON file and return the results."""
    print(f"\n=== Processing {input_file} ===")

    # Create output directory at the same level as the parent directory
    parent_dir = input_file.parent
    output_dir = parent_dir.parent / f"{parent_dir.name}_parsed"
    output_dir.mkdir(exist_ok=True)

    # Step 1: Load and validate
    try:
        reports = load_and_validate_json(input_file)
    except Exception as e:
        print(f"Error loading/validating {input_file}: {e}")
        return [], pd.DataFrame()

    if not reports:
        print(f"No valid reports found in {input_file}")
        return [], pd.DataFrame()

    # Step 2: Flatten detections
    flattened_data = flatten_detections(reports)

    # Save flattened JSON
    flattened_json_path = output_dir / f"{input_file.stem}_flattened.json"
    with open(flattened_json_path, "w") as f:
        json.dump(flattened_data, f, indent=2)
    print(f"Saved flattened JSON to: {flattened_json_path}")

    # Step 3: Create DataFrame and save CSV
    df = create_dataframe(flattened_data)
    csv_path = output_dir / f"{input_file.stem}_parsed.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved CSV to: {csv_path}")

    # Print summary stats
    print(f"\nSummary for {input_file.name}:")
    print(f"  Reports: {len(reports)}")
    print(f"  Total detections: {len(flattened_data)}")
    print(
        f"  Date range: {df['detection.timestamp'].min()} to {df['detection.timestamp'].max()}"
    )
    print(f"  Unique feeds: {df['feed.name'].nunique()}")

    return flattened_data, df


def main():
    parser = argparse.ArgumentParser(description="Process Orcasound listener reports")
    parser.add_argument("files", nargs="+", help="JSON files to process")

    args = parser.parse_args()

    files_to_process = [Path(f) for f in args.files]

    # Track all results to combine
    all_flattened_data = []
    all_dataframes = []
    processed_files = []

    # Process each file
    for file_path in files_to_process:
        if not file_path.exists():
            print(f"File not found: {file_path}")
            continue

        try:
            flattened_data, df = process_file(file_path)
            if flattened_data and len(df) > 0:
                all_flattened_data.extend(flattened_data)
                all_dataframes.append(df)
                processed_files.append(file_path)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            import traceback

            traceback.print_exc()

    # Combine processed files
    print(f"\n=== Combining results from {len(processed_files)} files ===")

    # Determine output directory at the same level as the parent directory
    parent_dir = processed_files[0].parent
    output_dir = parent_dir.parent / f"{parent_dir.name}_parsed"

    # Save combined flattened JSON
    combined_json_path = output_dir / "reports_combined.json"
    with open(combined_json_path, "w") as f:
        json.dump(all_flattened_data, f, indent=2)
    print(f"Saved combined flattened JSON to: {combined_json_path}")

    # Combine all DataFrames
    combined_df = pd.concat(all_dataframes, ignore_index=True)

    # Save combined CSV
    combined_csv_path = output_dir / "reports_combined.csv"
    combined_df.to_csv(combined_csv_path, index=False)
    print(f"Saved combined CSV to: {combined_csv_path}")

    # Create and save daily aggregated data
    combined_agg_df = aggregate_reports_daily(combined_df)
    combined_agg_csv_path = output_dir / "reports_combined_daily_aggregated.csv"
    combined_agg_df.to_csv(combined_agg_csv_path, index=False)
    print(f"Saved combined daily aggregated CSV to: {combined_agg_csv_path}")

    # Print combined summary stats
    print("\nCombined Summary:")
    print(f"  Total files processed: {len(processed_files)}")
    print(f"  Total detections: {len(all_flattened_data)}")
    if len(combined_df) > 0:
        print(
            f"  Date range: {combined_df['detection.timestamp'].min()} to {combined_df['detection.timestamp'].max()}"
        )
        print(f"  Unique feeds: {combined_df['feed.name'].nunique()}")
        print(f"  Files processed: {[f.name for f in processed_files]}")
        print(f"  Daily aggregated records: {len(combined_agg_df)}")


if __name__ == "__main__":
    main()

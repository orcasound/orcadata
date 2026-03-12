#!/usr/bin/env python3
"""Google Sheets integration utilities."""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import gspread
import yaml
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

logger = logging.getLogger(__name__)

# CSV source directory mapping
CSV_SOURCE_DIRS = {
    "detections": Path("./combined_logbook/detections"),
    "hourly_events": Path("./combined_logbook/hourly_events"),
    "daily_events": Path("./combined_logbook/daily_events"),
}

CSV_SOURCE_FILES = {
    "detections": "all_detections.csv",
    "hourly_events": "all_hourly_events.csv",
    "daily_events": "all_daily_events.csv",
}


def load_gsheet_config(config_path: Path) -> Dict[str, Any]:
    """Load Google Sheets configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_gspread_client(config: Dict[str, Any]) -> gspread.Client:
    """
    Initialize gspread client.

    Uses service account if credentials_file is specified in config,
    otherwise uses OAuth flow (opens browser for interactive auth).
    """
    credentials_file = config.get("credentials_file")

    if credentials_file:
        # Service account authentication
        creds_path = Path(credentials_file)
        # Handle relative paths from current directory
        if not creds_path.is_absolute():
            creds_path = Path.cwd() / creds_path

        if not creds_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {creds_path}")

        logger.info(f"Using service account credentials from: {creds_path}")
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = ServiceAccountCredentials.from_service_account_file(
            str(creds_path), scopes=scopes
        )
        return gspread.authorize(credentials)
    else:
        # OAuth flow (interactive browser-based auth)
        logger.info("Using OAuth flow - browser may open for authentication...")
        return gspread.oauth()


def get_csv_path(csv_source: str) -> Path:
    """Get the full path to a CSV file based on source identifier."""
    if csv_source not in CSV_SOURCE_DIRS:
        raise ValueError(f"Unknown csv_source: {csv_source}")
    return CSV_SOURCE_DIRS[csv_source] / CSV_SOURCE_FILES[csv_source]


def read_csv_as_values(csv_path: Path) -> List[List[str]]:
    """Read CSV file and return as list of lists (for gspread)."""
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return list(reader)


def get_sheet_info(
    client: gspread.Client, spreadsheet_id: str, gid: int
) -> Tuple[gspread.Worksheet, int]:
    """
    Get worksheet by GID and return current row count.

    Returns:
        Tuple of (worksheet, current_row_count)
    """
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.get_worksheet_by_id(gid)
    row_count = len(worksheet.get_all_values())
    return worksheet, row_count


def update_sheet(worksheet: gspread.Worksheet, data: List[List[str]]) -> int:
    """
    Clear and update a sheet with new data.

    Returns:
        Number of rows written
    """
    worksheet.clear()
    if data:
        worksheet.update("A1", data, value_input_option="RAW")
    return len(data)

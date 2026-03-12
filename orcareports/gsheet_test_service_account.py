#!/usr/bin/env python3
"""Test Google Sheets service account authentication."""

from pathlib import Path
from gsheet_utils import load_gsheet_config, get_gspread_client

print("Testing service account authentication...")
print()

try:
    # Load config
    config_path = Path("gsheet_config.yaml")
    config = load_gsheet_config(config_path)

    print(f"Config loaded from: {config_path}")
    print(f"Spreadsheet ID: {config['spreadsheet_id']}")
    print()

    # Authenticate
    client = get_gspread_client(config)
    print("✓ Service account authentication successful!")
    print()

    # Try to open the spreadsheet
    spreadsheet_id = config["spreadsheet_id"]
    spreadsheet = client.open_by_key(spreadsheet_id)
    print(f"✓ Successfully opened spreadsheet: '{spreadsheet.title}'")
    print()

    # List all sheets and show configured sheets
    print("All worksheets in spreadsheet:")
    for worksheet in spreadsheet.worksheets():
        print(f"  - {worksheet.title} (gid={worksheet.id}, {worksheet.row_count} rows)")

    print()
    print("Configured sheets to update:")
    for sheet_name, sheet_config in config["sheets"].items():
        gid = sheet_config['gid']
        csv_source = sheet_config['csv_source']

        # Find matching worksheet to get actual title
        worksheet_title = None
        for ws in spreadsheet.worksheets():
            if ws.id == gid:
                worksheet_title = ws.title
                break

        if worksheet_title:
            print(f"  - Config name: '{sheet_name}' → Worksheet: '{worksheet_title}' (gid={gid}, csv_source={csv_source})")
        else:
            print(f"  - Config name: '{sheet_name}' → NOT FOUND (gid={gid}, csv_source={csv_source})")

    print()
    print("✓ All tests passed! Service account is properly configured.")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

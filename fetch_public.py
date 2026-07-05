#!/usr/bin/env python3
"""
Standalone calendar fetcher for GitHub Actions CI.
No maple_toolkit dependency — reads config from env vars or hardcoded defaults.
Outputs plain-text report to docs/calendar.txt.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dateutil import parser as dt_parser
from dateutil.tz import gettz

# ─── Config ─────────────────────────────────────────────────
CALENDAR_ID = os.environ.get(
    "CALENDAR_ID",
    "bd32d4293373d21333696ed89ca1f360c1a252582a0ad27b7d2d01008ee0fd04@group.calendar.google.com",
)
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Taipei")
LOOKAHEAD_DAYS = int(os.environ.get("LOOKAHEAD_DAYS", "9"))
CREDENTIAL_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "gcp-key.json")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "docs/calendar.txt")

# ─── Logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("fetch-public")

WEEKDAY_NAMES = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def _weekday_zh(dt):
    """Return Chinese weekday name for a datetime object."""
    return WEEKDAY_NAMES[dt.weekday()]


# ─── Google Auth ────────────────────────────────────────────

def authenticate(credential_file):
    """Authenticate with Google using service account JSON file."""
    if not os.path.exists(credential_file):
        logger.error(f"Credential file not found: {credential_file}")
        return None
    try:
        credentials = service_account.Credentials.from_service_account_file(
            credential_file,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        logger.info("Authenticated with Google Service Account")
        return credentials
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return None


# ─── Fetch Events ───────────────────────────────────────────

def fetch_events(service, calendar_id, lookahead_days, timezone_str):
    """Fetch upcoming events from the specified calendar."""
    tz = gettz(timezone_str) or gettz("Asia/Taipei")
    now_local = datetime.now(tz)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    time_min = today_start.isoformat()
    time_max = (today_start + timedelta(days=lookahead_days + 1)).isoformat()

    logger.info(f"Fetching events: {time_min} → {time_max} ({timezone_str})")

    try:
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = result.get("items", [])
        logger.info(f"Found {len(events)} events")
        return events
    except HttpError as e:
        logger.error(f"HTTP error fetching events: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return []


# ─── Format Report ──────────────────────────────────────────

def format_event(event):
    """Format a single event as plain text."""
    start_raw = event["start"].get("dateTime", event["start"].get("date"))
    end_raw = event["end"].get("dateTime", event["end"].get("date"))
    start_dt = dt_parser.parse(start_raw)
    end_dt = dt_parser.parse(end_raw)

    summary = event.get("summary", "（無標題）")
    location = event.get("location", "")
    description = event.get("description", "")
    if description and len(description) > 100:
        description = description[:97] + "..."

    lines = [f"▸ {summary}"]

    if "T" in start_raw:
        lines.append(f"  🕐 {start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}")
    else:
        end_check = end_dt - timedelta(days=1)  # Google API end date is exclusive
        if end_check.date() > start_dt.date():
            end_wd = _weekday_zh(end_check)
            lines.append(f"  🕐 整天｜至 {end_check.strftime('%m/%d')}（{end_wd}）")
        else:
            lines.append("  🕐 整天")

    if location:
        lines.append(f"  📍 {location}")
    if description:
        lines.append(f"  📝 {description}")

    return "\n".join(lines)


def format_report(events, timezone_str):
    """Format a list of events into a plain-text report string."""
    if not events:
        return "未來查詢範圍內沒有任何行程。"

    tz = gettz(timezone_str) or gettz("Asia/Taipei")
    now = datetime.now(tz)

    events_by_date = {}
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        try:
            date_key = dt_parser.parse(start).strftime("%Y-%m-%d")
        except Exception:
            date_key = "Unknown Date"
        events_by_date.setdefault(date_key, []).append(event)

    lines = []
    for i, date in enumerate(sorted(events_by_date.keys())):
        try:
            date_obj = dt_parser.parse(date)
            wd = _weekday_zh(date_obj)
            if date_obj.date() == now.date():
                date_header = f"📌 {date_obj.strftime('%m/%d')}（{wd}）◂ 今天"
            else:
                date_header = f"📌 {date_obj.strftime('%m/%d')}（{wd}）"
        except Exception:
            date_header = f"📌 {date}"

        if i > 0:
            lines.append("")
        lines.append(date_header)
        for event in events_by_date[date]:
            lines.append(format_event(event))

    return "\n".join(lines)


# ─── Main ───────────────────────────────────────────────────

def main():
    credentials = authenticate(CREDENTIAL_FILE)
    if not credentials:
        sys.exit(1)

    try:
        service = build("calendar", "v3", credentials=credentials)
    except Exception as e:
        logger.error(f"Failed to build calendar service: {e}")
        sys.exit(1)

    events = fetch_events(service, CALENDAR_ID, LOOKAHEAD_DAYS, TIMEZONE)
    report = format_report(events, TIMEZONE)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info(f"Written {len(report)} chars to {OUTPUT_PATH}")
    print(report)


if __name__ == "__main__":
    main()

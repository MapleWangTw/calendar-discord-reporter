#!/usr/bin/env python3
"""
Google Calendar Report Generator
Core module that fetches calendar events and produces a plain-text report.
Decoupled from any notification channel — returns a string you can use anywhere.
"""

import os
import logging
from datetime import datetime, timedelta

# Google API imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Date handling
from dateutil import parser
from dateutil.tz import gettz

# Module-level logger
logger = logging.getLogger("calendar-report")

WEEKDAY_NAMES = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def _weekday_zh(dt):
    """Return Chinese weekday name for a datetime object."""
    return WEEKDAY_NAMES[dt.weekday()]


def _authenticate_google(service_account_file):
    """Authenticate with Google using service account."""
    try:
        if not os.path.exists(service_account_file):
            logger.error(f"Service account file not found: {service_account_file}")
            return None

        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=['https://www.googleapis.com/auth/calendar.readonly']
        )
        logger.info("Successfully authenticated with Google Service Account")
        return credentials
    except Exception as e:
        logger.error(f"Failed to authenticate with Google: {e}")
        return None


def _get_calendar_service(credentials):
    """Build and return the Google Calendar service object."""
    try:
        service = build('calendar', 'v3', credentials=credentials)
        return service
    except Exception as e:
        logger.error(f"Failed to build calendar service: {e}")
        return None


def _fetch_events(service, calendar_id, lookahead_days, timezone_str):
    """Fetch upcoming events from the specified calendar."""
    try:
        tz = gettz(timezone_str) if timezone_str else gettz('Asia/Taipei')

        now_local = datetime.now(tz)
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

        time_min = today_start.isoformat()
        time_max = (today_start + timedelta(days=lookahead_days + 1)).isoformat()

        logger.info(f"Fetching events from {time_min} to {time_max} ({timezone_str})")

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        logger.info(f"Found {len(events)} upcoming events")
        return events
    except HttpError as error:
        logger.error(f"An HTTP error occurred: {error}")
        return []
    except Exception as e:
        logger.error(f"An error occurred while fetching events: {e}")
        return []


def _format_event(event):
    """Format a single event as plain text (no Markdown)."""
    try:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))

        start_dt = parser.parse(start)
        end_dt = parser.parse(end)

        summary = event.get('summary', '（無標題）')
        location = event.get('location', '')
        description = event.get('description', '')

        # Truncate description if too long
        if description and len(description) > 100:
            description = description[:97] + "..."

        lines = []
        lines.append(f"▸ {summary}")

        if 'T' in start:
            # Timed event
            lines.append(f"  🕐 {start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}")
        else:
            # All-day event — check for multi-day
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
    except Exception as e:
        logger.error(f"Error formatting event {event.get('id', 'unknown')}: {e}")
        return f"▸ {event.get('summary', '（未知事件）')}（格式錯誤）"


def _format_report(events, timezone_str):
    """Format a list of events into a plain-text report string."""
    if not events:
        return "未來查詢範圍內沒有任何行程。"

    tz = gettz(timezone_str) if timezone_str else gettz('Asia/Taipei')
    now = datetime.now(tz)

    lines = []

    # Group events by date
    events_by_date = {}
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        try:
            date_key = parser.parse(start).strftime('%Y-%m-%d')
        except:
            date_key = 'Unknown Date'

        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    sorted_dates = sorted(events_by_date.keys())

    for i, date in enumerate(sorted_dates):
        try:
            date_obj = parser.parse(date)
            wd = _weekday_zh(date_obj)
            if date_obj.date() == now.date():
                date_header = f"📌 {date_obj.strftime('%m/%d')}（{wd}）◂ 今天"
            else:
                date_header = f"📌 {date_obj.strftime('%m/%d')}（{wd}）"
        except:
            date_header = f"📌 {date}"

        if i > 0:
            lines.append("")  # blank line between date groups
        lines.append(date_header)
        for event in events_by_date[date]:
            lines.append(_format_event(event))

    return "\n".join(lines)


# ─── Public API ─────────────────────────────────────────────

def get_calendar_report():
    """
    Fetch calendar events and return a formatted plain-text report.

    Loads configuration via maple_toolkit's ConfigManager
    (same config as main.py), handles auth/fetch/format internally.

    Returns:
        str: Formatted plain-text report, or None on failure.
    """
    from maple_toolkit.config import ConfigManager

    config = ConfigManager.load_project_config(
        app_name="calendar-discord-reporter"
    )

    timezone_str = config.get("TIMEZONE", "Asia/Taipei")
    calendar_id = config.get("CALENDAR_ID", "primary")
    service_account_file = config.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account_key.json")
    service_account_file = os.path.expanduser(service_account_file)
    lookahead_days = int(config.get("LOOKAHEAD_DAYS", 9))

    # Authenticate
    credentials = _authenticate_google(service_account_file)
    if not credentials:
        return None

    # Build service
    service = _get_calendar_service(credentials)
    if not service:
        return None

    # Fetch events
    events = _fetch_events(service, calendar_id, lookahead_days, timezone_str)

    # Format and return
    return _format_report(events, timezone_str)

#!/usr/bin/env python3
"""
Verification script for Google Calendar events retrieval.
Loads config using maple_toolkit, authenticates with Google Calendar,
and prints upcoming events without posting to Discord.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dateutil import parser

# Shared module imports from maple_toolkit
from maple_toolkit.config import ConfigManager
from maple_toolkit.utils import setup_logging

# Module-level logger
logger = logging.getLogger("calendar-verifier")

def authenticate_google(service_account_file):
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

def get_upcoming_events(service, calendar_id, lookahead_days, timezone_str):
    """Fetch upcoming events from the specified calendar for today and lookahead_days ahead."""
    try:
        from dateutil.tz import gettz
        tz = gettz(timezone_str) if timezone_str else gettz('Asia/Taipei')
        
        # Calculate start of today in local timezone
        now_local = datetime.now(tz)
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate end of range (today + lookahead_days + 1 day to cover all of the last day)
        time_min = today_start.isoformat()
        time_max = (today_start + timedelta(days=lookahead_days + 1)).isoformat()
        
        logger.info(f"Fetching events from {time_min} to {time_max} ({timezone_str}) for calendar: {calendar_id}")
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        logger.info(f"Successfully retrieved {len(events)} events.")
        return events
    except HttpError as error:
        logger.error(f"An HTTP error occurred: {error}")
        return None
    except Exception as e:
        logger.error(f"An error occurred while fetching events: {e}")
        return None

def main():
    # 1. Load config
    try:
        config = ConfigManager.load_project_config(
            app_name="calendar-discord-reporter"
        )
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)
        
    log_level_str = config.get("LOG_LEVEL", "INFO")
    timezone_str = config.get("TIMEZONE", "Asia/Taipei")
    calendar_id = config.get("CALENDAR_ID", "primary")
    service_account_file = config.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account_key.json")
    service_account_file = os.path.expanduser(service_account_file)
    lookahead_days = int(config.get("LOOKAHEAD_DAYS", 15))

    # 2. Setup logger
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    global logger
    logger = setup_logging("calendar-verifier", level=log_level)
    
    logger.info("--- Google Calendar Connection Test ---")
    logger.info(f"Calendar ID: {calendar_id}")
    logger.info(f"Service Account: {service_account_file}")
    logger.info(f"Lookahead: {lookahead_days} days (including today)")
    
    # 3. Authenticate
    credentials = authenticate_google(service_account_file)
    if not credentials:
        logger.error("Authentication failed. Check your credential file path and contents.")
        sys.exit(1)
        
    # 4. Build service
    try:
        service = build('calendar', 'v3', credentials=credentials)
    except Exception as e:
        logger.error(f"Failed to build Google Calendar service: {e}")
        sys.exit(1)
        
    # 5. Fetch events
    events = get_upcoming_events(service, calendar_id, lookahead_days, timezone_str)
    if events is None:
        logger.error("Failed to fetch events. Did you share the calendar with the service account email?")
        sys.exit(1)
        
    print("\n--- Upcoming Events Results ---")
    if not events:
        print("No events found in the lookahead window.")
        print(f"Service Account Email: {credentials.service_account_email}")
        print("Ensure this email has been added to your calendar settings under 'Share with specific people'.")
    else:
        for i, event in enumerate(events, 1):
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'No Title')
            print(f"{i}. [{start}] {summary}")
            
    print("\nVerification process completed successfully!")

if __name__ == "__main__":
    main()

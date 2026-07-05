#!/usr/bin/env python3
"""
Google Calendar to Discord Reporter
Thin entry point: fetches calendar report and posts it to Discord.
Designed for cron jobs and automated execution.
"""

import os
import sys
import logging

# Shared module imports from maple_toolkit
from maple_toolkit.config import ConfigManager
from maple_toolkit.notifications import DiscordNotifier
from maple_toolkit.utils import setup_logging

# Core report generator
from calendar_report import get_calendar_report

# Module-level logger declaration
logger = logging.getLogger("calendar-discord-reporter")


def send_to_discord(message, webhook_url):
    """Send message to Discord via webhook using maple_toolkit's DiscordNotifier."""
    if not webhook_url:
        logger.error("Discord webhook URL not provided")
        return False
    try:
        notifier = DiscordNotifier(webhook_url=webhook_url)
        return notifier.send(content=message)
    except Exception as e:
        logger.error(f"Failed to send to Discord: {e}")
        return False


def main():
    """Main function to run the calendar reporter."""
    # 1. Load project configurations
    try:
        config = ConfigManager.load_project_config(
            app_name="calendar-discord-reporter"
        )
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # 2. Setup logger
    log_level_str = config.get("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    global logger
    logger = setup_logging("calendar-discord-reporter", level=log_level)

    logger.info("Starting Google Calendar to Discord Reporter")

    # 3. Validate Discord config
    discord_webhook_url = (
        config.get("DISCORD_WEBHOOK_URL") or
        config.get("discord", {}).get("webhook_url") or
        os.getenv("DISCORD_WEBHOOK_URL")
    )
    if not discord_webhook_url:
        logger.error("Discord Webhook URL is required (set in config.json or environment)")
        sys.exit(1)

    # 4. Generate report (reads same config internally)
    report = get_calendar_report()

    if report is None:
        logger.error("Failed to generate calendar report")
        sys.exit(1)

    # 5. Send to Discord
    if not send_to_discord(report, discord_webhook_url):
        logger.error("Failed to send report to Discord")
        sys.exit(1)

    logger.info("Report successfully sent to Discord")
    print("Success: Calendar report sent to Discord")


if __name__ == "__main__":
    main()
"""Pure timezone and timestamp helpers for the FYP backend; no environment loading."""
from datetime import datetime
from zoneinfo import ZoneInfo


def local_now(settings):
    return datetime.now(ZoneInfo(settings.timezone)).replace(tzinfo=None)


def iso_time(value, settings):
    return value.replace(tzinfo=ZoneInfo(settings.timezone)).isoformat() if value else None

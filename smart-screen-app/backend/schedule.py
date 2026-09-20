import datetime

from config import config


def day_ranges(day):
    days = (config.get().get("schedule") or {}).get("days") or {}
    return days.get(str(day)) or days.get(day) or []


def enabled():
    return bool((config.get().get("schedule") or {}).get("enabled"))


def is_off_now(now=None):
    if not enabled():
        return False
    now = now or datetime.datetime.now()
    minutes = now.hour * 60 + now.minute
    for item in day_ranges(now.isoweekday()):
        try:
            if not isinstance(item, dict):
                continue
            start_h, start_m = (int(part) for part in item["start"].split(":"))
            end_h, end_m = (int(part) for part in item["end"].split(":"))
        except (KeyError, ValueError, AttributeError):
            continue
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        if start == end:
            continue
        if start < end:
            if start <= minutes < end:
                return True
        elif minutes >= start or minutes < end:
            return True
    return False


def today():
    now = datetime.datetime.now()
    return {
        "day": now.isoweekday(),
        "minutes_now": now.hour * 60 + now.minute,
        "off_now": is_off_now(now),
        "ranges": day_ranges(now.isoweekday()),
    }
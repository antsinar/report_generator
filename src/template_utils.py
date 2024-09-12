from datetime import datetime
from typing import Optional


def datetime_format(value, format="%d/%m/%Y @ %H:%M:%S"):
    return value.strftime(format) if value and isinstance(value, datetime) else None


def timestamp_format(value, format="%d/%m/%Y @ %H:%M:%S") -> Optional[str]:
    return (
        datetime.fromtimestamp(value).strftime(format)
        if value and isinstance(value, int)
        else None
    )


def handle_none(value: Optional[str]) -> str:
    if not value:
        return "&dash;"
    return value

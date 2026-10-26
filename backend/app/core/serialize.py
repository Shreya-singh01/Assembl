"""Convert raw MongoDB documents into JSON-safe values (ObjectId -> str, NaN -> None)."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from bson import ObjectId


def plain(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {("id" if k == "_id" else str(k)): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [plain(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value

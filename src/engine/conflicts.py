"""Pure pairwise conflict detection over already-expanded event occurrences."""

from collections.abc import Iterable
from datetime import datetime

from src.models.conflict import EventConflict
from src.models.event import Event
from src.models.reminder import Reminder


def detect_conflicts(
    items: Iterable[Event | Reminder], start: datetime, end: datetime
) -> list[EventConflict]:
    """Return each unordered occurrence pair once, clipped to [start, end).

    Reminders are excluded. Identity includes source ID AND occurrence start,
    so overlapping occurrences of the same long-running series still conflict.
    Sorting permits an early stop for disjoint intervals; worst case is O(n²),
    appropriate for personal-calendar windows and all-pairs conflict output.
    """
    if start.tzinfo is not None or end.tzinfo is not None or end <= start:
        raise ValueError("Use a positive local-naive conflict range.")
    unique = {
        (item.id, item.start_datetime): item
        for item in items
        if isinstance(item, Event)
        and item.start_datetime < end
        and item.end_datetime > start
    }
    events = sorted(unique.values(), key=lambda item: (item.start_datetime, item.id))
    conflicts = []
    for index, first in enumerate(events):
        for second in events[index + 1 :]:
            if second.start_datetime >= first.end_datetime:
                break
            lower = max(start, first.start_datetime, second.start_datetime)
            upper = min(end, first.end_datetime, second.end_datetime)
            if lower < upper:
                conflicts.append(EventConflict(first, second, lower, upper))
    return sorted(
        conflicts,
        key=lambda conflict: (
            conflict.overlap_start,
            conflict.first.start_datetime,
            conflict.first.id,
            conflict.second.start_datetime,
            conflict.second.id,
        ),
    )

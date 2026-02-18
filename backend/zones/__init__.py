"""
Zone-specific detection processors.

Each zone has isolated detection logic with:
- Multi-frame buffering
- Suspicion scoring
- Threshold verification

No cross-zone logic allowed.
"""

from .outgate import OutgateProcessor
from .corridor import CorridorProcessor
from .school_ground import SchoolGroundProcessor
from .classroom import ClassroomProcessor

ZONE_PROCESSORS = {
    "outgate": OutgateProcessor,
    "corridor": CorridorProcessor,
    "school_ground": SchoolGroundProcessor,
    "classroom": ClassroomProcessor,
}

__all__ = [
    "ZONE_PROCESSORS",
    "OutgateProcessor",
    "CorridorProcessor",
    "SchoolGroundProcessor",
    "ClassroomProcessor",
]

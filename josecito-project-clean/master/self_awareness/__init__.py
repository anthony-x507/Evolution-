"""
MASTER Self-Awareness System
============================
The self-awareness system is MASTER's internal compass.

It consists of three coordinated modules:

1. GPS Centinella — Watches the route, detects problems (potholes)
2. Destination — Holds the final objective, the "north star"
3. DriftDetector — Coordinates both to detect true drift vs potholes

When drift is detected (GPS and Destination no longer agree),
the DriftDetector stops and asks the user:
    "Continue on the original path, or are we working on something different?"

This prevents the agent from wandering off-mission without the user's knowledge.
"""

from .destination import Destination
from .gps_centinella import GPSCentinella, Pothole, RouteReport
from .drift_detector import DriftDetector, DriftAssessment

__all__ = [
    "Destination",
    "GPSCentinella",
    "Pothole",
    "RouteReport",
    "DriftDetector",
    "DriftAssessment",
]

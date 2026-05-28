"""
MASTER Skills System
==================
The Skills layer implements MASTER's capability honesty principle.
Every skill is a declarative CapabilityCard that states what
the system CAN do, what it CANNOT do, and what evidence supports
each claim.

This is the "pharmacy that only sells what's actually on the shelf."
"""

from .capability import CapabilityCard, CapabilityStatus, SkillEvidence
from .registry import SkillRegistry
from .checker import CapabilityHonestyChecker
from .self_awareness import SelfAwarenessReviewer

__all__ = [
    "CapabilityCard",
    "CapabilityStatus",
    "SkillEvidence",
    "SkillRegistry",
    "CapabilityHonestyChecker",
    "SelfAwarenessReviewer",
]

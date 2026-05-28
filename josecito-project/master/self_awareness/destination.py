"""
MASTER Self-Awareness — Destination
====================================
The Destination is the "north star" of the self-awareness system.
It holds the final objective — the reason the mission exists.

The Destination does not navigate. It does not track progress.
It simply holds the answer to: "Where are we trying to go?"

When consulted alongside the GPS Centinella, the Destination provides
the ground truth that determines whether a drift is a pothole
(fixable on the same route) or a true deviation (different road entirely).

Key principle: "The destination doesn't change unless the user changes it."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from gps import STOP_WORDS


# Punctuation characters to strip when extracting keywords
_PUNCTUATION = ".,!?;:()[]{}'\""


def _tokenize(text: str) -> List[str]:
    """Extract meaningful keywords from text, filtering stop words and punctuation."""
    words = text.lower().split()
    return [
        w.strip(_PUNCTUATION)
        for w in words
        if w.strip(_PUNCTUATION) not in STOP_WORDS
        and len(w.strip(_PUNCTUATION)) > 1
    ]


@dataclass
class Destination:
    """
    The mission's final objective — immutable unless explicitly changed.

    The Destination is the source of truth for "what are we trying to achieve?"
    It pairs with the GPS Centinella to form the complete navigation system:
    - Destination: WHERE we're going (static)
    - GPS Centinella: HOW we're getting there (dynamic)
    """

    # ── Core destination ──
    goal: str = ""
    description: str = ""
    set_at: Optional[datetime] = None
    set_by: str = "system"  # "user", "system", "onboarding"

    # ── Context ──
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # ── History ──
    previous_destinations: List[Dict[str, Any]] = field(default_factory=list)
    change_count: int = 0

    # ── Alignment thresholds ──
    strong_alignment_threshold: float = 0.7
    weak_alignment_threshold: float = 0.3

    def set(
        self,
        goal: str,
        description: str = "",
        set_by: str = "user",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Set a new destination.

        If a destination already exists, it's archived before being replaced.
        """
        if self.goal:
            self.previous_destinations.append({
                "goal": self.goal,
                "description": self.description,
                "set_at": self.set_at.isoformat() if self.set_at else None,
                "set_by": self.set_by,
                "replaced_at": datetime.now().isoformat(),
            })
            self.change_count += 1

        self.goal = goal
        self.description = description or goal
        self.set_at = datetime.now()
        self.set_by = set_by
        if context:
            self.context.update(context)

    def update_context(self, key: str, value: Any) -> None:
        """Add or update context metadata without changing the destination."""
        self.context[key] = value

    def is_set(self) -> bool:
        """Has a destination been set?"""
        return bool(self.goal)

    def clear(self) -> None:
        """Clear the destination (archive first)."""
        if self.goal:
            self.previous_destinations.append({
                "goal": self.goal,
                "description": self.description,
                "set_at": self.set_at.isoformat() if self.set_at else None,
                "set_by": self.set_by,
                "replaced_at": datetime.now().isoformat(),
                "cleared": True,
            })
        self.goal = ""
        self.description = ""
        self.set_at = None
        self.set_by = "system"
        self.context = {}

    # ──────────────────────────────────────────────────────────────────
    # Alignment checks
    # ──────────────────────────────────────────────────────────────────

    def extract_keywords(self) -> List[str]:
        """Extract meaningful keywords from the destination goal."""
        return _tokenize(self.goal)

    def alignment_score(self, other_text: str) -> float:
        """
        Calculate how aligned another text is with this destination.

        Returns 0.0 (completely unrelated) to 1.0 (perfect match).
        """
        if not self.goal:
            return 1.0  # No destination = everything is aligned

        dest_keywords = set(_tokenize(self.goal))
        if not dest_keywords:
            return 1.0

        other_keywords = set(_tokenize(other_text))
        if not other_keywords:
            return 0.0

        overlap = dest_keywords & other_keywords
        return len(overlap) / len(dest_keywords)

    def is_aligned(self, other_text: str, threshold: Optional[float] = None) -> bool:
        """
        Quick check: is the other text aligned with this destination?

        Uses strong_alignment_threshold by default.
        """
        threshold = threshold or self.strong_alignment_threshold
        return self.alignment_score(other_text) >= threshold

    # ──────────────────────────────────────────────────────────────────
    # Consensus with GPS
    # ──────────────────────────────────────────────────────────────────

    def consensus_with_gps(self, gps_destination: str) -> Dict[str, Any]:
        """
        Check if this Destination is in consensus with the GPS Centinella.

        Consensus means both systems agree on where we're going.
        Lack of consensus means drift has occurred and we need
        to stop and ask the user.

        Returns:
            {
                "consensus": True/False,
                "score": 0.0-1.0,
                "destination_keywords": [...],
                "gps_keywords": [...],
                "shared_keywords": [...],
                "destination_only": [...],
                "gps_only": [...],
                "verdict": "aligned" | "diverged" | "no_destination",
            }
        """
        if not self.goal:
            return {
                "consensus": True,
                "score": 1.0,
                "destination_keywords": [],
                "gps_keywords": [],
                "shared_keywords": [],
                "destination_only": [],
                "gps_only": [],
                "verdict": "no_destination",
            }

        dest_kw = set(_tokenize(self.goal))
        gps_kw = set(_tokenize(gps_destination))

        shared = dest_kw & gps_kw
        dest_only = dest_kw - gps_kw
        gps_only = gps_kw - dest_kw

        if not dest_kw and not gps_kw:
            score = 1.0
        elif not dest_kw:
            score = 0.0
        else:
            score = len(shared) / len(dest_kw)

        verdict = "aligned" if score >= self.strong_alignment_threshold else "diverged"

        return {
            "consensus": verdict == "aligned",
            "score": score,
            "destination_keywords": sorted(dest_kw),
            "gps_keywords": sorted(gps_kw),
            "shared_keywords": sorted(shared),
            "destination_only": sorted(dest_only),
            "gps_only": sorted(gps_only),
            "verdict": verdict,
        }

    # ──────────────────────────────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Get the current destination status."""
        return {
            "goal": self.goal[:120] if self.goal else "(not set)",
            "description": self.description[:200],
            "set_by": self.set_by,
            "set_at": self.set_at.isoformat() if self.set_at else None,
            "change_count": self.change_count,
            "context_keys": list(self.context.keys()),
            "tags": self.tags,
            "previous_count": len(self.previous_destinations),
        }

    def summary(self) -> str:
        """Human-readable destination summary."""
        if not self.goal:
            return "🎯 Destination: (not set)"

        age = ""
        if self.set_at:
            delta = datetime.now() - self.set_at
            if delta.total_seconds() < 60:
                age = " (just set)"
            elif delta.total_seconds() < 3600:
                age = f" ({int(delta.total_seconds() / 60)}m ago)"
            else:
                age = f" ({int(delta.total_seconds() / 3600)}h ago)"

        return (
            f"🎯 Destination: {self.goal[:100]}{'...' if len(self.goal) > 100 else ''}"
            f"{age}"
        )

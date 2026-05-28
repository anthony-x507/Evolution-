"""
MASTER GPS — Navigation System
===============================
The GPS is MASTER's navigator. It does not execute, it does not judge.
It asks one question and one question only:

    "Are we still going where we said we were going?"

The GPS maintains the mission destination, tracks waypoints,
identifies the "active block" (the current task in context of the
larger objective), and filters noise from signal.

Principle: "If you don't know where you're going, any road will take you there."
The GPS ensures MASTER always knows the destination.

Key distinction:
- GPS: "Does this take us closer to the destination?" → BEFORE acting
- Self-Awareness: "Were we honest? Did we drift?" → AFTER acting
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


# ── Stop words filtered from alignment calculations ─────────────────────

STOP_WORDS: Set[str] = {
    "the", "a", "an", "is", "to", "of", "in", "for",
    "and", "or", "with", "on", "at", "by", "it", "its",
    "be", "are", "was", "were", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might",
    "can", "could", "must", "need", "this", "that",
    "these", "those", "i", "you", "he", "she", "we", "they",
    "me", "him", "her", "us", "them", "my", "your",
    "his", "our", "their", "not", "no", "yes",
    "from", "as", "if", "then", "than", "so", "just",
    "very", "also", "only", "all", "some", "any",
    "each", "every", "both", "few", "more", "most",
    "other", "about", "into", "over", "under",
    "between", "through", "during", "before", "after",
    "above", "below", "up", "down", "out", "off",
    "here", "there", "when", "where", "why", "how",
}


@dataclass
class Waypoint:
    """A waypoint on the mission route.

    Waypoints are checkpoints — intermediate destinations that mark
    progress toward the final objective. They are NOT the destination
    itself, but they confirm you're on the right path.
    """

    description: str
    reached: bool = False
    reached_at: Optional[datetime] = None
    notes: str = ""


@dataclass
class ActiveBlock:
    """The current task in context of the larger mission.

    This is the GPS's answer to "what are we doing RIGHT NOW
    that moves us toward the destination?"

    The active block prevents MASTER from getting lost in the
    details — it keeps the immediate task connected to the
    larger purpose.
    """

    description: str
    parent_waypoint: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    is_noise: bool = False  # True if this task is irrelevant to the mission


@dataclass
class NavigationCheck:
    """Result of a GPS navigation check.

    Answers: "Should we proceed with this action?"
    """

    action: str
    is_on_course: bool
    alignment_score: float  # 0.0 = total drift, 1.0 = perfect alignment
    relevant_keywords: List[str] = field(default_factory=list)
    missed_keywords: List[str] = field(default_factory=list)
    noise_detected: bool = False
    recommendation: str = ""  # "proceed", "recalibrate", "abort"
    reasoning: str = ""
    checked_at: datetime = field(default_factory=datetime.now)


@dataclass
class GPS:
    """MASTER's navigation system.

    The GPS does not fly the plane. It does not own the route.
    It simply keeps asking the most important question:
    "Are we still going where we said we were going?"

    This prevents agent drift — when an agent becomes obsessed
    with the last problem and forgets the larger purpose.

    Attributes:
        destination: The final objective. The "why" of the mission.
        waypoints: Checkpoints along the route to the destination.
        active_block: What MASTER is doing RIGHT NOW in context of the mission.
        drift_history: Record of alignment scores over time.
        noise_filter_enabled: If True, the GPS actively filters irrelevant tasks.
    """

    name: str = "gps"
    version: str = "1.0.0"

    # ── Mission state ──
    destination: str = ""
    waypoints: List[Waypoint] = field(default_factory=list)
    active_block: Optional[ActiveBlock] = None

    # ── Noise filter ──
    noise_filter_enabled: bool = True
    noise_threshold: float = 0.15  # Actions below this score are noise

    # ── Drift tracking ──
    drift_history: List[float] = field(default_factory=list)
    drift_warning_threshold: float = 0.3   # Below this = warning
    drift_critical_threshold: float = 0.6  # Below this = critical (inverted: low alignment = high drift)

    # ── Navigation history ──
    navigation_history: List[NavigationCheck] = field(default_factory=list)
    max_history: int = 200

    # ── Callbacks ──
    on_destination_reached: Optional[Any] = None
    on_drift_critical: Optional[Any] = None

    # ──────────────────────────────────────────────────────────────────
    # Mission Setup
    # ──────────────────────────────────────────────────────────────────

    def set_destination(
        self,
        destination: str,
        waypoints: Optional[List[str]] = None,
    ) -> None:
        """Set the mission destination and optional waypoints.

        The destination is the final objective — the "why" of the mission.
        Waypoints are checkpoints along the route.

        Example:
            gps.set_destination(
                "Build a REST API for the inventory system",
                waypoints=[
                    "Design the data model",
                    "Implement CRUD endpoints",
                    "Add authentication",
                    "Write tests",
                ]
            )
        """
        self.destination = destination
        self.waypoints = [
            Waypoint(description=wp) for wp in (waypoints or [])
        ]
        self.drift_history = []
        self.navigation_history = []
        self.active_block = None

    def set_active_block(
        self,
        description: str,
        parent_waypoint: Optional[str] = None,
    ) -> None:
        """Set what MASTER is doing RIGHT NOW.

        This connects the immediate task to the larger mission.
        """
        self.active_block = ActiveBlock(
            description=description,
            parent_waypoint=parent_waypoint,
        )

    # ──────────────────────────────────────────────────────────────────
    # Navigation
    # ──────────────────────────────────────────────────────────────────

    def check_course(self, action: str) -> NavigationCheck:
        """Check if an action is on course toward the destination.

        This is the main navigation method — call it BEFORE executing
        any action to verify it moves toward the destination.

        Returns a NavigationCheck with:
        - is_on_course: True if the action aligns with the destination
        - alignment_score: 0.0–1.0 (higher = more aligned)
        - recommendation: "proceed", "recalibrate", or "abort"
        """
        if not self.destination:
            return NavigationCheck(
                action=action,
                is_on_course=True,
                alignment_score=1.0,
                recommendation="proceed",
                reasoning="No destination set — free navigation",
            )

        # Extract meaningful keywords from destination and action
        dest_keywords = self._extract_keywords(self.destination)
        action_keywords = self._extract_keywords(action)

        if not dest_keywords:
            return NavigationCheck(
                action=action,
                is_on_course=True,
                alignment_score=1.0,
                recommendation="proceed",
                reasoning="Destination has no analyzable keywords",
            )

        # Find overlap
        relevant = [kw for kw in action_keywords if kw in dest_keywords]
        missed = [kw for kw in dest_keywords if kw not in action_keywords]

        # Calculate alignment
        alignment = len(relevant) / max(len(dest_keywords), 1)

        # Detect noise
        is_noise = alignment < self.noise_threshold if self.noise_filter_enabled else False

        # Form recommendation
        if alignment >= 0.7:
            recommendation = "proceed"
            reasoning = f"Strong alignment ({alignment:.0%}) — action is on course"
        elif alignment >= 0.3:
            recommendation = "recalibrate"
            reasoning = (
                f"Partial alignment ({alignment:.0%}) — "
                f"action may be tangential to destination. "
                f"Missing keywords: {', '.join(missed[:5])}"
            )
        elif is_noise:
            recommendation = "abort"
            reasoning = (
                f"Noise detected ({alignment:.0%} alignment) — "
                f"action appears unrelated to destination. "
                f"Destination keywords: {', '.join(list(dest_keywords)[:5])}"
            )
        else:
            recommendation = "recalibrate"
            reasoning = (
                f"Low alignment ({alignment:.0%}) — "
                f"action may be off course"
            )

        check = NavigationCheck(
            action=action,
            is_on_course=alignment >= self.drift_warning_threshold,
            alignment_score=alignment,
            relevant_keywords=relevant,
            missed_keywords=missed,
            noise_detected=is_noise,
            recommendation=recommendation,
            reasoning=reasoning,
        )

        # Track history
        self.drift_history.append(alignment)
        self.navigation_history.append(check)

        # Trim history
        if len(self.drift_history) > self.max_history:
            self.drift_history = self.drift_history[-self.max_history:]
        if len(self.navigation_history) > self.max_history:
            self.navigation_history = self.navigation_history[-self.max_history:]

        # Fire critical drift callback
        if alignment < self.drift_critical_threshold and self.on_drift_critical:
            self.on_drift_critical(check)

        return check

    def is_on_course(self, action: str) -> bool:
        """Quick check: is this action on course? (no detailed report)"""
        if not self.destination:
            return True
        return self.check_course(action).is_on_course

    # ──────────────────────────────────────────────────────────────────
    # Waypoint Management
    # ──────────────────────────────────────────────────────────────────

    def reached_waypoint(self, description: str) -> bool:
        """Mark a waypoint as reached. Returns True if found."""
        for wp in self.waypoints:
            if wp.description.lower() == description.lower():
                wp.reached = True
                wp.reached_at = datetime.now()
                return True
        return False

    def next_waypoint(self) -> Optional[Waypoint]:
        """Get the next unreached waypoint."""
        for wp in self.waypoints:
            if not wp.reached:
                return wp
        return None

    def progress(self) -> float:
        """What fraction of waypoints have been reached? (0.0–1.0)"""
        if not self.waypoints:
            return 1.0 if self.destination else 0.0
        reached = sum(1 for wp in self.waypoints if wp.reached)
        return reached / len(self.waypoints)

    # ──────────────────────────────────────────────────────────────────
    # Drift Analysis
    # ──────────────────────────────────────────────────────────────────

    def get_drift_trend(self, window: int = 10) -> str:
        """Get the alignment trend over recent checks.

        Returns: "improving ⬆️", "worsening ⬇️", or "stable ➡️"
        """
        if len(self.drift_history) < 3:
            return "insufficient data"

        recent = self.drift_history[-window:]
        if len(recent) < 3:
            return "insufficient data"

        mid = len(recent) // 2
        first_half = sum(recent[:mid]) / max(mid, 1)
        second_half = sum(recent[mid:]) / max(len(recent) - mid, 1)

        diff = second_half - first_half
        if diff > 0.1:
            return "improving ⬆️"
        elif diff < -0.1:
            return "worsening ⬇️"
        else:
            return "stable ➡️"

    def current_alignment(self) -> float:
        """Get the most recent alignment score (0.0–1.0)."""
        if not self.drift_history:
            return 1.0
        return self.drift_history[-1]

    # ──────────────────────────────────────────────────────────────────
    # Status & Summaries
    # ──────────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Get the current GPS status as a dict."""
        alignment = self.current_alignment()
        return {
            "destination": self.destination[:100] if self.destination else "(not set)",
            "waypoints_total": len(self.waypoints),
            "waypoints_reached": sum(1 for wp in self.waypoints if wp.reached),
            "progress": f"{self.progress():.0%}",
            "current_alignment": f"{alignment:.0%}",
            "drift_trend": self.get_drift_trend(),
            "active_block": self.active_block.description if self.active_block else "(none)",
            "noise_filter": "active" if self.noise_filter_enabled else "off",
            "navigation_checks": len(self.navigation_history),
        }

    def summary(self) -> str:
        """Human-readable GPS status."""
        if not self.destination:
            return "🧭 GPS: No destination set. Free navigation."

        alignment = self.current_alignment()
        trend = self.get_drift_trend()
        next_wp = self.next_waypoint()

        lines = [
            "🧭 GPS NAVIGATION",
            f"   Destination: {self.destination[:80]}{'...' if len(self.destination) > 80 else ''}",
            f"   Progress: {self.progress():.0%} ({sum(1 for wp in self.waypoints if wp.reached)}/{len(self.waypoints)} waypoints)",
            f"   Alignment: {alignment:.0%} | Trend: {trend}",
        ]

        if self.active_block:
            lines.append(f"   Active: {self.active_block.description[:70]}...")

        if next_wp:
            lines.append(f"   Next: {next_wp.description[:70]}...")

        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────────────
    # Internal Helpers
    # ──────────────────────────────────────────────────────────────────

    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract meaningful keywords from text, filtering stop words."""
        words = text.lower().split()
        return {
            w.strip(".,!?;:()[]{}'\"")
            for w in words
            if w.strip(".,!?;:()[]{}'\"") not in STOP_WORDS
            and len(w.strip(".,!?;:()[]{}'\"")) > 1
        }

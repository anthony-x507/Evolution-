"""
MASTER Self-Awareness — GPS Centinella
======================================
The GPS Centinella is the "sentinel" of the self-awareness system.
It wraps MASTER's GPS with additional intelligence:

- Monitors the route continuously, not just on request
- Detects "potholes" — problems encountered along the way
- Tracks checkpoints and reports route integrity
- Distinguishes between fixable problems (potholes) and true deviations (wrong road)

The Centinella does not decide — it observes and reports.
Decisions are made by the DriftDetector, which consults both
the GPS Centinella and the Destination.

Key principle: "The sentinel watches. The general decides."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from gps import GPS, NavigationCheck, Waypoint


@dataclass
class Pothole:
    """
    A problem encountered along the mission route.

    A pothole is a fixable problem — it doesn't mean we're on the
    wrong road, just that the road needs repair. The Centinella
    detects potholes so the system can fix them without losing
    sight of the destination.

    Contrast with "drift" — drift means we're on the wrong road entirely.
    """

    description: str
    severity: str  # "minor", "moderate", "major", "blocking"
    detected_at: datetime = field(default_factory=datetime.now)
    related_action: str = ""
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution: str = ""

    def resolve(self, resolution: str = "") -> None:
        """Mark this pothole as resolved."""
        self.is_resolved = True
        self.resolved_at = datetime.now()
        self.resolution = resolution


@dataclass
class RouteReport:
    """
    A comprehensive report from the GPS Centinella about the current route.

    This is the Centinella saying: "Here's what I see on the road ahead."
    """

    # ── Navigation ──
    destination: str
    current_alignment: float  # 0.0-1.0
    is_on_course: bool
    drift_trend: str  # "improving ⬆️", "worsening ⬇️", "stable ➡️"

    # ── Progress ──
    waypoints_total: int
    waypoints_reached: int
    progress_pct: float

    # ── Active ──
    active_block: str
    next_waypoint: str

    # ── Potholes ──
    active_potholes: List[Pothole]
    resolved_potholes: List[Pothole]
    has_blocking_pothole: bool

    # ── Metadata ──
    generated_at: datetime = field(default_factory=datetime.now)
    navigation_checks: int = 0


@dataclass
class GPSCentinella:
    """
    The GPS Centinella — MASTER's route sentinel.

    Wraps the core GPS with continuous monitoring, pothole detection,
    and route integrity reporting. The Centinella watches the road
    so the DriftDetector can make informed decisions.

    Lifecycle:
    1. set_destination() → Centinella starts watching
    2. check_course() → called before every action
    3. report_pothole() → called when a problem is encountered
    4. get_route_report() → full status for DriftDetector
    """

    # ── Core GPS ──
    _gps: GPS = field(default_factory=GPS)

    # ── Pothole tracking ──
    potholes: List[Pothole] = field(default_factory=list)
    max_potholes: int = 50

    # ── Monitoring ──
    continuous_monitoring: bool = True
    check_count: int = 0
    last_report: Optional[RouteReport] = None

    # ── Callbacks ──
    on_pothole_detected: Optional[Callable[[Pothole], None]] = None
    on_route_diverged: Optional[Callable[[NavigationCheck], None]] = None

    def set_destination(
        self,
        destination: str,
        waypoints: Optional[List[str]] = None,
    ) -> None:
        """
        Set the mission destination and begin monitoring.

        The Centinella immediately starts watching the route.
        """
        self._gps.set_destination(destination, waypoints)
        self.potholes = []  # Clear potholes on new mission

    @property
    def destination(self) -> str:
        """The current mission destination."""
        return self._gps.destination

    @property
    def is_monitoring(self) -> bool:
        """Is the Centinella actively monitoring a route?"""
        return self.continuous_monitoring and bool(self._gps.destination)

    # ──────────────────────────────────────────────────────────────────
    # Navigation
    # ──────────────────────────────────────────────────────────────────

    def check_course(self, action: str) -> NavigationCheck:
        """
        Check if an action is on course.

        This is the main navigation method — call BEFORE executing
        any action. The Centinella evaluates the route and updates
        its internal state.
        """
        nav = self._gps.check_course(action)
        self.check_count += 1

        # If the action is severely off course, report it
        if nav.recommendation == "abort" and self.on_route_diverged:
            self.on_route_diverged(nav)

        return nav

    def set_active_block(self, description: str, parent_waypoint: Optional[str] = None) -> None:
        """Set what MASTER is doing RIGHT NOW."""
        self._gps.set_active_block(description, parent_waypoint)

    # ──────────────────────────────────────────────────────────────────
    # Pothole Management
    # ──────────────────────────────────────────────────────────────────

    def report_pothole(
        self,
        description: str,
        severity: str = "moderate",
        related_action: str = "",
    ) -> Pothole:
        """
        Report a problem encountered along the route.

        This is the Centinella saying: "There's a pothole on the road."
        The DriftDetector will decide if it's worth stopping for.

        severity: "minor" (cosmetic), "moderate" (needs attention),
                  "major" (must fix soon), "blocking" (cannot proceed)
        """
        pothole = Pothole(
            description=description,
            severity=severity,
            related_action=related_action,
        )
        self.potholes.append(pothole)

        # Trim
        if len(self.potholes) > self.max_potholes:
            self.potholes = self.potholes[-self.max_potholes:]

        # Fire callback
        if self.on_pothole_detected:
            self.on_pothole_detected(pothole)

        return pothole

    def resolve_pothole(self, pothole_index: int = -1, resolution: str = "") -> Optional[Pothole]:
        """
        Mark the most recent (or specified) pothole as resolved.

        Returns the resolved pothole, or None if none found.
        """
        active = self.get_active_potholes()
        if not active:
            return None

        # Negative index for "most recent"
        if pothole_index < 0:
            pothole_index = len(self.potholes) - 1 - (abs(pothole_index) - 1)
            # Find the actual index in self.potholes
            target = active[-1] if pothole_index < 0 else active[pothole_index]
        else:
            if pothole_index >= len(active):
                return None
            target = active[pothole_index]

        target.resolve(resolution)
        return target

    def get_active_potholes(self) -> List[Pothole]:
        """Get all unresolved potholes, sorted by severity."""
        severity_order = {"blocking": 0, "major": 1, "moderate": 2, "minor": 3}
        active = [p for p in self.potholes if not p.is_resolved]
        return sorted(active, key=lambda p: severity_order.get(p.severity, 99))

    def get_resolved_potholes(self) -> List[Pothole]:
        """Get all resolved potholes."""
        return [p for p in self.potholes if p.is_resolved]

    def has_blocking_pothole(self) -> bool:
        """Is there a blocking pothole on the route?"""
        return any(
            p.severity == "blocking" and not p.is_resolved
            for p in self.potholes
        )

    # ──────────────────────────────────────────────────────────────────
    # Route Reports
    # ──────────────────────────────────────────────────────────────────

    def get_route_report(self) -> RouteReport:
        """
        Generate a comprehensive route report.

        This is the full picture the DriftDetector uses to make decisions.
        """
        active_potholes = self.get_active_potholes()
        next_wp = self._gps.next_waypoint()

        report = RouteReport(
            destination=self._gps.destination,
            current_alignment=self._gps.current_alignment(),
            is_on_course=self._gps.current_alignment() >= self._gps.drift_warning_threshold,
            drift_trend=self._gps.get_drift_trend(),
            waypoints_total=len(self._gps.waypoints),
            waypoints_reached=sum(1 for wp in self._gps.waypoints if wp.reached),
            progress_pct=self._gps.progress(),
            active_block=self._gps.active_block.description if self._gps.active_block else "",
            next_waypoint=next_wp.description if next_wp else "",
            active_potholes=active_potholes,
            resolved_potholes=self.get_resolved_potholes(),
            has_blocking_pothole=self.has_blocking_pothole(),
            navigation_checks=len(self._gps.navigation_history),
        )

        self.last_report = report
        return report

    def reached_waypoint(self, description: str) -> bool:
        """Mark a waypoint as reached."""
        return self._gps.reached_waypoint(description)

    def progress(self) -> float:
        """Get mission progress (0.0-1.0)."""
        return self._gps.progress()

    # ──────────────────────────────────────────────────────────────────
    # GPS delegate
    # ──────────────────────────────────────────────────────────────────

    @property
    def waypoints(self) -> List[Waypoint]:
        """Access the underlying GPS waypoints."""
        return self._gps.waypoints

    @property
    def navigation_history(self) -> List[NavigationCheck]:
        """Access the navigation history."""
        return self._gps.navigation_history

    # ──────────────────────────────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Get the Centinella's current status."""
        report = self.get_route_report()
        return {
            "destination": report.destination[:120] if report.destination else "(not set)",
            "is_monitoring": self.is_monitoring,
            "current_alignment": f"{report.current_alignment:.0%}",
            "drift_trend": report.drift_trend,
            "is_on_course": report.is_on_course,
            "progress": f"{report.progress_pct:.0%}",
            "waypoints": f"{report.waypoints_reached}/{report.waypoints_total}",
            "active_potholes": len(report.active_potholes),
            "has_blocking": report.has_blocking_pothole,
            "navigation_checks": report.navigation_checks,
            "next_waypoint": report.next_waypoint[:80],
        }

    def summary(self) -> str:
        """Human-readable Centinella summary."""
        report = self.get_route_report()

        if not report.destination:
            return "🧭 GPS Centinella: No route set. Standing by."

        lines = [
            "🧭 GPS CENTINELLA",
            f"   Route: {report.destination[:80]}{'...' if len(report.destination) > 80 else ''}",
            f"   Progress: {report.progress_pct:.0%} | Alignment: {report.current_alignment:.0%} | Trend: {report.drift_trend}",
        ]

        if report.active_block:
            lines.append(f"   Active: {report.active_block[:70]}")

        if report.next_waypoint:
            lines.append(f"   Next WP: {report.next_waypoint[:70]}")

        if report.active_potholes:
            lines.append(f"   ⚠️  Potholes: {len(report.active_potholes)} active"
                         f"{' (BLOCKING!)' if report.has_blocking_pothole else ''}")
            for ph in report.active_potholes[:3]:
                lines.append(f"      [{ph.severity}] {ph.description[:60]}")

        return "\n".join(lines)

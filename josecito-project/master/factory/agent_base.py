"""
MASTER Factory Agent Base
=========================
Every agent in the Factory — Engineer, Superior Agent, Internal Agents —
carries its own GPS, Self-Awareness, and DriftDetector.
No agent flies blind. Each agent knows where it's going,
checks its own honesty, and detects when it has drifted
from the mission.

Philosophy: "An agent without a compass is not an agent — it's a tool.
An agent that can't detect drift is a danger to the mission."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from gps import GPS, NavigationCheck
from skills.self_awareness import SelfAwarenessReviewer, SelfAwarenessReport
from skills.registry import SkillRegistry
from skills.capability import CapabilityCard, CapabilityStatus, SkillEvidence, EvidenceStrength
from self_awareness import DriftDetector, DriftAssessment, GPSCentinella, Destination


@dataclass
class AgentBase:
    """
    Base class for every agent in the MASTER Factory.

    Every agent has:
    - A name and role
    - Its own GPS to stay on course
    - Its own Self-Awareness to check honesty
    - Its own mission
    - Its own skill registry (what it can do)
    """

    name: str = "agent"
    role: str = "worker"
    description: str = ""

    # ── Embedded navigation ──
    _gps: Optional[GPS] = None
    _self_awareness: Optional[SelfAwarenessReviewer] = None
    _drift_detector: Optional[DriftDetector] = None
    _skill_registry: Optional[SkillRegistry] = None

    # ── Agent state ──
    mission: str = ""
    status: str = "idle"  # idle, working, blocked, resetting
    started_at: datetime = field(default_factory=datetime.now)
    last_check: Optional[datetime] = None
    actions: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # ── Auto-evolution ──
    skills_generated: List[str] = field(default_factory=list)  # IDs of auto-generated skills
    health_history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """Initialize GPS, Self-Awareness, and DriftDetector on creation."""
        if self._gps is None:
            self._gps = GPS()
        if self._skill_registry is None:
            self._skill_registry = SkillRegistry()
        if self._drift_detector is None:
            self._drift_detector = DriftDetector(
                gps=GPSCentinella(_gps=self._gps),
                destination=Destination(),
            )
        self.set_mission(self.mission or f"Be a reliable {self.role}")

    # ── GPS Navigation ───────────────────────────────────────────────

    def set_mission(self, mission: str) -> None:
        """Set this agent's mission and align GPS + DriftDetector."""
        self.mission = mission
        if self._gps:
            self._gps.set_destination(mission)
        if self._drift_detector:
            self._drift_detector.set_destination(mission)

    def check_course(self, action: str) -> NavigationCheck:
        """
        Check if an action is on course for this agent's mission.

        Returns NavigationCheck for backward compatibility.
        Internally also runs DriftDetector assessment to detect true drift.
        """
        if self._gps is None:
            return NavigationCheck(
                action=action,
                alignment_score=0.5,
                is_on_course=True,
                recommendation="proceed",
                reasoning="No GPS available — proceeding",
            )

        # Run DriftDetector assessment for true drift detection
        if self._drift_detector and self._drift_detector.is_active:
            drift_assessment = self._drift_detector.assess_action(action)
            # If drift detected and should ask user, log it
            if drift_assessment.should_ask_user:
                self.errors.append(
                    f"DRIFT DETECTED: {drift_assessment.reason[:100]}"
                )
                self.actions.append(f"[DRIFT] {action[:80]}")

        # Legacy GPS check
        nav = self._gps.check_course(action)
        self.actions.append(f"[{nav.recommendation}] {action[:80]}")
        self.last_check = datetime.now()
        return nav

    def check_drift(self, action: str) -> DriftAssessment:
        """
        Run a full drift assessment on an action.

        Returns DriftAssessment with:
        - decision: "proceed", "fix_pothole", "ask_user", "abort"
        - should_ask_user: True if user needs to be consulted
        """
        if self._drift_detector is None:
            self._drift_detector = DriftDetector(
                gps=GPSCentinella(_gps=self._gps or GPS()),
                destination=Destination(),
            )
            if self.mission:
                self._drift_detector.set_destination(self.mission)

        return self._drift_detector.assess_action(action)

    def report_pothole(
        self,
        description: str,
        severity: str = "moderate",
        related_action: str = "",
    ) -> Optional[DriftAssessment]:
        """
        Report a problem (pothole) encountered during task execution.

        The DriftDetector determines if it's a fixable pothole or true drift.
        """
        if self._drift_detector is None:
            return None
        return self._drift_detector.assess_pothole(
            description=description,
            severity=severity,
            related_action=related_action,
        )

    def summary_gps(self) -> str:
        """Human-readable GPS + DriftDetector status for this agent."""
        parts = []
        if self._gps and self._gps.destination:
            parts.append(f"🧭 [{self.name}] Destination: {self._gps.destination[:60]}")
        else:
            parts.append(f"🧭 [{self.name}] No destination set")

        if self._drift_detector and self._drift_detector.is_active:
            consensus = self._drift_detector.destination.consensus_with_gps(
                self._drift_detector.gps.destination
            )
            status = "🟢" if consensus["consensus"] else "🔴"
            parts.append(f"   {status} Consensus: {consensus['verdict']}")

        return "\n".join(parts) if len(parts) > 1 else parts[0]

    # ── Self-Awareness ───────────────────────────────────────────────

    def init_self_awareness(self, mission_statement: str = "") -> None:
        """Initialize this agent's Self-Awareness reviewer."""
        if self._self_awareness is None and self._skill_registry:
            self._self_awareness = SelfAwarenessReviewer(
                registry=self._skill_registry,
                mission_statement=mission_statement or self.description,
                current_mission=self.mission,
            )

    def review_self(self) -> Optional[SelfAwarenessReport]:
        """Run a self-awareness check on this agent."""
        if self._self_awareness is None:
            self.init_self_awareness()

        if self._self_awareness is None:
            return None

        report = self._self_awareness.review(
            recent_actions=self.actions[-20:] if self.actions else ["idle"],
            claimed_capabilities=self.get_capabilities(),
        )

        self.health_history.append({
            "timestamp": datetime.now().isoformat(),
            "health": report.overall_health,
            "mission_alignment": report.mission_alignment_score,
            "findings": len(report.critical_findings) + len(report.warning_findings),
        })

        # Trim history
        if len(self.health_history) > 50:
            self.health_history = self.health_history[-50:]

        return report

    def am_i_honest(self) -> bool:
        """Quick check: am I being honest right now?"""
        report = self.review_self()
        if report is None:
            return True  # No self-awareness → assume honest
        return report.overall_health != "critical"

    # ── Skills ───────────────────────────────────────────────────────

    def register_skill(self, card: CapabilityCard) -> None:
        """Register a capability in this agent's skill registry."""
        if self._skill_registry:
            self._skill_registry.register(card)

    def get_capabilities(self) -> List[str]:
        """Get this agent's active capabilities."""
        if self._skill_registry:
            return self._skill_registry.get_active_capabilities()
        return []

    def has_capability(self, name: str) -> bool:
        """Check if this agent has a specific capability."""
        return name in self.get_capabilities()

    # ── Status ───────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get this agent's current status."""
        nav_status = {}
        if self._gps and self._gps.destination:
            nav_status = {
                "destination": self._gps.destination,
                "waypoints": len(self._gps.waypoints),
                "drift_checks": len(self._gps.navigation_history),
            }

        drift_status = {}
        if self._drift_detector:
            consensus = self._drift_detector.destination.consensus_with_gps(
                self._drift_detector.gps.destination
            ) if self._drift_detector.has_destination else {"verdict": "no_destination"}
            drift_status = {
                "active": self._drift_detector.is_active,
                "consensus": consensus["verdict"],
                "consensus_score": consensus.get("score", 1.0),
                "assessments": len(self._drift_detector.assessments),
            }

        health_status = {}
        if self.health_history:
            last = self.health_history[-1]
            health_status = {
                "last_health": last["health"],
                "last_check": last["timestamp"],
            }

        return {
            "name": self.name,
            "role": self.role,
            "mission": self.mission[:100],
            "status": self.status,
            "actions": len(self.actions),
            "errors": len(self.errors),
            "capabilities": self.get_capabilities(),
            "skills_generated": len(self.skills_generated),
            "navigation": nav_status,
            "drift_detection": drift_status,
            "health": health_status,
        }

    def summary(self) -> str:
        """Human-readable agent summary."""
        lines = [
            f"🤖 [{self.name}] {self.role}",
            f"   Status: {self.status}",
            f"   Mission: {self.mission[:80]}",
            f"   Actions: {len(self.actions)} | Errors: {len(self.errors)}",
            f"   Capabilities: {len(self.get_capabilities())}",
            f"   Skills generated: {len(self.skills_generated)}",
        ]
        return "\n".join(lines)

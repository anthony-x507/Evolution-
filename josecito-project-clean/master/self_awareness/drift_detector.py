"""
MASTER Self-Awareness — Drift Detector
======================================
The DriftDetector is the decision-maker of the self-awareness system.
It coordinates between the GPS Centinella and the Destination
to answer the critical question:

    "Are we still on track, or have we drifted?"

When a problem or deviation is detected, the DriftDetector:
1. Consults the GPS Centinella → "Where are we on the route?"
2. Consults the Destination → "Where were we supposed to go?"
3. Compares their answers for CONSENSUS

   ✅ CONSENSUS (both agree on destination):
      → It's a POTHole — fixable problem on the same road.
      → Continue, fix the problem, don't bother the user.

   ❌ NO CONSENSUS (GPS and Destination disagree):
      → TRUE DRIFT — we've wandered off the mission.
      → STOP and ASK THE USER:
        "I've detected a deviation from the mission.
         Do you want to continue on the original path,
         or are we working on something different now?"

Key principle: "The sentinel watches. The destination guides.
The detector decides when to stop and ask."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .destination import Destination
from .gps_centinella import GPSCentinella, Pothole, RouteReport


@dataclass
class DriftAssessment:
    """
    The result of a drift detection analysis.

    This is the DriftDetector's answer to:
    "Should we keep going, or stop and ask the user?"
    """

    # ── What triggered this assessment ──
    triggered_by: str  # "action_check", "pothole", "periodic_review"
    triggered_action: str = ""

    # ── GPS Centinella verdict ──
    gps_alignment: float = 1.0
    gps_on_course: bool = True
    gps_destination: str = ""

    # ── Destination verdict ──
    destination_goal: str = ""
    destination_alignment: float = 1.0

    # ── Consensus ──
    consensus_score: float = 1.0
    has_consensus: bool = True
    consensus_verdict: str = "aligned"  # "aligned", "diverged", "no_destination"

    # ── Decision ──
    decision: str = "proceed"  # "proceed", "fix_pothole", "ask_user", "abort"
    reason: str = ""
    should_ask_user: bool = False
    user_question: str = ""

    # ── Metadata ──
    assessed_at: datetime = field(default_factory=datetime.now)
    pothole: Optional[Pothole] = None


@dataclass
class DriftDetector:
    """
    The DriftDetector — MASTER's drift detection and decision engine.

    Coordinates GPS Centinella + Destination to detect drift,
    distinguish potholes from true deviations, and decide when
    to ask the user for guidance.

    Lifecycle:
    1. set_destination() → activates both GPS and Destination
    2. assess_action() → called before every action
    3. assess_pothole() → called when a problem is encountered
    4. The detector returns a DriftAssessment with a decision
    """

    # ── Subsystems ──
    gps: GPSCentinella = field(default_factory=GPSCentinella)
    destination: Destination = field(default_factory=Destination)

    # ── Configuration ──
    auto_ask_user: bool = True  # If True, flags should_ask_user on drift
    drift_sensitivity: float = 0.5  # Higher = more sensitive to drift
    pothole_severity_threshold: str = "major"  # Blocking to ask user automatically

    # ── History ──
    assessments: List[DriftAssessment] = field(default_factory=list)
    max_assessments: int = 200
    user_override_active: bool = False  # True when user said "keep going"

    # ── Callbacks ──
    on_drift_detected: Optional[Callable[[DriftAssessment], None]] = None
    on_user_question_needed: Optional[Callable[[str], None]] = None

    def set_destination(
        self,
        goal: str,
        description: str = "",
        waypoints: Optional[List[str]] = None,
        set_by: str = "user",
    ) -> None:
        """
        Set the mission destination on all subsystems.

        This activates both the GPS Centinella and the Destination
        folder simultaneously — they work as a pair from this point.
        """
        self.destination.set(goal, description, set_by=set_by)
        self.gps.set_destination(goal, waypoints)
        self.user_override_active = False

    @property
    def has_destination(self) -> bool:
        """Is a destination currently set?"""
        return self.destination.is_set()

    @property
    def is_active(self) -> bool:
        """Is the drift detection system active?"""
        return self.has_destination and self.gps.is_monitoring

    # ──────────────────────────────────────────────────────────────────
    # Core Assessment
    # ──────────────────────────────────────────────────────────────────

    def assess_action(self, action: str) -> DriftAssessment:
        """
        Assess an action BEFORE execution for drift risk.

        This is the main entry point. Call before every action
        to check if it's aligned with the mission destination.

        Returns a DriftAssessment with:
        - decision: "proceed", "fix_pothole", "ask_user", "abort"
        - should_ask_user: True if the user needs to be consulted
        - user_question: The question to ask the user (if should_ask_user)
        """
        assessment = DriftAssessment(
            triggered_by="action_check",
            triggered_action=action,
        )

        # ── Step 1: GPS Centinella checks the route ──
        nav = self.gps.check_course(action)
        assessment.gps_alignment = nav.alignment_score
        assessment.gps_on_course = nav.is_on_course
        assessment.gps_destination = self.gps.destination

        # ── Step 2: Destination checks alignment ──
        assessment.destination_goal = self.destination.goal
        assessment.destination_alignment = self.destination.alignment_score(action)

        # ── Step 3: Check consensus between GPS and Destination ──
        consensus = self.destination.consensus_with_gps(self.gps.destination)
        assessment.consensus_score = consensus["score"]
        assessment.has_consensus = consensus["consensus"]
        assessment.consensus_verdict = consensus["verdict"]

        # ── Step 4: Decision logic ──
        assessment = self._decide(assessment, nav)

        # ── Track ──
        self.assessments.append(assessment)
        if len(self.assessments) > self.max_assessments:
            self.assessments = self.assessments[-self.max_assessments:]

        # ── Fire callbacks ──
        if assessment.should_ask_user and self.on_drift_detected:
            self.on_drift_detected(assessment)

        return assessment

    def assess_pothole(
        self,
        description: str,
        severity: str = "moderate",
        related_action: str = "",
    ) -> DriftAssessment:
        """
        Assess a pothole (problem) encountered during execution.

        When something goes wrong, this method determines if it's:
        - A pothole on the same road (keep going, fix it)
        - A sign we've drifted off course (stop, ask user)
        """
        # Report the pothole to the Centinella
        pothole = self.gps.report_pothole(description, severity, related_action)

        assessment = DriftAssessment(
            triggered_by="pothole",
            triggered_action=related_action,
            pothole=pothole,
        )

        # ── Get current route status ──
        assessment.gps_alignment = self.gps._gps.current_alignment()
        assessment.gps_on_course = assessment.gps_alignment >= self.gps._gps.drift_warning_threshold
        assessment.gps_destination = self.gps.destination

        # ── Destination alignment ──
        assessment.destination_goal = self.destination.goal
        assessment.destination_alignment = self.destination.alignment_score(related_action)

        # ── Consensus check ──
        # For potholes, we check if the GPS and Destination still agree
        # If they agree, it's just a pothole — fix it and keep going
        # If they DON'T agree, the pothole may have caused drift
        consensus = self.destination.consensus_with_gps(self.gps.destination)
        assessment.consensus_score = consensus["score"]
        assessment.has_consensus = consensus["consensus"]
        assessment.consensus_verdict = consensus["verdict"]

        # ── Decision ──
        severity_order = {"blocking": 0, "major": 1, "moderate": 2, "minor": 3}
        threshold = severity_order.get(self.pothole_severity_threshold, 1)

        if severity_order.get(severity, 99) <= threshold and not assessment.has_consensus:
            # Serious pothole + consensus lost → true drift
            assessment.decision = "ask_user"
            assessment.should_ask_user = True
            assessment.reason = (
                f"Blocking pothole ('{description}') combined with loss of consensus "
                f"between GPS and Destination (score: {assessment.consensus_score:.0%}). "
                f"This may indicate the mission has drifted."
            )
            assessment.user_question = self._form_drift_question(assessment)
        elif severity_order.get(severity, 99) <= threshold:
            # Serious pothole but consensus holds → fix it, don't ask
            assessment.decision = "fix_pothole"
            assessment.should_ask_user = False
            assessment.reason = (
                f"Pothole detected ('{description}') but consensus holds. "
                f"Fix it and continue toward destination."
            )
        else:
            # Minor pothole → log it, keep going
            assessment.decision = "proceed"
            assessment.should_ask_user = False
            assessment.reason = (
                f"Minor pothole ('{description}') — logged and continuing."
            )

        # ── Track ──
        self.assessments.append(assessment)
        if len(self.assessments) > self.max_assessments:
            self.assessments = self.assessments[-self.max_assessments:]

        if assessment.should_ask_user and self.on_drift_detected:
            self.on_drift_detected(assessment)

        return assessment

    def periodic_review(self) -> DriftAssessment:
        """
        Periodic self-check — are we still on course?

        Runs a full consensus check between GPS and Destination
        without a specific action trigger. Useful for background
        monitoring.
        """
        assessment = DriftAssessment(
            triggered_by="periodic_review",
        )

        assessment.gps_alignment = self.gps._gps.current_alignment()
        assessment.gps_on_course = assessment.gps_alignment >= self.gps._gps.drift_warning_threshold
        assessment.gps_destination = self.gps.destination
        assessment.destination_goal = self.destination.goal

        consensus = self.destination.consensus_with_gps(self.gps.destination)
        assessment.consensus_score = consensus["score"]
        assessment.has_consensus = consensus["consensus"]
        assessment.consensus_verdict = consensus["verdict"]

        if not assessment.has_consensus and not self.user_override_active:
            assessment.decision = "ask_user"
            assessment.should_ask_user = True
            assessment.reason = (
                f"Periodic review detected consensus drift "
                f"(score: {assessment.consensus_score:.0%}). "
                f"GPS and Destination may no longer agree on the mission."
            )
            assessment.user_question = self._form_drift_question(assessment)
        else:
            assessment.decision = "proceed"
            assessment.should_ask_user = False
            assessment.reason = "Periodic review — all systems aligned."

        self.assessments.append(assessment)
        if len(self.assessments) > self.max_assessments:
            self.assessments = self.assessments[-self.max_assessments:]

        return assessment

    # ──────────────────────────────────────────────────────────────────
    # Decision Logic
    # ──────────────────────────────────────────────────────────────────

    def _decide(
        self,
        assessment: DriftAssessment,
        nav: Any,
    ) -> DriftAssessment:
        """
        Core decision logic: proceed, fix, ask, or abort?

        Decision matrix:
        ┌──────────────────┬────────────────┬──────────────────┐
        │   Situation       │ Consensus      │ Decision          │
        ├──────────────────┼────────────────┼──────────────────┤
        │ On course         │ YES            │ proceed           │
        │ Slight drift      │ YES            │ proceed (warn)    │
        │ Slight drift      │ NO             │ ask_user          │
        │ Off course        │ YES (pothole)  │ fix_pothole       │
        │ Off course        │ NO (true drift)│ ask_user          │
        │ No destination    │ N/A            │ proceed           │
        └──────────────────┴────────────────┴──────────────────┘
        """
        # No destination set → free navigation
        if not self.has_destination:
            assessment.decision = "proceed"
            assessment.should_ask_user = False
            assessment.reason = "No destination set — free navigation."
            return assessment

        # User override active → proceed regardless
        if self.user_override_active:
            assessment.decision = "proceed"
            assessment.should_ask_user = False
            assessment.reason = "User override active — proceeding."
            return assessment

        # On course → proceed
        if nav.recommendation == "proceed":
            assessment.decision = "proceed"
            assessment.should_ask_user = False
            assessment.reason = f"On course (alignment: {assessment.gps_alignment:.0%})."
            return assessment

        # Recalibrate (slight drift) → check consensus
        if nav.recommendation == "recalibrate":
            if assessment.has_consensus:
                # Slight drift but consensus holds → warn but proceed
                assessment.decision = "proceed"
                assessment.should_ask_user = False
                assessment.reason = (
                    f"Slight drift detected but consensus holds. "
                    f"Recalibrating (GPS: {assessment.gps_alignment:.0%}, "
                    f"Consensus: {assessment.consensus_score:.0%})."
                )
            else:
                # Slight drift AND no consensus → TRUE DRIFT
                assessment.decision = "ask_user"
                assessment.should_ask_user = True
                assessment.reason = (
                    f"Slight drift detected AND consensus lost "
                    f"(GPS: {assessment.gps_alignment:.0%}, "
                    f"Consensus: {assessment.consensus_score:.0%}). "
                    f"This is TRUE DRIFT — the agent has deviated from the mission."
                )
                assessment.user_question = self._form_drift_question(assessment)
            return assessment

        # Abort (severe drift) → always check consensus
        if nav.recommendation == "abort":
            if assessment.has_consensus:
                # Severe misalignment but same destination → pothole
                assessment.decision = "fix_pothole"
                assessment.should_ask_user = False
                assessment.reason = (
                    f"Severe misalignment detected (GPS: {assessment.gps_alignment:.0%}) "
                    f"but consensus holds. This is a POTHole, not drift. Fix and continue."
                )
            else:
                # Severe misalignment AND no consensus → TRUE DRIFT
                assessment.decision = "ask_user"
                assessment.should_ask_user = True
                assessment.reason = (
                    f"CRITICAL: Severe misalignment (GPS: {assessment.gps_alignment:.0%}) "
                    f"AND consensus lost (score: {assessment.consensus_score:.0%}). "
                    f"GPS says: '{assessment.gps_destination[:80]}'. "
                    f"Destination says: '{assessment.destination_goal[:80]}'. "
                    f"These no longer match. The agent must ask the user."
                )
                assessment.user_question = self._form_drift_question(assessment)
            return assessment

        # Default
        assessment.decision = "proceed"
        assessment.should_ask_user = False
        assessment.reason = "Default — proceeding."
        return assessment

    # ──────────────────────────────────────────────────────────────────
    # User Interaction
    # ──────────────────────────────────────────────────────────────────

    def _form_drift_question(self, assessment: DriftAssessment) -> str:
        """
        Form the question to ask the user when drift is detected.

        The question must be clear, non-technical, and give the user
        a simple choice: stay on the original path, or confirm a new direction.
        """
        dest = self.destination.goal[:80]
        gps_dest = self.gps.destination[:80]

        return (
            f"🧭 I've detected a deviation from the current mission.\n\n"
            f"   Original destination: {dest}\n"
            f"   Current GPS route: {gps_dest}\n\n"
            f"   These no longer align (consensus: {assessment.consensus_score:.0%}).\n\n"
            f"   Would you like me to:\n"
            f"   A) Continue on the ORIGINAL path toward '{dest[:60]}...'\n"
            f"   B) Confirm we're working on something DIFFERENT now"
        )

    def user_confirms_continue(self) -> None:
        """
        User chose option A: continue on the original path.

        The detector resets the GPS to align with the Destination
        and clears any drift flags.
        """
        self.gps.set_destination(self.destination.goal)
        self.user_override_active = False
        # Resolve any active potholes
        for p in self.gps.get_active_potholes():
            p.resolve("User confirmed original path — pothole bypassed")

    def user_confirms_redirect(self, new_destination: str = "") -> None:
        """
        User chose option B: we're working on something different.

        If a new destination is provided, it's set.
        Otherwise, the current GPS destination becomes the new goal.
        """
        if new_destination:
            self.set_destination(new_destination, set_by="user_redirect")
        else:
            # Use whatever the GPS currently thinks is the destination
            self.destination.set(
                self.gps.destination,
                set_by="user_redirect",
            )
        self.user_override_active = False

    def user_overrides(self) -> None:
        """
        User says 'keep going, I know what I'm doing.'

        Sets an override flag that suppresses drift questions
        until the destination is changed.
        """
        self.user_override_active = True

    # ──────────────────────────────────────────────────────────────────
    # Status & Summaries
    # ──────────────────────────────────────────────────────────────────

    def get_route_report(self) -> RouteReport:
        """Get the full route report from the GPS Centinella."""
        return self.gps.get_route_report()

    def status(self) -> Dict[str, Any]:
        """Get the full drift detector status."""
        last = self.assessments[-1] if self.assessments else None

        return {
            "active": self.is_active,
            "destination": self.destination.status(),
            "gps": self.gps.status(),
            "consensus": self.destination.consensus_with_gps(self.gps.destination) if self.has_destination else {"verdict": "no_destination"},
            "last_decision": last.decision if last else "none",
            "last_reason": last.reason if last else "",
            "should_ask_user": last.should_ask_user if last else False,
            "user_override_active": self.user_override_active,
            "assessments_count": len(self.assessments),
        }

    def summary(self) -> str:
        """Human-readable drift detector summary."""
        if not self.has_destination:
            return "🔍 DriftDetector: No destination set. Standing by."

        consensus = self.destination.consensus_with_gps(self.gps.destination)
        last = self.assessments[-1] if self.assessments else None

        status_emoji = "🟢" if consensus["consensus"] else "🔴"
        override_note = " [USER OVERRIDE]" if self.user_override_active else ""

        lines = [
            f"{status_emoji} DRIFT DETECTOR{override_note}",
            self.destination.summary(),
            f"   Consensus: {consensus['verdict'].upper()} ({consensus['score']:.0%})",
        ]

        if last and last.decision != "proceed":
            lines.append(f"   Last Decision: {last.decision.upper()} — {last.reason[:100]}")

        active_potholes = self.gps.get_active_potholes()
        if active_potholes:
            lines.append(f"   Active Potholes: {len(active_potholes)}")

        return "\n".join(lines)

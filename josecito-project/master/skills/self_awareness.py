"""
MASTER Self-Awareness Reviewer
==============================
The self-awareness system is MASTER's internal conscience.
It continuously asks: "Are we still doing what we said we would do?
Are we being honest about our capabilities? Have we drifted?"

This is the "connecting with its self-awareness" mechanism —
the meta-cognitive layer that reviews MASTER's own behavior
against its declared skills, mission, and principles.

The self-awareness reviewer operates in layers:
1. Capability honesty — are we claiming only what we can do?
2. Mission alignment — are we still on the right path?
3. Behavioral consistency — are we acting like MASTER?
4. Evidence freshness — is our evidence still valid?
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from .capability import CapabilityCard, CapabilityStatus, SkillEvidence, EvidenceStrength
from .registry import SkillRegistry
from .checker import HonestyReport, HonestyViolation


@dataclass
class SelfAwarenessFinding:
    """A single finding from the self-awareness review."""

    layer: str  # "capability", "mission", "behavior", "evidence"
    severity: str  # "critical", "warning", "info"
    description: str
    skill_name: Optional[str] = None
    detected_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False


@dataclass
class SelfAwarenessReport:
    """
    A comprehensive self-awareness review report.

    This is MASTER looking in the mirror and asking:
    "Am I being honest? Am I still on track? Am I who I claim to be?"
    """

    findings: List[SelfAwarenessFinding] = field(default_factory=list)
    honesty_report: Optional[HonestyReport] = None
    mission_alignment_score: float = 1.0  # 1.0 = perfect alignment
    behavioral_consistency_score: float = 1.0
    evidence_freshness_score: float = 1.0
    overall_health: str = "healthy"  # "healthy", "warning", "critical"
    generated_at: datetime = field(default_factory=datetime.now)
    review_duration_ms: float = 0.0

    @property
    def is_healthy(self) -> bool:
        return self.overall_health == "healthy"

    @property
    def critical_findings(self) -> List[SelfAwarenessFinding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def warning_findings(self) -> List[SelfAwarenessFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    def summary(self) -> str:
        """One-line health summary."""
        emoji = {"healthy": "🟢", "warning": "🟡", "critical": "🔴"}
        return (
            f"{emoji.get(self.overall_health, '⚪')} MASTER Self-Awareness: "
            f"{self.overall_health.upper()} | "
            f"Mission: {self.mission_alignment_score:.0%} | "
            f"Behavior: {self.behavioral_consistency_score:.0%} | "
            f"Evidence: {self.evidence_freshness_score:.0%} | "
            f"Findings: {len(self.critical_findings)} critical, "
            f"{len(self.warning_findings)} warnings"
        )

    def detailed_summary(self) -> str:
        """Detailed multi-line summary."""
        lines = [
            "=" * 60,
            "🧠 MASTER SELF-AWARENESS REVIEW",
            "=" * 60,
            f"Overall: {self.overall_health.upper()}",
            f"Mission Alignment: {self.mission_alignment_score:.0%}",
            f"Behavioral Consistency: {self.behavioral_consistency_score:.0%}",
            f"Evidence Freshness: {self.evidence_freshness_score:.0%}",
        ]

        if self.honesty_report:
            lines.append(f"\n--- Honesty ---")
            lines.append(self.honesty_report.summary())

        if self.critical_findings:
            lines.append(f"\n--- 🔴 Critical Findings ({len(self.critical_findings)}) ---")
            for f in self.critical_findings:
                lines.append(f"   {f.description}")

        if self.warning_findings:
            lines.append(f"\n--- 🟡 Warnings ({len(self.warning_findings)}) ---")
            for f in self.warning_findings:
                lines.append(f"   {f.description}")

        lines.append("=" * 60)
        return "\n".join(lines)


@dataclass
class SelfAwarenessReviewer:
    """
    The self-awareness review engine.

    This is MASTER's "conscience" — it continuously reviews the system's
    own behavior against its declared identity, capabilities, and mission.

    Key principle: "No single AI can convict its own opinion."
    The SelfAwarenessReviewer provides the evidence that the Reviewer
    and Auditor intelligences use to make decisions.
    """

    registry: SkillRegistry
    mission_statement: str = ""
    current_mission: str = ""

    # Review configuration
    check_interval_seconds: int = 60
    max_findings_per_review: int = 50
    auto_resolve_old_findings: bool = True
    finding_ttl_hours: int = 24

    # History
    review_history: List[SelfAwarenessReport] = field(default_factory=list)
    last_review: Optional[datetime] = None

    # Callbacks for integration
    on_critical_finding: Optional[Callable[[SelfAwarenessFinding], None]] = None
    on_health_change: Optional[Callable[[str, str], None]] = None

    def review(
        self,
        recent_actions: Optional[List[str]] = None,
        claimed_capabilities: Optional[List[str]] = None,
    ) -> SelfAwarenessReport:
        """
        Run a full self-awareness review across all layers.

        This is the main entry point for MASTER's self-reflection.
        """
        start_time = datetime.now()
        report = SelfAwarenessReport()

        # Layer 1: Capability honesty
        if claimed_capabilities:
            from .checker import CapabilityHonestyChecker
            checker = CapabilityHonestyChecker(self.registry, strict_mode=True)
            report.honesty_report = checker.check(claimed_capabilities)
            if not report.honesty_report.is_honest:
                for v in report.honesty_report.violations:
                    report.findings.append(SelfAwarenessFinding(
                        layer="capability",
                        severity=v.severity,
                        description=v.summary(),
                        skill_name=v.skill_name,
                    ))

        # Layer 2: Mission alignment
        if self.current_mission:
            alignment = self._check_mission_alignment(recent_actions or [])
            report.mission_alignment_score = alignment["score"]
            for issue in alignment["issues"]:
                report.findings.append(SelfAwarenessFinding(
                    layer="mission",
                    severity=issue["severity"],
                    description=issue["description"],
                ))

        # Layer 3: Behavioral consistency
        behavior = self._check_behavioral_consistency()
        report.behavioral_consistency_score = behavior["score"]
        for issue in behavior["issues"]:
            report.findings.append(SelfAwarenessFinding(
                layer="behavior",
                severity=issue["severity"],
                description=issue["description"],
            ))

        # Layer 4: Evidence freshness
        evidence = self._check_evidence_freshness()
        report.evidence_freshness_score = evidence["score"]
        for issue in evidence["issues"]:
            report.findings.append(SelfAwarenessFinding(
                layer="evidence",
                severity=issue["severity"],
                description=issue["description"],
                skill_name=issue.get("skill_name"),
            ))

        # Determine overall health
        report.overall_health = self._determine_health(report)

        # Track history
        self.review_history.append(report)
        self.last_review = datetime.now()

        # Trim history if too long
        if len(self.review_history) > 100:
            self.review_history = self.review_history[-100:]

        # Fire callbacks
        if report.critical_findings and self.on_critical_finding:
            for finding in report.critical_findings:
                if self.on_critical_finding:
                    self.on_critical_finding(finding)

        report.review_duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return report

    def quick_check(self, action: str) -> bool:
        """
        Quick self-check before an action: "Should I do this?"
        Returns True if the action passes all checks.
        """
        from .checker import CapabilityHonestyChecker

        checker = CapabilityHonestyChecker(self.registry, strict_mode=True)
        report = checker.preflight_check(action)

        if not report.is_honest:
            return False

        # Also check mission alignment
        if self.current_mission:
            alignment = self._check_single_action_alignment(action)
            if alignment < 0.3:
                return False

        return True

    def _check_mission_alignment(
        self, recent_actions: List[str]
    ) -> Dict[str, Any]:
        """
        Check if recent actions align with the current mission.

        Returns a score (0.0 = total drift, 1.0 = perfect alignment)
        and a list of issues.
        """
        issues: List[Dict] = []

        if not self.current_mission or not recent_actions:
            return {"score": 1.0, "issues": issues}

        # Simplified alignment check — in production, this would use
        # semantic similarity or the Auditor intelligence
        mission_keywords = set(self.current_mission.lower().split())
        total_actions = len(recent_actions)
        aligned_actions = 0

        for action in recent_actions:
            action_keywords = set(action.lower().split())
            overlap = mission_keywords & action_keywords
            if overlap or len(mission_keywords) == 0:
                aligned_actions += 1

        score = aligned_actions / max(total_actions, 1)

        if score < 0.5:
            issues.append({
                "severity": "critical",
                "description": (
                    f"Mission drift detected: only {score:.0%} of recent "
                    f"actions align with mission '{self.current_mission[:50]}...'"
                ),
            })
        elif score < 0.7:
            issues.append({
                "severity": "warning",
                "description": (
                    f"Slight mission drift: {score:.0%} alignment with "
                    f"current mission"
                ),
            })

        return {"score": score, "issues": issues}

    def _check_behavioral_consistency(self) -> Dict[str, Any]:
        """
        Check that MASTER is behaving consistently with its identity.

        This prevents identity confusion — MASTER should always
        act like MASTER, not like another system.
        """
        issues: List[Dict] = []
        score = 1.0

        # Check that all required layers are active
        registry_report = self.registry.check_integrity()
        if not registry_report.is_healthy:
            score -= 0.2
            issues.append({
                "severity": "warning",
                "description": "Skill registry has integrity issues",
            })

        # Check for skills without self-checks
        for name, card in self.registry.cards.items():
            if card.self_check_enabled and card.self_check_issues:
                score -= 0.1
                issues.append({
                    "severity": "warning",
                    "description": f"Skill '{name}' has unresolved self-check issues",
                    "skill_name": name,
                })

        return {"score": max(0.0, score), "issues": issues}

    def _check_evidence_freshness(self) -> Dict[str, Any]:
        """
        Check that evidence for active skills is still fresh.

        Stale evidence is dishonest — it implies a capability
        that may no longer work.
        """
        issues: List[Dict] = []
        total_active = 0
        stale_count = 0
        now = datetime.now()
        max_age = timedelta(hours=24)

        for name, card in self.registry.cards.items():
            if card.status != CapabilityStatus.ACTIVE:
                continue
            total_active += 1

            if card.evidence_collected:
                for ev in card.evidence_collected:
                    if ev.expires_at and ev.expires_at < now:
                        stale_count += 1
                        issues.append({
                            "severity": "warning",
                            "description": (
                                f"Evidence for '{name}' has expired "
                                f"(expired: {ev.expires_at.isoformat()})"
                            ),
                            "skill_name": name,
                        })
                        break
            elif card.evidence_required:
                stale_count += 1
                issues.append({
                    "severity": "warning",
                    "description": f"Skill '{name}' has no evidence collected",
                    "skill_name": name,
                })

        if total_active == 0:
            score = 1.0
        else:
            score = 1.0 - (stale_count / total_active)

        return {"score": max(0.0, score), "issues": issues}

    def _check_single_action_alignment(self, action: str) -> float:
        """Quick alignment check for a single action."""
        if not self.current_mission:
            return 1.0
        mission_words = set(self.current_mission.lower().split())
        action_words = set(action.lower().split())
        overlap = mission_words & action_words
        return len(overlap) / max(len(mission_words), 1)

    def _determine_health(self, report: SelfAwarenessReport) -> str:
        """Determine overall health from findings and scores."""
        if report.critical_findings:
            return "critical"
        if report.warning_findings:
            return "warning"
        if report.mission_alignment_score < 0.5:
            return "warning"
        if report.behavioral_consistency_score < 0.5:
            return "warning"
        if report.evidence_freshness_score < 0.5:
            return "warning"
        return "healthy"

    def get_trend(self, last_n: int = 5) -> List[float]:
        """Get the health trend over the last N reviews."""
        history = self.review_history[-last_n:]
        if not history:
            return []
        return [
            1.0 if r.overall_health == "healthy"
            else 0.5 if r.overall_health == "warning"
            else 0.0
            for r in history
        ]

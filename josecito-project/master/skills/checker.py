"""
MASTER Capability Honesty Checker
================================
The active enforcement mechanism for MASTER's core principle:
"If a capability is not ACTIVE in the registry, MASTER must not claim it."

This is the runtime guard that prevents MASTER from handing out
empty boxes or pretending to have capabilities it doesn't possess.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .capability import CapabilityStatus, SkillEvidence, EvidenceStrength
from .registry import SkillRegistry


@dataclass
class HonestyViolation:
    """A violation of capability honesty."""

    severity: str  # "critical", "warning", "info"
    skill_name: str
    claimed_capability: str
    reason: str
    detected_at: datetime = field(default_factory=datetime.now)
    suggested_action: str = ""

    def summary(self) -> str:
        return (
            f"🚨 [{self.severity.upper()}] {self.skill_name} "
            f"claimed '{self.claimed_capability}' but: {self.reason}"
        )


@dataclass
class HonestyReport:
    """Report from a capability honesty check."""

    is_honest: bool
    violations: List[HonestyViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.now)

    def summary(self) -> str:
        if self.is_honest:
            return "✅ MASTER is being honest about its capabilities."
        lines = [f"❌ MASTER is claiming capabilities it cannot support:"]
        for v in self.violations:
            lines.append(f"   {v.summary()}")
        return "\n".join(lines)


@dataclass
class CapabilityHonestyChecker:
    """
    The active enforcer of capability honesty.

    This checker runs on every user request (or periodically) to ensure
    MASTER never claims a capability that:
    1. Is not registered
    2. Is not ACTIVE
    3. Has no valid evidence
    4. Is explicitly listed as a limitation
    """

    registry: SkillRegistry
    strict_mode: bool = True  # If True, even warnings become violations

    def check(self, claimed_capabilities: List[str]) -> HonestyReport:
        """
        Check if the claimed capabilities are honest.

        For each claimed capability, verifies:
        - Is it registered?
        - Is it ACTIVE?
        - Is there valid evidence?
        - Is it NOT in the limitations list?
        """
        violations: List[HonestyViolation] = []
        warnings: List[str] = []

        for cap in claimed_capabilities:
            # Find which skill owns this capability
            owner = self._find_owner(cap)

            if owner is None:
                violations.append(HonestyViolation(
                    severity="critical",
                    skill_name="unknown",
                    claimed_capability=cap,
                    reason="Capability is not registered in any skill",
                    suggested_action="Register the capability or remove the claim",
                ))
                continue

            card = self.registry.get(owner)
            if card is None:
                continue

            # Check status
            if card.status == CapabilityStatus.DISABLED:
                violations.append(HonestyViolation(
                    severity="critical",
                    skill_name=owner,
                    claimed_capability=cap,
                    reason=f"Skill '{owner}' is DISABLED",
                    suggested_action="Enable the skill or stop claiming this capability",
                ))
                continue

            if card.status == CapabilityStatus.PENDING:
                msg = f"Skill '{owner}' is PENDING (not yet verified)"
                if self.strict_mode:
                    violations.append(HonestyViolation(
                        severity="warning",
                        skill_name=owner,
                        claimed_capability=cap,
                        reason=msg,
                        suggested_action="Verify the skill before claiming it",
                    ))
                else:
                    warnings.append(msg)

            if card.status == CapabilityStatus.FAILED:
                violations.append(HonestyViolation(
                    severity="critical",
                    skill_name=owner,
                    claimed_capability=cap,
                    reason=f"Skill '{owner}' FAILED verification",
                    suggested_action="Fix the skill or remove it from the registry",
                ))
                continue

            if card.status == CapabilityStatus.DEGRADED:
                warnings.append(
                    f"Skill '{owner}' is DEGRADED — capability '{cap}' may not work fully"
                )

            # Check evidence
            if card.evidence_required and not card.evidence_collected:
                violations.append(HonestyViolation(
                    severity="warning" if not self.strict_mode else "critical",
                    skill_name=owner,
                    claimed_capability=cap,
                    reason="No evidence collected for this capability",
                    suggested_action="Collect evidence before claiming this capability",
                ))

            # Check limitations
            for limitation in card.limitations:
                if limitation.lower() in cap.lower():
                    violations.append(HonestyViolation(
                        severity="critical",
                        skill_name=owner,
                        claimed_capability=cap,
                        reason=f"This is explicitly listed as a limitation of '{owner}'",
                        suggested_action="Remove the claim — this is a declared limitation",
                    ))

        # Check for orphaned capabilities — active but no owner
        active = set(self.registry.get_active_capabilities())
        claimed_set = {c.lower() for c in claimed_capabilities}
        for c in active:
            if c.lower() not in claimed_set and c.lower() not in {v.claimed_capability.lower() for v in violations}:
                pass  # It's okay to have capabilities not currently claimed

        return HonestyReport(
            is_honest=len(violations) == 0,
            violations=violations,
            warnings=warnings,
        )

    def validate_evidence(
        self, skill_name: str, capability: str
    ) -> Optional[SkillEvidence]:
        """
        Validate that a capability has supporting evidence.

        Returns the best evidence or None.
        """
        return self.registry.verify_capability(skill_name, capability)

    def preflight_check(self, requested_action: str) -> HonestyReport:
        """
        Run a preflight check before executing a user request.

        This is the "before you act, verify you CAN act" check.
        Returns an HonestyReport. If not honest, the orchestrator
        should refuse to execute the action.
        """
        # Extract capability keywords from the action
        capabilities = self._extract_capabilities(requested_action)
        return self.check(capabilities)

    def _find_owner(self, capability: str) -> Optional[str]:
        """Find which skill owns a capability."""
        cap_lower = capability.lower()
        for name, card in self.registry.cards.items():
            if card.status == CapabilityStatus.ACTIVE:
                for c in card.capabilities:
                    if c.lower() == cap_lower:
                        return name
        return None

    def _extract_capabilities(self, action: str) -> List[str]:
        """
        Extract capability claims from an action string.

        This is a simplified heuristic; in production, this would use
        NLP or the Auditor intelligence for more accurate extraction.
        """
        action_lower = action.lower()
        capabilities = []

        # Check against all registered active capabilities
        for name, card in self.registry.cards.items():
            if card.status == CapabilityStatus.ACTIVE:
                for cap in card.capabilities:
                    if cap.lower() in action_lower:
                        capabilities.append(cap)

        return capabilities if capabilities else [action]

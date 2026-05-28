"""
MASTER Skill Registry
===================
Central registry for all CapabilityCards. This is the "pharmacy shelf" —
only capabilities registered here with valid evidence can be claimed.

The Registry enforces: "A pharmacy that only sells what is actually on the shelf."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from .capability import CapabilityCard, CapabilityStatus, SkillEvidence


@dataclass
class RegistryIntegrityReport:
    """Report on the integrity of the entire skill registry."""

    total_skills: int = 0
    active_skills: int = 0
    pending_skills: int = 0
    failed_skills: int = 0
    disabled_skills: int = 0
    degraded_skills: int = 0
    skills_without_evidence: List[str] = field(default_factory=list)
    skills_with_failed_checks: List[str] = field(default_factory=list)
    orphaned_capabilities: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def is_healthy(self) -> bool:
        """Registry is healthy if no critical issues."""
        return (
            len(self.skills_without_evidence) == 0
            and len(self.skills_with_failed_checks) == 0
        )

    def summary(self) -> str:
        """Human-readable integrity summary."""
        return (
            f"🏥 Registry Health: {'✅ Healthy' if self.is_healthy else '⚠️ Issues detected'}\n"
            f"   Total: {self.total_skills} | Active: {self.active_skills} | "
            f"Pending: {self.pending_skills} | Failed: {self.failed_skills}\n"
            f"   Without evidence: {len(self.skills_without_evidence)}\n"
            f"   Failed checks: {len(self.skills_with_failed_checks)}"
        )


@dataclass
class SkillRegistry:
    """Central registry for all MASTER capability cards."""

    cards: Dict[str, CapabilityCard] = field(default_factory=dict)

    # Fast lookup indexes
    _active_capabilities: Set[str] = field(default_factory=set)
    _all_limitations: Set[str] = field(default_factory=set)

    def register(self, card: CapabilityCard) -> None:
        """Register a new capability card."""
        if card.name in self.cards:
            raise ValueError(
                f"Skill '{card.name}' is already registered. "
                f"Use update() to modify existing skills."
            )
        self.cards[card.name] = card
        self._rebuild_indexes()

    def update(self, card: CapabilityCard) -> None:
        """Update an existing capability card."""
        if card.name not in self.cards:
            raise ValueError(f"Skill '{card.name}' is not registered.")
        self.cards[card.name] = card
        self._rebuild_indexes()

    def get(self, name: str) -> Optional[CapabilityCard]:
        """Get a capability card by name."""
        return self.cards.get(name)

    def remove(self, name: str) -> None:
        """Remove a capability card from the registry."""
        if name in self.cards:
            del self.cards[name]
            self._rebuild_indexes()

    def get_active_capabilities(self) -> List[str]:
        """Get all currently active capabilities across all skills."""
        return sorted(self._active_capabilities)

    def get_all_limitations(self) -> List[str]:
        """Get all declared limitations across all skills."""
        return sorted(self._all_limitations)

    def can_do(self, capability: str) -> bool:
        """
        The central honesty check: does MASTER actually have this capability?

        This is the method that prevents "handing out empty boxes."
        """
        return capability.lower() in {
            c.lower() for c in self._active_capabilities
        }

    def cannot_do(self, action: str) -> bool:
        """Check if an action is explicitly declared as a limitation."""
        return action.lower() in {
            l.lower() for l in self._all_limitations
        }

    def verify_capability(
        self, skill_name: str, capability: str
    ) -> Optional[SkillEvidence]:
        """
        Verify a specific capability claim against its evidence.

        Returns the strongest evidence found, or None if unverified.
        """
        card = self.cards.get(skill_name)
        if card is None:
            return None

        if not card.is_honest(capability):
            return None

        # Return the strongest evidence
        strongest: Optional[SkillEvidence] = None
        for ev in card.evidence_collected:
            if not ev.is_valid():
                continue
            if strongest is None or ev.strength.value > strongest.strength.value:
                strongest = ev

        return strongest

    def check_integrity(self) -> RegistryIntegrityReport:
        """Run a full integrity check on the registry."""
        report = RegistryIntegrityReport()
        report.total_skills = len(self.cards)

        for name, card in self.cards.items():
            if card.status == CapabilityStatus.ACTIVE:
                report.active_skills += 1
                if card.evidence_required and not card.evidence_collected:
                    report.skills_without_evidence.append(name)
            elif card.status == CapabilityStatus.PENDING:
                report.pending_skills += 1
            elif card.status == CapabilityStatus.FAILED:
                report.failed_skills += 1
            elif card.status == CapabilityStatus.DISABLED:
                report.disabled_skills += 1
            elif card.status == CapabilityStatus.DEGRADED:
                report.degraded_skills += 1

            if card.self_check_issues:
                report.skills_with_failed_checks.append(name)

        report.generated_at = datetime.now()
        return report

    def _rebuild_indexes(self) -> None:
        """Rebuild fast lookup indexes."""
        self._active_capabilities.clear()
        self._all_limitations.clear()

        for card in self.cards.values():
            if card.status == CapabilityStatus.ACTIVE:
                self._active_capabilities.update(card.capabilities)
            self._all_limitations.update(card.limitations)

    def list_all(self) -> List[CapabilityCard]:
        """List all registered capability cards."""
        return list(self.cards.values())

    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "cards": {name: card.to_dict() for name, card in self.cards.items()},
            "active_capabilities": self.get_active_capabilities(),
            "all_limitations": self.get_all_limitations(),
        }

    def summary(self) -> str:
        """Human-readable summary of the registry."""
        report = self.check_integrity()
        return (
            f"{report.summary()}\n"
            f"   Active capabilities: {len(self._active_capabilities)}\n"
            f"   Declared limitations: {len(self._all_limitations)}"
        )

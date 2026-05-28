"""
MASTER Capability Card System
===========================
The foundational data model for MASTER's skill system.
Every capability in MASTER must be declared through a CapabilityCard.

This implements the principle: "A pharmacy that only sells what is
actually on the shelf." No empty boxes. No pretending.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class CapabilityStatus(Enum):
    """The current operational status of a capability."""
    PROPOSED = "proposed"       # Auto-generated, not yet formally registered
    ACTIVE = "active"           # Fully operational, verified
    PENDING = "pending"         # Registered but not yet verified
    DEGRADED = "degraded"       # Partially operational
    DISABLED = "disabled"       # Intentionally turned off
    DEPRECATED = "deprecated"   # Will be removed
    FAILED = "failed"           # Verification failed


class EvidenceStrength(Enum):
    """How strong the evidence is for a capability claim."""
    NONE = "none"
    WEAK = "weak"               # Self-reported only
    MODERATE = "moderate"       # Cross-checked by another intelligence
    STRONG = "strong"           # Externally verified
    IRREFUTABLE = "irrefutable"  # Mathematically/logically proven


@dataclass
class SkillEvidence:
    """Evidence supporting a capability claim."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    source: str = ""  # Which intelligence/tool provided this evidence
    strength: EvidenceStrength = EvidenceStrength.NONE
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    raw_output: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None

    def is_valid(self) -> bool:
        """Check if the evidence is still valid (not expired)."""
        if self.expires_at is None:
            return True
        return datetime.now() < self.expires_at

    def summary(self) -> str:
        """Human-readable evidence summary."""
        return (
            f"[{self.strength.value.upper()}] {self.description} "
            f"(source: {self.source}, verified: {self.verified_at})"
        )


@dataclass
class CapabilityCard:
    """
    A declarative capability card — the DNA of a MASTER skill.

    Each card explicitly states:
    - What it CAN do (capabilities)
    - What it CANNOT do (limitations)
    - What it NEEDS (dependencies)
    - What PROVES it works (evidence)
    """

    # Identity
    name: str
    version: str = "1.0.0"
    description: str = ""

    # Unique identifier
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Capability declarations
    capabilities: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    # Status
    status: CapabilityStatus = CapabilityStatus.PENDING

    # Evidence
    evidence_required: List[str] = field(default_factory=list)
    evidence_collected: List[SkillEvidence] = field(default_factory=list)
    last_verified: Optional[datetime] = None
    verification_method: str = ""

    # Metadata
    tags: List[str] = field(default_factory=list)
    owner: str = "master"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Self-awareness hooks
    self_check_enabled: bool = True
    self_check_frequency_seconds: int = 300
    last_self_check: Optional[datetime] = None
    self_check_issues: List[str] = field(default_factory=list)

    def can_do(self, capability: str) -> bool:
        """Check if this skill claims a specific capability."""
        if self.status != CapabilityStatus.ACTIVE:
            return False
        return capability.lower() in [c.lower() for c in self.capabilities]

    def cannot_do(self, limitation_check: str) -> bool:
        """Check if a limitation is declared."""
        return limitation_check.lower() in [l.lower() for l in self.limitations]

    def is_honest(self, claimed_capability: str) -> bool:
        """
        Core honesty check: can we support this claim with evidence?

        Returns True only if:
        1. The capability is declared
        2. The status is ACTIVE
        3. At least some evidence has been collected
        """
        if not self.can_do(claimed_capability):
            return False
        if self.status != CapabilityStatus.ACTIVE:
            return False
        if self.evidence_required and not self.evidence_collected:
            return False
        return True

    def add_evidence(self, evidence: SkillEvidence) -> None:
        """Add evidence to this capability card."""
        self.evidence_collected.append(evidence)
        self.last_verified = datetime.now()
        self.updated_at = datetime.now()

        # Auto-activate if evidence is at least moderate
        if evidence.strength in (
            EvidenceStrength.MODERATE,
            EvidenceStrength.STRONG,
            EvidenceStrength.IRREFUTABLE,
        ):
            if self.status == CapabilityStatus.PENDING:
                self.status = CapabilityStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities,
            "limitations": self.limitations,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "evidence_required": self.evidence_required,
            "evidence_count": len(self.evidence_collected),
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "tags": self.tags,
            "self_check_issues": self.self_check_issues,
        }

    def summary(self) -> str:
        """Human-readable summary of this capability."""
        return (
            f"📋 {self.name} v{self.version} [{self.status.value.upper()}]\n"
            f"   ✅ Can: {', '.join(self.capabilities) if self.capabilities else 'nothing declared'}\n"
            f"   ❌ Cannot: {', '.join(self.limitations) if self.limitations else 'no limitations declared'}\n"
            f"   📎 Dependencies: {', '.join(self.dependencies) if self.dependencies else 'none'}\n"
            f"   🧾 Evidence: {len(self.evidence_collected)}/{len(self.evidence_required)} items"
        )

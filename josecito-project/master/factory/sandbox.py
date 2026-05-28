"""
MASTER Factory Sandbox
======================
A secure, isolated environment where skills are modified and tested.
Skills enter, are isolated, get modified by internal agents,
audited, reviewed, and emerge superior.

Principle: "Nothing leaves the sandbox unverified."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from .ticket import Ticket, TicketStatus


@dataclass
class SandboxedSkill:
    """
    A skill inside the sandbox — isolated from the live system.

    While in the sandbox, the skill is:
    - Isolated (does not affect the live system)
    - Modifiable (internal agents can change it)
    - Auditable (every change is tracked)
    - Revertible (can roll back to original)
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    skill_name: str = ""
    skill_description: str = ""

    # Original and modified versions
    original_capabilities: List[str] = field(default_factory=list)
    modified_capabilities: List[str] = field(default_factory=list)
    original_limitations: List[str] = field(default_factory=list)
    modified_limitations: List[str] = field(default_factory=list)

    # Evolution tracking
    revision: int = 0
    revision_history: List[Dict[str, Any]] = field(default_factory=list)
    entered_at: datetime = field(default_factory=datetime.now)
    last_modified: Optional[datetime] = None

    # Ticket reference
    ticket_id: Optional[str] = None

    # State
    is_verified: bool = False
    is_promoted: bool = False  # True = made "superior" by Engineer
    errors: List[str] = field(default_factory=list)

    def modify(
        self,
        new_capabilities: List[str],
        new_limitations: List[str],
        changed_by: str,
        reason: str,
    ) -> int:
        """Modify the skill. Returns the new revision number."""
        self.revision += 1
        self.modified_capabilities = new_capabilities
        self.modified_limitations = new_limitations
        self.last_modified = datetime.now()

        self.revision_history.append({
            "revision": self.revision,
            "changed_by": changed_by,
            "reason": reason,
            "capabilities": new_capabilities.copy(),
            "limitations": new_limitations.copy(),
            "timestamp": datetime.now().isoformat(),
        })

        return self.revision

    def verify(self, passed: bool, findings: str = "") -> None:
        """Mark the skill as verified or flag errors."""
        self.is_verified = passed
        if not passed:
            self.errors.append(findings)

    def promote(self) -> None:
        """Promote — the Engineer marks this skill as 'superior'."""
        self.is_promoted = True

    def rollback(self, target_revision: int) -> bool:
        """
        Roll back to a specific revision (1-based).
        revision=0 restores the original. Returns True if successful.
        """
        if target_revision == 0:
            # Rollback to original
            self.revision += 1
            self.modified_capabilities = self.original_capabilities.copy()
            self.modified_limitations = self.original_limitations.copy()
            self.last_modified = datetime.now()
            self.revision_history.append({
                "revision": self.revision,
                "changed_by": "rollback",
                "reason": "Rolled back to original",
                "capabilities": self.modified_capabilities.copy(),
                "limitations": self.modified_limitations.copy(),
                "timestamp": datetime.now().isoformat(),
            })
            return True

        # target_revision is 1-based
        idx = target_revision - 1
        if idx < 0 or idx >= len(self.revision_history):
            return False

        history = self.revision_history[idx]
        self.revision += 1
        self.modified_capabilities = history["capabilities"].copy()
        self.modified_limitations = history["limitations"].copy()
        self.last_modified = datetime.now()

        self.revision_history.append({
            "revision": self.revision,
            "changed_by": "rollback",
            "reason": f"Rolled back to revision {target_revision}",
            "capabilities": self.modified_capabilities.copy(),
            "limitations": self.modified_limitations.copy(),
            "timestamp": datetime.now().isoformat(),
        })

        return True

    def is_better_than_original(self) -> bool:
        """Check if the modified skill is better than the original."""
        added = set(self.modified_capabilities) - set(self.original_capabilities)
        removed_limitations = set(self.original_limitations) - set(self.modified_limitations)
        return len(added) > 0 or len(removed_limitations) > 0

    def summary(self) -> str:
        """Human-readable sandbox skill summary."""
        status_icon = "✅" if self.is_promoted else ("🔍" if self.is_verified else "🔧")
        return (
            f"{status_icon} [{self.skill_name}] v{self.revision} "
            f"(verified={self.is_verified}, promoted={self.is_promoted}) "
            f"caps: {len(self.modified_capabilities)} | "
            f"limitations: {len(self.modified_limitations)}"
        )


@dataclass
class Sandbox:
    """
    The Sandbox — an isolated environment for skill evolution.

    Skills enter the sandbox, get modified by internal agents,
    audited, reviewed, and emerge superior.

    Only the Superior Agent can move skills in/out of the sandbox.
    The Engineer promotes skills to "superior" status.
    """

    name: str = "factory_sandbox"
    active_skills: Dict[str, SandboxedSkill] = field(default_factory=dict)
    completed_skills: List[SandboxedSkill] = field(default_factory=list)

    # Stats
    total_entered: int = 0
    total_promoted: int = 0
    total_failed: int = 0

    def enter(
        self,
        skill_name: str,
        description: str,
        capabilities: List[str],
        limitations: List[str],
        ticket_id: Optional[str] = None,
    ) -> SandboxedSkill:
        """Enter a skill into the sandbox for modification."""
        skill = SandboxedSkill(
            skill_name=skill_name,
            skill_description=description,
            original_capabilities=capabilities.copy(),
            modified_capabilities=capabilities.copy(),
            original_limitations=limitations.copy(),
            modified_limitations=limitations.copy(),
            ticket_id=ticket_id,
        )
        self.active_skills[skill.id] = skill
        self.total_entered += 1
        return skill

    def modify_skill(
        self,
        skill_id: str,
        new_capabilities: List[str],
        new_limitations: List[str],
        changed_by: str,
        reason: str,
    ) -> Optional[int]:
        """Modify a skill in the sandbox. Returns new revision or None."""
        skill = self.active_skills.get(skill_id)
        if skill is None:
            return None
        return skill.modify(new_capabilities, new_limitations, changed_by, reason)

    def verify_skill(self, skill_id: str, passed: bool, findings: str = "") -> bool:
        """Verify a skill after modification."""
        skill = self.active_skills.get(skill_id)
        if skill is None:
            return False
        skill.verify(passed, findings)
        return True

    def promote_skill(self, skill_id: str) -> bool:
        """Promote a skill to 'superior' status (Engineer action)."""
        skill = self.active_skills.get(skill_id)
        if skill is None:
            return False
        if not skill.is_verified:
            return False

        skill.promote()
        self.completed_skills.append(skill)
        del self.active_skills[skill_id]
        self.total_promoted += 1
        return True

    def reject_skill(self, skill_id: str, reason: str) -> bool:
        """Reject a skill that failed verification."""
        skill = self.active_skills.get(skill_id)
        if skill is None:
            return False

        skill.errors.append(f"REJECTED: {reason}")
        self.completed_skills.append(skill)
        del self.active_skills[skill_id]
        self.total_failed += 1
        return True

    def get_skill(self, skill_id: str) -> Optional[SandboxedSkill]:
        """Get a sandboxed skill by ID (active or completed)."""
        if skill_id in self.active_skills:
            return self.active_skills[skill_id]
        for skill in self.completed_skills:
            if skill.id == skill_id:
                return skill
        return None

    def summary(self) -> str:
        """Human-readable sandbox summary."""
        lines = [
            "🏖️  SANDBOX",
            f"   Active: {len(self.active_skills)} | "
            f"Promoted: {self.total_promoted} | "
            f"Failed: {self.total_failed} | "
            f"Total: {self.total_entered}",
        ]
        for skill in list(self.active_skills.values())[:5]:
            lines.append(f"   {skill.summary()}")
        if len(self.active_skills) > 5:
            lines.append(f"   ... and {len(self.active_skills) - 5} more")
        return "\n".join(lines)

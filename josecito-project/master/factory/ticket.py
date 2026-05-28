"""
MASTER Factory Ticket System
============================
Tickets are the operational currency of MASTER's Factory.
When internal agents need work done (new tools, fixes, infrastructure),
they file a ticket. The Factory routes and resolves tickets
without interrupting the main agent or confusing the user.

Principle: "The Factory engineer touches the controls.
The main agent protects the mission."
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional
import uuid


class TicketStatus(Enum):
    """Status of a Factory ticket."""
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"


class TicketPriority(IntEnum):
    """Priority of a Factory ticket."""
    LOW = 1            # Nice to have
    MEDIUM = 2         # Normal priority
    HIGH = 3           # Major impact
    CRITICAL = 4       # System is broken


class TicketType(Enum):
    """Type of work the ticket represents."""
    TOOL_REQUEST = "tool_request"         # New tool needed
    TOOL_FIX = "tool_fix"                 # Tool is broken
    INFRASTRUCTURE = "infrastructure"     # System-level change
    DEPENDENCY = "dependency"             # External dependency issue
    CONFIG = "config"                     # Configuration change
    MAINTENANCE = "maintenance"           # Routine maintenance
    AUDIT_REQUEST = "audit_request"       # Request for Auditor review
    SKILL_REQUEST = "skill_request"       # New skill/capability needed
    SKILL_UPGRADE = "skill_upgrade"       # Modify existing skill in sandbox
    SKILL_GENERATED = "skill_generated"   # Auto-generated skill from internal agent
    RETRIEVE_FRAGMENT = "retrieve_fragment"  # Retrieve redacted PII from vault


@dataclass
class Ticket:
    """A Factory ticket — a unit of operational work.

    The ticket is the "Bible" of the Factory. Everything that happens
    to a tool/skill is recorded here: who touched it, what was scanned,
    what was fixed, what was improved, and who approved the release.

    Checkmarks track each phase:
    ☑️ security — Caja Segura malware + injection scan passed
    ☑️ efficiency — Code is more efficient than original
    ☑️ evolution — Self-awareness has reviewed and evolved the skill
    ☑️ agent_work — Internal agent (Builder/Auditor/Reviewer) completed their step
    ☑️ released — Engineer released the tool to the system
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    ticket_type: TicketType = TicketType.MAINTENANCE
    priority: TicketPriority = TicketPriority.MEDIUM
    status: TicketStatus = TicketStatus.OPEN

    # Metadata
    created_by: str = "system"
    assigned_to: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None

    # Content
    payload: Dict[str, Any] = field(default_factory=dict)
    resolution: Optional[str] = None
    comments: List[str] = field(default_factory=list)

    # ── Checkmarks (the "Bible" traceability system) ──
    checkmarks: Dict[str, Any] = field(default_factory=lambda: {
        "security": {"passed": False, "timestamp": None, "details": ""},
        "efficiency": {"passed": False, "timestamp": None, "details": ""},
        "evolution": {"passed": False, "timestamp": None, "details": ""},
        "agent_work": {"passed": False, "timestamp": None, "agent": "", "details": ""},
        "released": {"passed": False, "timestamp": None, "details": ""},
    })

    # Revision tracking (for skill upgrades)
    revision_count: int = 0
    revisions: List[Dict[str, Any]] = field(default_factory=list)

    # Ticket number (human-readable, sequential)
    ticket_number: Optional[int] = None

    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)

    def assign(self, assignee: str) -> None:
        """Assign the ticket to an engineer."""
        self.assigned_to = assignee
        self.status = TicketStatus.ASSIGNED
        self.updated_at = datetime.now()

    def start(self) -> None:
        """Mark the ticket as in progress."""
        self.status = TicketStatus.IN_PROGRESS
        self.updated_at = datetime.now()

    def block(self, reason: str) -> None:
        """Block the ticket."""
        self.status = TicketStatus.BLOCKED
        self.comments.append(f"BLOCKED: {reason}")
        self.updated_at = datetime.now()

    def resolve(self, resolution: str) -> None:
        """Resolve the ticket."""
        self.status = TicketStatus.RESOLVED
        self.resolution = resolution
        self.resolved_at = datetime.now()
        self.updated_at = datetime.now()

    def close(self) -> None:
        """Close the ticket (final state)."""
        self.status = TicketStatus.CLOSED
        self.updated_at = datetime.now()

    def reject(self, reason: str) -> None:
        """Reject the ticket."""
        self.status = TicketStatus.REJECTED
        self.comments.append(f"REJECTED: {reason}")
        self.updated_at = datetime.now()

    def comment(self, message: str) -> None:
        """Add a comment to the ticket."""
        self.comments.append(message)
        self.updated_at = datetime.now()

    def record_revision(self, changed_by: str, changes: Dict[str, Any]) -> int:
        """Record a revision to the ticket (for skill modifications)."""
        self.revision_count += 1
        self.revisions.append({
            "revision": self.revision_count,
            "changed_by": changed_by,
            "changes": changes,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()
        return self.revision_count

    # ── Checkmarks (the "Bible" traceability) ────────────────────────

    def checkmark_security(self, passed: bool, details: str = "") -> None:
        """☑️ Mark the security scan (Caja Segura) as complete."""
        self.checkmarks["security"] = {
            "passed": passed,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.updated_at = datetime.now()
        if not passed:
            self.comments.append(f"SECURITY: FAILED — {details}")

    def checkmark_efficiency(self, passed: bool, details: str = "") -> None:
        """☑️ Mark the efficiency check as complete."""
        self.checkmarks["efficiency"] = {
            "passed": passed,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.updated_at = datetime.now()

    def checkmark_evolution(self, passed: bool, details: str = "") -> None:
        """☑️ Mark the self-awareness evolution check as complete."""
        self.checkmarks["evolution"] = {
            "passed": passed,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.updated_at = datetime.now()

    def checkmark_agent_work(self, passed: bool, agent: str, details: str = "") -> None:
        """☑️ Mark an internal agent's work as complete."""
        self.checkmarks["agent_work"] = {
            "passed": passed,
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "details": details,
        }
        self.updated_at = datetime.now()

    def checkmark_released(self, passed: bool, details: str = "") -> None:
        """☑️ Mark the tool/skill as released by the Engineer."""
        self.checkmarks["released"] = {
            "passed": passed,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.updated_at = datetime.now()

    def all_checkmarks_passed(self) -> bool:
        """Have all required checkmarks passed?"""
        required = ["security", "efficiency", "evolution", "agent_work", "released"]
        return all(self.checkmarks.get(c, {}).get("passed", False) for c in required)

    def get_checkmark_summary(self) -> str:
        """Get a visual checkmark summary."""
        icons = []
        for name in ["security", "efficiency", "evolution", "agent_work", "released"]:
            cm = self.checkmarks.get(name, {})
            icon = "✅" if cm.get("passed") else "⏳"
            icons.append(f"{icon} {name}")
        return " | ".join(icons)

    def summary(self) -> str:
        """One-line summary of the ticket with checkmarks."""
        num = f"#{self.ticket_number} " if self.ticket_number else ""
        revs = f" (v{self.revision_count})" if self.revision_count > 0 else ""
        checks = self.get_checkmark_summary()
        return (
            f"🎫 {num}[{self.id[:8]}] [{self.priority.name}] "
            f"{self.ticket_type.value}: {self.title[:50]} "
            f"({self.status.value}){revs}\n"
            f"      {checks}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "ticket_type": self.ticket_type.value,
            "priority": self.priority.name.lower(),
            "status": self.status.value,
            "created_by": self.created_by,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

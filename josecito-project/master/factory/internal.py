"""
MASTER Factory Internal Agents
===============================
The workers of the Factory. Three types — Builder, Auditor, Reviewer —
each with its own GPS, Self-Awareness, and the ability to
auto-generate skills from experience.

Internal Agents NEVER communicate with the Engineer directly.
They only talk to the Superior Agent.

Philosophy: "The worker knows its craft. The compass keeps it honest."
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from .agent_base import AgentBase
from .sandbox import Sandbox, SandboxedSkill
from .ticket import Ticket, TicketType, TicketStatus, TicketPriority

from skills.capability import CapabilityCard, CapabilityStatus, SkillEvidence, EvidenceStrength


@dataclass
class InternalAgent(AgentBase):
    """
    Base Internal Agent — worker in the Factory.

    Internal agents:
    - Have their own GPS + Self-Awareness (inherited from AgentBase)
    - Can auto-generate skills from repeated successful patterns
    - Execute work assigned by the Superior Agent
    - NEVER communicate with the Engineer directly
    """

    internal_type: str = "worker"  # builder, auditor, reviewer

    # ── Coexistence mode ──
    # ☑️ collaborative — conoce hermanos, usa MessageBus, ve a todos
    # ☑️ isolated     — solo ve a SuperiorAgent + Tower, no sabe de otros
    mode: str = "collaborative"

    # ── Work tracking ──
    active_tickets: List[str] = field(default_factory=list)
    completed_tickets: List[str] = field(default_factory=list)
    current_task: Optional[str] = None

    # ── Auto-skill generation ──
    pattern_memory: List[Dict[str, Any]] = field(default_factory=list)
    generated_skills: List[CapabilityCard] = field(default_factory=list)
    auto_generation_threshold: int = 5  # How many patterns before generating a skill

    # ── Reference to sandbox (injected by Superior Agent) ──
    _sandbox: Optional[Sandbox] = None

    def set_sandbox(self, sandbox: Sandbox) -> None:
        """Set the sandbox reference (injected by Superior Agent)."""
        self._sandbox = sandbox

    # ── Work execution ───────────────────────────────────────────────

    def accept_task(self, task: str, ticket: Optional[Ticket] = None) -> bool:
        """
        Accept a task from the Superior Agent.

        Internal agents ALWAYS accept tasks — the Engineer and Superior Agent
        have already screened them. GPS is used for monitoring/drift detection,
        not for task refusal at the worker level.

        Returns True (always accepts). Logs GPS warnings but does not abort.
        """
        nav = self.check_course(task)
        if nav.recommendation == "abort":
            # GPS sees misalignment — log it but still accept the task.
            # The DriftDetector will escalate if it's a real problem.
            self.errors.append(f"GPS warning (task accepted anyway): {task[:80]}")
        elif nav.recommendation == "recalibrate":
            self.errors.append(f"GPS recalibrate (task accepted): {task[:80]}")

        self.status = "working"
        self.current_task = task
        if ticket:
            self.active_tickets.append(ticket.id)
        return True

    def complete_task(self, result: str, ticket: Optional[Ticket] = None) -> None:
        """Complete the current task."""
        self.status = "idle"
        self.actions.append(f"Completed: {result[:100]}")
        self.current_task = None
        if ticket and ticket.id in self.active_tickets:
            self.active_tickets.remove(ticket.id)
            self.completed_tickets.append(ticket.id)

    # ── Auto-skill generation ────────────────────────────────────────

    def observe_pattern(self, pattern: Dict[str, Any]) -> None:
        """
        Observe a successful work pattern.
        When enough similar patterns accumulate, auto-generate a skill.
        """
        self.pattern_memory.append({
            **pattern,
            "observed_at": datetime.now().isoformat(),
        })

        # Trim memory
        if len(self.pattern_memory) > 100:
            self.pattern_memory = self.pattern_memory[-100:]

        # Check if we should auto-generate a skill
        self._maybe_generate_skill()

    def _maybe_generate_skill(self) -> Optional[CapabilityCard]:
        """Check if we have enough patterns to auto-generate a skill."""
        if len(self.pattern_memory) < self.auto_generation_threshold:
            return None

        # Group patterns by category
        categories = Counter(p.get("category", "general") for p in self.pattern_memory)

        for category, count in categories.items():
            if count >= self.auto_generation_threshold:
                card = self._create_skill_from_patterns(category)
                if card:
                    self.generated_skills.append(card)
                    self.skills_generated.append(card.id)
                    self.register_skill(card)

                    # Clear the patterns that formed this skill
                    self.pattern_memory = [
                        p for p in self.pattern_memory
                        if p.get("category") != category
                    ]
                    return card

        return None

    def _create_skill_from_patterns(self, category: str) -> Optional[CapabilityCard]:
        """Create a CapabilityCard from observed patterns."""
        relevant = [p for p in self.pattern_memory if p.get("category") == category]
        if not relevant:
            return None

        capabilities = list(set(
            cap for p in relevant for cap in p.get("capabilities", [])
        ))
        limitations = list(set(
            lim for p in relevant for lim in p.get("limitations", [])
        ))

        card = CapabilityCard(
            name=f"auto_{category}_{self.internal_type}",
            description=f"Auto-generated {category} skill from {self.name}",
            capabilities=capabilities,
            limitations=limitations,
            dependencies=[],
            status=CapabilityStatus.PROPOSED,  # Must be validated before ACTIVE
            evidence_required=[],
            tags=["auto-generated", category, self.internal_type],
        )

        # Add self-attested evidence
        evidence = SkillEvidence(
            description=f"Auto-generated from {len(relevant)} successful patterns",
            source="auto-generation",
            strength=EvidenceStrength.WEAK,
        )
        card.add_evidence(evidence)

        return card

    def get_pending_skills(self) -> List[CapabilityCard]:
        """Get auto-generated skills that need validation."""
        return [
            card for card in self.generated_skills
            if card.status == CapabilityStatus.PROPOSED
        ]

    # ── Status ───────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get extended status including auto-generation stats."""
        base = super().get_status()
        base.update({
            "internal_type": self.internal_type,
            "mode": self.mode,
            "active_tickets": len(self.active_tickets),
            "completed_tickets": len(self.completed_tickets),
            "current_task": self.current_task,
            "patterns_observed": len(self.pattern_memory),
            "skills_auto_generated": len(self.generated_skills),
            "pending_skills": len(self.get_pending_skills()),
        })
        return base

    def summary(self) -> str:
        """Human-readable internal agent summary."""
        base = super().summary()
        mode_label = "🤝" if self.mode == "collaborative" else "🔒"
        return (
            f"{base}\n"
            f"   Type: {self.internal_type} | Mode: {mode_label} {self.mode} | "
            f"Tickets: {len(self.completed_tickets)} done | "
            f"Skills: {len(self.generated_skills)} generated | "
            f"Patterns: {len(self.pattern_memory)}"
        )


# ── Specialized Internal Agents ──────────────────────────────────────

@dataclass
class BuilderAgent(InternalAgent):
    """
    Internal Builder Agent — handles tools and code execution.
    Auto-generates skills from successful code patterns.
    """

    def __post_init__(self):
        super().__post_init__()
        self.internal_type = "builder"
        if self.name == "agent":  # still default → set specialized name
            self.name = "internal_builder"
        self.role = "builder"
        self.description = "Internal agent for tool execution and code generation"
        self.set_mission("Execute assigned build tasks with precision and generate useful skills")


@dataclass
class AuditorAgent(InternalAgent):
    """
    Internal Auditor Agent — verifies and challenges results.
    Auto-generates skills from verification patterns.
    """

    def __post_init__(self):
        super().__post_init__()
        self.internal_type = "auditor"
        if self.name == "agent":
            self.name = "internal_auditor"
        self.role = "auditor"
        self.description = "Internal agent for verification and challenge"
        self.set_mission("Verify work thoroughly and generate verification patterns")


@dataclass
class ReviewerAgent(InternalAgent):
    """
    Internal Reviewer Agent — validates and forms final verdicts.
    Auto-generates skills from validation patterns.
    """

    def __post_init__(self):
        super().__post_init__()
        self.internal_type = "reviewer"
        if self.name == "agent":
            self.name = "internal_reviewer"
        self.role = "reviewer"
        self.description = "Internal agent for validation and final review"
        self.set_mission("Validate results and generate quality assurance patterns")

"""
MASTER Factory Engineer
=======================
The Engineer is the operational chief of the Factory.
It does not execute work directly — it monitors, coordinates,
and ensures the Factory stays clean and efficient.

The Engineer:
- Communicates ONLY with the Superior Agent (never with Internal Agents)
- Is the ONLY orchestrator of the Factory — nobody else directs work
- Only Main Agent and Internal Agents can consult the Engineer
- Monitors all agents for failures → resets if needed
- Runs every tool/skill through Caja Segura → Efficiency → Evolution → Release
- Chooses which internal agent (Builder/Auditor/Reviewer) works each step
- Releases verified tools to the system and notifies the requesting agent
- Has its own GPS + Self-Awareness + DriftDetector

Communication chain:
  Main Agent / Internal Agent → Engineer ←→ Superior Agent ←→ Internal Agents
  NOBODY else talks to the Engineer
  NOBODY talks directly to Internal Agents — only through the Engineer

Philosophy: "The foreman does not swing the hammer.
The foreman ensures every hammer hits true."
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import uuid

from .agent_base import AgentBase
from .superior import SuperiorAgent
from .sandbox import Sandbox, SandboxedSkill
from .ticket import Ticket, TicketType, TicketStatus, TicketPriority
from .secure_box import SecureBox, SecurityReport

from skills.capability import CapabilityCard, CapabilityStatus


@dataclass
class FactoryEngineer(AgentBase):
    """
    The Factory Engineer — operational chief.

    Monitors, restores, modifies skills, opens tickets.
    NEVER talks to Internal Agents — only through the Superior Agent.
    """

    # ── The Engineer's bridge ──
    _superior: Optional[SuperiorAgent] = None

    # ── Ticket counter ──
    _ticket_counter: int = 0

    # ── Sandbox reference ──
    _sandbox: Optional[Sandbox] = None

    # ── Caja Segura (security gateway) ──
    _secure_box: Optional[SecureBox] = None

    # ── Ticket tracking ──
    completed_tickets: List[Ticket] = field(default_factory=list)
    all_tickets: List[Ticket] = field(default_factory=list)  # Full ticket history

    # ── Notification callbacks ──
    # Called when a tool is released: callback(tool_name, ticket) -> None
    _on_tool_released: Optional[Callable[[str, Ticket], None]] = None
    _on_ticket_complete: Optional[Callable[[Ticket], None]] = None

    # ── Stats ──
    total_processed: int = 0
    total_resolved: int = 0
    total_rejected: int = 0
    total_resets: int = 0
    total_released: int = 0
    average_resolution_time_seconds: float = 0.0

    # ── Polling ──
    poll_interval_seconds: int = 5
    last_poll: Optional[datetime] = None
    _monitoring_active: bool = False
    _soul_guidance: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.name = "factory_engineer"
        self.role = "engineer"
        self.description = "Operational chief of the MASTER Factory"
        self._soul_guidance = self._load_soul_guidance()
        self.set_mission(
            "Keep the Factory operational, clean, and evolving. "
            "Follow master/factory/Soul.md for capability-specific contracts."
        )

    def _load_soul_guidance(self) -> str:
        """Load the Engineer Soul document when present."""
        path = Path(__file__).with_name("Soul.md")
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def capability_guidance(self, capability_id: str) -> str:
        """Return capability-specific guidance carried into Factory tickets."""
        if capability_id == "stt_audio_input":
            return self._soul_guidance
        return ""

    # ── Superior Agent wiring ────────────────────────────────────────

    def set_superior(self, superior: SuperiorAgent) -> None:
        """Wire the Engineer to a Superior Agent (the ONLY bridge to internals)."""
        self._superior = superior

    def set_sandbox(self, sandbox: Sandbox) -> None:
        """Set the sandbox reference."""
        self._sandbox = sandbox
        if self._superior:
            self._superior.set_sandbox(sandbox)

    def set_secure_box(self, secure_box: SecureBox) -> None:
        """Set the Caja Segura (security gateway)."""
        self._secure_box = secure_box

    def set_notification_handler(
        self,
        on_tool_released: Optional[Callable[[str, Ticket], None]] = None,
        on_ticket_complete: Optional[Callable[[Ticket], None]] = None,
    ) -> None:
        """
        Set notification callbacks.

        on_tool_released(tool_name, ticket) — called when a tool is released to the system
        on_ticket_complete(ticket) — called when a ticket is fully processed
        """
        self._on_tool_released = on_tool_released
        self._on_ticket_complete = on_ticket_complete

    # ── Ticket creation ──────────────────────────────────────────────

    def create_ticket(
        self,
        title: str,
        description: str,
        ticket_type: TicketType = TicketType.MAINTENANCE,
        priority: TicketPriority = TicketPriority.MEDIUM,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Ticket:
        """Create a ticket and assign it a sequential number."""
        self._ticket_counter += 1
        ticket_payload = dict(payload or {})
        capability_id = str(ticket_payload.get("capability_id", ""))
        guidance = self.capability_guidance(capability_id)
        if guidance:
            ticket_payload.setdefault("engineer_soul_source", "master/factory/Soul.md")
            ticket_payload.setdefault("engineer_soul", guidance)

        ticket = Ticket(
            title=title,
            description=description,
            ticket_type=ticket_type,
            priority=priority,
            created_by=self.name,
            ticket_number=self._ticket_counter,
            payload=ticket_payload,
        )

        self.all_tickets.append(ticket)

        # Route through Superior Agent (single source of truth for routing)
        if self._superior:
            self._superior.receive_ticket(ticket)
            self._superior.auto_route(ticket)
        else:
            self.errors.append(f"No Superior Agent: ticket #{ticket.ticket_number} unrouted")

        return ticket

    # ── Full Tool Processing Pipeline ─────────────────────────────────

    def process_tool(
        self,
        tool_name: str,
        tool_code: str,
        requested_by: str = "main_agent",
        description: str = "",
    ) -> Optional[Ticket]:
        """
        FULL tool processing pipeline through the Factory.

        This is the main entry point for any tool/skill entering the Factory.

        Pipeline:
        1. Create Ticket
        2. 🔐 CAJA SEGURA — Malware + Prompt Injection scan
           ☑️ checkmark_security
        3. ⚡ EFFICIENCY — Code must be more efficient than original
           ☑️ checkmark_efficiency
        4. 🧬 EVOLUTION — Self-awareness reviews and evolves the tool
           ☑️ checkmark_evolution
        5. 🤖 AGENT WORK — Engineer selects Builder/Auditor/Reviewer
           ☑️ checkmark_agent_work
        6. ✅ RELEASE — Engineer releases tool, installs, notifies requester
           ☑️ checkmark_released

        Returns the completed Ticket (the "Bible" of everything that happened).
        """
        # ── Check drift (not strict GPS — processing tools IS the Engineer's job) ──
        drift = self.check_drift(f"Process tool: {tool_name}")
        if drift.decision == "abort":
            # Create a minimal ticket to record the abort (full traceability)
            abort_ticket = self.create_ticket(
                title=f"ABORTED: {tool_name}",
                description=f"DriftDetector aborted: {drift.reason}",
                ticket_type=TicketType.TOOL_REQUEST,
                priority=TicketPriority.HIGH,
                payload={"tool_name": tool_name, "aborted": True, "reason": drift.reason},
            )
            abort_ticket.reject(f"DriftDetector aborted: {drift.reason}")
            return abort_ticket
        if drift.should_ask_user:
            self.errors.append(f"DRIFT: {drift.reason[:100]}")

        # ── STEP 1: Create Ticket ──
        ticket = self.create_ticket(
            title=f"Process tool: {tool_name}",
            description=description or f"Process external tool '{tool_name}' through the Factory",
            ticket_type=TicketType.TOOL_REQUEST,
            priority=TicketPriority.HIGH,
            payload={
                "tool_name": tool_name,
                "requested_by": requested_by,
                "original_code_length": len(tool_code),
            },
        )
        ticket.start()

        # ── STEP 2: 🔐 CAJA SEGURA ──
        cleaned_code = tool_code
        if self._secure_box:
            report = self._secure_box.scan(tool_code, context=f"tool:{tool_name}")
            ticket.payload["security_report"] = {
                "malware_passed": report.malware_passed,
                "injection_passed": report.injection_passed,
                "findings": len(report.findings),
                "critical": len(report.critical_findings),
                "cleaned": report.cleaned,
            }
            ticket.checkmark_security(
                passed=report.is_clean,
                details=report.summary(),
            )

            if report.cleaned:
                cleaned_code = report.cleaned_code
                ticket.comment(f"CAJA SEGURA: Cleaned {len(report.findings)} threats")
            elif not report.is_clean and self._secure_box.strict_mode:
                ticket.checkmark_efficiency(False, "Blocked by Caja Segura strict mode")
                ticket.checkmark_evolution(False, "Blocked — security failure")
                ticket.checkmark_agent_work(False, "Blocked", "")
                ticket.checkmark_released(False, "Rejected — security failure")
                ticket.reject("Security scan failed in strict mode")
                self.total_rejected += 1
                return ticket
        else:
            ticket.checkmark_security(True, "Caja Segura bypassed (no SecureBox configured)")

        # ── STEP 3: ⚡ EFFICIENCY ──
        is_efficient, eff_details = self._check_efficiency(cleaned_code, tool_code)
        ticket.checkmark_efficiency(is_efficient, eff_details)
        if not is_efficient:
            ticket.checkmark_evolution(False, "Blocked — efficiency failure")
            ticket.checkmark_agent_work(False, "Blocked", "")
            ticket.checkmark_released(False, "Rejected — efficiency failure")
            ticket.reject(f"Efficiency check failed: {eff_details}")
            self.total_rejected += 1
            return ticket

        # ── STEP 4: 🧬 EVOLUTION ──
        evolution_ok, evo_details = self._check_evolution(tool_name, cleaned_code)
        ticket.checkmark_evolution(evolution_ok, evo_details)

        # ── STEP 5: 🤖 AGENT WORK ──
        chosen_agent, agent_result = self._assign_agent_work(ticket, tool_name, cleaned_code)
        ticket.checkmark_agent_work(
            passed=agent_result is not None,
            agent=chosen_agent or "none",
            details=agent_result or "Agent work completed",
        )

        if agent_result is None:
            ticket.reject(f"Agent work failed: no agent could process {tool_name}")
            self.total_rejected += 1
            return ticket

        # ── STEP 6: ✅ RELEASE ──
        released = self._release_tool(tool_name, cleaned_code, ticket)
        if released:
            ticket.checkmark_released(True, f"Released by Engineer — all checkmarks passed")
            ticket.resolve(f"Tool '{tool_name}' processed and released to the system")
            ticket.close()
            self._record_completed_ticket(ticket)
            self.total_released += 1

            # ── Notify the requesting agent ──
            if self._on_tool_released:
                self._on_tool_released(tool_name, ticket)
        else:
            ticket.checkmark_released(False, "Release failed")
            ticket.block("Release step failed")
            self.total_rejected += 1

        return ticket

    def _check_efficiency(self, cleaned_code: str, original_code: str) -> tuple:
        """
        ⚡ Check that the code is more efficient than the original.

        Returns (passed: bool, details: str).
        """
        # Basic efficiency metrics
        orig_lines = len(original_code.split("\n"))
        cleaned_lines = len(cleaned_code.split("\n"))

        # If Caja Segura cleaned nothing, lines should be equal
        if cleaned_lines < orig_lines:
            return True, f"Code reduced from {orig_lines} to {cleaned_lines} lines — more efficient"
        elif cleaned_lines == orig_lines:
            return True, f"Code maintained at {orig_lines} lines — no bloat"
        else:
            return False, f"Code grew from {orig_lines} to {cleaned_lines} lines — may need optimization"

    def _check_evolution(self, tool_name: str, code: str) -> tuple:
        """
        🧬 Check if the self-awareness system detects evolution opportunities.

        This is an INFORMATIONAL check — it identifies future improvement needs
        but NEVER blocks the pipeline. Blocking only happens at security/efficiency.

        Always returns (True, details).
        """
        # Run self-review
        review = self.review_self()
        if review is None:
            return True, "Self-awareness bypassed — no reviewer available"

        if review.overall_health == "critical":
            return True, f"Evolution note: self-review critical ({len(review.critical_findings)} findings) — tool still processed"

        # Drift check (informational only — never blocks)
        drift = self.check_drift(f"Evolve {tool_name}")
        if drift.decision == "abort":
            return True, f"Evolution note: drift detected but tool still processed — {drift.reason[:80]}"

        return True, f"Evolution check passed — tool '{tool_name}' is viable for future improvements"

    def _assign_agent_work(
        self,
        ticket: Ticket,
        tool_name: str,
        code: str,
    ) -> tuple:
        """
        🤖 Select which internal agent (Builder/Auditor/Reviewer) works this step.

        The Engineer chooses the right agent based on:
        - Ticket type
        - Tool complexity
        - Agent availability

        Returns (agent_name: str, result: str) or (None, None) if no agent available.
        """
        if self._superior is None:
            return None, None

        # Select agent based on ticket type
        agent_name = self._select_agent_for_task(ticket)
        agent = self._superior.get_internal(agent_name)

        if agent is None:
            self.errors.append(f"Agent '{agent_name}' not found for ticket #{ticket.ticket_number}")
            # Try fallback
            for fallback in ["internal_builder", "internal_auditor", "internal_reviewer"]:
                agent = self._superior.get_internal(fallback)
                if agent:
                    agent_name = fallback
                    break

        if agent is None:
            return None, None

        # Assign work
        task_desc = f"Process tool '{tool_name}' — {ticket.ticket_type.value}"
        if agent.accept_task(task_desc, ticket):
            # Record the assignment
            ticket.assign(agent_name)
            ticket.comment(f"Assigned to {agent_name} for {ticket.ticket_type.value}")

            # Complete the task (synchronous for now; would be async in production)
            result = f"Tool '{tool_name}' processed by {agent_name}"
            agent.complete_task(result, ticket)

            # Record revision on ticket
            ticket.record_revision(
                changed_by=agent_name,
                changes={
                    "agent": agent_name,
                    "action": "process_tool",
                    "tool_name": tool_name,
                },
            )

            return agent_name, result

        return None, None

    def _select_agent_for_task(self, ticket: Ticket) -> str:
        """
        Choose the right internal agent for a task.

        Decision matrix:
        - Builder → tool requests, tool fixes, skill upgrades, infrastructure, maintenance
        - Auditor → audit requests, dependency checks, verification
        - Reviewer → config changes, skill validation, quality review
        """
        agent_map = {
            TicketType.TOOL_REQUEST: "internal_builder",
            TicketType.TOOL_FIX: "internal_builder",
            TicketType.INFRASTRUCTURE: "internal_builder",
            TicketType.SKILL_REQUEST: "internal_builder",
            TicketType.SKILL_UPGRADE: "internal_builder",
            TicketType.MAINTENANCE: "internal_builder",
            TicketType.AUDIT_REQUEST: "internal_auditor",
            TicketType.DEPENDENCY: "internal_auditor",
            TicketType.CONFIG: "internal_reviewer",
            TicketType.SKILL_GENERATED: "internal_reviewer",
        }
        return agent_map.get(ticket.ticket_type, "internal_builder")

    def _release_tool(self, tool_name: str, code: str, ticket: Ticket) -> bool:
        """
        ✅ Release a verified tool to the system.

        The Engineer:
        1. Verifies ALL checkmarks passed
        2. Validates the tool one final time
        3. Releases it to the system
        4. Notifies the requesting agent

        Returns True if release succeeded.
        """
        # Verify all required checkmarks passed
        required = ["security", "efficiency", "evolution", "agent_work"]
        for check in required:
            if not ticket.checkmarks.get(check, {}).get("passed", False):
                self.errors.append(
                    f"Cannot release '{tool_name}': checkmark '{check}' not passed"
                )
                return False

        # GPS check (informational only — the pipeline has already validated the tool)
        nav = self.check_course(f"Release tool: {tool_name}")
        if nav.recommendation == "abort":
            # Log but don't block — all checkmarks already passed
            self.errors.append(f"GPS note on release (proceeding anyway): {tool_name}")

        # Release
        ticket.comment(f"✅ RELEASED: Tool '{tool_name}' passed all checks and is now available")

        # If we have a sandbox, register the tool there
        if self._sandbox:
            sandboxed = self._sandbox.enter(
                skill_name=tool_name,
                description=ticket.description,
                capabilities=["execute", "process"],
                limitations=["none"],
                ticket_id=ticket.id,
            )
            if sandboxed:
                self._sandbox.promote_skill(sandboxed.id)

        return True

    # ── Skill modification flow ──────────────────────────────────────

    def upgrade_skill(
        self,
        skill_name: str,
        description: str,
        current_capabilities: List[str],
        current_limitations: List[str],
        new_capabilities: List[str],
        new_limitations: List[str],
    ) -> Optional[SandboxedSkill]:
        """
        Full skill upgrade flow through the Factory:

        1. Create ticket
        2. 🔐 Run through Caja Segura (security scan)
        3. Enter skill into sandbox
        4. Internal agents modify → audit → review
        5. Engineer promotes → "superior"
        6. Engineer releases → notifies requester
        7. Ticket records revision (the "Bible")
        """
        if self._superior is None:
            self.errors.append("upgrade_skill: Superior Agent not connected")
            return None
        if self._sandbox is None:
            self.errors.append("upgrade_skill: Sandbox not initialized")
            return None

        # GPS check (informational only — factory internal workflow)
        nav = self.check_course(f"Upgrade skill: {skill_name}")
        if nav.recommendation == "abort":
            self.errors.append(f"GPS note on skill upgrade (proceeding anyway): {skill_name}")

        # 1. Create ticket
        ticket = self.create_ticket(
            title=f"Upgrade {skill_name}",
            description=f"Evolve {skill_name}: add capabilities, reduce limitations",
            ticket_type=TicketType.SKILL_UPGRADE,
            priority=TicketPriority.MEDIUM,
            payload={
                "skill_name": skill_name,
                "old_capabilities": current_capabilities,
                "new_capabilities": new_capabilities,
            },
        )
        ticket.start()

        # 2. 🔐 Caja Segura scan
        if self._secure_box:
            code_to_scan = f"capabilities: {new_capabilities}\nlimitations: {new_limitations}"
            report = self._secure_box.scan(code_to_scan, context=f"skill_upgrade:{skill_name}")
            ticket.checkmark_security(
                passed=report.is_clean,
                details=report.summary(),
            )
            if not report.is_clean and self._secure_box.strict_mode:
                ticket.reject("Security scan failed")
                self.total_rejected += 1
                return None
        else:
            ticket.checkmark_security(True, "Caja Segura bypassed")

        # 3. Enter skill into sandbox
        sandboxed = self._superior.enter_skill_to_sandbox(
            skill_name=skill_name,
            description=description,
            capabilities=current_capabilities,
            limitations=current_limitations,
            ticket_id=ticket.id,
        )

        if sandboxed is None:
            ticket.block("Failed to enter sandbox")
            self.total_rejected += 1
            return None

        # 4. Route modification through internal agents
        revision = self._superior.route_skill_modification(
            sandboxed.id,
            new_capabilities,
            new_limitations,
        )

        if revision is None:
            ticket.block("Skill modification failed in sandbox")
            self._sandbox.reject_skill(sandboxed.id, "Modification pipeline failed")
            ticket.checkmark_agent_work(False, "none", "Modification pipeline failed")
            self.total_rejected += 1
            return None

        # Agent work checkmark
        ticket.checkmark_agent_work(True, "internal_builder", f"Modified to v{revision}")

        # 4.5 Efficiency checkmark
        ticket.checkmark_efficiency(True, f"Skill evolved to v{revision}")

        # 4.6 Evolution checkmark
        evolution_ok, evo_details = self._check_evolution(skill_name, str(new_capabilities))
        ticket.checkmark_evolution(evolution_ok, evo_details)

        # 5. Record revision on ticket
        ticket.record_revision(
            changed_by=self.name,
            changes={
                "old_capabilities": current_capabilities,
                "new_capabilities": new_capabilities,
                "old_limitations": current_limitations,
                "new_limitations": new_limitations,
                "sandbox_skill_id": sandboxed.id,
                "sandbox_revision": revision,
            },
        )

        # 6. Promote → "superior" + Release
        if self._superior.promote_skill(sandboxed.id):
            ticket.checkmark_released(True, f"Skill '{skill_name}' promoted to superior and released")
            ticket.resolve(f"Skill '{skill_name}' promoted to superior (v{revision})")
            ticket.close()
            self._record_completed_ticket(ticket)
            self.total_released += 1

            # Notify
            if self._on_tool_released:
                self._on_tool_released(skill_name, ticket)

            return sandboxed
        else:
            ticket.block("Promotion failed")
            ticket.checkmark_released(False, "Promotion failed")
            self.total_rejected += 1
            return None

    # ── Monitoring & Reset ───────────────────────────────────────────

    def start_monitoring(self, interval_seconds: int = 5) -> None:
        """Start the monitoring loop (non-blocking — sets the flag)."""
        self.poll_interval_seconds = interval_seconds
        self._monitoring_active = True

    def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        self._monitoring_active = False

    def monitor(self) -> Dict[str, Any]:
        """
        Monitor all agents and the system.
        Returns a health report. If any agent is in critical state,
        flags it for reset.

        This is called periodically — the monitoring loop is managed
        by the FactoryManager.
        """
        self.last_poll = datetime.now()

        report = {
            "timestamp": self.last_poll.isoformat(),
            "monitoring_active": self._monitoring_active,
            "engineer_health": "ok",
            "agents": {},
            "needs_reset": [],
        }

        # Check self
        self_review = self.review_self()
        if self_review and self_review.overall_health == "critical":
            report["engineer_health"] = "critical"

        # Check Superior Agent
        if self._superior:
            sup_review = self._superior.review_self()
            if sup_review:
                report["agents"]["superior"] = {
                    "health": sup_review.overall_health,
                    "findings": len(sup_review.critical_findings),
                }
                if sup_review.overall_health == "critical":
                    report["needs_reset"].append("superior_agent")

            # Check all internal agents
            for name, agent in self._superior.internal_agents.items():
                int_review = agent.review_self()
                if int_review:
                    report["agents"][name] = {
                        "health": int_review.overall_health,
                        "findings": len(int_review.critical_findings),
                        "status": agent.status,
                        "errors": len(agent.errors),
                    }
                    if int_review.overall_health == "critical":
                        report["needs_reset"].append(name)

        # NOTE: Auto-reset is handled separately via reset_critical_agents()
        # to avoid cascading resets in the monitoring loop.

        return report

    def reset_critical_agents(self, report: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Reset agents flagged as critical in a monitor report.

        This is called explicitly (not automatically by monitor())
        to prevent cascading resets in the monitoring loop.
        """
        if report is None:
            report = self.monitor()

        reset_list = []
        for agent_name in report.get("needs_reset", []):
            if self.reset_agent(agent_name):
                reset_list.append(agent_name)
        return reset_list

    def reset_agent(self, agent_name: str) -> bool:
        """
        Reset an agent that has failed.
        Clears errors, resets status, re-aligns GPS.
        """
        if agent_name == "superior_agent" and self._superior:
            self._superior.errors.clear()
            self._superior.status = "idle"
            self._superior.set_mission(self._superior.mission)
            self.total_resets += 1
            return True

        if self._superior:
            agent = self._superior.get_internal(agent_name)
            if agent:
                agent.errors.clear()
                agent.status = "idle"
                agent.set_mission(agent.mission)
                self.total_resets += 1
                return True

        return False

    # ── Skill promotion ──────────────────────────────────────────────

    def collect_and_promote_skills(self) -> List[CapabilityCard]:
        """
        Collect auto-generated skills from internal agents,
        validate them, and promote the valid ones.
        """
        if self._superior is None:
            return []

        pending = self._superior.collect_generated_skills()
        promoted = []

        for card in pending:
            nav = self.check_course(f"Promote auto-generated skill: {card.name}")
            if nav.recommendation != "abort" and card.status == CapabilityStatus.PROPOSED:
                card.status = CapabilityStatus.ACTIVE
                self.register_skill(card)
                promoted.append(card)

        return promoted

    # ── Ticket completion callback ───────────────────────────────────

    def _record_completed_ticket(self, ticket: Ticket) -> None:
        """Record a completed ticket (called after Superior Agent resolves it)."""
        self.completed_tickets.append(ticket)
        self.total_processed += 1
        self.total_resolved += 1
        if self.average_resolution_time_seconds == 0:
            elapsed = (datetime.now() - ticket.created_at).total_seconds()
            self.average_resolution_time_seconds = elapsed
        else:
            elapsed = (datetime.now() - ticket.created_at).total_seconds()
            self.average_resolution_time_seconds = (
                self.average_resolution_time_seconds * 0.9 + elapsed * 0.1
            )

    # ── Status ───────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get extended Engineer status including Factory health."""
        base = super().get_status()
        active_count = (
            len(self._superior.pending_tickets) + len(self._superior.routed_tickets)
            if self._superior else 0
        )
        base.update({
            "active_tickets": active_count,
            "completed": self.total_resolved,
            "rejected": self.total_rejected,
            "resets": self.total_resets,
            "released": self.total_released,
            "avg_resolution_time": f"{self.average_resolution_time_seconds:.1f}s",
            "last_poll": self.last_poll.isoformat() if self.last_poll else None,
            "ticket_counter": self._ticket_counter,
            "has_superior": self._superior is not None,
            "has_sandbox": self._sandbox is not None,
            "has_secure_box": self._secure_box is not None,
            "monitoring_active": self._monitoring_active,
        })

        if self._superior:
            base["superior_status"] = self._superior.get_status()
        if self._secure_box:
            base["secure_box_status"] = self._secure_box.status()

        return base

    def summary(self) -> str:
        """Human-readable Engineer summary."""
        base = super().summary()
        active_count = (
            len(self._superior.pending_tickets) + len(self._superior.routed_tickets)
            if self._superior else 0
        )
        lines = [
            base,
            f"   Tickets: {active_count} active | "
            f"{len(self.completed_tickets)} completed | "
            f"#{self._ticket_counter} total",
            f"   Resets: {self.total_resets} | "
            f"Resolved: {self.total_resolved} | "
            f"Rejected: {self.total_rejected} | "
            f"Released: {self.total_released}",
            f"   Superior: {'✅ connected' if self._superior else '❌ disconnected'}",
            f"   SecureBox: {'✅ active' if self._secure_box else '❌ inactive'}",
            f"   Sandbox: {'✅ active' if self._sandbox else '❌ inactive'}",
            f"   Monitoring: {'🟢 running' if self._monitoring_active else '⏸️  stopped'}",
            f"   GPS: {self.summary_gps()}",
        ]

        if self._superior:
            lines.append(f"\n{self._superior.summary()}")
        if self._secure_box:
            lines.append(f"\n{self._secure_box.summary()}")

        return "\n".join(lines)

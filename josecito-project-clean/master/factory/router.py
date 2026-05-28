"""
MASTER Factory Ticket Router
============================
Routes tickets to the appropriate engineer or subsystem
based on ticket type, priority, and current system load.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .ticket import Ticket, TicketStatus, TicketType, TicketPriority


@dataclass
class RoutingRule:
    """A rule for routing tickets."""
    ticket_type: TicketType
    route_to: str  # engineer name or subsystem
    priority_threshold: TicketPriority = TicketPriority.CRITICAL


@dataclass
class TicketRouter:
    """Routes incoming tickets to the right destination."""

    rules: List[RoutingRule] = field(default_factory=lambda: [
        RoutingRule(TicketType.TOOL_REQUEST, "internal_builder"),
        RoutingRule(TicketType.TOOL_FIX, "internal_builder"),
        RoutingRule(TicketType.INFRASTRUCTURE, "internal_builder"),
        RoutingRule(TicketType.DEPENDENCY, "internal_builder"),
        RoutingRule(TicketType.CONFIG, "internal_reviewer"),
        RoutingRule(TicketType.MAINTENANCE, "internal_builder"),
        RoutingRule(TicketType.AUDIT_REQUEST, "internal_auditor"),
        RoutingRule(TicketType.SKILL_REQUEST, "internal_builder"),
        RoutingRule(TicketType.SKILL_UPGRADE, "internal_builder"),
        RoutingRule(TicketType.SKILL_GENERATED, "internal_reviewer"),
        RoutingRule(TicketType.RETRIEVE_FRAGMENT, "internal_builder"),
    ])

    # Routing history
    routing_history: List[Dict] = field(default_factory=list)

    # Current load per route
    load: Dict[str, int] = field(default_factory=dict)

    # Max concurrent tickets per route
    max_per_route: int = 10

    def route(self, ticket: Ticket) -> str:
        """
        Route a ticket to the appropriate engineer.

        Returns the name of the engineer/subsystem to handle it.
        """
        # Find the matching rule
        for rule in self.rules:
            if rule.ticket_type == ticket.ticket_type:
                if ticket.priority >= rule.priority_threshold:
                    route = rule.route_to
                    if self._can_accept(route):
                        self._record_route(ticket, route)
                        return route
                    else:
                        ticket.block(f"Route '{route}' is overloaded")
                        return "overflow_queue"

        # Default route
        default = "general_engineer"
        if self._can_accept(default):
            self._record_route(ticket, default)
            return default

        return "overflow_queue"

    def get_load(self, route: str) -> int:
        """Get current load for a route."""
        return self.load.get(route, 0)

    def _can_accept(self, route: str) -> bool:
        """Check if a route can accept more tickets."""
        return self.load.get(route, 0) < self.max_per_route

    def _record_route(self, ticket: Ticket, route: str) -> None:
        """Record the routing decision."""
        self.load[route] = self.load.get(route, 0) + 1
        self.routing_history.append({
            "ticket_id": ticket.id,
            "route": route,
            "ticket_type": ticket.ticket_type.value,
            "timestamp": datetime.now().isoformat(),
        })

    def release(self, route: str) -> None:
        """Release a slot on a route (when ticket completes)."""
        if route in self.load:
            self.load[route] = max(0, self.load[route] - 1)

    def summary(self) -> str:
        """Human-readable router status."""
        lines = ["🎯 ROUTER STATUS:"]
        for route, load in sorted(self.load.items()):
            pct = (load / self.max_per_route) * 100
            bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            lines.append(f"  {route:25s} [{bar}] {load}/{self.max_per_route}")
        return "\n".join(lines)

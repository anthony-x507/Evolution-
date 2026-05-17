# Mission Charter

Owner: A. Sanchez
Manager: Codex 0

## Purpose

Evolution Rocket Cluster is a standalone control fabric for coordinating
multiple Macs. It should not depend on Hermes, ABACO, OpenCloud, or any existing
profile system. Those systems may become clients later, but Rocket owns its own
node logic, scheduling, routing, health, state, logs, plugins, and upgrade path.

## Operating Principles

### Operational Stability

The cluster must avoid crashes, loops, lost jobs, ghost nodes, unsafe route
selection, and unexplained failures. Every major decision should have a reason
and an audit trail.

### Total Efficiency

The cluster should choose the best available route and machine. Thunderbolt can
win when available, Ethernet can win when stable, and Wi-Fi can be used when it
is the only reasonable path.

### Open Evolution

Rocket must remain modular and updatable. The architecture should support new
plugins, route strategies, scheduler policies, dashboards, and health checks
without forcing a full redesign.

## Trusted Node Family

Each Mac should have:

- a stable identity;
- a human-readable family name;
- explicit pairing;
- known routes;
- documented permissions;
- auditable messages;
- clear trust status;
- graceful fallback when a route is blocked.

## Non-Goals For The First Implementation

- No real Mac pairing.
- No live route checks.
- No persistent service.
- No launchd integration.
- No system setting changes.
- No dashboard control execution.
- No secrets or credentials.

# Evolution Rocket Cluster

Standalone cluster fabric for Anthony's Mac network.

## Mission

Evolution Rocket Cluster is designed to coordinate multiple Macs as a trusted
operational family. It is independent from Hermes, ABACO, OpenCloud, gateways,
profile systems, credentials, and existing runtime services.

The first goal is to build a clean, testable core before touching any real
machines.

## Three Master Rules

1. **Operational stability**: the system must be explainable, recoverable,
   observable, and strong under failure.
2. **Total efficiency**: the system should choose the best available machine
   and route, including Thunderbolt, Ethernet, or Wi-Fi when appropriate.
3. **Open evolution**: the architecture must remain modular, plugin-friendly,
   and ready for weekly improvement.

## Trusted Node Family

Rocket should make known Macs behave like trusted family nodes:

- stable node identity;
- explicit pairing;
- known routes;
- auditable messages;
- clear trust state;
- graceful fallback when a route is blocked.

## Current Status

Planning and repository bootstrap.

No live cluster implementation is active yet. The first code phase will be an
offline simulator using synthetic fixtures only.

## Hard Boundaries

This repository must not contain:

- secrets, tokens, API keys, Keychain exports, or `.env` files;
- Hermes profile configs;
- ABACO live files;
- gateway configs;
- launchd services;
- macOS firewall, TCC, Local Network, or Thunderbolt settings;
- copied source trees from research candidates.

## Planned Phases

1. Core cluster brain.
2. Runtime, plugin, and job lifecycle.
3. Multi-node simulation, failure, and recovery.
4. Dashboard projection.
5. Manual real cluster test readiness.

Phase 5 requires separate explicit owner approval after Phases 1-4 are green.

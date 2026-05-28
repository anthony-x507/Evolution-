# Josecito Project — Key Decisions

## 2026-05-27: Hybrid AgentInfra + Deep-Claw Architecture

**Decision:** Adopt a hybrid approach combining AgentInfra's structured knowledge directory with Deep-Claw's self-improvement cycle.

**Rationale:**
- AgentInfra provides persistent project context that survives session boundaries
- Deep-Claw provides autonomous improvement without human intervention
- Together they give the agent both knowledge AND growth

## 2026-05-27: Knowledge Directory

**Decision:** Place knowledge/ directory in project root, loaded at agent birth.

**Files:**
- ARCHITECTURE.md — system architecture
- DECISIONS.md — key decisions and rationale
- CAPABILITIES.md — what the system can do
- ACTIVE.md — current work in progress

## 2026-05-27: Symphony Prompt

**Decision:** Inject Kendo + Self-Awareness + GPS + Work + Knowledge into agent system prompt at birth.

**Components:**
1. Base identity (multilingual)
2. Safety Candle (Kendo) — 6 immutable rules
3. Engine context — GPS destination + Self-Awareness + Work Tracker
4. Knowledge Base — project context from knowledge/ directory
5. System info — version, creator, provider
6. Security guidance — yellow flag handling

## 2026-05-26: Modular Architecture

**Decision:** Split monolithic digos.py into digos_lib/ modules.

**Why:** Single file grew to 3000+ lines. Module separation allows independent testing and development.

## 2026-05-26: Security Levels

**Decision:** Three-level security policy (RED/YELLOW/GREEN).

**RED — Never:** Delete Principal Agent, Safety Candle, GPS, Self-Awareness, Work Destination, core structure, Engineer, vault
**YELLOW — With ticket:** Delete internal agents, change API keys/tokens, modify gateway
**GREEN — Permitted:** Normal operations, tools, skills

## 2026-05-26: Creator Identity

**Decision:** System creator is "Anthony Sanchez and an Artificial Intelligence".
The AI is never named individually ("Josecito") in system responses for legal safety.

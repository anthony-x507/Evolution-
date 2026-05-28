# Josecito Project — Architecture

## System Overview

Multi-agent system with Control Tower (TorreDeControl) as the central orchestrator.
Each agent is born with Kendo (Safety Candle), Self-Awareness, GPS (destination),
Work Tracker, and Knowledge Base injected into its system prompt.

## Core Components

### Control Tower (digos_lib/core_tower.py)
The brain. Born first, guides onboarding, lives 24/7 as daemon.
- Orchestrates Centinela, Engineer, Log Keeper, Self-Awareness
- Initializes Gateways (Telegram, CLI), Message Bus, AIAgent
- Runs daemon loop: Centinela cycle → Engineer cycle → Gateway polling

### AIAgent (digos_lib/agent_core.py)
The musician. Processes user messages with LLM + tools.
- Security Gate checks every input (RED/YELLOW/GREEN)
- Intent Classifier detects capability gaps (Camino B)
- LLM loop with tool execution and transparency tracking

### Centinela / Sentinel (digos_lib/core_centinela.py)
Detects defects. Does NOT investigate or decide.
- Monitors API keys, Telegram tokens
- Fires alarms and reminders
- Reports to System Engineer after 3 consecutive failures

### System Engineer (digos_lib/core_engineer.py)
Investigates and decides. Creates tickets per profile mailbox.
- FIFO queue processing
- Credential disclosure and rotation
- Internal agent creation through Factory
- Skill audit system (every 10 new skills)

### Security Gate (security.py)
~2ms filter on every incoming message.
- RED: immediate block (illegal content, weapons, chemicals)
- ORANGE: sanitize (prompt injection removed)
- YELLOW: annotate for LLM deep intent analysis
- GREEN: pass through

### Knowledge Base (digos_lib/knowledge_base.py)
Persistent structured knowledge loaded at agent birth.
- Architecture, decisions, capabilities, active context
- Injected into system prompt alongside Self-Awareness
- Updated by nightly Dream Cycle

## Data Flow

```
User → Gateway → Security Gate → Agent → LLM → Response
                              ↘ Intent Classifier ↗
                                  (Camino B)
```

## Nightly Cycle (Dream Cycle)

Runs once per night via Centinela alarm:
1. Scan skills and knowledge for gaps
2. Check for duplicates and stale content
3. Propose improvements
4. Update knowledge files
5. Log results in Engineer queue

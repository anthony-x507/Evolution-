# Josecito Project — Capabilities

## Current Capabilities

### Communication
- Telegram message send/receive (text)
- CLI interactive mode
- Message editing and deletion (Telegram API)

### Security
- RED content blocking (illegal, weapons, chemicals, exploitation)
- YELLOW word detection with LLM intent analysis
- Prompt injection detection and sanitization
- Credential redaction in inputs and outputs
- File scanning for dangerous patterns

### Knowledge & Memory
- Self-Awareness (identity, state)
- GPS (destination, course, deviations)
- Work Tracker (active, paused, completed tasks)
- Engineer ticket system (per-profile mailboxes, FIFO queue)
- Skill audit (every 10 skills, auto-analysis)

### Agent Operations
- Multi-agent Message Bus (Unix sockets)
- Internal agent creation (builders, auditors, reviewers)
- Credential disclosure and rotation
- Tool execution (web search, file ops, code exec, terminal)

### Transparency
- Real-time tool progress with emoji indicators
- Auto-clear progress window before final response
- Typing indicators (Telegram sendChatAction)

## Planned Capabilities

### Voice (in Factory queue)
- STT audio input (voice messages)
- TTS audio output (voice responses)
- Full duplex voice conversation

### Web
- Web browsing and navigation
- Enhanced web search
- API data fetching

# MASTER Factory Engineer Soul

This file is the operating soul for the Factory Engineer. It is not public
copy. It is the internal contract the Engineer must follow when a capability
request reaches the Factory.

## Voice Input For Telegram

Capability:
`stt_audio_input`

Goal:
Enable MASTER to receive a Telegram voice message, convert it to governed text,
and pass that text into the same agent path used by normal Telegram text.

The capability is not complete when the Factory only creates an STT processor.
It is complete only when the voice path is connected end to end:

Telegram voice message
-> GatewayTelegram
-> secure audio download
-> STT transcription
-> governed text message
-> AIAgent
-> final Telegram response

### Required Engineer Work

1. Telegram intake
- Update the Telegram gateway so `poll_updates()` recognizes `message["voice"]`.
- Also accept `message["audio"]` when Telegram sends an audio file instead of a
  voice note.
- Preserve the same chat boundary used for text messages.
- Capture only the metadata needed for processing:
  `chat_id`, `message_id`, `file_id`, `file_unique_id`, `duration`, `mime_type`,
  and `file_size` if present.
- Do not treat a voice message as plain unsupported text once this capability is
  installed.

2. Telegram file download
- Implement the Bot API file flow:
  call `getFile` with the voice/audio `file_id`;
  read the returned `file_path`;
  download the file from Telegram's file endpoint using the bot token and
  `file_path`.
- Keep the token out of logs, prompts, tickets, Factory notes, and user-visible
  messages.
- Download audio only into a private runtime temp directory, never into the repo.
- Delete the temp audio after transcription unless a future explicit retention
  policy is approved.

3. Audio guardrails
- Enforce a maximum duration and maximum file size before download/transcription.
- Reject unsupported or excessive audio politely.
- Do not forward raw audio to the language provider.
- Do not store private audio in knowledge, logs, tickets, or summaries.
- Redact accidental credentials found in transcripts before sending text to the
  provider.

4. STT engine
- Add a configurable STT adapter.
- The first adapter may be OpenAI-compatible Whisper, local Whisper, or another
  approved STT provider, but it must be explicit.
- If no STT adapter is configured, the capability stays pending activation and
  MASTER must continue saying it works by text only.
- The adapter returns text plus safe metadata: language if detected, confidence
  if available, duration, and provider name.

5. Governed text handoff
- Convert the transcript into a normal governed user message.
- Mark the internal source as `telegram_voice_transcript`.
- Pass the transcript through the same privacy, safety, language, identity,
  capability, Factory, and provider gates used for typed text.
- The agent must not bypass MASTER governance because the input came from audio.

6. Language behavior
- If the transcript language differs from the active response language, follow
  the existing language-awareness rule: ask before changing response language,
  unless the user explicitly requested a change.
- Do not switch languages just because STT detected another language.

7. Telegram response
- Send the final response through the existing Telegram send path.
- Do not create a separate Telegram -> STT -> provider -> Telegram shortcut.
- If the transcription fails, respond with a clear product message:
  "No pude entender ese audio. Puedes intentarlo otra vez o escribirlo por texto."

8. Activation evidence
The Engineer may mark `stt_audio_input` active only after these checks pass:
- fake/local Telegram voice update is recognized;
- fake/local `getFile` response is handled;
- fake/local audio download path is created outside the repo;
- fake STT transcript is produced;
- transcript reaches AIAgent as governed text;
- normal text gates still apply to the transcript;
- final Telegram response is sent through the normal gateway;
- unsupported/oversized audio is refused cleanly;
- secrets do not appear in logs, tickets, prompts, or user-visible status;
- no internal names, ticket internals, or Factory mechanics are exposed.

### Required User-Facing Honesty

Before the full checklist passes:
MASTER must say that voice is not active yet.

Allowed:
"La Factoría está trabajando la capacidad de voz. Todavía falta conectarla al
canal de Telegram y validarla de punta a punta."

Not allowed:
- "Ya puedes mandar mensajes de voz."
- "La herramienta está lista."
- "La Factoría terminó" if Telegram intake, file download, STT, governed handoff,
  and final Telegram response are not all verified.

### Responsibility Split

- GatewayTelegram owns Telegram update intake, file metadata, `getFile`, and
  secure download.
- STT adapter owns audio-to-text conversion.
- AIAgent owns governed reasoning over the transcript.
- Factory Engineer owns coordination, evidence, ticket status, and activation
  honesty.
- Runtime Integration owns marking the capability active only after the live
  channel path is connected.

The Engineer must keep the whole chain visible to itself until the ticket closes.
If any link is missing, the capability remains pending activation.

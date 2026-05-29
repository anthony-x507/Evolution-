"""
DIGOS Intent Classifier — Hybrid Architecture
=============================================

Translates natural human language into operational intent.
Bridges the gap between "Quiero que me escuches" and
"SKILL_REQUEST: stt_audio_input → Factory".

Architecture:
  Camino A (regex): Structured commands (api_key, credentials, agent creation)
  Camino B (LLM):   Natural language → intent family → capability gap → Factory

Principle: "No decir 'no puedo', decir 'eso requiere una mejora; puedo prepararla.'"
"""

import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

from digos_lib.agent_tools import AVAILABLE_TOOLS


# ── Intent Families ──────────────────────────────────────────────────

@dataclass
class SubIntent:
    """A specific sub-intention within a family."""
    id: str                              # e.g., "VOICE_INPUT_CAPABILITY_REQUEST"
    description: str                     # human-readable description
    capability: str                      # required capability (e.g., "stt_input")
    gap_response: str                    # what to tell the user when capability is missing


@dataclass
class IntentFamily:
    """A family of related intents."""
    id: str                              # e.g., "VOICE"
    description: str                     # human-readable description
    sub_intents: List[SubIntent] = field(default_factory=list)


@dataclass
class IntentClassification:
    """Result of intent classification."""
    matched: bool = False
    family: str = ""
    family_description: str = ""
    sub_intent_id: str = ""
    sub_intent_description: str = ""
    capability: str = ""
    has_gap: bool = True                 # True if the capability is NOT available
    gap_response: str = ""               # Response to give when gap exists
    factory_action: str = ""             # "SKILL_REQUEST" or "" if no factory action needed
    confidence: float = 0.0
    raw_response: str = ""               # For debugging


# ── Intent Families Definition ───────────────────────────────────────

INTENT_FAMILIES: Dict[str, IntentFamily] = {
    "VOICE": IntentFamily(
        id="VOICE",
        description="Audio/voice communication — STT, TTS, voice messages",
        sub_intents=[
            SubIntent(
                id="VOICE_INPUT_NOW",
                description="User wants to send audio/voice right now (in this conversation)",
                capability="stt_audio_input",
                gap_response=(
                    "Por ahora no puedo procesar audio ni mensajes de voz. "
                    "Puedo responder mensajes de texto."
                ),
            ),
            SubIntent(
                id="VOICE_INPUT_CAPABILITY_REQUEST",
                description="User wants the system to GAIN the ability to receive audio/voice messages",
                capability="stt_audio_input",
                gap_response=(
                    "Puedo dejar esa solicitud identificada para agregar mensajes de voz. "
                    "Todavía no queda activa en Telegram."
                ),
            ),
            SubIntent(
                id="VOICE_OUTPUT_REQUEST",
                description="User wants the system to respond with voice/audio (TTS)",
                capability="tts_audio_output",
                gap_response=(
                    "Para responder con voz necesito una capacidad de audio que todavía "
                    "no está activa. Puedo dejar esa solicitud identificada para revisión."
                ),
            ),
            SubIntent(
                id="VOICE_CONVERSATION_REQUEST",
                description="User wants full bidirectional voice conversation (STT + TTS)",
                capability="voice_full_duplex",
                gap_response=(
                    "La conversación por voz todavía no está activa. "
                    "Puedo dejar identificada la solicitud para agregar voz de entrada, "
                    "voz de salida o ambas."
                ),
            ),
            SubIntent(
                id="VOICE_HELP_OR_SETUP_REQUEST",
                description="User asks how to activate or set up voice features",
                capability="voice_full_duplex",
                gap_response=(
                    "La función de voz todavía no está disponible para activarse desde aquí. "
                    "Puedo dejar esa solicitud identificada para revisión."
                ),
            ),
            SubIntent(
                id="VOICE_FRUSTRATION",
                description="User is frustrated or complaining about lack of voice support",
                capability="stt_audio_input",
                gap_response=(
                    "Entiendo. Por ahora solo puedo trabajar con texto, "
                    "pero puedo dejar identificada la solicitud para agregar voz."
                ),
            ),
        ],
    ),
    "WEB": IntentFamily(
        id="WEB",
        description="Web browsing, search, and internet capabilities",
        sub_intents=[
            SubIntent(
                id="WEB_BROWSING_REQUEST",
                description="User wants the system to browse the web or open websites",
                capability="web_browsing",
                gap_response=(
                    "Ahora no tengo navegación web activa desde Telegram. "
                    "Puedo dejar esa solicitud identificada para revisión."
                ),
            ),
            SubIntent(
                id="WEB_SEARCH_REQUEST",
                description="User wants the system to search the internet",
                capability="web_search",
                gap_response=(
                    "Ahora no tengo búsqueda web activa desde Telegram. "
                    "Puedo dejar esa solicitud identificada para revisión."
                ),
            ),
            SubIntent(
                id="WEB_DATA_REQUEST",
                description="User wants to fetch data from a URL or API",
                capability="web_fetch",
                gap_response=(
                    "Ahora no tengo lectura de páginas web activa desde Telegram. "
                    "Puedo dejar esa solicitud identificada para revisión."
                ),
            ),
        ],
    ),
    "NEW_TOOL": IntentFamily(
        id="NEW_TOOL",
        description="User wants a new tool, feature, or capability not yet available",
        sub_intents=[
            SubIntent(
                id="GENERIC_CAPABILITY_REQUEST",
                description="User requests a capability the system doesn't have yet",
                capability="custom_tool",
                gap_response=(
                    "🛠️ I see you need a capability I don't have yet. "
                    "Could you describe what you need in a bit more detail? "
                    "What exactly should this tool do?\n\n"
                    "Once I have a clear picture, I can check if the Factory "
                    "can build it for you."
                ),
            ),
            SubIntent(
                id="SPECIFIC_TOOL_REQUEST",
                description="User asks for a specific named tool or integration",
                capability="custom_tool",
                gap_response=(
                    "🛠️ I understand you want a specific tool. "
                    "Could you tell me more about what it should do?\n"
                    "  - What's the main task you need it for?\n"
                    "  - Any specific API or service it should work with?\n\n"
                    "With more details I can prepare a precise Factory request."
                ),
            ),
        ],
    ),
    "CONVERSATION": IntentFamily(
        id="CONVERSATION",
        description="Normal conversation — no capability gap, no factory action needed",
        sub_intents=[
            SubIntent(
                id="GENERAL_CHAT",
                description="Normal conversation, question, or request within existing capabilities",
                capability="",
                gap_response="",
            ),
        ],
    ),
}

# Flattened lookup: sub_intent_id → SubIntent
_ALL_SUB_INTENTS: Dict[str, SubIntent] = {}
for family in INTENT_FAMILIES.values():
    for si in family.sub_intents:
        _ALL_SUB_INTENTS[si.id] = si


def get_family(family_id: str) -> Optional[IntentFamily]:
    """Get an intent family by ID."""
    return INTENT_FAMILIES.get(family_id)


def get_sub_intent(sub_intent_id: str) -> Optional[SubIntent]:
    """Get a sub-intent by ID."""
    return _ALL_SUB_INTENTS.get(sub_intent_id)


# ── Capabilities Registry ─────────────────────────
# Tools and features that are ALREADY available.
# If a capability is in this set, the intent classifier
# will NOT route it to Factory — it passes to normal LLM.
AVAILABLE_CAPABILITIES = {
    tool["function"]["name"]
    for tool in AVAILABLE_TOOLS
    if tool.get("type") == "function" and tool.get("function", {}).get("name")
}

# ── Classification Prompt ────────────────────────────────────────────

CLASSIFICATION_SYSTEM_PROMPT = """You are an intent classifier for MASTER. Your ONLY task is to classify the user's message into an intent family and sub-intent.

Respond with ONLY a JSON object. Nothing else. No markdown, no explanations.

The JSON must have exactly these fields:
{
  "family": "VOICE" | "WEB" | "NEW_TOOL" | "CONVERSATION",
  "sub_intent": "VOICE_INPUT_NOW" | "VOICE_INPUT_CAPABILITY_REQUEST" | "VOICE_OUTPUT_REQUEST" | "VOICE_CONVERSATION_REQUEST" | "VOICE_HELP_OR_SETUP_REQUEST" | "VOICE_FRUSTRATION" | "WEB_BROWSING_REQUEST" | "WEB_SEARCH_REQUEST" | "WEB_DATA_REQUEST" | "GENERIC_CAPABILITY_REQUEST" | "SPECIFIC_TOOL_REQUEST" | "GENERAL_CHAT",
  "confidence": 0.0 to 1.0
}

FAMILIES:

VOICE — Audio/voice:
The user wants to send, receive, or interact with audio/voice.
Look for NATURAL LANGUAGE clues (not technical terms):

  VOICE_INPUT_NOW: User wants to send audio RIGHT NOW
    EN: "listen to this", "hear me out", "I'm sending a voice message",
        "check this audio", "I have a voice note for you"
    ES: "escucha esto", "te mando un audio", "te voy a mandar un mensaje de voz",
        "oye esto", "préstame atención", "escúchame un momento"
    PT: "escuta isso", "vou mandar um áudio", "ouve isso"

  VOICE_INPUT_CAPABILITY_REQUEST: User wants the system to GAIN the ability to hear/receive audio
    EN: "I want you to listen to me", "can you hear me?", "I need you to understand audio",
        "when will you be able to hear me?", "learn to listen", "I wish you could hear me",
        "can you process voice messages?", "I want to talk to you"
    ES: "quiero que me escuches", "necesito que me entiendas", "puedes oírme?",
        "quiero que entiendas audio", "necesito hablar contigo", "quiero conversar contigo",
        "quiero mandarte un mensaje de voz", "quiero que me entiendas en audio",
        "puedes escuchar?", "te puedo hablar?", "puedes oír lo que digo?"
    PT: "quero que me ouça", "você pode me ouvir?", "preciso falar com você"

  VOICE_OUTPUT_REQUEST: User wants the system to SPEAK back (TTS)
    EN: "talk to me", "speak to me", "answer me with your voice",
        "I want to hear your voice", "can you say it out loud?", "read it to me"
    ES: "respóndeme", "háblame", "dímelo en voz alta", "quiero escuchar tu voz",
        "puedes hablar?", "léemelo"

  VOICE_CONVERSATION_REQUEST: User wants full two-way voice conversation
    EN: "can we have a conversation?", "I want to talk to you properly",
        "can we talk?", "I want a voice call", "let's have a chat"
    ES: "podemos tener una conversación?", "quiero hablar contigo",
        "podemos tener una llamada?", "quiero conversar", "háblame y te respondo"

  VOICE_HELP_OR_SETUP_REQUEST: User asks HOW to activate/use voice
    EN: "how do I use voice?", "how to activate audio?", "can I use voice commands?",
        "setup voice", "enable microphone"
    ES: "cómo activo el audio?", "cómo uso la voz?", "se puede usar voz?",
        "activa el micrófono", "configura el audio"

  VOICE_FRUSTRATION: User is frustrated about lack of voice support
    EN: "why can't you hear me?", "you don't understand audio",
        "this is useless without voice", "I need voice support"
    ES: "por qué no puedes oírme?", "no entiendes audio", "no sirves sin voz",
        "necesito que me escuches"

WEB — Internet browsing/search:
The user wants to browse, search, or fetch data from the internet.

  WEB_BROWSING_REQUEST: User wants to navigate/open a website
    EN: "go to", "open this page", "navigate to", "take me to",
        "open google", "visit this website", "load this URL"
    ES: "abre google", "ve a esta página", "navega a", "llévame a",
        "abre esta página", "entra a este sitio"

  WEB_SEARCH_REQUEST: User wants to search the internet
    EN: "search for", "look up", "find information about", "google this",
        "research", "look into", "find me", "I want to know about",
        "search the web", "search online", "investigate"
    ES: "busca en internet", "googlea esto", "investiga", "encuentra información",
        "quiero buscar", "búscame", "averigua", "investiga sobre",
        "quiero que investigues", "quiero que me ayudes a buscar"

  WEB_DATA_REQUEST: User wants data from a specific URL/API
    EN: "fetch this URL", "read this page", "get data from",
        "download from this link", "extract from this website"
    ES: "lee esta página", "descarga de esta URL", "trae datos de",
        "obtén información de esta página"

NEW_TOOL — New capability requested:
The user asks for something the system clearly cannot do yet,
or explicitly asks for a new tool/feature.

  GENERIC_CAPABILITY_REQUEST: User wants a capability that doesn't exist
    EN: "can you do X?", "I need you to do Y", "I wish you could...",
        "is there a way to...", "I want a tool that...", "do you support...",
        "can you integrate with...", "I need a feature for..."
    ES: "puedes hacer X?", "necesito que hagas Y", "necesito una herramienta para...",
        "hay alguna forma de...?", "quiero una función que...",

  SPECIFIC_TOOL_REQUEST: User asks for a specific named tool
    EN: "create a tool for...", "add integration with...", "build me a...",
        "I need a tool that can...", "develop a feature to..."
    ES: "necesito una herramienta para X", "agrega integración con Y",
        "crea un tool para...", "fabrica una herramienta que..."

CONVERSATION — Normal chat:
  GENERAL_CHAT: Normal conversation, question, greeting, small talk.
  ALWAYS use this when the message is NOT about voice, web, or a new tool.

RULES:
1. If the message contains ANY of these clues → classify as the matching family
2. When in doubt, prefer a LOWER confidence over wrong classification
3. For ambiguous messages, choose the most LIKELY intent based on ALL clues
4. English, Spanish, Portuguese, French, and German clues are all valid

IMPORTANT: Respond ONLY with the JSON. No text before or after."""


def classify_intent(
    user_message: str,
    base_url: str = "",
    api_key: str = "",
    model: str = "gpt-4o",
    timeout: int = 15,
) -> IntentClassification:
    """Classify a user message into an intent family and sub-intent.

    Uses a lightweight LLM call for classification. This is the Camino B
    of the hybrid architecture — natural language that doesn't match regex.

    Args:
        user_message: The raw user message
        base_url: LLM API base URL
        api_key: LLM API key
        model: Model to use for classification (usually the same as main agent)
        timeout: Timeout in seconds

    Returns:
        IntentClassification with family, sub_intent, capability gap info
    """
    if not base_url or not api_key:
        return IntentClassification(
            matched=False,
            family="CONVERSATION",
            sub_intent_id="GENERAL_CHAT",
            gap_response="",
            confidence=0.0,
        )

    endpoint = base_url.rstrip("/") + "/chat/completions"

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_message[:500]},  # truncate long messages
        ],
        "max_tokens": 150,
        "temperature": 0.0,  # deterministic
    }

    try:
        payload = json.dumps(body).encode("utf-8")
        req = Request(
            endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))

        choices = data.get("choices", [])
        if not choices:
            return _fallback_classification()

        content = choices[0].get("message", {}).get("content", "").strip()

        # Parse the JSON response
        return _parse_classification_response(content, user_message)

    except URLError:
        return _fallback_classification()
    except json.JSONDecodeError:
        return _fallback_classification()
    except Exception:
        return _fallback_classification()


def _parse_classification_response(
    content: str,
    user_message: str = "",
) -> IntentClassification:
    """Parse the LLM classification response into an IntentClassification."""
    # Try to extract JSON from response (handle markdown code blocks)
    json_str = content.strip()

    # Remove markdown code fences if present
    if json_str.startswith("```"):
        lines = json_str.split("\n")
        if len(lines) > 1:
            lines = lines[1:]  # remove opening ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # remove closing ```
        json_str = "\n".join(lines).strip()

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        return _fallback_classification()

    family_id = parsed.get("family", "CONVERSATION")
    sub_intent_id = parsed.get("sub_intent", "GENERAL_CHAT")
    confidence = float(parsed.get("confidence", 0.5))

    family = get_family(family_id)
    sub_intent = get_sub_intent(sub_intent_id)

    if family is None or sub_intent is None:
        return _fallback_classification()

    # CONVERSATION family means no capability gap
    if family_id == "CONVERSATION":
        return IntentClassification(
            matched=True,
            family=family_id,
            family_description=family.description,
            sub_intent_id=sub_intent_id,
            sub_intent_description=sub_intent.description,
            capability="",
            has_gap=False,
            gap_response="",
            factory_action="",
            confidence=confidence,
            raw_response=content,
        )

    # Check if the required capability is already available
    cap = sub_intent.capability if sub_intent else ""
    has_gap = bool(cap) and cap not in AVAILABLE_CAPABILITIES
    factory_action = "SKILL_REQUEST" if has_gap else ""

    return IntentClassification(
        matched=True,
        family=family_id,
        family_description=family.description,
        sub_intent_id=sub_intent_id,
        sub_intent_description=sub_intent.description,
        capability=sub_intent.capability,
        has_gap=has_gap,
        gap_response=sub_intent.gap_response,
        factory_action=factory_action,
        confidence=confidence,
        raw_response=content,
    )


# ── Capability → Skill Mapping ────────────────────────────────────────
# When a capability gap is confirmed, this map tells the Factory
# what skill to create: name, capabilities to develop, limitations, description.

@dataclass
class CapabilitySkillDefinition:
    """Defines a skill for the Factory to build."""
    skill_name: str
    description: str
    target_capabilities: List[str] = field(default_factory=list)
    target_limitations: List[str] = field(default_factory=list)
    activation_requirements: List[str] = field(default_factory=list)
    tool_name: str = ""  # name of the tool the Factory will produce


CAPABILITY_SKILL_MAP: Dict[str, CapabilitySkillDefinition] = {
    # ── VOICE ──
    "stt_audio_input": CapabilitySkillDefinition(
        skill_name="speech_to_text",
        description="Speech-to-text: convierte mensajes de voz/audio en texto para procesamiento",
        target_capabilities=[
            "receive_telegram_voice_messages",
            "download_telegram_audio_files",
            "transcribe_speech_to_text",
            "route_transcript_as_governed_text",
            "support_spanish_voice",
            "support_english_voice",
        ],
        target_limitations=[
            "requires_whisper_api_or_similar",
            "max_audio_duration_5min",
            "requires_telegram_getfile_download_flow",
            "must_not_store_private_audio_in_repo_or_logs",
        ],
        activation_requirements=[
            "actualizar GatewayTelegram.poll_updates para reconocer message.voice y message.audio",
            "capturar chat_id, message_id, file_id, file_unique_id, duration, mime_type y file_size si existe",
            "usar getFile con file_id y descargar el archivo desde el endpoint de archivos de Telegram",
            "guardar el audio solo en un directorio temporal privado fuera del repo y borrarlo despues de transcribir",
            "validar duracion, tamano y tipo de audio antes de descargar o transcribir",
            "transcribir el audio con un adaptador STT configurado y explicito",
            "redactar credenciales accidentales en la transcripcion antes de enviarla al proveedor",
            "enviar la transcripcion al agente como mensaje de texto gobernado con source telegram_voice_transcript",
            "pasar la transcripcion por privacidad, safety, idioma, identidad, capability, Factoria y provider gates",
            "responder por el mismo GatewayTelegram sin crear ruta directa Telegram-STT-provider-Telegram",
            "validar fake/local: voice update, getFile, descarga temporal, STT fake, handoff al agente y respuesta final",
        ],
        tool_name="stt_processor",
    ),
    "tts_audio_output": CapabilitySkillDefinition(
        skill_name="text_to_speech",
        description="Text-to-speech: convierte respuestas de texto en audio/voz",
        target_capabilities=[
            "synthesize_text_to_voice",
            "stream_audio_response",
            "support_spanish_tts",
            "support_english_tts",
        ],
        target_limitations=[
            "requires_tts_api",
            "voice_quality_depends_on_provider",
        ],
        activation_requirements=[
            "generar audio desde la respuesta final aprobada",
            "configurar proveedor TTS explicito con voice, speed, language y modo por chat",
            "aplicar perfil de voz aprobado como es-MX-JorgeNeural con velocidad configurable",
            "generar audio solo despues de output safety y nunca desde reglas internas",
            "convertir audio a formato compatible con Telegram voice/audio",
            "enviar el archivo de audio al canal de Telegram",
            "mantener una respuesta de texto si el audio falla",
            "borrar audio temporal despues de enviarlo salvo politica de retencion aprobada",
            "validar el flujo completo antes de marcarlo activo",
        ],
        tool_name="tts_synthesizer",
    ),
    "voice_full_duplex": CapabilitySkillDefinition(
        skill_name="voice_conversation",
        description="Conversación por voz completa: STT + TTS bidireccional",
        target_capabilities=[
            "receive_audio_messages",
            "transcribe_speech_to_text",
            "synthesize_text_to_voice",
            "stream_audio_response",
            "full_duplex_conversation",
        ],
        target_limitations=[
            "requires_both_stt_and_tts_apis",
            "latency_depends_on_provider",
        ],
        activation_requirements=[
            "recibir audio desde Telegram",
            "transcribir audio a texto",
            "procesar la transcripcion por el agente",
            "generar respuesta de voz desde salida aprobada",
            "mantener modos por chat off, voice_only y all",
            "evitar doble envio de voz cuando el adaptador ya respondio",
            "validar STT y TTS por separado antes de activar conversacion completa",
            "validar entrada y salida de voz antes de marcarlo activo",
        ],
        tool_name="voice_duplex",
    ),
    # ── WEB ──
    "web_browsing": CapabilitySkillDefinition(
        skill_name="web_browser",
        description="Navegación web: permite abrir y leer páginas web",
        target_capabilities=[
            "fetch_web_page",
            "extract_readable_content",
            "render_javascript_pages",
            "follow_links",
        ],
        target_limitations=[
            "requires_headless_browser",
            "some_sites_block_automation",
        ],
        activation_requirements=[
            "configurar o adjuntar Chrome CDP con browser.cdp_url ws://127.0.0.1:9222",
            "usar perfil dedicado de navegador para automatizacion",
            "verificar endpoint CDP antes de decir que navegacion web esta activa",
            "navegar solo URLs solicitadas o resultados permitidos",
            "aplicar checks de URL, redirecciones, timeouts y tamano de respuesta",
            "extraer titulo, URL, texto legible y evidencia segura",
            "no exponer cookies, tokens, local storage ni datos privados del navegador",
        ],
        tool_name="web_browser",
    ),
    "web_search": CapabilitySkillDefinition(
        skill_name="web_searcher",
        description="Búsqueda web: buscar información en internet",
        target_capabilities=[
            "search_web",
            "parse_search_results",
            "rank_by_relevance",
        ],
        target_limitations=[
            "requires_search_api",
            "rate_limited_by_provider",
        ],
        activation_requirements=[
            "recibir consulta de busqueda desde Telegram o CLI",
            "validar intencion segura antes de buscar",
            "ejecutar busqueda con adaptador permitido o CDP/search provider configurado",
            "resumir resultados con fuente o URL visible cuando aplique",
            "bloquear busquedas inseguras antes de usar el adaptador",
            "impedir que el proveedor invente resultados web si no hubo evidencia de busqueda",
        ],
        tool_name="web_searcher",
    ),
    "telegram_web_search": CapabilitySkillDefinition(
        skill_name="telegram_web_search",
        description="Búsqueda web desde Telegram bajo gobierno MASTER",
        target_capabilities=[
            "receive_web_search_request_from_telegram",
            "classify_safe_search_intent",
            "execute_web_search_when_allowed",
            "summarize_sources_for_telegram",
            "refuse_unsafe_searches",
        ],
        target_limitations=[
            "requires_live_channel_web_policy",
            "must_not_search_for_unsafe_acquisition",
            "must_keep_source_attribution",
        ],
        activation_requirements=[
            "conectar solicitudes de búsqueda web al canal de Telegram",
            "configurar o adjuntar Chrome CDP con browser.cdp_url ws://127.0.0.1:9222 o proveedor de busqueda aprobado",
            "validar intención segura antes de buscar",
            "ejecutar búsqueda con proveedor permitido",
            "mantener evidencia de que el adaptador web corrio antes de mencionar resultados actuales",
            "resumir fuentes de forma corta para Telegram",
            "filtrar resultados antes de responder al usuario",
            "bloquear busquedas de adquisicion peligrosa o instrucciones de dano antes de navegar",
            "validar el flujo completo con una búsqueda permitida y una bloqueada",
        ],
        tool_name="telegram_web_search",
    ),
    "web_fetch": CapabilitySkillDefinition(
        skill_name="data_fetcher",
        description="Fetch de datos: obtener datos de URLs y APIs externas",
        target_capabilities=[
            "fetch_url",
            "parse_json_response",
            "handle_authentication",
        ],
        target_limitations=[
            "respects_robots_txt",
            "rate_limited",
        ],
        tool_name="data_fetcher",
    ),
    # ── VISION ──
    "vision_image_input": CapabilitySkillDefinition(
        skill_name="image_vision",
        description="Visión de imágenes: recibir imágenes/capturas desde Telegram y convertirlas en contexto seguro",
        target_capabilities=[
            "receive_images_from_telegram",
            "extract_image_context",
            "support_screenshot_analysis",
            "support_document_image_reading",
            "route_vision_result_to_agent",
        ],
        target_limitations=[
            "requires_vision_model_or_ocr_provider",
            "must_not_store_private_images_unnecessarily",
            "image_quality_affects_accuracy",
        ],
        activation_requirements=[
            "recibir message.photo y documentos de imagen desde Telegram",
            "capturar chat_id, message_id, file_id, file_unique_id, mime_type y file_size si existe",
            "usar getFile con file_id y descargar el archivo visual de forma segura",
            "guardar imagen solo en directorio temporal privado fuera del repo",
            "validar tipo MIME, tamano y dimensiones antes de analizar",
            "analizar la imagen con OCR o modelo de vision explicito",
            "redactar tokens, passwords y datos sensibles visibles antes de enviar contexto al proveedor",
            "pasar el resumen visual al agente como contexto gobernado con source telegram_image_context",
            "validar privacidad y respuestas antes de marcarlo activo",
        ],
        tool_name="image_vision",
    ),
    # ── NEW_TOOL (generic) ──
    "custom_tool": CapabilitySkillDefinition(
        skill_name="custom_capability",
        description="Capacidad personalizada solicitada por el usuario",
        target_capabilities=["custom_implementation"],
        target_limitations=["to_be_defined"],
        tool_name="custom_tool",
    ),
}


def get_skill_for_capability(capability: str) -> Optional[CapabilitySkillDefinition]:
    """Get the skill definition for a capability ID."""
    return CAPABILITY_SKILL_MAP.get(capability)


def _fallback_classification() -> IntentClassification:
    """Fallback when classification fails — treat as normal conversation."""
    return IntentClassification(
        matched=False,
        family="CONVERSATION",
        sub_intent_id="GENERAL_CHAT",
        gap_response="",
        factory_action="",
        confidence=0.0,
    )

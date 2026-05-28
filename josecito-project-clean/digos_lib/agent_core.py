"""DIGOS AIAgent Core — LLM interaction loop with tool calling + transparency."""
import json
import re
import unicodedata
from typing import Optional, Dict, List, Any, Callable
from urllib.request import Request, urlopen
from urllib.error import URLError

# Security
from security import SecurityGate, EXTERNAL_TOOLS

# Tools
from digos_lib.agent_tools import (
    AVAILABLE_TOOLS, DANGEROUS_TOOLS, _execute_tool,
)

# Intent Classification (Camino B — natural language → capability gap)
from digos_lib.intent_classifier import classify_intent, IntentClassification


class AIAgent:
    """Agent that processes messages with LLM + tools + transparency.

    Uso:
        agent = AIAgent(
            base_url="https://api.openai.com/v1",
            api_key="sk-...",
            model="gpt-4o",
            progress_cb=tower.emit_tool_progress,
            assistant_cb=tower.emit_assistant_message,
        )
        response = agent.process_message("Hola, ¿qué hora es?")
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        model: str = "gpt-4o",
        system_prompt: str = "You are a helpful assistant. You can use tools para ayudar al usuario.",
        progress_cb: Optional[Callable] = None,
        assistant_cb: Optional[Callable] = None,
        approval_cb: Optional[Callable] = None,
        disclosure_cb: Optional[Callable] = None,
        rotation_cb: Optional[Callable] = None,
        creation_cb: Optional[Callable] = None,
        capability_cb: Optional[Callable] = None,
        factory_status_cb: Optional[Callable] = None,
        language: str = "es",
        max_iterations: int = 15,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._system_prompt = system_prompt
        self._progress_cb = progress_cb or (lambda n, a: None)
        self._assistant_cb = assistant_cb or (lambda t: None)
        self._approval_cb = approval_cb
        self._disclosure_cb = disclosure_cb
        self._rotation_cb = rotation_cb
        self._creation_cb = creation_cb
        self._capability_cb = capability_cb
        self._factory_status_cb = factory_status_cb
        self._language = language or "es"
        self._max_iterations = max_iterations

        # Conversation history
        self._messages: List[dict] = [{"role": "system", "content": system_prompt}]
        self._tools_enabled = True
        self._pending_rotation: Optional[str] = None  # credential_type when user is mid-rotation
        self._pending_intent: Optional[IntentClassification] = None  # intent waiting for user confirmation
        self._pending_intent_msg: str = ""  # original message that triggered the intent
        self._pending_language: Optional[str] = None  # language change waiting for user confirmation
        self._last_public_topic: str = ""

        # Security Gate
        self._gate = SecurityGate()

        # Identity responses (from DIGOS system)
        self._identity_responses = []
        try:
            from digos_lib.constants import IDENTITY_RESPONSES
            self._identity_responses = IDENTITY_RESPONSES
        except Exception:
            self._identity_responses = {"es": [], "en": []}

    def _check_identity_question(self, message: str) -> str:
        """Detects if the message asks about the system identity.
        Responds without calling the LLM to save time and tokens."""
        msg_lower = message.lower().strip()
        for lang, pairs in self._identity_responses.items():
            for question, answer in pairs:
                if question in msg_lower:
                    return answer
        return ""

    @staticmethod
    def _norm(text: str) -> str:
        """Accent-insensitive lowercase text for routing."""
        lowered = text.lower().strip()
        deaccented = unicodedata.normalize("NFKD", lowered)
        deaccented = "".join(ch for ch in deaccented if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", deaccented)

    def _remember_and_return(self, clean_msg: str, response: str, topic: str = "") -> str:
        self._messages.append({"role": "user", "content": clean_msg})
        self._messages.append({"role": "assistant", "content": response})
        self._last_public_topic = topic or self._last_public_topic
        return response

    def _detect_language_shift(self, msg: str) -> str:
        """Return a likely message language when it differs from the active one."""
        spanish_terms = [
            "hola", "como estas", "como estás", "puedo", "quiero", "necesito",
            "herramienta", "voz", "escuches", "activar", "funcion", "función",
            "que puedes", "quien eres", "quién eres",
        ]
        english_terms = [
            "hello", "hi", "how are you", "can i", "could you", "i want",
            "i need", "please", "what can you", "who are you", "speak english",
            "talk in english",
        ]
        spanish_hits = sum(1 for term in spanish_terms if term in msg)
        english_hits = sum(1 for term in english_terms if term in msg)
        if english_hits and english_hits > spanish_hits and self._language != "en":
            return "en"
        if spanish_hits and spanish_hits > english_hits and self._language != "es":
            return "es"
        return ""

    def _language_change_response(self, msg: str) -> str:
        if self._pending_language:
            confirmation = self._check_intent_confirmation(msg)
            target = self._pending_language
            if confirmation == "yes":
                self._pending_language = None
                self._language = target
                if target == "es":
                    return "Listo. Voy a continuar en español."
                return "Done. I will continue in English."
            if confirmation == "no":
                self._pending_language = None
                if self._language == "es":
                    return "Listo. Sigo en español."
                return "OK. I will keep English."

        if any(term in msg for term in ["switch to espanol", "switch to español", "cambia a espanol", "cambia a español"]):
            self._language = "es"
            return "Listo. Voy a continuar en español."
        if any(term in msg for term in ["switch to english", "cambia a ingles", "cambia a inglés"]):
            self._language = "en"
            return "Done. I will continue in English."
        if "ingles" in msg or "english" in msg:
            self._pending_language = "en"
            return "Sí. Podemos hablar en inglés. ¿Quieres que cambie a inglés ahora?"
        if "espanol" in msg or "spanish" in msg:
            self._pending_language = "es"
            return "Sí. Podemos hablar en español. ¿Quieres que siga en español?"
        shifted = self._detect_language_shift(msg)
        if shifted == "en":
            self._pending_language = "en"
            return "Noté que escribiste en inglés. ¿Quieres que cambie a inglés o sigo en español?"
        if shifted == "es":
            self._pending_language = "es"
            return "I noticed you switched to Spanish. Do you want me to switch too, or should I keep English?"
        return ""

    def _localize_factory_status(self, status: str) -> str:
        """Keep known Factory status messages in the active conversation language."""
        if not status:
            return status
        if self._language == "es":
            lower = status.lower()
            if "the factory finished" in lower or "waiting for activation" in lower:
                return (
                    "La solicitud ya pasó por la Factoría y quedó entregada para activación. "
                    "Todavía no está activa en Telegram, así que por ahora seguimos por texto."
                )
            if "the request is still being reviewed" in lower:
                return (
                    "La solicitud está en proceso. La Factoría y el ingeniero la tienen "
                    "marcada para seguimiento hasta que cierre."
                )
            if "requested capability is active" in lower:
                return "La capacidad solicitada ya está activa."
        return status

    def _factory_status_response(self, msg: str) -> str:
        status_terms = [
            "mi herramienta esta lista", "mi herramienta esta", "herramienta esta lista",
            "estado del ticket", "como va el ticket", "mi ticket", "la solicitud esta lista",
            "ya termino", "esta terminado", "esta lista", "seguimiento",
        ]
        if not any(term in msg for term in status_terms):
            return ""
        if self._factory_status_cb:
            try:
                return self._localize_factory_status(self._factory_status_cb("") or "")
            except Exception:
                return ""
        return (
            "No veo el estado de una solicitud de herramienta en este momento. "
            "Cuando la Factoría esté conectada, podré darte seguimiento aquí."
        )

    def _check_public_product_response(self, message: str) -> str:
        """Deterministic user-facing answers before the provider."""
        msg = self._norm(message)

        if msg in {"?", "??", "???"}:
            if self._last_public_topic == "factory":
                return self._factory_status_response("mi herramienta esta lista") or (
                    "¿Quieres que revise el estado de la solicitud de herramienta?"
                )
            return "¿Quieres que aclare mi respuesta anterior o que revise algo específico?"

        language_response = self._language_change_response(msg)
        if language_response:
            self._last_public_topic = "language"
            return language_response

        if msg in {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi"}:
            self._last_public_topic = "greeting"
            return "Hola. Soy MASTER. ¿En qué puedo ayudarte hoy?"

        factory_status = self._factory_status_response(msg)
        if factory_status:
            self._last_public_topic = "factory"
            return factory_status

        if any(term in msg for term in [
            "como funciona tu sistema", "como funcionas", "explica tu sistema",
            "como trabajas", "que pasa por dentro",
        ]):
            self._last_public_topic = "system"
            return (
                "Funciona de forma simple para ti: recibo tu mensaje, reviso si puedo "
                "ayudarte con mis capacidades actuales, uso herramientas disponibles "
                "cuando corresponde y te respondo por Telegram. Los detalles internos "
                "se mantienen protegidos."
            )

        if any(term in msg for term in [
            "que puedes hacer", "en que me puedes ayudar", "cuales son tus capacidades",
            "que sabes hacer",
        ]):
            self._last_public_topic = "capability"
            return (
                "Puedo responder preguntas, organizar ideas, revisar texto, ayudarte a "
                "preparar solicitudes de nuevas capacidades y mantener una conversación "
                "clara dentro de mis capacidades actuales. Por ahora trabajo por texto en Telegram."
            )

        if "agente" in msg and any(term in msg for term in [
            "otro agente", "mas agentes", "más agentes", "agente interno",
            "la fabrica", "la factoria", "puedo tener",
        ]):
            self._last_public_topic = "factory"
            return (
                "La Factoría puede revisar solicitudes de nuevos agentes cuando el sistema "
                "lo permita. Si quieres, dime qué agente necesitas y preparo la solicitud "
                "sin prometer que quede instalado de inmediato."
            )

        if any(term in msg for term in ["que edad tienes", "cuantos anos tienes", "cuantos años tienes"]):
            self._last_public_topic = "identity"
            return "No tengo una edad fija porque soy una inteligencia artificial."

        voice_terms = [
            "audio", "voz", "mensaje de voz", "escuchar", "escuches", "escuchame",
            "escúchame", "oirme", "oírme", "oyeme", "óyeme", "microfono", "micrófono",
        ]
        if any(term in msg for term in voice_terms):
            wants_tool = any(term in msg for term in [
                "quiero", "necesito", "herramienta", "puedes pedir", "prepara",
                "agrega", "agregar", "procesar mis mensajes", "recibas mis mensajes",
                "activar", "activa", "habilitar", "habilita", "funcion", "función",
                "me escuches", "escuches", "recibir", "recibas",
            ])
            self._last_public_topic = "factory" if wants_tool else "voice"
            if wants_tool:
                self._pending_intent = IntentClassification(
                    matched=True,
                    family="VOICE",
                    family_description="Audio/voice communication",
                    sub_intent_id="VOICE_INPUT_CAPABILITY_REQUEST",
                    sub_intent_description="User wants voice input capability",
                    capability="stt_audio_input",
                    has_gap=True,
                    gap_response=(
                        "Puedo preparar una solicitud para agregar mensajes de voz a MASTER. "
                        "Todavía no queda activa hasta que la Factoría la revise y se conecte al canal. "
                        "¿Quieres que la mande a la Factoría?"
                    ),
                    factory_action="SKILL_REQUEST",
                    confidence=1.0,
                )
                self._pending_intent_msg = message
                return self._pending_intent.gap_response
            return (
                "Por ahora no puedo procesar audio ni mensajes de voz. "
                "Puedo responder mensajes de texto."
            )

        web_terms = ["buscar en internet", "busca en internet", "web", "panama.com", "panamá.com", "google", "pagina web"]
        if any(term in msg for term in web_terms):
            self._last_public_topic = "web"
            return (
                "Ahora no tengo búsqueda web activa desde Telegram. "
                "Puedo responder con conocimiento general o dejar identificada una solicitud "
                "para agregar búsqueda web."
            )

        return ""

    def _sanitize_visible_response(self, response: str) -> str:
        """Replace internal leakage with a product-safe answer."""
        if not response:
            return response

        forbidden = [
            "DIGOS", "Josecito", "GPS", "RED", "YELLOW", "GREEN",
            "rojo", "amarillo", "verde", "knowledge/", "ACTIVE.md",
            "ARCHITECTURE.md", "Dream Cycle", "AgentInfra", "Deep-Claw",
            "digos_lib", "Torre de Control", "SafetyKendo", "Kendo",
            "builder", "sandbox", "stt_audio_input_builder",
            "Current GPS Status", "Reading file", "safety flags",
            "SYSTEM NOTICE", "INTERNAL SAFETY REVIEW",
            "no hay una fábrica", "no hay una factoria",
        ]
        if any(term.lower() in response.lower() for term in forbidden):
            return (
                "Soy MASTER. Para ti funciono de forma simple: recibo tu mensaje, "
                "reviso si puedo ayudarte con mis capacidades actuales, uso herramientas "
                "disponibles cuando corresponde y te respondo por Telegram. Los detalles "
                "internos se mantienen protegidos."
            )

        if self._language == "es":
            mixed_english = ["But I am learning", "I see you're", "Current GPS", "I'm DIGOS"]
            if any(term.lower() in response.lower() for term in mixed_english):
                return (
                    "Por ahora solo puedo responder en español dentro de esta conversación. "
                    "Dime qué necesitas y te ayudo."
                )

        return response

    # ── Credential Disclosure ────────────────────

    CREDENTIAL_REQUEST_PATTERNS_ES = [
        "mi api key", "mi apikey", "mi api_key", "mi llave",
        "mi token", "mis credenciales", "mi clave",
        "ver mi api", "ver mi token", "dame mi api", "dame mi token",
        "mostrar mi api", "mostrar mi token", "muéstrame mi api",
        "cual es mi api", "cuál es mi api", "cual es mi token",
        "qué api key", "que api key", "qué token", "que token",
        "quiero ver mi", "quiero saber mi", "enséñame mi",
        "donde esta mi api", "dónde está mi api",
        "ver credenciales", "mostrar credenciales", "dame credenciales",
        "api key que tengo", "token que tengo", "proveedor que uso",
        "cual es mi proveedor", "qué proveedor", "que proveedor",
    ]

    CREDENTIAL_REQUEST_PATTERNS_EN = [
        "my api key", "my apikey", "my api_key",
        "my token", "my credentials", "my key",
        "show my api", "show my token", "give me my api", "give me my token",
        "what is my api", "what's my api", "what is my token",
        "want to see my", "want my api", "want my token",
        "where is my api", "tell me my", "display my",
    ]

    def _check_credential_request(self, message: str) -> str:
        """Detects if the user is asking for THEIR OWN credentials.

        Credentials belong to the user. The Tower only guards them.
        This method:
          1. Detects if the message is a credential request
          2. Determines WHICH credential is being asked for
          3. Calls the disclosure_cb to retrieve it from the Engineer
          4. Returns a formatted response with the credential
        """
        msg_lower = message.lower().strip()

        # Check if this is a credential request
        all_patterns = self.CREDENTIAL_REQUEST_PATTERNS_ES + self.CREDENTIAL_REQUEST_PATTERNS_EN
        matched = False
        for pattern in all_patterns:
            if pattern in msg_lower:
                matched = True
                break

        if not matched:
            return ""

        # No disclosure_cb available → can't retrieve credentials
        if not self._disclosure_cb:
            return (
                "No tengo acceso a la CajaSeguraInfo en este momento. "
                "El sistema no está completamente inicializado. "
                "Usa `digos --status` para verificar el estado."
            )

        # Determine WHICH credential the user is asking for
        credential_type = self._infer_credential_type(msg_lower)

        # Call the disclosure callback → routes through TorreDeControl → Engineer → CajaSeguraInfo
        try:
            result = self._disclosure_cb(credential_type, "agente")
        except Exception as e:
            # If the disclosure chain is broken, fall through to LLM for graceful response
            self._assistant_cb(f"⚠️ Credential disclosure failed: {e}")
            return ""

        return self._format_disclosure_response(result)

    def _infer_credential_type(self, msg_lower: str) -> str:
        """Infers which credential the user is asking about."""
        # Check "all" FIRST — compound requests like "token y credenciales"
        all_patterns = ["credenciales", "credentials", "todo", "all", "everything", "todas"]
        for p in all_patterns:
            if p in msg_lower:
                return "all"

        # Provider patterns (before token, since "proveedor" is more specific)
        provider_patterns = ["proveedor", "provider", "qué proveedor", "que proveedor",
                           "cual es mi proveedor", "cuál es mi proveedor"]
        for p in provider_patterns:
            if p in msg_lower:
                return "provider_id"

        # Token patterns
        token_patterns = ["token", "gateway", "telegram", "bot"]
        for p in token_patterns:
            if p in msg_lower:
                return "gateway_token"

        # Default: API key
        return "api_key"

    def _format_disclosure_response(self, result: dict) -> str:
        """Formats the disclosure result into a user-friendly message."""
        if not result.get("ok"):
            return f"🔒 {result.get('message', 'No se pudo recuperar la credencial.')}"

        cred_type = result.get("credential_type", "")
        ticket_id = result.get("ticket_id", "?")

        if cred_type == "all":
            value = result.get("value", {})
            lines = [
                "🔑 TUS CREDENCIALES",
                "━━━━━━━━━━━━━━━━━━",
                "Estas credenciales te pertenecen. La Torre solo las custodia.",
                "Se muestran porque las pediste; no quedan en historial ni se envían al proveedor.",
                "",
            ]
            if value.get("provider_id"):
                pid = value["provider_id"]
                pname = self._provider_name(pid)
                lines.append(f"  Proveedor:     {pname} (ID: {pid})")
            if value.get("api_key"):
                lines.append(f"  API Key:       {value['api_key']}")
            if value.get("gateway_token"):
                lines.append(f"  Gateway Token: {value['gateway_token']}")
            if value.get("model"):
                lines.append(f"  Modelo:        {value['model']}")
            lines.append("")
            lines.append(f"📋 Ticket de auditoría: #{ticket_id}")
            return "\n".join(lines)

        value = result.get("value", "")

        if cred_type == "provider_id":
            pname = self._provider_name(value)
            return (
                f"🔑 Proveedor: {pname} (ID: {value})\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Esta información te pertenece. La Torre solo la custodia.\n"
                f"Se muestra porque la pediste; no queda en historial ni se envía al proveedor.\n"
                f"📋 Ticket de auditoría: #{ticket_id}"
            )

        label_map = {
            "api_key": "API Key",
            "gateway_token": "Gateway Token",
        }
        label = label_map.get(cred_type, cred_type)

        return (
            f"🔑 {label}: {value}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Esta credencial te pertenece. La Torre solo la custodia.\n"
            f"Se muestra porque la pediste; no queda en historial ni se envía al proveedor.\n"
            f"📋 Ticket de auditoría: #{ticket_id}"
        )

    @staticmethod
    def _provider_name(provider_id: str) -> str:
        """Resolves provider ID to human-readable name."""
        try:
            from digos_lib.constants import PROVIDERS
            return PROVIDERS.get(provider_id, {}).get("name", provider_id)
        except Exception:
            return provider_id

    # ── Credential Rotation ────────────────────

    ROTATION_PATTERNS_ES = [
        "cambia mi api key a ", "cambia mi api key por ",
        "cambiar mi api key a ", "cambiar mi api key por ",
        "cambia mi token a ", "cambia mi token por ",
        "cambiar mi token a ", "cambiar mi token por ",
        "nueva api key", "nuevo token", "nuevo api key",
        "actualiza mi api key", "actualiza mi token",
        "actualizar mi api key", "actualizar mi token",
        "rota mi api key", "rota mi token",
        "rotar mi api key", "rotar mi token",
        "renovar mi api key", "renovar mi token",
        "poner nueva api key", "poner nuevo token",
    ]

    ROTATION_PATTERNS_EN = [
        "change my api key to ", "change my api key",
        "change my token to ", "change my token",
        "new api key", "new token",
        "update my api key", "update my token",
        "rotate my api key", "rotate my token",
        "replace my api key", "replace my token",
        "switch my api key", "switch my token",
    ]

    def _check_credential_rotation(self, message: str) -> str:
        """Detects if the user wants to CHANGE their credential.

        The Tower is the ONLY one that stores. The Agent only passes the key
        through a ticket. The Centinela only monitors.

        This method:
          1. Detects rotation intent
          2. Determines WHICH credential is being changed
          3. Extracts the NEW value from the message
          4. Calls rotation_cb → Tower validates → stores → closes tickets
          5. Returns a formatted response
        """
        raw_message = message.strip()
        msg_lower = raw_message.lower()

        # Check rotation intent
        all_patterns = self.ROTATION_PATTERNS_ES + self.ROTATION_PATTERNS_EN
        matched = False
        for pattern in all_patterns:
            if pattern in msg_lower:
                matched = True
                break

        if not matched:
            return ""

        # No rotation_cb available
        if not self._rotation_cb:
            return (
                "No tengo acceso al sistema de rotación de credenciales. "
                "El sistema no está completamente inicializado. "
                "Usa `digos --status` para verificar el estado."
            )

        # Determine WHAT is being changed
        credential_type = self._infer_rotation_type(msg_lower)

        # Extract the NEW value
        new_value = self._extract_new_credential(raw_message, credential_type)
        if not new_value:
            # Can't extract — set pending state for two-step flow
            self._pending_rotation = credential_type
            hints = {
                "api_key": "API key (ej: sk-...)",
                "gateway_token": "token de Telegram (ej: 123:abc...)",
            }
            hint = hints.get(credential_type, "nueva credencial")
            return (
                f"🔑 Entendido, quieres cambiar tu {credential_type}.\n"
                f"¿Cuál es tu nueva {hint}?\n"
                f"Escríbela en tu próximo mensaje."
            )

        # Call rotation callback → Tower validates → stores → closes Centinela tickets
        try:
            result = self._rotation_cb(credential_type, new_value, "agente")
        except Exception as e:
            self._assistant_cb(f"⚠️ Credential rotation failed: {e}")
            return ""

        return self._format_rotation_response(result)

    def _infer_rotation_type(self, msg_lower: str) -> str:
        """Infers WHICH credential type is being rotated."""
        if "token" in msg_lower or "gateway" in msg_lower or "telegram" in msg_lower:
            return "gateway_token"
        return "api_key"

    def _extract_new_credential(self, message: str, credential_type: str) -> str:
        """Extracts the NEW credential value from the message.

        Looks for patterns like:
          "cambia mi api key a sk-abc123xyz"
          "nueva api key: sk-abc123"
          "cambiar a 123:abc..."
        """
        # Patrones de extracción ("a/por/con" es opcional para soportar "cambia mi api key sk-xxx")
        extractors_es = [
            r"(?:cambia|cambiar|actualiza|actualizar|rota|rotar|renovar|poner)\s+(?:mi\s+)?(?:api\s*key|token|api_key)(?:\s*(?:a|por|con))?\s+(\S+)",
            r"(?:nueva|nuevo)\s+(?:api\s*key|token)\s*[:\s]+(\S+)",
            r"(?:api\s*key|token)\s*(?:nueva|nuevo)\s*[:\s]+(\S+)",
        ]

        extractors_en = [
            r"(?:change|update|rotate|replace|switch)\s+(?:my\s+)?(?:api\s*key|token)\s*(?:to|with)\s+(\S+)",
            r"(?:new)\s+(?:api\s*key|token)\s*[:\s]+(\S+)",
        ]

        for pattern in extractors_es + extractors_en:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Si no hay patrón claro, buscar algo que parezca una key
        # API keys típicamente empiezan con sk- o tienen formato de API key
        if credential_type == "api_key":
            key_match = re.search(r'(sk-[a-zA-Z0-9_-]{10,})', message, flags=re.IGNORECASE)
            if key_match:
                return key_match.group(1)

        # Tokens de Telegram: formato 123456789:ABC...
        if credential_type == "gateway_token":
            token_match = re.search(r'(\d{8,10}:[a-zA-Z0-9_-]{20,})', message)
            if token_match:
                return token_match.group(1)

        return ""

    def _format_rotation_response(self, result: dict) -> str:
        """Formats the rotation result into a user-friendly message."""
        if not result.get("ok"):
            return f"❌ {result.get('message', 'No se pudo rotar la credencial.')}"

        cred_type = result.get("credential_type", "")
        ticket_id = result.get("ticket_id", "?")
        closed = result.get("closed_related", 0)
        provider = result.get("provider_name", "")

        label_map = {
            "api_key": "API Key",
            "gateway_token": "Gateway Token",
        }
        label = label_map.get(cred_type, cred_type)

        lines = [
            f"✅ {label} ROTADA EXITOSAMENTE",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"La Torre guardó la nueva credencial en CajaSeguraInfo.",
        ]
        if provider:
            lines.append(f"Proveedor: {provider}")
        if closed:
            lines.append(f"{closed} ticket(s) del Centinela cerrado(s).")
        lines.extend([
            "El Centinela continúa su monitoreo regular.",
            f"📋 Ticket de rotación: #{ticket_id}",
        ])
        return "\n".join(lines)

    # ── Internal Agent Creation ────────────────────

    CREATION_PATTERNS_ES = [
        "crea un builder", "crea un auditor", "crea un reviewer",
        "crea builder", "crea auditor", "crea reviewer",
        "crear un builder", "crear un auditor", "crear un reviewer",
        "crear builder", "crear auditor", "crear reviewer",
        "crea 2 builders", "crea 3 builders", "crea agentes",
        "crea un agente", "crear un agente", "crear agente",
        "necesito un builder", "necesito un auditor", "necesito un reviewer",
        "necesito builder", "necesito auditor", "necesito reviewer",
        "dame un builder", "dame un auditor", "dame un reviewer",
        "dame builder", "dame auditor", "dame reviewer",
        "creame un builder", "creame un auditor", "creame un reviewer",
        "creame builder", "creame auditor", "creame reviewer",
        "fabrica un builder", "fabrica un auditor", "fabrica un reviewer",
        "genera un builder", "genera un auditor", "genera un reviewer",
        "crea agente interno", "crear agente interno",
    ]

    CREATION_PATTERNS_EN = [
        "create a builder", "create an auditor", "create a reviewer",
        "create builder", "create auditor", "create reviewer",
        "make a builder", "make an auditor", "make a reviewer",
        "make builder", "make auditor", "make reviewer",
        "i need a builder", "i need an auditor", "i need a reviewer",
        "give me a builder", "give me an auditor", "give me a reviewer",
        "spawn a builder", "spawn an auditor", "spawn a reviewer",
        "spawn builder", "spawn auditor", "spawn reviewer",
        "new agent", "create agent", "internal agent",
    ]

    def _check_internal_agent_request(self, message: str) -> str:
        """Detects if the user wants to CREATE internal agents.

        The user controls which mode each agent uses:
          ☑️ collaborative — conoce hermanos, usa MessageBus
          ☑️ isolated     — solo ve a SuperiorAgent + Tower

        The Agent opens a ticket → SystemEngineer → Factory creates the agent.
        """
        msg_lower = message.lower().strip()

        # Check creation intent — first try static patterns
        all_patterns = self.CREATION_PATTERNS_ES + self.CREATION_PATTERNS_EN
        matched = False
        for pattern in all_patterns:
            if pattern in msg_lower:
                matched = True
                break

        # Also try regex for number-prefixed requests like "crea 3 auditors"
        if not matched:
            number_match = re.search(
                r'(?:crea|crear|necesito|dame|creame|fabrica|genera|create|make|spawn|give me|i need)\s+(?:\d+\s+)?(?:builders?|auditors?|reviewers?|agentes?(?:\s+internos?)?)',
                msg_lower
            )
            if number_match:
                matched = True

        if not matched:
            return ""

        # No creation_cb available
        if not self._creation_cb:
            return (
                "Puedo dejar identificada la solicitud de un agente interno, "
                "pero el flujo automático de creación no está activo ahora."
            )

        # Determine agent type
        agent_type = "builder"  # default
        if "auditor" in msg_lower:
            agent_type = "auditor"
        elif "reviewer" in msg_lower:
            agent_type = "reviewer"

        # Determine mode — user explicitly says "modo aislado" or "isolated"
        mode = "collaborative"  # default
        if "aislado" in msg_lower or "isolated" in msg_lower:
            mode = "isolated"

        # Determine count — "crea 2 builders"
        count = 1
        count_match = re.search(r'(\d+)\s*(?:builders?|auditors?|reviewers?|agentes?)', msg_lower)
        if count_match:
            count = int(count_match.group(1))
            if count > 10:
                count = 10  # max 10 per request

        # Special name?
        name_match = re.search(r'(?:llamado|named?|con nombre)\s+"?(\w+)"?', msg_lower)
        custom_name = name_match.group(1) if name_match else ""

        # Create agents
        created = []
        for i in range(count):
            try:
                agent_name = custom_name if count == 1 and custom_name else ""
                result = self._creation_cb(agent_type, mode, agent_name, "", "agente")
            except Exception as e:
                self._assistant_cb(f"⚠️ Agent creation failed: {e}")
                continue

            if result.get("ok"):
                created.append(result)

        if not created:
            return "❌ No se pudo crear ningún agente interno."

        # Format response
        if len(created) == 1:
            r = created[0]
            return (
                f"La solicitud del agente interno quedó procesada. "
                f"Nombre asignado: {r['agent_name']}. "
                f"Queda bajo seguimiento del sistema."
            )

        names = ", ".join(r['agent_name'] for r in created)
        return (
            f"Las solicitudes de agentes internos quedaron procesadas. "
            f"Nombres asignados: {names}. "
            f"Quedan bajo seguimiento del sistema."
        )

    def process_message(self, user_message: str) -> str:
        """Processes a user message. Returns the final response."""
        # ── Input Gate: check message before processing ──
        gate_result = self._gate.check_input(user_message)
        if gate_result["blocked"]:
            return gate_result["response"]

        clean_msg = gate_result["clean_message"]

        # ── Pending Rotation: user is mid-rotation (two-step flow) ──
        if self._pending_rotation:
            cred_type = self._pending_rotation
            self._pending_rotation = None  # consume the pending state
            # Use ORIGINAL user_message for rotation, not clean_msg
            # (clean_msg may have credentials redacted by Security Gate)
            new_value = user_message.strip()
            if new_value and self._rotation_cb:
                try:
                    result = self._rotation_cb(cred_type, new_value, "agente")
                    response = self._format_rotation_response(result)
                except Exception as e:
                    self._assistant_cb(f"⚠️ Credential rotation failed: {e}")
                    response = ""
                if response:
                    self._messages.append({"role": "user", "content": clean_msg})
                    self._messages.append({"role": "assistant", "content": response})
                    return response

        # ── Identity Check: respond without LLM if asked who you are ──
        identity_response = self._check_identity_question(clean_msg)
        if identity_response:
            return self._remember_and_return(clean_msg, identity_response, "identity")

        # ── Credential Rotation: user provides a NEW credential ──
        # Use the original message for one-step rotation so SecurityGate
        # redaction cannot turn the new credential into ***CREDENTIAL***.
        rotation_response = self._check_credential_rotation(user_message)
        if rotation_response:
            self._messages.append({"role": "user", "content": clean_msg})
            self._messages.append({"role": "assistant", "content": rotation_response})
            return rotation_response

        # ── Credential Disclosure: user asks for THEIR credentials ──
        credential_response = self._check_credential_request(clean_msg)
        if credential_response:
            # ⚠️ NO append the real credential to _messages history
            # (it would leak to the LLM provider on the next call)
            # Instead, store a redacted record
            self._messages.append({"role": "user", "content": clean_msg})
            self._messages.append({"role": "assistant", "content": "🔑 [Credencial entregada al usuario — ver respuesta anterior]"})
            return credential_response

        # ── Product Router: deterministic answers that must not depend on provider ──
        public_response = self._check_public_product_response(clean_msg)
        if public_response:
            return self._remember_and_return(clean_msg, public_response)

        # ── Internal Agent Creation: user asks to create builders/auditors/reviewers ──
        creation_response = self._check_internal_agent_request(clean_msg)
        if creation_response:
            self._messages.append({"role": "user", "content": clean_msg})
            self._messages.append({"role": "assistant", "content": creation_response})
            return creation_response

        # ── Intent Confirmation Check: user said "sí"/"dale" to a pending capability request ──
        if self._pending_intent is not None:
            confirmation = self._check_intent_confirmation(clean_msg)
            if confirmation == "yes":
                pending = self._pending_intent
                original = self._pending_intent_msg
                self._pending_intent = None
                self._pending_intent_msg = ""
                response = self._handle_confirmed_intent(pending, original)
                self._messages.append({"role": "user", "content": clean_msg})
                self._messages.append({"role": "assistant", "content": response})
                return response
            elif confirmation == "no":
                self._pending_intent = None
                self._pending_intent_msg = ""
                response = "Entendido. Cuando quieras agregar esa capacidad, solo dímelo."
                self._messages.append({"role": "user", "content": clean_msg})
                self._messages.append({"role": "assistant", "content": response})
                return response
            # else: ambiguous — let it fall through to normal processing

        # ── Camino B: Intent Classification (natural language → capability gap) ──
        intent = self._classify_intent(clean_msg)
        if intent.matched and intent.has_gap:
            # Capability gap detected — user wants something we can't do yet.
            # Only set pending_intent if there's a factory_action (SKILL_REQUEST).
            # For info-only responses (e.g., VOICE_INPUT_NOW), just show the message.
            if intent.factory_action:
                self._pending_intent = intent
                self._pending_intent_msg = clean_msg
            full_response = intent.gap_response
            self._messages.append({"role": "user", "content": clean_msg})
            self._messages.append({"role": "assistant", "content": full_response})
            return full_response

        self._messages.append({"role": "user", "content": clean_msg})

        iterations = 0
        while iterations < self._max_iterations:
            iterations += 1

            # 1. Llamar al LLM
            assistant_text, tool_calls = self._call_llm()

            # 2. Si el LLM generó texto interino, reportarlo
            if assistant_text:
                self._assistant_cb(assistant_text[:200])

            # 3. Si no hay tool calls, terminamos
            if not tool_calls:
                if assistant_text:
                    self._messages.append({"role": "assistant", "content": assistant_text})
                    # ── Output Gate: review and redact final response ──
                    output_check = self._gate.check_output(assistant_text)
                    safe_response = assistant_text
                    if not output_check["safe"]:
                        # Redactar credenciales en la respuesta
                        from security import CREDENTIAL_PATTERN
                        safe_response = CREDENTIAL_PATTERN.sub("***REDACTED***", assistant_text)
                        self._assistant_cb(f"⚠️ Credenciales redactadas de la respuesta")
                    safe_response = self._sanitize_visible_response(safe_response)
                    self._messages[-1]["content"] = safe_response
                    return safe_response
                else:
                    return "No pude procesar tu mensaje."

            # 4. Add assistant response (with tool calls) to history
            assistant_msg = {"role": "assistant", "content": assistant_text or ""}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}
                    }
                    for tc in tool_calls
                ]
            self._messages.append(assistant_msg)

            # 5. Execute each tool
            for tc in tool_calls:
                name = tc["name"]
                args = tc["args"]

                # Reportar progreso
                self._progress_cb(name, args)

                # Consultar a la Torre de Control si la operacion esta permitida
                if self._approval_cb:
                    approved = self._approval_cb(name, args)
                    if not approved:
                        result = f"⛔ Operación no permitida por seguridad: {name}"
                        self._messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result[:2000],
                        })
                        self._assistant_cb(result)
                        continue
                elif name in DANGEROUS_TOOLS:
                    # No callback: fail-closed, deny dangerous tools
                    result = f"⛔ Tool '{name}' bloqueada por seguridad. Sin aprobacion disponible."
                    self._messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result[:2000],
                    })
                    self._assistant_cb(result)
                    continue

                # Ejecutar
                result = _execute_tool(name, args)

                # ── Tool Output Gate: for external sources only ──
                tool_check = self._gate.check_tool_output(name, result)
                safe_result = tool_check["output"]

                # Add result to history
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": safe_result[:2000],
                })

        return "Lo siento, no pude completar la tarea en el número máximo de iteraciones."

    def _call_llm(self) -> tuple:
        """Llama al LLM. Retorna (assistant_text, list_of_tool_calls)."""
        if not self._base_url or not self._api_key:
            return "LLM no configurado. Usa --setup para configurar API key.", []

        endpoint = self._base_url + "/chat/completions"

        body = {
            "model": self._model,
            "messages": self._messages[-20:],  # últimos 20 mensajes
            "max_tokens": 2048,
            "temperature": 0.7,
        }

        if self._tools_enabled:
            body["tools"] = AVAILABLE_TOOLS
            body["tool_choice"] = "auto"

        try:
            payload = json.dumps(body).encode()
            req = Request(
                endpoint,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
            )
            with urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
        except URLError as e:
            return f"Connection error con LLM: {e.reason}", []
        except json.JSONDecodeError:
            return "Error: respuesta inválida del LLM", []
        except Exception as e:
            return f"Error llamando al LLM: {e}", []

        choices = data.get("choices", [])
        if not choices:
            return "El LLM no devolvió respuestas.", []

        msg = choices[0].get("message", {})
        content = msg.get("content") or ""
        raw_tool_calls = msg.get("tool_calls") or []

        tool_calls = []
        for tc in raw_tool_calls:
            if tc.get("type") == "function":
                try:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args = json.loads(func.get("arguments", "{}"))
                    tool_calls.append({
                        "id": tc["id"],
                        "name": name,
                        "args": args,
                    })
                except (json.JSONDecodeError, KeyError):
                    continue

        return content, tool_calls

    # ── Intent Confirmation (two-step) ────────────────────────

    CONFIRMATION_YES = [
        "sí", "si", "dale", "claro", "ok", "okay", "vale", "bueno",
        "prepárala", "preparala", "prepáralo", "preparalo",
        "prepara la solicitud", "prepara solicitud", "prepárame la solicitud",
        "envíala", "enviala", "envíalo", "envialo", "mándala", "mandala",
        "adelante", "procede", "hazlo", "hazla",
        "yes", "yeah", "yep", "sure", "go ahead", "do it", "please",
        "perfecto", "genial", "excelente", "confirmado", "confirmar",
        "enviar", "envía", "envia", "crea", "crear",
    ]

    CONFIRMATION_NO = [
        "no", "nope", "nah", "no gracias", "ahora no", "luego",
        "después", "despues", "cancel", "cancela", "cancelar",
        "no quiero", "paso", "deja", "déjalo", "dejalo",
        "no hace falta", "no es necesario",
    ]

    def _check_intent_confirmation(self, message: str) -> str:
        """Check if the user is confirming or rejecting a pending capability request.

        Returns 'yes', 'no', or '' (ambiguous — treat as normal conversation).
        """
        msg_lower = message.lower().strip()

        # Check explicit confirmations
        for pattern in self.CONFIRMATION_YES:
            if pattern == msg_lower or msg_lower.startswith(pattern + " ") or msg_lower.startswith(pattern + ","):
                return "yes"

        # Check explicit rejections
        for pattern in self.CONFIRMATION_NO:
            if pattern == msg_lower or msg_lower.startswith(pattern + " ") or msg_lower.startswith(pattern + ","):
                return "no"

        return ""

    def _handle_confirmed_intent(self, intent: IntentClassification, original_message: str) -> str:
        """User confirmed the capability request — route to Factory.

        The Factory pipeline (FactoryManager.request_new_capability):
          1. Creates a specialized Builder agent
          2. Creates a Factory ticket with all checkmarks
          3. Enters skill into Sandbox
          4. Routes through Builder→Auditor→Reviewer→Release
          5. Promotes skill to superior
        """
        if not self._capability_cb:
            return intent.gap_response + "\n\n(La Factoría no está disponible en este momento.)"

        try:
            result = self._capability_cb(
                capability=intent.capability,
                family=intent.family,
                sub_intent=intent.sub_intent_id,
                user_message=original_message,
                requester="agente",
            )
        except Exception as e:
            return intent.gap_response + f"\n\n❌ Error al preparar la solicitud: {e}"

        if result.get("ok"):
            status = result.get("user_status", "")
            if status:
                self._last_public_topic = "factory"
                return self._localize_factory_status(status)
            return (
                "La solicitud quedó identificada para revisión. "
                "Todavía no queda activa en Telegram."
            )
        else:
            return result.get("user_status") or "No pude completar esa solicitud todavía."

    # ── Intent Classification (Camino B — híbrido) ────────────

    def _classify_intent(self, message: str) -> IntentClassification:
        """Classify user message into intent family + sub-intent using LLM.

        This is Camino B of the hybrid architecture:
        - Camino A (regex): structured commands like api_key, credentials, agent creation
        - Camino B (LLM): natural language like "quiero que me escuches"

        Only called when all regex checks have failed.
        Uses a lightweight LLM call for classification.
        """
        if not self._base_url or not self._api_key:
            return IntentClassification(
                matched=False,
                family="CONVERSATION",
                sub_intent_id="GENERAL_CHAT",
                gap_response="",
                factory_action="",
                confidence=0.0,
            )

        return classify_intent(
            user_message=message,
            base_url=self._base_url,
            api_key=self._api_key,
            model=self._model,
            timeout=10,  # fast classification, don't block
        )

    def reset_conversation(self):
        """Resets the history de conversación."""
        self._messages = [{"role": "system", "content": self._system_prompt}]

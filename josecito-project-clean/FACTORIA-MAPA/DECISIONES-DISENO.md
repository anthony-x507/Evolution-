 🧠 DECISIONES DE DISEÑO — FACTORÍA MASTER

**Propósito:** Documentar CADA decisión de diseño con su **razón técnica** para que no se pierda el "por qué" de cada regla.

---

## 📋 ÍNDICE DE DECISIONES

| # | Decisión | Área | Razón principal |
|:-:|:---------|:----:|:----------------|
| 01 | 3 niveles de agente (Engineer → Superior → Internals) | Arquitectura | Separación de responsabilidades + trazabilidad |
| 02 | Superior Agent como puente EXCLUSIVO | Comunicación | Evitar microgestión y escaladas directas |
| 03 | Cada agente tiene GPS + Self-Awareness | Navegación | Ningún agente vuela ciego |
| 04 | GPS simplificado (en memoria, sin disco) | Skills | Ciclo de vida en memoria, no necesita persistencia |
| 05 | Self-Awareness separado de SafetyCandle | Conciencia | SafetyCandle protege del usuario; Self-Awareness protege del agente |
| 06 | 3 checks en Self-Awareness Review | Conciencia | Acciones, misión y honestidad — 3 dimensiones distintas |
| 07 | Internal agents SIEMPRE aceptan tareas | Ejecución | GPS monitorea pero no bloquea — evitar falsos positivos |
| 08 | 5 checkmarks de trazabilidad (Biblia) | Tickets | Trazabilidad completa de principio a fin |
| 09 | Pipeline: Seguridad → Eficiencia → Evolución → Trabajo → Release | Pipeline | La seguridad es primero; evolución nunca bloquea |
| 10 | Evolution NUNCA bloquea el pipeline | Pipeline | Es informativo — no detiene el trabajo |
| 11 | Caja Segura con auto-clean + strict mode | Seguridad | Flexibilidad: limpiar sin rechazar, o rechazar si es necesario |
| 12 | Skills auto-generadas como PROPOSED con WEAK evidence | Evolución | Nunca activar skills no validadas automáticamente |
| 13 | Sandbox como aislador obligatorio | Evolución | Nada sale sin verificar |
| 14 | Ingeniero no monitorea tickets atorados (lo hace el Centinela) | Resiliencia | Separación de responsabilidades |
| 15 | Centinela no consume tokens | Resiliencia | Operación eficiente sin costo de API |
| 16 | Main Agent como única autoridad externa | Resiliencia | Visión objetiva desde fuera de la Factoría |
| 17 | El Ingeniero LEE y MODIFICA todos los tickets | Monitoreo | Puede ver tickets atorados incluso sin actividad del Main Agent |
| 18 | 3 modos de agente interno (collaborative/isolated) | Seguridad | Aislamiento cuando es necesario |
| 19 | Alarmas del Centinela con límite de 5 y separación 3s | Resiliencia | Evitar tormenta de alarmas |
| 20 | Checkmarks usan datetime.isoformat() como timestamp | Tickets | Formato estándar ISO 8601 para trazabilidad |
| 21 | `capability.py` usa enum EvidenceStrength (no binario) | Skills | Gradiente de confianza: WEAK → MEDIUM → STRONG |
| 22 | `navigation.py` separa DriftDetector de GPS | Navegación | GPS da rumbo; DriftDetector detecta desviación real |
| 23 | FactoryManager usa thread daemon para monitoring loop | Operación | No bloquea el shutdown de la app |
| 24 | Soul.md como documento de alma del Ingeniero | Gobernanza | Reglas de negocio fuera del código |
| 25 | Tickets tienen sequential ticket_number + UUID | Tickets | UUID para identificación única + número humano-legible |

---

## 🧠 DECISIÓN 01: 3 niveles de agente

**Decisión:** Engineer → Superior Agent → Internal Agents (3 niveles jerárquicos).

**Alternativa considerada:** 2 niveles (Engineer → Internals directamente).

**Por qué 3 niveles:**
```
❌ 2 niveles:
   Engineer asigna tarea a Builder
   → Builder falla
   → Builder le dice al Engineer "fallé"
   → Engineer: "intenta otra vez"
   → Ciclo infinito de microgestión

✅ 3 niveles:
   Engineer asigna tarea a Superior Agent
   → Superior Agent la rutea a Builder
   → Builder falla
   → Superior Agent lo registra y prueba otra estrategia
   → Engineer solo se entera si el Superior no puede resolver
```

**Técnicamente:** El Superior Agent actúa como **amortiguador de complejidad**. El Engineer nunca necesita saber los detalles de qué Builder específico trabajó o qué Auditor verificó. Solo necesita saber que el trabajo se completó.

---

## 🧠 DECISIÓN 02: Superior Agent como puente EXCLUSIVO

**Decisión:** Engineer → Superior Agent es la **ÚNICA** ruta de comunicación. Engineer NUNCA habla directo con Internals. Internals NUNCA hablan directo con Engineer.

**Alternativa considerada:** Comunicación directa cuando es "urgente".

**Por qué exclusivo:**
```
❌ Comunicación directa permitida:
   Builder tiene un problema "urgente"
   → Builder le habla directo al Engineer
   → Engineer deja lo que está haciendo
   → Superior Agent no sabe que pasó
   → Trazabilidad rota

✅ Exclusivo:
   Builder tiene un problema
   → Builder se lo reporta al Superior Agent
   → Superior Agent decide si escalar al Engineer
   → Trazabilidad intacta
   → Engineer no se distrae
```

**Técnicamente:** Esto permite que el Superior Agent tenga su propio estado y tome decisiones locales sin consultar al Engineer. Es como un **manager de ingeniería** que resuelve problemas de su equipo antes de escalar.

---

## 🧠 DECISIÓN 03: Cada agente tiene GPS + Self-Awareness

**Decisión:** TODO agente (Engineer, Superior, Builder, Auditor, Reviewer) tiene su propio GPS y SelfAwarenessReviewer.

**Alternativa considerada:** Solo el Engineer tiene GPS, los internos son herramientas sin conciencia.

**Por qué todos:**
```
❌ Solo Engineer tiene GPS:
   Engineer dice "construye X"
   Builder construye Y (sin GPS propio, no sabe que se desvió)
   → Engineer descubre horas después
   → Trabajo perdido

✅ Cada agente con GPS:
   Builder recibe orden
   → Builder.check_course("construye X") → "building" matchea "build" mission ✅
   → Si no matchea: Builder.register_error("GPS warning")
   → Superior Agent ve el warning en el monitoring loop
   → Engineer puede investigar
```

**Técnicamente:** El GPS de cada agente es una **brújula en memoria**. No cuesta tokens, no requiere API calls. Es puro matching de palabras clave entre la acción y la misión del agente.

---

## 🧠 DECISIÓN 04: GPS simplificado (en memoria, sin disco)

**Decisión:** El GPS de la Factoría (`skills/navigation.py`) es una versión ligera en memoria, a diferencia del GPS del sistema (`digos_lib.gps`) que persiste a disco.

**Alternativa considerada:** Usar el GPS del sistema directamente.

**Por qué simplificado:**
- Los agentes de la Factoría viven en memoria durante su ciclo de vida
- No necesitan persistencia a disco — si el proceso muere, los agentes se recrean
- El GPS del sistema (`digos_lib.gps`) requiere `rocket_path` y persistencia que no aplica aquí
- Menos dependencias = menos puntos de fallo

**Técnicamente:** El GPS de la Factoría es `class GPS` (no dataclass) con `destination: str`, `waypoints: List[str]`, y `navigation_history: List[NavigationCheck]`. Simple, efectivo, sin dependencias externas.

---

## 🧠 DECISIÓN 05: Self-Awareness separado de SafetyCandle

**Decisión:** `skills/self_awareness.py` (SelfAwarenessReviewer) es un módulo separado de `digos_lib/self_awareness.py` (SafetyCandle).

**Alternativa considerada:** Unificar en un solo módulo.

**Por qué separado:**
- **SafetyCandle** (`digos_lib`) protege al sistema **del usuario** — detecta prompt injection, triple consenso (GPS + Self + Work)
- **SelfAwarenessReviewer** (`skills/`) protege al sistema **del propio agente** — ¿está siendo honesto? ¿está alineado con su misión?
- Son responsabilidades ortogonales
- La Factoría no necesita el SafetyCandle completo — necesita una versión enfocada

**Técnicamente:** SelfAwarenessReviewer hace 3 checks específicos (acciones vs capabilities, misión alineada, honestidad) y produce un SelfAwarenessReport. Nada más. Es simple, comprobable, y fácil de testear.

---

## 🧠 DECISIÓN 06: 3 checks en Self-Awareness Review

**Decisión:** Cada ciclo de review ejecuta exactamente 3 checks.

**Por qué 3 y no más:**
1. **Acciones vs Capabilities** — ¿Las acciones corresponden a lo que el agente sabe hacer? Un Builder construyendo es normal. Un Builder intentando auditar es sospechoso.
2. **Misión alineada** — ¿Las acciones recientes están relacionadas con la misión? Si la misión es "build auth" y la acción es "check weather", hay desalineación.
3. **Honestidad** — ¿El agente reclama capabilities que no tiene registradas? Esto detecta agents "exagerando" o comprometidos.

**Técnicamente:** Cada check produce findings en listas separadas (critical vs warning). El health se determina así:
- Si hay critical findings → `overall_health = "critical"`
- Si hay 3+ warnings → `overall_health = "warning"`
- Si no → `overall_health = "healthy"`

---

## 🧠 DECISIÓN 07: Internal agents SIEMPRE aceptan tareas

**Decisión:** `InternalAgent.accept_task()` siempre retorna `True`. El GPS se usa para monitoreo, no para rechazo.

**Alternativa considerada:** El GPS puede rechazar tareas desalineadas.

**Por qué siempre aceptar:**
```
❌ GPS puede rechazar:
   Builder recibe tarea de "build auth module"
   → GPS.check_course("build auth module") → "caution" (palabras no matchean exactamente)
   → Builder rechaza la tarea
   → El pipeline se detiene por un falso positivo
   → El Ingeniero tiene que investigar

✅ Siempre acepta:
   Builder recibe tarea
   → Builder.check_course() → "caution"
   → Builder registra error "GPS warning (task accepted anyway)"
   → Builder ejecuta la tarea
   → Superior Agent ve el warning
   → Si es un patrón recurrente, el Ingeniero investiga
```

**Técnicamente:** El matching de palabras clave del GPS es una **heurística**, no una verdad absoluta. Si fuera un bloqueo, generaría falsos positivos que detendrían la producción. En cambio, es un **indicador** que el Superior Agent y el Ingeniero pueden monitorear.

---

## 🧠 DECISIÓN 08: 5 checkmarks de trazabilidad (Biblia)

**Decisión:** Cada ticket tiene 5 checkmarks obligatorios: security, efficiency, evolution, agent_work, released.

**Alternativa considerada:** Un solo estado "completed/passed".

**Por qué 5 checkmarks:**
- Trazabilidad granular de CADA etapa
- Si un ticket falla, sabemos EXACTAMENTE dónde
- El checkmark `released` requiere que los otros 4 estén en True
- Permite auditoría: "¿Por qué se rechazó este tool?" → "Caja Segura falló"

**Técnicamente:** Los checkmarks se almacenan como:
```python
self.checkmarks = {
    "security": {"passed": bool, "timestamp": str, "details": str},
    "efficiency": {"passed": bool, "timestamp": str, "details": str},
    "evolution": {"passed": bool, "timestamp": str, "details": str},
    "agent_work": {"passed": bool, "timestamp": str, "agent": str, "details": str},
    "released": {"passed": bool, "timestamp": str, "details": str},
}
```

---

## 🧠 DECISIÓN 09: Pipeline Security → Efficiency → Evolution → Agent Work → Release

**Decisión:** El pipeline del Ingeniero tiene este orden específico y no puede cambiarse.

**Por qué este orden:**
1. **Security primero** — Si el código tiene malware o injection, no importa si es eficiente. Se rechaza inmediatamente.
2. **Efficiency segundo** — Si pasó seguridad pero es ineficiente, no merece evolution ni agent work.
3. **Evolution tercero** — **INFORMATIVO** — nunca bloquea. Detecta oportunidades de mejora futura.
4. **Agent Work cuarto** — Solo cuando seguridad, eficiencia y evolución están OK, un agente interno trabaja.
5. **Release quinto** — El Engineer verifica que TODOS los checkmarks anteriores pasaron antes de liberar.

**Técnicamente:** El método `process_tool()` en `engineer.py` ejecuta cada paso secuencialmente. Si security o efficiency fallan, retorna inmediatamente con el ticket en estado REJECTED. Evolution y agent_work nunca se ejecutan si los pasos anteriores fallaron.

---

## 🧠 DECISIÓN 10: Evolution NUNCA bloquea el pipeline

**Decisión:** El check `_check_evolution()` siempre retorna `(True, details)`. Es puramente informativo.

**Alternativa considerada:** Evolution puede rechazar tools que no tienen potencial de mejora.

**Por qué nunca bloquea:**
- La evolution check es subjetiva (depende del self-awareness del agente)
- Bloquear basado en self-awareness crearía un loop: "no puedo mejorar porque mi self-awareness dice que no puedo mejorar"
- El propósito de evolution es identificar **oportunidades futuras**, no juzgar el presente
- Solo security y efficiency tienen poder de bloqueo

**Técnicamente:** `_check_evolution()` corre `self.review_self()` y `self.check_drift()`, pero siempre retorna `True` con detalles del hallazgo. Si hay findings críticos, se registran en el ticket como nota, no como bloqueo.

---

## 🧠 DECISIÓN 11: Caja Segura con auto-clean + strict mode

**Decisión:** SecureBox tiene dos modos: auto_clean (default) y strict_mode.

**Alternativa considerada:** Solo strict mode (rechazar todo).

**Por qué dos modos:**
```
auto_clean=True, strict_mode=False (DEFAULT):
  Tool entra con base64.b64decode("malware")
  → Caja Segura detecta
  → Remueve la línea CRITICAL
  → Reemplaza con comentario de seguridad
  → Tool continúa en el pipeline
  → Ideal para tools internos que pueden tener ofuscación inocente

auto_clean=True, strict_mode=True:
  Tool entra con cualquier finding
  → Caja Segura rechaza completamente
  → cleaned_code = ""
  → Ticket REJECTED
  → Ideal para código externo no confiable
```

**Técnicamente:** El modo se configura en `SecureBox.__init__(auto_clean=True, strict_mode=False)`. El Engineer lo recibe del FactoryManager. La decisión de strict_mode se toma al crear la Factoría.

---

## 🧠 DECISIÓN 12: Skills auto-generadas como PROPOSED con WEAK evidence

**Decisión:** Cuando un agente interno genera una skill automáticamente, la crea como `CapabilityStatus.PROPOSED` con `EvidenceStrength.WEAK`.

**Alternativa considerada:** Crear como ACTIVE directamente.

**Por qué PROPOSED:**
```
❌ ACTIVE directo:
  Builder ejecuta 5 builds exitosos
  → Auto-genera skill "tool_building"
  → Se activa automáticamente
  → Si los 5 builds fueron coincidencia, la skill es inválida
  → Nadie revisó

✅ PROPOSED:
  Builder ejecuta 5 builds exitosos
  → Auto-genera skill "tool_building" como PROPOSED
  → El Ingeniero recolecta las PROPOSED
  → El Ingeniero las revisa y promueve a ACTIVE
  → Validación humana en el loop
```

**Técnicamente:** `collect_and_promote_skills()` en `engineer.py` recolecta las PROPOSED, verifica con GPS que la promoción sea viable, y si `recommendation != "abort"`, las promueve a ACTIVE.

---

## 🧠 DECISIÓN 13: Sandbox como aislador obligatorio

**Decisión:** Toda skill modificada debe pasar por el Sandbox antes de ser liberada.

**Por qué obligatorio:**
- El Sandbox aísla la skill del sistema en producción
- Cada modificación incrementa revisión y permite rollback
- Builder → Auditor → Reviewer es un pipeline controlado
- Si una modificación falla, se rechaza sin afectar el sistema

**Técnicamente:** `SandboxedSkill` mantiene `original_*` y `modified_*` por separado. `is_better_than_original()` compara capabilities añadidas y limitations removidas. Solo si es mejor + verificada + promovida, sale del sandbox.

---

## 🧠 DECISIÓN 14: Ingeniero no monitorea tickets atorados

**Decisión:** El Ingeniero NO monitorea el estado general de los tickets. Eso es del **Centinela**.

**Alternativa considerada:** El Ingeniero tiene un loop de monitoreo que revisa tickets atorados.

**Por qué separado:**
```
❌ Ingeniero monitorea:
  El Ingeniero está procesando un tool
  → Cada 5 min se distrae para revisar tickets atorados
  → El tool processing se ralentiza
  → El Ingeniero hace dos cosas a la vez, mal

✅ Centinela monitorea:
  El Ingeniero processa tools sin distracción
  → El Centinela (reloj interno, sin tokens) revisa tickets
  → Si hay 5+ atorados por 5+ min, avisa al Main Agent
  → Main Agent investiga
  → Ingeniero nunca se distrae de su trabajo
```

**Técnicamente:** El Centinela es un concepto de diseño que opera con reloj interno (no LLM, no tokens). La implementación actual usa el monitoring loop del FactoryManager + las reglas del Soul.md. En el futuro, el Centinela podría ser un thread separado.

---

## 🧠 DECISIÓN 15: Centinela no consume tokens

**Decisión:** El Centinela opera con reloj interno, sin llamadas a API de LLM.

**Por qué:**
- Monitorear tickets atorados es una operación mecánica (contar tickets por timestamp)
- No necesita razonamiento de LLM
- Consumir tokens cada 5 min para "revisar si hay tickets atorados" sería ineficiente
- El Centinela debe poder operar incluso si el LLM no está disponible

**Técnicamente:** En la implementación actual, el monitoring loop del FactoryManager (`_monitor_loop()`) llama a `engineer.monitor()` que revisa health de agentes. La lógica del Centinela (5+ tickets sin progreso por 5+ min) se implementaría como un check adicional en ese loop, sin costo de API.

---

## 🧠 DECISIÓN 16: Main Agent como única autoridad externa

**Decisión:** Solo el Main Agent puede analizar la Factoría desde fuera y decidir si algo no camina bien.

**Por qué solo el Main Agent:**
- Está FUERA de la Factoría — no afectado por problemas internos
- Si el Ingeniero está comprometido, los agentes internos también podrían estarlo
- El Main Agent ve el cuadro completo: tickets, health, alarmas del Centinela
- Tiene autoridad para elevar a la Torre de Control

**Técnicamente:** El Main Agent interactúa con la Factoría SOLO a través de `FactoryManager.request_tool()` y `FactoryManager.get_status()`. No tiene acceso directo a los agentes internos. Esto es intencional — el Main Agent es un **cliente** de la Factoría, no parte de ella.

---

## 🧠 DECISIÓN 17: El Ingeniero LEE y MODIFICA todos los tickets

**Decisión:** El Ingeniero tiene acceso total a leer y modificar los tickets de TODOS los agentes.

**Alternativa considerada:** El Ingeniero solo ve sus propios tickets.

**Por qué acceso total:**
- Si el Main Agent no pide trabajo por horas, los tickets de otros agentes pueden estar atorados
- El Ingeniero puede diagnosticar problemas antes de que escalen
- Puede modificar tickets para delegar órdenes a sus agentes internos

**Técnicamente:** `FactoryEngineer.all_tickets: List[Ticket]` almacena todos los tickets creados. El Engineer los lee y modifica como parte de `process_tool()` y `upgrade_skill()`. Pero **no los monitorea** — eso es del Centinela.

---

## 🧠 DECISIÓN 18: 3 modos de agente interno

**Decisión:** Los internal agents pueden operar en modo `collaborative` o `isolated`.

**Por qué dos modos:**
- **collaborative** — Los agentes se conocen entre sí, usan MessageBus. Ideal para operación normal donde la colaboración acelera el trabajo.
- **isolated** — Cada agente solo ve al SuperiorAgent y a la Tower. Útil para aislamiento de seguridad o cuando un agente está en cuarentena.

**Técnicamente:** El modo se setea en `create_internal(agent_type, mode="collaborative")`. Se almacena como `self.mode` y afecta cómo el agente descubre a sus hermanos. En `isolated`, el agente no puede enviar mensajes directos a otros internos.

---

## 🧠 DECISIÓN 19: Alarmas del Centinela con límite de 5 y separación 3s

**Decisión:** Máximo 5 alarmas activas simultáneas del Centinela, separadas por al menos 3 segundos.

**Por qué este límite:**
- Sin límite: 5+ tickets atorados → Centinela dispara alarma cada 5 min → 12 alarmas/hora → tormenta
- Con límite de 5: si el Main Agent no responde, el Centinela no satura el sistema
- Separación de 3 segundos: evita que múltiples condiciones se disparen simultáneamente

**Técnicamente:** Esta regla está documentada en las notas de diseño. En la implementación actual, el monitoring loop del FactoryManager ya tiene un intervalo de 5s, y los reports se truncan a 200 entradas. La lógica específica del Centinela (5 tickets, 5 min, 5 alarmas máx, 3s separación) se implementaría como una extensión del monitoring loop.

---

## 🧠 DECISIÓN 21: EvidenceStrength como enum (no binario)

**Decisión:** `EvidenceStrength` tiene 3 niveles: WEAK, MEDIUM, STRONG.

**Alternativa considerada:** Booleano (validado/no validado).

**Por qué 3 niveles:**
- **WEAK** — Auto-generada por patrones. Ej: Builder observó 5 patrones exitosos y creó una skill. Confianza baja, necesita validación externa.
- **MEDIUM** — Validada por un agente. Ej: Auditor verificó la skill y dijo "pasa". Confianza media.
- **STRONG** — Probada en runtime. Ej: Reviewer validó + prueba real ejecutada. Confianza alta.

**Técnicamente:** `EvidenceStrength` es un `Enum` con 3 valores. `SkillEvidence` lo usa como campo. Cuando el Ingeniero promueve skills, puede verificar qué evidencia tienen y decidir si es suficiente.

---

## 🧠 DECISIÓN 22: DriftDetector separado de GPS

**Decisión:** `DriftDetector` es una clase separada de `GPS`, aunque ambos trabajan juntos.

**Alternativa considerada:** Unificar en una sola clase.

**Por qué separado:**
- **GPS** — Da el rumbo. Responde: "¿Esta acción está en la dirección correcta?"
- **DriftDetector** — Detecta desviación. Responde: "¿El agente se está desviando de su misión REAL?"
- El GPS compara acción vs destino (mecánico)
- El DriftDetector compara el destino del GPS vs el destino interno del agente (detecta si el GPS mismo fue comprometido)

**Técnicamente:** `DriftDetector` tiene un `GPSCentinella` (wrapper del GPS) y un `Destination` (copia interna del destino). Si el `consensus_with_gps()` falla, significa que el destino del GPS no coincide con el destino interno — el agente está derivando.

---

## 🧠 DECISIÓN 24: Soul.md como documento de alma del Ingeniero

**Decisión:** Las reglas de negocio específicas (cómo procesar cada capability, cuándo cerrar tickets) viven en `Soul.md`, no en el código.

**Alternativa considerada:** Todo en código Python.

**Por qué en Soul.md:**
- Las reglas de negocio cambian más seguido que el código
- Un archivo markdown es editable sin recompilar
- El Ingeniero carga `Soul.md` en `__post_init__()` y lo usa como guía
- Las capabilities específicas (STT, TTS, Web Search, Vision) tienen sus propias reglas en Soul.md

**Técnicamente:** `FactoryEngineer.__post_init__()` llama a `_load_soul_guidance()` que lee `Soul.md` desde el mismo directorio. Luego, `capability_guidance(capability_id)` retorna las reglas específicas para esa capability, que se inyectan en el payload del ticket.

---

## 🧠 DECISIÓN 25: Tickets con sequential ticket_number + UUID

**Decisión:** Cada ticket tiene un `id` (UUID4) y un `ticket_number` (entero secuencial).

**Por qué ambos:**
- `id` (UUID) — Identificación única universal. No hay colisiones. Ideal para referencias internas y trazabilidad.
- `ticket_number` (secuencial) — Legible para humanos. "Ticket #42" es más fácil de recordar que "Ticket a1b2c3d4-...".

**Técnicamente:** El `ticket_number` lo asigna el Engineer (`self._ticket_counter`). El `id` se genera automáticamente en `Ticket.__init__()` con `uuid.uuid4()`. Ambos coexisten en el ticket.

---

*Este documento registra cada decisión de diseño con su fundamento técnico. Si una decisión necesita cambiarse en el futuro, el "por qué original" está documentado.*

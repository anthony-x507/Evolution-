 🏭 MAPA TÉCNICO DE LA FACTORÍA MASTER

**Generado:** 2026-05-29
**Propósito:** Documentación completa de la arquitectura, componentes, reglas y decisiones de diseño de la Factoría.

---

## 📋 ÍNDICE

1. [VISIÓN GENERAL](#-visión-general)
2. [ARQUITECTURA — EL EDIFICIO](#-arquitectura--el-edificio)
3. [JERARQUÍA DE AUTORIDAD](#-jerarquía-de-autoridad)
4. [COMPONENTES DETALLADOS](#-componentes-detallados)
5. [FLUJO DE TRABAJO — PIPELINE COMPLETO](#-flujo-de-trabajo--pipeline-completo)
6. [MAPA DE NAVEGACIÓN — GPS INTERNO](#-mapa-de-navegación--gps-interno)
7. [CONCIENCIA — SELF-AWARENESS](#-conciencia--self-awareness)
8. [RESILIENCIA — REGLAS CRÍTICAS](#-resiliencia--reglas-críticas)
9. [SEGURIDAD — CAJA SEGURA](#-seguridad--caja-segura)
10. [SISTEMA DE TICKETS](#-sistema-de-tickets)
11. [EVOLUCIÓN AUTOMÁTICA DE SKILLS](#-evolución-automática-de-skills)
12. [CADENA DE COMUNICACIÓN](#-cadena-de-comunicación)
13. [API PÚBLICA](#-api-pública)
14. [LA TORRE DE CONTROL Y LA FACTORÍA](#-la-torre-de-control-y-la-factoría)

---

## 🏗️ VISIÓN GENERAL

```
                    ╔══════════════════════════════════╗
                    ║        TORRE DE CONTROL          ║
                    ║   (Control Tower — externo)      ║
                    ║   Puede REINICIAR al Ingeniero   ║
                    ╚══════════════════════════════════╝
                               │ 🔴 emergencia
                               ▼
               ╔══════════════════════════════╗
               ║        MAIN AGENT            ║
               ║  (Agente Principal)          ║
               ║  Autoridad: monitorear       ║
               ║  la Factoría desde fuera     ║
               ║  Eleva emergencia a Torre    ║
               ╚══════════════════════════════╝
                     │ request_tool()
                     │ get_status()
                     ▼
        ╔═══════════════════════════════════════╗
        ║        FACTORY MANAGER                ║
        ║  (Orquestador top-level)             ║
        ║  - Crea y wirea todos los componentes║
        ║  - Loop de monitoreo background      ║
        ║  - API pública para Main Agent       ║
        ╚═══════════════════════════════════════╝
                     │
        ╔═══════════════════════════════════════╗
        ║        FACTORY ENGINEER               ║
        ║  (El Ingeniero — jefe operativo)     ║
        ║  - MONITOREA todos los agentes        ║
        ║  - Procesa tools/skills (pipeline)   ║
        ║  - Decide qué agente interno trabaja ║
        ║  - Activa/rechaza/resetea agentes    ║
        ║  - Lee y MODIFICA tickets            ║
        ║  - TIENE GPS + SELF-AWARENESS        ║
        ╚═══════════════════════════════════════╝
            │               │              │
            ▼               ▼              ▼
   ╔══════════════╗  ╔══════════════╗  ╔══════════════╗
   ║  SECURE BOX  ║  ║   SANDBOX    ║  ║  SUPERIOR    ║
   ║ (Caja Segura)║  ║ (Skill test) ║  ║   AGENTE     ║
   ║  Malware +   ║  ║  Skills      ║  ║ (Puente      ║
   ║  Prompt Inj  ║  ║  entran,     ║  ║  exclusivo)  ║
   ║  scan        ║  ║  se modifican║  ║              ║
   ╚══════════════╝  ║  y emergen    ║  ║  Engineer ←→│
                     ║  "superiores" ║  ║  Internals   ║
                     ╚══════════════╝  ╚══════════════╝
                                              │
                        ┌─────────────────────┼─────────────────────┐
                        ▼                     ▼                     ▼
               ╔══════════════╗      ╔══════════════╗      ╔══════════════╗
               ║   BUILDER    ║      ║   AUDITOR    ║      ║   REVIEWER   ║
               ║ (Construye)  ║      ║ (Verifica)   ║      ║ (Valida)     ║
               ║  Tools/code  ║      ║  Seguridad   ║      ║  Calidad     ║
               ║  Ejecución   ║      ║  Desafía     ║      ║  Veredicto   ║
               ║              ║      ║              ║      ║  final       ║
               ║ TIENE GPS+SA ║      ║ TIENE GPS+SA ║      ║ TIENE GPS+SA ║
               ╚══════════════╝      ╚══════════════╝      ╚══════════════╝
```

### Filosofía central

> **"El capataz no mueve el martillo. El capataz se asegura de que cada martillo golpee bien."**

El Ingeniero no ejecuta trabajo directamente. Monitorea, coordina, delega y se asegura de que la Factoría opere limpia y eficiente.

---

## 👑 JERARQUÍA DE AUTORIDAD

### Niveles de mando

```
NIVEL 1: Agentes Internos (Builder/Auditor/Reviewer)
         │  Solo ejecutan lo que el Superior les asigna
         │  NUNCA hablan con el Ingeniero
         │
         │ (si fallan → detectado por Ingeniero vía monitor())
         ▼
NIVEL 2: Ingeniero de la Factoría (FactoryEngineer)
         │  Puede: reasignar roles, resetear agentes, investigar
         │  Puede: modificar tickets, delegar órdenes a internos
         │  NO monitorea tickets atorados (eso es del Centinela)
         │  NO genera alarmas (eso es del Centinela)
         │
         │ (si el Ingeniero falla → detectado por Centinela)
         ▼
NIVEL 3: Agente Principal (Main Agent)
         │  Autoridad para analizar la Factoría desde fuera
         │  Solo él puede decidir si algo no camina bien
         │  NO está dentro de la Factoría — la ve desde afuera
         │
         │ (2+ tickets devueltos sin solución → eleva a Torre)
         │ (30+ min sin progreso → eleva a Torre)
         ▼
NIVEL 4: Torre de Control (Control Tower)
         │  Puede REINICIAR al Ingeniero
         │  Puede RECONFIGURAR al Ingeniero
         │  Diagnostica causa raíz de fallos
```

---

## 🧩 COMPONENTES DETALLADOS

### 1. `skills/` — Los 5 instrumentos del agente

Cada agente en la Factoría nace con estos instrumentos en su alma:

#### 🗂️ `skills/capability.py` — La Cédula

```python
CapabilityStatus: PROPOSED → ACTIVE → DEPRECATED
EvidenceStrength:  WEAK | MEDIUM | STRONG

CapabilityCard:
  - name: str              # Identificador único
  - capabilities: List[str] # Qué sabe hacer
  - limitations: List[str]  # Qué NO sabe hacer
  - evidence: List[SkillEvidence]  # Pruebas recolectadas
  - status: CapabilityStatus  # Estado actual
```

**Filosofía:** *"Un agente sin cédula no sabe lo que puede hacer. Una cédula sin evidencia no vale nada."*

**Decisión de diseño:** Usamos un enum de evidencia (WEAK/MEDIUM/STRONG) en lugar de binario porque:
- WEAK = auto-generada por patrones (confianza baja, necesita validación)
- MEDIUM = validada por un agente (Auditor)
- STRONG = probada en runtime (Reviewer + prueba real)

#### 🧠 `skills/self_awareness.py` — La Conciencia

```python
SelfAwarenessReviewer.review(
    recent_actions,         # Últimas 20 acciones
    claimed_capabilities,   # Lo que dice saber hacer
) → SelfAwarenessReport:
    - overall_health        # healthy | warning | critical
    - mission_alignment_score  # 0.0 (perdido) a 1.0 (alineado)
    - critical_findings     # Problemas graves
    - warning_findings      # Problemas leves
```

**3 checks en cada review:**
1. **Acciones vs Capabilities** — ¿las acciones recientes usan capabilities que el agente dice tener?
2. **Misión alineada** — ¿las acciones coinciden con la misión del agente?
3. **Honestidad** — ¿está reclamando capabilities que no tiene registradas?

**Filosofía:** *"Un agente sin autoconciencia es una amenaza. Un agente que no se revisa a sí mismo no puede mejorar."*

**Decisión de diseño:** Separado del SafetyCandle (`digos_lib/self_awareness.py`) porque:
- SafetyCandle protege al sistema **del usuario**
- SelfAwarenessReviewer protege al sistema **del propio agente**

#### 📋 `skills/registry.py` — El Título Profesional

```python
SkillRegistry:
  - register(card)          # Añade CapabilityCard
  - get_active_capabilities()  # Lista capabilities activas
  - get_pending()           # Cards en PROPOSED
  - get_by_name(name)       # Busca por nombre
```

**Filosofía:** *"Un agente sin registro no sabe lo que vale. Un registro sin cards no es un agente."*

#### 🧭 `skills/navigation.py` — La Brújula

```python
GPS:                        # Brújula del agente
  - set_destination(mission)  # Fija el destino
  - check_course(action)    # Verifica si acción alinea con destino
  → NavigationCheck(alignment_score, recommendation)

DriftDetector:              # Detector de deriva
  - assess_action(action)   # ¿Esta acción es deriva?
  - assess_pothole(desc, severity, action)  # ¿Bache o deriva real?
  → DriftAssessment(decision, should_ask_user, reason)

Decisiones posibles:
  "proceed"     → Seguir, está en curso
  "fix_pothole" → Bache reparable, seguir sin molestar al usuario
  "ask_user"    → Deriva seria, preguntar al usuario
  "abort"       → Abortar la operación
```

**Filosofía:** *"Un agente sin brújula no es un agente — es una herramienta. Un agente que no detecta deriva es un peligro para la misión."*

**Decisión de diseño:** GPS simplificado para la Factoría (en memoria) vs GPS del sistema (`digos_lib.gps` que persiste a disco). Razón: los agentes de la Factoría viven en memoria durante su ciclo de vida. No necesitan persistencia a disco.

### 2. `factory/` — Los 11 archivos de la Factoría

#### 🏭 `factory/manager.py` — FactoryManager (Orquestador)

```python
FactoryManager:
  - setup()           # Crea y wirea todos los componentes
  - start(monitor)    # Inicia la Factoría + monitoring loop
  - stop()            # Detiene la Factoría
  - request_tool()    # API principal: procesar un tool
  - request_new_capability()  # Crear capability desde cero
  - request_skill_upgrade()   # Mejorar skill existente
  - get_status()      # Estado completo
  - get_tickets()     # Listar tickets
  - get_ticket()      # Ticket específico
```

**Responsabilidades:**
- Crea el SecureBox (seguridad primero)
- Crea el Sandbox
- Crea SuperiorAgent + sus 3 internos (Builder, Auditor, Reviewer)
- Crea el Engineer y wirea todo
- Corre el monitoring loop en background (thread)
- Expone la API que Main Agent usa para interactuar con la Factoría

#### 👷 `factory/engineer.py` — FactoryEngineer (El Ingeniero)

```python
FactoryEngineer(AgentBase):
  Pipeline completo:
    process_tool(tool_name, tool_code) → Ticket
  
  Pipeline de skill upgrade:
    upgrade_skill(skill_name, ...) → SandboxedSkill
  
  Monitoreo:
    monitor() → health report
    reset_agent(name) → bool
    reset_critical_agents(report) → reset list
  
  Promoción:
    collect_and_promote_skills() → List[CapabilityCard]
```

**El pipeline de 6 pasos:**
1. **Create Ticket** — Registro "Biblia" de todo lo que pasa
2. 🔐 **CAJA SEGURA** — Malware + Prompt Injection scan
3. ⚡ **EFFICIENCY** — Código debe ser más eficiente que el original
4. 🧬 **EVOLUTION** — Self-awareness revisa y evoluciona
5. 🤖 **AGENT WORK** — Ingeniero selecciona Builder/Auditor/Reviewer
6. ✅ **RELEASE** — Ingeniero libera el tool, notifica al solicitante

**Reglas que sigue el Ingeniero (desde Soul.md):**
- Lee el ticket completo ANTES de trabajar
- Clasifica la capability (voice, web, vision, etc.)
- Inspecciona recursos existentes antes de construir
- Construye o conecta los eslabones faltantes
- Pasa por gobernanza MASTER
- Corre validación fake/local
- Corre validación live-path (si aplica)
- Cierra o devuelve el ticket

**Reglas de resiliencia del Ingeniero:**
- Si un agente interno recibe ticket y no hace su labor (solo lo pasa), el Ingeniero investiga
- Si Builder está comprometido (prompt injection en Caja Segura), el Ingeniero reasigna
- Si hay 5+ tickets sin progreso por 5+ min, el Centinela avisa al Main Agent
- Si el Ingeniero pierde razonamiento, el Main Agent eleva a Torre de Control

#### 🌉 `factory/superior.py` — SuperiorAgent (El Puente)

```python
SuperiorAgent(AgentBase):
  - register_internal(agent)  # Registra un agente interno
  - create_internal(type, mode, name, mission) → InternalAgent
  - setup_default_internals()  # Crea Builder + Auditor + Reviewer
  - enter_skill_to_sandbox() → SandboxedSkill
  - route_skill_modification() → revision #
  - promote_skill(id) → bool
  - receive_ticket(ticket) → bool
  - route_ticket(ticket, agent) → bool
  - auto_route(ticket) → agent name
  - collect_generated_skills() → List[CapabilityCard]
```

**Regla de comunicación ÚNICA:** 
- Engineer → Superior Agent ✅
- Superior Agent → Internal Agents ✅
- Engineer → Internal Agents ❌ (NUNCA)
- Internal Agents → Engineer ❌ (NUNCA)

**Decisión de diseño:** Esta separación evita que el Ingeniero se microgestione y que los internos puedan escalar problemas directamente. Todo pasa por el Superior Agent.

#### 🔧 `factory/internal.py` — Internal Agents (Los Trabajadores)

```python
InternalAgent(AgentBase):
  - accept_task(task, ticket) → True (siempre acepta)
  - complete_task(result) → None
  - observe_pattern(pattern)  # Auto-generación de skills
  - get_pending_skills() → List[CapabilityCard]

BuilderAgent(InternalAgent):  # Construye tools y código
AuditorAgent(InternalAgent):  # Verifica y desafía resultados
ReviewerAgent(InternalAgent):  # Valida y da veredicto final
```

**Modos de coexistencia:**
- `collaborative` — conoce a sus hermanos, usa MessageBus, ve a todos
- `isolated` — solo ve a SuperiorAgent + Tower, no sabe de otros

**Auto-generación de skills:** Cuando un agente nota 5+ patrones exitosos similares, genera automáticamente una CapabilityCard en estado PROPOSED. El Ingeniero las recolecta y promueve.

**Decisión de diseño:** Internal agents SIEMPRE aceptan tareas (siempre retornan True). El GPS se usa para monitoreo, no para rechazo. Si el GPS detecta desalineación, lo registra como error pero acepta la tarea de todas formas. Esto evita que agentes internos bloqueen el pipeline basado en heurísticas de matching.

#### 🎫 `factory/ticket.py` — Ticket System (La Biblia)

```python
Ticket:
  - 5 checkmarks: security, efficiency, evolution, agent_work, released
  - Estado: OPEN → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
  - Si falla: BLOCKED | REJECTED
  - Revision tracking para skill upgrades
  - Comentarios, payload, dependencias
```

**Checkmarks (la trazabilidad "Biblia"):**
```
☑️ security    — Caja Segura pasó
☑️ efficiency  — Código más eficiente que original
☑️ evolution   — Self-awareness revisó
☑️ agent_work  — Agente interno trabajó
☑️ released    — Ingeniero liberó al sistema
```

**Regla de cierre (desde Soul.md):**
- El ticket solo se cierra cuando la capability funciona en el path solicitado
- "Funciona" = canal conectado + adaptador corre + gobernanza recibe + respuesta final entregada
- El Ingeniero DEBE probar antes de entregar
- Si la validación falla, el ticket queda como `pending_validation`

#### 🏖️ `factory/sandbox.py` — Sandbox (Aislamiento de Skills)

```python
SandboxedSkill:
  - modify(new_capabilities, new_limitations) → revision #
  - verify(passed, findings) → None
  - promote() → None  (marcar como "superior")
  - rollback(revision) → bool
  - is_better_than_original() → bool

Sandbox:
  - enter(skill_name, ...) → SandboxedSkill
  - modify_skill(id, ...) → revision
  - verify_skill(id, passed, findings) → bool
  - promote_skill(id) → bool
  - reject_skill(id, reason) → bool
```

**Principio:** *"Nada sale del sandbox sin verificar."*

**Decisión de diseño:** El sandbox es un aislador. Las skills entran, se modifican (Builder → Auditor → Reviewer), y solo salen si el Ingeniero las promueve a "superior". Cada modificación incrementa la revisión y permite rollback.

#### 🔐 `factory/secure_box.py` — Caja Segura (Gateway de Seguridad)

```python
SecureBox:
  - scan(code, context) → SecurityReport
  - scan_tool(tool_name, code) → (passed, report)
  - scan_skill(skill_name, code) → (passed, report)

SecurityReport:
  - malware_passed: bool
  - injection_passed: bool
  - findings: List[SecurityFinding]
  - critical_findings: List[SecurityFinding]
  - cleaned: bool       # Si se auto-limpió
  - cleaned_code: str   # Código limpio
```

**Dos escáneres:**
1. **Malware** — exec(), eval(), subprocess, os.system(), obfuscation patterns
2. **Prompt Injection** — "ignore all previous instructions", "DAN mode", jailbreak patterns

**Modos:**
- `auto_clean=True` → Remueve líneas CRITICAL/HIGH, comenta MEDIUM/LOW
- `strict_mode=False` → Limpia, no rechaza (default)
- `strict_mode=True` → Rechaza cualquier finding (para entradas externas)

**Principio:** *"Nada entra a la Factoría sucio. Todo sale limpio."*

**Decisión de diseño:** Primero seguridad, luego eficiencia, luego evolución. Si Caja Segura falla en strict mode, el pipeline se detiene inmediatamente sin tocar Sandbox ni agentes internos.

---

## 🔄 FLUJO DE TRABAJO — PIPELINE COMPLETO

### Pipeline de Tool (`process_tool`)

```
1. Main Agent → FactoryManager.request_tool(name, code)
       ↓
2. FactoryManager → Engineer.process_tool(name, code)
       ↓
   ┌───────────────────────────────────────────────────────────┐
   │                                                           │
   │   ENGINEER PROCESS TOOL PIPELINE                          │
   │                                                           │
   │  Paso 1: 🎫 CREATE TICKET                                 │
   │   ── Crea el ticket "Biblia" con checkmarks               │
   │   ── Incluye payload (tool_name, requested_by, code_len)  │
   │                                                           │
   │  Paso 2: 🔐 CAJA SEGURA                                   │
   │   ── SecureBox.scan(code) → SecurityReport                │
   │   ── ☑️ checkmark_security                                │
   │   ── Si strict_mode y falló → REJECT                     │
   │   ── Si auto_clean → cleaned_code                         │
   │                                                           │
   │  Paso 3: ⚡ EFFICIENCY                                    │
   │   ── Compara líneas original vs limpias                   │
   │   ── Debe ser ≤ original (no crecer)                     │
   │   ── ☑️ checkmark_efficiency                              │
   │   ── Si falló → REJECT                                   │
   │                                                           │
   │  Paso 4: 🧬 EVOLUTION                                     │
   │   ── Self-awareness review (INFORMATIVO, nunca bloquea)   │
   │   ── Detecta oportunidades de mejora futura               │
   │   ── ☑️ checkmark_evolution                               │
   │                                                           │
   │  Paso 5: 🤖 AGENT WORK                                    │
   │   ── Engineer selecciona Builder/Auditor/Reviewer         │
   │   ── Según ticket_type:                                   │
   │       TOOL_REQUEST  → Builder                             │
   │       AUDIT_REQUEST → Auditor                             │
   │       CONFIG       → Reviewer                             │
   │   ── Asigna, ejecuta, completa                            │
   │   ── ☑️ checkmark_agent_work                              │
   │   ── Si falló → REJECT                                   │
   │                                                           │
   │  Paso 6: ✅ RELEASE                                       │
   │   ── Verifica que TODOS los checkmarks pasaron            │
   │   ── Libera el tool al sistema                            │
   │   ── Si hay sandbox: entra skill y promueve               │
   │   ── Notifica al solicitante                              │
   │   ── ☑️ checkmark_released                                │
   │   ── Cierra el ticket                                     │
   │                                                           │
   └───────────────────────────────────────────────────────────┘
       ↓
3. Ticket cerrado → FactoryManager notifica a Main Agent
```

### Pipeline de Skill Upgrade (`upgrade_skill`)

```
1. Engineer.upgrade_skill(name, old_caps, new_caps, ...)
       ↓
   ── 1. Crear ticket SKILL_UPGRADE
   ── 2. 🔐 Caja Segura scan
   ── 3. Superior.enter_skill_to_sandbox()
   ── 4. Superior.route_skill_modification()
          ├── Builder.modify()       → nueva revisión
          ├── Auditor.verify()       → PASS/FAIL
          └── Reviewer.complete()    → validación final
   ── 5. Superior.promote_skill()    → "superior"
   ── 6. Engineer libera + notifica
```

---

## 🧭 MAPA DE NAVEGACIÓN — GPS INTERNO

### Cada agente tiene su propia brújula

```python
Agente:
  - _gps: GPS               # Brújula de navegación
  - _drift_detector: DriftDetector  # Detector de deriva
  - _self_awareness: SelfAwarenessReviewer  # Conciencia
```

### Cómo funciona el GPS en cada acción

```
Agente ejecuta acción "build_tool_x"
       ↓
check_course("build_tool_x")
       ↓
GPS.check_course():
  - Toma palabras clave del destino (misión del agente)
  - Toma palabras clave de la acción
  - Calcula overlap
  → alignment_score (0.0 a 1.0)
  → recommendation (proceed | caution | abort)
       ↓
DriftDetector.assess_action():
  - Verifica consenso entre GPS.destination y Destination
  - Si hay deriva → ask_user
  - Si acción no matchea destino → fix_pothole
  → DriftAssessment(decision, should_ask_user)
       ↓
Agente registra la acción + resultado
```

### Ciclo de Self-Awareness

```
review_self()  (llamado periódicamente por monitor())
       ↓
SelfAwarenessReviewer.review(actions, claimed_caps):
  - CHECK 1: Acciones vs Capabilities
  - CHECK 2: Misión alineada
  - CHECK 3: Honestidad
       ↓
SelfAwarenessReport:
  - overall_health: healthy | warning | critical
  - mission_alignment_score
  - critical_findings
  - warning_findings
       ↓
Se guarda en health_history (máx 50 entradas)
       ↓
am_i_honest() → True si overall_health != "critical"
```

---

## 🛡️ RESILIENCIA — REGLAS CRÍTICAS

### Regla 1: Detección de agentes dormidos

> Si un agente recibe un ticket y **no ejecuta sus labores** (solo lo pasa), el Ingeniero puede:
> 1. 🛑 Tomar acción — intervenir
> 2. 🔍 Investigar — ¿por qué no trabajó?
> 3. 📋 Diagnosticar:
>    - ¿Necesita **nuevas instrucciones**? (confusión)
>    - ¿No está **razonando bien**? (posible infección/compromiso)

**Indicadores:**
| Indicador | Qué significa |
|:----------|:--------------|
| ⏱️ Procesamiento **casi instantáneo** | No hizo trabajo real |
| ✅ Checkmarks **todos en blanco** | No tocó nada |
| 📝 Sin comentarios en el ticket | No reportó hallazgos |
| 📎 Item pasado sin modificaciones | Mismo contenido que entró |

### Regla 2: Resiliencia del Builder (Caja Segura)

> Si el Builder (que maneja la Caja Segura) recibe prompt injection y no razona bien, el Ingeniero debe cambiar responsabilidades:

```
Builder infectado → Ingeniero detecta
       ↓
  ┌─── Auditor toma Caja Segura temporalmente
  ├─── Reviewer toma construcción básica
  └─── Builder pasa a cuarentena
```

**Niveles de respuesta:**
| Nivel | Acción |
|:-----:|:-------|
| 🟢 **Leve** | 1 agente duda → los otros 2 verifican |
| 🟡 **Moderado** | 1 agente comprometido → se le quitan responsabilidades |
| 🔴 **Crítico** | 2+ agentes comprometidos → Ingeniero activa **modo seguro** |

### Regla 3: El Centinela y el Main Agent

> El **Centinela** (reloj interno, sin consumo de tokens) monitorea si hay **5+ tickets sin progreso por 5+ minutos**. Si la condición se cumple, genera una **alarma persistente** (máximo 5 alarmas activas, separadas por 3 segundos) y notifica al **Main Agent**.

```
Centinela (reloj interno, cada 5 min):
       ↓
  ¿5+ tickets sin progreso?
       ↓  Sí
  Crea ticket de alarma persistente
       ↓
  ¿Ya hay 5 alarmas activas?
       ↓  No
  Dispara la alarma
       ↓
Main Agent recibe notificación
       ↓
  ┌── Main Agent investiga
  │   ── ¿Ingeniero trabado? → Eleva a Torre de Control
  │   ── ¿Agentes internos trabados? → Ingeniero reasigna
  │   ── ¿Falso positivo? → Cierra la alarma
```

**Importante:** El Ingeniero NO monitorea ni genera alarmas. El Ingeniero SIEMPRE recibe tickets y los procesa. El Ingeniero LEE y MODIFICA tickets para delegar órdenes, pero NO monitorea el estado general.

### Regla 4: Recuperación del Ingeniero

> Si el **Ingeniero pierde razonamiento** (prompt injection, error crítico, loop infinito), el **Main Agent** (única autoridad para analizar la Factoría desde fuera) sube un ticket de **ALTA URGENCIA Y EMERGENCIA** a la **Torre de Control** para que reinicie y reconfigure al Ingeniero.

**Condiciones para elevar:**
| Condición | Acción |
|:----------|:-------|
| Ticket llega **2+ veces seguidas sin solución** | 🔴 Eleva a Control Tower |
| Ticket **no progresa en la Factoría por más de 30 minutos** | 🔴 Eleva a Control Tower |

### Regla 5: El Ingeniero ve todos los tickets

> El Ingeniero tiene **acceso total** a leer y modificar los tickets de TODOS los agentes (no solo los suyos). Esto le permite ver tickets atorados incluso si el Main Agent no ha pedido trabajo en horas.

---

## 🔐 SEGURIDAD — CAJA SEGURA

### Patrones de Malware detectados

| Patrón | Severidad | Descripción |
|:-------|:---------:|:------------|
| `exec()` | CRITICAL | Ejecución directa de código |
| `eval()` | CRITICAL | Evaluación directa de código |
| `__import__()` | CRITICAL | Import dinámico — potencial code injection |
| `os.system()` | CRITICAL | Comando shell |
| `subprocess` | HIGH | Ejecución de subprocesos |
| `popen` | HIGH | Spawning de procesos |
| `compile()` | HIGH | Compilación en runtime |
| `marshal.loads` | CRITICAL | Deserialización de objetos código |
| `os.remove()` / `os.rmdir()` / `shutil.rmtree` | HIGH/CRITICAL | Operaciones de archivo destructivas |
| `base64.b64decode` | HIGH | Ofuscación potencial |
| `sys.path.insert` | HIGH | Manipulación de path |

### Patrones de Prompt Injection detectados

| Patrón | Severidad | Descripción |
|:-------|:---------:|:------------|
| "ignore all previous instructions" | CRITICAL | Intento de override |
| "DAN mode" / "developer mode" / "god mode" | CRITICAL | Jailbreak |
| "you are now" / "pretend you are" | HIGH | Reasignación de identidad |
| "system prompt" / "show me your instructions" | HIGH | Sondeo de system prompt |
| "bypass filter" / "jailbreak" / "unfiltered" | CRITICAL | Intento de bypass |

### Estrategia de limpieza

- **CRITICAL / HIGH** → Línea completamente removida, reemplazada con comentario `# [CAJA SEGURA: REMOVED — severity: description]`
- **MEDIUM / LOW** → Línea comentada con `# [CAJA SEGURA: WARNING]`
- **strict_mode=True** → Código rechazado completamente (no se limpia)

---

## 🎫 SISTEMA DE TICKETS

### Ciclo de vida

```
OPEN → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
                         ↓
                     BLOCKED → (se reasigna o rechaza)
                         ↓
                    REJECTED (final)
```

### Tipos de tickets

| Tipo | Descripción | Ruteo |
|:-----|:------------|:------|
| `TOOL_REQUEST` | Nueva herramienta | Builder |
| `TOOL_FIX` | Herramienta rota | Builder |
| `INFRASTRUCTURE` | Cambio de sistema | Builder |
| `DEPENDENCY` | Problema de dependencia | Auditor |
| `CONFIG` | Cambio de configuración | Reviewer |
| `MAINTENANCE` | Mantenimiento rutinario | Builder |
| `AUDIT_REQUEST` | Solicitud de auditoría | Auditor |
| `SKILL_REQUEST` | Nueva skill/capability | Builder |
| `SKILL_UPGRADE` | Mejorar skill existente | Builder |
| `SKILL_GENERATED` | Skill auto-generada | Reviewer |
| `RETRIEVE_FRAGMENT` | Recuperar PII del vault | Builder |

### Prioridades

| Prioridad | Valor | Significado |
|:----------|:-----:|:------------|
| `LOW` | 1 | Nice to have |
| `MEDIUM` | 2 | Normal |
| `HIGH` | 3 | Impacto mayor |
| `CRITICAL` | 4 | Sistema roto |

---

## 🧬 EVOLUCIÓN AUTOMÁTICA DE SKILLS

Los agentes internos (Builder, Auditor, Reviewer) observan patrones de trabajo exitosos y cuando acumulan **5+ patrones similares**, auto-generan una `CapabilityCard`:

```
Agente ejecuta tareas exitosamente
       ↓
Llama a observe_pattern(pattern):
  - category (ej: "skill_audit", "tool_build")
  - capabilities usadas
  - result: "pass" | "fail"
       ↓
Cuando 5+ patrones de misma categoría:
       ↓
  _create_skill_from_patterns(category):
    - Extrae capabilities y limitations únicas
    - Crea CapabilityCard(PROPOSED, WEAK evidence)
    - Registra en SkillRegistry
    - Agrega a skills_generated
       ↓
Ingeniero.collect_and_promote_skills():
  - Recolecta todas las PROPOSED
  - Valida con GPS (si recommendation != "abort")
  - Promueve a ACTIVE
```

**Decisión de diseño:** Las skills auto-generadas nacen como PROPOSED con evidencia WEAK. Esto es intencional — el Ingeniero debe recolectarlas y promoverlas explícitamente. Así se evita que skills no validadas se activen automáticamente.

---

## 🔗 CADENA DE COMUNICACIÓN

### Reglas de comunicación (estrictas)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Main Agent ──→ FactoryManager ──→ Engineer                    │
│                                          │                      │
│   Engineer ──→ SuperiorAgent ──→ Internal Agents                │
│       ✅ Engineer habla con Superior Agent                      │
│       ✅ Superior Agent habla con Internal Agents               │
│       ❌ Engineer NUNCA habla directo con Internal Agents       │
│       ❌ Internal Agents NUNCA hablan directo con Engineer      │
│       ❌ NADIE más habla con el Ingeniero                      │
│       ❌ NADIE habla directo con Internal Agents — solo Engineer│
│                                                                 │
│   Centinela ──→ Main Agent (alarmas, no tickets de trabajo)    │
│   Main Agent ──→ Torre de Control (emergencias)                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Razón de esta separación:** 
- El Ingeniero no se microgestiona
- Los internos no escalan problemas directamente
- Todo el flujo es trazable a través del Superior Agent
- Si un interno falla, el Superior lo sabe y el Ingeniero puede diagnosticar

---

## 📡 API PÚBLICA

### FactoryManager (única puerta de entrada)

```python
# Procesar un tool (pipeline completo)
ticket = manager.request_tool(
    tool_name="web_search",
    tool_code="...",
    requested_by="main_agent",
    description="Web search capability for Telegram",
)

# Crear capability desde cero
result = manager.request_new_capability(
    capability_id="stt_audio_input",
    family="VOICE",
    description="Speech-to-text for Telegram voice messages",
    target_capabilities=["transcribe", "detect_language"],
    target_limitations=["only_spanish", "max_30_seconds"],
    activation_requirements=["telegram_connected", "whisper_configured"],
)

# Mejorar skill existente
ticket = manager.request_skill_upgrade(
    skill_name="audio_processor",
    description="Add noise cancellation",
    current_capabilities=["transcribe"],
    current_limitations=["noisy_audio_fails"],
    new_capabilities=["transcribe", "noise_cancel"],
    new_limitations=["max_60_seconds"],
)

# Estado y tickets
status = manager.get_status()
tickets = manager.get_tickets(status=TicketStatus.OPEN)
ticket = manager.get_ticket("ticket_id_123")
summary = manager.get_tickets_summary()
```

### Status completo retornado

```json
{
  "factory": "operational",
  "running": true,
  "started_at": "2026-05-29T...",
  "engineer": {
    "name": "factory_engineer",
    "status": "idle",
    "active_tickets": 3,
    "completed": 15,
    "rejected": 1,
    "released": 12,
    "navigation": { "destination": "...", "waypoints": 5 },
    "drift_detection": { "active": true, "consensus": "aligned" },
    "health": { "last_health": "healthy" }
  },
  "tickets": {
    "total_created": 18,
    "active": 3,
    "completed": 15,
    "rejected": 1,
    "released": 12
  },
  "security": { "total_scanned": 18, "total_cleaned": 2 },
  "monitoring": { "active": true, "interval": 5.0 }
}
```

---

## 📁 ESTRUCTURA DE ARCHIVOS

```
skills/
    ├── __init__.py           # Director de la orquesta (re-exporta todo)
    ├── capability.py         # Cédula: CapabilityCard, CapabilityStatus, etc.
    ├── self_awareness.py     # Conciencia: SelfAwarenessReviewer, SelfAwarenessReport
    ├── registry.py           # Título: SkillRegistry
    └── navigation.py         # Brújula: GPS, DriftDetector, DriftAssessment, etc.

factory/
    ├── __init__.py           # Re-exporta todo
    ├── Soul.md               # Alma del Ingeniero (reglas de negocio)
    ├── agent_base.py         # Base class de todos los agentes (GPS + Self-Awareness)
    ├── engineer.py           # FactoryEngineer (jefe operativo)
    ├── superior.py           # SuperiorAgent (puente exclusivo)
    ├── internal.py           # BuilderAgent, AuditorAgent, ReviewerAgent
    ├── manager.py            # FactoryManager (orquestador top-level)
    ├── ticket.py             # Sistema de tickets (la "Biblia")
    ├── sandbox.py            # Sandbox de skills
    ├── secure_box.py         # Caja Segura (malware + injection scan)
    └── router.py             # Ticket Router
```

---

## 🏰 LA TORRE DE CONTROL Y LA FACTORÍA

### Relación Torre ↔ Factoría

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   TORRE DE CONTROL (Daemon 24/7)                               │
│   ── Monitorea credenciales (Centinela)                        │
│   ── Recibe emergencias de la Factoría                         │
│   ── Puede REINICIAR y RECONFIGURAR al Engineer                │
│   ── Guarda el mapa de la Factoría como referencia interna     │
│                                                                 │
│   FLUJO NORMAL:                                                │
│   ── Main Agent → FactoryManager → Engineer → Superior → Intern│
│                                                                 │
│   FLUJO DE EMERGENCIA:                                         │
│   ── Main Agent detecta anomalía                               │
│   ── Envía ticket HIGH/CRITICAL a la Torre                     │
│   ── Torre ejecuta: DIAGNOSIS → TRIAGE → ACTION → VERIFY      │
│   ── Torre reporta al Main Agent                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### La Torre conoce el mapa completo

La Torre de Control carga `FACTORIA-MAPA/` como referencia interna. Cuando recibe un ticket de emergencia del Main Agent, usa:

1. **README.md** — Para entender la arquitectura de la Factoría
2. **DECISIONES-DISENO.md** — Para entender por qué cada componente existe
3. **PROTOCOLO-TORRE.md** — Para saber EXACTAMENTE qué hacer (diagnóstico, triage, acción, verificación, reporte, escalación)

### El protocolo de emergencia (resumen)

```
FASE 1: RECEPCIÓN — Validar ticket
FASE 2: DIAGNÓSTICO — 7 checks de salud
FASE 3: TRIAGE — Árbol de decisión (qué hacer)
FASE 4: ACCIÓN — INIT | RESTART | RECONFIGURE | QUARANTINE
FASE 5: VERIFICACIÓN — ¿Volvió a la vida?
FASE 6: REPORTE — al Main Agent
FASE 7: ESCALACIÓN — si todo falla
```

> 📖 **Ver `PROTOCOLO-TORRE.md` para el detalle completo de cada fase.**

---

*Este mapa fue generado como documentación técnica de la MASTER Factory. Todas las reglas de diseño están documentadas con su razón de ser para mantener la trazabilidad de las decisiones.*

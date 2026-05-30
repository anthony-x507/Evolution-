# 🏰 PROTOCOLO DE LA TORRE DE CONTROL

**Propósito:** Definir EXACTAMENTE qué hace la Torre de Control cuando el Agente Principal le envía un ticket de emergencia de la Factoría.

---

## 📋 ÍNDICE

1. [¿Cómo llega un ticket de emergencia?](#-cómo-llega-un-ticket-de-emergencia)
2. [Fase 1: Recepción y Validación](#-fase-1-recepción-y-validación)
3. [Fase 2: Diagnóstico — El CheckList](#-fase-2-diagnóstico--el-checklist)
4. [Fase 3: Triage — Árbol de Decisión](#-fase-3-triage--árbol-de-decisión)
5. [Fase 4: Acción — Restaurar o Reconfigurar](#-fase-4-acción--restaurar-o-reconfigurar)
6. [Fase 5: Verificación — ¿Volvió a la vida?](#-fase-5-verificación--volvió-a-la-vida)
7. [Fase 6: Reporte al Main Agent](#-fase-6-reporte-al-main-agent)
8. [Fase 7: Escalación — Si todo falla](#-fase-7-escalación--si-todo-falla)
9. [Diagrama de Flujo Completo](#-diagrama-de-flujo-completo)
10. [Registro de Intervenciones (Bitácora)](#-registro-de-intervenciones-bitácora)

---

## 🚨 ¿CÓMO LLEGA UN TICKET DE EMERGENCIA?

### El contrato

El Main Agent envía un ticket a la Torre de Control cuando detecta que la Factoría no está funcionando correctamente. El ticket debe tener:

```json
{
  "type": "factory_emergency",
  "severity": "high" | "critical",
  "source": "main_agent",
  "target": "torre_de_control",
  "reason": "engineer_stuck" | "factory_not_responding" | "tickets_stuck_30min" | "tickets_returned_2x",
  "description": "Detalles del problema...",
  "ticket_ids": ["#42", "#43"],
  "diagnosis_hint": "El Ingeniero parece no procesar tickets",
  "centinela_alarms": 3,
  "timestamp": "2026-05-29T..."
}
```

### Condiciones que activan el ticket

| Condición | Severidad | Gatillado por |
|:----------|:---------:|:--------------|
| 2+ tickets devueltos sin solución | 🔴 HIGH | Main Agent |
| 30+ min sin progreso en la Factoría | 🔴 CRITICAL | Main Agent |
| 5+ tickets sin progreso por 5+ min | 🟡 MEDIUM | Centinela (avisa al Main Agent, y este decide) |

### ¿Qué NO es una emergencia?

- Un ticket normal de tool request → va al Engineer, no a la Torre
- Una capability request → va a la Factory, no a la Torre
- Una credential rotation → va al Engineer, no a la Torre

**Solo las condiciones arriba activan el protocolo de emergencia.**

---

## 📥 FASE 1: RECEPCIÓN Y VALIDACIÓN

Cuando la Torre recibe un ticket de emergencia:

```
PASO 1: ¿El ticket es realmente una emergencia?
         ├── ¿type == "factory_emergency"? 
         │     ├── Sí → continuar
         │     └── No → rechazar con "ticket_type_invalid"
         │
         ├── ¿severity in ("high", "critical")?
         │     ├── Sí → continuar
         │     └── No → bajar a priority normal, no emergencia
         │
         ├── ¿source == "main_agent"?
         │     ├── Sí → continuar
         │     └── No → rechazar con "unauthorized_source"
         │
         └── ¿target == "torre_de_control"?
               ├── Sí → continuar
               └── No → re-rutear al destino correcto

PASO 2: Registrar el ticket en la bitácora de la Torre
         ├── timestamp
         ├── ticket_id original del Main Agent
         ├── reason
         └── estado inicial: "received"

PASO 3: Iniciar el protocolo de emergencia
         └── Saltar cualquier otro ciclo en curso
```

### Registro en bitácora

```python
{
    "intervention_id": "INT-20260529-001",
    "triggered_by": "main_agent",
    "received_at": "2026-05-29T14:30:00Z",
    "ticket": {...},
    "status": "received",
}
```

---

## 🔍 FASE 2: DIAGNÓSTICO — EL CHECKLIST

La Torre ejecuta estos checks EN ORDEN:

### Check 1: ¿La Factoría está inicializada?

```python
if self._factory_manager is None:
    return {"finding": "factory_not_initialized", "severity": "critical"}
```

### Check 2: ¿El Engineer de la Factoría responde?

```python
try:
    status = self._factory_manager.get_status()
    engineer_health = status.get("engineer", {}).get("health", {})
except Exception as e:
    return {"finding": "factory_unresponsive", "error": str(e), "severity": "critical"}
```

### Check 3: ¿Cuántos tickets están atorados?

```python
tickets = self._factory_manager.get_tickets()
stuck = [t for t in tickets if t.status not in ("closed", "delivered") 
         and t.updated_at < (now - timedelta(minutes=30))]
return {"finding": "tickets_stuck", "count": len(stuck), "ticket_ids": [...]}
```

### Check 4: ¿El Centinela reportó alarmas sobre la Factoría?

```python
reports = self._centinela.get_reports(source="factory")
return {"finding": "centinela_reports", "count": len(reports), "reports": reports}
```

### Check 5: ¿Hay agentes internos comprometidos?

```python
for name, agent in self._superior_agent.internal_agents.items():
    if agent.status == "compromised":
        findings.append({"finding": "agent_compromised", "agent": name})
```

### Check 6: ¿El Ingeniero tiene salud?

```python
engineer = status.get("engineer", {})
health = engineer.get("health", {}).get("last_health", "unknown")
if health != "healthy":
    findings.append({"finding": "engineer_unhealthy", "health": health})
```

### Check 7: ¿Hay errores en los logs de la Factoría?

```python
logs = self._log.get_logs(source="factory", level="error", limit=10)
if logs:
    findings.append({"finding": "factory_errors", "count": len(logs)})
```

### Resultado del diagnóstico

```python
diagnosis = {
    "factory_initialized": bool(self._factory_manager),
    "factory_responsive": bool(engineer_health),
    "tickets_stuck": len(stuck_tickets),
    "centinela_reports": len(centinela_reports),
    "agents_compromised": compromised_agents,
    "engineer_healthy": engineer_healthy,
    "logs_with_errors": error_count,
    "overall_health": "critical" | "warning" | "healthy",
    "findings": findings_list,
}
```

---

## ⚖️ FASE 3: TRIAGE — ÁRBOL DE DECISIÓN

Basado en los findings del diagnóstico, la Torre decide QUÉ hacer:

### Matriz de decisión

| Finding | Acción | Prioridad |
|:--------|:-------|:---------:|
| `factory_not_initialized` | **INIT** — Inicializar la Factoría | 🟢 Baja |
| `factory_unresponsive` | **RESTART** — Reiniciar la Factoría | 🔴 Alta |
| `engineer_unhealthy` | **RECONFIGURE** — Reconfigurar al Engineer | 🔴 Alta |
| `agent_compromised` | **QUARANTINE** + **RECONFIGURE** | 🔴 Crítica |
| `tickets_stuck >= 5` | **RESTART** — Engineer trabado | 🟡 Media |
| `tickets_stuck >= 10` | **RESTART** + **RECONFIGURE** | 🔴 Alta |
| `centinela_reports > 0` | **INVESTIGATE** — Revisar cada reporte | 🟡 Media |
| `logs_with_errors > 5` | **RECONFIGURE** — Engineer degradado | 🟡 Media |
| Múltiples findings | **RESTART** + **RECONFIGURE** | 🔴 Crítica |

### Árbol de decisión completo

```
DIAGNOSIS COMPLETE
       ↓
  ┌── ¿factory_not_initialized?
  │     ↓ Sí → INIT → FASE 4
  │
  ├── ¿factory_unresponsive?
  │     ↓ Sí → RESTART → FASE 4
  │
  ├── ¿agent_compromised?
  │     ↓ Sí → QUARANTINE + RECONFIGURE → FASE 4
  │
  ├── ¿engineer_unhealthy?
  │     ↓ Sí → RECONFIGURE → FASE 4
  │
  ├── ¿tickets_stuck >= 5?
  │     ↓ Sí → RESTART → FASE 4
  │
  └── ¿Ningún finding crítico?
        ↓ Sí → NOTIFY Main Agent "falso positivo" → FIN
```

---

## ⚡ FASE 4: ACCIÓN — RESTAURAR O RECONFIGURAR

### Acción: INIT (Inicializar Factoría)

```python
def _action_init(self):
    """Inicializa la Factoría desde cero."""
    self._log.warn("torre", "FASE 4 — INIT: Inicializando Factoría")
    
    # 1. Crear FactoryManager
    from factory.manager import FactoryManager
    self._factory_manager = FactoryManager()
    
    # 2. Setup
    self._factory_manager.setup()
    self._factory_manager._progress_cb = self.emit_tool_progress
    
    # 3. Inicializar SuperiorAgent
    self._superior_agent = self._factory_manager._superior
    
    # 4. Crear agentes internos por defecto
    self._superior_agent.setup_default_internals()
    
    # 5. Verificar
    status = self._factory_manager.get_status()
    ok = status.get("factory") == "operational"
    
    return {"action": "init", "success": ok, "status": status}
```

### Acción: RESTART (Reiniciar Factoría)

```python
def _action_restart(self):
    """Reinicia la Factoría manteniendo la estructura.
    
    NO borra tickets ni skills — solo reinicia los procesos.
    """
    self._log.warn("torre", "FASE 4 — RESTART: Reiniciando Factoría")
    
    # 1. Detener monitoring loop
    self._factory_manager.stop()
    
    # 2. Preservar tickets y skills
    preserved_tickets = self._factory_manager.get_all_tickets()
    preserved_skills = self._factory_manager._engineer._skill_registry
    
    # 3. Resetear agentes internos
    for name in list(self._superior_agent.internal_agents.keys()):
        self._superior_agent.remove_internal(name)
    
    # 4. Re-crear SuperiorAgent
    from factory.superior import SuperiorAgent
    self._superior_agent = SuperiorAgent()
    
    # 5. Reconectar con FactoryManager
    self._factory_manager._superior = self._superior_agent
    self._superior_agent._manager = self._factory_manager
    
    # 6. Restaurar tickets
    for ticket in preserved_tickets:
        self._factory_manager._engineer._tickets[ticket.id] = ticket
    
    # 7. Restaurar skills
    self._factory_manager._engineer._skill_registry = preserved_skills
    
    # 8. Re-crear agentes internos por defecto
    self._superior_agent.setup_default_internals()
    
    # 9. Iniciar monitoring loop de nuevo
    self._factory_manager.start()
    
    # 10. Verificar
    status = self._factory_manager.get_status()
    ok = status.get("factory") == "operational" and status.get("running")
    
    return {"action": "restart", "success": ok, "status": status}
```

### Acción: RECONFIGURE (Reconfigurar al Engineer)

```python
def _action_reconfigure(self):
    """Reconfigura al Engineer de la Factoría.
    
    Mantiene todos los tickets y skills, pero:
    - Recarga el Soul.md (reglas de negocio)
    - Resetea el GPS del Engineer
    - Re-inyecta Self-Awareness
    """
    self._log.warn("torre", "FASE 4 — RECONFIGURE: Reconfigurando Engineer")
    
    # 1. Obtener el Engineer
    engineer = self._factory_manager._engineer
    
    # 2. Preservar tickets y skills
    tickets_backup = engineer.all_tickets.copy()
    skills_backup = engineer._skill_registry
    
    # 3. Recargar Soul.md
    engineer._load_soul_guidance()
    
    # 4. Resetear GPS del Engineer
    engineer._gps = GPS()
    engineer._gps.set_destination(engineer.mission)
    
    # 5. Re-inyectar Self-Awareness
    engineer._self_awareness = SelfAwarenessReviewer(
        registry=skills_backup,
        mission_statement=engineer.mission,
        current_mission=engineer.mission,
    )
    
    # 6. Re-inyectar DriftDetector
    engineer._drift_detector = DriftDetector(
        gps=GPSCentinella(_gps=engineer._gps),
        destination=Destination(),
    )
    engineer._drift_detector.set_destination(engineer.mission)
    
    # 7. Restaurar tickets
    engineer.all_tickets = tickets_backup
    
    # 8. Verificar salud
    report = engineer.review_self()
    ok = report.overall_health != "critical"
    
    return {"action": "reconfigure", "success": ok, "health": report.overall_health}
```

### Acción: QUARANTINE (Aislar agente comprometido)

```python
def _action_quarantine(self, agent_name: str):
    """Aísla un agente interno comprometido.
    
    1. Pone el agente en modo isolated
    2. Revoca su acceso a la Caja Segura
    3. Loggea el incidente
    4. Notifica al Main Agent
    """
    self._log.warn("torre", f"FASE 4 — QUARANTINE: aislando agente '{agent_name}'")
    
    agent = self._superior_agent.internal_agents.get(agent_name)
    if agent is None:
        return {"action": "quarantine", "success": False, "reason": "agent_not_found"}
    
    # 1. Poner en modo isolated
    agent.mode = "isolated"
    
    # 2. Revocar acceso a SecureBox
    agent._secure_box_access = False
    
    # 3. Resetear GPS (para que no ejecute nada sin supervisión)
    agent._gps = GPS()
    
    # 4. Marcar estado
    agent.status = "quarantined"
    
    # 5. Registrar en bitácora
    self._log.warn("torre", 
        f"⚠️ AGENTE EN CUARENTENA: {agent_name} — modo={agent.mode}, "
        f"secure_box={agent._secure_box_access}, status={agent.status}")
    
    return {"action": "quarantine", "success": True, "agent": agent_name, "status": "quarantined"}
```

---

## ✅ FASE 5: VERIFICACIÓN — ¿VOLVIÓ A LA VIDA?

Después de ejecutar la acción, la Torre debe verificar que la Factoría está operativa:

### Post-checklist

```python
def _verify_factory_health(self) -> dict:
    """Verifica que la Factoría está saludable después de la intervención."""
    
    checks = {}
    
    # 1. ¿FactoryManager responde?
    try:
        status = self._factory_manager.get_status()
        checks["factory_responsive"] = status.get("factory") == "operational"
    except:
        checks["factory_responsive"] = False
    
    # 2. ¿Engineer responde?
    try:
        engineer = self._factory_manager._engineer
        report = engineer.review_self()
        checks["engineer_healthy"] = report.overall_health != "critical"
    except:
        checks["engineer_healthy"] = False
    
    # 3. ¿SuperiorAgent responde?
    checks["superior_active"] = self._superior_agent is not None
    
    # 4. ¿Agentes internos existen y responden?
    try:
        internal_count = len(self._superior_agent.internal_agents)
        checks["internal_agents_count"] = internal_count
        checks["internal_agents_ok"] = internal_count >= 3
    except:
        checks["internal_agents_ok"] = False
    
    # 5. ¿Puede procesar un ticket de prueba?
    try:
        test_ticket = self._factory_manager._engineer.create_ticket(
            "system", "test_ticket",
            "Post-recovery verification",
            "low", source="torre_de_control"
        )
        checks["can_create_ticket"] = bool(test_ticket)
    except:
        checks["can_create_ticket"] = False
    
    # Health general
    all_ok = all([
        checks.get("factory_responsive", False),
        checks.get("engineer_healthy", False),
        checks.get("superior_active", False),
        checks.get("internal_agents_ok", False),
        checks.get("can_create_ticket", False),
    ])
    
    checks["overall_ok"] = all_ok
    
    return checks
```

### Criterios de éxito

| Check | Esperado | Si falla |
|:------|:--------:|:---------|
| Factory responde | ✅ True | La intervención no funcionó → ESCALAR |
| Engineer saludable | ✅ healthy/warning | Reintentar RECONFIGURE |
| SuperiorAgent activo | ✅ not None | Re-crear SuperiorAgent |
| Agentes internos | ✅ >= 3 | Re-crear internos por defecto |
| Puede crear ticket | ✅ True | Engineer no está operativo → ESCALAR |

---

## 📨 FASE 6: REPORTE AL MAIN AGENT

Después de la verificación, la Torre envía un reporte completo al Main Agent:

```json
{
  "type": "factory_emergency_report",
  "from": "torre_de_control",
  "to": "main_agent",
  "original_ticket_id": "#TICKET-123",
  "intervention_id": "INT-20260529-001",
  
  "diagnosis": {
    "findings": ["engineer_unhealthy", "tickets_stuck"],
    "overall_health": "warning"
  },
  
  "action_taken": {
    "action": "reconfigure",
    "success": true,
    "timestamp": "2026-05-29T14:31:00Z"
  },
  
  "verification": {
    "factory_responsive": true,
    "engineer_healthy": true,
    "superior_active": true,
    "internal_agents_ok": true,
    "can_create_ticket": true,
    "overall_ok": true
  },
  
  "recommendation": "La Factoría ha sido restaurada. El Main Agent puede re-enviar tickets normalmente.",
  
  "intervention_log": "INT-20260529-001: RECONFIGURE ejecutado exitosamente. Engineer reconfigurado con nuevo GPS + Self-Awareness."
}
```

```python
def _report_to_main_agent(self, diagnosis, action_result, verification):
    """Envía reporte al Main Agent después de la intervención."""
    
    report = {
        "type": "factory_emergency_report",
        "from": "torre_de_control",
        "diagnosis": diagnosis,
        "action_taken": action_result,
        "verification": verification,
    }
    
    # Loggear el reporte
    self._log.info("torre", f"📨 Reporte de intervención enviado al Main Agent")
    self._log.info("torre", f"   Acción: {action_result.get('action', '?')} — "
                           f"{'✅ OK' if action_result.get('success') else '❌ FALLÓ'}")
    self._log.info("torre", f"   Factoría: {'✅ Saludable' if verification.get('overall_ok') else '🔴 Aún caída'}")
    
    # Inyectar notificación al agente si está vivo
    if self._agent is not None:
        self._agent.inject_factory_report(report)
    
    return report
```

---

## 🔴 FASE 7: ESCALACIÓN — SI TODO FALLA

Si después de RESTART + RECONFIGURE la Factoría sigue caída:

### Cuándo escalar

| Condición | Acción |
|:----------|:-------|
| RESTART falló | Reintentar 1 vez → si falla de nuevo, ESCALAR |
| RECONFIGURE falló | Reintentar 1 vez → si falla de nuevo, ESCALAR |
| QUARANTINE + RECONFIGURE falló | ESCALAR directamente (es crítico) |
| INIT falló | ESCALAR — posible error de infraestructura |

### A quién escalar

```
NIVEL 1: Torre de Control (auto-recuperación)
         ── Intenta RESTART / RECONFIGURE / INIT

NIVEL 2: Sistema (logs + diagnóstico completo)
         ── Registra el error con máximo detalle
         ── Apaga la Factoría para evitar daños mayores
         ── Deja un mensaje claro al usuario

NIVEL 3: Usuario / Administrador del Sistema
         ── Mensaje: "⚠️ La Factoría ha fallado y no pudo recuperarse."
         ── Instrucciones: "Revisa los logs en ~/.digos/logs/factory_emergency.log"
         ── Recomendación: "Reinicia DIGOS con 'digos --daemon'"
```

### Mensaje de escalación al usuario

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🔴 EMERGENCIA — FACTORÍA NO RESPONDE                      ║
║                                                              ║
║   La Torre de Control ha intentado recuperar la Factoría     ║
║   pero NO ha sido posible.                                   ║
║                                                              ║
║   Diagnóstico final:                                         ║
║   ── Factory responsive:  ❌                                 ║
║   ── Engineer healthy:    ❌                                 ║
║   ── Internals ok:        ❌                                 ║
║                                                              ║
║   Acciones tomadas:                                          ║
║   ── RESTART  → falló                                       ║
║   ── RECONFIGURE → falló                                    ║
║                                                              ║
║   📁 Logs: ~/.digos/logs/factory_emergency.log              ║
║   🔧 Solución: Reinicia DIGOS con 'digos --daemon'          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 🔄 DIAGRAMA DE FLUJO COMPLETO

```
MAIN AGENT envía ticket de emergencia
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 1: RECEPCIÓN                                          │
│  ── Validar tipo, severidad, origen, destino                │
│  ── Registrar en bitácora                                   │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 2: DIAGNÓSTICO                                        │
│  ── Check 1: ¿Factoría inicializada?                        │
│  ── Check 2: ¿Factory responde?                             │
│  ── Check 3: ¿Tickets atorados?                             │
│  ── Check 4: ¿Centinela reportó?                            │
│  ── Check 5: ¿Agentes comprometidos?                        │
│  ── Check 6: ¿Engineer saludable?                           │
│  ── Check 7: ¿Errores en logs?                              │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 3: TRIAGE                                             │
│                                                             │
│  ┌── factory_not_initialized? ──→ INIT                      │
│  ├── factory_unresponsive?    ──→ RESTART                   │
│  ├── agent_compromised?       ──→ QUARANTINE + RECONFIGURE  │
│  ├── engineer_unhealthy?      ──→ RECONFIGURE               │
│  ├── tickets_stuck >= 5?      ──→ RESTART                   │
│  ├── tickets_stuck >= 10?     ──→ RESTART + RECONFIGURE     │
│  └── no_critical_findings?    ──→ NOTIFY (falso positivo)   │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 4: ACCIÓN                                             │
│  ── INIT      → Crear Factoría desde cero                   │
│  ── RESTART   → Reiniciar procesos (preservar tickets)      │
│  ── RECONFIGURE → Recargar Soul.md + reset GPS + SA        │
│  ── QUARANTINE → Aislar agente comprometido                 │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 5: VERIFICACIÓN                                       │
│  ── ¿Factory responde?                                      │
│  ── ¿Engineer saludable?                                    │
│  ── ¿SuperiorAgent activo?                                  │
│  ── ¿Internos >= 3?                                         │
│  ── ¿Puede crear ticket?                                    │
│                                                             │
│  ┌── all_ok ✅ ──→ FASE 6                                   │
│  └── falló ❌ ──→ FASE 7 (escalar)                          │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 6: REPORTE                                            │
│  ── Enviar reporte completo al Main Agent                   │
│  ── Incluir: diagnosis + action + verification              │
│  ── Recomendación: "puedes enviar tickets de nuevo"         │
└─────────────────────────────────────────────────────────────┘

    (si FASE 5 falló)
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 7: ESCALACIÓN                                         │
│  ── Reintentar RESTART 1 vez                                │
│  ── Si falla: mensaje al usuario                            │
│  ── Apagar Factoría para evitar daños                       │
│  ── Recomendación: reiniciar DIGOS                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 REGISTRO DE INTERVENCIONES (BITÁCORA)

Cada intervención de la Torre se registra en una bitácora interna con:

```python
bitacora_entry = {
    "intervention_id": "INT-20260529-001",     # Auto-incremental
    "triggered_by": "main_agent",               # Quién gatilló
    "received_at": "2026-05-29T14:30:00Z",      # Cuándo
    "ticket_id": "#TICKET-123",                # Ticket original
    "reason": "engineer_stuck",                # Por qué
    "diagnosis": {
        "findings": ["engineer_unhealthy"],
        "overall_health": "warning",
    },
    "action_taken": {
        "action": "reconfigure",
        "success": True,
        "duration_seconds": 1.2,
    },
    "verification": {
        "overall_ok": True,
        "details": {...},
    },
    "resolved_at": "2026-05-29T14:31:00Z",
    "status": "resolved",                      # resolved | failed | escalated
}
```

### ¿Dónde se guarda?

```python
self._factory_interventions: List[dict] = []  # En memoria (máx 100)
```

También se persiste a disco como parte del estado de la Torre:
```python
FACTORY_INTERVENTIONS_FILE = DIGOS_DIR / "factory_interventions.json"
```

---

*Este protocolo define exactamente cómo la Torre de Control maneja las emergencias de la Factoría. Cada paso está diseñado para minimizar el tiempo de recuperación y maximizar la trazabilidad.*

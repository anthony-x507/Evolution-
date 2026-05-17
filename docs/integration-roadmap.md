# Integration Roadmap

Status: public-safe roadmap

## Master Test Rule

Each implementation phase must pass 200 clean cycles after the last correction.
If a failure appears, the phase stops, the smallest correction is made, and that
phase restarts from cycle 0.

## Phase 1: Core Cluster Brain

Scope:

- task IR;
- node identity;
- trusted-node checks;
- route scoring;
- scheduling decisions;
- lease proposals;
- audit event creation;
- synthetic fixture loading.

Exit label:

```text
PHASE_1_CORE_GREEN
```

## Phase 2: Runtime, Plugin, And Job Lifecycle

Scope:

- plugin descriptor reading;
- plugin capability matching;
- job lifecycle state;
- dry-run previews;
- expected output generation;
- status snapshot generation;
- audit story generation.

Exit label:

```text
PHASE_2_RUNTIME_GREEN
```

## Phase 3: Multi-Node Simulation, Failure, And Recovery

Scope:

- synthetic multi-Mac fixtures;
- route fallback;
- lease expiry;
- node loss;
- stale or degraded routes;
- retry and wait decisions;
- local fallback when policy allows.

Exit label:

```text
PHASE_3_RECOVERY_GREEN
```

## Phase 4: Dashboard Projection

Scope:

- one Rocket Cluster dashboard slot;
- compact status projection;
- full Rocket view data shape;
- node status display data;
- route status display data;
- queue and job summary;
- dry-run result projection;
- freshness and warning labels.

Exit label:

```text
PHASE_4_DASHBOARD_GREEN
```

## Phase 5: Manual Real Cluster Test

Phase 5 is not part of the offline simulator. It requires separate owner
approval after Phases 1-4 are green.

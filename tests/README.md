# Tests

Rocket tests will begin with offline, synthetic fixtures.

The project target is:

```text
200 clean cycles after the last correction for each integration phase
```

The first tests should verify:

- trusted node selection;
- unknown node rejection;
- blocked route avoidance;
- audit event creation;
- deterministic scheduling output.

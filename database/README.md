# Runtime Databases

This directory contains generated SQLite runtime state and is excluded from Git:

- `jrkj.sqlite3`: query database built from `data/2` through `data/5`;
- `jrkj_memory.sqlite3`: persistent evidence memory created during Agent runs.

Rebuild the query database after the required source files are available:

```bash
jrkj build-db --force
```


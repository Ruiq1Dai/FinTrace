# Data Layout

JRKJ keeps source data and reproducible audit samples under this directory.
Large licensed/raw datasets and the generated SQLite database may need to be supplied separately.

| Path | Contents |
| --- | --- |
| `1/` | Multi-turn user questions |
| `2/` | Top-shareholder snapshots |
| `3/` | Risk-announcement index |
| `4/` | Income, balance-sheet, and cash-flow statements |
| `5/` | Research-report summaries |
| `enriched/` | Auditable announcement text, consolidated statements, entity master, and local document graph |
| `manifest.json` | Auditable data contract |

Do not commit credentials, private data, or locally generated databases. Validate
the selected audit sample with:

```bash
python scripts/check_data.py --strict
```

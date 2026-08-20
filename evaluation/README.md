# Evaluation

Evaluation assets are separated from runtime code:

```text
evaluation/
├── dataset/          # benchmark cases and question templates
├── results/          # curated deterministic results
│   └── archive/      # historical Agent CSV/LOG runs
├── GROUND_TRUTH.md   # annotation protocol
└── ENTITY_RESOLUTION.md
```

Run the deterministic ablation without Neo4j:

```bash
python scripts/run_evaluation.py --skip-neo4j
```

Run the 19-question model evaluation only when an LLM endpoint is configured:

```bash
python scripts/run_agent_evaluation.py --batch local-run
```

Risk labels and answer correctness still require the human review defined in
`GROUND_TRUTH.md`.

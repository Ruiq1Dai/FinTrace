# Entity Resolution Contract

Ownership names are not legal identities. A name-only shareholder record must
remain `unresolved_name_match` and cannot produce a controller or circular
ownership finding.

To resolve a holder, create `data/enriched/entity_resolutions.jsonl` with one
record per verified mapping:

```json
{"holder_name":"...","security_code":"...","entity_id":"security:...","verification_status":"verified_external_source","verification_source":"registry-or-official-document#...","effective_from":"YYYYMMDD","effective_to":"YYYYMMDD"}
```

The migration script rejects rows without a verification source or with any
status other than `verified_external_source`. It writes a Neo4j
`RESOLVED_AS` relationship and only then enables circular ownership analysis.
The mapping must be reviewed by a finance-literate human; no external name
matching is accepted as Ground Truth automatically.

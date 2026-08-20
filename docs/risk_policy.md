# JRKJ Risk Policy v1

## Scope

This policy labels investigation leads. It does not determine fraud, audit
misstatement, insolvency, or legal liability. Every output must include the
policy version, source evidence, reporting scope, and limitations.

Multi-Agent orchestration is out of scope for this version. The production
investigation path is one Agent using deterministic SQL, calculation, graph,
scorecard, and evidence tools.

## Screening conventions

| Signal | Rule | Guardrail |
| --- | --- | --- |
| Beneish M-Score | `M > -1.78` | Screening flag only; validate all eight indexes and model scope. |
| Altman Z-Score | `<1.81` distress, `1.81-2.99` grey, `>2.99` safer zone | Original public-company model is scope-sensitive; do not apply blindly to financial or non-manufacturing firms. |
| Piotroski F-Score | `0-3` weak, `4-6` neutral, `7-9` strong | Quality screen, not a fraud model. |
| Peer z-score | `abs(z) >= 2` | At least 10 same-industry, same-period, same-scope peers. |
| Receivables/inventory | Growth exceeds revenue growth by at least 10 percentage points | Requires comparable periods; business-context review is mandatory. |
| Revenue/cash flow | Revenue rises while operating cash flow falls | One period is a low-level lead; two comparable periods strengthen it. |

The thresholds are project screening conventions. They must be reported as
fields, not hidden in prose or converted into a fraud probability.

## Risk level rules

`insufficient_data` takes precedence when required values, reporting scope,
period comparability, announcement body, or entity identity are missing.

`none` means no configured material signal was triggered. `low` means one
reproducible signal family without independent corroboration. `medium` means
two independent signal families, or one signal family plus an external clue.
`high` requires at least two independent signal families over two comparable
periods plus strong external evidence (audit opinion, announcement body,
regulatory decision, court decision, or verified graph path).

`confirmed_fact` is separate from risk level. It is allowed only when an
official regulatory, judicial, or exchange document explicitly establishes the
relevant violation. A score or model signal can never produce this label.

Confidence is separate from risk: primary records plus deterministic formulas
can be high confidence even when the risk level is low; title-only evidence or
mother-company-only statements generally lower confidence.

## Minimal data enrichment

The minimum enrichment set is:

1. PDF text for the selected announcement cases, retaining page/paragraph,
   URL, retrieval time, and document hash;
2. consolidated financial statements for selected demo/evaluation companies,
   retaining statement scope and source identifiers;
3. an entity alias table for selected companies and shareholders, retaining
   stable entity IDs, aliases, effective dates, and verification source.

The project may remain incomplete for companies outside this selected set. It
must say “data insufficient” instead of extrapolating a controller or fraud
finding.

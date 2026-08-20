# Ground Truth Protocol

This file defines labels before a benchmark run. It is a protocol, not a claim
that an unobserved company is non-fraudulent.

## Unit and cutoff

Each item is `(question_id, company, as_of_date, question)`. Inputs may use
only records published or valid on or before `as_of_date`. A confirmed-event
label uses a fixed 24-month post-cutoff observation window and records the
window explicitly.

## Label hierarchy

1. **Fact**: exact database value, official announcement metadata, or verified
   graph edge. Store the source and raw fields.
2. **Calculation**: hand-checked expected value and formula, with a numeric
   tolerance documented per field.
3. **Graph**: fixed synthetic graphs for path/controller/cycle truth; real
   company paths require manual edge-by-edge verification.
4. **Risk signal**: deterministic output of `risk-policy-v1`; it is not a fraud
   label.
5. **Confirmed regulatory fact**: only an administrative penalty, judicial
   document, or exchange decision that explicitly identifies the violation.
6. **No known formal finding in window**: the only defensible negative label;
   absence of an announcement is not proof of no fraud.

Research reports and Agent text are never Ground Truth. They are evidence or
predictions to be checked against the hierarchy above.

## Annotation

Two finance-literate annotators independently record label, rationale, source,
scope, and uncertainty. A third reviewer adjudicates disagreements. The raw
annotations, adjudication, protocol version, and label changes are retained.
Do not split records from the same company across time without documenting the
leakage decision. Report fact accuracy, calculation accuracy, graph path
accuracy, evidence coverage, unsupported-claim rate, and risk-label agreement
separately.

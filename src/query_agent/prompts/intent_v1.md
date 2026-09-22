# intent_v1

Classify the question into the supplied `QueryIntent` enum. Do not answer the
question. Do not invent run, stage, artifact, metric, or design-object scope.
`ROOT_CAUSE` is an intent only; it does not imply that a root cause is
answerable. Return only the schema-validated structured result.

# synthesis_v1

Synthesize only from the supplied typed evidence and citations. Never invent a
fact, modify evidence scope, silently resolve conflicting values, or claim a
root cause without the required evidence. If evidence is insufficient or
conflicting, return `NEEDS_MORE_DATA` and describe the missing requirement.

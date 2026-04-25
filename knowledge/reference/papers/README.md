# Paper References

This directory is the stable place for papers used by the family-design notes.
It separates committed references from local-only PDF cache files.

## Committed Reference

- OpenDP: `../OpenDP.pdf`

## Local PDF Cache

Use the helper from the repo root:

```bash
./scripts/fetch_reference_papers.sh
```

The script downloads clearly fetchable papers into:

```text
knowledge/reference/papers/pdf_cache/
```

That cache is ignored by Git.  It is meant for local reading and for research
agents running on this machine, not for redistribution.

For author-version papers that explicitly say personal use only, the script
does not download them by default.  You can opt in locally with:

```bash
./scripts/fetch_reference_papers.sh --include-personal-use
```

Do not commit the resulting cache.

## Paper Roles

- OpenDP: canonical OpenROAD detailed-placement reference.
- NBLG: negotiation-based legalization mechanism reference.
- LEGALM / LEGALM 2.0: ALM-style legalization and partition/refinement
  mechanism reference.
- DREAMPlace: GPU/global-placement and external comparator reference.
- Abacus: row/cluster legalization and minimal-displacement donor reference.

See `paper_sources.yaml` for source links, fetch policy, and notes.

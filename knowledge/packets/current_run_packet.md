# Current Run Packet

- problem: aes_nangate45_legalizer_wl
- primary objective: legalization_hpwl
- selected track: strict_legalizer
- patch surface: tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp

## Key includes
- set_placement_padding
- detailed_placement
- check_placement
- estimate_parasitics -placement

## Key excludes
- balance_row_usage
- improve_placement
- optimize_mirroring

## NBLG / OpenROAD delta highlights
- documented post-optimisation fully active in current code
- deterministic multithreading
- explicit dynamic region adjustment
- full NBLG-style postopt chain

## Selected playbook
- family: negotiation_cost_family
- max-displacement penalty rebalance
- adaptive penalty schedule tweak

## Hard gates
- legality
- metrics.json present
- runtime bounded

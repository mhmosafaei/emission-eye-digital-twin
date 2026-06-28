# GitHub Reference Policy

These repositories are engineering references only for the Emission-Eye simulator upgrade. They are used to study architecture, module boundaries, modeling ideas, and validation discipline. They are not production dependencies and their code must not be copied into this repository.

## Reference repos and what we learn from them

- `ShipNetSim`: route/scenario organization, voyage progression, and environmental-effect simulation patterns.
- `SINTEF FEEMS`: machinery subsystem separation, power/fuel/emissions breakdowns, and energy-balance thinking.
- `Kystverket MarU`: AIS-style pipeline structure, voyage reconstruction, and emissions inventory workflow ideas.
- `Vessel.js`: vessel geometry and draft/trim/displacement object modeling concepts.
- `Data-driven Ship Fuel Efficiency Modeling`: ML-ready feature categories and validation discipline for voyage and time-based splits.

## Copy warning

- Do not copy functions, classes, formulas, comments, or file structure verbatim.
- Do not import reference repositories into runtime.
- Do not add GPL or unclear-license code to the source tree.
- Re-implement useful ideas in original Python modules under `simulator_core/`.

## Current simulator note

The sprint brief references `external/simulator.py` as the source-of-truth simulator. In the current workspace, the preserved simulator file is `simulator.py`, so the extension modules added in this sprint are designed to integrate with that payload shape without replacing it.

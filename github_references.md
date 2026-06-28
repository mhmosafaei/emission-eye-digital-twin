# GitHub References for Emission-Eye Digital CO₂ Twin

**Purpose:** This file gives Codex a controlled list of external GitHub references to study for architecture, modeling ideas, feature design, validation discipline, and module organization.

**Critical rule:** These repositories are **references only**. Do **not** copy third-party code into the Emission-Eye project unless a compatible license is explicitly confirmed and attribution/notice requirements are handled. Prefer original re-implementation in our own Python modules.

**Generated:** 2026-06-28  
**Project context:** Emission-Eye Digital CO₂ Twin — Sea Passage MVP  
**Current simulator location:** `external/simulator.py`

---

## 1. Strict Codex Rules

Codex must follow these rules:

1. Do **not** copy code verbatim from any reference repository.
2. Do **not** import reference repositories into the product runtime.
3. Do **not** add GPL or unlicensed code into the Emission-Eye source tree.
4. Do **not** reproduce third-party comments, file structures, class names, or implementation details verbatim.
5. Use the repositories only to understand architecture, modeling concepts, module boundaries, terminology, validation patterns, and feature categories.
6. Re-implement useful concepts from scratch in clean, original Emission-Eye Python code.
7. Keep all production code inside our own modules such as `app/` and `simulator_core/`.
8. Keep local reference clones, if any, outside production code and preferably inside a Git-ignored folder such as `reference_repos/`.
9. Preserve `external/simulator.py` as the current source-of-truth simulator unless explicitly asked to refactor it.
10. Any future direct reuse of permissively licensed code must preserve copyright notices, license files, and attribution.

---

## 2. Primary GitHub References

| Reference | URL | Known / observed license status | Use only for | What Codex should learn | Copy policy |
|---|---|---|---|---|---|
| ShipNetSim | https://github.com/VTTI-CSM/ShipNetSim | GPL-3.0 according to the repository page | Route/scenario/network simulation | Route graphs, maritime network simulation, vessel motion over routes, environmental effects, pathfinding architecture, scenario thinking | **Reference only. Do not copy code.** Re-implement concepts from scratch. |
| SINTEF FEEMS | https://github.com/SINTEF/FEEMS | Repository page states package-level licensing: `feems` MIT; `MachSysS` and `RunFeemsSim` Apache-2.0 | Marine machinery-system modeling | Main engine, auxiliary systems, fuel/emissions/energy-balance structure, machinery components, subsystem output separation | May be studied closely. Still prefer original implementation. Reuse only with explicit license notice handling. |
| Kystverket MarU | https://github.com/Kystverket/maru | No clear license visible from the repository page checked | AIS-based maritime emissions inventory | AIS data flow, geographic-area enrichment, vessel register enrichment, voyage/phase classification, emissions inventory structure | **Reference only. Do not copy code unless license is confirmed.** |
| Vessel.js | https://github.com/shiplab/vesseljs | MIT according to repository/package information | Vessel geometry, hydrostatics, ship object model | Vessel object structure, hull/draft/displacement/hydrostatics organization, conceptual design data model | Use as conceptual reference. It is JavaScript, so re-implement relevant ideas in original Python. |
| Data-driven Ship Fuel Efficiency Modeling | https://github.com/yuquandu/Data-driven-Ship-Fuel-Efficiency-Modeling | No clear license visible from the repository page checked | ML feature engineering and validation discipline | Feature categories: speed, draft/displacement, trim, weather, sea condition, sensor data, AIS, meteorological data; trained-model workflow; validation thinking | **Reference only. Do not copy code unless license is confirmed.** |

---

## 3. Optional GitHub References

These are useful but lower priority than the primary references.

| Reference | URL | Use only for | Notes | Copy policy |
|---|---|---|---|---|
| G0rocks Marine Vessel Simulator | https://github.com/G0rocks/marine_vessel_simulator | General marine-vessel simulation idea | Public page indicates GPL-3.0. It appears small and less mature than our simulator. | Reference only. Do not copy GPL code. |
| dynamic_speed_optimization | https://github.com/acdick/dynamic_speed_optimization | Ship sensor/weather regression and speed optimization concept | Useful mainly for the idea of using sensor streams + weather records to train predictive models. | Reference only unless license is checked. |

---

## 4. What We Want to Borrow Conceptually

### 4.1 From ShipNetSim

**Concepts to learn:**

- Scenario engine
- Route/network abstraction
- Waypoints and path segments
- Environmental effects along route
- Multiple route alternatives
- Modular simulation architecture
- Energy/emissions simulation over a maritime network

**What to build in our project:**

```text
simulator_core/
  scenarios.py
  routes.py
```

**Original Emission-Eye implementation target:**

- YAML/JSON scenario files
- Route definitions
- Named voyages
- Repeatable random seeds
- Weather severity and wave direction presets
- Single-vessel first, multi-vessel later

---

### 4.2 From SINTEF FEEMS

**Concepts to learn:**

- Machinery-system modeling
- Energy balance
- Main engine and auxiliary system separation
- Power, fuel, emissions per subsystem
- Machinery snapshots
- Hybrid/future-fuel extensibility

**What to build in our project:**

```text
simulator_core/
  machinery.py
```

**Original Emission-Eye implementation target:**

```text
MainEngine
AuxiliaryEngineSystem
BoilerSystem
MachinerySnapshot
```

Each subsystem should output:

```text
power_kw
load_pct
fuel_kg_h
co2_kg_h
ch4_kg_h
n2o_kg_h
nox_kg_h
sox_kg_h
```

---

### 4.3 From Kystverket MarU

**Concepts to learn:**

- AIS-based emissions pipeline
- AIS point enrichment
- Geographic-area classification
- Vessel register enrichment
- Voyage phase classification
- Emissions inventory methodology

**What to build later:**

```text
simulator_core/
  ais_replay.py
```

**Original Emission-Eye implementation target:**

- Read AIS CSV
- Convert AIS track to simulator route steps
- Infer operation phase from speed/location
- Generate simulated emissions over real AIS tracks
- Later compare AIS-estimated emissions with directly measured exhaust emissions

---

### 4.4 From Vessel.js

**Concepts to learn:**

- Vessel object model
- Hull geometry organization
- Draft, trim, displacement, hydrostatics
- Early-stage ship-design data structure

**What to build in our project:**

```text
simulator_core/
  vessel_geometry.py
```

**Original Emission-Eye implementation target:**

```text
VesselGeometry
calculate_mean_draft()
calculate_trim()
estimate_displacement_proxy()
calculate_depth_draft_ratio()
classify_depth_condition()
```

---

### 4.5 From Data-driven Ship Fuel Efficiency Modeling

**Concepts to learn:**

- Feature categories for fuel/emissions prediction
- Sensor data + AIS + meteorological data fusion
- Train/test discipline
- Validation by voyage or time block
- Avoiding leakage from random shuffling
- ML-ready feature exports

**What to build in our project:**

```text
simulator_core/
  feature_store.py
  validation_suite.py
```

**Original Emission-Eye implementation target:**

Export ML-ready rows containing:

```text
timestamp_utc
vessel_id
operation_mode
sog_kn
stw_kn
rpm
engine_load_pct
shaft_power_kw
fuel_flow_kg_h
co2_kg_h
co2_kg_nm
co2_g_kwh
draft_m
trim_m
wind_speed_kn
relative_wind_angle_deg
wave_height_m
depth_m
ukc_m
fouling_multiplier
fuel_type
state_bucket
is_valid_for_training
```

---

## 5. Recommended New Modules for Our Simulator

Create these modules gradually. Do not refactor the whole existing simulator in one step.

```text
simulator_core/
  __init__.py
  scenarios.py
  routes.py
  vessel_geometry.py
  machinery.py
  sensor_model.py
  state_buckets.py
  feature_store.py
  validation_suite.py
  packet_builder.py
  ais_replay.py
```

### Priority Order

| Priority | Module | Why |
|---:|---|---|
| 1 | `state_buckets.py` | Directly supports adaptive baseline comparison. |
| 2 | `feature_store.py` | Directly supports ML twin training. |
| 3 | `sensor_model.py` | Supports future direct CEMS-style exhaust data. |
| 4 | `scenarios.py` | Makes demos repeatable and investor/pilot friendly. |
| 5 | `vessel_geometry.py` | Improves vessel-specific realism. |
| 6 | `machinery.py` | Adds subsystem-level emissions and energy balance. |
| 7 | `validation_suite.py` | Adds credibility, metrics, and benchmark reports. |
| 8 | `routes.py` | Enables more formal route alternatives and path logic. |
| 9 | `ais_replay.py` | Adds real AIS track replay later. |
| 10 | `packet_builder.py` | Cleans final telemetry-packet generation after refactor. |

---

## 6. Codex Instruction Block

Paste this into Codex when asking it to use these references:

```text
Use `reference_notes/github_references.md` as the reference policy.

The repositories listed there are engineering references only. Do not copy code from them. Do not import them into runtime. Do not add GPL or unlicensed code to our source tree. Re-implement useful concepts from scratch in our own original Python modules.

Our existing simulator is located at `external/simulator.py`. Preserve it as the source-of-truth simulator for now.

Build clean, tested, original modules under `simulator_core/` that extend our simulator toward a Digital CO2 Twin. Focus on MVP value:
1. ML-ready features,
2. explainable state buckets,
3. raw exhaust sensor fields,
4. repeatable scenarios,
5. validation summaries.

Stop after the requested sprint and summarize files created, files modified, tests, commands, assumptions, and limitations.
```

---

## 7. Suggested Codex Tasks

### Task A — State Buckets and Feature Store First

```text
Read `reference_notes/github_references.md`.

Do not copy code from reference repositories.

Create:
- `simulator_core/state_buckets.py`
- `simulator_core/feature_store.py`
- tests for both modules

The modules should work with telemetry items produced by `external/simulator.py`.

`state_buckets.py` should generate explainable labels such as:
sea_passage|laden|speed_12_14|load_50_70|head_wind_15_25|wave_1_2m|deep_water|moderate_fouling

`feature_store.py` should convert simulator telemetry items into ML-ready rows for the future Digital CO2 Twin.

Do not build ML yet.
Do not modify `external/simulator.py` unless necessary.
```

### Task B — Raw Sensor Model

```text
Read `reference_notes/github_references.md`.

Do not copy code from reference repositories.

Create `simulator_core/sensor_model.py`.

The module should generate optional raw exhaust sensor fields from existing simulator mass-emissions outputs:
- co2_percent
- ch4_ppm
- n2o_ppm
- o2_percent
- exhaust_flow_kg_h
- exhaust_temp_c
- exhaust_pressure_kpa
- exhaust_moisture_pct
- sensor_drift_pct
- calibration_valid
- condensation_flag
- sensor_quality_flag

Keep formulas simple and configurable.
Add tests.
Do not build hardware integration yet.
```

### Task C — Scenario Config System

```text
Read `reference_notes/github_references.md`.

Do not copy code from reference repositories.

Create `simulator_core/scenarios.py`.

It should load YAML or JSON scenario files defining:
- scenario_name
- vessel_type
- route_name
- fuel_type
- loading_condition
- weather_severity
- wave_direction_mode
- fouling_level
- sensor_quality_mode
- duration_minutes
- random_seed

Add sample scenarios under `scenarios/`.
Add tests.
Do not refactor the whole simulator yet.
```

### Task D — Machinery Layer

```text
Read `reference_notes/github_references.md`.

Do not copy code from reference repositories.

Create `simulator_core/machinery.py`.

Implement original Python classes:
- MainEngine
- AuxiliaryEngineSystem
- BoilerSystem
- MachinerySnapshot

Each subsystem should output:
- power_kw
- load_pct
- fuel_kg_h
- co2_kg_h
- ch4_kg_h
- n2o_kg_h
- nox_kg_h
- sox_kg_h

Keep it simple and compatible with our existing simulator packet.
Add tests.
```

---

## 8. Local Reference Clone Option

The safest option is to use this Markdown file only. If local inspection is needed, clone references into a Git-ignored folder:

```bash
mkdir reference_repos
echo "reference_repos/" >> .gitignore
```

Then clone:

```bash
git clone --depth 1 https://github.com/VTTI-CSM/ShipNetSim.git reference_repos/ShipNetSim_GPL_REFERENCE_ONLY
git clone --depth 1 https://github.com/SINTEF/FEEMS.git reference_repos/FEEMS
git clone --depth 1 https://github.com/Kystverket/maru.git reference_repos/maru_REFERENCE_ONLY
git clone --depth 1 https://github.com/shiplab/vesseljs.git reference_repos/vesseljs
git clone --depth 1 https://github.com/yuquandu/Data-driven-Ship-Fuel-Efficiency-Modeling.git reference_repos/DataDrivenFuel_REFERENCE_ONLY
```

Add this warning to Codex if local references are cloned:

```text
The folder `reference_repos/` is for reading only. Do not import from it. Do not copy code from it. Re-implement concepts from scratch.
```

---

## 9. Notes on License Handling

This file is not legal advice. For production use, license status should be confirmed directly from each repository at the time of use.

Known current handling recommendation:

| Repository | Handling |
|---|---|
| ShipNetSim | GPL-3.0. Reference only. Do not copy into proprietary/commercial codebase. |
| FEEMS | Permissive package-level licenses observed. Can be studied closely; reuse only with proper attribution and license notices. |
| MarU | No clear license visible from checked page. Reference only unless confirmed. |
| Vessel.js | MIT observed. Use as concept reference; direct reuse unlikely because it is JavaScript. |
| Data-driven Ship Fuel Efficiency Modeling | No clear license visible from checked page. Reference only unless confirmed. |

---

## 10. Emission-Eye Differentiator

These references mostly estimate, simulate, or model ship fuel/emissions. Our unique product direction is:

```text
Directly measured exhaust emissions + digital twin + adaptive best-historical baseline.
```

So the simulator upgrades should serve this goal:

```text
Generate realistic, sensor-like, voyage-aware, weather-aware, draft-aware, fouling-aware emissions telemetry that can train and test a direct-measurement Digital CO2 Twin.
```

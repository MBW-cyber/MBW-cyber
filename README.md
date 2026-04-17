# Text-to-3D + Generatieve Simulatie (MVP)

Dit project is een **werkende MVP** van de pipeline die je schetste:

- User Prompt -> LLM Planner
- Asset Generator + Simulation Compiler
- Scene Assembler
- Web Viewer / Backend adapters
- Run Store

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m mbw_cyber.run --input examples/warehouse_spec.json --out runs
```

Na run krijg je in `runs/<run_id>/` o.a.:

- `scene_spec.json`
- `sim_spec.json`
- `assets_manifest.json`
- `scene_manifest.json`
- `trajectory.json`
- `metrics.json`

## Wat dit MVP nu doet

- Parse van declaratieve scene/simulatie JSON
- Asset-pipeline met simpele cache en export metadata
- Simulatie-compile stap met event-graph + deterministic seed
- Scene assembly naar een master scene manifest (incl. collider/LOD placeholders)
- Dummy backend runner (Genesis/Isaac adapter interface)
- Run store voor replay/metrics opslag

## Beperkingen (bewust in MVP)

- Nog geen echte TRELLIS/Hunyuan calls
- Nog geen echte USD/GLB geometry export (wel file manifests)
- Nog geen echte physics engine integratie (wel compile/runtime contract)


# Text-to-3D + Generatieve Simulatie

Dit project levert een **bruikbare pipeline** op basis van jouw architectuur:

- LLM Planner → SceneSpec + SimSpec
- Asset Generator → generatie/retrieval + cache + repair/export metadata
- Simulation Compiler → physics + agent goals + event graph + seed
- Scene Assembler → USD master + GLB export + colliders + LOD metadata
- Backend runtime → **Web Viewer + Rapier** of **Genesis/Isaac profiel**
- Run Store → seeds, trajectories, metrics, replay metadata

## Quickstart

```bash
PYTHONPATH=src python -m mbw_cyber.run \
  --input examples/warehouse_spec.json \
  --out runs \
  --backend web_rapier \
  --duration 12 \
  --hz 10
```

## Output per run

In `runs/<run_id>/`:

- `scene_spec.json`
- `sim_spec.json`
- `assets_manifest.json`
- `compiled_sim.json`
- `scene_manifest.json`
- `trajectory.json`
- `metrics.json`
- `replay.json`
- `run_summary.json`

## Notes

- Dit is een lokale MVP zonder externe model-calls.
- TRELLIS/Hunyuan en echte physics/USD export kunnen via dezelfde interfaces worden aangesloten.

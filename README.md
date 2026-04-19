# Text-to-3D + Generatieve Simulatie

Dit project levert een **bruikbare pipeline** op basis van jouw architectuur:

- LLM Planner → SceneSpec + SimSpec
- Asset Generator → generatie/retrieval + cache + repair/export metadata
- Simulation Compiler → physics + agent goals + event graph + seed
- Scene Assembler → USD master + GLB export + colliders + LOD metadata
- Backend runtime → **Web Viewer + Rapier** of **Genesis/Isaac profiel**
- Run Store → seeds, trajectories, metrics, replay metadata

## Single run

```bash
PYTHONPATH=src python -m mbw_cyber.run \
  --input examples/warehouse_spec.json \
  --out runs \
  --backend web_rapier \
  --duration 12 \
  --hz 10
```

## Experiment matrix (variations + metrics)

```bash
PYTHONPATH=src python -m mbw_cyber.run \
  --input examples/warehouse_spec.json \
  --experiment examples/experiment_spec.json \
  --out runs \
  --backend genesis_isaac \
  --duration 8 \
  --hz 6
```

Voor experiment mode wordt `runs/experiment_matrix.json` aangemaakt met alle variatie-cases, seeds, run directories en gevraagde metrics.

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


## HTTP API

Start server:

```bash
PYTHONPATH=src python -m mbw_cyber.run_api --host 127.0.0.1 --port 8000 --state-root .mbw_api
```

Beschikbare endpoints:

- `GET  /health`
- `POST /scene/generate`
- `POST /scene/validate`
- `POST /scene/compile`
- `POST /assets/generate`
- `POST /scene/assemble`
- `POST /sim/run`
- `POST /sim/replay`
- `GET  /runs`
- `GET  /runs/{id}`
- `GET  /assets/{id}`


## Web UI (React + Rapier)

Er staat nu een eenvoudige webclient in `apps/web` die prompt → generate → compile → run doorloopt en frames visualiseert met een slider.

Start lokaal:

```bash
cd apps/web
npm install
npm run dev
```

Optioneel API URL:

```bash
VITE_API_URL=http://localhost:8000 npm run dev
```

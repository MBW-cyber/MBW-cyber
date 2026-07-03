# SPEC — Datamodellen & Schema's (MVP, as-is)

Dit document is de specificatie van de datamodellen van de huidige MVP-implementatie
van de text-to-3D + generatieve-simulatiepipeline. Het beschrijft het systeem **zoals
het nu is** — een lokale MVP zonder externe model-calls — niet de doelarchitectuur.

## Machineleesbaarheid

Dit bestand is primair bedoeld voor tooling en validatie:

- **Elk `json`-codeblok in dit document is een JSON Schema** (draft 2020-12).
  Er staan geen losse JSON-voorbeelden in `json`-blokken; voorbeelden staan in
  `examples/`.
- Elk schema heeft een uniek `$id` met prefix `mbw-cyber/`, zodat tooling
  schema's op naam kan selecteren.
- De schema's zijn **permissief**: onbekende extra velden zijn toegestaan
  (geen `additionalProperties: false`). Dit spiegelt de implementatie, die
  onbekende sleutels tolereert en ontbrekende velden opvult met defaults.
  `required` staat alleen op velden die de code daadwerkelijk vereist
  (invoer) of altijd wegschrijft (artefacten).
- De test `tests/test_spec.py` extraheert alle `json`-blokken en controleert
  dat elk blok parseert en een geldig JSON Schema is.

## Overzicht

Invoermodellen (door de gebruiker aangeleverd):

| Model | Bron | Voorbeeld |
| --- | --- | --- |
| PromptPayload | invoer van `run_pipeline()` / CLI `--input` | `examples/warehouse_spec.json` |
| ExperimentSpec | invoer van `run_experiment_matrix()` / CLI `--experiment` | `examples/experiment_spec.json` |

Artefacten (door de pipeline gegenereerd, per run in `runs/<run_id>/`):

| Artefact | Producent |
| --- | --- |
| `scene_spec.json` | `LLMPlanner.parse()` → `SceneSpec` |
| `sim_spec.json` | `LLMPlanner.parse()` → `SimSpec` |
| `assets_manifest.json` | `AssetGenerator.materialize()` → `AssetRecord[]` |
| `compiled_sim.json` | `SimulationCompiler.compile()` |
| `scene_manifest.json` | `SceneAssembler.assemble()` |
| `trajectory.json` | backend-runtime (`web_rapier` / `genesis_isaac`) |
| `metrics.json` | `_compute_requested_metrics()` + runmetadata |
| `replay.json` | `run_pipeline()` |
| `run_summary.json` | `RunArtifacts.to_json()` |
| `experiment_matrix.json` | `run_experiment_matrix()` (in `runs/`, niet per run) |

## Invoermodellen

### PromptPayload

De volledige invoer voor één pipeline-run. De planner splitst dit in een
`SceneSpec` (`environment` + `objects`) en een `SimSpec` (`agents` + `events`
+ `seed`). Zonder expliciete `seed` wordt deterministisch een seed afgeleid
uit de SHA-256-hash van de payload. Elk object **moet** een `id` hebben; alle
overige velden zijn optioneel met defaults. `variation_case` wordt alleen
gezet door de experiment-runner (`apply_case()`).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/prompt_payload",
  "title": "PromptPayload",
  "type": "object",
  "properties": {
    "environment": {
      "type": "object",
      "description": "Vrije omgevingsbeschrijving; de MVP interpreteert deze niet inhoudelijk.",
      "properties": {
        "type": { "type": "string" },
        "size": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 },
        "floor_material": { "type": "string" }
      }
    },
    "objects": {
      "type": "array",
      "items": { "$ref": "#/$defs/sceneObject" }
    },
    "agents": {
      "type": "array",
      "items": { "$ref": "#/$defs/agent" }
    },
    "events": {
      "type": "array",
      "items": { "$ref": "#/$defs/event" }
    },
    "seed": {
      "type": "integer",
      "description": "Optioneel; zonder seed wordt er deterministisch één afgeleid uit de payload-hash."
    },
    "variation_case": {
      "type": "object",
      "description": "Alleen gezet door de experiment-runner; de gekozen variatiewaarden van deze case."
    }
  },
  "$defs": {
    "sceneObject": {
      "type": "object",
      "required": ["id"],
      "properties": {
        "id": { "type": "string" },
        "class": { "type": "string", "description": "Default: \"unknown\"." },
        "source": {
          "type": "string",
          "description": "\"generate\" of \"asset_library\"; onbekende waarden worden als asset_library-retrieval behandeld. Default: \"asset_library\".",
          "examples": ["generate", "asset_library"]
        },
        "prompt": { "type": "string", "description": "Default: de waarde van class." },
        "position": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3, "description": "Default: [0, 0, 0]." },
        "rotation": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3, "description": "Default: [0, 0, 0]." },
        "physics": {
          "type": "object",
          "properties": {
            "body": { "type": "string", "description": "Default: \"static\".", "examples": ["static", "dynamic"] },
            "mass": { "type": "number", "description": "Default: 0." },
            "speed_limit": { "type": ["number", "null"], "description": "Default: null." }
          }
        }
      }
    },
    "agent": {
      "type": "object",
      "properties": {
        "id": { "type": "string", "description": "Default in afgeleide structuren: \"agent\" of \"agent_<index>\"." },
        "goal": { "type": "string", "description": "Default: lege string / \"unspecified\"." },
        "policy": { "type": "string", "examples": ["llm_planner"] }
      }
    },
    "event": {
      "type": "object",
      "properties": {
        "t": { "type": "number", "description": "Tijdstip in seconden; default 0 bij sortering van de event graph." },
        "type": { "type": "string", "examples": ["spawn"] },
        "target": { "type": "string" }
      }
    }
  }
}
```

### ExperimentSpec

Invoer voor een variatie-sweep. Per variatiesleutel wordt de lijst waarden als
opties gebruikt (bij precies 2 waarden: beide als discrete opties, niet als
bereik); het cartesisch product van alle opties vormt de cases. Per case wordt
een deterministische seed afgeleid uit `seed` + de case-inhoud.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/experiment_spec",
  "title": "ExperimentSpec",
  "type": "object",
  "properties": {
    "seed": { "type": "integer", "description": "Basisseed voor case-seeds. Default: 0." },
    "variations": {
      "type": "object",
      "description": "Sleutel → lijst van te combineren waarden. Bekende sleutels die apply_case() interpreteert: num_workers, spawn_interval_sec, forklift_speed.",
      "additionalProperties": {
        "type": "array",
        "items": { "type": "number" }
      }
    },
    "metrics": {
      "type": "array",
      "description": "Aangevraagde metrics per run. Ondersteund: task_completion, travel_time, collisions; onbekende namen worden genegeerd.",
      "items": { "type": "string" }
    }
  }
}
```

## Run-artefacten

### scene_spec.json

Serialisatie van de `SceneSpec`-dataclass: het scene-deel van de invoer,
genormaliseerd (beide velden altijd aanwezig, eventueel leeg).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/scene_spec",
  "title": "SceneSpecArtifact",
  "type": "object",
  "required": ["environment", "objects"],
  "properties": {
    "environment": { "type": "object" },
    "objects": {
      "type": "array",
      "items": { "type": "object", "required": ["id"], "properties": { "id": { "type": "string" } } }
    }
  }
}
```

### sim_spec.json

Serialisatie van de `SimSpec`-dataclass: agents, events en de (afgeleide of
expliciete) seed.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/sim_spec",
  "title": "SimSpecArtifact",
  "type": "object",
  "required": ["agents", "events", "seed"],
  "properties": {
    "agents": { "type": "array", "items": { "type": "object" } },
    "events": { "type": "array", "items": { "type": "object" } },
    "seed": { "type": "integer" }
  }
}
```

### assets_manifest.json

Lijst van `AssetRecord`-serialisaties, één per scene-object. `path` wijst naar
het cache-bestand (`<md5>.asset.json`) in `runs/<run_id>/asset_cache/`. In de
MVP zijn `collider`, `lod` en `repaired` vaste waarden.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/assets_manifest",
  "title": "AssetsManifest",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["id", "klass", "source", "path", "collider", "lod", "repaired"],
    "properties": {
      "id": { "type": "string", "description": "Object-id uit de SceneSpec." },
      "klass": { "type": "string", "description": "Objectklasse; veldnaam klass omdat class een Python-keyword is." },
      "source": { "type": "string" },
      "path": { "type": "string", "description": "Pad naar het gecachte asset-metadatabestand." },
      "collider": { "type": "string", "description": "MVP: altijd \"convex_hull\"." },
      "lod": { "type": "string", "description": "MVP: altijd \"auto\"." },
      "repaired": { "type": "boolean", "description": "MVP: altijd true." }
    }
  }
}
```

### compiled_sim.json

Runtime-klaar contract uit de `SimulationCompiler`: physics per object,
agents, doel-mapping en de op tijd gesorteerde event graph.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/compiled_sim",
  "title": "CompiledSim",
  "type": "object",
  "required": ["seed", "physics", "agents", "agent_goals", "event_graph"],
  "properties": {
    "seed": { "type": "integer" },
    "physics": {
      "type": "object",
      "required": ["gravity", "objects"],
      "properties": {
        "gravity": {
          "type": "array",
          "items": { "type": "number" },
          "minItems": 3,
          "maxItems": 3,
          "description": "MVP: altijd [0, -9.81, 0]."
        },
        "objects": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "body", "mass", "position", "speed_limit"],
            "properties": {
              "id": { "type": "string" },
              "body": { "type": "string" },
              "mass": { "type": "number" },
              "position": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 },
              "speed_limit": { "type": ["number", "null"] }
            }
          }
        }
      }
    },
    "agents": { "type": "array", "items": { "type": "object" } },
    "agent_goals": {
      "type": "object",
      "description": "agent-id → goal-string; ontbrekend agent-id wordt agent_<index>.",
      "additionalProperties": { "type": "string" }
    },
    "event_graph": {
      "type": "array",
      "description": "Events oplopend gesorteerd op t (ontbrekende t telt als 0).",
      "items": { "type": "object" }
    }
  }
}
```

### scene_manifest.json

Uitvoer van de `SceneAssembler`: nodes met transform/collider/LOD per asset,
plus verwijzingen naar de export-placeholders (`scene_master.usda`,
`scene_preview.glb.json`) en het viewerprofiel.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/scene_manifest",
  "title": "SceneManifest",
  "type": "object",
  "required": ["environment", "nodes", "exports", "viewer"],
  "properties": {
    "environment": { "type": "object" },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "class", "asset_path", "transform", "collider", "lod"],
        "properties": {
          "id": { "type": "string" },
          "class": { "type": "string" },
          "asset_path": { "type": "string" },
          "transform": {
            "type": "object",
            "required": ["position", "rotation"],
            "properties": {
              "position": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 },
              "rotation": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 }
            }
          },
          "collider": { "type": "string" },
          "lod": { "type": "string" }
        }
      }
    },
    "exports": {
      "type": "object",
      "required": ["usd_master", "glb_preview"],
      "properties": {
        "usd_master": { "type": "string", "description": "Pad naar de USD-placeholder (scene_master.usda)." },
        "glb_preview": { "type": "string", "description": "Pad naar de GLB-preview-placeholder (scene_preview.glb.json)." }
      }
    },
    "viewer": {
      "type": "object",
      "properties": {
        "web": { "type": "string", "description": "MVP: altijd \"rapier\"." },
        "native": { "type": "string", "description": "MVP: altijd \"genesis_isaac\"." }
      }
    }
  }
}
```

### trajectory.json

Ruwe backend-uitvoer: het aantal frames is `duration_s × hz`; per frame de
toestand van elke agent. `progress` loopt deterministisch (seeded) op naar
maximaal 1.0, met backend-afhankelijke jitter (web_rapier 0.02,
genesis_isaac 0.01).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/trajectory",
  "title": "Trajectory",
  "type": "object",
  "required": ["backend", "frames"],
  "properties": {
    "backend": { "type": "string", "enum": ["web_rapier", "genesis_isaac"] },
    "frames": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["frame", "time", "agent_states"],
        "properties": {
          "frame": { "type": "integer", "minimum": 0 },
          "time": { "type": "number", "description": "frame / hz, in seconden." },
          "agent_states": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["id", "goal", "progress"],
              "properties": {
                "id": { "type": "string" },
                "goal": { "type": "string" },
                "progress": { "type": "number", "minimum": 0, "maximum": 1 }
              }
            }
          }
        }
      }
    }
  }
}
```

### metrics.json

Runmetadata plus de berekende waarden voor de aangevraagde metrics. Zonder
expliciete aanvraag wordt alleen `task_completion` berekend; onbekende
metricnamen ontbreken stilzwijgend in `requested_metrics`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/metrics",
  "title": "Metrics",
  "type": "object",
  "required": ["backend", "seed", "frames", "agents", "requested_metrics"],
  "properties": {
    "backend": { "type": "string", "enum": ["web_rapier", "genesis_isaac"] },
    "seed": { "type": "integer" },
    "frames": { "type": "integer", "minimum": 0 },
    "agents": { "type": "integer", "minimum": 0 },
    "requested_metrics": {
      "type": "object",
      "description": "Metricnaam → waarde. Mogelijke sleutels: task_completion (0..1), travel_time (>= 1.0), collisions (>= 0).",
      "additionalProperties": { "type": "number" }
    }
  }
}
```

### replay.json

Minimale metadata om een run deterministisch opnieuw af te spelen.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/replay",
  "title": "Replay",
  "type": "object",
  "required": ["run_id", "seed", "backend", "trajectory_file"],
  "properties": {
    "run_id": { "type": "string" },
    "seed": { "type": "integer" },
    "backend": { "type": "string", "enum": ["web_rapier", "genesis_isaac"] },
    "trajectory_file": { "type": "string", "description": "MVP: altijd \"trajectory.json\", relatief aan de run-directory." }
  }
}
```

### run_summary.json

Serialisatie van `RunArtifacts`: het run-id, de run-directory en alle
weggeschreven artefactbestanden.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/run_summary",
  "title": "RunSummary",
  "type": "object",
  "required": ["run_id", "root", "files"],
  "properties": {
    "run_id": { "type": "string", "description": "Formaat: run_<UTC-timestamp>Z, met suffix _NNN bij botsingen." },
    "root": { "type": "string", "description": "Pad naar de run-directory." },
    "files": {
      "type": "object",
      "description": "Artefactnaam → pad.",
      "additionalProperties": { "type": "string" }
    }
  }
}
```

### experiment_matrix.json

Samenvatting van een experiment-sweep, geschreven in de uitvoer-root (niet in
een run-directory): één rij per case met de case-waarden, de afgeleide seed,
het run-id en de aangevraagde metrics van die run.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "mbw-cyber/experiment_matrix",
  "title": "ExperimentMatrix",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["case_id", "case", "seed", "run_id", "metrics", "run_dir"],
    "properties": {
      "case_id": { "type": "integer", "minimum": 0 },
      "case": {
        "type": "object",
        "description": "Variatiesleutel → gekozen waarde voor deze case.",
        "additionalProperties": { "type": "number" }
      },
      "seed": { "type": "integer" },
      "run_id": { "type": "string" },
      "metrics": {
        "type": "object",
        "description": "De requested_metrics uit metrics.json van deze run.",
        "additionalProperties": { "type": "number" }
      },
      "run_dir": { "type": "string" }
    }
  }
}
```

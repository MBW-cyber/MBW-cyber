import { useMemo, useState, type CSSProperties } from "react"

// Zelfstandig experiment-scherm rond POST /experiment/run. Bewust niet
// verweven met client.ts of scene/types.ts zodat het los te verwijderen is.

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

const DEFAULT_BASE = JSON.stringify(
  {
    environment: { type: "warehouse", size: [20, 12, 6] },
    objects: [
      {
        id: "forklift_1",
        class: "forklift",
        source: "generate",
        prompt: "yellow electric forklift, industrial, realistic",
        position: [2, 0, 4],
        physics: { body: "dynamic", mass: 1200 },
      },
      {
        id: "pallet_stack_1",
        class: "pallet_stack",
        source: "asset_library",
        position: [6, 0, 4],
        physics: { body: "dynamic", mass: 300 },
      },
    ],
    agents: [{ id: "worker_1", goal: "move pallets to loading zone", policy: "llm_planner" }],
  },
  null,
  2
)

const DEFAULT_VARIATIONS = "num_workers: 2, 5\nspawn_interval_sec: 10, 45\nforklift_speed: 1.0, 2.4"
const ALL_METRICS = ["collisions", "task_completion", "travel_time"]

type MatrixRow = {
  case_id: number
  case: Record<string, number>
  seed: number
  run_id: string
  metrics: Record<string, number>
  run_dir: string
}

function parseVariations(text: string): Record<string, number[]> {
  const result: Record<string, number[]> = {}
  for (const line of text.split("\n")) {
    const [key, values] = line.split(":")
    if (!key?.trim() || !values) continue
    const parsed = values
      .split(",")
      .map((v) => Number(v.trim()))
      .filter((v) => Number.isFinite(v))
    if (parsed.length > 0) result[key.trim()] = parsed
  }
  return result
}

export function ExperimentLab({ onBack }: { onBack: () => void }) {
  const [baseText, setBaseText] = useState(DEFAULT_BASE)
  const [variationsText, setVariationsText] = useState(DEFAULT_VARIATIONS)
  const [seed, setSeed] = useState("18442")
  const [metrics, setMetrics] = useState<string[]>([...ALL_METRICS])
  const [matrix, setMatrix] = useState<MatrixRow[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const variations = useMemo(() => parseVariations(variationsText), [variationsText])
  const caseCount = Object.values(variations).reduce((acc, v) => acc * v.length, 1)
  const variationKeys = Object.keys(variations).sort()

  function toggleMetric(name: string) {
    setMetrics((m) => (m.includes(name) ? m.filter((x) => x !== name) : [...m, name]))
  }

  async function handleRun() {
    setLoading(true)
    setError(null)
    try {
      const base = JSON.parse(baseText)
      const res = await fetch(`${API}/experiment/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base,
          experiment: { seed: Number(seed) || 0, variations, metrics },
          backend: "web_rapier",
          duration: 6,
          hz: 5,
        }),
      })
      if (!res.ok) throw new Error("experiment run failed")
      const data = (await res.json()) as { matrix: MatrixRow[] }
      setMatrix(data.matrix)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Onbekende fout")
    } finally {
      setLoading(false)
    }
  }

  const metricMax: Record<string, number> = {}
  for (const m of metrics) {
    metricMax[m] = Math.max(...(matrix ?? []).map((r) => r.metrics[m] ?? 0), 0)
  }
  const bestCollisions =
    matrix && metrics.includes("collisions")
      ? Math.min(...matrix.map((r) => r.metrics.collisions ?? Infinity))
      : null

  return (
    <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", height: "100vh" }}>
      <div style={{ padding: 16, borderRight: "1px solid #ddd", overflowY: "auto" }}>
        <button onClick={onBack}>← Studio</button>
        <h2>Experiment Lab</h2>

        <h4 style={{ marginBottom: 4 }}>Basisscene (JSON)</h4>
        <textarea
          value={baseText}
          onChange={(e) => setBaseText(e.target.value)}
          rows={12}
          style={{ width: "100%", fontFamily: "monospace", fontSize: 11 }}
        />

        <h4 style={{ marginBottom: 4 }}>Variaties (naam: waarde, waarde)</h4>
        <textarea
          value={variationsText}
          onChange={(e) => setVariationsText(e.target.value)}
          rows={4}
          style={{ width: "100%", fontFamily: "monospace", fontSize: 12 }}
        />

        <h4 style={{ marginBottom: 4 }}>Metrics</h4>
        {ALL_METRICS.map((m) => (
          <label key={m} style={{ display: "block" }}>
            <input type="checkbox" checked={metrics.includes(m)} onChange={() => toggleMetric(m)} /> {m}
          </label>
        ))}

        <h4 style={{ marginBottom: 4 }}>Seed</h4>
        <input value={seed} onChange={(e) => setSeed(e.target.value)} style={{ width: "100%" }} />

        <button onClick={handleRun} disabled={loading || caseCount === 0} style={{ marginTop: 12, width: "100%" }}>
          {loading ? "Bezig..." : `Start sweep · ${caseCount} cases`}
        </button>

        {error && (
          <p style={{ color: "#b00020", marginTop: 12 }} role="alert">
            {error}
          </p>
        )}
      </div>

      <div style={{ padding: 16, overflowY: "auto" }}>
        {!matrix && <p>Nog geen resultaten. Configureer links een sweep en start.</p>}
        {matrix && (
          <>
            <h3>
              Resultaten — {matrix.length} runs
              {bestCollisions !== null && " · beste case gemarkeerd (laagste collisions)"}
            </h3>
            <table style={{ borderCollapse: "collapse", fontSize: 13, width: "100%" }}>
              <thead>
                <tr>
                  <th style={cell}>case</th>
                  {variationKeys.map((k) => (
                    <th key={k} style={cell}>
                      {k}
                    </th>
                  ))}
                  <th style={cell}>seed</th>
                  {metrics.map((m) => (
                    <th key={m} style={cell}>
                      {m}
                    </th>
                  ))}
                  <th style={cell}>run</th>
                </tr>
              </thead>
              <tbody>
                {matrix.map((row) => {
                  const isBest = bestCollisions !== null && row.metrics.collisions === bestCollisions
                  return (
                    <tr key={row.case_id} style={isBest ? { background: "#fdf3d7" } : undefined}>
                      <td style={cell}>c{row.case_id}</td>
                      {variationKeys.map((k) => (
                        <td key={k} style={{ ...cell, textAlign: "right" }}>
                          {row.case[k]}
                        </td>
                      ))}
                      <td style={{ ...cell, fontFamily: "monospace", fontSize: 11 }}>{row.seed}</td>
                      {metrics.map((m) => (
                        <td key={m} style={{ ...cell, textAlign: "right" }}>
                          <span
                            style={{
                              display: "inline-block",
                              width: Math.round(((row.metrics[m] ?? 0) / (metricMax[m] || 1)) * 60),
                              height: 6,
                              background: "#2a78d6",
                              marginRight: 6,
                              verticalAlign: "middle",
                            }}
                          />
                          {row.metrics[m]?.toFixed(3) ?? "—"}
                        </td>
                      ))}
                      <td style={{ ...cell, fontFamily: "monospace", fontSize: 11 }}>{row.run_id}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}

const cell: CSSProperties = {
  border: "1px solid #ddd",
  padding: "4px 8px",
  textAlign: "left",
  whiteSpace: "nowrap",
}

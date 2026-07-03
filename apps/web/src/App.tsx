import { useState } from "react"
import { generateScene, compileScene, runSim } from "./api/client"
import { SceneViewer } from "./components/SceneViewer"
import { ExperimentLab } from "./experiments/ExperimentLab"
import type { CompiledScene, RunResult } from "./scene/types"

export default function App() {
  const [showLab, setShowLab] = useState(false)
  const [prompt, setPrompt] = useState("Bouw een magazijn met een heftruck en drie pallets")
  const [compiled, setCompiled] = useState<CompiledScene | null>(null)
  const [run, setRun] = useState<RunResult | null>(null)
  const [frameIndex, setFrameIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleBuild() {
    setLoading(true)
    setError(null)
    try {
      const generated = await generateScene(prompt, 42)
      const compiledScene = await compileScene(generated.scene, generated.sim)
      setCompiled(compiledScene)

      const runResult = await runSim(compiledScene)
      setRun(runResult)
      setFrameIndex(0)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Onbekende fout")
    } finally {
      setLoading(false)
    }
  }

  if (showLab) return <ExperimentLab onBack={() => setShowLab(false)} />

  return (
    <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", height: "100vh" }}>
      <div style={{ padding: 16, borderRight: "1px solid #ddd" }}>
        <h2>Text-to-3D Sim</h2>
        <button onClick={() => setShowLab(true)} style={{ marginBottom: 12 }}>
          Experiment Lab →
        </button>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={10}
          style={{ width: "100%" }}
        />
        <button onClick={handleBuild} disabled={loading}>
          {loading ? "Bezig..." : "Genereer"}
        </button>

        {error && (
          <p style={{ color: "#b00020", marginTop: 12 }} role="alert">
            {error}
          </p>
        )}

        {run && (
          <>
            <h3>Metrics</h3>
            <pre>{JSON.stringify(run.metrics, null, 2)}</pre>
            <input
              type="range"
              min={0}
              max={Math.max((run.frames?.length ?? 1) - 1, 0)}
              value={frameIndex}
              onChange={(e) => setFrameIndex(Number(e.target.value))}
              style={{ width: "100%" }}
            />
            <div>Frame: {frameIndex}</div>
          </>
        )}
      </div>

      <div>
        <SceneViewer compiled={compiled} run={run} frameIndex={frameIndex} />
      </div>
    </div>
  )
}

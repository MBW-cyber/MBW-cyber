import type { CompiledScene, RunResult } from "../scene/types"

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

export async function generateScene(prompt: string, seed = 42) {
  const res = await fetch(`${API}/scene/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, seed }),
  })
  if (!res.ok) throw new Error("scene generation failed")
  return res.json() as Promise<{ scene: unknown; sim: unknown }>
}

export async function compileScene(scene: unknown, sim: unknown) {
  const res = await fetch(`${API}/scene/compile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scene, sim }),
  })
  if (!res.ok) throw new Error("scene compile failed")
  return (await res.json()) as CompiledScene
}

export async function runSim(compiled: CompiledScene) {
  const res = await fetch(`${API}/sim/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(compiled),
  })
  if (!res.ok) throw new Error("sim failed")
  return (await res.json()) as RunResult
}

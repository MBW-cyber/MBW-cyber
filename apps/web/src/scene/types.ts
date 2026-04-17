export type Vec3 = [number, number, number]

export type CompiledObject = {
  id: string
  kind: string
  position: Vec3
  rotation: Vec3
  scale: Vec3
  collider: Record<string, unknown>
  render: {
    type: "primitive" | "asset"
    primitive?: "box" | "sphere" | "cylinder" | "plane"
    size?: Vec3
    uri?: string
    material?: {
      color?: string
      roughness?: number
      metalness?: number
    }
  }
  physics: {
    body: "fixed" | "dynamic" | "kinematic"
    mass?: number
  }
}

export type CompiledScene = {
  scene_id: string
  objects: CompiledObject[]
  sim: {
    duration_sec: number
    timestep: number
  }
}

export type RunFrame = {
  t: number
  transforms: Record<string, { position: Vec3; rotation: Vec3 }>
}

export type RunResult = {
  run_id: string
  scene_id: string
  frames: RunFrame[]
  metrics: Record<string, number>
}

import { Canvas } from "@react-three/fiber"
import { Physics, RigidBody, CuboidCollider } from "@react-three/rapier"
import { useMemo } from "react"
import type { CompiledObject, CompiledScene, RunFrame, RunResult } from "../scene/types"

function PrimitiveObject({ obj, frame }: { obj: CompiledObject; frame?: RunFrame }) {
  const position = frame?.transforms?.[obj.id]?.position ?? obj.position
  const rotation = frame?.transforms?.[obj.id]?.rotation ?? obj.rotation
  const size = obj.render.size ?? [1, 1, 1]
  const material = obj.render.material ?? {}

  return (
    <RigidBody
      type={obj.physics.body === "fixed" ? "fixed" : "dynamic"}
      position={position}
      rotation={rotation}
    >
      <CuboidCollider args={[size[0] / 2, size[1] / 2, size[2] / 2]} />
      <mesh castShadow receiveShadow>
        <boxGeometry args={size} />
        <meshStandardMaterial
          color={material.color ?? "#cccccc"}
          roughness={material.roughness ?? 0.8}
          metalness={material.metalness ?? 0.1}
        />
      </mesh>
    </RigidBody>
  )
}

export function SceneViewer({
  compiled,
  run,
  frameIndex,
}: {
  compiled: CompiledScene | null
  run: RunResult | null
  frameIndex: number
}) {
  const frame = useMemo(() => run?.frames?.[frameIndex], [run, frameIndex])

  if (!compiled) return <div>Geen scene</div>

  return (
    <Canvas camera={{ position: [12, 10, 12], fov: 50 }} shadows>
      <ambientLight intensity={0.7} />
      <directionalLight position={[10, 10, 5]} intensity={1.2} castShadow />
      <Physics>
        {compiled.objects.map((obj) => (
          <PrimitiveObject key={obj.id} obj={obj} frame={frame} />
        ))}
      </Physics>
      <gridHelper args={[50, 50]} />
    </Canvas>
  )
}

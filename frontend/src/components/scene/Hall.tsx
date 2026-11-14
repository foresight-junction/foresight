import { useLayoutEffect, useMemo, useRef } from 'react'
import { Object3D, Quaternion, Vector3, type InstancedMesh } from 'three'
import { DEPARTMENTS, DEPARTMENT_COLOR, PALETTE } from '../../departments'
import { HALL_RADIUS, approachPoint } from '../../sceneLayout'

const PLANTERS: [number, number][] = [
  [-3.9, 10.8],
  [3.9, 10.8],
  [-11.1, 3.7],
  [-10.1, -5.5],
  [-4.4, -12.5],
  [4.4, -12.5],
  [10.1, -5.5],
  [11.3, 3.4],
]
const EMBLEM_RADIUS = 1.8
const SCRATCH_OBJECT = new Object3D()

function Planters() {
  const pots = useRef<InstancedMesh>(null)
  const leaves = useRef<InstancedMesh>(null)
  useLayoutEffect(() => {
    if (!pots.current || !leaves.current) return
    PLANTERS.forEach(([x, z], i) => {
      SCRATCH_OBJECT.position.set(x, 0.3, z)
      SCRATCH_OBJECT.rotation.set(0, i * 0.7, 0)
      SCRATCH_OBJECT.scale.setScalar(1)
      SCRATCH_OBJECT.updateMatrix()
      pots.current?.setMatrixAt(i, SCRATCH_OBJECT.matrix)
      SCRATCH_OBJECT.position.set(x, 1.05, z)
      SCRATCH_OBJECT.scale.set(1, 1.15 + (i % 3) * 0.12, 1)
      SCRATCH_OBJECT.updateMatrix()
      leaves.current?.setMatrixAt(i, SCRATCH_OBJECT.matrix)
    })
    pots.current.instanceMatrix.needsUpdate = true
    leaves.current.instanceMatrix.needsUpdate = true
    pots.current.computeBoundingSphere()
    leaves.current.computeBoundingSphere()
  }, [])
  return (
    <>
      <instancedMesh ref={pots} args={[undefined, undefined, PLANTERS.length]} castShadow receiveShadow>
        <cylinderGeometry args={[0.42, 0.34, 0.6, 14]} />
        <meshStandardMaterial color="#ffffff" roughness={0.55} />
      </instancedMesh>
      <instancedMesh ref={leaves} args={[undefined, undefined, PLANTERS.length]} castShadow>
        <icosahedronGeometry args={[0.62, 0]} />
        <meshStandardMaterial color="#9cc5a1" roughness={0.8} flatShading />
      </instancedMesh>
    </>
  )
}

function Wayfinding() {
  const lines = useMemo(
    () =>
      DEPARTMENTS.map((department) => {
        const end = approachPoint(department)
        end.y = 0
        const dir = end.clone().setY(0).normalize()
        const start = dir.clone().multiplyScalar(EMBLEM_RADIUS + 0.35)
        const length = start.distanceTo(end)
        const mid = start.clone().add(end).multiplyScalar(0.5)
        const q = new Quaternion().setFromUnitVectors(new Vector3(0, 0, 1), dir)
        return { department, mid, q, length, tick: dir.clone().multiplyScalar(EMBLEM_RADIUS - 0.25) }
      }),
    [],
  )
  return (
    <>
      {lines.map(({ department, mid, q, length, tick }) => (
        <group key={department}>
          <mesh position={[mid.x, 0.006, mid.z]} quaternion={q} receiveShadow>
            <boxGeometry args={[0.1, 0.01, length]} />
            <meshStandardMaterial color={DEPARTMENT_COLOR[department]} transparent opacity={0.38} roughness={0.8} />
          </mesh>
          <mesh position={[tick.x, 0.13, tick.z]} quaternion={q}>
            <boxGeometry args={[0.16, 0.03, 0.36]} />
            <meshStandardMaterial color={DEPARTMENT_COLOR[department]} emissive={DEPARTMENT_COLOR[department]} emissiveIntensity={0.25} />
          </mesh>
        </group>
      ))}
    </>
  )
}

export function Hall() {
  return (
    <group>
      <mesh position={[0, -0.03, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[90, 64]} />
        <meshStandardMaterial color={PALETTE.ground} roughness={0.95} />
      </mesh>
      <mesh position={[0, -0.04, 0]} receiveShadow>
        <cylinderGeometry args={[HALL_RADIUS + 0.7, HALL_RADIUS + 0.9, 0.08, 96]} />
        <meshStandardMaterial color={PALETTE.floor} roughness={0.7} />
      </mesh>
      <mesh position={[0, 0.002, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[HALL_RADIUS + 0.35, HALL_RADIUS + 0.5, 128]} />
        <meshStandardMaterial color="#dbe2ec" roughness={0.8} />
      </mesh>
      <mesh position={[0, 0.002, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[4.7, 4.8, 96]} />
        <meshStandardMaterial color="#dfe5ee" roughness={0.8} />
      </mesh>
      <mesh position={[0, 0.06, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[EMBLEM_RADIUS, EMBLEM_RADIUS + 0.12, 0.12, 64]} />
        <meshStandardMaterial color="#ffffff" roughness={0.45} />
      </mesh>
      <mesh position={[0, 0.125, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.1, 1.22, 6]} />
        <meshStandardMaterial color={PALETTE.ink} roughness={0.5} />
      </mesh>
      <mesh position={[0, 0.125, 0]} rotation={[-Math.PI / 2, 0, Math.PI / 6]}>
        <circleGeometry args={[0.42, 6]} />
        <meshStandardMaterial color={DEPARTMENT_COLOR.protection} emissive={DEPARTMENT_COLOR.protection} emissiveIntensity={0.3} />
      </mesh>
      <Wayfinding />
      <Planters />
    </group>
  )
}

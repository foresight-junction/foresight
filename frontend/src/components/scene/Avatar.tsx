import { RoundedBox } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useRef } from 'react'
import { CatmullRomCurve3, Color, Vector3, type Group, type MeshStandardMaterial } from 'three'
import { DEPARTMENT_COLOR } from '../../departments'
import { approachPoint, facingYaw, standPoint } from '../../sceneLayout'
import type { AvatarMove } from '../../state/applyEvent'
import { avatarRuntime, resetAvatarRuntime } from '../../state/avatarRuntime'
import { useSpectatorStore } from '../../state/store'
import type { Department } from '../../types'

const MAX_PENDING_BEFORE_SNAP = 5
const WALK_SPEED = 4.2
const DWELL_SECONDS = 0.35
const INNER_WAYPOINT_RADIUS = 4.3

interface Walk {
  move: AvatarMove
  curve: CatmullRomCurve3
  duration: number
  elapsed: number
}

const SCRATCH_TANGENT = new Vector3()
const SCRATCH_COLOR = new Color()

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

function lerpAngle(from: number, to: number, alpha: number): number {
  let diff = (to - from) % (Math.PI * 2)
  if (diff > Math.PI) diff -= Math.PI * 2
  if (diff < -Math.PI) diff += Math.PI * 2
  return from + diff * alpha
}

function buildWalk(from: Vector3, fromDepartment: Department, move: AvatarMove): Walk {
  const exit = approachPoint(fromDepartment)
  const entry = approachPoint(move.department)
  const points = [from.clone(), exit]
  const a = Math.atan2(exit.x, exit.z)
  const b = Math.atan2(entry.x, entry.z)
  let span = Math.abs(b - a)
  if (span > Math.PI) span = Math.PI * 2 - span
  if (span > Math.PI * 0.55) {
    const mid = new Vector3(exit.x + entry.x, 0, exit.z + entry.z)
    if (mid.lengthSq() < 0.01) mid.set(-exit.z, 0, exit.x)
    mid.setLength(INNER_WAYPOINT_RADIUS)
    points.push(mid)
  }
  points.push(entry, standPoint(move.department))
  const curve = new CatmullRomCurve3(points, false, 'centripetal', 0.5)
  const duration = Math.min(6, Math.max(0.9, curve.getLength() / WALK_SPEED))
  return { move, curve, duration, elapsed: 0 }
}

export function Avatar() {
  const root = useRef<Group>(null)
  const body = useRef<Group>(null)
  const legLeft = useRef<Group>(null)
  const legRight = useRef<Group>(null)
  const armLeft = useRef<Group>(null)
  const armRight = useRef<Group>(null)
  const antenna = useRef<MeshStandardMaterial>(null)
  const chest = useRef<MeshStandardMaterial>(null)
  const walk = useRef<Walk | null>(null)
  const consumed = useRef(-1)
  const dwell = useRef(0)
  const department = useRef<Department>('reception')
  const epoch = useRef(0)
  const stride = useRef(0)

  useFrame((state, delta) => {
    const dt = Math.min(delta, 0.1)
    const group = root.current
    if (!group) return
    const { avatar, epoch: storeEpoch } = useSpectatorStore.getState()

    if (storeEpoch !== epoch.current) {
      epoch.current = storeEpoch
      resetAvatarRuntime()
      consumed.current = -1
      walk.current = null
      dwell.current = 0
      department.current = 'reception'
    }

    let pending = avatar.moves.filter((m) => m.index > consumed.current)
    if (!walk.current && dwell.current <= 0 && pending.length > 0) {
      if (pending.length > MAX_PENDING_BEFORE_SNAP) {
        const snap = pending[pending.length - 2]
        standPoint(snap.department, avatarRuntime.position)
        avatarRuntime.yaw = facingYaw(snap.department)
        consumed.current = snap.index
        avatarRuntime.arrivedMoveIndex = snap.index
        department.current = snap.department
        pending = pending.slice(-1)
      }
      const next = pending[0]
      if (next.department === department.current) {
        consumed.current = next.index
        avatarRuntime.arrivedMoveIndex = next.index
      } else {
        walk.current = buildWalk(avatarRuntime.position, department.current, next)
      }
    }

    const hurry = 1 + 0.6 * Math.max(0, pending.length - 1)
    if (dwell.current > 0) dwell.current -= dt * hurry

    let targetYaw = facingYaw(department.current)
    const current = walk.current
    if (current) {
      current.elapsed += dt * hurry
      const t = Math.min(1, current.elapsed / current.duration)
      const u = easeInOutCubic(t)
      current.curve.getPointAt(u, avatarRuntime.position)
      current.curve.getTangentAt(u, SCRATCH_TANGENT)
      targetYaw = Math.atan2(SCRATCH_TANGENT.x, SCRATCH_TANGENT.z)
      if (t >= 1) {
        consumed.current = current.move.index
        avatarRuntime.arrivedMoveIndex = current.move.index
        department.current = current.move.department
        walk.current = null
        dwell.current = DWELL_SECONDS
      }
    }
    avatarRuntime.walking = walk.current !== null
    avatarRuntime.yaw = lerpAngle(avatarRuntime.yaw, targetYaw, 1 - Math.exp(-dt * 9))

    group.position.copy(avatarRuntime.position)
    group.rotation.y = avatarRuntime.yaw

    const time = state.clock.elapsedTime
    const walking = avatarRuntime.walking
    stride.current += (walking ? 1 : -1) * dt * 5
    stride.current = Math.min(1, Math.max(0, stride.current))
    const swing = Math.sin(time * 10) * stride.current
    if (body.current) body.current.position.y = walking ? Math.abs(Math.sin(time * 10)) * 0.05 : Math.sin(time * 2.2) * 0.035
    if (legLeft.current) legLeft.current.rotation.x = swing * 0.6
    if (legRight.current) legRight.current.rotation.x = -swing * 0.6
    if (armLeft.current) armLeft.current.rotation.x = -swing * 0.5 - 0.15
    if (armRight.current) armRight.current.rotation.x = swing * 0.5 - 0.15

    const accent = DEPARTMENT_COLOR[walk.current ? walk.current.move.department : department.current]
    if (antenna.current) {
      SCRATCH_COLOR.set(accent)
      antenna.current.emissive.lerp(SCRATCH_COLOR, 1 - Math.exp(-dt * 6))
      antenna.current.color.copy(antenna.current.emissive)
    }
    if (chest.current) chest.current.emissiveIntensity = walking ? 1.2 : 0.6 + 0.2 * Math.sin(time * 2.2)
  })

  return (
    <group ref={root}>
      <group ref={body} scale={1.2}>
        <group ref={legLeft} position={[-0.2, 0.45, 0]}>
          <mesh position={[0, -0.22, 0]} castShadow>
            <capsuleGeometry args={[0.11, 0.24, 4, 10]} />
            <meshStandardMaterial color="#334155" roughness={0.4} />
          </mesh>
        </group>
        <group ref={legRight} position={[0.2, 0.45, 0]}>
          <mesh position={[0, -0.22, 0]} castShadow>
            <capsuleGeometry args={[0.11, 0.24, 4, 10]} />
            <meshStandardMaterial color="#334155" roughness={0.4} />
          </mesh>
        </group>
        <RoundedBox args={[0.8, 0.74, 0.62]} radius={0.24} smoothness={4} position={[0, 0.86, 0]} castShadow>
          <meshStandardMaterial color="#24324a" roughness={0.38} metalness={0.15} />
        </RoundedBox>
        <mesh position={[0, 0.9, 0.315]}>
          <circleGeometry args={[0.085, 20]} />
          <meshStandardMaterial ref={chest} color="#38bdf8" emissive="#38bdf8" emissiveIntensity={0.6} toneMapped={false} />
        </mesh>
        <group ref={armLeft} position={[-0.5, 1.1, 0]}>
          <mesh position={[0, -0.2, 0.05]} castShadow>
            <capsuleGeometry args={[0.085, 0.3, 4, 10]} />
            <meshStandardMaterial color="#e2e8f0" roughness={0.35} />
          </mesh>
        </group>
        <group ref={armRight} position={[0.5, 1.1, 0]}>
          <mesh position={[0, -0.2, 0.05]} castShadow>
            <capsuleGeometry args={[0.085, 0.3, 4, 10]} />
            <meshStandardMaterial color="#e2e8f0" roughness={0.35} />
          </mesh>
        </group>
        <RoundedBox args={[0.92, 0.6, 0.74]} radius={0.24} smoothness={4} position={[0, 1.56, 0]} castShadow>
          <meshStandardMaterial color="#ffffff" roughness={0.3} metalness={0.05} />
        </RoundedBox>
        <RoundedBox args={[0.74, 0.3, 0.1]} radius={0.1} smoothness={3} position={[0, 1.58, 0.34]}>
          <meshStandardMaterial color="#0b1220" roughness={0.18} metalness={0.6} />
        </RoundedBox>
        {[-0.15, 0.15].map((x) => (
          <mesh key={x} position={[x, 1.59, 0.395]}>
            <boxGeometry args={[0.13, 0.06, 0.01]} />
            <meshStandardMaterial color="#7dd3fc" emissive="#38bdf8" emissiveIntensity={1.6} toneMapped={false} />
          </mesh>
        ))}
        <mesh position={[0, 2.0, 0]}>
          <cylinderGeometry args={[0.022, 0.022, 0.28, 8]} />
          <meshStandardMaterial color="#94a3b8" />
        </mesh>
        <mesh position={[0, 2.17, 0]}>
          <sphereGeometry args={[0.075, 16, 12]} />
          <meshStandardMaterial
            ref={antenna}
            color={DEPARTMENT_COLOR.reception}
            emissive={DEPARTMENT_COLOR.reception}
            emissiveIntensity={1.4}
            toneMapped={false}
          />
        </mesh>
      </group>
    </group>
  )
}

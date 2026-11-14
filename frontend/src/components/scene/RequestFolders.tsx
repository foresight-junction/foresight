import { useFrame } from '@react-three/fiber'
import { useLayoutEffect, useMemo, useRef } from 'react'
import { Color, Object3D, Vector3, type Group, type InstancedMesh, type Mesh, type MeshStandardMaterial } from 'three'
import { PALETTE } from '../../departments'
import {
  DEPARTMENT_LAYOUT,
  DESK_SPAWN_LOCAL,
  FOLDER_SIZE,
  PARKED_LOCAL,
  PLATFORM_HEIGHT,
  QUEUE_PILE_CAPACITY,
  QUEUE_PILE_LOCAL,
  TRAY_TOP,
  TRAY_X,
  TRAY_Z,
  toWorld,
} from '../../sceneLayout'
import type { RequestView } from '../../state/applyEvent'
import { avatarRuntime } from '../../state/avatarRuntime'
import { useSpectatorStore } from '../../state/store'
import { SceneLabel } from './SceneLabel'

const SCRATCH_TARGET = new Vector3()
const SCRATCH_COLOR = new Color()
const SCRATCH_OBJECT = new Object3D()
const NEUTRAL = new Color(PALETTE.neutralStamp)
const CORRECT = new Color(PALETTE.correct)
const INCORRECT = new Color(PALETTE.incorrect)
const LEAK = new Color(PALETTE.leak)
const MAX_QUEUE = QUEUE_PILE_LOCAL.length * QUEUE_PILE_CAPACITY

function jitter(seed: number, scale: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return (x - Math.floor(x) - 0.5) * scale
}

function hashId(id: string): number {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0
  return Math.abs(h) + 1
}

function stampColor(request: RequestView, out: Color): Color {
  if (request.leaks.length > 0 || (request.verdict && request.verdict.leak !== 'none')) return out.copy(LEAK)
  if (request.verdict) return out.copy(request.verdict.correct ? CORRECT : INCORRECT)
  return out.copy(NEUTRAL)
}

function lerpAngle(from: number, to: number, alpha: number): number {
  let diff = (to - from) % (Math.PI * 2)
  if (diff > Math.PI) diff -= Math.PI * 2
  if (diff < -Math.PI) diff += Math.PI * 2
  return from + diff * alpha
}

interface FolderProps {
  id: string
  slot: number
}

function Folder({ id, slot }: FolderProps) {
  const request = useSpectatorStore((s) => s.requests[id])
  const isCurrent = useSpectatorStore((s) => s.currentRequestId === id)
  const group = useRef<Group>(null)
  const stamp = useRef<Mesh>(null)
  const stampMaterial = useRef<MeshStandardMaterial>(null)
  const initialized = useRef(false)
  const spawn = useMemo(() => toWorld('reception', DESK_SPAWN_LOCAL), [])
  const parked = useMemo(() => toWorld('reception', PARKED_LOCAL), [])
  const seed = useMemo(() => hashId(id), [id])

  useFrame((_, delta) => {
    const g = group.current
    if (!g || !request) return
    const dt = Math.min(delta, 0.1)
    if (!initialized.current) {
      g.position.copy(spawn)
      g.rotation.y = DEPARTMENT_LAYOUT.reception.yaw
      g.scale.setScalar(0.01)
      initialized.current = true
    }
    const arrived = avatarRuntime.arrivedMoveIndex
    const decision = request.decision
    let yaw = DEPARTMENT_LAYOUT.reception.yaw
    let rate = 6
    if (decision && arrived >= decision.moveIndex) {
      toWorld(
        'decision',
        [TRAY_X[decision.action] + jitter(seed, 0.12), TRAY_TOP + slot * (FOLDER_SIZE[1] + 0.008), TRAY_Z + jitter(seed + 7, 0.1)],
        SCRATCH_TARGET,
      )
      yaw = DEPARTMENT_LAYOUT.decision.yaw + jitter(seed + 3, 0.35)
      rate = 5
    } else if (arrived < request.receivedMoveIndex) {
      SCRATCH_TARGET.copy(spawn)
    } else if (!isCurrent && !decision) {
      SCRATCH_TARGET.copy(parked)
    } else {
      const p = avatarRuntime.position
      const ay = avatarRuntime.yaw
      SCRATCH_TARGET.set(p.x + Math.sin(ay) * 0.66, p.y + 0.98, p.z + Math.cos(ay) * 0.66)
      yaw = ay
      rate = 16
    }
    g.position.lerp(SCRATCH_TARGET, 1 - Math.exp(-dt * rate))
    g.rotation.y = lerpAngle(g.rotation.y, yaw, 1 - Math.exp(-dt * rate))
    const s = g.scale.x + (1 - g.scale.x) * (1 - Math.exp(-dt * 7))
    g.scale.setScalar(s)
    if (stamp.current && stampMaterial.current) {
      const visible = decision !== null && arrived >= decision.moveIndex
      const sc = stamp.current.scale.x + ((visible ? 1 : 0.001) - stamp.current.scale.x) * (1 - Math.exp(-dt * 9))
      stamp.current.scale.setScalar(sc)
      stampColor(request, SCRATCH_COLOR)
      stampMaterial.current.color.lerp(SCRATCH_COLOR, 1 - Math.exp(-dt * 5))
      stampMaterial.current.emissive.copy(stampMaterial.current.color)
    }
  })

  return (
    <group ref={group}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={FOLDER_SIZE} />
        <meshStandardMaterial color="#9fb3c8" roughness={0.7} />
      </mesh>
      <mesh position={[-0.16, 0.004, -FOLDER_SIZE[2] / 2 - 0.025]}>
        <boxGeometry args={[0.2, FOLDER_SIZE[1] - 0.01, 0.06]} />
        <meshStandardMaterial color="#475569" roughness={0.6} />
      </mesh>
      <mesh position={[0, FOLDER_SIZE[1] / 2 + 0.002, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[FOLDER_SIZE[0] - 0.06, FOLDER_SIZE[2] - 0.06]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.9} />
      </mesh>
      <mesh ref={stamp} position={[0.12, FOLDER_SIZE[1] / 2 + 0.01, 0.04]} scale={0.001}>
        <cylinderGeometry args={[0.13, 0.13, 0.014, 24]} />
        <meshStandardMaterial
          ref={stampMaterial}
          color={PALETTE.neutralStamp}
          emissive={PALETTE.neutralStamp}
          emissiveIntensity={0.35}
          roughness={0.5}
        />
      </mesh>
    </group>
  )
}

function traySlots(order: string[], requests: Record<string, RequestView>): Map<string, number> {
  const decided = order
    .map((id) => requests[id])
    .filter((r): r is RequestView => r !== undefined && r.decision !== null)
    .sort((a, b) => (a.decision?.seq ?? 0) - (b.decision?.seq ?? 0))
  const counts: Record<string, number> = {}
  const slots = new Map<string, number>()
  for (const r of decided) {
    const action = r.decision?.action
    if (!action) continue
    const n = counts[action] ?? 0
    slots.set(r.id, n)
    counts[action] = n + 1
  }
  return slots
}

export function RequestFolders() {
  const order = useSpectatorStore((s) => s.requestOrder)
  const requests = useSpectatorStore((s) => s.requests)
  const epoch = useSpectatorStore((s) => s.epoch)
  const slots = useMemo(() => traySlots(order, requests), [order, requests])
  return (
    <>
      {order.map((id) => (
        <Folder key={`${epoch}:${id}`} id={id} slot={slots.get(id) ?? 0} />
      ))}
      <DecisionCallout />
    </>
  )
}

export function QueueStack() {
  const mesh = useRef<InstancedMesh>(null)
  const total = useSpectatorStore((s) => s.queue.total)
  const position = useSpectatorStore((s) => s.queue.position)
  const pending = Math.min(MAX_QUEUE, Math.max(0, (total ?? 0) - position))

  useLayoutEffect(() => {
    const m = mesh.current
    if (!m) return
    for (let i = 0; i < pending; i++) {
      const pile = Math.floor(i / QUEUE_PILE_CAPACITY)
      const level = i % QUEUE_PILE_CAPACITY
      const [lx, lz] = QUEUE_PILE_LOCAL[pile]
      toWorld(
        'reception',
        [lx + jitter(i + 1, 0.05), PLATFORM_HEIGHT + FOLDER_SIZE[1] / 2 + level * (FOLDER_SIZE[1] + 0.006), lz + jitter(i + 11, 0.05)],
        SCRATCH_OBJECT.position,
      )
      SCRATCH_OBJECT.rotation.set(0, DEPARTMENT_LAYOUT.reception.yaw + jitter(i + 5, 0.25), 0)
      SCRATCH_OBJECT.updateMatrix()
      m.setMatrixAt(i, SCRATCH_OBJECT.matrix)
    }
    m.count = pending
    m.instanceMatrix.needsUpdate = true
    m.computeBoundingSphere()
  }, [pending])

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, MAX_QUEUE]} castShadow receiveShadow frustumCulled={false}>
      <boxGeometry args={FOLDER_SIZE} />
      <meshStandardMaterial color="#9fb3c8" roughness={0.7} />
    </instancedMesh>
  )
}

function DecisionCallout() {
  const last = useSpectatorStore((s) => s.lastDecision)
  const request = useSpectatorStore((s) => (s.lastDecision?.requestId ? s.requests[s.lastDecision.requestId] : undefined))
  const box = useRef<HTMLDivElement>(null)
  const shownSeq = useRef(0)
  const life = useRef(0)
  const position = useMemo(() => toWorld('decision', [0, 3.0, 0.4]), [])

  useFrame((_, delta) => {
    const el = box.current
    if (!el) return
    const latest = useSpectatorStore.getState().lastDecision
    const arrived = request?.decision ? avatarRuntime.arrivedMoveIndex >= request.decision.moveIndex : false
    if (latest && latest.seq !== shownSeq.current && arrived) {
      shownSeq.current = latest.seq
      life.current = 3.2
    }
    life.current = Math.max(0, life.current - Math.min(delta, 0.1))
    const opacity = Math.min(1, life.current * 2)
    el.style.opacity = String(opacity)
    el.style.transform = `translateY(${(1 - opacity) * 8}px) scale(${0.92 + opacity * 0.08})`
  })

  if (!last) return null
  const verdict = request?.verdict
  const tone =
    request && (request.leaks.length > 0 || (verdict && verdict.leak !== 'none'))
      ? 'leak'
      : verdict
        ? verdict.correct
          ? 'correct'
          : 'incorrect'
        : 'neutral'
  return (
    <SceneLabel position={position} zIndex={25}>
      <div ref={box} className={`stamp-callout stamp-callout--${tone}`} style={{ opacity: 0 }}>
        <span className="stamp-callout__action">{last.action}</span>
        {last.requestId && <span className="stamp-callout__id">{last.requestId}</span>}
      </div>
    </SceneLabel>
  )
}

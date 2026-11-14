import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import { Color, Vector3, type Fog, type Mesh, type MeshBasicMaterial, type MeshStandardMaterial, type PointLight } from 'three'
import { PALETTE } from '../../departments'
import { DEPARTMENT_LAYOUT, PLATFORM_HEIGHT, toWorld } from '../../sceneLayout'
import { useSpectatorStore } from '../../state/store'
import { SceneLabel } from './SceneLabel'

const BACKGROUND = new Color(PALETTE.background)
const ALARM_BACKGROUND = new Color('#f7d4d4')
const RIPPLE_SECONDS = 2.6
const RIPPLE_RINGS = 3

function useSeqTrigger(read: () => number, onFire: (seq: number) => void) {
  const seen = useRef<number | null>(null)
  return () => {
    const seq = read()
    if (seen.current === null) {
      seen.current = seq
      return
    }
    if (seq !== seen.current) {
      if (seq > seen.current) onFire(seq)
      seen.current = seq
    }
  }
}

export function SceneBackground() {
  const color = useRef<Color>(null)
  const fog = useRef<Fog>(null)
  const tint = useRef(0)
  const check = useSeqTrigger(
    () => useSpectatorStore.getState().lastLeak?.seq ?? 0,
    () => {
      if (useSpectatorStore.getState().lastLeak?.severity === 'critical') tint.current = 1
    },
  )
  useFrame((_, delta) => {
    check()
    tint.current = Math.max(0, tint.current - Math.min(delta, 0.1) / 2)
    const amount = Math.min(1, tint.current * 3)
    if (color.current) color.current.copy(BACKGROUND).lerp(ALARM_BACKGROUND, amount)
    if (fog.current && color.current) fog.current.color.copy(color.current)
  })
  return (
    <>
      <color ref={color} attach="background" args={[PALETTE.background]} />
      <fog ref={fog} attach="fog" args={[PALETTE.background, 50, 100]} />
    </>
  )
}

export function StateRipple() {
  const rings = useRef<(Mesh | null)[]>([])
  const materials = useRef<(MeshBasicMaterial | null)[]>([])
  const elapsed = useRef(99)
  const origin = useRef(new Vector3())
  const check = useSeqTrigger(
    () => useSpectatorStore.getState().lastStateChange?.seq ?? 0,
    () => {
      const change = useSpectatorStore.getState().lastStateChange
      const department = change?.department
      if (department) {
        const [x, z] = DEPARTMENT_LAYOUT[department].center
        origin.current.set(x, 0.03, z)
      } else {
        origin.current.set(0, 0.03, 0)
      }
      elapsed.current = 0
    },
  )
  useFrame((_, delta) => {
    check()
    elapsed.current += Math.min(delta, 0.1)
    for (let i = 0; i < RIPPLE_RINGS; i++) {
      const ring = rings.current[i]
      const material = materials.current[i]
      if (!ring || !material) continue
      const local = elapsed.current - i * 0.38
      const visible = local >= 0 && local <= RIPPLE_SECONDS
      ring.visible = visible
      if (!visible) continue
      const progress = local / RIPPLE_SECONDS
      ring.position.copy(origin.current)
      ring.scale.setScalar(0.6 + progress * 20)
      material.opacity = (1 - progress) * 0.55
    }
  })
  return (
    <>
      {Array.from({ length: RIPPLE_RINGS }, (_, i) => (
        <mesh
          key={i}
          ref={(el) => {
            rings.current[i] = el
          }}
          rotation={[-Math.PI / 2, 0, 0]}
          visible={false}
        >
          <ringGeometry args={[0.94, 1, 96]} />
          <meshBasicMaterial
            ref={(el) => {
              materials.current[i] = el
            }}
            color={PALETTE.hidden}
            transparent
            opacity={0}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>
      ))}
    </>
  )
}

export function HiddenCallout() {
  const change = useSpectatorStore((s) => s.lastStateChange)
  const box = useRef<HTMLDivElement>(null)
  const life = useRef(0)
  const check = useSeqTrigger(
    () => useSpectatorStore.getState().lastStateChange?.seq ?? 0,
    () => {
      life.current = 4
    },
  )
  const position = useMemo(() => {
    const department = change?.department
    return department ? toWorld(department, [0, 3.9, 0]) : new Vector3(0, 3, 0)
  }, [change])
  useFrame((_, delta) => {
    check()
    life.current = Math.max(0, life.current - Math.min(delta, 0.1))
    if (!box.current) return
    const opacity = Math.min(1, life.current * 1.5)
    box.current.style.opacity = String(opacity)
    box.current.style.transform = `translateY(${(1 - opacity) * 10}px)`
  })
  if (!change) return null
  let text = 'State changed'
  if (change.change === 'sno_activated') text = `SNO issued${change.person ? ` for ${change.person.initials}` : ''}`
  else if (change.change === 'case_closed') text = change.caseId ? `Case ${change.caseId} closed` : 'Case closed'
  else if (change.change === 'officer_reassigned') text = `Officer reassigned${change.caseId ? ` · ${change.caseId}` : ''}`
  return (
    <SceneLabel position={position} zIndex={26}>
      <div ref={box} className="hidden-callout" style={{ opacity: 0 }}>
        <span className="hidden-callout__text">{text}</span>
        <span className="badge badge--hidden">hidden from agent</span>
      </div>
    </SceneLabel>
  )
}

export function LeakAlarm() {
  const pulseRing = useRef<Mesh>(null)
  const pulseMaterial = useRef<MeshBasicMaterial>(null)
  const sirenMaterial = useRef<MeshStandardMaterial>(null)
  const light = useRef<PointLight>(null)
  const alarm = useRef(0)
  const strength = useRef(0)
  const center = useMemo(() => toWorld('decision', [0, PLATFORM_HEIGHT + 0.05, 0]), [])
  const beacon = useMemo(() => toWorld('decision', [2.95, PLATFORM_HEIGHT, 2.05]), [])
  const check = useSeqTrigger(
    () => useSpectatorStore.getState().lastLeak?.seq ?? 0,
    () => {
      const critical = useSpectatorStore.getState().lastLeak?.severity === 'critical'
      alarm.current = 1
      strength.current = critical ? 1 : 0.55
    },
  )
  useFrame(({ clock }, delta) => {
    check()
    const dt = Math.min(delta, 0.1)
    alarm.current = Math.max(0, alarm.current - dt / 3.2)
    const a = alarm.current * strength.current
    const flash = a > 0 ? 0.5 + 0.5 * Math.sin(clock.elapsedTime * 14) : 0
    if (sirenMaterial.current) sirenMaterial.current.emissiveIntensity = 0.1 + a * (1.2 + flash * 2.4)
    if (light.current) light.current.intensity = a * flash * 30
    if (pulseRing.current && pulseMaterial.current) {
      const cycle = (1 - alarm.current) * 3.2
      const progress = cycle % 1
      pulseRing.current.visible = a > 0.01
      pulseRing.current.scale.setScalar(3.4 + progress * 4)
      pulseMaterial.current.opacity = a * (1 - progress) * 0.85
    }
  })
  return (
    <>
      <mesh ref={pulseRing} position={center} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
        <ringGeometry args={[0.9, 1, 96]} />
        <meshBasicMaterial ref={pulseMaterial} color={PALETTE.leak} transparent opacity={0} depthWrite={false} toneMapped={false} />
      </mesh>
      <group position={beacon}>
        <mesh position={[0, 0.5, 0]} castShadow>
          <cylinderGeometry args={[0.07, 0.09, 1.0, 10]} />
          <meshStandardMaterial color="#cbd5e1" roughness={0.4} />
        </mesh>
        <mesh position={[0, 1.12, 0]} castShadow>
          <sphereGeometry args={[0.2, 18, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
          <meshStandardMaterial
            ref={sirenMaterial}
            color={PALETTE.leak}
            emissive={PALETTE.leak}
            emissiveIntensity={0.1}
            roughness={0.3}
            toneMapped={false}
          />
        </mesh>
        <pointLight ref={light} position={[0, 1.4, 0]} color={PALETTE.leak} intensity={0} distance={9} decay={1.6} />
      </group>
    </>
  )
}

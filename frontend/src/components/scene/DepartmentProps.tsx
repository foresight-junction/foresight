import { RoundedBox } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useLayoutEffect, useMemo, useRef, type RefObject } from 'react'
import { Color, Object3D, type Group, type InstancedMesh, type Mesh, type MeshStandardMaterial } from 'three'
import { PALETTE } from '../../departments'
import type { PulseState } from '../../hooks/useDepartmentPulse'
import { DESK_HEIGHT, DESK_Z, PLATFORM_HEIGHT, TRAY_TOP, TRAY_X, TRAY_Z } from '../../sceneLayout'
import type { DecisionAction, Department } from '../../types'
import { SceneLabel } from './SceneLabel'

interface PropProps {
  pulse: RefObject<PulseState>
  color: string
  size: [number, number]
}

const BODY = '#ffffff'
const TRIM = '#cbd5e1'
const DARK = '#1e293b'
const ERROR_RED = new Color(PALETTE.leak)
const SCRATCH = new Object3D()

function ease(current: number, target: number, dt: number, rate: number): number {
  return current + (target - current) * (1 - Math.exp(-dt * rate))
}

function envelope(value: number): number {
  return Math.sin(Math.min(1, Math.max(0, value)) * Math.PI)
}

function ReceptionProp({ pulse, color }: PropProps) {
  const wheel = useRef<Mesh>(null)
  const screen = useRef<MeshStandardMaterial>(null)
  useFrame((_, delta) => {
    const p = pulse.current
    if (!wheel.current || !screen.current) return
    const dt = Math.min(delta, 0.1)
    wheel.current.rotation.x = ease(wheel.current.rotation.x, p.starts * (Math.PI / 4), dt, 6)
    screen.current.emissiveIntensity = 0.35 + p.activity * 0.7 + p.kick * 1.2
  })
  return (
    <group position={[0, PLATFORM_HEIGHT, DESK_Z]}>
      <RoundedBox args={[2.2, DESK_HEIGHT, 0.75]} radius={0.12} smoothness={3} position={[0, DESK_HEIGHT / 2, 0]} castShadow receiveShadow>
        <meshStandardMaterial color={BODY} roughness={0.5} />
      </RoundedBox>
      <mesh position={[0, DESK_HEIGHT * 0.48, 0.381]}>
        <boxGeometry args={[1.9, 0.42, 0.02]} />
        <meshStandardMaterial color={color} roughness={0.35} />
      </mesh>
      <group position={[1.55, 0, 0]}>
        <mesh position={[0, 0.75, 0]} castShadow>
          <cylinderGeometry args={[0.05, 0.06, 1.5, 12]} />
          <meshStandardMaterial color={TRIM} roughness={0.4} />
        </mesh>
        <mesh ref={wheel} position={[0, 1.65, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.34, 0.34, 0.24, 8]} />
          <meshStandardMaterial ref={screen} color={color} emissive={color} emissiveIntensity={0.35} flatShading roughness={0.3} />
        </mesh>
      </group>
    </group>
  )
}

function IdentityProp({ pulse, color, size }: PropProps) {
  const archZ = size[1] / 2 - 0.95
  const bar = useRef<Mesh>(null)
  const barMaterial = useRef<MeshStandardMaterial>(null)
  const screen = useRef<MeshStandardMaterial>(null)
  const base = useMemo(() => new Color(color), [color])
  useFrame(({ clock }) => {
    const p = pulse.current
    if (!bar.current || !barMaterial.current || !screen.current) return
    const sweep = 0.5 + 0.5 * Math.sin(clock.elapsedTime * 4.4)
    bar.current.position.y = 0.32 + (0.2 + sweep * 1.5) * p.activity
    barMaterial.current.emissiveIntensity = 0.3 + p.activity * 1.8 + p.kick
    barMaterial.current.emissive.copy(base).lerp(ERROR_RED, Math.min(1, p.error * 1.4))
    screen.current.emissiveIntensity = 0.3 + p.event * 1.4
  })
  return (
    <group position={[0, PLATFORM_HEIGHT, 0]}>
      {[-0.92, 0.92].map((x) => (
        <RoundedBox key={x} args={[0.26, 2.2, 0.34]} radius={0.08} smoothness={2} position={[x, 1.1, archZ]} castShadow receiveShadow>
          <meshStandardMaterial color={BODY} roughness={0.45} />
        </RoundedBox>
      ))}
      <RoundedBox args={[2.1, 0.28, 0.36]} radius={0.08} smoothness={2} position={[0, 2.32, archZ]} castShadow>
        <meshStandardMaterial color={BODY} roughness={0.45} />
      </RoundedBox>
      <mesh ref={bar} position={[0, 0.32, archZ]}>
        <boxGeometry args={[1.56, 0.05, 0.12]} />
        <meshStandardMaterial ref={barMaterial} color={color} emissive={color} emissiveIntensity={0.3} toneMapped={false} />
      </mesh>
      <group position={[0, 0, -1.2]}>
        <RoundedBox args={[1.1, 1.15, 0.5]} radius={0.1} smoothness={2} position={[0, 0.575, 0]} castShadow receiveShadow>
          <meshStandardMaterial color={BODY} roughness={0.5} />
        </RoundedBox>
        <mesh position={[0, 0.82, 0.255]}>
          <planeGeometry args={[0.8, 0.42]} />
          <meshStandardMaterial ref={screen} color={DARK} emissive={color} emissiveIntensity={0.3} />
        </mesh>
      </group>
    </group>
  )
}

const DRAWER_ROWS = [0.32, 0.8, 1.28]
const CABINET_X = [-1.12, 0, 1.12]
const DRAWER_BASE_Z = 0.39

function RegistryProp({ pulse, color }: PropProps) {
  const drawers = useRef<(Mesh | null)[]>([])
  const glow = useRef<MeshStandardMaterial>(null)
  useFrame((_, delta) => {
    const p = pulse.current
    const dt = Math.min(delta, 0.1)
    const open = Math.max(p.activity, p.kick)
    const activeIndex = p.starts === 0 ? -1 : (p.starts * 4) % drawers.current.length
    drawers.current.forEach((drawer, index) => {
      if (!drawer) return
      const target = DRAWER_BASE_Z + (index === activeIndex ? 0.42 * open : 0)
      drawer.position.z = ease(drawer.position.z, target, dt, 9)
    })
    if (glow.current) glow.current.emissiveIntensity = 0.2 + p.event * 1.5 + p.activity * 0.5
  })
  return (
    <group position={[0, PLATFORM_HEIGHT, -1.05]}>
      {CABINET_X.map((x, c) => (
        <group key={x} position={[x, 0, 0]}>
          <RoundedBox args={[0.98, 1.62, 0.74]} radius={0.07} smoothness={2} position={[0, 0.81, 0]} castShadow receiveShadow>
            <meshStandardMaterial color={BODY} roughness={0.5} />
          </RoundedBox>
          {DRAWER_ROWS.map((y, r) => (
            <mesh
              key={y}
              ref={(el) => {
                drawers.current[c * DRAWER_ROWS.length + r] = el
              }}
              position={[0, y, DRAWER_BASE_Z]}
              castShadow
            >
              <boxGeometry args={[0.84, 0.4, 0.08]} />
              <meshStandardMaterial color={r === 1 ? color : '#eef2f7'} roughness={0.45} />
            </mesh>
          ))}
        </group>
      ))}
      <mesh position={[0, 1.78, 0]}>
        <boxGeometry args={[3.3, 0.06, 0.5]} />
        <meshStandardMaterial ref={glow} color={color} emissive={color} emissiveIntensity={0.2} toneMapped={false} />
      </mesh>
    </group>
  )
}

function ProtectionProp({ pulse, color }: PropProps) {
  const shield = useRef<Group>(null)
  const face = useRef<MeshStandardMaterial>(null)
  const halo = useRef<Mesh>(null)
  const base = useMemo(() => new Color(color), [color])
  useFrame((_, delta) => {
    const p = pulse.current
    const dt = Math.min(delta, 0.1)
    if (!shield.current || !face.current || !halo.current) return
    shield.current.rotation.y = ease(shield.current.rotation.y, p.starts * (Math.PI / 3), dt, 5)
    face.current.emissiveIntensity = 0.45 + p.activity * 0.9 + p.event * 1.6 + p.hidden * 1.2
    face.current.emissive.copy(base).lerp(ERROR_RED, Math.min(1, p.error * 1.4))
    halo.current.scale.setScalar(1 + p.event * 0.35 + p.hidden * 0.5)
  })
  return (
    <group position={[0, PLATFORM_HEIGHT, -0.85]}>
      <mesh position={[0, 0.35, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.5, 0.62, 0.7, 6]} />
        <meshStandardMaterial color={BODY} roughness={0.5} flatShading />
      </mesh>
      <group ref={shield} position={[0, 1.65, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
          <cylinderGeometry args={[0.78, 0.78, 0.16, 6]} />
          <meshStandardMaterial ref={face} color={color} emissive={color} emissiveIntensity={0.45} flatShading roughness={0.3} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, 0.09]}>
          <cylinderGeometry args={[0.46, 0.46, 0.04, 6]} />
          <meshStandardMaterial color={BODY} roughness={0.3} flatShading />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -0.09]}>
          <cylinderGeometry args={[0.46, 0.46, 0.04, 6]} />
          <meshStandardMaterial color={BODY} roughness={0.3} flatShading />
        </mesh>
      </group>
      <mesh ref={halo} position={[0, 0.72, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.8, 0.86, 48]} />
        <meshBasicMaterial color={color} transparent opacity={0.7} toneMapped={false} />
      </mesh>
    </group>
  )
}

function AuthorityProp({ pulse, color }: PropProps) {
  const gavel = useRef<Group>(null)
  const badge = useRef<MeshStandardMaterial>(null)
  useFrame(() => {
    const p = pulse.current
    if (!gavel.current || !badge.current) return
    gavel.current.rotation.z = -1.0 * Math.max(envelope(p.kick), envelope(p.event))
    badge.current.emissiveIntensity = 0.35 + p.event * 1.5 + p.hidden * 1.4 + p.activity * 0.4
  })
  return (
    <group position={[0, PLATFORM_HEIGHT, -0.8]}>
      <RoundedBox args={[2.2, 0.9, 0.85]} radius={0.12} smoothness={3} position={[0, 0.45, 0]} castShadow receiveShadow>
        <meshStandardMaterial color={BODY} roughness={0.5} />
      </RoundedBox>
      <mesh position={[0, 0.5, 0.43]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.26, 0.26, 0.05, 5]} />
        <meshStandardMaterial ref={badge} color={color} emissive={color} emissiveIntensity={0.35} flatShading />
      </mesh>
      <mesh position={[0.55, 0.94, 0]} castShadow>
        <cylinderGeometry args={[0.2, 0.22, 0.08, 16]} />
        <meshStandardMaterial color={DARK} roughness={0.4} />
      </mesh>
      <group ref={gavel} position={[0.05, 1.0, 0]}>
        <mesh position={[0.3, 0.06, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.035, 0.035, 0.6, 10]} />
          <meshStandardMaterial color="#94a3b8" roughness={0.4} />
        </mesh>
        <mesh position={[0.55, 0.06, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
          <cylinderGeometry args={[0.1, 0.1, 0.36, 14]} />
          <meshStandardMaterial color={color} roughness={0.35} />
        </mesh>
      </group>
      <group position={[-0.6, 0.9, 0]}>
        {[0, 1, 2].map((i) => (
          <mesh key={i} position={[0, 0.03 + i * 0.05, 0]} rotation={[0, (i - 1) * 0.12, 0]} castShadow>
            <boxGeometry args={[0.5, 0.04, 0.36]} />
            <meshStandardMaterial color={i === 2 ? color : '#f1f5f9'} roughness={0.6} />
          </mesh>
        ))}
      </group>
    </group>
  )
}

const ROD_Y = [0.72, 1.08, 1.44]
const BEADS_PER_ROD = 5
const BEAD_COUNT = ROD_Y.length * BEADS_PER_ROD
const BEAD_SPACING = 0.2
const ROD_HALF = 0.95

function StatisticsProp({ pulse, color }: PropProps) {
  const beads = useRef<InstancedMesh>(null)
  const xs = useRef<Float32Array>(new Float32Array(BEAD_COUNT))
  const plaque = useRef<MeshStandardMaterial>(null)

  useLayoutEffect(() => {
    const mesh = beads.current
    if (!mesh) return
    const accent = new Color(color)
    const pale = new Color('#e2e8f0')
    for (let i = 0; i < BEAD_COUNT; i++) {
      const rod = Math.floor(i / BEADS_PER_ROD)
      const slot = i % BEADS_PER_ROD
      xs.current[i] = -ROD_HALF + 0.12 + slot * BEAD_SPACING
      mesh.setColorAt(i, rod === 1 ? pale : accent)
    }
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [color])

  useFrame((_, delta) => {
    const mesh = beads.current
    const p = pulse.current
    if (!mesh) return
    const dt = Math.min(delta, 0.1)
    const moved = p.starts % (BEAD_COUNT + 1)
    for (let i = 0; i < BEAD_COUNT; i++) {
      const rod = Math.floor(i / BEADS_PER_ROD)
      const slot = i % BEADS_PER_ROD
      const movedOnRod = Math.min(BEADS_PER_ROD, Math.max(0, moved - rod * BEADS_PER_ROD))
      const isMoved = slot >= BEADS_PER_ROD - movedOnRod
      const target = isMoved ? ROD_HALF - 0.12 - (BEADS_PER_ROD - 1 - slot) * BEAD_SPACING : -ROD_HALF + 0.12 + slot * BEAD_SPACING
      xs.current[i] = ease(xs.current[i], target, dt, 8)
      SCRATCH.position.set(xs.current[i], ROD_Y[rod], 0)
      SCRATCH.updateMatrix()
      mesh.setMatrixAt(i, SCRATCH.matrix)
    }
    mesh.instanceMatrix.needsUpdate = true
    if (plaque.current) plaque.current.emissiveIntensity = 0.25 + p.event * 1.4 + p.activity * 0.5
  })

  return (
    <group position={[0, PLATFORM_HEIGHT, -1.0]}>
      {[-1.08, 1.08].map((x) => (
        <RoundedBox key={x} args={[0.16, 1.9, 0.3]} radius={0.05} smoothness={2} position={[x, 0.95, 0]} castShadow>
          <meshStandardMaterial color={BODY} roughness={0.45} />
        </RoundedBox>
      ))}
      <RoundedBox args={[2.4, 0.16, 0.32]} radius={0.05} smoothness={2} position={[0, 1.86, 0]} castShadow>
        <meshStandardMaterial color={BODY} roughness={0.45} />
      </RoundedBox>
      {ROD_Y.map((y) => (
        <mesh key={y} position={[0, y, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.018, 0.018, 2.1, 8]} />
          <meshStandardMaterial color={TRIM} roughness={0.3} metalness={0.4} />
        </mesh>
      ))}
      <instancedMesh ref={beads} args={[undefined, undefined, BEAD_COUNT]} castShadow>
        <icosahedronGeometry args={[0.095, 1]} />
        <meshStandardMaterial roughness={0.35} flatShading />
      </instancedMesh>
      <mesh position={[0, 0.3, 0.16]}>
        <boxGeometry args={[1.4, 0.22, 0.03]} />
        <meshStandardMaterial ref={plaque} color={color} emissive={color} emissiveIntensity={0.25} />
      </mesh>
    </group>
  )
}

const TRAY_LABEL: Record<DecisionAction, string> = { RELEASE: 'RELEASE', DENY: 'DENY', FORWARD: 'FORWARD' }

function DecisionProp({ pulse, color }: PropProps) {
  const head = useRef<Group>(null)
  const face = useRef<MeshStandardMaterial>(null)
  useFrame(() => {
    const p = pulse.current
    if (!head.current || !face.current) return
    const press = envelope(p.event)
    head.current.position.y = 1.35 - press * 0.72
    face.current.emissiveIntensity = 0.15 + press * 1.4
  })
  return (
    <group position={[0, PLATFORM_HEIGHT, 0]}>
      <group position={[0, 0, 0.1]}>
        <RoundedBox args={[1.1, 0.42, 1.0]} radius={0.1} smoothness={2} position={[0, 0.21, 0]} castShadow receiveShadow>
          <meshStandardMaterial color={BODY} roughness={0.5} />
        </RoundedBox>
        <mesh position={[0, 0.425, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.7, 0.55]} />
          <meshStandardMaterial color="#f8fafc" roughness={0.9} />
        </mesh>
        <mesh position={[0, 1.15, -0.45]} castShadow>
          <boxGeometry args={[0.16, 1.9, 0.16]} />
          <meshStandardMaterial color={TRIM} roughness={0.35} metalness={0.3} />
        </mesh>
        <mesh position={[0, 2.05, -0.22]} castShadow>
          <boxGeometry args={[0.18, 0.16, 0.6]} />
          <meshStandardMaterial color={TRIM} roughness={0.35} metalness={0.3} />
        </mesh>
        <group ref={head} position={[0, 1.35, 0]}>
          <mesh position={[0, 0.32, 0]} castShadow>
            <cylinderGeometry args={[0.05, 0.05, 0.62, 10]} />
            <meshStandardMaterial color={TRIM} metalness={0.3} roughness={0.35} />
          </mesh>
          <mesh castShadow>
            <cylinderGeometry args={[0.32, 0.36, 0.22, 24]} />
            <meshStandardMaterial ref={face} color={color} emissive="#ffffff" emissiveIntensity={0.15} roughness={0.35} />
          </mesh>
        </group>
      </group>
      {(Object.keys(TRAY_X) as DecisionAction[]).map((action) => (
        <group key={action} position={[TRAY_X[action], 0, TRAY_Z]}>
          <RoundedBox
            args={[1.5, 0.12, 1.05]}
            radius={0.04}
            smoothness={2}
            position={[0, TRAY_TOP - PLATFORM_HEIGHT - 0.1, 0]}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial color="#f1f5f9" roughness={0.6} />
          </RoundedBox>
          <SceneLabel position={[0, 0.05, 0.75]} zIndex={20}>
            <div className={`tray-label tray-label--${action.toLowerCase()}`}>{TRAY_LABEL[action]}</div>
          </SceneLabel>
        </group>
      ))}
    </group>
  )
}

export function DepartmentProp({ department, ...props }: PropProps & { department: Department }) {
  switch (department) {
    case 'reception':
      return <ReceptionProp {...props} />
    case 'identity':
      return <IdentityProp {...props} />
    case 'registry':
      return <RegistryProp {...props} />
    case 'protection':
      return <ProtectionProp {...props} />
    case 'authority':
      return <AuthorityProp {...props} />
    case 'statistics':
      return <StatisticsProp {...props} />
    case 'decision':
      return <DecisionProp {...props} />
  }
}

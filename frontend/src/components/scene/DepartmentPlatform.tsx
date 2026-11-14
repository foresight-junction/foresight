import { RoundedBox } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useMemo, useRef, type CSSProperties } from 'react'
import { Color, type Mesh, type MeshStandardMaterial } from 'three'
import { DEPARTMENT_COLOR, DEPARTMENT_LABEL, PALETTE } from '../../departments'
import { useDepartmentPulse } from '../../hooks/useDepartmentPulse'
import { DEPARTMENT_LAYOUT, PLATFORM_HEIGHT } from '../../sceneLayout'
import { useSpectatorStore } from '../../state/store'
import type { Department } from '../../types'
import { DepartmentProp } from './DepartmentProps'
import { SceneLabel } from './SceneLabel'

const WHITE = new Color('#ffffff')
const ERROR_RED = new Color(PALETTE.leak)

function DepartmentLabel({ department }: { department: Department }) {
  const calls = useSpectatorStore((s) => s.departments[department].calls)
  const active = useSpectatorStore((s) => s.departments[department].active > 0)
  const errors = useSpectatorStore((s) => s.departments[department].errors)
  const isTarget = useSpectatorStore((s) => s.avatar.target === department)
  return (
    <SceneLabel position={[0, 3.2, 0]} zIndex={20}>
      <div
        className={`dept-label${active ? ' is-active' : ''}${isTarget ? ' is-target' : ''}`}
        style={{ '--accent': DEPARTMENT_COLOR[department] } as CSSProperties}
      >
        <span className="dept-label__dot" />
        <span className="dept-label__name">{DEPARTMENT_LABEL[department]}</span>
        {calls > 0 && <span className="dept-label__count">{calls}</span>}
        {errors > 0 && <span className="dept-label__errors">{errors} err</span>}
      </div>
    </SceneLabel>
  )
}

export function DepartmentPlatform({ department }: { department: Department }) {
  const { center, size, yaw } = DEPARTMENT_LAYOUT[department]
  const [width, depth] = size
  const color = DEPARTMENT_COLOR[department]
  const pulse = useDepartmentPulse(department)
  const ring = useRef<Mesh>(null)
  const ringMaterial = useRef<MeshStandardMaterial>(null)
  const baseColor = useMemo(() => new Color(color), [color])
  const insetColor = useMemo(() => '#' + new Color(color).lerp(WHITE, 0.62).getHexString(), [color])
  const ringRadius = Math.min(width, depth) / 2 - 0.32

  useFrame(() => {
    const p = pulse.current
    if (!ring.current || !ringMaterial.current) return
    const glow = 0.25 + p.activity * 1.1 + p.kick * 1.6 + p.error * 1.5
    ringMaterial.current.emissiveIntensity = glow
    ringMaterial.current.emissive.copy(baseColor).lerp(ERROR_RED, Math.min(1, p.error * 1.4))
    ringMaterial.current.color.copy(ringMaterial.current.emissive)
    ring.current.scale.setScalar(1 + p.kick * 0.09 + p.error * 0.05)
  })

  return (
    <group position={[center[0], 0, center[1]]} rotation={[0, yaw, 0]}>
      <RoundedBox
        args={[width, PLATFORM_HEIGHT, depth]}
        radius={0.16}
        smoothness={3}
        position={[0, PLATFORM_HEIGHT / 2, 0]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial color="#fcfdff" roughness={0.62} />
      </RoundedBox>
      <mesh position={[0, PLATFORM_HEIGHT + 0.004, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[width - 0.45, depth - 0.45]} />
        <meshStandardMaterial color={insetColor} roughness={0.85} />
      </mesh>
      <mesh ref={ring} position={[0, PLATFORM_HEIGHT + 0.012, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[ringRadius - 0.07, ringRadius, 72]} />
        <meshStandardMaterial
          ref={ringMaterial}
          color={color}
          emissive={color}
          emissiveIntensity={0.25}
          roughness={0.4}
          toneMapped={false}
        />
      </mesh>
      <mesh position={[0, 0.02, depth / 2 + 0.02]} rotation={[0, 0, 0]}>
        <boxGeometry args={[width * 0.6, 0.04, 0.05]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.35} />
      </mesh>
      <DepartmentProp department={department} pulse={pulse} color={color} size={size} />
      <DepartmentLabel department={department} />
    </group>
  )
}

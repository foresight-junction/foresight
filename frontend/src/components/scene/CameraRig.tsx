import { OrbitControls } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useRef, type ComponentRef } from 'react'
import { Vector3 } from 'three'
import { avatarRuntime } from '../../state/avatarRuntime'

const SCRATCH_TARGET = new Vector3()
const FOLLOW = 0.18

export function CameraRig() {
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null)
  useFrame((_, delta) => {
    const c = controls.current
    if (!c) return
    const p = avatarRuntime.position
    SCRATCH_TARGET.set(p.x * FOLLOW, 0.6, p.z * FOLLOW - 0.3)
    c.target.lerp(SCRATCH_TARGET, 1 - Math.exp(-Math.min(delta, 0.1) * 1.4))
  })
  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      enablePan={false}
      minDistance={16}
      maxDistance={60}
      minPolarAngle={0.3}
      maxPolarAngle={1.18}
      target={[0, 0.6, -0.3]}
    />
  )
}

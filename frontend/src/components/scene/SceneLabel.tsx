import { Html } from '@react-three/drei'
import type { ReactNode, RefObject } from 'react'
import type { Vector3 } from 'three'
import { sceneLabelLayer } from './sceneLabelLayer'

interface SceneLabelProps {
  position: [number, number, number] | Vector3
  zIndex?: number
  children: ReactNode
}

export function SceneLabel({ position, zIndex = 20, children }: SceneLabelProps) {
  return (
    <Html position={position} center zIndexRange={[zIndex, 0]} pointerEvents="none" portal={sceneLabelLayer as RefObject<HTMLElement>}>
      {children}
    </Html>
  )
}

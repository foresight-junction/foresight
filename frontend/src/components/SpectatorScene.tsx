import { Environment, Lightformer } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { memo } from 'react'
import { NeutralToneMapping } from 'three'
import { DEPARTMENTS } from '../departments'
import { Avatar } from './scene/Avatar'
import { CameraRig } from './scene/CameraRig'
import { DepartmentPlatform } from './scene/DepartmentPlatform'
import { Hall } from './scene/Hall'
import { PersonGallery } from './scene/PersonGallery'
import { QueueStack, RequestFolders } from './scene/RequestFolders'
import { HiddenCallout, LeakAlarm, SceneBackground, StateRipple } from './scene/SceneEffects'
import { sceneLabelLayer } from './scene/sceneLabelLayer'

export const SpectatorScene = memo(function SpectatorScene() {
  return (
    <>
      <Canvas
        className="scene-canvas"
        shadows="percentage"
        dpr={[1, 2]}
        camera={{ position: [0, 23.5, 27.5], fov: 40, near: 0.5, far: 220 }}
        gl={{ antialias: true, toneMapping: NeutralToneMapping }}
      >
        <SceneBackground />
        <hemisphereLight args={['#ffffff', '#c8d2e1', 0.55]} />
        <directionalLight
          castShadow
          position={[14, 26, 12]}
          intensity={2.4}
          shadow-mapSize={[2048, 2048]}
          shadow-bias={-0.0004}
          shadow-normalBias={0.03}
        >
          <orthographicCamera attach="shadow-camera" args={[-22, 22, 22, -22, 1, 80]} />
        </directionalLight>
        <Environment resolution={256} frames={1} environmentIntensity={0.45}>
          <Lightformer form="rect" intensity={2.2} position={[0, 12, 0]} rotation-x={Math.PI / 2} scale={[24, 24, 1]} />
          <Lightformer form="rect" intensity={1.2} color="#dbeafe" position={[-14, 5, 6]} rotation-y={Math.PI / 2} scale={[12, 5, 1]} />
          <Lightformer form="rect" intensity={0.9} color="#fff1dc" position={[14, 5, -6]} rotation-y={-Math.PI / 2} scale={[12, 5, 1]} />
          <Lightformer form="ring" intensity={1.4} position={[0, 6, -14]} scale={5} />
        </Environment>
        <Hall />
        {DEPARTMENTS.map((department) => (
          <DepartmentPlatform key={department} department={department} />
        ))}
        <PersonGallery />
        <QueueStack />
        <RequestFolders />
        <Avatar />
        <StateRipple />
        <HiddenCallout />
        <LeakAlarm />
        <CameraRig />
      </Canvas>
      <div ref={sceneLabelLayer} className="scene-labels" />
    </>
  )
})

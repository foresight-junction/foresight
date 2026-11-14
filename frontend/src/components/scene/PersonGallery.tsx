import { useFrame } from '@react-three/fiber'
import { useMemo, useRef, type CSSProperties } from 'react'
import { Color, Quaternion, Vector3, type Group, type Mesh, type MeshStandardMaterial } from 'three'
import { DEPARTMENT_COLOR, PALETTE } from '../../departments'
import { layoutGallery, type GalleryDome, type GalleryToken } from '../../galleryLayout'
import { GALLERY_CENTER, GALLERY_RADIUS, standPoint } from '../../sceneLayout'
import { useSpectatorStore } from '../../state/store'
import { SceneLabel } from './SceneLabel'

const DAIS_HEIGHT = 0.22
const SHIELD = DEPARTMENT_COLOR.protection
const BODY_NEUTRAL = new Color('#cbd5e1')
const BODY_SHIELDED = new Color('#7dd3fc')
const BODY_HIDDEN = new Color('#d8b4fe')
const BODY_LEAKED = new Color('#fca5a5')
const SCRATCH_TARGET = new Vector3()
const SCRATCH_COLOR = new Color()
const UP = new Vector3(0, 1, 0)

function worldOf(token: { x: number; z: number }, out: Vector3): Vector3 {
  return out.set(GALLERY_CENTER[0] + token.x, DAIS_HEIGHT, GALLERY_CENTER[1] + token.z)
}

function PersonToken({ token }: { token: GalleryToken }) {
  const person = useSpectatorStore((s) => s.persons[token.id])
  const group = useRef<Group>(null)
  const body = useRef<MeshStandardMaterial>(null)
  const shield = useRef<Mesh>(null)
  const initialized = useRef(false)

  useFrame(({ clock }, delta) => {
    const g = group.current
    if (!g || !person) return
    const dt = Math.min(delta, 0.1)
    if (!initialized.current) {
      standPoint(person.firstSeenDepartment, g.position)
      g.position.y += 0.6
      initialized.current = true
    }
    worldOf(token, SCRATCH_TARGET)
    const distance = g.position.distanceTo(SCRATCH_TARGET)
    g.position.lerp(SCRATCH_TARGET, 1 - Math.exp(-dt * 3.2))
    g.position.y = Math.max(g.position.y, SCRATCH_TARGET.y + Math.min(1.2, distance * 0.18))
    if (body.current) {
      const target = person.leaked ? BODY_LEAKED : person.sno === 'ACTIVE' ? (person.snoHidden ? BODY_HIDDEN : BODY_SHIELDED) : BODY_NEUTRAL
      SCRATCH_COLOR.copy(target)
      body.current.color.lerp(SCRATCH_COLOR, 1 - Math.exp(-dt * 4))
      body.current.emissive.copy(person.leaked ? BODY_LEAKED : BODY_NEUTRAL)
      body.current.emissiveIntensity = person.leaked ? 0.25 + 0.25 * Math.sin(clock.elapsedTime * 6) : 0
    }
    if (shield.current) {
      const visible = person.sno === 'ACTIVE' ? 1 : 0.001
      const s = shield.current.scale.x + (visible - shield.current.scale.x) * (1 - Math.exp(-dt * 6))
      shield.current.scale.setScalar(s)
    }
  })

  if (!person) return null
  const shieldColor = person.snoHidden ? PALETTE.hidden : SHIELD
  return (
    <group ref={group}>
      <mesh position={[0, 0.04, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.24, 0.27, 0.08, 18]} />
        <meshStandardMaterial color="#ffffff" roughness={0.5} />
      </mesh>
      <mesh position={[0, 0.3, 0]} castShadow>
        <capsuleGeometry args={[0.15, 0.24, 4, 12]} />
        <meshStandardMaterial ref={body} color="#cbd5e1" roughness={0.45} />
      </mesh>
      <mesh position={[0, 0.62, 0]} castShadow>
        <sphereGeometry args={[0.14, 18, 14]} />
        <meshStandardMaterial color="#f1f5f9" roughness={0.4} />
      </mesh>
      <mesh ref={shield} position={[0, 0.98, 0]} rotation={[Math.PI / 2, 0, 0]} scale={0.001}>
        <cylinderGeometry args={[0.16, 0.16, 0.04, 6]} />
        <meshStandardMaterial color={shieldColor} emissive={shieldColor} emissiveIntensity={0.9} flatShading toneMapped={false} />
      </mesh>
      <SceneLabel position={[0, 1.28, 0]} zIndex={18}>
        <div
          className={`person-tag${person.sno === 'ACTIVE' ? (person.snoHidden ? ' is-hidden-sno' : ' is-sno') : ''}${person.leaked ? ' is-leaked' : ''}`}
          title={person.ref.id}
        >
          {person.ref.initials || person.ref.id}
          {person.sno === 'ACTIVE' && <span className="person-tag__sno">SNO</span>}
        </div>
      </SceneLabel>
    </group>
  )
}

function HouseholdLink({ from, to }: { from: GalleryToken; to: GalleryToken }) {
  const { position, quaternion, length } = useMemo(() => {
    const a = worldOf(from, new Vector3()).setY(DAIS_HEIGHT + 0.3)
    const b = worldOf(to, new Vector3()).setY(DAIS_HEIGHT + 0.3)
    const dir = b.clone().sub(a)
    const q = new Quaternion().setFromUnitVectors(UP, dir.clone().normalize())
    return { position: a.add(b).multiplyScalar(0.5), quaternion: q, length: dir.length() }
  }, [from, to])
  return (
    <mesh position={position} quaternion={quaternion}>
      <cylinderGeometry args={[0.03, 0.03, length, 8]} />
      <meshStandardMaterial color="#e0f2fe" emissive={SHIELD} emissiveIntensity={0.9} transparent opacity={0.85} toneMapped={false} />
    </mesh>
  )
}

function Dome({ dome, tokens }: { dome: GalleryDome; tokens: Map<string, GalleryToken> }) {
  const mesh = useRef<Mesh>(null)
  const { center, radius } = useMemo(() => {
    const points = dome.memberIds.map((id) => tokens.get(id)).filter((t): t is GalleryToken => t !== undefined)
    const cx = points.reduce((sum, t) => sum + t.x, 0) / Math.max(1, points.length)
    const cz = points.reduce((sum, t) => sum + t.z, 0) / Math.max(1, points.length)
    const r = points.reduce((max, t) => Math.max(max, Math.hypot(t.x - cx, t.z - cz)), 0) + 0.55
    return { center: worldOf({ x: cx, z: cz }, new Vector3()), radius: r }
  }, [dome, tokens])
  useFrame((_, delta) => {
    const m = mesh.current
    if (!m) return
    const s = m.scale.x + (1 - m.scale.x) * (1 - Math.exp(-Math.min(delta, 0.1) * 4))
    m.scale.setScalar(s)
  })
  const color = dome.hidden ? PALETTE.hidden : SHIELD
  return (
    <mesh ref={mesh} position={center} scale={0.01}>
      <sphereGeometry args={[radius, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.35}
        transparent
        opacity={0.16}
        depthWrite={false}
        roughness={0.2}
      />
    </mesh>
  )
}

export function PersonGallery() {
  const personOrder = useSpectatorStore((s) => s.personOrder)
  const persons = useSpectatorStore((s) => s.persons)
  const households = useSpectatorStore((s) => s.households)
  const epoch = useSpectatorStore((s) => s.epoch)
  const layout = useMemo(() => layoutGallery(personOrder, persons, households), [personOrder, persons, households])
  const tokenMap = useMemo(() => new Map(layout.tokens.map((t) => [t.id, t])), [layout])

  return (
    <group>
      <mesh position={[GALLERY_CENTER[0], DAIS_HEIGHT / 2, GALLERY_CENTER[1]]} castShadow receiveShadow>
        <cylinderGeometry args={[GALLERY_RADIUS, GALLERY_RADIUS + 0.12, DAIS_HEIGHT, 56]} />
        <meshStandardMaterial color="#fcfdff" roughness={0.6} />
      </mesh>
      <mesh position={[GALLERY_CENTER[0], DAIS_HEIGHT + 0.004, GALLERY_CENTER[1]]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[GALLERY_RADIUS - 0.2, 56]} />
        <meshStandardMaterial color="#e0f2fe" roughness={0.85} />
      </mesh>
      <SceneLabel position={[GALLERY_CENTER[0], 2.4, GALLERY_CENTER[1] - GALLERY_RADIUS + 0.2]} zIndex={20}>
        <div className="dept-label dept-label--sub" style={{ '--accent': SHIELD } as CSSProperties}>
          <span className="dept-label__dot" />
          <span className="dept-label__name">Persons on file</span>
          {personOrder.length > 0 && <span className="dept-label__count">{personOrder.length}</span>}
        </div>
      </SceneLabel>
      {layout.tokens.map((token) => (
        <PersonToken key={`${epoch}:${token.id}`} token={token} />
      ))}
      {layout.links.map((link) => {
        const from = tokenMap.get(link.from)
        const to = tokenMap.get(link.to)
        return from && to ? <HouseholdLink key={`${epoch}:${link.key}:${from.x},${from.z}:${to.x},${to.z}`} from={from} to={to} /> : null
      })}
      {layout.domes.map((dome) => (
        <Dome
          key={`${epoch}:${dome.householdId ?? dome.memberIds[0]}:${dome.memberIds.join(',')}:${dome.hidden}`}
          dome={dome}
          tokens={tokenMap}
        />
      ))}
    </group>
  )
}

import { Vector3 } from 'three'
import { standPoint, facingYaw } from '../sceneLayout'

// Per-frame avatar pose shared between scene components without React re-renders.
export const avatarRuntime = {
  position: standPoint('reception'),
  yaw: facingYaw('reception'),
  arrivedMoveIndex: -1,
  walking: false,
  generation: 0,
}

export function resetAvatarRuntime(): void {
  avatarRuntime.position.copy(standPoint('reception', new Vector3()))
  avatarRuntime.yaw = facingYaw('reception')
  avatarRuntime.arrivedMoveIndex = -1
  avatarRuntime.walking = false
  avatarRuntime.generation += 1
}

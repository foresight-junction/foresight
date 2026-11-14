import { Vector3 } from 'three'
import type { DecisionAction, Department } from './types'

export const PLATFORM_HEIGHT = 0.4
export const HALL_RADIUS = 13.6

export const DESK_HEIGHT = 0.95
export const DESK_Z = -0.75
export const FOLDER_SIZE: [number, number, number] = [0.62, 0.06, 0.46]
export const DESK_SPAWN_LOCAL: [number, number, number] = [0.35, PLATFORM_HEIGHT + DESK_HEIGHT + 0.03, DESK_Z]
export const PARKED_LOCAL: [number, number, number] = [-0.45, PLATFORM_HEIGHT + DESK_HEIGHT + 0.03, DESK_Z]
export const QUEUE_PILE_LOCAL: [number, number][] = [
  [-2.15, -1.6],
  [-2.15, -1.05],
  [-2.15, -0.5],
  [-1.5, -1.6],
  [-1.5, -1.05],
  [-1.5, -0.5],
]
export const QUEUE_PILE_CAPACITY = 10

export const TRAY_X: Record<DecisionAction, number> = { RELEASE: -2.2, DENY: 0, FORWARD: 2.2 }
export const TRAY_Z = -1.5
export const TRAY_TOP = PLATFORM_HEIGHT + 0.16

export interface DepartmentLayout {
  center: [number, number]
  size: [number, number]
  yaw: number
}

function facingCenter(x: number, z: number): number {
  return Math.atan2(-x, -z)
}

function layout(x: number, z: number, w: number, d: number): DepartmentLayout {
  return { center: [x, z], size: [w, d], yaw: facingCenter(x, z) }
}

export const DEPARTMENT_LAYOUT: Record<Department, DepartmentLayout> = {
  reception: layout(0, 9.3, 5.2, 4.2),
  identity: layout(-7.3, 5.6, 4.4, 4.2),
  registry: layout(-10.1, -1.2, 4.4, 4.4),
  statistics: layout(-6.2, -7.7, 4.4, 4.2),
  decision: layout(0, -9.8, 6.6, 4.8),
  authority: layout(6.2, -7.7, 4.4, 4.2),
  protection: layout(10.1, -1.2, 4.4, 4.4),
}

export const GALLERY_CENTER: [number, number] = [7.5, 6.0]
export const GALLERY_RADIUS = 3.3

export function toWorld(department: Department, local: [number, number, number], out = new Vector3()): Vector3 {
  const { center, yaw } = DEPARTMENT_LAYOUT[department]
  const [lx, ly, lz] = local
  const cos = Math.cos(yaw)
  const sin = Math.sin(yaw)
  return out.set(center[0] + lx * cos + lz * sin, ly, center[1] - lx * sin + lz * cos)
}

export function standPoint(department: Department, out = new Vector3()): Vector3 {
  const depth = DEPARTMENT_LAYOUT[department].size[1]
  return toWorld(department, [0, PLATFORM_HEIGHT, depth / 2 - 0.95], out)
}

export function approachPoint(department: Department, out = new Vector3()): Vector3 {
  const depth = DEPARTMENT_LAYOUT[department].size[1]
  return toWorld(department, [0, 0, depth / 2 + 1.4], out)
}

export function facingYaw(department: Department): number {
  return DEPARTMENT_LAYOUT[department].yaw + Math.PI
}

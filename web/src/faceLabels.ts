import type { FaceStats } from './types'

// The six face slots are shared by all positions, but goalkeepers store the GK
// attribute set (Diving/Handling/Kicking/Reflexes/Speed/Positioning) in them.
// See fc26/ingest/fcratings_player.py _GK_LABELS for the slot mapping.
type FaceKey = keyof FaceStats

const OUTFIELD_FACE_KEYS: Array<[FaceKey, string]> = [
  ['pac', 'PAC'],
  ['sho', 'SHO'],
  ['pas', 'PAS'],
  ['dri', 'DRI'],
  ['def_', 'DEF'],
  ['phy', 'PHY'],
]

const GK_FACE_KEYS: Array<[FaceKey, string]> = [
  ['pac', 'DIV'],
  ['sho', 'HAN'],
  ['pas', 'KIC'],
  ['dri', 'REF'],
  ['def_', 'SPD'],
  ['phy', 'POS'],
]

export function faceKeys(position: string): Array<[FaceKey, string]> {
  return position === 'GK' ? GK_FACE_KEYS : OUTFIELD_FACE_KEYS
}

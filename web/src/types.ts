export interface FaceStats {
  pac: number | null
  sho: number | null
  pas: number | null
  dri: number | null
  def_: number | null
  phy: number | null
}

export interface Card {
  id: string
  player_name: string
  version: string
  ovr: number
  position: string
  alt_positions: string[]
  face: FaceStats
  subs: Record<string, number | null> | null
  playstyles: string[]
  playstyles_plus: string[]
  accelerate: string | null
  skill_moves: number | null
  weak_foot: number | null
  club: string | null
  league: string | null
  nation: string | null
  height_cm: number | null
  age: number | null
  price: number | null
  image_url: string | null
  bg_url: string | null
  futbin_url: string | null
  club_url: string | null
  league_url: string | null
  nation_url: string | null
  common_name: string | null
  source_url: string | null
  crawled_at: string | null
}

export interface CardListResponse {
  total: number
  cards: Card[]
}

export type SquadSlotValue = string | { id: string; style?: string }

export interface SquadFile {
  name: string
  formation: string
  starting_xi: Record<string, SquadSlotValue>
  manager?: { league?: string; nation?: string }
}

export interface SquadSummary {
  name: string
  path: string
}

export interface SlotChem {
  slot: string
  position: string
  card_id: string
  player_name: string
  version: string
  in_position: boolean
  chem: number
}

export interface TierStatus {
  kind: string
  name: string
  count: number
  points: number
  next_tier_at: number | null
}

export interface ChemReport {
  players: SlotChem[]
  team_total: number
  tiers: TierStatus[]
  warnings: string[]
}

export interface BuildXiPlayer extends Card {
  slot: string
}

export interface BuildResult {
  formation: string
  seed_cost: number
  total_cost: number
  team_chem: number
  xi: BuildXiPlayer[]
  squad: SquadFile
}

export interface Swap {
  slot: string
  out_id: string
  out_name: string
  out_version: string
  out_resale: number
  in_id: string
  in_name: string
  in_version: string
  in_price: number
  net_cost: number
  meta_delta: number
  chem_delta: number
  score_delta: number
}

export interface UpgradePlan {
  swaps: Swap[]
  spent: number
  budget: number
  score_before: number
  score_after: number
  chem_before: number
  chem_after: number
  warnings: string[]
}

export interface Meta {
  formations: Record<string, string[]>
  styles: string[]
  leagues: string[]
  nations: string[]
  clubs: string[]
  versions: string[]
}

export interface UpdateInfo {
  refreshed_at: string | null
  new_count: number
  updated_count: number
  new_cards: Card[]
}

export interface ValuePick extends Card {
  best_pos: string
  quality: number
  value: number
}

export interface ValueResponse {
  picks: ValuePick[]
}

import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { Card, Meta, SquadFile, ChemReport, BuildResult, UpgradePlan } from '../types'

export const MOCK_CARD: Card = {
  id: 'mbappe--base',
  player_name: 'Mbappe',
  version: 'base',
  ovr: 91,
  position: 'ST',
  alt_positions: [],
  face: { pac: 97, sho: 90, pas: 85, dri: 95, def_: 36, phy: 78 },
  subs: null,
  playstyles: [],
  playstyles_plus: [],
  accelerate: null,
  skill_moves: null,
  weak_foot: null,
  club: 'Real Madrid',
  league: 'La Liga',
  nation: 'France',
  height_cm: null,
  age: null,
  price: 1200000,
  source_url: null,
  crawled_at: null,
}

export const MOCK_HAALAND: Card = {
  ...MOCK_CARD,
  id: 'haaland--base',
  player_name: 'Haaland',
  position: 'ST',
  ovr: 90,
  club: 'Manchester City',
  league: 'Premier League',
  nation: 'Norway',
  price: 980000,
}

export const SLOTS_4231 = ['GK', 'RB', 'CB1', 'CB2', 'LB', 'CDM1', 'CDM2', 'CAM', 'RW', 'LW', 'ST'] as const

export const MOCK_META: Meta = {
  formations: {
    '4-2-3-1': [...SLOTS_4231],
    '4-3-3': ['GK', 'RB', 'CB1', 'CB2', 'LB', 'CM1', 'CM2', 'CM3', 'RW', 'LW', 'ST'],
  },
  styles: ['hunter', 'finisher', 'marksman', 'sniper'],
  leagues: ['La Liga', 'Premier League', 'Bundesliga'],
  versions: ['base', 'totw', 'tots'],
}

export const MOCK_SQUAD: SquadFile = {
  name: 'Test Squad',
  formation: '4-2-3-1',
  starting_xi: Object.fromEntries(SLOTS_4231.map(s => [s, 'mbappe--base'])),
}

export const MOCK_CHEM: ChemReport = {
  team_total: 33,
  players: SLOTS_4231.map(slot => ({
    slot,
    position: 'ST',
    card_id: 'mbappe--base',
    player_name: 'Mbappe',
    version: 'base',
    in_position: true,
    chem: 3,
  })),
  tiers: [],
  warnings: [],
}

export const MOCK_BUILD: BuildResult = {
  formation: '4-2-3-1',
  seed_cost: 100000,
  total_cost: 500000,
  team_chem: 33,
  xi: SLOTS_4231.map(slot => ({ slot, ...MOCK_CARD })),
  squad: MOCK_SQUAD,
}

export const MOCK_UPGRADE: UpgradePlan = {
  swaps: [{
    slot: 'ST',
    out_id: 'mbappe--base',
    out_name: 'Mbappe',
    out_version: 'base',
    out_resale: 1200000,
    in_id: 'haaland--base',
    in_name: 'Haaland',
    in_version: 'base',
    in_price: 980000,
    net_cost: -220000,
    meta_delta: 0.5,
    chem_delta: 0,
    score_delta: 0.5,
  }],
  spent: 0,
  budget: 500000,
  score_before: 10.0,
  score_after: 10.5,
  chem_before: 33,
  chem_after: 33,
  warnings: [],
}

export const handlers = [
  http.get('http://localhost:8026/api/meta', () =>
    HttpResponse.json({ ok: true, data: MOCK_META, error: null })),

  http.get('http://localhost:8026/api/cards', () =>
    HttpResponse.json({ ok: true, data: { total: 2, cards: [MOCK_CARD, MOCK_HAALAND] }, error: null })),

  http.get('http://localhost:8026/api/squads', () =>
    HttpResponse.json({ ok: true, data: [{ name: 'test-squad', path: 'squads/test-squad.json' }], error: null })),

  http.get('http://localhost:8026/api/squads/:name', () =>
    HttpResponse.json({ ok: true, data: MOCK_SQUAD, error: null })),

  http.put('http://localhost:8026/api/squads/:name', () =>
    HttpResponse.json({ ok: true, data: { name: 'test-squad', path: 'squads/test-squad.json' }, error: null })),

  http.post('http://localhost:8026/api/chem', () =>
    HttpResponse.json({ ok: true, data: MOCK_CHEM, error: null })),

  http.post('http://localhost:8026/api/build', () =>
    HttpResponse.json({ ok: true, data: MOCK_BUILD, error: null })),

  http.post('http://localhost:8026/api/upgrade', () =>
    HttpResponse.json({ ok: true, data: MOCK_UPGRADE, error: null })),

  http.get('http://localhost:8026/api/updates', () =>
    HttpResponse.json({
      ok: true,
      data: {
        refreshed_at: '2026-06-14T00:00:00+00:00',
        new_count: 2,
        updated_count: 5,
        new_cards: [MOCK_CARD, MOCK_HAALAND],
      },
      error: null,
    })),

  http.get('http://localhost:8026/api/value', () =>
    HttpResponse.json({
      ok: true,
      data: {
        picks: [
          { ...MOCK_CARD, best_pos: 'ST', quality: 88, value: 17.6 },
          { ...MOCK_HAALAND, best_pos: 'ST', quality: 90, value: 9.0 },
        ],
      },
      error: null,
    })),
]

export const server = setupServer(...handlers)

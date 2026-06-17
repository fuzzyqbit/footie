import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CardTile from './CardTile'
import { MOCK_CARD } from '../test/handlers'

test('shows OVR, name, position, price', () => {
  render(<CardTile card={MOCK_CARD} />)
  expect(screen.getByText('91')).toBeInTheDocument()
  expect(screen.getByText('Mbappe')).toBeInTheDocument()
  expect(screen.getByText('ST')).toBeInTheDocument()
  expect(screen.getByText('1.2M')).toBeInTheDocument()
})

test('click expands to show face stats', async () => {
  const user = userEvent.setup()
  render(<CardTile card={MOCK_CARD} />)
  expect(screen.queryByText('PAC')).not.toBeInTheDocument()
  await user.click(screen.getByText('Mbappe'))
  expect(screen.getByText('PAC')).toBeInTheDocument()
  expect(screen.getByText('97')).toBeInTheDocument()
})

test('click again collapses stats', async () => {
  const user = userEvent.setup()
  render(<CardTile card={MOCK_CARD} />)
  await user.click(screen.getByText('Mbappe'))
  await user.click(screen.getByText('Mbappe'))
  expect(screen.queryByText('PAC')).not.toBeInTheDocument()
})

test('shows the card version (base and special)', () => {
  const { rerender } = render(<CardTile card={MOCK_CARD} />)
  expect(screen.getByText('base')).toBeInTheDocument()
  rerender(<CardTile card={{ ...MOCK_CARD, version: 'TOTS' }} />)
  expect(screen.getByText('TOTS')).toBeInTheDocument()
})

test('shows null price as —', () => {
  render(<CardTile card={{ ...MOCK_CARD, price: null }} />)
  expect(screen.getByText('—')).toBeInTheDocument()
})

test('GK card shows goalkeeper stat labels, not outfield ones', async () => {
  const user = userEvent.setup()
  const gk = { ...MOCK_CARD, player_name: 'Alisson', position: 'GK' }
  render(<CardTile card={gk} />)
  await user.click(screen.getByText('Alisson'))
  expect(screen.getByText('DIV')).toBeInTheDocument()
  expect(screen.getByText('HAN')).toBeInTheDocument()
  expect(screen.queryByText('PAC')).not.toBeInTheDocument()
  expect(screen.queryByText('SHO')).not.toBeInTheDocument()
})

test('renders the player render image when card art is present', () => {
  render(<CardTile card={{
    ...MOCK_CARD,
    image_url: 'https://cdn.example/players/p1.png?w=485',
    bg_url: 'https://cdn.example/cards/hd/gold.png?w=644',
  }} />)
  const player = screen.getByAltText('Mbappe') as HTMLImageElement
  expect(player.src).toContain('/players/p1.png')
})


test('card art prefers common_name for the displayed name', () => {
  render(<CardTile card={{
    ...MOCK_CARD,
    player_name: 'Alejandro Balde Martínez',
    common_name: 'Balde',
    image_url: 'https://cdn.example/players/p1.png?w=485',
    bg_url: 'https://cdn.example/cards/hd/gold.png?w=644',
  }} />)
  expect(screen.getByText('Balde')).toBeInTheDocument()
})

test('card art renders club, league and nation logos when present', () => {
  const { container } = render(<CardTile card={{
    ...MOCK_CARD,
    image_url: 'https://cdn.example/players/p1.png?w=485',
    bg_url: 'https://cdn.example/cards/hd/gold.png?w=644',
    club_url: 'https://cdn.example/clubs/dark/241.png',
    league_url: 'https://cdn.example/league/dark/2222.png',
    nation_url: 'https://cdn.example/nation/45.png',
  }} />)
  const srcs = Array.from(container.querySelectorAll('img')).map(i => i.src)
  expect(srcs.some(s => s.includes('/clubs/dark/241.png'))).toBe(true)
  expect(srcs.some(s => s.includes('/league/dark/2222.png'))).toBe(true)
  expect(srcs.some(s => s.includes('/nation/45.png'))).toBe(true)
})


test('shows PlayStyles+ chips on the card', () => {
  render(<CardTile card={{ ...MOCK_CARD, playstyles_plus: ['Finesse Shot', 'Quick Step'] }} />)
  expect(screen.getByText('Finesse Shot')).toBeInTheDocument()
  expect(screen.getByText('Quick Step')).toBeInTheDocument()
})

test('renders no PlayStyles+ chips when empty', () => {
  render(<CardTile card={MOCK_CARD} />)
  expect(screen.queryByText('Finesse Shot')).not.toBeInTheDocument()
})

test('expanded detail shows position, alt positions, height and playstyle lists', async () => {
  const user = userEvent.setup()
  render(<CardTile card={{
    ...MOCK_CARD,
    position: 'ST',
    alt_positions: ['CF', 'LW'],
    height_cm: 190,
    playstyles: ['Power Shot', 'First Touch'],
    playstyles_plus: ['Finesse Shot'],
  }} />)
  await user.click(screen.getByText('Mbappe'))
  expect(screen.getByText('Preferred position')).toBeInTheDocument()
  expect(screen.getByText('Alternate positions')).toBeInTheDocument()
  expect(screen.getByText('CF, LW')).toBeInTheDocument()
  expect(screen.getByText('Height')).toBeInTheDocument()
  expect(screen.getByText('190 cm')).toBeInTheDocument()
  expect(screen.getByText('Power Shot, First Touch')).toBeInTheDocument()
})

test('expanded detail shows em-dash for missing alt positions and height', async () => {
  const user = userEvent.setup()
  render(<CardTile card={{ ...MOCK_CARD, alt_positions: [], height_cm: null }} />)
  await user.click(screen.getByText('Mbappe'))
  expect(screen.getByText('Alternate positions')).toBeInTheDocument()
  // both alt positions and height render as em-dash
  expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
})

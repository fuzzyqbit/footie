import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ComparePage from './ComparePage'
import { toggleWatch, clearWatchlist } from '../watchlist'
import { MOCK_CARD, MOCK_HAALAND } from '../test/handlers'

beforeEach(() => clearWatchlist())

test('empty state when nothing flagged', () => {
  render(<ComparePage />)
  expect(screen.getByText(/no flagged players yet/i)).toBeInTheDocument()
})

test('selecting flagged players builds a comparison table', async () => {
  const user = userEvent.setup()
  toggleWatch(MOCK_CARD)
  toggleWatch(MOCK_HAALAND)
  render(<ComparePage />)

  // before selecting, prompt to pick players
  expect(screen.getByText(/select one or more players/i)).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /Mbappe/ }))
  await user.click(screen.getByRole('button', { name: /Haaland/ }))

  expect(screen.getByRole('img', { name: /comparison radar/i })).toBeInTheDocument()
  const table = screen.getByRole('table')
  expect(within(table).getByText('OVR')).toBeInTheDocument()
  expect(within(table).getByText('91')).toBeInTheDocument() // Mbappe OVR (unique)
  // Haaland OVR 90 shares the value with some stat rows, so just assert presence
  expect(within(table).getAllByText('90').length).toBeGreaterThan(0)
})

test('caps selection at three players', async () => {
  const user = userEvent.setup()
  toggleWatch({ ...MOCK_CARD, id: 'a', player_name: 'AAA' })
  toggleWatch({ ...MOCK_CARD, id: 'b', player_name: 'BBB' })
  toggleWatch({ ...MOCK_CARD, id: 'c', player_name: 'CCC' })
  toggleWatch({ ...MOCK_CARD, id: 'd', player_name: 'DDD' })
  render(<ComparePage />)

  await user.click(screen.getByRole('button', { name: /AAA/ }))
  await user.click(screen.getByRole('button', { name: /BBB/ }))
  await user.click(screen.getByRole('button', { name: /CCC/ }))

  // fourth is disabled once three are chosen
  expect(screen.getByRole('button', { name: /DDD/ })).toBeDisabled()
})

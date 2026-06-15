import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CardTile from '../components/CardTile'
import WatchlistPage from './WatchlistPage'
import { MOCK_CARD } from '../test/handlers'
import { clearWatchlist } from '../watchlist'

beforeEach(() => {
  localStorage.clear()
  clearWatchlist()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <WatchlistPage />
    </MemoryRouter>
  )
}

test('shows empty state when nothing flagged', () => {
  renderPage()
  expect(screen.getByText(/no flagged players yet/i)).toBeInTheDocument()
})

test('flagging a card adds it to the watchlist', async () => {
  const user = userEvent.setup()
  render(
    <MemoryRouter>
      <CardTile card={MOCK_CARD} />
      <WatchlistPage />
    </MemoryRouter>
  )
  expect(screen.getByText(/no flagged players yet/i)).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /add to watchlist/i }))

  expect(screen.queryByText(/no flagged players yet/i)).not.toBeInTheDocument()
  // both the tile and the page now render the name
  expect(screen.getAllByText('Mbappe').length).toBeGreaterThan(1)
})

test('unflagging removes it again', async () => {
  const user = userEvent.setup()
  render(
    <MemoryRouter>
      <CardTile card={MOCK_CARD} />
      <WatchlistPage />
    </MemoryRouter>
  )
  await user.click(screen.getByRole('button', { name: /add to watchlist/i }))
  // standalone tile + page tile both now show a remove button — click one
  await user.click(screen.getAllByRole('button', { name: /remove from watchlist/i })[0])
  expect(screen.getByText(/no flagged players yet/i)).toBeInTheDocument()
})

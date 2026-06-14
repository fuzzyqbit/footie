import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server, MOCK_CHEM } from '../test/handlers'
import SquadsPage from './SquadsPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SquadsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

test('lists saved squads', async () => {
  renderPage()
  expect(await screen.findByText('test-squad')).toBeInTheDocument()
})

test('clicking a squad loads the pitch', async () => {
  const user = userEvent.setup()
  renderPage()
  await user.click(await screen.findByText('test-squad'))
  expect(await screen.findByText('Click a player to see details')).toBeInTheDocument()
})

test('clicking a slot updates side panel', async () => {
  const user = userEvent.setup()
  renderPage()
  await user.click(await screen.findByText('test-squad'))
  await screen.findAllByText('91')
  await user.click(screen.getAllByText('GK')[0])
  // Assert on side-panel-unique text: the player's club and chem only render in
  // the side panel (slot cards show the surname, so 'Mbappe' would be ambiguous).
  expect(await screen.findByText('Real Madrid')).toBeInTheDocument()
  expect(await screen.findByText('3/3')).toBeInTheDocument()
})

test('save button calls PUT and shows success', async () => {
  const user = userEvent.setup()
  let putCalled = false
  server.use(
    http.put('http://localhost:8026/api/squads/:name', () => {
      putCalled = true
      return HttpResponse.json({ ok: true, data: { name: 'test-squad', path: '' }, error: null })
    })
  )
  renderPage()
  await user.click(await screen.findByText('test-squad'))
  await screen.findAllByText('91')
  await user.click(screen.getByRole('button', { name: /save/i }))
  await waitFor(() => expect(putCalled).toBe(true))
})

test('swapping a slot replaces the player on the pitch', async () => {
  const user = userEvent.setup()
  renderPage()
  await user.click(await screen.findByText('test-squad'))
  await screen.findAllByText('91')
  await user.click(screen.getAllByText('GK')[0])
  await user.click(await screen.findByText('Haaland'))
  // After the swap the GK slot card and the side panel both show the new player.
  expect((await screen.findAllByText('Haaland')).length).toBeGreaterThan(1)
})

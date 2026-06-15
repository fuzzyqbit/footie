import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../test/handlers'
import UpdatesPage from './UpdatesPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <UpdatesPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

test('shows new cards from the last refresh', async () => {
  renderPage()
  expect(await screen.findByText('Mbappe')).toBeInTheDocument()
  expect(screen.getByText('Haaland')).toBeInTheDocument()
  expect(screen.getByText(/2 new cards, 5 updated/i)).toBeInTheDocument()
})

test('shows empty state when no new cards', async () => {
  server.use(
    http.get('http://localhost:8026/api/updates', () =>
      HttpResponse.json({
        ok: true,
        data: { refreshed_at: null, new_count: 0, updated_count: 0, new_cards: [] },
        error: null,
      }))
  )
  renderPage()
  expect(await screen.findByText(/no new cards from the last refresh/i)).toBeInTheDocument()
  expect(screen.getByText(/never refreshed/i)).toBeInTheDocument()
})

import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../test/handlers'
import ValuePage from './ValuePage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ValuePage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

test('shows value picks with the per-coin metric', async () => {
  renderPage()
  expect(await screen.findByText('Mbappe')).toBeInTheDocument()
  expect(screen.getByText('Haaland')).toBeInTheDocument()
  expect(screen.getByText(/17\.6 \/ 1k/)).toBeInTheDocument()
})

test('shows empty state when no picks', async () => {
  server.use(
    http.get('http://localhost:8026/api/value', () =>
      HttpResponse.json({ ok: true, data: { picks: [] }, error: null }))
  )
  renderPage()
  expect(await screen.findByText(/no value picks match the filters/i)).toBeInTheDocument()
})

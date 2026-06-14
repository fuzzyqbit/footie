import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../test/handlers'
import CardsPage from './CardsPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <CardsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

test('shows card tiles after load', async () => {
  renderPage()
  expect(await screen.findByText('Mbappe')).toBeInTheDocument()
  expect(screen.getByText('Haaland')).toBeInTheDocument()
})

test('shows total count', async () => {
  renderPage()
  expect(await screen.findByText(/2 cards/i)).toBeInTheDocument()
})

test('shows error message on API failure', async () => {
  server.use(
    http.get('http://localhost:8026/api/cards', () =>
      HttpResponse.json({ ok: false, data: null, error: 'DB offline' }))
  )
  renderPage()
  expect(await screen.findByText(/DB offline/i)).toBeInTheDocument()
})

test('prev/next pagination buttons present', async () => {
  renderPage()
  await screen.findByText('Mbappe')
  expect(screen.getByRole('button', { name: /prev/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument()
})

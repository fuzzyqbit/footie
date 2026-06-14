import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

function renderApp(path = '/cards') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

test('renders sidebar and redirects root to Cards', async () => {
  renderApp('/')
  expect(screen.getByText('FC 26')).toBeInTheDocument()
  expect(await screen.findByText('Mbappe')).toBeInTheDocument()
})

test('routes to the Squads page', async () => {
  renderApp('/squads')
  expect(await screen.findByText(/saved squads/i)).toBeInTheDocument()
})

test('routes to the Build page', async () => {
  renderApp('/build')
  expect(await screen.findByRole('button', { name: /^build$/i })).toBeInTheDocument()
})

test('routes to the Upgrade page', async () => {
  renderApp('/upgrade')
  expect(await screen.findByRole('button', { name: /find upgrades/i })).toBeInTheDocument()
})

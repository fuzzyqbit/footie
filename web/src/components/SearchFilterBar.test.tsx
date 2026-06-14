import { render, screen, act, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SearchFilterBar from './SearchFilterBar'
import type { CardParams } from '../api/cards'

function renderBar(onChange = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SearchFilterBar params={{}} onChange={onChange} />
    </QueryClientProvider>
  )
}

test('renders search input', () => {
  renderBar()
  expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
})

test('typing in search calls onChange after debounce', () => {
  vi.useFakeTimers()
  const onChange = vi.fn()
  renderBar(onChange)
  const input = screen.getByPlaceholderText(/search/i)
  fireEvent.change(input, { target: { value: 'mba' } })
  act(() => { vi.advanceTimersByTime(300) })
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ search: 'mba' }))
  vi.useRealTimers()
})

test('position select calls onChange with pos', () => {
  const onChange = vi.fn()
  renderBar(onChange)
  const select = screen.getByLabelText(/position/i)
  fireEvent.change(select, { target: { value: 'ST' } })
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ pos: 'ST' }))
})

import { render, screen, fireEvent } from '@testing-library/react'
import SearchSelect from './SearchSelect'

test('renders an input with datalist options and fires onChange', () => {
  const onChange = vi.fn()
  const { container } = render(
    <SearchSelect
      label="Club"
      placeholder="Any club"
      value=""
      options={['AS Roma', 'Real Madrid']}
      onChange={onChange}
    />,
  )
  const input = screen.getByLabelText('Club')
  // datalist wires the input to the option list
  expect(input).toHaveAttribute('list', container.querySelector('datalist')?.id)
  expect(container.querySelectorAll('datalist option')).toHaveLength(2)

  fireEvent.change(input, { target: { value: 'Roma' } })
  expect(onChange).toHaveBeenCalledWith('Roma')
})

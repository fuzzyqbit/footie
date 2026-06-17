interface Props {
  label: string
  value: string
  options: string[]
  placeholder: string
  onChange: (value: string) => void
  className?: string
}

// A text input backed by a <datalist> so long option lists (nations, clubs)
// get native typeahead — start typing "Roma" and the match surfaces.
export default function SearchSelect({
  label,
  value,
  options,
  placeholder,
  onChange,
  className = '',
}: Props) {
  const listId = `searchselect-${label.toLowerCase().replace(/\s+/g, '-')}`
  return (
    <>
      <input
        list={listId}
        aria-label={label}
        value={value}
        placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        className={`bg-card border border-border rounded px-2 py-1.5 text-sm text-fg placeholder-muted focus:outline-none focus:border-gold ${className}`}
      />
      <datalist id={listId}>
        {options.map(o => (
          <option key={o} value={o} />
        ))}
      </datalist>
    </>
  )
}

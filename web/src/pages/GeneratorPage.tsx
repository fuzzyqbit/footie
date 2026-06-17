import { useMemo, useRef, useState } from 'react'
import { useAllCards } from '../api/cards'
import { faceKeys } from '../faceLabels'
import SearchSelect from '../components/SearchSelect'

const POSITIONS = [
  'GK', 'RB', 'RWB', 'CB', 'LB', 'LWB', 'CDM', 'CM', 'CAM',
  'RM', 'LM', 'RW', 'LW', 'ST', 'CF',
] as const

interface Background {
  url: string
  version: string
}

// The six face slots are positional in the form (slot 0..5); the labels follow
// the chosen position via faceKeys (GK swaps PAC/SHO/... for DIV/HAN/...).
const DEFAULT_STATS = [85, 82, 80, 84, 45, 78]

function clampStat(v: number): number {
  if (Number.isNaN(v)) return 1
  return Math.max(1, Math.min(99, Math.round(v)))
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('image load failed'))
    img.src = src
  })
}

// Downscale an image to <=maxSide on its longest edge and return a PNG data URL,
// keeping uploaded photos small for the live preview and PNG export.
function scaleToDataUrl(img: HTMLImageElement, maxSide: number): string {
  const scale = Math.min(1, maxSide / Math.max(img.width, img.height))
  const w = Math.max(1, Math.round(img.width * scale))
  const h = Math.max(1, Math.round(img.height * scale))
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) return img.src
  ctx.drawImage(img, 0, 0, w, h)
  return canvas.toDataURL('image/png')
}

// Strip a photo's background with no dependency: flood-fill inward from the
// border, clearing every pixel that stays within tolerance of the averaged
// corner colour. Removes a connected, roughly-uniform studio/solid backdrop
// while leaving the subject (which the border fill can't reach) intact. The
// result is downscaled to <=512px so the data URL stays small for the preview
// and PNG export. Best-effort: busy/gradient backdrops won't fully clear.
function stripBackground(img: HTMLImageElement): string {
  const maxSide = 512
  const scale = Math.min(1, maxSide / Math.max(img.width, img.height))
  const w = Math.max(1, Math.round(img.width * scale))
  const h = Math.max(1, Math.round(img.height * scale))
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) return img.src
  ctx.drawImage(img, 0, 0, w, h)
  const id = ctx.getImageData(0, 0, w, h)
  const d = id.data

  const cornerIdx = [0, (w - 1) * 4, (h - 1) * w * 4, ((h - 1) * w + (w - 1)) * 4]
  let r = 0, g = 0, b = 0
  for (const c of cornerIdx) {
    r += d[c]; g += d[c + 1]; b += d[c + 2]
  }
  r /= 4; g /= 4; b /= 4

  const THRESHOLD = 4000 // squared RGB distance (~36/channel)
  const matches = (px: number) => {
    const o = px * 4
    const dr = d[o] - r, dg = d[o + 1] - g, db = d[o + 2] - b
    return dr * dr + dg * dg + db * db <= THRESHOLD
  }

  const visited = new Uint8Array(w * h)
  const stack: number[] = []
  const seed = (x: number, y: number) => {
    const i = y * w + x
    if (!visited[i] && matches(i)) {
      visited[i] = 1
      stack.push(i)
    }
  }
  for (let x = 0; x < w; x++) { seed(x, 0); seed(x, h - 1) }
  for (let y = 0; y < h; y++) { seed(0, y); seed(w - 1, y) }

  while (stack.length) {
    const i = stack.pop()!
    d[i * 4 + 3] = 0
    const x = i % w
    const y = (i - x) / w
    if (x > 0) { const n = i - 1; if (!visited[n] && matches(n)) { visited[n] = 1; stack.push(n) } }
    if (x < w - 1) { const n = i + 1; if (!visited[n] && matches(n)) { visited[n] = 1; stack.push(n) } }
    if (y > 0) { const n = i - w; if (!visited[n] && matches(n)) { visited[n] = 1; stack.push(n) } }
    if (y < h - 1) { const n = i + w; if (!visited[n] && matches(n)) { visited[n] = 1; stack.push(n) } }
  }

  ctx.putImageData(id, 0, 0)
  return canvas.toDataURL('image/png')
}

// The live preview reproduces CardArt's exact layout: a fixed dark backing,
// the signed frame PNG, an optional player render, and white overlay text with
// the shared textShadow so it reads on any frame in light AND dark themes.
function Preview({
  name,
  ovr,
  position,
  stats,
  bgUrl,
  imageUrl,
  clubUrl,
  leagueUrl,
  nationUrl,
  previewRef,
}: {
  name: string
  ovr: number
  position: string
  stats: number[]
  bgUrl: string | null
  imageUrl: string
  clubUrl: string | null
  leagueUrl: string | null
  nationUrl: string | null
  previewRef: React.RefObject<HTMLDivElement | null>
}) {
  const labels = faceKeys(position)
  const shadow = { textShadow: '0 0 2px rgba(0,0,0,0.95), 0 1px 3px rgba(0,0,0,0.85)' }
  return (
    <div
      ref={previewRef}
      className="relative w-full aspect-[7/10] select-none rounded-md bg-[#0f0f1a]"
    >
      {bgUrl && (
        <img
          src={bgUrl}
          alt=""
          aria-hidden
          crossOrigin="anonymous"
          className="absolute inset-0 w-full h-full object-contain"
        />
      )}
      {imageUrl && (
        <img
          src={imageUrl}
          alt={name}
          crossOrigin="anonymous"
          className="absolute left-1/2 top-[12%] w-[62%] max-h-[48%] -translate-x-1/2 object-contain drop-shadow"
        />
      )}
      <div
        className="absolute left-[15%] top-[22%] flex flex-col items-center leading-none"
        style={shadow}
      >
        <span className="text-white font-extrabold text-[clamp(0.9rem,4vw,1.6rem)]">{ovr}</span>
        <span className="text-white font-bold text-[clamp(0.5rem,2.2vw,0.8rem)]">{position}</span>
      </div>
      <div
        className="absolute inset-x-0 top-[60%] text-center px-2"
        style={shadow}
      >
        <div className="text-white font-bold uppercase tracking-tight truncate text-[clamp(0.55rem,3vw,1rem)]">
          {name || '—'}
        </div>
      </div>
      <div
        className="absolute inset-x-[12%] bottom-[20%] grid grid-cols-3 gap-x-2 gap-y-0.5 text-white"
        style={shadow}
      >
        {labels.map(([key, label], i) => (
          <div key={key} className="flex justify-center gap-1 text-[clamp(0.45rem,2.2vw,0.75rem)] font-semibold">
            <span>{stats[i] ?? '—'}</span>
            <span className="opacity-70">{label}</span>
          </div>
        ))}
      </div>
      {(clubUrl || leagueUrl || nationUrl) && (
        <div className="absolute inset-x-0 bottom-[12%] flex items-center justify-center gap-2">
          {clubUrl && <img src={clubUrl} alt="" aria-hidden crossOrigin="anonymous" className="h-4 w-auto object-contain drop-shadow" />}
          {leagueUrl && <img src={leagueUrl} alt="" aria-hidden crossOrigin="anonymous" className="h-4 w-auto object-contain drop-shadow" />}
          {nationUrl && <img src={nationUrl} alt="" aria-hidden crossOrigin="anonymous" className="h-4 w-auto object-contain drop-shadow" />}
        </div>
      )}
    </div>
  )
}

export default function GeneratorPage() {
  const { data, isLoading } = useAllCards()

  // Distinct frames from the card data: keep the first bg_url seen per version
  // so the picker offers one labelled thumbnail per card version (Icon, TOTY,
  // TOTS, base, ...). Sorted with "base" last so specials surface first.
  const backgrounds = useMemo<Background[]>(() => {
    const byVersion = new Map<string, string>()
    for (const card of data?.cards ?? []) {
      if (!card.bg_url) continue
      if (!byVersion.has(card.version)) byVersion.set(card.version, card.bg_url)
    }
    return Array.from(byVersion, ([version, url]) => ({ version, url })).sort((a, b) => {
      if (a.version.toLowerCase() === 'base') return 1
      if (b.version.toLowerCase() === 'base') return -1
      return a.version.localeCompare(b.version)
    })
  }, [data])

  // Club / league / nation pickers come from the dataset, each distinct name
  // mapped to the first crest URL seen so the preview can show the badge.
  const { clubs, leagues, nations, crest } = useMemo(() => {
    const club = new Map<string, string>()
    const league = new Map<string, string>()
    const nation = new Map<string, string>()
    for (const c of data?.cards ?? []) {
      if (c.club && c.club_url && !club.has(c.club)) club.set(c.club, c.club_url)
      if (c.league && c.league_url && !league.has(c.league)) league.set(c.league, c.league_url)
      if (c.nation && c.nation_url && !nation.has(c.nation)) nation.set(c.nation, c.nation_url)
    }
    return {
      clubs: [...club.keys()].sort((a, b) => a.localeCompare(b)),
      leagues: [...league.keys()].sort((a, b) => a.localeCompare(b)),
      nations: [...nation.keys()].sort((a, b) => a.localeCompare(b)),
      crest: { club, league, nation },
    }
  }, [data])

  const [name, setName] = useState('')
  const [ovr, setOvr] = useState(90)
  const [position, setPosition] = useState<string>('ST')
  const [stats, setStats] = useState<number[]>(DEFAULT_STATS)
  const [bgUrl, setBgUrl] = useState<string | null>(null)
  const [imageUrl, setImageUrl] = useState('')
  const [downloading, setDownloading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [club, setClub] = useState('')
  const [league, setLeague] = useState('')
  const [nation, setNation] = useState('')

  const previewRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // Default the frame to the first available background once data arrives.
  const effectiveBg = bgUrl ?? backgrounds[0]?.url ?? null

  const labels = faceKeys(position)

  function setStat(i: number, v: number) {
    setStats(s => s.map((x, j) => (j === i ? clampStat(v) : x)))
  }

  // Read an uploaded photo, strip its background on the client, and use the
  // result as the card's player layer. Falls back to the raw image if the
  // canvas pipeline fails (e.g. a decode error on an exotic format).
  async function handleFile(file: File | undefined) {
    if (!file) return
    setProcessing(true)
    try {
      // Primary: ML cut-out running fully client-side (WASM). Lazy-imported so
      // the model only downloads when someone actually uploads a photo. If the
      // model can't load or fails, fall back to the flood-fill chroma key, which
      // only clears a uniform backdrop. Either path downscales the result so the
      // data URL stays small for the preview and PNG export.
      try {
        const { removeBackground } = await import('@imgly/background-removal')
        const blob = await removeBackground(file)
        const img = await loadImage(URL.createObjectURL(blob))
        setImageUrl(scaleToDataUrl(img, 512))
      } catch {
        const raw = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result as string)
          reader.onerror = () => reject(new Error('read failed'))
          reader.readAsDataURL(file)
        })
        const img = await loadImage(raw)
        try {
          setImageUrl(stripBackground(img))
        } catch {
          setImageUrl(scaleToDataUrl(img, 512))
        }
      }
    } catch {
      alert('Could not process that image. Try a different file.')
    } finally {
      setProcessing(false)
    }
  }

  // Export by compositing the card on a canvas at the same fractional positions
  // the Preview uses. We load each image with crossOrigin so the cross-origin
  // futbin frame/crests don't taint the canvas (the CDN sends CORS headers, so
  // the preview already loads them this way), and the uploaded photo is a same
  // origin data URL. This is deterministic — earlier DOM-serialisation routes
  // dropped the <img> layers and exported only the text.
  async function downloadPng() {
    setDownloading(true)
    try {
      const W = 700
      const H = 1000
      const canvas = document.createElement('canvas')
      canvas.width = W
      canvas.height = H
      const ctx = canvas.getContext('2d')
      if (!ctx) throw new Error('no canvas context')
      ctx.fillStyle = '#0f0f1a'
      ctx.fillRect(0, 0, W, H)

      // Prefer the <img> nodes the preview already decoded: they were loaded
      // with crossOrigin from the futbin CDN, so they draw onto the canvas
      // without a fresh cross-origin re-fetch (which sometimes fails and left
      // the frame + crests missing from the export). Fall back to loading the
      // URL directly only when a node isn't present/decoded yet.
      const domImgs = previewRef.current
        ? Array.from(previewRef.current.querySelectorAll('img'))
        : []
      const fromDom = (src: string | null) =>
        src
          ? domImgs.find(i => i.src === src && i.complete && i.naturalWidth > 0) ?? null
          : null
      const load = (src: string | null) =>
        new Promise<HTMLImageElement | null>(resolve => {
          if (!src) return resolve(null)
          const im = new Image()
          im.crossOrigin = 'anonymous'
          im.onload = () => resolve(im)
          im.onerror = () => resolve(null)
          im.src = src
        })
      const getImg = async (src: string | null) => fromDom(src) ?? (await load(src))
      const drawContain = (
        im: HTMLImageElement, bx: number, by: number, bw: number, bh: number, anchorTop = false,
      ) => {
        const sc = Math.min(bw / im.naturalWidth, bh / im.naturalHeight)
        const dw = im.naturalWidth * sc
        const dh = im.naturalHeight * sc
        ctx.drawImage(im, bx + (bw - dw) / 2, anchorTop ? by : by + (bh - dh) / 2, dw, dh)
      }

      const frame = await getImg(effectiveBg)
      if (frame) drawContain(frame, 0, 0, W, H)
      const player = await getImg(imageUrl)
      if (player) drawContain(player, 0.19 * W, 0.14 * H, 0.62 * W, 0.48 * H, true)

      ctx.shadowColor = 'rgba(0,0,0,0.9)'
      ctx.shadowBlur = 3
      ctx.shadowOffsetY = 1
      ctx.fillStyle = '#fff'
      ctx.textBaseline = 'top'

      const ovrF = 0.085 * W
      ctx.textAlign = 'left'
      ctx.font = `800 ${ovrF}px system-ui, sans-serif`
      const ovrStr = String(ovr)
      ctx.fillText(ovrStr, 0.15 * W, 0.22 * H)
      const ovrW = ctx.measureText(ovrStr).width
      ctx.textAlign = 'center'
      ctx.font = `700 ${0.045 * W}px system-ui, sans-serif`
      ctx.fillText(position, 0.15 * W + ovrW / 2, 0.22 * H + ovrF)

      ctx.font = `700 ${0.052 * W}px system-ui, sans-serif`
      ctx.fillText((name || '—').toUpperCase(), 0.5 * W, 0.6 * H)

      ctx.font = `600 ${0.04 * W}px system-ui, sans-serif`
      const statLabels = faceKeys(position)
      const colX = [0, 1, 2].map(c => 0.12 * W + 0.76 * W * (c + 0.5) / 3)
      const rowH = 0.05 * H
      const blockBottom = 0.8 * H
      statLabels.forEach(([, label], i) => {
        const x = colX[i % 3]
        const y = (i < 3 ? blockBottom - 2 * rowH : blockBottom - rowH)
        ctx.fillText(`${stats[i] ?? '—'} ${label}`, x, y)
      })

      ctx.shadowBlur = 2
      const crestSrcs = [
        crest.club.get(club), crest.league.get(league), crest.nation.get(nation),
      ].filter(Boolean) as string[]
      const crestImgs = (await Promise.all(crestSrcs.map(getImg))).filter(Boolean) as HTMLImageElement[]
      if (crestImgs.length) {
        const ch = 0.05 * H
        const gap = 0.02 * W
        const widths = crestImgs.map(im => ch * (im.naturalWidth / im.naturalHeight))
        const total = widths.reduce((a, b) => a + b, 0) + gap * (crestImgs.length - 1)
        let x = 0.5 * W - total / 2
        const y = 0.88 * H - ch
        crestImgs.forEach((im, i) => {
          ctx.drawImage(im, x, y, widths[i], ch)
          x += widths[i] + gap
        })
      }

      const link = document.createElement('a')
      link.download = `${(name || 'card').replace(/\s+/g, '-').toLowerCase()}.png`
      link.href = canvas.toDataURL('image/png')
      link.click()
    } catch {
      alert(
        'Could not export PNG. Some card images may have blocked cross-origin export — ' +
          'try a different frame or photo.',
      )
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-fg mb-1">Create</h1>
      <p className="text-muted text-sm mb-4">
        Build a custom FC card. Pick a frame, set the rating and stats, and the preview updates live.
      </p>

      <div className="flex flex-col lg:flex-row gap-8 items-start">
        {/* Form */}
        <div className="flex-1 min-w-0 w-full max-w-xl flex flex-col gap-5">
          <label className="flex flex-col gap-1">
            <span className="text-muted text-sm">Player name</span>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Mbappe"
              className="bg-card border border-border rounded px-3 py-2 text-fg text-sm focus:outline-none focus:border-gold"
            />
          </label>

          <div className="flex gap-4">
            <label className="flex flex-col gap-1 w-28">
              <span className="text-muted text-sm">OVR</span>
              <input
                type="number"
                min={1}
                max={99}
                value={ovr}
                onChange={e => setOvr(clampStat(Number(e.target.value)))}
                className="bg-card border border-border rounded px-3 py-2 text-fg text-sm focus:outline-none focus:border-gold"
              />
            </label>
            <label className="flex flex-col gap-1 flex-1">
              <span className="text-muted text-sm">Position</span>
              <select
                aria-label="Position"
                value={position}
                onChange={e => setPosition(e.target.value)}
                className="bg-card border border-border rounded px-3 py-2 text-fg text-sm focus:outline-none focus:border-gold"
              >
                {POSITIONS.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </label>
          </div>

          <fieldset className="flex flex-col gap-3">
            <legend className="text-muted text-sm mb-1">Face stats</legend>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {labels.map(([key, label], i) => (
                <label key={key} className="flex flex-col gap-1">
                  <span className="text-fg text-xs font-semibold flex justify-between">
                    <span>{label}</span>
                    <span className="text-gold">{stats[i]}</span>
                  </span>
                  <input
                    type="range"
                    min={1}
                    max={99}
                    value={stats[i]}
                    onChange={e => setStat(i, Number(e.target.value))}
                    aria-label={label}
                    className="accent-gold"
                  />
                </label>
              ))}
            </div>
          </fieldset>

          <div className="flex flex-col gap-1">
            <span className="text-muted text-sm">Player photo (optional)</span>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              onChange={e => handleFile(e.target.files?.[0])}
              className="hidden"
            />
            <div className="flex items-center gap-3 flex-wrap">
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={processing}
                className="rounded bg-card border border-border px-3 py-2 text-fg text-sm hover:bg-card-hover transition-colors disabled:opacity-50"
              >
                {processing ? 'Removing background…' : 'Upload photo'}
              </button>
              {imageUrl && !processing && (
                <button
                  type="button"
                  onClick={() => {
                    setImageUrl('')
                    if (fileRef.current) fileRef.current.value = ''
                  }}
                  className="text-muted text-sm hover:text-fg transition-colors"
                >
                  Remove photo
                </button>
              )}
            </div>
            <span className="text-muted text-xs">
              Uploads are scaled down and the background is stripped in your browser. Solid backdrops clear best.
            </span>
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-muted text-sm">…or paste a player image URL</span>
            <input
              type="text"
              value={imageUrl.startsWith('data:') ? '' : imageUrl}
              onChange={e => setImageUrl(e.target.value)}
              placeholder="https://..."
              disabled={processing}
              className="bg-card border border-border rounded px-3 py-2 text-fg text-sm focus:outline-none focus:border-gold disabled:opacity-50"
            />
          </label>

          <div className="flex flex-col gap-3">
            <span className="text-muted text-sm">Club, league &amp; nation</span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-fg text-xs font-semibold">Club</span>
                <SearchSelect label="Club" value={club} options={clubs} placeholder="Any club" onChange={setClub} />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-fg text-xs font-semibold">League</span>
                <SearchSelect label="League" value={league} options={leagues} placeholder="Any league" onChange={setLeague} />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-fg text-xs font-semibold">Nation</span>
                <SearchSelect label="Nation" value={nation} options={nations} placeholder="Any nation" onChange={setNation} />
              </label>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-muted text-sm">Background</span>
            {isLoading ? (
              <p className="text-muted text-sm">Loading frames…</p>
            ) : backgrounds.length === 0 ? (
              <p className="text-muted text-sm">No frames available.</p>
            ) : (
              <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
                {backgrounds.map(bg => {
                  const active = effectiveBg === bg.url
                  return (
                    <button
                      key={bg.version}
                      type="button"
                      onClick={() => setBgUrl(bg.url)}
                      aria-pressed={active}
                      title={bg.version}
                      className={`relative rounded-md p-1 border transition-colors ${
                        active
                          ? 'border-gold bg-navy'
                          : 'border-border bg-card hover:bg-card-hover'
                      }`}
                    >
                      <div className="aspect-[7/10] rounded bg-[#0f0f1a]">
                        <img
                          src={bg.url}
                          alt={bg.version}
                          className="w-full h-full object-contain"
                        />
                      </div>
                      <span className="block truncate text-center text-[0.65rem] mt-0.5 text-muted">
                        {bg.version}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          <div>
            <button
              type="button"
              onClick={downloadPng}
              disabled={downloading}
              className="rounded bg-gold/20 text-gold ring-1 ring-gold/30 px-4 py-2 text-sm font-semibold hover:bg-gold/30 transition-colors disabled:opacity-50"
            >
              {downloading ? 'Exporting…' : 'Download PNG'}
            </button>
          </div>
        </div>

        {/* Live preview */}
        <div className="w-full max-w-xs shrink-0">
          <Preview
            name={name}
            ovr={ovr}
            position={position}
            stats={stats}
            bgUrl={effectiveBg}
            imageUrl={imageUrl}
            clubUrl={crest.club.get(club) ?? null}
            leagueUrl={crest.league.get(league) ?? null}
            nationUrl={crest.nation.get(nation) ?? null}
            previewRef={previewRef}
          />
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { Search, Activity, Gauge, Layers, ShieldCheck } from 'lucide-react'
import clsx from 'clsx'
import { categoriesAPI, productsAPI, trackIntent } from '../api/client'
import ProductCard from '../components/ProductCard'

const PAGE_SIZE = 12

const STEPS = [
  { n: '01', icon: Activity,    title: 'Signals',      body: 'Views, searches, cart adds, checkouts and purchases are recorded as intent events.' },
  { n: '02', icon: Gauge,       title: 'Demand score', body: 'Each signal carries a weight. The last hour is summed into a single score per product.' },
  { n: '03', icon: Layers,      title: 'Price bands',  body: 'The score maps to a band — low, normal, high or surge — and a multiplier on the base price.' },
  { n: '04', icon: ShieldCheck, title: 'Seller bounds', body: 'Every price is clamped between the floor and ceiling the seller set. Never outside them.' },
]

export default function Home() {
  const [products,   setProducts]   = useState([])
  const [trending,   setTrending]   = useState([])
  const [categories, setCategories] = useState([])
  const [loading,    setLoading]    = useState(true)
  const [search,     setSearch]     = useState('')
  const [query,      setQuery]      = useState('')     // the search that was actually submitted
  const [category,   setCategory]   = useState(null)
  const [page,       setPage]       = useState(1)
  const [meta,       setMeta]       = useState({})

  useEffect(() => {
    categoriesAPI.list().then(r => setCategories(r.data)).catch(() => {})
    productsAPI.trending(4).then(r => setTrending(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const params = { page, page_size: PAGE_SIZE }
    if (query) params.search = query
    if (category) params.category_id = category
    productsAPI.list(params)
      .then(({ data }) => {
        if (cancelled) return
        setProducts(data.items)
        setMeta(data)
        // Searching is a (weak) demand signal for whatever comes back
        if (query) data.items.slice(0, 3).forEach(p => trackIntent(p.id, 'ProductSearched', { query }))
      })
      .catch(() => { if (!cancelled) { setProducts([]); setMeta({}) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [page, query, category])

  const handleSearch = (e) => {
    e.preventDefault()
    const q = search.trim()
    setPage(1)
    setQuery(q.length >= 2 ? q : '')
  }

  const selectCategory = (id) => { setPage(1); setCategory(id) }
  const browsing = !query && !category && page === 1

  const stats = [
    { value: meta.total ?? '—', label: 'Products live' },
    { value: '1 hour',          label: 'Demand window' },
    { value: 'Four',            label: 'Pricing bands' },
    { value: 'Live',            label: 'Price updates' },
  ]

  return (
    <div>
      {/* Hero */}
      <section className="border-b border-line">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 pt-20 pb-16">
          <p className="eyebrow mb-6">Real-time demand intelligence</p>
          <h1 className="display text-5xl sm:text-7xl leading-[0.95] max-w-4xl">
            Prices that move<br className="hidden sm:block" /> with the market.
          </h1>
          <p className="mt-7 text-lg text-ink-500 max-w-xl leading-relaxed">
            Every product is priced in real time from live demand signals. Watch prices shift
            as people browse, add to cart and check out.
          </p>

          <form onSubmit={handleSearch} className="mt-12 flex items-center gap-3 max-w-md border-b border-line-strong pb-2.5">
            <Search className="w-4 h-4 text-ink-400 flex-shrink-0" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search products"
              aria-label="Search products"
              className="flex-1 bg-transparent text-sm text-ink placeholder:text-ink-400 focus:outline-none"
            />
            <button type="submit" className="btn-primary px-4 py-1.5">Search</button>
          </form>
        </div>
      </section>

      {/* Stat strip */}
      <section className="border-b border-line bg-paper-50">
        <dl className="max-w-7xl mx-auto px-5 sm:px-8 grid grid-cols-2 lg:grid-cols-4 divide-x divide-line">
          {stats.map((s, i) => (
            <div key={s.label} className={clsx('py-7', i === 0 ? 'lg:pr-8' : 'px-5 sm:px-8')}>
              <dt className="display text-3xl leading-none">{s.value}</dt>
              <dd className="eyebrow mt-2">{s.label}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* How the pricing works */}
      <section className="border-b border-line">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-20">
          <h2 className="display text-4xl sm:text-5xl max-w-2xl leading-[1.05]">We priced it by demand.</h2>
          <p className="mt-5 text-ink-500 max-w-lg">
            Four steps, re-run every time somebody interacts with a product.
          </p>

          <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 lg:gap-0 lg:divide-x divide-line">
            {STEPS.map(({ n, icon: Icon, title, body }, i) => (
              <div key={n} className={clsx('lg:px-8', i === 0 && 'lg:pl-0', i === STEPS.length - 1 && 'lg:pr-0')}>
                <div className="flex items-center gap-3 mb-4">
                  <Icon className="w-4 h-4 text-sage-600" />
                  <span className="eyebrow">{n}</span>
                </div>
                <h3 className="display text-xl mb-2">{title}</h3>
                <p className="text-sm text-ink-500 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Catalog */}
      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-16">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 mb-10">
          <div>
            <h2 className="display text-4xl">
              {query ? `Results for “${query}”` : category ? 'Category' : 'The catalog'}
            </h2>
            <p className="text-sm text-ink-500 mt-2">
              {loading ? 'Loading…' : `${meta.total ?? 0} product${meta.total === 1 ? '' : 's'}`}
              <span className="inline-flex items-center gap-1.5 ml-3">
                <span className="w-1.5 h-1.5 bg-sage-500 rounded-full animate-pulse" />
                Live pricing active
              </span>
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={() => selectCategory(null)}
              className={clsx('px-3.5 py-1.5 rounded-full border text-xs transition-colors',
                !category ? 'bg-sage-900 border-sage-900 text-paper-50' : 'border-line text-ink-500 hover:text-ink')}>
              All
            </button>
            {categories.map(c => (
              <button key={c.id} onClick={() => selectCategory(c.id)}
                className={clsx('px-3.5 py-1.5 rounded-full border text-xs transition-colors',
                  category === c.id ? 'bg-sage-900 border-sage-900 text-paper-50' : 'border-line text-ink-500 hover:text-ink')}>
                {c.name}
              </button>
            ))}
          </div>
        </div>

        {/* Trending — maintained by the Kafka event worker */}
        {browsing && trending.length > 0 && (
          <div className="mb-16">
            <div className="flex items-baseline gap-3 mb-6 pb-3 border-b border-line">
              <h3 className="display text-2xl">Trending now</h3>
              <span className="eyebrow">Most demand this hour</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {trending.map(p => <ProductCard key={p.id} product={p} />)}
            </div>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-80 rounded-2xl border border-line bg-paper-50 animate-pulse" />
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="text-center py-24">
            <p className="display text-3xl mb-2">Nothing here.</p>
            <p className="text-ink-500">No products match that search.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {products.map(p => <ProductCard key={p.id} product={p} />)}
          </div>
        )}

        {meta.pages > 1 && (
          <div className="flex justify-center gap-2 mt-14">
            {Array.from({ length: meta.pages }).map((_, i) => (
              <button key={i} onClick={() => setPage(i + 1)}
                className={clsx('w-9 h-9 rounded-full border text-sm transition-colors',
                  page === i + 1 ? 'bg-sage-900 border-sage-900 text-paper-50' : 'border-line text-ink-500 hover:text-ink')}>
                {i + 1}
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

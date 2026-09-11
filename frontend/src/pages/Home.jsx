import { useState, useEffect } from 'react'
import { Search, Zap, Flame } from 'lucide-react'
import clsx from 'clsx'
import { categoriesAPI, productsAPI, trackIntent } from '../api/client'
import ProductCard from '../components/ProductCard'

const PAGE_SIZE = 12

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
        // Searching for something is a (weak) demand signal for what comes back
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

  const selectCategory = (id) => {
    setPage(1)
    setCategory(id)
  }

  const browsing = !query && !category && page === 1

  return (
    <div className="min-h-screen">

      {/* Hero */}
      <section className="relative border-b border-surface-700 bg-gradient-to-b from-surface-800 to-surface-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-600/10 border border-brand-600/20 text-brand-500 text-xs font-medium mb-6">
            <Zap className="w-3.5 h-3.5" />
            Powered by Real-Time Demand Intelligence
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight mb-4">
            Prices that move<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-500 to-purple-400">
              with the market
            </span>
          </h1>
          <p className="text-slate-400 max-w-xl mx-auto text-lg mb-10">
            Every product is priced in real-time based on demand signals.
            Watch prices update live as others browse, add to cart, and checkout.
          </p>

          {/* Search */}
          <form onSubmit={handleSearch} className="flex max-w-md mx-auto gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search products…"
                aria-label="Search products"
                className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-surface-700 border border-surface-600 text-sm placeholder:text-slate-500 focus:outline-none focus:border-brand-600 transition-colors"
              />
            </div>
            <button type="submit" className="px-5 py-2.5 bg-brand-600 hover:bg-brand-700 rounded-xl text-sm font-medium transition-colors">
              Search
            </button>
          </form>
        </div>
      </section>

      {/* Stats + category filter */}
      <section className="border-b border-surface-700 bg-surface-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
          <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
            <button onClick={() => selectCategory(null)}
              className={clsx('px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors',
                !category ? 'bg-brand-600 text-white' : 'bg-surface-700 text-slate-400 hover:text-white')}>
              All
            </button>
            {categories.map(c => (
              <button key={c.id} onClick={() => selectCategory(c.id)}
                className={clsx('px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors',
                  category === c.id ? 'bg-brand-600 text-white' : 'bg-surface-700 text-slate-400 hover:text-white')}>
                {c.name}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-500 flex-shrink-0">
            <span>{loading ? 'Loading…' : `${meta.total ?? 0} product${meta.total === 1 ? '' : 's'}${query ? ` for “${query}”` : ''}`}</span>
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              Live pricing active
            </span>
          </div>
        </div>
      </section>

      {/* Trending (from the Kafka event worker) */}
      {browsing && trending.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-10">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Flame className="w-4 h-4 text-orange-400" /> Trending now
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {trending.map(p => <ProductCard key={p.id} product={p} />)}
          </div>
        </section>
      )}

      {/* Product Grid */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {browsing && trending.length > 0 && (
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">All products</h2>
        )}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="bg-surface-800 rounded-xl h-72 animate-pulse border border-surface-700" />
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="text-center py-24 text-slate-500">
            <Search className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p>No products found.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {products.map(p => <ProductCard key={p.id} product={p} />)}
          </div>
        )}

        {/* Pagination */}
        {meta.pages > 1 && (
          <div className="flex justify-center gap-2 mt-10">
            {Array.from({ length: meta.pages }).map((_, i) => (
              <button key={i}
                onClick={() => setPage(i + 1)}
                className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors
                  ${page === i + 1 ? 'bg-brand-600 text-white' : 'bg-surface-700 text-slate-400 hover:bg-surface-600'}`}>
                {i + 1}
              </button>
            ))}
          </div>
        )}
      </section>

    </div>
  )
}

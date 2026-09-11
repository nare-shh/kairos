import { useState, useEffect, useCallback } from 'react'
import { WS_BASE } from '../api/client'

const toNumber = (value) => (value == null ? null : Number(value))

export function useLivePrice(productId, initialPrice) {
  const [price, setPrice]         = useState(toNumber(initialPrice))
  const [demand, setDemand]       = useState(null)
  const [flashing, setFlashing]   = useState(false)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    setPrice(toNumber(initialPrice))
  }, [initialPrice])

  // Apply an authoritative price from elsewhere (e.g. the intent-tracking response)
  const applyUpdate = useCallback((newPrice, demandLevel) => {
    if (newPrice != null) setPrice(Number(newPrice))
    if (demandLevel) setDemand(demandLevel)
  }, [])

  useEffect(() => {
    if (!productId) return

    let ws
    let retryTimer
    let flashTimer
    let closedByUs = false   // don't reconnect after the component unmounts

    const connect = () => {
      ws = new WebSocket(`${WS_BASE}/ws/prices/${productId}`)

      ws.onopen = () => setConnected(true)

      ws.onmessage = (e) => {
        let msg
        try { msg = JSON.parse(e.data) } catch { return }

        // On (re)connect the server sends the current price — nothing is missed
        if (msg.type === 'connected') {
          if (msg.current_price != null) setPrice(Number(msg.current_price))
          if (msg.demand_level) setDemand(msg.demand_level)
          return
        }
        if (msg.type !== 'price_update') return

        setPrice(Number(msg.new_price))
        setDemand(msg.demand_level)
        // Flash animation when price changes
        setFlashing(true)
        clearTimeout(flashTimer)
        flashTimer = setTimeout(() => setFlashing(false), 800)
      }

      ws.onclose = () => {
        setConnected(false)
        // Reconnect after 3s if the connection drops
        if (!closedByUs) retryTimer = setTimeout(connect, 3000)
      }
    }

    connect()
    return () => {
      closedByUs = true
      clearTimeout(retryTimer)
      clearTimeout(flashTimer)
      ws?.close()
    }
  }, [productId])

  return { price, demand, flashing, connected, applyUpdate }
}

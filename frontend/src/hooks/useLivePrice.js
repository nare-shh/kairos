import { useState, useEffect, useRef } from 'react'
import { WS_BASE } from '../api/client'

export function useLivePrice(productId, initialPrice) {
  const [price, setPrice]       = useState(initialPrice)
  const [demand, setDemand]     = useState(null)
  const [flashing, setFlashing] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    if (!productId) return
    setPrice(initialPrice)
  }, [initialPrice])

  useEffect(() => {
    if (!productId) return

    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/prices/${productId}`)
      wsRef.current = ws

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'price_update') {
            setPrice(parseFloat(msg.new_price))
            setDemand(msg.demand_level)
            // Flash animation when price changes
            setFlashing(true)
            setTimeout(() => setFlashing(false), 800)
          }
        } catch {}
      }

      ws.onclose = () => {
        // Reconnect after 3s if connection drops
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => wsRef.current?.close()
  }, [productId])

  return { price, demand, flashing }
}

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import { StatusUpdate } from '../types/api'
import { wsManager } from '../services/wsManager'

type WSStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'ERROR'

interface WebSocketContextType {
  subscribe: (jobId: string, callback: (message: StatusUpdate) => void) => () => void
  unsubscribe: (jobId: string) => void
  getStatus: () => WSStatus
  reconnect: () => void
  lastUpdate: StatusUpdate | null
  error: string | null
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [lastUpdate, setLastUpdate] = useState<StatusUpdate | null>(null)
  const [error, setError] = useState<string | null>(null)

  const subscribe = useCallback(
    (jobId: string, callback: (message: StatusUpdate) => void): (() => void) => {
      // Connect to WebSocket for this job
      wsManager.connect(jobId).catch((err) => {
        console.error('WebSocket connection failed:', err)
        setError(err.message || 'WebSocket connection failed')
      })

      // Subscribe to messages
      const unsubscribe = wsManager.subscribe(jobId, (message) => {
        setLastUpdate(message)
        callback(message)
      })

      return unsubscribe
    },
    []
  )

  const unsubscribe = useCallback((jobId: string): void => {
    wsManager.disconnect()
  }, [])

  const getStatus = useCallback((): WSStatus => {
    return wsManager.getStatus()
  }, [])

  const reconnect = useCallback((): void => {
    wsManager.reconnect()
  }, [])

  const value: WebSocketContextType = {
    subscribe,
    unsubscribe,
    getStatus,
    reconnect,
    lastUpdate,
    error,
  }

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>
}

export function useWebSocket(): WebSocketContextType {
  const context = useContext(WebSocketContext)
  if (context === undefined) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}

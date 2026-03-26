import { StatusUpdate } from '../types/api'
import { getToken } from './apiClient'

type WSStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'ERROR'
type MessageCallback = (message: StatusUpdate) => void

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8080/ws/v1'

class WebSocketManager {
  private ws: WebSocket | null = null
  private jobId: string | null = null
  private status: WSStatus = 'DISCONNECTED'
  private subscribers: Map<string, Set<MessageCallback>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000 // Start at 1 second
  private maxReconnectDelay = 30000 // Cap at 30 seconds
  private reconnectTimer: number | null = null
  private heartbeatTimer: number | null = null
  private heartbeatInterval = 30000 // 30 seconds

  connect(jobId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws && this.status === 'CONNECTED' && this.jobId === jobId) {
        resolve()
        return
      }

      // Close existing connection if any
      this.disconnect()

      this.jobId = jobId
      this.status = 'CONNECTING'

      const token = getToken()
      if (!token) {
        reject(new Error('No authentication token available'))
        return
      }

      const wsUrl = `${WS_BASE_URL}/jobs/${jobId}/status?token=${encodeURIComponent(token)}`

      try {
        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
          console.log(`WebSocket connected for job ${jobId}`)
          this.status = 'CONNECTED'
          this.reconnectAttempts = 0
          this.reconnectDelay = 1000
          this.startHeartbeat()
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const message: StatusUpdate = JSON.parse(event.data)
            this.handleMessage(message)
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error)
          }
        }

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error)
          this.status = 'ERROR'
          reject(error)
        }

        this.ws.onclose = (event) => {
          console.log(`WebSocket closed: ${event.code} ${event.reason}`)
          this.status = 'DISCONNECTED'
          this.stopHeartbeat()

          if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect()
          }
        }
      } catch (error) {
        this.status = 'ERROR'
        reject(error)
      }
    })
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    this.stopHeartbeat()

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }

    this.status = 'DISCONNECTED'
    this.jobId = null
  }

  subscribe(jobId: string, callback: MessageCallback): () => void {
    if (!this.subscribers.has(jobId)) {
      this.subscribers.set(jobId, new Set())
    }

    this.subscribers.get(jobId)!.add(callback)

    // Return unsubscribe function
    return () => {
      const subscribers = this.subscribers.get(jobId)
      if (subscribers) {
        subscribers.delete(callback)
        if (subscribers.size === 0) {
          this.subscribers.delete(jobId)
        }
      }
    }
  }

  send(message: any): void {
    if (this.ws && this.status === 'CONNECTED') {
      this.ws.send(JSON.stringify(message))
    } else {
      console.warn('Cannot send message: WebSocket is not connected')
    }
  }

  getStatus(): WSStatus {
    return this.status
  }

  reconnect(): void {
    if (this.jobId) {
      this.reconnectAttempts = 0
      this.connect(this.jobId).catch((error) => {
        console.error('Manual reconnect failed:', error)
      })
    }
  }

  private handleMessage(message: StatusUpdate): void {
    // Handle heartbeat/pong responses
    if (message.message_type === 'heartbeat') {
      return
    }

    // Notify subscribers
    if (this.jobId) {
      const subscribers = this.subscribers.get(this.jobId)
      if (subscribers) {
        subscribers.forEach((callback) => {
          try {
            callback(message)
          } catch (error) {
            console.error('Subscriber callback error:', error)
          }
        })
      }
    }
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++

    // Exponential backoff with jitter
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    )
    const jitter = Math.random() * 1000 // Add up to 1 second jitter

    console.log(
      `Scheduling reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${Math.round(delay + jitter)}ms`
    )

    this.reconnectTimer = window.setTimeout(() => {
      if (this.jobId) {
        this.connect(this.jobId).catch((error) => {
          console.error('Reconnect failed:', error)
        })
      }
    }, delay + jitter)
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = window.setInterval(() => {
      this.send({ message_type: 'ping' })
    }, this.heartbeatInterval)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }
}

// Singleton instance
export const wsManager = new WebSocketManager()

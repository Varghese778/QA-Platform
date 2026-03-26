import { useEffect, useState } from 'react'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface ToastProps {
  message: string
  type: ToastType
  duration?: number
  onClose: () => void
}

export default function Toast({ message, type, duration = 5000, onClose }: ToastProps) {
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false)
      setTimeout(onClose, 300) // Wait for fade out animation
    }, duration)

    return () => clearTimeout(timer)
  }, [duration, onClose])

  const typeStyles = {
    success: 'bg-green-500 border-green-600',
    error: 'bg-red-500 border-red-600',
    warning: 'bg-yellow-500 border-yellow-600',
    info: 'bg-blue-500 border-blue-600',
  }

  const icons = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ',
  }

  return (
    <div
      className={`fixed top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg text-white border-l-4 transition-opacity duration-300 ${
        typeStyles[type]
      } ${isVisible ? 'opacity-100' : 'opacity-0'}`}
    >
      <span className="text-xl font-bold">{icons[type]}</span>
      <span className="text-sm font-medium">{message}</span>
      <button
        onClick={() => {
          setIsVisible(false)
          setTimeout(onClose, 300)
        }}
        className="ml-2 text-white hover:text-gray-200 font-bold text-lg"
        aria-label="Close"
      >
        ×
      </button>
    </div>
  )
}

// Toast Container Component
interface ToastMessage {
  id: string
  message: string
  type: ToastType
}

let toastIdCounter = 0
const toastListeners: Array<(toasts: ToastMessage[]) => void> = []
let toasts: ToastMessage[] = []

export function showToast(message: string, type: ToastType = 'info'): void {
  const id = `toast-${++toastIdCounter}`
  toasts = [...toasts, { id, message, type }]
  toastListeners.forEach((listener) => listener(toasts))
}

export function ToastContainer() {
  const [toastMessages, setToastMessages] = useState<ToastMessage[]>([])

  useEffect(() => {
    const listener = (newToasts: ToastMessage[]) => {
      setToastMessages(newToasts)
    }
    toastListeners.push(listener)
    return () => {
      const index = toastListeners.indexOf(listener)
      if (index > -1) {
        toastListeners.splice(index, 1)
      }
    }
  }, [])

  const removeToast = (id: string) => {
    toasts = toasts.filter((t) => t.id !== id)
    setToastMessages(toasts)
  }

  return (
    <>
      {toastMessages.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </>
  )
}

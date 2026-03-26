import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { parseApiError } from '../utils/api-error'

const getToken = (): string | null => {
  return localStorage.getItem('auth_token')
}

const setToken = (token: string): void => {
  localStorage.setItem('auth_token', token)
}

const clearToken = (): void => {
  localStorage.removeItem('auth_token')
}

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api/v1'

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: Add JWT token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor: Handle errors and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - redirect to login
      clearToken()
      window.location.href = '/login'
    }
    return Promise.reject(parseApiError(error))
  }
)

export { getToken, setToken, clearToken }

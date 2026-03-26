import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { User } from '../types/api'
import { getToken, setToken as saveToken, clearToken } from '../services/apiClient'
import { apiClient } from '../services/apiClient'

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  setUser: (user: User | null) => void
  setAuthToken: (token: string) => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setTokenState] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Check for existing token on mount
    const existingToken = getToken()
    if (existingToken) {
      setTokenState(existingToken)
      // Decode JWT to extract user info (simplified - in production, verify with backend)
      try {
        const payload = JSON.parse(atob(existingToken.split('.')[1]))
        setUser({
          id: payload.sub,
          email: payload.email || '',
          name: payload.name || '',
          roles: payload.roles || {},
        })
      } catch (error) {
        console.error('Failed to decode token:', error)
        clearToken()
      }
    }
    setIsLoading(false)
  }, [])

  const login = async (email: string, password: string): Promise<void> => {
    setIsLoading(true)
    setError(null)

    try {
      // Route login through the API gateway (auth-service is not directly accessible from browser)
      const response = await apiClient.post('/demo/login', {
        email,
        password,
      })

      const { access_token, user: userData } = response.data

      saveToken(access_token)
      setTokenState(access_token)
      setUser(userData)
    } catch (err: any) {
      setError(err.message || 'Login failed')
      throw err
    } finally {
      setIsLoading(false)
    }
  }

  const logout = (): void => {
    clearToken()
    setTokenState(null)
    setUser(null)
    setError(null)
  }

  const setAuthToken = (newToken: string): void => {
    saveToken(newToken)
    setTokenState(newToken)

    // Decode JWT to extract user info
    try {
      const payload = JSON.parse(atob(newToken.split('.')[1]))
      setUser({
        id: payload.sub,
        email: payload.email || '',
        name: payload.name || '',
        roles: payload.roles || {},
      })
    } catch (error) {
      console.error('Failed to decode token:', error)
    }
  }

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    isLoading,
    error,
    login,
    logout,
    setUser,
    setAuthToken,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

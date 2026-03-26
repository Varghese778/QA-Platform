import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { showToast } from '../components/Common/Toast'
import LoadingSpinner from '../components/Common/LoadingSpinner'
import { ToastContainer } from '../components/Common/Toast'

export default function LoginPage() {
  const { login, setAuthToken } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    if (!email || !password) {
      showToast('Please enter email and password', 'error')
      return
    }

    setIsLoading(true)

    try {
      await login(email, password)
      showToast('Login successful!', 'success')
      navigate('/dashboard')
    } catch (error: any) {
      showToast(error.message || 'Login failed', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  // Quick demo login bypass (for development/testing)
  const handleDemoLogin = () => {
    // Create a properly structured JWT for demo purposes
    const header = btoa(JSON.stringify({ alg: 'RS256', typ: 'JWT' }))
    const payload = btoa(
      JSON.stringify({
        sub: 'demo-user-123',
        email: 'demo@qaplatform.com',
        name: 'Demo User',
        roles: {
          'demo-project-001': 'QA_ENGINEER',
          'demo-project-002': 'QA_ENGINEER',
          'demo-project-003': 'VIEWER',
        },
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 86400,
      })
    )
    const signature = btoa('demo-signature')

    const fullMockToken = `${header}.${payload}.${signature}`
    setAuthToken(fullMockToken)
    showToast('Logged in as demo user', 'success')
    navigate('/dashboard')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4">
      <div className="max-w-md w-full bg-white shadow-2xl rounded-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">QA Platform</h1>
          <p className="text-gray-600 mt-2">Sign in to access the dashboard</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="you@example.com"
              disabled={isLoading}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="••••••••"
              disabled={isLoading}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-primary text-white py-3 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2 font-medium"
          >
            {isLoading ? (
              <>
                <LoadingSpinner size="sm" />
                Signing in...
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-gray-200">
          <button
            onClick={handleDemoLogin}
            className="w-full bg-gray-100 text-gray-700 py-2 rounded-md hover:bg-gray-200 transition-colors text-sm font-medium"
          >
            🚀 Quick Demo Login
          </button>
          <p className="text-xs text-gray-500 text-center mt-2">
            Bypass authentication for demonstration purposes
          </p>
        </div>
      </div>
      <ToastContainer />
    </div>
  )
}

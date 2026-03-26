import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { JobProvider } from './context/JobContext'
import { WebSocketProvider } from './context/WebSocketContext'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import JobDetailPage from './pages/JobDetailPage'
import IntegrationsPage from './pages/IntegrationsPage'
import NotFoundPage from './pages/NotFoundPage'
import ProtectedRoute from './components/Common/ProtectedRoute'

function App() {
  return (
    <Router>
      <AuthProvider>
        <JobProvider>
          <WebSocketProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <DashboardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/jobs/:jobId"
                element={
                  <ProtectedRoute>
                    <JobDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/integrations"
                element={
                  <ProtectedRoute>
                    <IntegrationsPage />
                  </ProtectedRoute>
                }
              />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </WebSocketProvider>
        </JobProvider>
      </AuthProvider>
    </Router>
  )
}

export default App


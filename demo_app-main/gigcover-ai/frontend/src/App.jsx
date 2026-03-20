import { Navigate, Route, Routes } from 'react-router-dom'
import NavBar from './components/NavBar'
import ProtectedRoute from './components/ProtectedRoute'
import { useAuth } from './context/AuthContext'
import AdminDashboard from './pages/AdminDashboard'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import OnboardingPage from './pages/OnboardingPage'
import SignupPage from './pages/SignupPage'
import WorkerDashboard from './pages/WorkerDashboard'

function DashboardRedirect() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={user.role === 'Admin' ? '/admin' : '/worker'} replace />
}

function App() {
  return (
    <div className="min-h-screen pb-10">
      <NavBar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route
          path="/onboarding"
          element={
            <ProtectedRoute allowedRoles={['Employee']}>
              <OnboardingPage />
            </ProtectedRoute>
          }
        />
        <Route path="/dashboard" element={<DashboardRedirect />} />
        <Route
          path="/worker"
          element={
            <ProtectedRoute allowedRoles={['Employee']}>
              <WorkerDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute allowedRoles={['Admin']}>
              <AdminDashboard />
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  )
}

export default App

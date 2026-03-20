import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const onSubmit = async (event) => {
    event.preventDefault()
    setError('')

    const email = form.email.trim().toLowerCase()
    const password = form.password
    const emailRegex = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

    if (!email || !password) {
      setError('Email and password are required.')
      return
    }
    if (!emailRegex.test(email)) {
      setError('Please enter a valid email address.')
      return
    }

    setLoading(true)

    try {
      const { data } = await api.post('/login', { email, password })
      console.log('[login success]', data)
      login(data.token, data.user)
      if (data.user.role === 'Admin') {
        navigate('/admin')
      } else if (!data.user.onboarding_complete) {
        navigate('/onboarding')
      } else {
        navigate('/worker')
      }
    } catch (err) {
      console.error('[login failed]', err.response?.status, err.response?.data || err.message)
      setError(err.response?.data?.error || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-xl px-6 py-16 sm:px-10">
      <form onSubmit={onSubmit} className="glass w-full rounded-3xl p-8">
        <h1 className="font-outfit text-3xl font-bold text-slate-800">Login</h1>
        <p className="mt-2 text-slate-700">Use your real email and password to access your dashboard.</p>

        <label className="mt-6 block text-sm font-medium text-slate-700">Email</label>
        <input
          type="email"
          required
          value={form.email}
          onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
          className="input-field mt-2"
          placeholder="name@email.com"
        />

        <label className="mt-4 block text-sm font-medium text-slate-700">Password</label>
        <input
          type="password"
          required
          value={form.password}
          onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
          className="input-field mt-2"
          placeholder="********"
        />

        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}

        <button disabled={loading} className="primary-btn mt-6 w-full justify-center" type="submit">
          {loading ? 'Signing in...' : 'Login'}
        </button>
      </form>
    </div>
  )
}

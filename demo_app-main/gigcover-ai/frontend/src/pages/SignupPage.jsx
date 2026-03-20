import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function SignupPage() {
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'Employee' })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setSuccess('')

    const name = form.name.trim()
    const email = form.email.trim().toLowerCase()
    const password = form.password
    const emailRegex = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

    if (!name || !email || !password) {
      setError('Name, email and password are required.')
      return
    }
    if (!emailRegex.test(email)) {
      setError('Please enter a valid email address.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    setLoading(true)

    try {
      const payload = { ...form, name, email }
      const { data } = await api.post('/signup', payload)
      console.log('[signup success]', data)
      setSuccess('Account created! Redirecting to login...')
      setTimeout(() => navigate('/login'), 1200)
    } catch (err) {
      console.error('[signup failed]', err.response?.status, err.response?.data || err.message)
      setError(err.response?.data?.error || 'Signup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-xl px-6 py-16 sm:px-10">
      <form onSubmit={onSubmit} className="glass w-full rounded-3xl p-8">
        <h1 className="font-outfit text-3xl font-bold text-slate-800">Create Account</h1>

        <label className="mt-6 block text-sm font-medium text-slate-700">Name</label>
        <input
          required
          value={form.name}
          onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
          className="input-field mt-2"
          placeholder="Full name"
        />

        <label className="mt-4 block text-sm font-medium text-slate-700">Email</label>
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

        <label className="mt-4 block text-sm font-medium text-slate-700">Role</label>
        <select
          value={form.role}
          onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value }))}
          className="input-field mt-2"
        >
          <option value="Employee">Employee</option>
          <option value="Admin">Admin</option>
        </select>

        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
        {success && <p className="mt-3 text-sm text-green-600">{success}</p>}

        <button disabled={loading} className="primary-btn mt-6 w-full justify-center" type="submit">
          {loading ? 'Creating account...' : 'Signup'}
        </button>
      </form>
    </div>
  )
}

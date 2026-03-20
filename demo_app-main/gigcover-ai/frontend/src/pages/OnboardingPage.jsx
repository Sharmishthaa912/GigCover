import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

const workTypes = ['Delivery', 'Driver', 'Freelancer', 'Technician', 'Field Sales']
const platforms = ['Swiggy', 'Zomato', 'Blinkit', 'Uber', 'Zepto', 'Other']

export default function OnboardingPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    full_name: '',
    age: 0,
    gender: 'Male',
    email: '',
    work_type: 'Delivery',
    platform_used: 'Swiggy',
    working_hours: 8,
    working_shift: 'Day',
    weekly_working_days: 6,
    city: '',
    manual_location: '',
    location_text: '',
    latitude: 0,
    longitude: 0,
    daily_income: 500,
    income_dependency: 'Medium',
    zone_type: 'Urban',
  })

  const canSubmit = useMemo(() => {
    return (
      form.full_name.trim() &&
      Number(form.age) > 0 &&
      Number(form.daily_income) > 0 &&
      Number(form.working_hours) > 0 &&
      Number(form.weekly_working_days) > 0
    )
  }, [form])

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const detectLocation = async () => {
    setError('')
    if (!navigator.geolocation) {
      setError('Geolocation is not supported in this browser.')
      return
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const latitude = position.coords.latitude
        const longitude = position.coords.longitude
        update('latitude', latitude)
        update('longitude', longitude)

        try {
          const { data } = await api.post('/weather-risk', { latitude, longitude })
          console.log('[onboarding location]', data)
          update('city', data.location?.city || '')
          update('location_text', data.location?.display_name || '')
        } catch {
          // Keep coordinates even if reverse geocoding fails.
        }
      },
      () => setError('Unable to detect current location. You can enter it manually.'),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 12000 },
    )
  }

  const onSubmit = async (event) => {
    event.preventDefault()
    if (!canSubmit) {
      setError('Please complete required fields.')
      return
    }
    if (Number(form.weekly_working_days) > 7) {
      setError('Weekly working days must be between 1 and 7.')
      return
    }
    if (Number(form.working_hours) > 24) {
      setError('Working hours must be between 1 and 24.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const payload = {
        ...form,
        full_name: form.full_name.trim(),
        email: form.email.trim().toLowerCase(),
        city: form.city.trim(),
        manual_location: form.manual_location.trim(),
        location_text: form.location_text.trim(),
      }
      const { data } = await api.post('/onboarding', payload)
      console.log('[onboarding success]', data)
      navigate('/worker')
    } catch (err) {
      console.error('[onboarding failed]', err.response?.status, err.response?.data || err.message)
      setError(err.response?.data?.error || 'Unable to save onboarding data.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <form onSubmit={onSubmit} className="glass rounded-3xl p-6 sm:p-8">
        <h1 className="font-outfit text-3xl font-bold text-slate-900">Onboarding Form</h1>
        <p className="mt-1 text-sm text-slate-600">Tell us about your work profile to calculate smart risk and premium.</p>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Field label="Full Name" value={form.full_name} onChange={(v) => update('full_name', v)} required />
          <Field label="Age" type="number" value={form.age} onChange={(v) => update('age', Number(v))} required />
          <Select label="Gender" value={form.gender} onChange={(v) => update('gender', v)} options={['Male', 'Female', 'Other']} />
          <Field label="Email" type="email" value={form.email} onChange={(v) => update('email', v)} />
        </div>

        <h2 className="mt-7 font-outfit text-xl font-semibold text-slate-900">Work Details</h2>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <Select label="Type of Work" value={form.work_type} onChange={(v) => update('work_type', v)} options={workTypes} />
          <Select label="Platform Used" value={form.platform_used} onChange={(v) => update('platform_used', v)} options={platforms} />
          <Field label="Working Hours / Day" type="number" value={form.working_hours} onChange={(v) => update('working_hours', Number(v))} />
          <Select label="Working Shift" value={form.working_shift} onChange={(v) => update('working_shift', v)} options={['Day', 'Night']} />
          <Field
            label="Weekly Working Days"
            type="number"
            value={form.weekly_working_days}
            onChange={(v) => update('weekly_working_days', Number(v))}
          />
        </div>

        <h2 className="mt-7 font-outfit text-xl font-semibold text-slate-900">Location & Income</h2>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <button type="button" className="secondary-btn" onClick={detectLocation}>
              Auto Detect Current Location
            </button>
          </div>
          <Field label="City" value={form.city} onChange={(v) => update('city', v)} />
          <Field label="Manual Location" value={form.manual_location} onChange={(v) => update('manual_location', v)} />
          <div className="md:col-span-2">
            <Field label="Detected Place" value={form.location_text} onChange={(v) => update('location_text', v)} />
          </div>
          <Field label="Average Daily Income" type="number" value={form.daily_income} onChange={(v) => update('daily_income', Number(v))} required />
          <Select label="Dependency on Income" value={form.income_dependency} onChange={(v) => update('income_dependency', v)} options={['Low', 'Medium', 'High']} />
        </div>

        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

        <button disabled={loading || !canSubmit} className="primary-btn mt-6" type="submit">
          {loading ? 'Saving...' : 'Complete Onboarding'}
        </button>
      </form>
    </div>
  )
}

function Field({ label, value, onChange, type = 'text', required = false }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <input type={type} value={value} required={required} onChange={(e) => onChange(e.target.value)} className="input-field mt-2" />
    </label>
  )
}

function Select({ label, value, onChange, options }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="input-field mt-2">
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  )
}

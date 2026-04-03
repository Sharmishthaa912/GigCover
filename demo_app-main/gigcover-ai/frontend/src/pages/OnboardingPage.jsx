import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

const PLATFORMS = ['Swiggy', 'Zomato', 'Blinkit', 'Zepto', 'Uber', 'Other']
const WORK_TYPES = ['Delivery', 'Driver', 'Freelancer', 'Technician', 'Field Sales']
const CITIES = ['Delhi', 'Mumbai', 'Bengaluru', 'Hyderabad', 'Chennai', 'Kolkata', 'Pune', 'Other']

const STEPS = ['Personal', 'Work', 'Location & Income', 'Payment & Consent']

const CITY_COORDS = {
  delhi: [28.6139, 77.209], mumbai: [19.076, 72.8777],
  bengaluru: [12.9716, 77.5946], bangalore: [12.9716, 77.5946],
  hyderabad: [17.385, 78.4867], chennai: [13.0827, 80.2707],
  kolkata: [22.5726, 88.3639], pune: [18.5204, 73.8567],
}

export default function OnboardingPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [locating, setLocating] = useState(false)
  const [locSource, setLocSource] = useState('')

  const [form, setForm] = useState({
    // Step 1
    full_name: '', age: '', gender: 'Male', email: '',
    // Step 2
    work_type: 'Delivery', platform_used: 'Swiggy',
    working_hours: 8, working_shift: 'Day', weekly_working_days: 6,
    // Step 3
    city: '', manual_location: '', location_text: '',
    latitude: 0, longitude: 0,
    daily_income: 500, income_dependency: 'Medium', zone_type: 'Urban',
    // Step 4
    upi_id: '', phone: '', gps_consent: false, tracking_consent: false,
  })

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const stepValid = useMemo(() => {
    if (step === 0) return form.full_name.trim() && Number(form.age) > 0
    if (step === 1) return form.work_type && form.platform_used && Number(form.working_hours) > 0
    if (step === 2) return form.city.trim() && Number(form.daily_income) > 0
    if (step === 3) return form.upi_id.trim() && form.phone.trim() && form.gps_consent && form.tracking_consent
    return false
  }, [form, step])

  const detectLocation = async () => {
    setLocating(true)
    setError('')
    setLocSource('')

    const applyCoords = async (lat, lon, source) => {
      set('latitude', lat)
      set('longitude', lon)
      setLocSource(source)
      try {
        const { data } = await api.post('/weather-risk', { latitude: lat, longitude: lon })
        if (data.location?.city) set('city', data.location.city)
        if (data.location?.display_name) set('location_text', data.location.display_name)
      } catch { /* keep coords */ }
      setLocating(false)
    }

    // 1. Browser GPS
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => applyCoords(pos.coords.latitude, pos.coords.longitude, 'GPS'),
        async () => {
          // 2. City coordinate table fallback
          const cityKey = form.city.trim().toLowerCase()
          const coords = CITY_COORDS[cityKey]
          if (coords) {
            await applyCoords(coords[0], coords[1], `City table (${form.city})`)
          } else {
            setError('GPS unavailable. Select your city from the dropdown — coordinates will be auto-assigned.')
            setLocating(false)
          }
        },
        { enableHighAccuracy: true, timeout: 8000 }
      )
    } else {
      // 3. No geolocation API — use city table
      const cityKey = form.city.trim().toLowerCase()
      const coords = CITY_COORDS[cityKey]
      if (coords) {
        await applyCoords(coords[0], coords[1], `City table (${form.city})`)
      } else {
        setError('Geolocation not supported. Select your city to auto-assign coordinates.')
        setLocating(false)
      }
    }
  }

  // Auto-assign city coords when city dropdown changes
  const handleCityChange = (v) => {
    set('city', v)
    const coords = CITY_COORDS[v.toLowerCase()]
    if (coords && form.latitude === 0) {
      set('latitude', coords[0])
      set('longitude', coords[1])
      setLocSource(`Auto (${v})`)
    }
  }

  const submit = async () => {
    setLoading(true); setError('')
    try {
      await api.post('/onboarding', {
        ...form,
        full_name: form.full_name.trim(),
        age: Number(form.age),
        working_hours: Number(form.working_hours),
        weekly_working_days: Number(form.weekly_working_days),
        daily_income: Number(form.daily_income),
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
      })
      navigate('/worker')
    } catch (err) {
      setError(err.response?.data?.error || 'Onboarding failed. Please try again.')
    } finally { setLoading(false) }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      {/* Step indicator */}
      <div className="mb-8 flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s} className="flex flex-1 flex-col items-center gap-1">
            <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold transition-all ${
              i < step ? 'bg-green-500 text-white' : i === step ? 'bg-[#ffc107] text-black' : 'bg-slate-200 text-slate-500'
            }`}>{i < step ? '✓' : i + 1}</div>
            <span className={`hidden text-xs sm:block ${i === step ? 'font-semibold text-slate-900' : 'text-slate-400'}`}>{s}</span>
          </div>
        ))}
      </div>

      <div className="glass rounded-3xl p-6 sm:p-8">
        <h1 className="font-outfit text-2xl font-bold text-slate-900">{STEPS[step]}</h1>
        <p className="mt-1 text-sm text-slate-500">Step {step + 1} of {STEPS.length}</p>

        <div className="mt-6 space-y-4">
          {/* STEP 1 – Personal */}
          {step === 0 && <>
            <Field label="Full Name *" value={form.full_name} onChange={v => set('full_name', v)} />
            <div className="grid grid-cols-2 gap-4">
              <Field label="Age *" type="number" value={form.age} onChange={v => set('age', v)} />
              <Sel label="Gender" value={form.gender} onChange={v => set('gender', v)} opts={['Male', 'Female', 'Other']} />
            </div>
            <Field label="Email" type="email" value={form.email} onChange={v => set('email', v)} />
          </>}

          {/* STEP 2 – Work */}
          {step === 1 && <>
            <Sel label="Work Type *" value={form.work_type} onChange={v => set('work_type', v)} opts={WORK_TYPES} />
            <Sel label="Platform *" value={form.platform_used} onChange={v => set('platform_used', v)} opts={PLATFORMS} />
            <div className="grid grid-cols-2 gap-4">
              <Field label="Hours / Day *" type="number" value={form.working_hours} onChange={v => set('working_hours', v)} />
              <Field label="Days / Week *" type="number" value={form.weekly_working_days} onChange={v => set('weekly_working_days', v)} />
            </div>
            <Sel label="Working Shift" value={form.working_shift} onChange={v => set('working_shift', v)} opts={['Day', 'Night']} />
          </>}

          {/* STEP 3 – Location & Income */}
          {step === 2 && <>
            <button type="button" onClick={detectLocation} disabled={locating}
              className="secondary-btn w-full">
              {locating ? '📍 Detecting...' : '📍 Auto-Detect Location'}
            </button>
            <Sel label="City *" value={form.city} onChange={handleCityChange} opts={CITIES} />
            <Field label="Area / Locality" value={form.manual_location} onChange={v => set('manual_location', v)} />
            <Sel label="Zone Type" value={form.zone_type} onChange={v => set('zone_type', v)} opts={['Urban', 'Semi-Urban', 'Rural']} />
            <div className="grid grid-cols-2 gap-4">
              <Field label="Daily Income (₹) *" type="number" value={form.daily_income} onChange={v => set('daily_income', v)} />
              <Sel label="Income Dependency" value={form.income_dependency} onChange={v => set('income_dependency', v)} opts={['Low', 'Medium', 'High']} />
            </div>
            {form.latitude !== 0 && (
              <p className="text-xs text-green-600">✓ Location set via {locSource || 'GPS'}: {Number(form.latitude).toFixed(4)}, {Number(form.longitude).toFixed(4)}</p>
            )}
            {form.latitude === 0 && form.city && (
              <p className="text-xs text-amber-600">⚠ No GPS coords yet. Click Auto-Detect or select city to assign coordinates.</p>
            )}
          </>}

          {/* STEP 4 – Payment & Consent */}
          {step === 3 && <>
            <div className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-800">
              <p className="font-semibold">💳 Payout Details</p>
              <p className="mt-1">Your UPI ID is used for instant automatic payouts when a trigger fires. No manual action needed.</p>
            </div>
            <Field label="UPI ID *" value={form.upi_id} onChange={v => set('upi_id', v)} placeholder="yourname@upi" />
            <Field label="Phone Number *" type="tel" value={form.phone} onChange={v => set('phone', v)} placeholder="10-digit mobile" />

            <div className="mt-4 space-y-3 rounded-2xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-800">Consent & Permissions</p>
              <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-700">
                <input type="checkbox" checked={form.gps_consent} onChange={e => set('gps_consent', e.target.checked)}
                  className="mt-0.5 h-4 w-4 accent-amber-500" />
                <span>I consent to GPS location tracking during active work hours for claim validation.</span>
              </label>
              <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-700">
                <input type="checkbox" checked={form.tracking_consent} onChange={e => set('tracking_consent', e.target.checked)}
                  className="mt-0.5 h-4 w-4 accent-amber-500" />
                <span>I consent to platform activity monitoring (online/offline status) for fraud prevention.</span>
              </label>
            </div>

            <div className="rounded-2xl bg-slate-50 p-4 text-xs text-slate-500">
              <p className="font-semibold text-slate-700">Your Risk Pool Assignment</p>
              <p className="mt-1">Based on your city (<strong>{form.city || 'selected city'}</strong>) and platform (<strong>{form.platform_used}</strong>), you will be auto-assigned to the matching city risk pool for group-level trigger monitoring.</p>
            </div>
          </>}
        </div>

        {error && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-600">{error}</p>}

        <div className="mt-6 flex gap-3">
          {step > 0 && (
            <button onClick={() => { setStep(s => s - 1); setError('') }} className="secondary-btn flex-1">
              ← Back
            </button>
          )}
          {step < STEPS.length - 1 ? (
            <button disabled={!stepValid} onClick={() => { if (stepValid) { setStep(s => s + 1); setError('') } }}
              className="primary-btn flex-1">
              Next →
            </button>
          ) : (
            <button disabled={loading || !stepValid} onClick={submit} className="primary-btn flex-1">
              {loading ? 'Activating...' : '🚀 Activate Coverage'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, type = 'text', placeholder = '' }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <input type={type} value={value} placeholder={placeholder}
        onChange={e => onChange(e.target.value)} className="input-field mt-1.5" />
    </label>
  )
}

function Sel({ label, value, onChange, opts }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <select value={value} onChange={e => onChange(e.target.value)} className="input-field mt-1.5">
        {opts.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  )
}

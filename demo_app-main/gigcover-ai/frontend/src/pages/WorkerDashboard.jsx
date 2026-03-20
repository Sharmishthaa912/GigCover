import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'

const menuItems = ['Dashboard', 'Policy', 'Claims', 'Profile', 'Logout']

export default function WorkerDashboard() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [active, setActive] = useState('Dashboard')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [dashboard, setDashboard] = useState({})
  const [toast, setToast] = useState(null)
  const [profileEdit, setProfileEdit] = useState(false)
  const [profileForm, setProfileForm] = useState({
    name: user?.name || '',
    city: '',
    location_text: '',
    delivery_platform: '',
    working_hours: 8,
    weekly_working_days: 6,
    working_shift: 'Day',
  })
  const [weather, setWeather] = useState(null)
  const [premiumInfo, setPremiumInfo] = useState(null)

  const worker = dashboard.worker || {}
  const policy = dashboard.policy || {}
  const claims = dashboard.claims || []

  const dismissToast = () => setTimeout(() => setToast(null), 3200)

  const showToast = (kind, text) => {
    setToast({ kind, text })
    dismissToast()
  }

  const fetchDashboard = async () => {
    const { data } = await api.get('/dashboard-data')
    if (!data.worker?.onboarding_complete) {
      navigate('/onboarding')
      return
    }
    setDashboard(data)

    if (data.premium_payment) {
      setPremiumInfo(data.premium_payment)
    }

    setProfileForm((prev) => ({
      ...prev,
      name: data.user?.name || prev.name,
      city: data.worker?.city || '',
      location_text: data.worker?.location_text || '',
      delivery_platform: data.worker?.delivery_platform || prev.delivery_platform,
      working_hours: data.worker?.working_hours ?? prev.working_hours,
      weekly_working_days: data.worker?.weekly_working_days ?? prev.weekly_working_days,
      working_shift: data.worker?.working_shift || prev.working_shift,
    }))
  }

  useEffect(() => {
    const run = async () => {
      try {
        await fetchDashboard()
      } catch {
        showToast('error', 'Unable to load dashboard data.')
      } finally {
        setLoading(false)
      }
    }
    run()
  }, [])

  const getWeatherRisk = async () => {
    const fetchWeatherByCoords = async (latitude, longitude) => {
      const { data } = await api.post('/weather-risk', { latitude, longitude })
      setWeather(data)
      setProfileForm((prev) => ({
        ...prev,
        city: data.location?.city || prev.city,
        location_text: data.location?.display_name || prev.location_text,
      }))
      showToast('success', `Weather updated for ${data.location?.display_name || 'your location'}.`)
    }

    if (!navigator.geolocation) {
      const fallbackLat = Number(worker.latitude || 0)
      const fallbackLon = Number(worker.longitude || 0)
      if (fallbackLat && fallbackLon) {
        setBusy(true)
        try {
          await fetchWeatherByCoords(fallbackLat, fallbackLon)
        } catch {
          showToast('error', 'Unable to fetch weather data.')
        } finally {
          setBusy(false)
        }
        return
      }

      showToast('error', 'Enable location to fetch weather')
      return
    }

    setBusy(true)
    try {
      const position = await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 12000,
          maximumAge: 15000,
        })
      })

      const { latitude, longitude } = position.coords
      await fetchWeatherByCoords(latitude, longitude)
    } catch {
      const fallbackLat = Number(worker.latitude || 0)
      const fallbackLon = Number(worker.longitude || 0)
      if (fallbackLat && fallbackLon) {
        try {
          await fetchWeatherByCoords(fallbackLat, fallbackLon)
          showToast('info', 'Using your saved onboarding location for weather.')
        } catch {
          try {
            const { data } = await api.post('/weather-risk', {})
            setWeather(data)
            showToast('info', 'Using saved profile location for weather.')
          } catch {
            showToast('error', 'Unable to fetch weather data')
          }
        }
      } else {
        try {
          const { data } = await api.post('/weather-risk', {})
          setWeather(data)
          showToast('info', 'Using saved profile location for weather.')
        } catch {
          showToast('error', 'Enable location to fetch weather')
        }
      }
    } finally {
      setBusy(false)
    }
  }

  const claimPolicyNow = async () => {
    const riskLabel = String(weather?.risk?.risk || weather?.risk?.risk_level || 'low').toLowerCase()
    if (!(riskLabel === 'medium' || riskLabel === 'high')) {
      showToast('info', 'Claim not eligible due to low risk')
      return
    }
    setBusy(true)
    try {
      const { data } = await api.post('/create-claim', {
        trigger_type: 'Weather Risk',
        lost_hours: 3,
        risk: riskLabel,
        risk_score: Number(weather?.risk?.risk_score || 0),
      })
      const msg = data.message || (riskLabel === 'medium' ? 'Claim approved (moderate risk)' : 'Claim approved (high risk)')
      if (data.claim_status === 'Approved') {
        showToast('success', `${msg}. Payout Rs ${Number(data.claim?.payout || 0).toFixed(2)} initiated.`)
      } else {
        showToast('info', msg)
      }
      setActive('Claims')
      await fetchDashboard()
    } catch {
      showToast('error', 'Failed to trigger policy claim.')
    } finally {
      setBusy(false)
    }
  }

  const payWeeklyPremium = async () => {
    setBusy(true)
    try {
      const { data } = await api.post('/pay-weekly-premium')
      setPremiumInfo(data.payment)
      showToast('success', `Payment successful. Next due date: ${data.payment.next_due_date}`)
      await fetchDashboard()
    } catch (error) {
      showToast('error', error.response?.data?.error || 'Unable to process premium payment.')
    } finally {
      setBusy(false)
    }
  }

  const saveProfile = async () => {
    setBusy(true)
    try {
      await api.put('/profile', profileForm)
      showToast('success', 'Profile updated successfully.')
      await fetchDashboard()
    } catch {
      showToast('error', 'Could not update profile.')
    } finally {
      setBusy(false)
    }
  }

  const riskScore = Number(worker.risk_score || 0)
  const premiumAmount = Number(worker.weekly_premium || policy.premium || 0)
  const coverageAmount = Number(policy.coverage_amount || worker.coverage_amount || 0)

  if (loading) {
    return <div className="px-6 py-16 text-slate-700">Loading worker dashboard...</div>
  }

  return (
    <div className="mx-auto grid min-h-[80vh] max-w-7xl gap-6 px-4 pb-10 pt-8 md:grid-cols-[220px_1fr]">
      <aside className="glass rounded-3xl p-4">
        <p className="px-3 pb-2 font-space text-lg font-semibold text-slate-900">Worker Menu</p>
        <div className="space-y-2">
          {menuItems.map((item) => (
            <button
              key={item}
              onClick={() => {
                if (item === 'Logout') {
                  logout()
                  return
                }
                setActive(item)
              }}
              className={`w-full rounded-xl px-3 py-2 text-left text-sm font-semibold transition ${
                active === item ? 'bg-[#ffc107] text-black shadow-sm' : 'text-slate-700 hover:bg-white'
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </aside>

      <section className="space-y-5">
        {toast && (
          <div
            className={`rounded-2xl px-4 py-3 text-sm font-semibold shadow-sm ${
              toast.kind === 'error'
                ? 'bg-red-50 text-red-700'
                : toast.kind === 'info'
                ? 'bg-slate-100 text-slate-700'
                : 'bg-amber-50 text-amber-900'
            }`}
          >
            {toast.text}
          </div>
        )}

        {active === 'Dashboard' && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Metric title="Worker" value={worker.full_name || user?.name || '-'} subtitle={worker.city || 'Location pending'} />
              <Metric title="Risk Score" value={riskScore.toFixed(2)} subtitle={dashboard.risk_category || 'Not assessed'} />
              <Metric title="Weekly Premium" value={`Rs ${premiumAmount.toFixed(2)}`} subtitle="Policy protection" />
              <Metric title="Coverage" value={`Rs ${coverageAmount.toFixed(2)}`} subtitle="Income shield" />
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <div className="glass rounded-3xl p-6">
                <h3 className="font-outfit text-xl font-semibold text-slate-900">Weather & Risk</h3>
                <p className="mt-1 text-sm text-slate-600">Live weather with city + area and claim recommendation.</p>
                <button disabled={busy} onClick={getWeatherRisk} className="primary-btn mt-4">
                  {busy ? 'Fetching...' : 'Fetch Weather Risk'}
                </button>
                {weather && (
                  <div className="mt-4 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
                    <Info label="Location" value={weather.location?.display_name || '-'} />
                    <Info label="Temperature" value={`${weather.weather?.temperature} C`} />
                    <Info label="Humidity" value={`${weather.weather?.humidity}%`} />
                    <Info label="Wind Speed" value={`${weather.weather?.wind_speed} m/s`} />
                    <Info label="Visibility" value={`${weather.weather?.visibility} m`} />
                    <Info label="Risk Level" value={weather.risk?.risk_level || 'Low'} />
                  </div>
                )}
                {weather?.risk?.recommendation && (
                  <p className="mt-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-700">{weather.risk.recommendation}</p>
                )}
                {!!weather?.risk?.reason?.length && (
                  <ul className="mt-3 space-y-1 text-sm text-slate-700">
                    {weather.risk.reason.map((reason) => (
                      <li key={reason}>- {reason}</li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="glass rounded-3xl p-6">
                <h3 className="font-outfit text-xl font-semibold text-slate-900">Premium & Claim Actions</h3>
                <p className="mt-1 text-sm text-slate-600">Pay weekly premium and trigger policy claim when risk is high.</p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button disabled={busy} onClick={payWeeklyPremium} className="primary-btn">
                    Pay Weekly Premium
                  </button>
                  <button disabled={busy} onClick={claimPolicyNow} className="secondary-btn">
                    Claim Policy Now
                  </button>
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  {(() => {
                    const riskLabel = String(weather?.risk?.risk || weather?.risk?.risk_level || 'low').toLowerCase()
                    if (riskLabel === 'medium') return 'Claim approved (moderate risk)'
                    if (riskLabel === 'high') return 'Claim approved (high risk)'
                    return 'Claim not eligible due to low risk'
                  })()}
                </p>
                {premiumInfo && (
                  <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
                    <p>Amount: Rs {Number(premiumInfo.amount || premiumAmount).toFixed(2)}</p>
                    <p>Next Due Date: {premiumInfo.next_due_date || 'N/A'}</p>
                    <p>Status: {premiumInfo.status || 'Pending'}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="widget-card">
              <p className="mb-2 font-space text-sm font-semibold text-slate-900">Policy Summary</p>
              <div className="grid gap-3 text-sm text-slate-700 sm:grid-cols-3">
                <Info label="Total Claims" value={String(claims.length)} />
                <Info label="Weekly Premium" value={`Rs ${premiumAmount.toFixed(2)}`} />
                <Info label="Coverage" value={`Rs ${coverageAmount.toFixed(2)}`} />
              </div>
            </div>
          </>
        )}

        {active === 'Policy' && (
          <div className="glass rounded-3xl p-6 text-slate-800">
            <h2 className="font-outfit text-2xl font-semibold text-slate-900">Policy Details</h2>
            <p className="mt-3">Status: {policy.policy_status || 'Inactive'}</p>
            <p>Premium: Rs {premiumAmount.toFixed(2)} per week</p>
            <p>Coverage: Rs {coverageAmount.toFixed(2)}</p>
            <button className="primary-btn mt-4" onClick={payWeeklyPremium}>
              Pay Weekly Premium
            </button>
          </div>
        )}

        {active === 'Claims' && (
          <div className="glass rounded-3xl p-6">
            <h2 className="font-outfit text-2xl font-semibold text-slate-900">Claims History</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="text-slate-700">
                    <th className="p-2">Claim ID</th>
                    <th className="p-2">Trigger</th>
                    <th className="p-2">Payout</th>
                    <th className="p-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {claims.map((claim) => (
                    <tr key={claim.claim_id} className="border-t border-slate-200">
                      <td className="p-2">{claim.claim_id}</td>
                      <td className="p-2">{claim.trigger_type}</td>
                      <td className="p-2">Rs {Number(claim.payout).toFixed(2)}</td>
                      <td className="p-2">{claim.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {active === 'Profile' && (
          <div className="space-y-4">
            {/* Header */}
            <div className="glass flex items-center justify-between rounded-3xl p-6">
              <div>
                <h2 className="font-outfit text-2xl font-semibold text-slate-900">My Profile</h2>
                <p className="mt-1 text-sm text-slate-500">View and manage your personal and work details.</p>
              </div>
              <button onClick={() => setProfileEdit((v) => !v)} className="secondary-btn">
                {profileEdit ? 'Cancel' : '✏️ Edit Profile'}
              </button>
            </div>

            {/* Personal Info */}
            <div className="glass rounded-3xl p-6">
              <h3 className="font-outfit text-lg font-semibold text-slate-900">👤 Personal Information</h3>
              {profileEdit ? (
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <Field label="Full Name" value={profileForm.name} onChange={(v) => setProfileForm((p) => ({ ...p, name: v }))} />
                  <Field label="City" value={profileForm.city} onChange={(v) => setProfileForm((p) => ({ ...p, city: v }))} />
                  <div className="md:col-span-2">
                    <Field label="Location" value={profileForm.location_text} onChange={(v) => setProfileForm((p) => ({ ...p, location_text: v }))} />
                  </div>
                </div>
              ) : (
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <Info label="Full Name" value={worker.full_name || user?.name || '-'} />
                  <Info label="Email" value={dashboard.user?.email || '-'} />
                  <Info label="City" value={worker.city || '-'} />
                  <Info label="📍 Location" value={worker.location_text || '-'} />
                </div>
              )}
            </div>

            {/* Work Info */}
            <div className="glass rounded-3xl p-6">
              <h3 className="font-outfit text-lg font-semibold text-slate-900">💼 Work Information</h3>
              {profileEdit ? (
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <ProfileSelect
                    label="Platform"
                    value={profileForm.delivery_platform}
                    onChange={(v) => setProfileForm((p) => ({ ...p, delivery_platform: v }))}
                    options={['Swiggy', 'Zomato', 'Blinkit', 'Uber', 'Zepto', 'Other']}
                  />
                  <ProfileSelect
                    label="Working Shift"
                    value={profileForm.working_shift}
                    onChange={(v) => setProfileForm((p) => ({ ...p, working_shift: v }))}
                    options={['Day', 'Night']}
                  />
                  <Field label="Working Hours / Day" value={String(profileForm.working_hours)} onChange={(v) => setProfileForm((p) => ({ ...p, working_hours: Number(v) }))} />
                  <Field label="Working Days / Week" value={String(profileForm.weekly_working_days)} onChange={(v) => setProfileForm((p) => ({ ...p, weekly_working_days: Number(v) }))} />
                </div>
              ) : (
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <Info label="Platform" value={worker.delivery_platform || '-'} />
                  <Info label="Working Shift" value={worker.working_shift || '-'} />
                  <Info label="Hours / Day" value={`${worker.working_hours || 8} hrs`} />
                  <Info label="Days / Week" value={`${worker.weekly_working_days || 6} days`} />
                  <Info label="Work Type" value={worker.work_type || '-'} />
                  <Info label="Zone" value={worker.zone_type || '-'} />
                </div>
              )}
            </div>

            {/* Coverage Summary */}
            <div className="glass rounded-3xl p-6">
              <h3 className="font-outfit text-lg font-semibold text-slate-900">📊 Coverage Summary</h3>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="widget-card text-center">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Risk Level</p>
                  <p className="mt-2 font-outfit text-xl font-bold text-slate-900">{dashboard.risk_category || 'Not assessed'}</p>
                </div>
                <div className="widget-card text-center">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Weekly Premium</p>
                  <p className="mt-2 font-outfit text-xl font-bold text-slate-900">Rs {premiumAmount.toFixed(2)}</p>
                </div>
                <div className="widget-card text-center">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Coverage</p>
                  <p className="mt-2 font-outfit text-xl font-bold text-slate-900">Rs {coverageAmount.toFixed(2)}</p>
                </div>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <Info label="Policy Status" value={policy.policy_status || 'Inactive'} />
                <Info label="Total Claims Filed" value={String(claims.length)} />
              </div>
            </div>

            {profileEdit && (
              <button
                disabled={busy}
                onClick={async () => {
                  await saveProfile()
                  setProfileEdit(false)
                }}
                className="primary-btn"
              >
                {busy ? 'Saving...' : 'Save Changes'}
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

function Metric({ title, value, subtitle }) {
  return (
    <div className="widget-card">
      <p className="text-xs uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-2 font-outfit text-2xl font-bold text-slate-900">{value}</p>
      <p className="text-sm text-slate-600">{subtitle}</p>
    </div>
  )
}

function Info({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-semibold text-slate-900">{value}</p>
    </div>
  )
}

function Field({ label, value, onChange }) {
  return (
    <label className="block text-sm text-slate-700">
      {label}
      <input value={value} onChange={(e) => onChange(e.target.value)} className="input-field mt-2" />
    </label>
  )
}

function ProfileSelect({ label, value, onChange, options }) {
  return (
    <label className="block text-sm text-slate-700">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="input-field mt-2">
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </label>
  )
}

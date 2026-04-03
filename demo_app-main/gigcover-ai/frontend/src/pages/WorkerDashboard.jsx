import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'

const menuItems = ['Dashboard', 'Parametric', 'Policy', 'Claims', 'Transactions', 'Profile', 'Logout']

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
  const [parametric, setParametric] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [triggerEvents, setTriggerEvents] = useState([])

  const worker = dashboard.worker || {}
  const policy = dashboard.policy || {}
  const claims = dashboard.claims || []

  const dismissToast = () => setTimeout(() => setToast(null), 3200)

  const showToast = (kind, text) => {
    setToast({ kind, text })
    dismissToast()
  }

  const fetchParametricData = async () => {
    try {
      const [txnRes, evtRes] = await Promise.all([
        api.get('/parametric/transactions'),
        api.get('/parametric/trigger-events'),
      ])
      setTransactions(txnRes.data.transactions || [])
      setTriggerEvents(evtRes.data.trigger_events || [])
    } catch {
      // non-critical
    }
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
    fetchParametricData()

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

  const runParametricTrigger = async () => {
    setBusy(true)
    try {
      const pos = await new Promise((res, rej) =>
        navigator.geolocation
          ? navigator.geolocation.getCurrentPosition(res, rej, { timeout: 8000 })
          : rej(new Error('no geolocation'))
      ).catch(() => null)
      const payload = pos
        ? { latitude: pos.coords.latitude, longitude: pos.coords.longitude }
        : { latitude: Number(worker.latitude || 0), longitude: Number(worker.longitude || 0) }

      // Use new 5-trigger endpoint
      const { data } = await api.post('/triggers/check', payload)
      setParametric(data)

      if (!data.any_fired) {
        showToast('info', 'All clear — no income disruption triggers active right now.')
      } else {
        const approved = (data.payout_results || []).filter(r => r.decision === 'Approved')
        const blocked  = (data.payout_results || []).filter(r => r.decision === 'Blocked')
        if (approved.length) {
          showToast('success', `💰 ${approved.length} trigger(s) fired! ₹${data.total_payout?.toFixed(2)} auto-credited via UPI.`)
        } else if (blocked.length) {
          showToast('error', '⚠️ Payout blocked: fraud risk detected.')
        } else {
          showToast('info', 'Triggers evaluated. Check Triggers tab for details.')
        }
        // Show notifications
        ;(data.notifications || []).forEach(n => showToast('success', n))
      }
      await fetchParametricData()
      await fetchDashboard()
    } catch (err) {
      showToast('error', err.response?.data?.error || 'Trigger check failed.')
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
                  <button disabled={busy} onClick={() => { runParametricTrigger(); setActive('Parametric') }} className="secondary-btn bg-amber-100">
                    Run Parametric Check
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

        {active === 'Parametric' && (
          <div className="space-y-5">
            <div className="glass rounded-3xl p-6">
              <h2 className="font-outfit text-2xl font-semibold text-slate-900">5-Trigger Income Protection</h2>
              <p className="mt-1 text-sm text-slate-600">Automated checks for Rain • AQI • Heatwave • Flood/Storm • Low Demand. Zero-touch payouts when thresholds breach.</p>
              <button disabled={busy} onClick={runParametricTrigger} className="primary-btn mt-4">
                {busy ? '⏳ Checking all triggers...' : '⚡ Run All 5 Trigger Checks'}
              </button>
            </div>

            {parametric && (
              <>
                {/* Summary bar */}
                <div className={`rounded-2xl p-4 text-sm font-semibold ${
                  parametric.any_fired ? 'bg-amber-50 text-amber-900 border border-amber-200' : 'bg-green-50 text-green-800 border border-green-200'
                }`}>
                  {parametric.any_fired
                    ? `⚠️ ${parametric.fired_count} trigger(s) fired — Max income disruption: ${parametric.max_income_disruption_pct?.toFixed(1)}% — Total payout: ₹${parametric.total_payout?.toFixed(2) || '0'}`
                    : '✅ All clear — No income disruption triggers active'}
                </div>

                {/* Notifications */}
                {parametric.notifications?.length > 0 && (
                  <div className="space-y-2">
                    {parametric.notifications.map((n, i) => (
                      <div key={i} className="rounded-xl bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900 border border-amber-100">{n}</div>
                    ))}
                  </div>
                )}

                {/* All 5 trigger cards */}
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {(parametric.triggers || []).map((t, i) => (
                    <div key={i} className={`rounded-2xl border p-4 ${
                      t.fired && t.severity === 'high'   ? 'border-red-200 bg-red-50'
                      : t.fired && t.severity === 'medium' ? 'border-amber-200 bg-amber-50'
                      : t.fired                           ? 'border-yellow-200 bg-yellow-50'
                      : 'border-slate-100 bg-white'
                    }`}>
                      <div className="flex items-center justify-between">
                        <p className="font-semibold text-slate-900 text-sm">
                          {t.trigger_type === 'Heavy Rain'          ? '🌧️' :
                           t.trigger_type === 'High AQI'            ? '🌫️' :
                           t.trigger_type === 'Heatwave'            ? '🌡️' :
                           t.trigger_type === 'Flood / Storm'       ? '🌊' :
                           t.trigger_type === 'Low Platform Demand' ? '📉' : '⚡'} {t.trigger_type}
                        </p>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                          t.fired ? (t.severity === 'high' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700') : 'bg-slate-100 text-slate-500'
                        }`}>{t.fired ? t.severity.toUpperCase() : 'OK'}</span>
                      </div>
                      <p className="mt-2 text-xs text-slate-600">{t.description}</p>
                      <div className="mt-2 flex justify-between text-xs text-slate-500">
                        <span>Observed: <strong>{t.observed_value} {t.unit}</strong></span>
                        <span>Threshold: {t.threshold_value} {t.unit}</span>
                      </div>
                      {t.fired && (
                        <p className="mt-1 text-xs font-semibold text-red-600">Income disruption: ~{t.income_disruption_pct}%</p>
                      )}
                      <p className="mt-1 text-xs text-slate-400">Source: {t.source}</p>
                    </div>
                  ))}
                </div>

                {/* Payout results */}
                {parametric.payout_results?.length > 0 && (
                  <div className="glass rounded-3xl p-6">
                    <p className="mb-3 font-semibold text-slate-900">Payout Results</p>
                    <div className="space-y-2">
                      {parametric.payout_results.map((r, i) => (
                        <div key={i} className={`rounded-xl p-3 text-sm ${
                          r.decision === 'Approved' ? 'bg-green-50 text-green-800'
                          : r.decision === 'Blocked' ? 'bg-red-50 text-red-800'
                          : 'bg-slate-50 text-slate-700'
                        }`}>
                          <p className="font-semibold">{r.trigger_type} — {r.decision}</p>
                          {r.claim_id && <p>Claim: {r.claim_id} | Payout: ₹{Number(r.payout).toFixed(2)}</p>}
                          {r.transaction?.gateway_ref && <p className="text-xs opacity-70">Ref: {r.transaction.gateway_ref} | UTR: {r.transaction.utr || '-'}</p>}
                          {r.reason && <p className="text-xs">{r.reason}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Live data summary */}
                <div className="glass rounded-3xl p-6">
                  <p className="mb-3 font-semibold text-slate-900">Live Data Used</p>
                  <div className="grid gap-2 text-sm sm:grid-cols-3">
                    <Info label="Temperature" value={`${parametric.weather?.temperature ?? '-'}°C`} />
                    <Info label="Rain Probability" value={`${parametric.weather?.rain_probability ?? '-'}%`} />
                    <Info label="Wind Speed" value={`${parametric.weather?.wind_speed ?? '-'} m/s`} />
                    <Info label="Visibility" value={`${parametric.weather?.visibility ?? '-'} m`} />
                    <Info label="AQI" value={String(parametric.aqi?.aqi ?? '-')} />
                    <Info label="Demand Index" value={String(parametric.demand?.demand_index ?? '-')} />
                  </div>
                  <p className="mt-2 text-xs text-slate-400">Data source: {parametric.weather?.source || 'unknown'} • Evaluated: {parametric.evaluated_at?.slice(0,16)}</p>
                </div>
              </>
            )}

            {triggerEvents.length > 0 && (
              <div className="glass rounded-3xl p-6">
                <p className="mb-3 font-semibold text-slate-900">Recent Trigger Events (Your City)</p>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                    <thead><tr className="text-slate-500">
                      <th className="p-2">Type</th><th className="p-2">Observed</th><th className="p-2">Threshold</th><th className="p-2">Status</th><th className="p-2">Time</th>
                    </tr></thead>
                    <tbody>
                      {triggerEvents.map((e) => (
                        <tr key={e.id} className="border-t border-slate-100">
                          <td className="p-2">{e.trigger_type}</td>
                          <td className="p-2">{e.observed_value}</td>
                          <td className="p-2">{e.threshold_value}</td>
                          <td className="p-2">{e.status}</td>
                          <td className="p-2 text-xs text-slate-400">{e.triggered_at?.slice(0, 16)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {active === 'Transactions' && (
          <div className="glass rounded-3xl p-6">
            <h2 className="font-outfit text-2xl font-semibold text-slate-900">Transaction History</h2>
            <p className="mt-1 mb-4 text-sm text-slate-500">All payouts and premium payments with gateway references.</p>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead><tr className="text-slate-500">
                  <th className="p-2">Type</th><th className="p-2">Amount</th><th className="p-2">Method</th><th className="p-2">Status</th><th className="p-2">Ref</th><th className="p-2">Date</th>
                </tr></thead>
                <tbody>
                  {transactions.length === 0 && (
                    <tr><td colSpan={6} className="p-4 text-center text-slate-400">No transactions yet.</td></tr>
                  )}
                  {transactions.map((t) => (
                    <tr key={t.id} className="border-t border-slate-100">
                      <td className="p-2 capitalize">{t.txn_type}</td>
                      <td className="p-2">Rs {Number(t.amount).toFixed(2)}</td>
                      <td className="p-2">{t.method}</td>
                      <td className={`p-2 font-semibold ${
                        t.status === 'Success' ? 'text-green-700' : t.status === 'Failed' ? 'text-red-600' : 'text-slate-600'
                      }`}>{t.status}</td>
                      <td className="p-2 text-xs text-slate-400">{t.gateway_ref || '-'}</td>
                      <td className="p-2 text-xs text-slate-400">{t.created_at?.slice(0, 16)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
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

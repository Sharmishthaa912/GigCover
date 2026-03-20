import { useEffect, useMemo, useState } from 'react'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'
import { api } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend)

export default function AdminDashboard() {
  const [data, setData] = useState(null)
  const [settings, setSettings] = useState({ rainfall_threshold: 100, risk_weight: 1.0, disruption_type: 'Rainfall' })
  const [message, setMessage] = useState('')

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const response = await api.get('/dashboard-data')
        if (mounted) setData(response.data)
      } catch (error) {
        console.error('Error loading dashboard:', error)
      }
    })()

    return () => {
      mounted = false
    }
  }, [])

  const saveSettings = async () => {
    try {
      await api.post('/admin/settings', settings)
      setMessage('Settings updated successfully.')
      setTimeout(() => setMessage(''), 3000)
    } catch (error) {
      setMessage('Error updating settings.')
    }
  }

  const chartData = useMemo(() => {
    const risks = data?.risks || []
    return {
      labels: risks.map((item) => `U${item.user_id}`),
      datasets: [
        {
          label: 'Risk Score',
          data: risks.map((item) => item.risk_score),
          borderColor: '#a78bfa',
          backgroundColor: '#93c5fd',
          tension: 0.35,
        },
      ],
    }
  }, [data])

  const payoutsData = useMemo(() => {
    const claims = data?.claims || []
    return {
      labels: claims.map((claim) => claim.claim_id),
      datasets: [
        {
          label: 'Payout Amount',
          data: claims.map((claim) => claim.payout),
          backgroundColor: '#86efac',
        },
      ],
    }
  }, [data])

  if (!data) {
    return <div className="px-8 py-16 text-slate-700">Loading admin panel...</div>
  }

  return (
    <div className="mx-auto max-w-7xl px-4 pb-12 pt-8">
      {message && <div className="glass mb-4 rounded-2xl p-4 text-sm text-slate-800">{message}</div>}

      <div className="grid gap-4 md:grid-cols-3">
        <Metric title="Total Users" value={data.analytics.total_users} />
        <Metric title="Total Claims" value={data.analytics.total_claims} />
        <Metric title="Total Payouts" value={`Rs ${Number(data.analytics.total_payouts).toFixed(2)}`} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <div className="glass rounded-3xl p-6">
          <h2 className="font-outfit text-2xl font-semibold text-slate-800">Risk Score Trend</h2>
          <Line data={chartData} />
        </div>

        <div className="glass rounded-3xl p-6">
          <h2 className="font-outfit text-2xl font-semibold text-slate-800">Claim Payouts</h2>
          <Bar data={payoutsData} />
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <div className="glass rounded-3xl p-6">
          <h3 className="font-space text-lg font-semibold text-slate-800">Admin Controls</h3>
          <label className="mt-4 block text-sm text-slate-700">Add New Disruption Type</label>
          <input
            className="input-field mt-2"
            value={settings.disruption_type}
            onChange={(e) => setSettings((prev) => ({ ...prev, disruption_type: e.target.value }))}
          />

          <label className="mt-4 block text-sm text-slate-700">Modify Rainfall Threshold</label>
          <input
            type="number"
            className="input-field mt-2"
            value={settings.rainfall_threshold}
            onChange={(e) => setSettings((prev) => ({ ...prev, rainfall_threshold: Number(e.target.value) }))}
          />

          <label className="mt-4 block text-sm text-slate-700">Modify Risk Weight</label>
          <input
            type="number"
            step="0.1"
            className="input-field mt-2"
            value={settings.risk_weight}
            onChange={(e) => setSettings((prev) => ({ ...prev, risk_weight: Number(e.target.value) }))}
          />

          <button onClick={saveSettings} className="primary-btn mt-6">
            Save Settings
          </button>
        </div>

        <div className="glass rounded-3xl p-6">
          <h3 className="font-space text-lg font-semibold text-slate-800">Live Records</h3>
          <p className="mt-4 text-sm font-semibold text-slate-700">Users</p>
          <div className="mt-2 max-h-40 overflow-y-auto rounded-xl bg-white/70 p-3 text-sm text-slate-700">
            {(data.users || []).map((user) => (
              <p key={user.id}>
                {user.name} ({user.role}) - {user.email}
              </p>
            ))}
          </div>

          <p className="mt-4 text-sm font-semibold text-slate-700">Claims</p>
          <div className="mt-2 max-h-40 overflow-y-auto rounded-xl bg-white/70 p-3 text-sm text-slate-700">
            {(data.claims || []).map((claim) => (
              <p key={claim.claim_id}>
                {claim.claim_id} | {claim.trigger_type} | Rs {Number(claim.payout).toFixed(2)}
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function Metric({ title, value }) {
  return (
    <div className="rounded-2xl bg-gradient-to-r from-[#c4b5fd] via-[#bfdbfe] to-[#bbf7d0] p-5 shadow-md transition duration-300 hover:shadow-lg">
      <p className="text-sm text-slate-600">{title}</p>
      <p className="font-outfit text-3xl font-bold text-slate-800">{value}</p>
    </div>
  )
}
